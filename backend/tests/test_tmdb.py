import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app import clock
from app.collectors.base import CollectorError
from app.collectors.tmdb import (
    DISCOVER_TV_URL,
    UPCOMING_URL,
    TMDBCollector,
    parse_tv,
    parse_upcoming,
)
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "tmdb"
UPCOMING = json.loads((FIXTURES / "upcoming_br.json").read_text(encoding="utf-8"))
TV = json.loads((FIXTURES / "discover_tv.json").read_text(encoding="utf-8"))

SETTINGS = {"api_keys": {"tmdb": "tokenTMDB"}, "countries": ["BR", "JP"]}


@pytest.fixture(autouse=True)
def fixed(monkeypatch):
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())
    monkeypatch.setattr(clock, "today", lambda: date(2026, 9, 27))


def test_upcoming_maps_movie_release():
    _, releases = parse_upcoming(UPCOMING, "BR")

    chainsaw = releases[0]
    assert chainsaw.external_id == "1100001"
    assert chainsaw.kind == "filme"
    assert chainsaw.country == "BR"
    assert chainsaw.title == "Chainsaw Man – O Filme: Arco dos Assassinos"
    assert chainsaw.release_date == date(2026, 10, 15)
    assert chainsaw.popularity == pytest.approx(312.4)
    assert chainsaw.aliases == ["劇場版 チェンソーマン 刺客篇"]
    assert chainsaw.url == "https://www.themoviedb.org/movie/1100001"


def test_missing_release_date_is_none():
    _, releases = parse_upcoming(UPCOMING, "BR")

    assert releases[2].release_date is None
    assert releases[2].aliases == []  # título original igual ao título


def test_poster_url_built():
    _, releases = parse_upcoming(UPCOMING, "BR")

    assert releases[0].image_url == "https://image.tmdb.org/t/p/w342/p1.jpg"
    assert releases[2].image_url is None


def test_discover_tv_maps_series():
    items, releases = parse_tv(TV)

    frieren = releases[1]
    assert frieren.kind == "serie"
    assert frieren.country == GLOBAL
    assert frieren.release_date == date(2026, 10, 30)
    assert frieren.aliases == ["葬送のフリーレン 第3期"]
    assert frieren.url == "https://www.themoviedb.org/tv/2200002"
    assert items[1].metric == pytest.approx(150.5)


@respx.mock
def test_collect_calls_each_country_and_tv_with_bearer():
    upcoming = respx.get(url__startswith=UPCOMING_URL).mock(
        return_value=httpx.Response(200, json=UPCOMING)
    )
    tv = respx.get(url__startswith=DISCOVER_TV_URL).mock(return_value=httpx.Response(200, json=TV))

    with make_client() as http:
        collector = TMDBCollector(SETTINGS, http)
        collector.collect()

    assert upcoming.call_count == 2
    assert {c.request.url.params["region"] for c in upcoming.calls} == {"BR", "JP"}
    assert upcoming.calls.last.request.headers["authorization"] == "Bearer tokenTMDB"
    assert tv.calls.last.request.url.params["first_air_date.gte"] == "2026-09-27"
    kinds = [r.kind for r in collector.releases()]
    assert kinds.count("filme") == 6 and kinds.count("serie") == 2


@respx.mock
def test_401_raises():
    respx.get(url__startswith=UPCOMING_URL).mock(return_value=httpx.Response(401, json={}))

    with make_client() as http:
        with pytest.raises(CollectorError, match="Chave inválida"):
            TMDBCollector(SETTINGS, http).collect()
