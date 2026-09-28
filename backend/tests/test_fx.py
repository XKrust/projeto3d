from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.fx import ECB_URL, FALLBACK_DATE, FALLBACK_RATES, get_rates, parse_ecb, to_eur
from app.http import make_client

XML = (Path(__file__).parent / "fixtures" / "ecb" / "eurofxref-daily.xml").read_text(encoding="utf-8")
DAY = date(2026, 9, 28)


def test_parse_ecb_reads_rates_per_euro():
    rates = parse_ecb(XML)

    assert rates["USD"] == 1.1403
    assert rates["JPY"] == 179.70
    assert rates["EUR"] == 1.0


def test_to_eur_converts():
    assert to_eur(11.403, "USD", {"USD": 1.1403, "EUR": 1.0}) == pytest.approx(10.0)


@respx.mock
def test_rates_are_fetched_once_per_day(session):
    route = respx.get(ECB_URL).mock(return_value=httpx.Response(200, text=XML))

    with make_client() as http:
        first, source = get_rates(session, http, DAY)
        second, _ = get_rates(session, http, DAY)

    assert route.call_count == 1
    assert first == second
    assert source == "cotação do Banco Central Europeu de 2026-09-25"


@respx.mock
def test_ecb_down_uses_last_saved_rates(session):
    respx.get(ECB_URL).mock(side_effect=[httpx.Response(200, text=XML), httpx.Response(500)])

    with make_client() as http:
        get_rates(session, http, date(2026, 9, 27))
        rates, source = get_rates(session, http, DAY)

    assert rates["USD"] == 1.1403
    assert source == "cotação do Banco Central Europeu de 2026-09-25"


@respx.mock
def test_ecb_down_without_cache_uses_fixed_rates(session):
    respx.get(ECB_URL).mock(return_value=httpx.Response(500))

    with make_client() as http:
        rates, source = get_rates(session, http, DAY)

    assert rates == FALLBACK_RATES
    assert source == f"cotação fixa de {FALLBACK_DATE} (Banco Central Europeu fora do ar)"
