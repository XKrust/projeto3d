import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

import app.collectors as collectors_pkg
from app import clock
from app import pipeline
from app import scheduler as scheduler_mod
from app.api import sources as sources_api
from app.collectors.base import Collector, CollectedItem, CollectorError
from app.constants import GLOBAL
from app.main import create_app
from app.models import RawItem, Topic, TopicItem, TopicListing, TopicScore, TopicSignal
from app.pipeline import compute_scores, make_after, run_pipeline, update_listings
from app.platforms import seed_platforms
from app.settings_store import update_settings

DAY = date(2026, 9, 26)


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: DAY)


@pytest.fixture()
def platforms(session):
    seed_platforms(session)


def _topic(session, name):
    topic = Topic(slug=name.lower().replace(" ", "-"), name=name, is_candidate=False, created_day=DAY)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def _signal(session, topic, value, *, source="google_trends", country="BR", day=DAY):
    session.add(TopicSignal(topic_id=topic.id, source=source, country=country, day=day, value=value))
    session.commit()


def _raw_item(session, *, source, external_id="x", country=GLOBAL, day=DAY, title="Item"):
    item = RawItem(source=source, external_id=external_id, country=country, day=day, title=title, metric=1.0)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def _scores(session, *, country=None, platform=None, topic=None):
    query = select(TopicScore).where(TopicScore.day == DAY)
    if country is not None:
        query = query.where(TopicScore.country == country)
    if platform is not None:
        query = query.where(TopicScore.platform == platform)
    if topic is not None:
        query = query.where(TopicScore.topic_id == topic.id)
    return session.exec(query).all()


# ---------------------------------------------------------------- compute_scores


def test_topic_with_highest_signal_has_highest_demand_in_br(session, platforms):
    _raw_item(session, source="sketchfab")
    low = _topic(session, "Baixo")
    mid = _topic(session, "Medio")
    high = _topic(session, "Alto")
    _signal(session, low, 10)
    _signal(session, mid, 50)
    _signal(session, high, 90)

    written = compute_scores(session, DAY)

    assert written == 3  # 3 topicos x BR x sketchfab
    demand = {s.topic_id: s.demand for s in _scores(session, country="BR", platform="sketchfab")}
    assert demand[high.id] > demand[mid.id] > demand[low.id]


def test_global_signal_counts_for_br_and_jp(session, platforms):
    _raw_item(session, source="sketchfab")
    update_settings(session, {"countries": ["BR", "JP", "US"]})
    only_global = _topic(session, "So Global")
    only_us = _topic(session, "So US")
    _signal(session, only_global, 42, source="reddit", country=GLOBAL)
    _signal(session, only_us, 10, country="US")

    compute_scores(session, DAY)

    assert {s.country for s in _scores(session, topic=only_global)} == {"BR", "JP", "US"}
    # sem sinal no pais (nem GLOBAL) na janela: nenhuma linha
    assert {s.country for s in _scores(session, topic=only_us)} == {"US"}


def test_topic_without_listing_has_saturation_50(session, platforms):
    _raw_item(session, source="sketchfab")
    a = _topic(session, "A")
    b = _topic(session, "B")
    c = _topic(session, "C")
    for topic in (a, b, c):
        _signal(session, topic, 10)
    session.add(TopicListing(topic_id=a.id, platform="sketchfab", day=DAY - timedelta(days=2), count=5))
    session.add(TopicListing(topic_id=a.id, platform="sketchfab", day=DAY, count=100))  # mais recente
    session.add(TopicListing(topic_id=b.id, platform="sketchfab", day=DAY, count=20))
    session.commit()

    compute_scores(session, DAY)

    saturation = {s.topic_id: s.saturation for s in _scores(session, country="BR", platform="sketchfab")}
    assert saturation[c.id] == 50.0
    assert saturation[a.id] == 75.0  # 100 anuncios > 20 anuncios
    assert saturation[b.id] == 25.0


def test_growing_ten_day_series_peaks_today_plus_10(session, platforms):
    _raw_item(session, source="sketchfab")
    growing = _topic(session, "Crescente")
    falling = _topic(session, "Caindo")
    steady = _topic(session, "Estavel")
    for i in range(10):
        day = DAY - timedelta(days=9 - i)
        _signal(session, growing, 10 + 10 * i, day=day)  # 10 .. 100
        _signal(session, falling, 100 - 10 * i, day=day)  # 100 .. 10
        _signal(session, steady, 55, day=day)

    compute_scores(session, DAY)

    by_topic = {s.topic_id: s for s in _scores(session, country="BR", platform="sketchfab")}
    assert by_topic[growing.id].peak_day == DAY + timedelta(days=10)
    assert by_topic[growing.id].momentum_raw > 0
    assert by_topic[growing.id].fit_window == 1.0  # pico (hoje+10) >= entrega (hoje+7)
    assert by_topic[falling.id].peak_day == DAY
    assert by_topic[falling.id].momentum_raw < 0
    assert by_topic[falling.id].fit_window == 0.5  # 7 dias de atraso


