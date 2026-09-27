import copy
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app import clock
from app.collectors.anilist import GRAPHQL_URL, AniListCollector, parse_media
from app.collectors.base import CollectorError
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "anilist"
PAGE = json.loads((FIXTURES / "page.json").read_text(encoding="utf-8"))
TODAY = date(2026, 9, 27)


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())


def test_parse_media_builds_releases_with_native_aliases():
    _, releases = parse_media(PAGE)

    assert len(releases) == 5
    apothecary = next(r for r in releases if r.external_id == "195516")
    assert apothecary.kind == "anime"
    assert apothecary.country == GLOBAL
    assert apothecary.title == "The Apothecary Diaries Season 3"
    assert apothecary.release_date == date(2026, 10, 2)
    assert apothecary.popularity == 74305
    assert apothecary.url == "https://anilist.co/anime/195516"
    assert "Kusuriya no Hitorigoto 3rd Season" in apothecary.aliases
    assert "薬屋のひとりごと 第3期" in apothecary.aliases
    assert apothecary.title not in apothecary.aliases


def test_title_falls_back_to_romaji_without_english():
    data = copy.deepcopy(PAGE)
    data["data"]["Page"]["media"][0]["title"]["english"] = None

    _, releases = parse_media(data)

    assert releases[0].title == "BLEACH: Sennen Kessen-hen - Kashin-tan"


def test_parse_media_date_none_when_day_missing():
    data = copy.deepcopy(PAGE)
    data["data"]["Page"]["media"][0]["startDate"] = {"year": 2027, "month": 1, "day": None}

    _, releases = parse_media(data)

    assert releases[0].release_date is None


def test_parse_media_characters_top3():
    _, releases = parse_media(PAGE)

    apothecary = next(r for r in releases if r.external_id == "195516")
    assert [c["name"] for c in apothecary.characters] == ["Maomao", "Jinshi", "Gaoshun"]
    assert apothecary.characters[0] == {
        "name": "Maomao",
        "native": "猫猫",
        "favourites": 22459,
        "image_url": PAGE["data"]["Page"]["media"][1]["characters"]["nodes"][0]["image"]["medium"],
    }


def test_parse_media_items_carry_aliases_as_tags():
    items, _ = parse_media(PAGE)

    item = next(i for i in items if i.external_id == "195516")
    assert item.title == "The Apothecary Diaries Season 3"
    assert "薬屋のひとりごと 第3期" in item.tags
    assert item.metric == pytest.approx(74.305)
    assert item.country == GLOBAL


@respx.mock
def test_collect_sends_start_date_filter(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: TODAY)
    route = respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=PAGE))

    with make_client() as http:
        collector = AniListCollector({}, http)
        items = collector.collect()

    body = json.loads(route.calls.last.request.content)
    assert body["variables"]["startAfter"] == 20260629  # hoje − 90 dias
    assert len(items) == 5
    assert len(collector.releases()) == 5


@respx.mock
def test_graphql_errors_raise(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: TODAY)
    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "Too Many Requests"}]})
    )

    with make_client() as http:
        with pytest.raises(CollectorError, match="Erro na API do AniList: Too Many Requests"):
            AniListCollector({}, http).collect()
