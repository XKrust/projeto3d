"""Lojas por país e países padrão da venda (spec 3b §4).

Usa a mesma fórmula do radar (`formulas.platform_fit`): força de venda no país ×
afinidade com a categoria do tema.
"""

import json

from sqlalchemy import func
from sqlmodel import Session, select

from app.constants import COUNTRIES, in_country
from app.models import CountryRank, Platform
from app.scoring.formulas import platform_fit
from app.settings_store import get_settings

TOP_STORES = 3
TOP_COUNTRIES = 3
HOME_COUNTRY = "BR"

CATEGORY_LABELS = {
    "anime": "Anime",
    "games": "Games",
    "filmes_series": "Filmes e séries",
    "toys_memes": "Toys e memes",
    "rpg_miniaturas": "RPG e miniaturas",
    "decoracao": "Decoração",
    "outros": "Outros",
}


def _decimal(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _why(country: str, strength: float, categories: list[str], category: str) -> str:
    label = CATEGORY_LABELS.get(category, category)
    if not categories:
        affinity = "generalista"
    elif category in categories:
        affinity = f"forte em {label}"
    else:
        affinity = f"{label} não é o forte da loja"
    return f"Força de venda {in_country(country)}: {_decimal(strength)} · {affinity}"


def rank_stores(session: Session, country: str, *, market: str, category: str) -> list[dict]:
    """As 3 lojas com maior encaixe no país (só as que vendem e aceitam o mercado)."""
    stores = []
    for platform in session.exec(select(Platform).where(Platform.sells)).all():
        if market not in json.loads(platform.markets_json):
            continue
        strength = json.loads(platform.strength_json).get(country)
        if not strength:
            continue
        categories = json.loads(platform.categories_json or "[]")
        stores.append({
            "platform": platform.slug,
            "name": platform.name,
            "fee_pct": platform.fee_pct,
            "fit": round(platform_fit(strength, categories, category), 2),
            "why": _why(country, strength, categories, category),
        })
    stores.sort(key=lambda s: s["platform"])
    stores.sort(key=lambda s: s["fit"], reverse=True)
    return stores[:TOP_STORES]


def default_countries(session: Session) -> list[str]:
    """Os 3 primeiros do ranking do dia entre os países ativos, mais o BR (se ativo)."""
    active = [c for c in COUNTRIES if c in get_settings(session).get("countries", [])]
    last_day = session.exec(select(func.max(CountryRank.day))).first()
    ranked: list[str] = []
    if last_day is not None:
        rows = session.exec(
            select(CountryRank).where(CountryRank.day == last_day).order_by(CountryRank.position)
        ).all()
        ranked = [row.country for row in rows if row.country in active]
    ordered = ranked + [c for c in active if c not in ranked]
    chosen = ordered[:TOP_COUNTRIES]
    if HOME_COUNTRY in active and HOME_COUNTRY not in chosen:
        chosen.append(HOME_COUNTRY)
    return chosen
