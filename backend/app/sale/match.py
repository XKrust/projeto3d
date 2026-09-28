"""Liga uma análise a um tema do radar (spec 3b §3).

O personagem tem prioridade sobre o tema, e o tema sobre o termo de busca. Dentro do
primeiro candidato que casar, vence o tópico de maior oportunidade no último dia de score.
"""

import json

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Analysis, Topic, TopicScore
from app.topics.normalize import matches_phrase, normalize


def _names(topic: Topic) -> list[str]:
    names = [topic.name, *json.loads(topic.aliases_json or "[]")]
    return [n for n in (normalize(name) for name in names) if n]


def _best_opportunity(session: Session, topic_ids: list[int]) -> dict[int, float]:
    last_day = session.exec(select(func.max(TopicScore.day))).first()
    if last_day is None:
        return {}
    rows = session.exec(
        select(TopicScore.topic_id, func.max(TopicScore.opportunity))
        .where(TopicScore.topic_id.in_(topic_ids), TopicScore.day == last_day)
        .group_by(TopicScore.topic_id)
    ).all()
    return dict(rows)


def match_topic(session: Session, analysis: Analysis) -> Topic | None:
    candidates = [normalize(text) for text in (analysis.character, analysis.theme, analysis.search_query)]
    topics = session.exec(select(Topic).where(Topic.is_candidate == False)).all()  # noqa: E712
    names = {topic.id: _names(topic) for topic in topics}
    for candidate in candidates:
        if not candidate:
            continue
        matched = [t for t in topics if any(n == candidate or matches_phrase(candidate, n) for n in names[t.id])]
        if matched:
            opportunity = _best_opportunity(session, [t.id for t in matched])
            return max(matched, key=lambda t: (opportunity.get(t.id, 0.0), -t.id))
    return None
