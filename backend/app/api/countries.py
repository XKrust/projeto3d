"""Rota da tela inicial (/api/countries): cada país com a chance de venda estimada.

`chance` = média da nota de oportunidade dos 5 melhores tópicos do país no último dia
com score. Cada tópico conta uma vez, pela mesma plataforma que o radar mostra (maior
oportunidade × fit da plataforma). A interface exibe como "NN% (estimativa)". País
inativo vem com `chance` nulo (a nota antiga não é mais atualizada).
"""

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from app.constants import COUNTRIES, COUNTRY_NAMES
from app.db import get_session
from app.models import Topic, TopicScore
from app.settings_store import get_settings

router = APIRouter()

TOP_N = 5


def _best_opportunities(session: Session, country: str) -> list[tuple[float, int]]:
    """(opportunity, topic_id) do melhor score de cada tópico, da maior nota para a menor."""
    last_day = session.exec(
        select(func.max(TopicScore.day)).where(TopicScore.country == country)
    ).first()
    if last_day is None:
        return []
    rows_by_topic: dict[int, list[TopicScore]] = defaultdict(list)
    for row in session.exec(
        select(TopicScore).where(TopicScore.country == country, TopicScore.day == last_day)
    ).all():
        rows_by_topic[row.topic_id].append(row)
    best = []
    for topic_id, rows in rows_by_topic.items():
        row = max(sorted(rows, key=lambda r: r.platform), key=lambda r: r.opportunity * r.fit_platform)
        best.append((row.opportunity, topic_id))
    best.sort(reverse=True)
    return best


@router.get("/countries")
def read_countries(session: Session = Depends(get_session)) -> list[dict]:
    active = set(get_settings(session).get("countries", []))
    result = []
    for code in COUNTRIES:
        # País inativo não é coletado: a nota antiga ficaria parada, então não mostra.
        best = _best_opportunities(session, code) if code in active else []
        top = best[:TOP_N]
        top_topic = session.get(Topic, top[0][1]).name if top else None
        result.append(
            {
                "code": code,
                "name": COUNTRY_NAMES[code],
                "active": code in active,
                "chance": round(sum(opp for opp, _ in top) / len(top)) if top else None,
                "top_topic": top_topic,
                "topics": len(best),
            }
        )
    return result
