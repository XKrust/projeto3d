import json
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from app import clock
from app.collectors.base import CollectorError
from app.collectors.igdb import GAMES_URL, TOKEN_URL, IGDBCollector, parse_games
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "igdb"
TOKEN = json.loads((FIXTURES / "token.json").read_text(encoding="utf-8"))
GAMES = json.loads((FIXTURES / "games.json").read_text(encoding="utf-8"))

SETTINGS = {"api_keys": {"igdb_client_id": "cid", "igdb_client_secret": "csecret"}}
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixed(monkeypatch):
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())
    monkeypatch.setattr(clock, "now", lambda: NOW)


def test_maps_release_date_from_unix():
    _, releases = parse_games(GAMES)

    silksong = releases[0]
    assert silksong.external_id == "350001"
    assert silksong.kind == "jogo"
    assert silksong.country == GLOBAL
    assert silksong.title == "Hollow Knight: Silksong 2"
    assert silksong.release_date == date(2026, 11, 1)
    assert silksong.popularity == 1840
    assert silksong.aliases == ["Silksong 2"]
    assert silksong.url == "https://www.igdb.com/games/hollow-knight-silksong-2"


def test_cover_url():
    _, releases = parse_games(GAMES)

    assert releases[0].image_url == "https://images.igdb.com/igdb/image/upload/t_cover_big/co9abc.jpg"
    assert releases[2].image_url is None


def test_items_use_hypes_as_metric():
    items, _ = parse_games(GAMES)

    assert items[1].metric == 920
    assert "モンスターハンターストーリーズ3" in items[1].tags


@respx.mock
def test_token_then_games():
    token = respx.post(url__startswith=TOKEN_URL).mock(return_value=httpx.Response(200, json=TOKEN))
    games = respx.post(GAMES_URL).mock(return_value=httpx.Response(200, json=GAMES))

    with make_client() as http:
        collector = IGDBCollector(SETTINGS, http)
        items = collector.collect()

    params = token.calls.last.request.url.params
    assert params["client_id"] == "cid"
    assert params["client_secret"] == "csecret"
    assert params["grant_type"] == "client_credentials"
    request = games.calls.last.request
    assert request.headers["client-id"] == "cid"
    assert request.headers["authorization"] == "Bearer tok123abc"
    assert len(items) == 3
    assert len(collector.releases()) == 3


@respx.mock
def test_body_filters_future_and_hypes():
    respx.post(url__startswith=TOKEN_URL).mock(return_value=httpx.Response(200, json=TOKEN))
    games = respx.post(GAMES_URL).mock(return_value=httpx.Response(200, json=GAMES))

    with make_client() as http:
        IGDBCollector(SETTINGS, http).collect()

    body = games.calls.last.request.content.decode()
    assert f"where first_release_date > {int(NOW.timestamp())} & hypes > 0;" in body
    assert "sort hypes desc;" in body
    assert "limit 50;" in body


@respx.mock
def test_token_invalid_client_raises():
    respx.post(url__startswith=TOKEN_URL).mock(
        return_value=httpx.Response(400, json={"status": 400, "message": "invalid client"})
    )

    with make_client() as http:
        with pytest.raises(CollectorError, match="Client ID ou Client Secret do IGDB inválido"):
            IGDBCollector(SETTINGS, http).collect()


@respx.mock
def test_games_401_raises():
    respx.post(url__startswith=TOKEN_URL).mock(return_value=httpx.Response(200, json=TOKEN))
    respx.post(GAMES_URL).mock(return_value=httpx.Response(401, json={}))

    with make_client() as http:
        with pytest.raises(CollectorError, match="Chave inválida"):
            IGDBCollector(SETTINGS, http).collect()
