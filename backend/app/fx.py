"""Câmbio: taxas de referência diárias do Banco Central Europeu (grátis, sem chave).

`eurofxref-daily.xml` traz quantas unidades de cada moeda valem 1 euro. Buscamos no máximo
1x por dia (guardado em `Setting`); falhando, vale a última guardada; sem nenhuma, a taxa
fixa abaixo — e a fonte devolvida diz qual foi usada, para a tela mostrar.
"""

import json
import logging
from datetime import date

import httpx
from defusedxml import ElementTree as ET
from sqlmodel import Session

from app.models import Setting

logger = logging.getLogger(__name__)

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
SETTING_KEY = "fx_rates"
FALLBACK_DATE = "2026-09-25"
FALLBACK_RATES = {"EUR": 1.0, "USD": 1.1403, "JPY": 179.70}
TIMEOUT_SECONDS = 8.0


def parse_ecb(xml: str) -> dict[str, float]:
    """Moeda → unidades por 1 euro (inclui `"EUR": 1.0`)."""
    rates = {"EUR": 1.0}
    for element in ET.fromstring(xml).iter():
        if element.get("currency") and element.get("rate"):
            rates[element.get("currency")] = float(element.get("rate"))
    return rates


def _ecb_date(xml: str) -> str:
    for element in ET.fromstring(xml).iter():
        if element.get("time"):
            return element.get("time")
    return ""


def fetch_rates(http: httpx.Client) -> tuple[dict[str, float], str]:
    """(taxas, data da cotação) direto do BCE. Lança exceção se falhar."""
    response = http.get(ECB_URL, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    rates = parse_ecb(response.text)
    if "USD" not in rates:
        raise ValueError("Resposta do BCE sem USD")
    return rates, _ecb_date(response.text)


def _source(ecb_day: str) -> str:
    return f"cotação do Banco Central Europeu de {ecb_day}"


def get_rates(session: Session, http: httpx.Client, today: date) -> tuple[dict[str, float], str]:
    """(taxas, fonte legível). Busca no máximo 1x por dia; cai no cache e depois na taxa fixa."""
    row = session.get(Setting, SETTING_KEY)
    cached = json.loads(row.value_json) if row else None
    if cached and cached.get("fetched_day") == today.isoformat():
        return cached["rates"], _source(cached["date"])
    try:
        rates, ecb_day = fetch_rates(http)
    except Exception as exc:  # noqa: BLE001 — sem câmbio novo, segue com o que tiver
        logger.warning("Câmbio do BCE falhou: %s", exc)
        if cached:
            return cached["rates"], _source(cached["date"])
        return dict(FALLBACK_RATES), f"cotação fixa de {FALLBACK_DATE} (Banco Central Europeu fora do ar)"
    payload = json.dumps({"fetched_day": today.isoformat(), "date": ecb_day, "rates": rates})
    if row is None:
        row = Setting(key=SETTING_KEY, value_json=payload)
    else:
        row.value_json = payload
    session.add(row)
    session.commit()
    return rates, _source(ecb_day)


def to_eur(amount: float, currency: str, rates: dict[str, float]) -> float:
    return amount / rates[currency]


def convert(amount: float, from_currency: str, to_currency: str, rates: dict[str, float]) -> float:
    return to_eur(amount, from_currency, rates) * rates[to_currency]
