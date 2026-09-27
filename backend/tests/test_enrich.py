import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.ai.provider import AIQuotaError, GeminiTextProvider, get_text_provider
from app.constants import GLOBAL
from app.models import RawItem, Topic, TopicItem, TopicListing, TopicScore, TopicSignal
from app.topics.enrich import enrich_topics, merge_topics

DAY = date(2026, 9, 26)


def _topic(session, name, *, category="outros"):
    topic = Topic(
        slug=name.lower().replace(" ", "-"), name=name, category=category, is_candidate=False, created_day=DAY
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def _signal(session, topic, value, *, source="google_trends", country="BR", day=DAY):
    session.add(TopicSignal(topic_id=topic.id, source=source, country=country, day=day, value=value))
    session.commit()


def _raw_item(session, *, source="sketchfab", external_id="x", country=GLOBAL, day=DAY, title="Item"):
    item = RawItem(source=source, external_id=external_id, country=country, day=day, title=title, metric=1.0)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


class FakeProvider:
    """`TextProvider` de teste: devolve `response` ou lanca `error`, e conta chamadas."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0
        self.prompts: list[str] = []

    def generate_json(self, prompt: str) -> dict:
        self.calls += 1
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.response


# ---------------------------------------------------------------- get_text_provider


def test_get_text_provider_without_key_returns_none():
    assert get_text_provider({"api_keys": {"gemini": ""}}) is None
    assert get_text_provider({}) is None


def test_get_text_provider_with_key_returns_gemini_provider():
    provider = get_text_provider({"api_keys": {"gemini": "abc"}, "gemini_model": "gemini-x"})

    assert isinstance(provider, GeminiTextProvider)
    assert provider.api_key == "abc"
    assert provider.model == "gemini-x"


# ---------------------------------------------------------------- GeminiTextProvider


def test_gemini_provider_parses_json_response(monkeypatch):
    import app.ai.provider as provider_module

    captured: dict = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text=json.dumps({"ok": True}))

    class FakeClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.models = FakeModels()

    monkeypatch.setattr(provider_module, "Client", FakeClient)

    provider = GeminiTextProvider("secret", "gemini-2.5-flash")
    result = provider.generate_json("um prompt")

    assert result == {"ok": True}
    assert captured["api_key"] == "secret"
    assert captured["model"] == "gemini-2.5-flash"
    assert captured["contents"] == "um prompt"
    assert captured["config"] == {"response_mime_type": "application/json"}


def test_gemini_provider_maps_429_resource_exhausted_to_ai_quota_error(monkeypatch):
    import app.ai.provider as provider_module
    from google.genai.errors import ClientError

    class FakeModels:
        def generate_content(self, **kwargs):
            raise ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "cota excedida"}})

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(provider_module, "Client", FakeClient)

    provider = GeminiTextProvider("secret", "gemini-2.5-flash")
    with pytest.raises(AIQuotaError):
        provider.generate_json("um prompt")


def test_gemini_provider_reraises_other_api_errors(monkeypatch):
    import app.ai.provider as provider_module
    from google.genai.errors import ClientError

    class FakeModels:
        def generate_content(self, **kwargs):
            raise ClientError(400, {"error": {"status": "INVALID_ARGUMENT", "message": "prompt invalido"}})

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(provider_module, "Client", FakeClient)

    provider = GeminiTextProvider("secret", "gemini-2.5-flash")
    with pytest.raises(ClientError):
        provider.generate_json("um prompt")


# ---------------------------------------------------------------- merge_topics


def test_merge_topics_sums_conflicting_signals_and_removes_topic(session):
    fern = _topic(session, "Fern")
    frieren = _topic(session, "Fern Frieren")
    _signal(session, fern, 5, source="google_trends", country="BR", day=DAY)
    _signal(session, frieren, 7, source="google_trends", country="BR", day=DAY)
    _signal(session, fern, 3, source="reddit", country=GLOBAL, day=DAY)

    merge_topics(session, frieren.id, fern.id)

    assert session.get(Topic, fern.id) is None
    signals = session.exec(select(TopicSignal).where(TopicSignal.topic_id == frieren.id)).all()
    by_source = {(s.source, s.country): s.value for s in signals}
    assert by_source[("google_trends", "BR")] == 12
    assert by_source[("reddit", GLOBAL)] == 3


def test_merge_topics_keeps_larger_listing_dedupes_items_and_drops_scores(session):
    keep = _topic(session, "Fern Frieren")
    merge = _topic(session, "Fern")
    item1 = _raw_item(session, external_id="a", title="Fern figure")
    item2 = _raw_item(session, external_id="b", title="Fern figure 2")
    session.add(TopicItem(topic_id=keep.id, raw_item_id=item1.id))
    session.add(TopicItem(topic_id=merge.id, raw_item_id=item1.id))  # ja vinculado ao keep tambem
    session.add(TopicItem(topic_id=merge.id, raw_item_id=item2.id))
    session.add(TopicListing(topic_id=keep.id, platform="sketchfab", day=DAY, count=5))
    session.add(TopicListing(topic_id=merge.id, platform="sketchfab", day=DAY, count=20))
    session.add(
        TopicScore(
            topic_id=merge.id, country="BR", platform="sketchfab", day=DAY,
            demand=0, momentum=0, momentum_raw=0, saturation=0, peak_day=DAY,
            fit_window=0, fit_platform=0, opportunity=0,
        )
    )
    session.commit()

    merge_topics(session, keep.id, merge.id)

    items = session.exec(select(TopicItem).where(TopicItem.topic_id == keep.id)).all()
    assert {i.raw_item_id for i in items} == {item1.id, item2.id}
    listing = session.exec(select(TopicListing).where(TopicListing.topic_id == keep.id)).one()
    assert listing.count == 20
    assert session.exec(select(TopicScore).where(TopicScore.topic_id == merge.id)).all() == []
    aliases = json.loads(session.get(Topic, keep.id).aliases_json)
    assert "fern" in aliases


# ---------------------------------------------------------------- enrich_topics


def test_enrich_topics_merges_fern_into_fern_frieren(session):
    fern = _topic(session, "Fern")
    frieren = _topic(session, "Fern Frieren")
    _signal(session, fern, 5)
    _signal(session, frieren, 7)
    provider = FakeProvider(response={"merges": [{"keep": "fern-frieren", "merge": ["fern"]}], "reasons": {}})

    merged, reasons = enrich_topics(session, provider, DAY)

    assert (merged, reasons) == (1, 0)
    remaining = session.exec(select(Topic)).all()
    assert [t.slug for t in remaining] == ["fern-frieren"]
    signal = session.exec(select(TopicSignal).where(TopicSignal.topic_id == frieren.id)).one()
    assert signal.value == 12


def test_enrich_topics_truncates_reason_to_140_chars(session):
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)
    long_reason = "x" * 200
    provider = FakeProvider(response={"merges": [], "reasons": {"tema": long_reason}})

    merged, reasons = enrich_topics(session, provider, DAY)

    assert (merged, reasons) == (0, 1)
    session.refresh(topic)
    assert topic.reason == "x" * 140
    assert topic.reason_day == DAY


def test_enrich_topics_ignores_unknown_slug(session):
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)
    provider = FakeProvider(
        response={"merges": [{"keep": "tema", "merge": ["desconhecido"]}], "reasons": {"desconhecido": "x"}}
    )

    merged, reasons = enrich_topics(session, provider, DAY)

    assert (merged, reasons) == (0, 0)
    remaining = session.exec(select(Topic)).all()
    assert len(remaining) == 1
    assert remaining[0].reason is None


def test_enrich_topics_does_not_call_provider_twice_same_day(session):
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)
    provider = FakeProvider(response={"merges": [], "reasons": {}})

    enrich_topics(session, provider, DAY)
    enrich_topics(session, provider, DAY)

    assert provider.calls == 1


def test_enrich_topics_runs_again_on_a_later_day(session):
    topic = _topic(session, "Tema")
    _signal(session, topic, 10, day=DAY)
    _signal(session, topic, 10, day=DAY.replace(day=DAY.day + 1))
    provider = FakeProvider(response={"merges": [], "reasons": {}})

    enrich_topics(session, provider, DAY)
    enrich_topics(session, provider, DAY.replace(day=DAY.day + 1))

    assert provider.calls == 2


def test_enrich_topics_quota_error_returns_zero_and_does_not_mark_day(session):
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)
    provider = FakeProvider(error=AIQuotaError("cota excedida"))

    assert enrich_topics(session, provider, DAY) == (0, 0)

    # nao marcou o dia como feito: uma chamada seguinte no mesmo dia tenta de novo
    provider.error = None
    provider.response = {"merges": [], "reasons": {}}
    enrich_topics(session, provider, DAY)
    assert provider.calls == 2


def test_enrich_topics_generic_provider_error_returns_zero_without_raising(session):
    topic = _topic(session, "Tema")
    _signal(session, topic, 10)
    provider = FakeProvider(error=ValueError("JSON invalido"))

    assert enrich_topics(session, provider, DAY) == (0, 0)


def test_enrich_topics_ignores_merge_of_entity_topic(session):
    """Uma entidade (`seed/entities.yaml`) nunca pode ser o lado removido de uma
    fusao: ela seria re-semeada como topico separado no proximo `extract_topics`."""
    labubu = _topic(session, "Labubu", category="toys_memes")
    other = _topic(session, "Algum Tema")
    _signal(session, labubu, 10)
    _signal(session, other, 10)
    provider = FakeProvider(response={"merges": [{"keep": "algum-tema", "merge": ["labubu"]}], "reasons": {}})

    merged, _ = enrich_topics(session, provider, DAY)

    assert merged == 0
    assert {t.slug for t in session.exec(select(Topic)).all()} == {"labubu", "algum-tema"}


def test_enrich_topics_returns_zero_when_no_topics(session):
    provider = FakeProvider(response={"merges": [], "reasons": {}})

    assert enrich_topics(session, provider, DAY) == (0, 0)
    assert provider.calls == 0
