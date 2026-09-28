import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import respx
from sqlmodel import select

from app import clock
from app.fx import CURRENCY_BY_COUNTRY, FX_URL, fx_for_country, update_fx_rates
from app.http import make_client
from app.models import FxRate

# Formato documentado da API Frankfurter (v1 /latest). A API não é acessível no ambiente
# em que este teste foi escrito; valores de exemplo.
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "frankfurter" / "latest_usd.json").read_text())
TODAY = date(2026, 9, 28)


def test_currency_map_covers_countries_except_ru_by():
    assert CURRENCY_BY_COUNTRY["BR"] == "BRL"
    assert CURRENCY_BY_COUNTRY["DE"] == CURRENCY_BY_COUNTRY["NL"] == "EUR"
    assert "RU" not in CURRENCY_BY_COUNTRY and "BY" not in CURRENCY_BY_COUNTRY


@respx.mock
def test_update_saves_rates_once_per_day(session):
    route = respx.get(FX_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    with make_client() as http:
        assert update_fx_rates(session, http, TODAY) == 8
        assert update_fx_rates(session, http, TODAY) == 0
    assert route.call_count == 1
    assert "symbols" in str(route.calls[0].request.url)
    rows = {r.currency: r for r in session.exec(select(FxRate)).all()}
    assert rows["BRL"].rate == 5.4312
    assert rows["BRL"].day == date(2026, 9, 25)  # data das taxas, não a do pedido


@respx.mock
def test_network_error_does_not_raise(session):
    respx.get(FX_URL).mock(side_effect=httpx.ConnectError("sem rede"))
    with make_client() as http:
        assert update_fx_rates(session, http, TODAY, sleep=lambda _: None) == 0
    assert session.exec(select(FxRate)).all() == []


@respx.mock
def test_bad_payload_does_not_raise(session):
    respx.get(FX_URL).mock(return_value=httpx.Response(200, json={"oops": 1}))
    with make_client() as http:
        assert update_fx_rates(session, http, TODAY) == 0


def _rate(session, currency, rate, day):
    session.add(FxRate(day=day, currency=currency, rate=rate))
    session.commit()


def test_fx_for_country_uses_latest_recent_rate(session):
    today = clock.today()
    _rate(session, "BRL", 5.0, today - timedelta(days=3))
    _rate(session, "BRL", 5.5, today - timedelta(days=1))
    assert fx_for_country(session, "BR") == {"currency": "BRL", "rate": 5.5,
                                              "day": (today - timedelta(days=1)).isoformat()}


def test_fx_for_country_old_or_missing(session):
    _rate(session, "EUR", 0.9, clock.today() - timedelta(days=8))
    assert fx_for_country(session, "DE") is None
    assert fx_for_country(session, "JP") is None


def test_fx_for_us_and_russia_is_none(session):
    _rate(session, "USD", 1.0, clock.today())
    assert fx_for_country(session, "US") is None
    assert fx_for_country(session, "RU") is None
