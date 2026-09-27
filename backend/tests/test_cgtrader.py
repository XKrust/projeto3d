import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.cgtrader import MODELS_URL, CGTraderCollector, parse_models
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "cgtrader"
MODELS = json.loads((FIXTURES / "models.json").read_text(encoding="utf-8"))
COUNT = json.loads((FIXTURES / "count.json").read_text(encoding="utf-8"))

SETTINGS = {"api_keys": {"cgtrader": "chaveCG"}}


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())


def test_collect_metric_by_rank():
    items = parse_models(MODELS)

    assert [i.metric for i in items] == [5, 4, 3, 2, 1]
    assert all(i.likes is None and i.downloads is None and i.views is None for i in items)


def test_parse_models_maps_fields():
    raw = MODELS["models"][0]
    item = parse_models(MODELS)[0]

    assert item.external_id == str(raw["id"])
    assert item.title == raw["title"]
    assert item.url == raw["url"]
    assert item.tags == raw["tags"]
    assert item.thumb_url == raw["thumbnails"][0]
    assert item.country == GLOBAL


def test_collect_price_from_prices_download():
    items = parse_models(MODELS)

    assert items[0].price_usd == 14.9
    assert items[2].thumb_url is None  # modelo sem thumbnails


@respx.mock
def test_collect_sends_bearer_and_sales_sort():
    route = respx.get(url__startswith=MODELS_URL).mock(return_value=httpx.Response(200, json=MODELS))

    with make_client() as http:
        CGTraderCollector(SETTINGS, http).collect()

    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer chaveCG"
    assert request.url.params["sort"] == "sales"
    assert request.url.params["per_page"] == "50"


@respx.mock
def test_count_listings_reads_total():
    route = respx.get(url__startswith=MODELS_URL).mock(return_value=httpx.Response(200, json=COUNT))

    with make_client() as http:
        total = CGTraderCollector(SETTINGS, http).count_listings("frieren")

    assert total == 2214
    params = route.calls.last.request.url.params
    assert params["keywords"] == "frieren"
    assert params["per_page"] == "1"


@respx.mock
def test_401_raises_collector_error():
    respx.get(url__startswith=MODELS_URL).mock(return_value=httpx.Response(401, text=""))

    with make_client() as http:
        with pytest.raises(CollectorError, match="Chave inválida"):
            CGTraderCollector(SETTINGS, http).collect()
