import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.thingiverse import SEARCH_URL, ThingiverseCollector, parse_hits
from app.constants import GLOBAL
from app.http import make_client
from app.topics.extract import PLATFORM_SOURCES

FIXTURES = Path(__file__).parent / "fixtures" / "thingiverse"
POPULAR = json.loads((FIXTURES / "popular.json").read_text(encoding="utf-8"))

SETTINGS = {"api_keys": {"thingiverse": "token789"}}


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())


def test_parse_hits_maps_fields():
    items = parse_hits(POPULAR)
    first = POPULAR["hits"][0]
    item = items[0]

    assert item.external_id == str(first["id"])
    assert item.title == first["name"]
    assert item.url == first["public_url"]
    assert item.thumb_url == first["thumbnail"]
    assert item.likes == first["like_count"]
    assert item.downloads == first["collect_count"]
    assert item.metric == first["like_count"] + 2 * first["collect_count"]
    assert item.tags == ["dragon", "articulated"]
    assert item.country == GLOBAL


def test_parse_hits_skips_nsfw():
    ids = [i.external_id for i in parse_hits(POPULAR)]

    assert "7001004" not in ids
    assert len(ids) == 4


@respx.mock
def test_collect_sends_bearer_and_popular_sort():
    route = respx.get(url__startswith=SEARCH_URL).mock(return_value=httpx.Response(200, json=POPULAR))

    with make_client() as http:
        items = ThingiverseCollector(SETTINGS, http).collect()

    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer token789"
    assert request.url.params["sort"] == "popular"
    assert request.url.params["type"] == "things"
    assert len(items) == 4


@respx.mock
def test_401_raises_collector_error():
    respx.get(url__startswith=SEARCH_URL).mock(return_value=httpx.Response(401, json={}))

    with make_client() as http:
        with pytest.raises(CollectorError, match="Chave inválida"):
            ThingiverseCollector(SETTINGS, http).collect()


def test_thingiverse_is_not_a_platform():
    assert ThingiverseCollector.platform is None
    assert not hasattr(ThingiverseCollector, "count_listings")
    assert "thingiverse" in PLATFORM_SOURCES