def test_compute_scores_twice_does_not_duplicate_rows(session, platforms):
    _raw_item(session, source="sketchfab")
    _raw_item(session, source="cults3d")
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)

    first = compute_scores(session, DAY)
    second = compute_scores(session, DAY)

    assert first == second == 2
    assert len(session.exec(select(TopicScore)).all()) == 2


def test_only_platforms_with_data_are_scored(session, platforms):
    _raw_item(session, source="cults3d", day=DAY - timedelta(days=30))
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)

    compute_scores(session, DAY)

    assert {s.platform for s in _scores(session)} == {"cults3d"}


def test_score_fields_follow_the_formulas(session, platforms):
    raw = _raw_item(session, source="sketchfab", day=DAY - timedelta(days=3))
    present = _topic(session, "Presente")
    absent = _topic(session, "Ausente")
    session.add(TopicItem(topic_id=present.id, raw_item_id=raw.id))
    session.commit()
    _signal(session, present, 10, source="sketchfab")
    _signal(session, absent, 10, source="cults3d")

    compute_scores(session, DAY)

    by_topic = {s.topic_id: s for s in _scores(session, country="BR", platform="sketchfab")}
    # forca do Sketchfab no BR = 0.5 (seed); presente -> 1.0, ausente -> 0.5
    assert by_topic[present.id].fit_platform == pytest.approx(0.5)
    assert by_topic[absent.id].fit_platform == pytest.approx(0.25)

    score = by_topic[present.id]
    # sketchfab + cults3d somam no grupo "platforms": empate -> demanda 50
    assert score.demand == 50.0
    # so ha dado hoje: anterior = 0, recente > 0 -> momentum_raw = 2 -> score 100
    assert score.momentum_raw == 2.0
    assert score.momentum == pytest.approx(100.0)
    assert score.saturation == 50.0
    assert score.fit_window == 1.0
    assert score.opportunity == pytest.approx(round(0.40 * 50 + 0.25 * 100 + 0.35 * 50, 1))


def test_platform_sources_weigh_equally_regardless_of_scale(session, platforms):
    # BOOTH mede favoritos (dezenas de milhares); CGTrader, a posicao no ranking (1 a 50).
    # Cada topico lidera uma fonte: a demanda dos dois tem que empatar.
    _raw_item(session, source="booth", country="JP")
    _raw_item(session, source="cgtrader")
    a = _topic(session, "Tema A")
    b = _topic(session, "Tema B")
    _signal(session, a, 50000, source="booth", country="JP")
    _signal(session, a, 1, source="cgtrader", country=GLOBAL)
    _signal(session, b, 40000, source="booth", country="JP")
    _signal(session, b, 50, source="cgtrader", country=GLOBAL)

    compute_scores(session, DAY)

    demand = {s.topic_id: s.demand for s in _scores(session, country="JP", platform="booth")}
    assert demand[a.id] == demand[b.id]


# ---------------------------------------------------------------- update_listings


class FakeCounter:
    def __init__(self, counts=None, error=None):
        self.counts = counts or {}
        self.error = error
        self.queries: list[str] = []

    def count_listings(self, query: str) -> int:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.counts.get(query, 7)


def test_failing_counter_does_not_stop_other_platforms(session):
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)
    ok = FakeCounter({"Tema": 12})
    broken = FakeCounter(error=CollectorError("Falha simulada"))

    written = update_listings(session, {"cults3d": broken, "sketchfab": ok}, DAY, 50)

    assert written == 1
    listings = session.exec(select(TopicListing)).all()
    assert [(row.platform, row.topic_id, row.count) for row in listings] == [("sketchfab", topic.id, 12)]


class FlakyCounter(FakeCounter):
    """Falha so nos termos de `failing`."""

    def __init__(self, counts, failing):
        super().__init__(counts)
        self.failing = set(failing)

    def count_listings(self, query: str) -> int:
        self.queries.append(query)
        if query in self.failing:
            raise CollectorError("Falha simulada")
        return self.counts.get(query, 7)


def test_failing_term_only_skips_that_topic(session):
    good = _topic(session, "Bom")
    bad = _topic(session, "Ruim")
    _signal(session, good, 10)
    _signal(session, bad, 20)
    counter = FlakyCounter({"Bom": 12}, failing={"Ruim"})

    written = update_listings(session, {"booth": counter}, DAY, 50)

    assert written == 1
    listings = session.exec(select(TopicListing)).all()
    assert [(row.platform, row.topic_id, row.count) for row in listings] == [("booth", good.id, 12)]


