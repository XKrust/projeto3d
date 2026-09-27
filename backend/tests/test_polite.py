import httpx
import pytest
import respx

from app.collectors.base import CollectorError
from app.collectors.polite import check_robots, polite_delay
from app.http import make_client

ROBOTS_URL = "https://exemplo.test/robots.txt"


@respx.mock
def test_check_robots_404_allows():
    respx.get(ROBOTS_URL).mock(return_value=httpx.Response(404, text="Not Found"))

    with make_client() as http:
        check_robots(http, ROBOTS_URL, "https://exemplo.test/qualquer/coisa")


@respx.mock
def test_check_robots_disallow_raises():
    respx.get(ROBOTS_URL).mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
    )

    with make_client() as http:
        with pytest.raises(CollectorError, match=r"Bloqueado pelo robots\.txt: .*/private/x"):
            check_robots(http, ROBOTS_URL, "https://exemplo.test/private/x")


def test_polite_delay_sleeps_between_3_and_5(monkeypatch):
    ranges: list[tuple[float, float]] = []
    waits: list[float] = []

    def fake_uniform(a: float, b: float) -> float:
        ranges.append((a, b))
        return 3.7

    monkeypatch.setattr("app.collectors.polite.random.uniform", fake_uniform)
    monkeypatch.setattr("app.collectors.polite.time.sleep", waits.append)

    polite_delay()

    assert ranges == [(3.0, 5.0)]
    assert waits == [3.7]
