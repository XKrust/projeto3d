import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.youtube import VIDEOS_URL, YouTubeCollector
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "youtube"
MOST_POPULAR_BR = json.loads((FIXTURES / "most_popular_br.json").read_text(encoding="utf-8"))

SETTINGS = {"countries": ["BR"], "api_keys": {"youtube": "test-key"}}


@respx.mock
def test_fixture_generates_items_with_metric_equal_to_view_count():
    respx.get(VIDEOS_URL).mock(return_value=httpx.Response(200, json=MOST_POPULAR_BR))

    with make_client() as http:
        items = YouTubeCollector(SETTINGS, http).collect()

    by_id = {item.external_id: item for item in items}
    assert by_id["abc123"].metric == 123456
    assert by_id["abc123"].views == 123456
    assert by_id["abc123"].likes == 7890
    assert by_id["abc123"].comments == 321
    assert by_id["abc123"].tags == [
        "3d print", "miniatura", "anime", "game", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10",
    ]
    assert by_id["abc123"].thumb_url == "https://i.ytimg.com/vi/abc123/mqdefault.jpg"

    assert by_id["def456"].metric == 654321
    assert by_id["def456"].likes is None
    assert by_id["def456"].comments is None


@respx.mock
def test_category_404_does_not_block_other_categories():
    def handler(request):
        category = request.url.params.get("videoCategoryId")
        if category == "20":
            return httpx.Response(404)
        return httpx.Response(200, json=MOST_POPULAR_BR)

    respx.get(VIDEOS_URL).mock(side_effect=handler)

    with make_client() as http:
        items = YouTubeCollector(SETTINGS, http).collect()

    # categorias 1 e 24 (2 videos cada) rodam normalmente; so a 20 (404) e ignorada.
    assert len(items) == 4


@respx.mock
def test_403_raises_collector_error():
    respx.get(VIDEOS_URL).mock(return_value=httpx.Response(403))

    with make_client() as http:
        with pytest.raises(CollectorError, match=r"Chave inválida ou sem permissão \(403\)"):
            YouTubeCollector(SETTINGS, http).collect()
