"""Preço sugerido a partir dos anúncios comparáveis coletados (spec 3b §5).

Todo preço é estimativa em US$ e traz `basis`: de onde veio o número.
"""

import json
import math
import statistics
from datetime import timedelta

from sqlmodel import Session, select

from app import clock
from app.models import Platform, RawItem, Topic, TopicItem
from app.sale.stores import CATEGORY_LABELS

MIN_ITEMS = 5
WINDOW_DAYS = 90
LAUNCH_DISCOUNT = 0.8
NO_DATA = "sem dados suficientes para esta loja"


def _latest_unique(rows: list[RawItem]) -> list[RawItem]:
    """Um item por `source` + `external_id`, o do dia mais recente."""
    latest: dict[tuple[str, str], RawItem] = {}
    for item in rows:
        key = (item.source, item.external_id)
        if key not in latest or item.day > latest[key].day:
            latest[key] = item
    return list(latest.values())


def _priced(session: Session, topic_ids: list[int], sources: list[str]) -> list[RawItem]:
    if not topic_ids or not sources:
        return []
    since = clock.today() - timedelta(days=WINDOW_DAYS)
    rows = session.exec(
        select(RawItem)
        .join(TopicItem, TopicItem.raw_item_id == RawItem.id)
        .where(TopicItem.topic_id.in_(topic_ids), RawItem.source.in_(sources),
               RawItem.price_usd > 0, RawItem.day >= since)
        .distinct()
    ).all()
    return _latest_unique(list(rows))


def comparable_items(session: Session, *, topic: Topic | None, platform: str, platform_name: str,
                     category: str) -> tuple[list[RawItem], str]:
    """Itens da primeira camada com pelo menos 5: tópico na loja → tópico em qualquer loja
    que vende → categoria na loja. Sem camada suficiente → ([], NO_DATA)."""
    if topic is not None:
        items = _priced(session, [topic.id], [platform])
        if len(items) >= MIN_ITEMS:
            return items, f"mediana de {len(items)} anúncios de {topic.name} no {platform_name}"
        selling = [p.slug for p in session.exec(select(Platform).where(Platform.sells)).all()]
        items = _priced(session, [topic.id], selling)
        if len(items) >= MIN_ITEMS:
            return items, f"mediana de {len(items)} anúncios de {topic.name} em todas as lojas"
    same_category = session.exec(
        select(Topic.id).where(Topic.category == category, Topic.is_candidate == False)  # noqa: E712
    ).all()
    items = _priced(session, list(same_category), [platform])
    if len(items) >= MIN_ITEMS:
        label = CATEGORY_LABELS.get(category, category)
        return items, f"mediana de {len(items)} anúncios de {label} no {platform_name}"
    return [], NO_DATA


def round_99(value: float) -> float:
    """Arredonda para o `.99` mais próximo (mínimo US$ 0,99)."""
    return max(0.99, round(math.floor(value + 0.5) - 0.01, 2))


def quality_factor(overall: float | None) -> float:
    return 1.0 if overall is None else round(0.7 + 0.06 * overall, 4)


def price_for_store(prices: list[float], *, overall: float | None, fee_pct: float | None,
                    basis: str) -> dict | None:
    if len(prices) < MIN_ITEMS:
        return None
    factor = quality_factor(overall)
    low, median, high = statistics.quantiles(prices, n=4, method="inclusive")
    suggested = round_99(median * factor)
    return {
        "suggested": suggested,
        "low": round_99(low * factor),
        "high": round_99(high * factor),
        "launch": round_99(suggested * LAUNCH_DISCOUNT),
        "net": None if fee_pct is None else round(suggested * (1 - fee_pct / 100), 2),
        "basis": basis,
    }


def sales_to_cover(*, hours: float | None, hourly_rate: float, price: float | None) -> int | None:
    """Quantas vendas pagam as horas gastas ao valor/hora dado."""
    if not hours or not price:
        return None
    return math.ceil(hours * hourly_rate / price)


def item_tags(items: list[RawItem]) -> list[list[str]]:
    return [json.loads(item.tags_json or "[]") for item in items]
