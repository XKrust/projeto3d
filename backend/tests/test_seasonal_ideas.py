import json
from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from app import clock
from app.collectors.base import CollectorError
from app.constants import GLOBAL
from app.hype.seasonal import event_ideas, load_events, top_models, upcoming_events
from app.hype.seasonal_ideas import (
    update_seasonal_listings,
    update_seasonal_signals,
)
from app.models import RawItem, SeasonalIdeaSignal, SeasonalListing

DAY = date(2026, 9, 27)


def _event(slug):
    return next(e for e in load_events() if e["slug"] == slug)


def _item(session, *, title, source="sketchfab", country=GLOBAL, metric=10.0, day=DAY, tags=()):
    session.add(
        RawItem(source=source, external_id=f"{source}-{title}-{country}-{day}", country=country,
                day=day, title=title, tags_json=json.dumps(list(tags)), metric=metric)
    )
    session.commit()


class FakeCounter:
    def __init__(self, counts=None, failing=()):
        self.counts = counts or {}
        self.failing = set(failing)
        self.queries: list[str] = []

    def count_listings(self, query: str) -> int:
        self.queries.append(query)
        if query in self.failing:
            raise CollectorError("Falha simulada")
        return self.counts.get(query, 5)


def test_ideas_resolved_from_idea_set():
    ideas = event_ideas(_event("halloween"))

    names = [i["name"] for i in ideas]
    assert "Caveira" in names
    skull = next(i for i in ideas if i["name"] == "Caveira")
    assert skull["query"] == "skull"
    assert "caveira" in skull["keywords"]
    assert len(ideas) >= 5


def test_every_event_has_at_least_5_ideas():
    for event in load_events():
        assert len(event_ideas(event)) >= 5, event["slug"]


def test_idea_signal_matches_keywords_last_30_days(session):
    _item(session, title="Articulated Skull keychain", metric=40)
    _item(session, title="caveira mexicana decorativa", metric=10)
    _item(session, title="Skull lamp", metric=99, day=DAY - timedelta(days=45))  # velho demais
    _item(session, title="skullcandy headphones", metric=500)  # não é a palavra "skull"
    _item(session, title="Skull", source="google_trends", country="JP", metric=1000)  # outro país

    update_seasonal_signals(session, DAY)

    row = session.exec(
        select(SeasonalIdeaSignal).where(SeasonalIdeaSignal.idea == "Caveira", SeasonalIdeaSignal.country == "BR")
    ).one()
    assert row.signal == 50
    jp = session.exec(
        select(SeasonalIdeaSignal).where(SeasonalIdeaSignal.idea == "Caveira", SeasonalIdeaSignal.country == "JP")
    ).one()
    assert jp.signal == 1050


def test_update_seasonal_signals_runs_once_per_day(session):
    _item(session, title="skull", metric=10)
    update_seasonal_signals(session, DAY)
    _item(session, title="another skull", metric=10)
    update_seasonal_signals(session, DAY)

    row = session.exec(
        select(SeasonalIdeaSignal).where(SeasonalIdeaSignal.idea == "Caveira", SeasonalIdeaSignal.country == "BR")
    ).one()
    assert row.signal == 10


def test_update_seasonal_listings_only_upcoming_events(session, monkeypatch):
    counter = FakeCounter()

    update_seasonal_listings(session, {"cults3d": counter}, DAY, lead_days=21, modeling_days=7)

    # Halloween (comece até 03/10) está nos próximos 60 dias; Carnaval não.
    assert "skull" in counter.queries
    assert "carnival mask" not in counter.queries
    assert len(counter.queries) <= 20
    rows = session.exec(select(SeasonalListing)).all()
    assert {r.platform for r in rows} == {"cults3d"}


def test_update_seasonal_listings_skips_failed_term(session):
    counter = FakeCounter(failing={"skull"})

    update_seasonal_listings(session, {"cults3d": counter}, DAY, lead_days=21, modeling_days=7)

    terms = {r.term for r in session.exec(select(SeasonalListing)).all()}
    assert "skull" not in terms
    assert "pumpkin" in terms


def _signal(session, idea, value, country="BR"):
    session.add(SeasonalIdeaSignal(idea=idea, country=country, day=DAY, signal=value))
    session.commit()


def _listing(session, term, count, platform="cults3d"):
    session.add(SeasonalListing(term=term, platform=platform, day=DAY, count=count))
    session.commit()


WEIGHTS = {"demand": 0.40, "momentum": 0.25, "saturation": 0.35}


def test_top_models_ranked_by_opportunity(session):
    _signal(session, "Caveira", 500)
    _signal(session, "Abóbora", 100)
    _signal(session, "Bruxa", 300)
    _listing(session, "skull", 900)
    _listing(session, "pumpkin", 5)

    models = top_models(session, _event("halloween"), "BR", DAY, date(2026, 10, 31),
                        lead_days=21, modeling_days=7, weights=WEIGHTS, names={"cults3d": "Cults3D"})

    assert len(models) == 5
    measured = [m for m in models if m["measured"]]
    opps = [m["opportunity"] for m in measured]
    assert opps == sorted(opps, reverse=True)
    skull = next(m for m in models if m["name"] == "Caveira")
    assert skull["competition"] == {"Cults3D": 900}
    assert skull["sale_chance"] in {"Alta", "Média", "Baixa"}


def test_unmeasured_ideas_have_no_chance(session):
    models = top_models(session, _event("halloween"), "BR", DAY, date(2026, 10, 31),
                        lead_days=21, modeling_days=7, weights=WEIGHTS, names={})

    assert len(models) == 5
    assert all(m["measured"] is False for m in models)
    assert all(m["sale_chance"] is None and m["opportunity"] is None for m in models)
    # sem dados: ordem do YAML
    assert [m["name"] for m in models] == [i["name"] for i in event_ideas(_event("halloween"))][:5]


def test_upcoming_events_themes_are_idea_names():
    events = {e["slug"]: e for e in upcoming_events("BR", DAY, lead_days=21, modeling_days=7)}

    assert "Caveira" in events["halloween"]["themes"]


def test_api_seasonal_includes_top5(client, engine, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: DAY)
    with Session(engine) as session:
        _signal(session, "Caveira", 500)

    body = client.get("/api/seasonal?country=BR").json()

    halloween = next(e for e in body["events"] if e["slug"] == "halloween")
    assert len(halloween["top_models"]) == 5
    assert halloween["top_models"][0]["name"] == "Caveira"
    assert halloween["top_models"][0]["measured"] is True
    assert set(halloween["top_models"][0]) >= {
        "name", "query", "opportunity", "sale_chance", "measured", "competition", "signal"
    }


@pytest.mark.parametrize("slug", ["halloween", "natal", "tanabata", "dia_das_maes"])
def test_idea_queries_are_unique_per_event(slug):
    queries = [i["query"] for i in event_ideas(_event(slug))]
    assert len(queries) == len(set(queries))
