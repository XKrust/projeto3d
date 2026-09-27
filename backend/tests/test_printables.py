import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.printables import (
    GRAPHQL_URL,
    ROBOTS_URL,
    PrintablesCollector,
    parse_count,
    parse_trending,
)
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "printables"
TRENDING = json.loads((FIXTURES / "trending.json").read_text(encoding="utf-8"))
SEARCH = json.loads((FIXTURES / "search.json").read_text(encoding="utf-8"))

SETTINGS = {"api_keys": {}}

# Robots.txt real de api.printables.com (26/09/2026): 404, sem regras — tudo liberado.
ROBOTS_NOT_FOUND = httpx.Response(404, text="Not Found")


def _mock_robots_allowed():
    return respx.get(ROBOTS_URL).mock(return_value=ROBOTS_NOT_FOUND)


@pytest.fixture(autouse=True)
def no_real_delay(monkeypatch):
    """Nenhum teste deve realmente dormir 3-5s; s0 os testes de delay checam a chamada."""
    monkeypatch.setattr("app.collectors.polite.time.sleep", lambda _: None)


def test_parse_trending_returns_5_items_with_title_url_and_likes():
    items = parse_trending(TRENDING)

    assert len(items) == 5
    first = TRENDING["data"]["result"]["items"][0]
    item = items[0]
    assert item.external_id == str(first["id"])
    assert item.title == first["name"]
    assert item.url == f"https://www.printables.com/model/{first['id']}-{first['slug']}"
    assert item.likes == first["likesCount"]
    assert item.downloads == first["downloadCount"]
    assert item.metric == first["likesCount"] + 2 * first["downloadCount"]
    assert item.country == GLOBAL
    assert item.thumb_url == "https://media.printables.com/" + first["image"]["filePath"]
    # nenhum resultado real trazia preco (nem em buscas por termos premium).
    assert item.price_usd is None


def test_parse_count_returns_total_count_from_fixture():
    assert parse_count(SEARCH) == SEARCH["data"]["result"]["totalCount"]


@respx.mock
def test_collect_returns_parsed_trending_items():
    _mock_robots_allowed()
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        items = PrintablesCollector(SETTINGS, http).collect()

    assert len(items) == 5


@respx.mock
def test_count_listings_returns_total_count():
    _mock_robots_allowed()
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=SEARCH))

    with make_client() as http:
        total = PrintablesCollector(SETTINGS, http).count_listings("dragon")

    assert total == SEARCH["data"]["result"]["totalCount"]


@respx.mock
def test_search_query_sends_the_search_term_and_pagination_args():
    _mock_robots_allowed()
    route = respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=SEARCH))

    with make_client() as http:
        PrintablesCollector(SETTINGS, http).count_listings("dragon")

    body = json.loads(route.calls.last.request.content)
    assert body["variables"]["query"] == "dragon"
    assert body["variables"]["limit"] == 1
    assert body["variables"]["ordering"] == "best_match"


@respx.mock
def test_trending_query_uses_empty_search_term_and_popular_ordering():
    _mock_robots_allowed()
    route = respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        PrintablesCollector(SETTINGS, http).collect()

    body = json.loads(route.calls.last.request.content)
    assert body["variables"]["query"] == ""
    assert body["variables"]["ordering"] == "popular"


@respx.mock
def test_missing_robots_txt_is_treated_as_allowed():
    # 404 em api.printables.com/robots.txt (comportamento real confirmado) nao deve bloquear.
    _mock_robots_allowed()
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        items = PrintablesCollector(SETTINGS, http).collect()

    assert len(items) == 5


@respx.mock
def test_collect_blocked_by_robots_raises_and_never_queries_graphql():
    respx.get(ROBOTS_URL).mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n")
    )
    graphql_route = respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        with pytest.raises(CollectorError, match=r"Bloqueado pelo robots\.txt: .*graphql"):
            PrintablesCollector(SETTINGS, http).collect()

    assert graphql_route.call_count == 0


@respx.mock
def test_count_listings_blocked_by_robots_raises_and_never_queries_graphql():
    respx.get(ROBOTS_URL).mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n")
    )
    graphql_route = respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=SEARCH))

    with make_client() as http:
        with pytest.raises(CollectorError, match=r"Bloqueado pelo robots\.txt: .*graphql"):
            PrintablesCollector(SETTINGS, http).count_listings("dragon")

    assert graphql_route.call_count == 0


@respx.mock
def test_graphql_errors_raise_collector_error():
    _mock_robots_allowed()
    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(400, json={"errors": [{"message": "campo invalido"}]})
    )

    with make_client() as http:
        with pytest.raises(CollectorError, match="Erro na API do Printables: campo invalido"):
            PrintablesCollector(SETTINGS, http).collect()


@respx.mock
def test_waits_random_delay_between_robots_check_and_query(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("app.collectors.polite.time.sleep", waits.append)
    monkeypatch.setattr("app.collectors.polite.random.uniform", lambda a, b: 4.2)

    _mock_robots_allowed()
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        PrintablesCollector(SETTINGS, http).collect()

    assert waits == [4.2]
