"""Rota do radar (/api/radar, /api/radar/meta): scores por topico, filtros e sparkline."""

import json
import statistics
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app import clock
from app.constants import CATEGORIES, COUNTRIES, MARKETS
from app.db import get_session
from app.models import Platform, RawItem, Source, Topic, TopicItem, TopicScore
from app.scoring.formulas import momentum_arrow, sale_chance
from app.settings_store import get_settings

router = APIRouter()

COUNTRY_GROUPS = {"Europa": ["GB", "DE", "FR", "ES", "IT", "PL", "NL"]}
SPARKLINE_DAYS = 30


TOP_PLATFORMS = 3


def _platforms_by_slug(session: Session) -> dict[str, Platform]:
    """Só as lojas que vendem: Sketchfab e ArtStation (lojas fechadas) ficam de fora."""
    return {p.slug: p for p in session.exec(select(Platform).where(Platform.sells)).all()}


@router.get("/radar/meta")
def read_meta(session: Session = Depends(get_session)) -> dict:
    platforms = _platforms_by_slug(session).values()
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
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[dict]:
    # Um filtro vazio na URL (ex.: `?platform=`, do exemplo do brief) chega aqui como
    # string vazia, nao None - normaliza para "sem filtro" antes de validar.
    platform = platform or None
    market = market or None
    category = category or None

    if country not in COUNTRIES:
        raise HTTPException(status_code=422, detail="País inválido")

    if not (1 <= limit <= 200):
        raise HTTPException(status_code=422, detail="Limite deve estar entre 1 e 200")

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
        if row.platform not in platforms_by_slug:  # score antigo de loja que fechou
            return False
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
    ranked_rows: dict[int, list[TopicScore]] = {}
    for topic_id, topic_rows in rows_by_topic.items():
        # Ordena por slug antes para que um empate em opportunity * fit_platform sempre
        # resolva para a mesma plataforma (a primeira em ordem alfabetica), nao para a
        # ordem de retorno do banco (sorted é estável).
        candidates = sorted(topic_rows, key=lambda r: r.platform)
        ranked = sorted(candidates, key=lambda r: r.opportunity * r.fit_platform, reverse=True)
        ranked_rows[topic_id] = ranked
        best_rows[topic_id] = ranked[0]

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
    # Um preço por anúncio: o mesmo item coletado em vários dias conta uma vez só (o do dia
    # mais recente), igual a app/sale/pricing.py.
    latest: dict[tuple[int, str, str], RawItem] = {}
    for topic_item, raw_item in topic_items:
        key = (topic_item.topic_id, raw_item.source, raw_item.external_id)
        if key not in latest or raw_item.day > latest[key].day:
            latest[key] = raw_item
    prices_by_topic_and_source: dict[tuple[int, str], list[float]] = defaultdict(list)
    for (topic_id, source, _), raw_item in latest.items():
        prices_by_topic_and_source[(topic_id, source)].append(raw_item.price_usd)

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
                # As 3 melhores lojas para vender o tema, da melhor para a pior.
                "platforms": [
                    {"slug": r.platform, "name": platforms_by_slug[r.platform].name}
                    for r in ranked_rows[topic_id][:TOP_PLATFORMS]
                ],
                "median_price_usd": median_price_usd,
                "sparkline": sparkline,
            }
        )

    return result
