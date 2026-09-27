import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.etsy import ACTIVE_URL, KEYWORDS, EtsyCollector, parse_listings
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "etsy"
ACTIVE_A = json.loads((FIXTURES / "active_a.json").read_text(encoding="utf-8"))
ACTIVE_B = json.loads((FIXTURES / "active_b.json").read_text(encoding="utf-8"))
COUNT = json.loads((FIXTURES / "count.json").read_text(encoding="utf-8"))

SETTINGS = {"api_keys": {"etsy_keystring": "chave123", "etsy_shared_secret": "segredo456"}}


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())


def _by_keyword(request: httpx.Request) -> httpx.Response:
    keyword = request.url.params["keywords"]
    return httpx.Response(200, json=ACTIVE_A if keyword == KEYWORDS[0] else ACTIVE_B)


@respx.mock
def test_collect_sends_keystring_colon_secret_header():
    route = respx.get(url__startswith=ACTIVE_URL).mock(side_effect=_by_keyword)

    with make_client() as http:
        EtsyCollector(SETTINGS, http).collect()

    assert route.call_count == len(KEYWORDS)
    assert route.calls.last.request.headers["x-api-key"] == "chave123:segredo456"
    params = route.calls.last.request.url.params
    assert params["sort_on"] == "score"
    assert params["limit"] == "100"


@respx.mock
def test_collect_dedupes_by_listing_id():
    respx.get(url__startswith=ACTIVE_URL).mock(side_effect=_by_keyword)

    with make_client() as http:
        items = EtsyCollector(SETTINGS, http).collect()

    ids = [i.external_id for i in items]
    assert len(ids) == len(set(ids)) == 5


def test_parse_listings_maps_fields():
    item = parse_listings(ACTIVE_A)[0]
    raw = ACTIVE_A["results"][0]

    assert item.external_id == str(raw["listing_id"])
    assert item.title == raw["title"]
    assert item.url == raw["url"]
    assert item.tags == raw["tags"]
    assert item.likes == raw["num_favorers"]
    assert item.views == raw["views"]
    assert item.metric == raw["num_favorers"] + raw["views"] / 100
    assert item.country == GLOBAL


def test_price_only_when_usd():
    items = {i.external_id: i for i in parse_listings(ACTIVE_A)}

    assert items["1501234567"].price_usd == 12.5
    assert items["1501234568"].price_usd is None  # EUR


def test_missing_views_counts_as_zero():
    items = {i.external_id: i for i in parse_listings(ACTIVE_A)}

    axolotl = items["1501234569"]
    assert axolotl.views is None
    assert axolotl.metric == 1204


@respx.mock
def test_403_raises_collector_error():
    respx.get(url__startswith=ACTIVE_URL).mock(return_value=httpx.Response(403, json={}))

    with make_client() as http:
        with pytest.raises(CollectorError, match="Chave inválida"):
            EtsyCollector(SETTINGS, http).collect()


@respx.mock
def test_count_listings_appends_3d_and_reads_count():
    route = respx.get(url__startswith=ACTIVE_URL).mock(return_value=httpx.Response(200, json=COUNT))

    with make_client() as http:
        total = EtsyCollector(SETTINGS, http).count_listings("frieren")

    assert total == 4821
    params = route.calls.last.request.url.params
    assert params["keywords"] == "frieren 3d"
    assert params["limit"] == "1"
