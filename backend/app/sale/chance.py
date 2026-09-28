"""Chance de venda de um tema numa loja e país (spec 3b §6).

`chance = oportunidade × (0.5 + 0.05 · nota)`. A saturação não entra de novo: ela já faz
parte da oportunidade. É estimativa, não probabilidade medida.
"""

from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.constants import COUNTRY_NAMES, in_country
from app.models import Topic, TopicScore
from app.scoring.formulas import sale_chance

NO_TOPIC = "tema ainda não está no radar: sem dado de procura"


def _decimal(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _last_rows(session: Session, topic: Topic, country: str) -> list[TopicScore]:
    last_day = session.exec(select(func.max(TopicScore.day)).where(TopicScore.country == country)).first()
    if last_day is None:
        return []
    return list(session.exec(
        select(TopicScore).where(TopicScore.topic_id == topic.id, TopicScore.country == country,
                                 TopicScore.day == last_day)
    ).all())


def chance_for_store(session: Session, *, topic: Topic | None, country: str, platform: str,
                     platform_name: str, fit: float, overall: float | None) -> dict:
    if topic is None:
        return {"value": None, "label": None, "why": NO_TOPIC}
    country_name = COUNTRY_NAMES.get(country, country)
    rows = _last_rows(session, topic, country)
    if not rows:
        return {"value": None, "label": None, "why": f"o tema ainda não tem nota {in_country(country)}"}
    quality = "qualidade não avaliada" if overall is None else f"qualidade {_decimal(overall)}"
    factor = 0.75 if overall is None else 0.5 + 0.05 * overall
    store_row = next((row for row in rows if row.platform == platform), None)
    if store_row is not None:
        opportunity = store_row.opportunity
        why = f"oportunidade {round(opportunity)} no {platform_name} ({country_name}) × {quality}"
    else:
        best = max(row.opportunity for row in rows)
        opportunity = best * fit
        why = f"oportunidade {round(best)} do tema {in_country(country)} × encaixe {_decimal(fit)} da loja × {quality}"
    value = round(opportunity * factor)
    return {"value": value, "label": sale_chance(value), "why": why}


def peak_for_topic(session: Session, topic: Topic | None, country: str) -> date | None:
    """Pico previsto do tema no país (linha de maior oportunidade do último dia)."""
    if topic is None:
        return None
    rows = _last_rows(session, topic, country)
    if not rows:
        return None
    return max(rows, key=lambda row: row.opportunity).peak_day
