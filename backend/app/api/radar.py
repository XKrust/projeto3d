"""Rota do radar (/api/radar, /api/radar/meta): scores por topico, filtros e sparkline."""

import json
import statistics
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app import clock
from app.constants import CATEGORIES, COUNTRIES, MARKETS
from app.db import get_session
from app.models import Platform, RawItem, Source, Topic, TopicItem, TopicScore
from app.scoring.formulas import momentum_arrow, sale_chance
from app.settings_store import get_settings

router = APIRouter()

COUNTRY_GROUPS = {"Europa": ["GB", "DE", "FR", "ES"]}
SPARKLINE_DAYS = 30


def _platforms_by_slug(session: Session) -> dict[str, Platform]:
    return {p.slug: p for p in session.exec(select(Platform)).all()}


@router.get("/radar/meta")
def read_meta(session: Session = Depends(get_session)) -> dict:
    platforms = session.exec(select(Platform)).all()
    last_updated = session.exec(select(func.max(Source.last_run))).first()
    return {
        "countries": COUNTRIES,
        "country_groups": COUNTRY_GROUPS,
        "categories": CATEGORIES,
        "markets": MARKETS,
        "platforms": [
            {"slug": p.slug, "name": p.name, "markets": json.loads(p.markets_json)}
            for p in platforms
        ],
        "last_updated": last_updated,
    }


@router.get("/radar")
def read_radar(
    country: str = "BR",
    platform: str | None = None,
    market: str | None = None,
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[dict]:
    if country not in COUNTRIES:
        raise HTTPException(status_code=422, detail="País inválido")

    platforms_by_slug = _platforms_by_slug(session)
    if platform is not None and platform not in platforms_by_slug:
        raise HTTPException(status_code=422, detail="Plataforma inválida")
    if market is not None and market not in MARKETS:
        raise HTTPException(status_code=422, detail="Mercado inválido")
    if category is not None and category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Categoria inválida")

    settings = get_settings(session)
    if country not in settings.get("countries", []):
        return []

    last_day = session.exec(
        select(func.max(TopicScore.day)).where(TopicScore.country == country)
    ).first()
    if last_day is None:
        return []

    rows = session.exec(
        select(TopicScore).where(TopicScore.country == country, TopicScore.day == last_day)
    ).all()
    if not rows:
        return []

    topic_ids = {row.topic_id for row in rows}
    topics_by_id = {
        t.id: t for t in session.exec(select(Topic).where(Topic.id.in_(topic_ids))).all()
    }

    def _row_passes_filters(row: TopicScore) -> bool:
        if platform is not None and row.platform != platform:
            return False
        if market is not None:
            row_platform = platforms_by_slug.get(row.platform)
            if row_platform is None or market not in json.loads(row_platform.markets_json):
                return False
        if category is not None:
            topic = topics_by_id.get(row.topic_id)
            if topic is None or topic.category != category:
                return False
        return True

    rows_by_topic: dict[int, list[TopicScore]] = defaultdict(list)
    for row in rows:
        if _row_passes_filters(row):
            rows_by_topic[row.topic_id].append(row)

    best_rows: dict[int, TopicScore] = {}
    for topic_id, topic_rows in rows_by_topic.items():
        best_rows[topic_id] = max(topic_rows, key=lambda r: r.opportunity * r.fit_platform)

    ordered_topic_ids = sorted(
        best_rows.keys(), key=lambda tid: best_rows[tid].opportunity, reverse=True
    )[:limit]

    if not ordered_topic_ids:
        return []

    # ---- mediana de preco: uma unica consulta para todos os topicos retornados
    topic_items = session.exec(
        select(TopicItem, RawItem)
        .join(RawItem, TopicItem.raw_item_id == RawItem.id)
        .where(TopicItem.topic_id.in_(ordered_topic_ids), RawItem.price_usd > 0)
    ).all()
    prices_by_topic_and_source: dict[tuple[int, str], list[float]] = defaultdict(list)
    for topic_item, raw_item in topic_items:
        prices_by_topic_and_source[(topic_item.topic_id, raw_item.source)].append(raw_item.price_usd)

    # ---- sparkline: uma unica consulta para os ultimos 30 dias de todos os topicos
    window_start = last_day - timedelta(days=SPARKLINE_DAYS - 1)
    sparkline_rows = session.exec(
        select(TopicScore.topic_id, TopicScore.day, TopicScore.opportunity).where(
            TopicScore.topic_id.in_(ordered_topic_ids),
            TopicScore.country == country,
            TopicScore.day >= window_start,
            TopicScore.day <= last_day,
        )
    ).all()
    max_opportunity_by_topic_and_day: dict[int, dict] = defaultdict(dict)
    for topic_id, day, opportunity in sparkline_rows:
        current = max_opportunity_by_topic_and_day[topic_id].get(day)
        if current is None or opportunity > current:
            max_opportunity_by_topic_and_day[topic_id][day] = opportunity

    today = clock.today()
    result = []
    for topic_id in ordered_topic_ids:
        topic = topics_by_id[topic_id]
        best_row = best_rows[topic_id]
        best_platform = platforms_by_slug[best_row.platform]

        prices = prices_by_topic_and_source.get((topic_id, best_row.platform), [])
        median_price_usd = round(statistics.median(prices), 2) if prices else None

        day_values = max_opportunity_by_topic_and_day.get(topic_id, {})
        sparkline = [
            {"day": day.isoformat(), "value": day_values[day]} for day in sorted(day_values)
        ]

        result.append(
            {
                "topic_id": topic.id,
                "slug": topic.slug,
                "name": topic.name,
                "category": topic.category,
                "image_url": topic.image_url,
                "reason": topic.reason,
                "opportunity": best_row.opportunity,
                "sale_chance": sale_chance(best_row.opportunity),
                "estimate": True,
                "momentum_arrow": momentum_arrow(best_row.momentum_raw),
                "days_to_peak": (best_row.peak_day - today).days,
                "best_platform": {"slug": best_platform.slug, "name": best_platform.name},
                "median_price_usd": median_price_usd,
                "sparkline": sparkline,
            }
        )

    return result
