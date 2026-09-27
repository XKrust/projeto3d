import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.myminifactory import SEARCH_URL, MyMiniFactoryCollector, parse_items
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "myminifactory"
POPULAR = json.loads((FIXTURES / "popular.json").read_text(encoding="utf-8"))
COUNT = json.loads((FIXTURES / "count.json").read_text(encoding="utf-8"))

SETTINGS = {"api_keys": {"myminifactory": "segredo123"}}


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())


def test_parse_items_maps_fields():
    items = parse_items(POPULAR)
    raw = POPULAR["items"][0]
    item = items[0]

    assert len(items) == 5
    assert item.external_id == str(raw["id"])
    assert item.title == raw["name"]
    assert item.url == raw["url"]
    assert item.likes == raw["likes"]
    assert item.views == raw["views"]
    assert item.metric == raw["likes"] + raw["views"] / 100
    assert item.tags == raw["tags"]
    assert item.thumb_url == raw["images"][0]["thumbnail"]["url"]
    assert item.price_usd is None
    assert item.country == GLOBAL


def test_parse_items_prefers_primary_image():
    item = parse_items(POPULAR)[1]  # a imagem primaria e a segunda da lista

    assert item.thumb_url == POPULAR["items"][1]["images"][1]["thumbnail"]["url"]


@respx.mock
def test_collect_sends_key_and_popularity_sort():
    route = respx.get(url__startswith=SEARCH_URL).mock(return_value=httpx.Response(200, json=POPULAR))

    with make_client() as http:
        MyMiniFactoryCollector(SETTINGS, http).collect()

    params = route.calls.last.request.url.params
    assert params["key"] == "segredo123"
    assert params["sort"] == "popularity"
    assert params["q"] == ""


@respx.mock
def test_count_listings_reads_total_count():
    route = respx.get(url__startswith=SEARCH_URL).mock(return_value=httpx.Response(200, json=COUNT))

    with make_client() as http:
        total = MyMiniFactoryCollector(SETTINGS, http).count_listings("frieren")

    assert total == 3127
    params = route.calls.last.request.url.params
    assert params["q"] == "frieren"
    assert params["per_page"] == "1"


@respx.mock
def test_401_raises_collector_error():
    respx.get(url__startswith=SEARCH_URL).mock(return_value=httpx.Response(401, json={}))

    with make_client() as http:
        with pytest.raises(CollectorError, match="Chave inválida"):
            MyMiniFactoryCollector(SETTINGS, http).collect()


@respx.mock
def test_error_message_does_not_leak_key():
    respx.get(url__startswith=SEARCH_URL).mock(return_value=httpx.Response(500))

    with make_client() as http:
        with pytest.raises(CollectorError) as exc:
            MyMiniFactoryCollector(SETTINGS, http).collect()

    assert "segredo123" not in str(exc.value)
