"""Fábricas de dados para os testes da Etapa 3b (venda)."""

import json
from datetime import date

from sqlmodel import select

from app import clock
from app.models import Analysis, Platform, RawItem, Topic, TopicItem, TopicScore


def add_analysis(session, *, theme="Busto Frieren", character="Frieren", search_query="frieren bust",
                 category="anime", market="print", authorship="fanart", hours=10.0, overall=6.0,
                 strengths=None):
    result = {"overall": overall, "strengths": strengths or [{"text": "mechas do cabelo", "image": 1, "area": "cabelo"}]}
    row = Analysis(created_at=clock.now(), authorship=authorship, market=market, hours=hours, theme=theme,
                   category=category, character=character, search_query=search_query, image_count=1,
                   has_wireframe=False, result_json=json.dumps(result), overall=overall)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def add_topic(session, name, *, aliases=(), category="anime", candidate=False):
    topic = Topic(slug=name.lower().replace(" ", "-"), name=name, category=category,
                  aliases_json=json.dumps(list(aliases)), is_candidate=candidate, created_day=date(2026, 9, 1))
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def add_score(session, topic, *, country="BR", platform="cults3d", opportunity=60.0, day=None,
              peak_day=None):
    day = day or clock.today()
    row = TopicScore(topic_id=topic.id, country=country, platform=platform, day=day, demand=50,
                     momentum=50, momentum_raw=0, saturation=50, peak_day=peak_day or day, fit_window=1,
                     fit_platform=0.8, opportunity=opportunity)
    session.add(row)
    session.commit()
    return row


def add_platform(session, slug, *, markets=("print",), strength=None, categories=(), sells=True, fee_pct=None):
    platform = Platform(slug=slug, name=slug.capitalize(), markets_json=json.dumps(list(markets)),
                        strength_json=json.dumps(strength or {"BR": 0.5, "US": 0.5}), sells=sells,
                        categories_json=json.dumps(list(categories)), fee_pct=fee_pct)
    session.add(platform)
    session.commit()
    return platform


def add_items(session, topic, source, prices, *, day=None, tags=(), likes=None, country="BR"):
    """Um RawItem por preço, ligado ao tópico (se houver)."""
    day = day or clock.today()
    start = len(session.exec(select(RawItem.id)).all())
    for number, price in enumerate(prices):
        item = RawItem(source=source, external_id=f"{source}-{start + number}", country=country, day=day,
                       title=f"item {number}", tags_json=json.dumps(list(tags)), price_usd=price,
                       likes=likes if likes is not None else number, metric=1.0)
        session.add(item)
        session.commit()
        session.refresh(item)
        if topic is not None:
            session.add(TopicItem(topic_id=topic.id, raw_item_id=item.id))
            session.commit()
