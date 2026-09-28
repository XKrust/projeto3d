"""Rota da tela inicial (/api/countries): o que vende em cada país.

Para cada país: os 3 melhores temas (maior nota de oportunidade no último dia com score,
cada tema contado uma vez pela loja que o radar mostra) e as 3 lojas que vendem com maior
força ali. Não há mais "% de chance": era a média de percentis dentro do próprio país e
dava ~80% em todo lugar, sem diferenciar nada. País inativo vem sem temas.
"""

import json
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from app.constants import COUNTRIES, COUNTRY_NAMES
from app.db import get_session
from app.models import Platform, Topic, TopicScore
from app.settings_store import get_settings

router = APIRouter()

TOP_THEMES = 3
TOP_STORES = 3


def _best_opportunities(session: Session, country: str) -> list[tuple[float, int]]:
    """(opportunity, topic_id) do melhor score de cada tópico, da maior nota para a menor."""
    last_day = session.exec(
        select(func.max(TopicScore.day)).where(TopicScore.country == country)
    ).first()
    if last_day is None:
        return []
    # Score antigo de loja que fechou (Sketchfab, ArtStation) não conta.
    closed = set(session.exec(select(Platform.slug).where(Platform.sells == False)).all())  # noqa: E712
    rows_by_topic: dict[int, list[TopicScore]] = defaultdict(list)
    for row in session.exec(
        select(TopicScore).where(TopicScore.country == country, TopicScore.day == last_day)
    ).all():
        if row.platform not in closed:
            rows_by_topic[row.topic_id].append(row)
    best = []
    for topic_id, rows in rows_by_topic.items():
        row = max(sorted(rows, key=lambda r: r.platform), key=lambda r: r.opportunity * r.fit_platform)
        best.append((row.opportunity, topic_id))
    best.sort(reverse=True)
    return best


def _strongest_stores(session: Session) -> dict[str, list[str]]:
    """país → nomes das `TOP_STORES` lojas que vendem com maior força ali."""
    stores = [p for p in session.exec(select(Platform).where(Platform.sells)).all()]
    result = {}
    for code in COUNTRIES:
        ranked = sorted(stores, key=lambda p: (-json.loads(p.strength_json).get(code, 0.0), p.name))
        result[code] = [p.name for p in ranked[:TOP_STORES] if json.loads(p.strength_json).get(code, 0.0) > 0]
    return result


@router.get("/countries")
def read_countries(session: Session = Depends(get_session)) -> list[dict]:
    active = set(get_settings(session).get("countries", []))
    stores = _strongest_stores(session)
    result = []
    for code in COUNTRIES:
        # País inativo não é coletado: os temas antigos ficariam parados, então não mostra.
        best = _best_opportunities(session, code) if code in active else []
        result.append(
            {
                "code": code,
                "name": COUNTRY_NAMES[code],
                "active": code in active,
                "top_topics": [session.get(Topic, topic_id).name for _, topic_id in best[:TOP_THEMES]],
                "stores": stores[code],
                "topics": len(best),
            }
        )
    return result
