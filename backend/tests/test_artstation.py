import copy
import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.artstation import (
    MARKETPLACE_URL,
    PROJECTS_URL,
    ROBOTS_URL,
    ArtStationCollector,
    parse_count,
    parse_trending,
)
from app.collectors.base import CollectorError
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "artstation"
TRENDING = json.loads((FIXTURES / "trending.json").read_text(encoding="utf-8"))
SEARCH = json.loads((FIXTURES / "marketplace_search.json").read_text(encoding="utf-8"))
ROBOTS = (FIXTURES / "robots.txt").read_text(encoding="utf-8")

SETTINGS = {"api_keys": {}}


@pytest.fixture(autouse=True)
def no_real_delay(monkeypatch):
    monkeypatch.setattr("app.collectors.polite.time.sleep", lambda _: None)
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())


def _mock_robots():
    respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=ROBOTS))


def test_parse_trending_maps_fields():
    items = parse_trending(TRENDING)

    assert len(items) == 5
    first = TRENDING["data"][0]
    item = items[0]
    assert item.external_id == str(first["id"])
    assert item.title == first["title"]
    assert item.url == first["permalink"]
    assert item.likes == first["likes_count"]
    assert item.views == first["views_count"]
    assert item.metric == first["likes_count"] + first["views_count"] / 100
    assert item.thumb_url == first["cover"]["thumb_url"]
    assert item.country == GLOBAL


def test_parse_trending_skips_adult():
    data = copy.deepcopy(TRENDING)
    data["data"][1]["adult_content"] = True
    data["data"][2]["hide_as_adult"] = True

    assert len(parse_trending(data)) == 3


def test_parse_trending_null_tag_list_gives_empty_tags():
    data = copy.deepcopy(TRENDING)
    data["data"][0]["tag_list"] = None
    data["data"][1]["tag_list"] = ["dragon", "fantasy"]

    items = parse_trending(data)

    assert items[0].tags == []
    assert items[1].tags == ["dragon", "fantasy"]


def test_parse_trending_skips_item_without_id():
    data = copy.deepcopy(TRENDING)
    del data["data"][0]["id"]

    assert len(parse_trending(data)) == 4


def test_parse_count_returns_total_count():
    assert parse_count(SEARCH) == 5983


@respx.mock
def test_collect_reads_two_pages():
    _mock_robots()
    route = respx.get(url__startswith=PROJECTS_URL).mock(
        return_value=httpx.Response(200, json=TRENDING)
    )

    with make_client() as http:
        items = ArtStationCollector(SETTINGS, http).collect()

    assert route.call_count == 2
    assert {c.request.url.params["page"] for c in route.calls} == {"1", "2"}
    assert len(items) == 10


@respx.mock
def test_collect_empty_raises_format_changed():
    _mock_robots()
    respx.get(url__startswith=PROJECTS_URL).mock(
        return_value=httpx.Response(200, json={"data": [], "total_count": 0})
    )

    with make_client() as http:
        with pytest.raises(CollectorError, match="Formato da página do ArtStation mudou"):
            ArtStationCollector(SETTINGS, http).collect()


@respx.mock
def test_count_listings_returns_total_count():
    _mock_robots()
    respx.get(url__startswith=MARKETPLACE_URL).mock(return_value=httpx.Response(200, json=SEARCH))

    with make_client() as http:
        assert ArtStationCollector(SETTINGS, http).count_listings("dragon") == 5983


@respx.mock
def test_count_listings_sends_required_params():
    _mock_robots()
    route = respx.get(url__startswith=MARKETPLACE_URL).mock(
        return_value=httpx.Response(200, json=SEARCH)
    )

    with make_client() as http:
        ArtStationCollector(SETTINGS, http).count_listings("Re:Zero / Rem")

    params = route.calls.last.request.url.params
    assert params["page"] == "1"
    assert params["per_page"] == "5"
    assert params["visibility"] == "profile"
    assert params["q"] == "Re:Zero / Rem"
