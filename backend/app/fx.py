"""Câmbio diário (Etapa 3c): 1 US$ em cada moeda dos países do app.

Fonte: Frankfurter (taxas de referência do Banco Central Europeu), grátis e sem chave.
O BCE não publica RUB (desde 2022) nem BYN: Rússia e Bielorrússia ficam só em US$.
"""

import logging
from collections.abc import Callable
from datetime import date, timedelta
import time

import httpx
from sqlmodel import Session, select

from app import clock
from app.daily import claim_daily
from app.http import get_with_retry
from app.models import FxRate

logger = logging.getLogger(__name__)

FX_URL = "https://api.frankfurter.dev/v1/latest"
MAX_AGE_DAYS = 7
DAILY_TASK = "fx"

CURRENCY_BY_COUNTRY: dict[str, str] = {
    "BR": "BRL", "GB": "GBP", "DE": "EUR", "FR": "EUR", "ES": "EUR", "IT": "EUR", "NL": "EUR",
    "JP": "JPY", "MX": "MXN", "CA": "CAD", "AU": "AUD", "PL": "PLN",
}


def update_fx_rates(session: Session, http: httpx.Client, day: date,
                    sleep: Callable[[float], None] = time.sleep) -> int:
    """Baixa as taxas 1x por dia. Devolve quantas moedas gravou (0 se já tentou hoje ou
    se falhou: a falha vai para o log e tenta de novo amanhã)."""
    if not claim_daily(session, DAILY_TASK, day):
        return 0
    symbols = ",".join(sorted(set(CURRENCY_BY_COUNTRY.values())))
    try:
        response = get_with_retry(http, "GET", FX_URL, params={"base": "USD", "symbols": symbols}, sleep=sleep)
        payload = response.json()
        rates_day = date.fromisoformat(payload["date"])
        rates = {cur: float(rate) for cur, rate in payload["rates"].items()}
    except Exception:  # noqa: BLE001 — câmbio nunca derruba o ciclo
        logger.exception("Falha ao baixar o câmbio")
        return 0
    for currency, rate in rates.items():
        row = session.exec(select(FxRate).where(FxRate.day == rates_day, FxRate.currency == currency)).first()
        if row is None:
            row = FxRate(day=rates_day, currency=currency, rate=rate)
        row.rate = rate
        session.add(row)
    session.commit()
    return len(rates)


def fx_for_country(session: Session, country: str) -> dict | None:
    """Taxa mais recente (até 7 dias) da moeda do país; None para EUA, RU/BY ou sem taxa."""
    currency = CURRENCY_BY_COUNTRY.get(country)
    if currency is None:
        return None
    since = clock.today() - timedelta(days=MAX_AGE_DAYS)
    row = session.exec(
        select(FxRate).where(FxRate.currency == currency, FxRate.day >= since).order_by(FxRate.day.desc())
    ).first()
    if row is None:
        return None
    return {"currency": currency, "rate": row.rate, "day": row.day.isoformat()}
