"""Onde divulgar (Etapa 3c): comunidades do Reddit e hashtags.

Só usa subreddits que o app já acompanha (`seed/reddit.yaml`) ou em que o tema apareceu de
verdade: nunca inventa comunidade.
"""

import json
import re
from collections import defaultdict
from datetime import timedelta

from sqlmodel import Session, select

from app import clock
from app.collectors.reddit import load_subreddits
from app.models import RawItem, Topic, TopicItem
from app.topics.normalize import normalize

WINDOW_DAYS = 30
MAX_COMMUNITIES = 3
MAX_HASHTAGS = 8
NOTE = ("Leia as regras de cada comunidade antes: muitas proíbem autopromoção ou pedem um dia "
        "específico para isso.")

# Comunidades por tipo de modelo, entre as que o coletor do Reddit acompanha.
BY_CATEGORY: dict[str, list[tuple[str, str]]] = {
    "anime": [("anime", "comunidade de anime")],
    "games": [("gaming", "comunidade de games")],
    "rpg_miniaturas": [("DnD", "comunidade de RPG"), ("boardgames", "comunidade de jogos de tabuleiro")],
    "toys_memes": [("ActionFigures", "comunidade de colecionáveis")],
}
BY_MARKET: dict[str, list[tuple[str, str]]] = {
    "print": [("3Dprinting", "comunidade de impressão 3D"), ("PrintedMinis", "comunidade de miniaturas impressas")],
    "digital": [("blender", "comunidade de Blender"), ("3Dmodeling", "comunidade de modelagem 3D"),
                ("ZBrush", "comunidade de ZBrush")],
}


def _community(subreddit: str, why: str, source: str) -> dict:
    return {"name": f"r/{subreddit}", "url": f"https://www.reddit.com/r/{subreddit}/", "why": why, "source": source}


def _from_topic(session: Session, topic: Topic) -> list[dict]:
    since = clock.today() - timedelta(days=WINDOW_DAYS)
    rows = session.exec(
        select(RawItem).join(TopicItem, TopicItem.raw_item_id == RawItem.id)
        .where(TopicItem.topic_id == topic.id, RawItem.source == "reddit", RawItem.day >= since)
    ).all()
    latest: dict[str, RawItem] = {}
    for item in rows:
        if item.external_id not in latest or item.day > latest[item.external_id].day:
            latest[item.external_id] = item
    engagement: dict[str, float] = defaultdict(float)
    posts: dict[str, int] = defaultdict(int)
    for item in latest.values():
        tags = json.loads(item.tags_json or "[]")
        if not tags:
            continue
        engagement[tags[0]] += item.metric
        posts[tags[0]] += 1
    ranked = sorted(engagement, key=lambda sub: (-engagement[sub], sub))[:MAX_COMMUNITIES]
    return [
        _community(sub, f"{posts[sub]} post{'s' if posts[sub] > 1 else ''} do tema em alta nos últimos "
                        f"{WINDOW_DAYS} dias", "tema")
        for sub in ranked
    ]


def _by_type(market: str, category: str) -> list[dict]:
    known = set(load_subreddits())
    candidates = BY_CATEGORY.get(category, []) + BY_MARKET.get(market, [])
    return [_community(sub, why, "tipo") for sub, why in candidates if sub in known][:MAX_COMMUNITIES]


def hashtags(tags: list[str]) -> list[str]:
    """Tags viram hashtags: sem espaço, hífen, acento ou `#` repetido; 8 no máximo."""
    result: list[str] = []
    for tag in tags:
        text = re.sub(r"[\W_]+", "", normalize(tag))
        if text and f"#{text}" not in result:
            result.append(f"#{text}")
    return result[:MAX_HASHTAGS]


def build_promotion(session: Session, *, topic: Topic | None, market: str, category: str,
                    tags: list[str]) -> dict:
    communities = _from_topic(session, topic) if topic is not None else []
    return {
        "communities": communities or _by_type(market, category),
        "hashtags": hashtags(tags),
        "note": NOTE,
    }
