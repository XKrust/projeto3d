"""Ranking diário de países por possibilidade de venda (ver docs/score.md).

`score` (0–100, estimativa) = 0.60·público + 0.25·procura + 0.15·pagamento·100:
- **público** (`audience_index`): tamanho do público do país nas lojas de arquivo 3D
  (Similarweb, `seed/country_markets.yaml`), com o maior país = 100. Muda 1x por mês.
- **procura**: momentum médio (0–100) dos 10 temas de maior oportunidade do país no último
  dia com nota, só entre temas com 4+ dias de nota; 50 (neutro, "ainda medindo") sem
  nenhum. Muda todo dia: é o que mexe no ranking.
- **pagamento**: 1 normal; menor onde cartão/PayPal estão bloqueados (sanções).

Roda no pipeline depois de `compute_scores`, só para os países ativos. Um `CountryRank`
por (dia, país): o histórico mostra quem subiu, quem caiu e há quanto tempo o 1º é 1º.
"""

from collections import defaultdict
from datetime import date, timedelta
from functools import cache
from pathlib import Path

import yaml
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import CountryRank, TopicScore
from app.settings_store import get_settings

MARKETS_FILE = Path(__file__).resolve().parent / "seed" / "country_markets.yaml"

AUDIENCE_WEIGHT = 0.60
DEMAND_WEIGHT = 0.25
PAYMENT_WEIGHT = 0.15
TOP_THEMES = 10
NEUTRAL_DEMAND = 50.0
# Tema com menos dias de nota que isto não conta na procura: "de zero para algo" parece
# subida máxima, mas é só falta de histórico.
MIN_HISTORY_DAYS = 4
HISTORY_WINDOW_DAYS = 10


@cache
def _markets() -> dict:
    with open(MARKETS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def audience_index() -> dict[str, float]:
    """País → público nas lojas de arquivo 3D, com o maior = 100.

    Em cada loja, país fora do top 5 conta metade da 5ª participação (ver o YAML)."""
    from app.constants import COUNTRIES

    markets = _markets()
    codes = set(COUNTRIES) | {code for site in markets["sites"] for code in site["shares"]}
    raw = dict.fromkeys(codes, 0.0)
    for site in markets["sites"]:
        shares = site["shares"]
        unknown = min(shares.values()) / 2
        for code in codes:
            raw[code] += site["visits_m"] * site["weight"] * shares.get(code, unknown) / 100
    top = max(raw.values())
    return {code: round(100 * value / top, 1) for code, value in raw.items()}


def payment_factor(country: str) -> float:
    return float(_markets().get("payment", {}).get(country, 1.0))


def _demand(session: Session, country: str, day: date) -> tuple[float, bool]:
    """(procura 0–100, medida?). Média do momentum dos 10 temas de maior oportunidade
    com pelo menos `MIN_HISTORY_DAYS` dias de nota; sem nenhum, (50, False)."""
    last_day = session.exec(
        select(func.max(TopicScore.day)).where(TopicScore.country == country, TopicScore.day <= day)
    ).first()
    if last_day is None:
        return NEUTRAL_DEMAND, False
    start = last_day - timedelta(days=HISTORY_WINDOW_DAYS - 1)
    days_by_topic: dict[int, set[date]] = defaultdict(set)
    best: dict[int, TopicScore] = {}
    for row in session.exec(
        select(TopicScore).where(
            TopicScore.country == country, TopicScore.day >= start, TopicScore.day <= last_day
        )
    ).all():
        days_by_topic[row.topic_id].add(row.day)
        if row.day == last_day and (row.topic_id not in best or row.opportunity > best[row.topic_id].opportunity):
            best[row.topic_id] = row
    with_history = [r for r in best.values() if len(days_by_topic[r.topic_id]) >= MIN_HISTORY_DAYS]
    top = sorted(with_history, key=lambda r: r.opportunity, reverse=True)[:TOP_THEMES]
    if not top:
        return NEUTRAL_DEMAND, False
    return round(sum(r.momentum for r in top) / len(top), 1), True


def compute_country_ranks(session: Session, day: date) -> int:
    """Grava (upsert) o `CountryRank` de `day` para os países ativos. Retorna quantos."""
    countries = get_settings(session).get("countries", [])
    audience = audience_index()
    scored = []
    for country in countries:
        demand, measured = _demand(session, country, day)
        payment = payment_factor(country)
        score = round(
            AUDIENCE_WEIGHT * audience.get(country, 0.0) + DEMAND_WEIGHT * demand + PAYMENT_WEIGHT * payment * 100,
            1,
        )
        scored.append((country, score, audience.get(country, 0.0), demand, payment, measured))
    scored.sort(key=lambda r: (-r[1], r[0]))

    existing = {r.country: r for r in session.exec(select(CountryRank).where(CountryRank.day == day)).all()}
    for country, row in list(existing.items()):
        if country not in countries:
            session.delete(row)
    for position, (country, score, aud, demand, payment, measured) in enumerate(scored, start=1):
        row = existing.get(country) or CountryRank(
            day=day, country=country, score=0, position=0, audience=0, demand=0, payment=0
        )
        row.score, row.position, row.audience, row.demand, row.payment = score, position, aud, demand, payment
        row.demand_measured = measured
        session.add(row)
    session.commit()
    return len(scored)
