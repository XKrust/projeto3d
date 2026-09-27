import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.http import USER_AGENT, get_with_retry, make_client


def test_make_client_has_timeout_and_user_agent():
    client = make_client()
    try:
        assert client.timeout == httpx.Timeout(20.0)
        assert client.headers["user-agent"] == USER_AGENT
    finally:
        client.close()


@respx.mock
def test_retry_then_success():
    route = respx.get("https://exemplo.test/dados").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    sleeps: list[float] = []

    with make_client() as client:
        response = get_with_retry(
            client, "GET", "https://exemplo.test/dados", sleep=sleeps.append
        )

    assert response.status_code == 200
    assert sleeps == [1, 2]
    assert route.call_count == 3


@respx.mock
def test_401_no_retry():
    route = respx.get("https://exemplo.test/dados").mock(return_value=httpx.Response(401))
    sleeps: list[float] = []

    with make_client() as client:
        with pytest.raises(CollectorError, match=r"Chave inválida ou sem permissão \(401\)"):
            get_with_retry(client, "GET", "https://exemplo.test/dados", sleep=sleeps.append)

    assert route.call_count == 1
    assert sleeps == []


@respx.mock
def test_exhausted_retries_raise_with_status():
    respx.get("https://exemplo.test/dados").mock(return_value=httpx.Response(503))
    sleeps: list[float] = []

    with make_client() as client:
        with pytest.raises(CollectorError, match=r"Falha ao acessar a fonte \(503\)"):
            get_with_retry(client, "GET", "https://exemplo.test/dados", sleep=sleeps.append)

    assert sleeps == [1, 2, 4]


@respx.mock
def test_exhausted_retries_timeout_message():
    respx.get("https://exemplo.test/dados").mock(side_effect=httpx.TimeoutException("timeout"))
    sleeps: list[float] = []

    with make_client() as client:
        with pytest.raises(CollectorError, match=r"Falha ao acessar a fonte \(timeout\)"):
            get_with_retry(client, "GET", "https://exemplo.test/dados", sleep=sleeps.append)

    assert sleeps == [1, 2, 4]