def test_platform_is_abandoned_after_3_consecutive_failures(session):
    names = [f"Tema {i}" for i in range(6)]
    for value, name in enumerate(names):
        _signal(session, _topic(session, name), 100 - value)
    counter = FakeCounter(error=CollectorError("Fora do ar"))

    written = update_listings(session, {"booth": counter}, DAY, 50)

    assert written == 0
    assert len(counter.queries) == 3


def test_update_listings_uses_signal_sum_when_there_is_no_score(session):
    small = _topic(session, "Pequeno")
    big = _topic(session, "Grande")
    medium = _topic(session, "Medio")
    _signal(session, small, 5)
    _signal(session, big, 30)
    _signal(session, big, 30, source="reddit", country=GLOBAL)
    _signal(session, medium, 50)
    counter = FakeCounter()

    written = update_listings(session, {"sketchfab": counter}, DAY, 2)

    assert written == 2
    assert counter.queries == ["Grande", "Medio"]


def test_update_listings_uses_opportunity_of_last_scored_day(session):
    a = _topic(session, "A")
    b = _topic(session, "B")
    c = _topic(session, "C")
    old_day = DAY - timedelta(days=2)
    for topic, opp in ((a, 30.0), (b, 80.0), (c, 60.0)):
        session.add(
            TopicScore(
                topic_id=topic.id, country="BR", platform="sketchfab", day=old_day,
                demand=0, momentum=0, momentum_raw=0, saturation=0, peak_day=old_day,
                fit_window=1, fit_platform=1, opportunity=opp,
            )
        )
    session.commit()
    _signal(session, a, 1000)  # o sinal do dia nao importa quando ja ha score
    counter = FakeCounter()

    update_listings(session, {"sketchfab": counter}, DAY, 2)

    assert counter.queries == ["B", "C"]


def test_update_listings_upserts_same_day(session):
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)

    update_listings(session, {"sketchfab": FakeCounter({"Tema": 1})}, DAY, 50)
    update_listings(session, {"sketchfab": FakeCounter({"Tema": 9})}, DAY, 50)

    rows = session.exec(select(TopicListing)).all()
    assert [(row.count) for row in rows] == [9]


# ---------------------------------------------------------------- run_pipeline / make_after


def test_run_pipeline_extracts_counts_once_per_day_scores_and_enriches(session, platforms):
    _raw_item(session, source="google_trends", external_id="t1", country="BR", title="Nova Serie Qualquer")
    _raw_item(session, source="sketchfab", external_id="s1", title="Nova Serie Qualquer figure")
    counter = FakeCounter()
    enriched: list[bool] = []

    run_pipeline(session, {"sketchfab": counter}, enrich=lambda s: enriched.append(True))
    run_pipeline(session, {"sketchfab": counter})

    topic = session.exec(select(Topic).where(Topic.name == "Nova Serie Qualquer")).one()
    assert counter.queries == ["Nova Serie Qualquer"]  # 2a rodada: ja ha TopicListing do dia
    assert session.exec(select(TopicListing)).one().topic_id == topic.id
    assert {s.country for s in _scores(session, topic=topic)} == {"BR", "US", "GB", "DE", "FR", "ES", "JP"}
    assert enriched == [True]


class FakePlatformCollector(Collector):
    name = "fake_platform"
    label = "Fake plataforma"
    kind = "api"
    platform = "fake_platform"
    needs_key = ()

    def collect(self) -> list[CollectedItem]:
        return []

    def count_listings(self, query: str) -> int:
        return 3


class FakeKeyedPlatformCollector(FakePlatformCollector):
    name = "fake_keyed"
    platform = "fake_keyed"
    needs_key = ("cults3d_key",)


class FakeNoCounterCollector(Collector):
    name = "fake_no_counter"
    label = "Fake sem contagem"
    kind = "api"
    platform = "fake_no_counter"

    def collect(self) -> list[CollectedItem]:
        return []


class FakeNotPlatformCollector(FakePlatformCollector):
    name = "fake_not_platform"
    platform = None


def test_make_after_builds_counters_only_for_eligible_collectors(session, monkeypatch):
    monkeypatch.setattr(
        collectors_pkg,
        "ALL_COLLECTORS",
        [FakePlatformCollector, FakeKeyedPlatformCollector, FakeNoCounterCollector, FakeNotPlatformCollector],
    )
    captured: dict = {}

    def fake_run_pipeline(session, counters, *, enrich=None):
        captured["counters"] = counters
        captured["enrich"] = enrich

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run_pipeline)
    http = object()
    settings = {"api_keys": {"cults3d_key": ""}}

    after = make_after(settings, http)
    after(session)

    assert list(captured["counters"]) == ["fake_platform"]
    counter = captured["counters"]["fake_platform"]
    assert isinstance(counter, FakePlatformCollector)
    assert counter.http is http
    assert captured["enrich"] is None

    settings["api_keys"]["cults3d_key"] = "abc"
    make_after(settings, http)(session)
    assert list(captured["counters"]) == ["fake_platform", "fake_keyed"]


