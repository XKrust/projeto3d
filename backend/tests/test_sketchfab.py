import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.sketchfab import COUNT_LISTINGS_CAP, SEARCH_URL, SketchfabCollector
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "sketchfab"
TRENDING = json.loads((FIXTURES / "trending.json").read_text(encoding="utf-8"))
SEARCH_COUNT_PAGE1 = json.loads((FIXTURES / "search_count.json").read_text(encoding="utf-8"))

# Segunda pagina fabricada a partir dos mesmos 5 resultados reais da pagina 1
# (busca real por "dragon" tem mais paginas do que precisamos para o teste), so
# que com `next=None` para fechar a paginacao de forma deterministica.
SEARCH_COUNT_PAGE2 = {**SEARCH_COUNT_PAGE1, "next": None, "results": SEARCH_COUNT_PAGE1["results"][:3]}

SETTINGS_NO_TOKEN = {"api_keys": {}}
SETTINGS_WITH_TOKEN = {"api_keys": {"sketchfab": "tok-123"}}


@respx.mock
def test_metric_is_like_count_plus_view_count_over_100():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        items = SketchfabCollector(SETTINGS_NO_TOKEN, http).collect()

    by_id = {item.external_id: item for item in items}
    first = TRENDING["results"][0]
    item = by_id[first["uid"]]
    assert item.likes == first["likeCount"]
    assert item.views == first["viewCount"]
    assert item.metric == first["likeCount"] + first["viewCount"] / 100
    assert item.tags == [tag["name"] for tag in first["tags"]]
    assert item.country == GLOBAL
    # nenhum resultado real trazia preco de loja (confirmado por chamada real).
    assert item.price_usd is None


@respx.mock
def test_thumb_url_is_the_largest_image_up_to_640px():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        items = SketchfabCollector(SETTINGS_NO_TOKEN, http).collect()

    first = TRENDING["results"][0]
    widths = [img["width"] for img in first["thumbnails"]["images"] if img["width"] <= 640]
    expected_url = next(
        img["url"] for img in first["thumbnails"]["images"] if img["width"] == max(widths)
    )
    by_id = {item.external_id: item for item in items}
    assert by_id[first["uid"]].thumb_url == expected_url


@respx.mock
def test_pagination_stops_at_4_pages():
    route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        items = SketchfabCollector(SETTINGS_NO_TOKEN, http).collect()

    assert route.call_count == 4
    assert len(items) == 4 * len(TRENDING["results"])


@respx.mock
def test_token_goes_in_authorization_header_when_present():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={**TRENDING, "next": None})
    )

    with make_client() as http:
        SketchfabCollector(SETTINGS_WITH_TOKEN, http).collect()

    assert route.calls.last.request.headers["Authorization"] == "Token tok-123"


@respx.mock
def test_no_token_sends_no_authorization_header():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={**TRENDING, "next": None})
    )

    with make_client() as http:
        SketchfabCollector(SETTINGS_NO_TOKEN, http).collect()

    assert "Authorization" not in route.calls.last.request.headers


@respx.mock
def test_count_listings_sums_pages_until_exhausted():
    respx.get(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json=SEARCH_COUNT_PAGE1),
            httpx.Response(200, json=SEARCH_COUNT_PAGE2),
        ]
    )

    with make_client() as http:
        total = SketchfabCollector(SETTINGS_NO_TOKEN, http).count_listings("dragon")

    assert total == len(SEARCH_COUNT_PAGE1["results"]) + len(SEARCH_COUNT_PAGE2["results"])


@respx.mock
def test_count_listings_caps_at_200_when_pagination_never_ends():
    # Cada pagina tem 24 resultados e sempre traz `next`; sem teto isso rodaria para sempre.
    endless_page = {**TRENDING, "results": TRENDING["results"] * 5, "next": "https://api.sketchfab.com/v3/search?cursor=x"}
    assert len(endless_page["results"]) == 25

    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=endless_page))

    with make_client() as http:
        total = SketchfabCollector(SETTINGS_NO_TOKEN, http).count_listings("populartag")

    assert total == COUNT_LISTINGS_CAP


@respx.mock
def test_count_listings_uses_total_field_when_response_brings_one():
    route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"count": 4321, "results": []}))

    with make_client() as http:
        total = SketchfabCollector(SETTINGS_NO_TOKEN, http).count_listings("dragon")

    assert total == 4321
    assert route.call_count == 1


@respx.mock
def test_403_raises_collector_error():
    from app.collectors.base import CollectorError

    respx.get(SEARCH_URL).mock(return_value=httpx.Response(403))

    with make_client() as http:
        with pytest.raises(CollectorError, match=r"Chave inválida ou sem permissão \(403\)"):
            SketchfabCollector(SETTINGS_NO_TOKEN, http).collect()


@respx.mock
def test_count_listings_non_json_answer_is_a_short_collector_error():
    """Página de bloqueio (HTML) no lugar do JSON: erro curto, sem traceback no log."""
    from app.collectors.base import CollectorError

    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="<html>Just a moment...</html>"))
    with make_client() as http:
        with pytest.raises(CollectorError, match="Sketchfab respondeu sem JSON"):
            SketchfabCollector(SETTINGS_NO_TOKEN, http).count_listings("dinosaur")
