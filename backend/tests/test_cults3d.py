import json
from pathlib import Path

import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.cults3d import GRAPHQL_URL, Cults3DCollector
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "cults3d"
TRENDING = json.loads((FIXTURES / "trending.json").read_text(encoding="utf-8"))
COUNT = json.loads((FIXTURES / "count.json").read_text(encoding="utf-8"))

SETTINGS = {"api_keys": {"cults3d_user": "meu_usuario", "cults3d_key": "minha_chave"}}


@respx.mock
def test_metric_is_likes_plus_twice_downloads():
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        items = Cults3DCollector(SETTINGS, http).collect()

    by_id = {item.external_id: item for item in items}
    for creation in TRENDING["data"]["creationsBatch"]["results"]:
        item = by_id[creation["identifier"]]
        assert item.likes == creation["likesCount"]
        assert item.downloads == creation["downloadsCount"]
        assert item.metric == creation["likesCount"] + 2 * creation["downloadsCount"]
        assert item.country == GLOBAL
        assert item.tags == creation["tags"]
        assert item.thumb_url == creation["illustrationImageUrl"]
        assert item.url == creation["shortUrl"]


@respx.mock
def test_price_usd_converts_cents_and_is_none_when_free():
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        items = Cults3DCollector(SETTINGS, http).collect()

    by_id = {item.external_id: item for item in items}
    assert by_id["2201002"].price_usd == 7.5  # 750 centavos
    assert by_id["2201004"].price_usd == 12.0  # 1200 centavos
    assert by_id["2201001"].price_usd is None  # price: null (gratuito)


@respx.mock
def test_basic_auth_uses_configured_user_and_key():
    route = respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=TRENDING))

    with make_client() as http:
        Cults3DCollector(SETTINGS, http).collect()

    request = route.calls.last.request
    assert request.headers["Authorization"].startswith("Basic ")
    import base64

    decoded = base64.b64decode(request.headers["Authorization"].removeprefix("Basic ")).decode()
    assert decoded == "meu_usuario:minha_chave"


@respx.mock
def test_errors_in_response_raises_collector_error_with_first_message():
    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={"errors": [{"message": "Query fields must be a valid identifier"}]},
        )
    )

    with make_client() as http:
        with pytest.raises(
            CollectorError,
            match=r"Erro na API do Cults3D: Query fields must be a valid identifier",
        ):
            Cults3DCollector(SETTINGS, http).collect()


@respx.mock
def test_count_listings_returns_total():
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=COUNT))

    with make_client() as http:
        total = Cults3DCollector(SETTINGS, http).count_listings("dragon")

    assert total == 842


@respx.mock
def test_401_raises_collector_error():
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(401))

    with make_client() as http:
        with pytest.raises(CollectorError, match=r"Chave inválida ou sem permissão \(401\)"):
            Cults3DCollector(SETTINGS, http).collect()


def test_needs_key_and_platform_metadata():
    assert Cults3DCollector.needs_key == ("cults3d_user", "cults3d_key")
    assert Cults3DCollector.platform == "cults3d"
    assert Cults3DCollector.name == "cults3d"
    assert Cults3DCollector.label == "Cults3D"