def test_make_after_wires_enrich_when_gemini_key_present(session, monkeypatch):
    import app.topics.enrich as enrich_mod
    from app.ai.provider import GeminiTextProvider

    monkeypatch.setattr(collectors_pkg, "ALL_COLLECTORS", [])
    captured: dict = {}
    monkeypatch.setattr(
        enrich_mod,
        "enrich_topics",
        lambda s, provider, day: captured.update(session=s, provider=provider, day=day),
    )
    http = object()
    settings = {"api_keys": {"gemini": "chave-secreta"}, "gemini_model": "gemini-2.5-flash"}

    make_after(settings, http)(session)

    assert captured["session"] is session
    assert captured["day"] == DAY
    assert isinstance(captured["provider"], GeminiTextProvider)
    assert captured["provider"].api_key == "chave-secreta"


def test_make_after_leaves_enrich_none_without_gemini_key(session, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        pipeline, "run_pipeline", lambda s, counters, *, enrich=None: captured.update(enrich=enrich)
    )
    settings = {"api_keys": {}}

    make_after(settings, object())(session)

    assert captured["enrich"] is None


def test_post_collect_passes_pipeline_after(client, monkeypatch):
    captured: dict = {}

    def fake_start(session_factory, **kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(sources_api, "start_cycle_in_background", fake_start)

    response = client.post("/api/collect?source=reddit")

    assert response.json()["started"] is True
    assert captured["only"] == "reddit"
    assert captured["after"] is pipeline.run_after_cycle


def test_run_after_cycle_runs_pipeline_with_fresh_settings(session, monkeypatch):
    monkeypatch.setattr(collectors_pkg, "ALL_COLLECTORS", [FakePlatformCollector])
    captured: dict = {}
    monkeypatch.setattr(
        pipeline, "run_pipeline", lambda s, counters, *, enrich=None: captured.update(counters=counters)
    )

    pipeline.run_after_cycle(session)

    assert list(captured["counters"]) == ["fake_platform"]


# ---------------------------------------------------------------- agendador


def test_build_scheduler_has_10_minute_job_and_run_30s_after_start():
    factory = object()
    sched = scheduler_mod.build_scheduler(factory)  # montado, mas nao iniciado (sem thread)

    jobs = {job.id: job for job in sched.get_jobs()}
    assert set(jobs) == {"coleta_periodica", "coleta_inicial"}
    assert jobs["coleta_periodica"].trigger.interval == timedelta(minutes=10)
    assert jobs["coleta_inicial"].trigger.run_date is not None
    assert jobs["coleta_periodica"].func is scheduler_mod.run_scheduled_cycle
    assert jobs["coleta_inicial"].func is scheduler_mod.run_scheduled_cycle
    assert jobs["coleta_periodica"].args == jobs["coleta_inicial"].args == (factory,)
    assert sched.running is False


def test_scheduler_job_starts_cycle_with_pipeline_after(monkeypatch):
    captured: dict = {}

    def fake_start(session_factory, **kwargs):
        captured["factory"] = session_factory
        captured.update(kwargs)
        return True

    monkeypatch.setattr(scheduler_mod, "start_cycle_in_background", fake_start)
    factory = object()

    scheduler_mod.run_scheduled_cycle(factory)

    assert captured == {"factory": factory, "after": pipeline.run_after_cycle}


class FakeScheduler:
    def __init__(self):
        self.shutdown_calls = 0

    def shutdown(self, wait=True):
        self.shutdown_calls += 1


def test_lifespan_starts_and_stops_scheduler(engine, monkeypatch):
    fake = FakeScheduler()
    started: list = []

    def fake_start_scheduler(session_factory):
        started.append(session_factory)
        return fake

    monkeypatch.setattr(scheduler_mod, "start_scheduler", fake_start_scheduler)
    monkeypatch.delenv("RADAR_NO_SCHEDULER", raising=False)

    with TestClient(create_app(engine=engine)):
        assert len(started) == 1
        assert fake.shutdown_calls == 0

    assert fake.shutdown_calls == 1


def test_lifespan_skips_scheduler_when_disabled(engine, monkeypatch):
    started: list = []
    monkeypatch.setattr(scheduler_mod, "start_scheduler", lambda f: started.append(f))
    monkeypatch.setenv("RADAR_NO_SCHEDULER", "1")

    with TestClient(create_app(engine=engine)):
        pass

    assert started == []


def test_run_pipeline_updates_hype_listings(session, platforms, monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "update_hype_listings", lambda s, counters, day: calls.append((counters, day)))
    counters = {"cults3d": FakeCounter()}

    run_pipeline(session, counters)

    assert calls == [(counters, DAY)]
