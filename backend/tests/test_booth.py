import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.booth import (
    ACCOUNTS_ROBOTS_URL,
    BROWSE_URL,
    ROBOTS_URL,
    WISH_URL,
    BoothCollector,
    parse_browse,
    parse_search_count,
    parse_wish_counts,
)
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "booth"
BROWSE = (FIXTURES / "browse.html").read_text(encoding="utf-8")
SEARCH = (FIXTURES / "search.html").read_text(encoding="utf-8")
WISH = json.loads((FIXTURES / "wish_lists.json").read_text(encoding="utf-8"))
ROBOTS = (FIXTURES / "robots.txt").read_text(encoding="utf-8")
ACCOUNTS_ROBOTS = (FIXTURES / "accounts_robots.txt").read_text(encoding="utf-8")
SEARCH_ZERO = (FIXTURES / "search_zero.html").read_text(encoding="utf-8")

SETTINGS = {"api_keys": {}}
IDS = ["7657840", "5479202", "5813187", "4511536", "6106863"]


@pytest.fixture(autouse=True)
def no_real_delay(monkeypatch):
    monkeypatch.setattr("app.collectors.polite.time.sleep", lambda _: None)
    monkeypatch.setattr("app.http.RETRY_DELAYS", ())


def _mock_robots(accounts_robots: str = ACCOUNTS_ROBOTS):
    respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=ROBOTS))
    respx.get(ACCOUNTS_ROBOTS_URL).mock(return_value=httpx.Response(200, text=accounts_robots))


def test_parse_browse_reads_5_cards():
    cards = parse_browse(BROWSE)

    assert [c["id"] for c in cards] == IDS
    first = cards[0]
    assert first["name"] == "もちふぃった～"
    assert first["price_jpy"] == 2500
    assert first["brand"] == "yamirin"
    assert first["thumb_url"].startswith("https://booth.pximg.net/")


def test_parse_browse_skips_card_without_id():
    broken = BROWSE.replace('data-product-id="7657840"', "", 1)

    cards = parse_browse(broken)

    assert [c["id"] for c in cards] == IDS[1:]


def test_parse_wish_counts_maps_ids():
    assert parse_wish_counts(WISH)["7657840"] == 51601


def test_parse_search_count_reads_total():
    assert parse_search_count(SEARCH) == 11068


@respx.mock
def test_collect_uses_wish_counts_as_metric():
    _mock_robots()
    respx.get(BROWSE_URL).mock(return_value=httpx.Response(200, text=BROWSE))
    respx.get(url__startswith=WISH_URL).mock(return_value=httpx.Response(200, json=WISH))

    with make_client() as http:
        items = BoothCollector(SETTINGS, http).collect()

    assert [i.external_id for i in items] == IDS
    first = items[0]
    assert first.likes == 51601
    assert first.metric == 51601
    assert first.country == "JP"
    assert first.price_usd is None
    assert first.url == "https://booth.pm/ja/items/7657840"
    assert first.title == "もちふぃった～"


@respx.mock
def test_collect_without_wish_counts_falls_back_to_position():
    _mock_robots()
    respx.get(BROWSE_URL).mock(return_value=httpx.Response(200, text=BROWSE))
    respx.get(url__startswith=WISH_URL).mock(return_value=httpx.Response(500))

    with make_client() as http:
        collector = BoothCollector(SETTINGS, http)
        items = collector.collect()

    assert [i.likes for i in items] == [None] * 5
    assert [i.metric for i in items] == [5, 4, 3, 2, 1]


@respx.mock
def test_collect_empty_page_raises_format_changed():
    _mock_robots()
    respx.get(BROWSE_URL).mock(return_value=httpx.Response(200, text="<html><body></body></html>"))

    with make_client() as http:
        with pytest.raises(CollectorError, match="Formato da página do BOOTH mudou"):
            BoothCollector(SETTINGS, http).collect()


@respx.mock
def test_count_listings_parses_total():
    _mock_robots()
    respx.get(url__startswith="https://booth.pm/ja/search/").mock(
        return_value=httpx.Response(200, text=SEARCH)
    )

    with make_client() as http:
        assert BoothCollector(SETTINGS, http).count_listings("ドラゴン") == 11068


@respx.mock
def test_count_listings_quotes_slash():
    _mock_robots()
    route = respx.get(url__startswith="https://booth.pm/ja/search/").mock(
        return_value=httpx.Response(200, text=SEARCH)
    )

    with make_client() as http:
        BoothCollector(SETTINGS, http).count_listings("Re:Zero / Rem")

    assert str(route.calls.last.request.url).endswith("/ja/search/Re%3AZero%20%2F%20Rem")


@respx.mock
def test_collect_waits_between_requests(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("app.collectors.polite.time.sleep", waits.append)
    _mock_robots()
    respx.get(BROWSE_URL).mock(return_value=httpx.Response(200, text=BROWSE))
    respx.get(url__startswith=WISH_URL).mock(return_value=httpx.Response(200, json=WISH))

    with make_client() as http:
        BoothCollector(SETTINGS, http).collect()

    assert len(waits) >= 2


def test_parse_search_count_zero_results():
    assert parse_search_count(SEARCH_ZERO) == 0


@respx.mock
def test_wish_counts_respect_accounts_robots():
    _mock_robots(accounts_robots="User-agent: *\nDisallow: /\n")
    respx.get(BROWSE_URL).mock(return_value=httpx.Response(200, text=BROWSE))
    wish = respx.get(url__startswith=WISH_URL).mock(return_value=httpx.Response(200, json=WISH))

    with make_client() as http:
        items = BoothCollector(SETTINGS, http).collect()

    assert not wish.called
    assert [i.metric for i in items] == [5, 4, 3, 2, 1]


@respx.mock
def test_collect_survives_connection_error_on_wish_counts():
    _mock_robots()
    respx.get(BROWSE_URL).mock(return_value=httpx.Response(200, text=BROWSE))
    respx.get(url__startswith=WISH_URL).mock(side_effect=httpx.ConnectError("sem rede"))

    with make_client() as http:
        items = BoothCollector(SETTINGS, http).collect()

    assert [i.likes for i in items] == [None] * 5
    assert [i.metric for i in items] == [5, 4, 3, 2, 1]
