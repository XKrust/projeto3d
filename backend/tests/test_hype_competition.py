import json
from datetime import date, timedelta

from sqlmodel import select

from app.collectors.base import CollectorError
from app.constants import GLOBAL
from app.hype.competition import hype_terms, update_hype_listings
from app.models import HypeListing, HypeRelease

DAY = date(2026, 9, 27)


def _release(session, *, external_id, title, popularity, kind="anime", characters=()):
    session.add(
        HypeRelease(
            source="anilist",
            external_id=external_id,
            kind=kind,
            title=title,
            release_date=DAY + timedelta(days=20),
            popularity=popularity,
            country=GLOBAL,
            characters_json=json.dumps(list(characters), ensure_ascii=False),
            updated_day=DAY,
        )
    )
    session.commit()


def _char(name, favourites=5000):
    return {"name": name, "native": None, "favourites": favourites, "image_url": None}


class FakeCounter:
    def __init__(self, counts=None, failing=()):
        self.counts = counts or {}
        self.failing = set(failing)
        self.queries: list[str] = []

    def count_listings(self, query: str) -> int:
        self.queries.append(query)
        if query in self.failing:
            raise CollectorError("Falha simulada")
        return self.counts.get(query, 3)


def test_hype_terms_title_plus_two_characters(session):
    _release(
        session,
        external_id="1",
        title="The Apothecary Diaries Season 3",
        popularity=100,
        characters=[_char("Anya Forger", 9000), _char("Loid Forger", 8000), _char("Yor Forger", 7000)],
    )
    _release(session, external_id="2", title="Monster Hunter Stories 3", popularity=50, kind="jogo")

    assert hype_terms(session, DAY) == [
        "The Apothecary Diaries",
        "Anya Forger",
        "Loid Forger",
        "Monster Hunter Stories 3",
    ]


def test_hype_terms_respects_limit(session):
    _release(session, external_id="1", title="Anime Grande", popularity=100, characters=[_char("Personagem Um")])
    _release(session, external_id="2", title="Anime Menor", popularity=10)

    assert hype_terms(session, DAY, limit=2) == ["Anime Grande", "Personagem Um"]


def test_update_hype_listings_writes_counts_per_platform(session):
    _release(session, external_id="1", title="Frieren", popularity=100)

    written = update_hype_listings(
        session, {"cults3d": FakeCounter({"Frieren": 34}), "booth": FakeCounter({"Frieren": 7})}, DAY
    )

    assert written == 2
    rows = {r.platform: r.count for r in session.exec(select(HypeListing)).all()}
    assert rows == {"cults3d": 34, "booth": 7}


def test_update_hype_listings_skips_failed_term(session):
    _release(session, external_id="1", title="Frieren", popularity=100)
    _release(session, external_id="2", title="Dandadan", popularity=50)

    update_hype_listings(session, {"cults3d": FakeCounter(failing={"Frieren"})}, DAY)

    terms = {r.term for r in session.exec(select(HypeListing)).all()}
    assert terms == {"Dandadan"}


def test_update_hype_listings_abandons_platform_after_3_failures(session):
    for i in range(5):
        _release(session, external_id=str(i), title=f"Anime Numero {chr(65 + i)}", popularity=100 - i)
    counter = FakeCounter(failing={f"Anime Numero {chr(65 + i)}" for i in range(5)})

    update_hype_listings(session, {"cults3d": counter}, DAY)

    assert len(counter.queries) == 3


def test_update_hype_listings_runs_once_per_day(session):
    _release(session, external_id="1", title="Frieren", popularity=100)
    counter = FakeCounter()

    update_hype_listings(session, {"cults3d": counter}, DAY)
    update_hype_listings(session, {"cults3d": counter}, DAY)

    assert counter.queries == ["Frieren"]


def test_hype_terms_include_other_kinds_despite_popularity_scale(session):
    _release(session, external_id="1", title="Anime Enorme", popularity=100_000)
    _release(session, external_id="2", title="Anime Grande", popularity=90_000)
    _release(session, external_id="3", title="Filme Pequeno", popularity=500, kind="filme")

    assert hype_terms(session, DAY, limit=2) == ["Anime Enorme", "Filme Pequeno"]
