"""Venda: línguas do título, lojas, preço (estimativa em euro) e chance (spec 3b §1–§4)."""

import json
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from statistics import median

import yaml
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import CountryRank, Platform, RawItem, Topic, TopicScore
from app.scoring import formulas
from app.topics.normalize import matches_phrase, normalize

RANGES_FILE = Path(__file__).resolve().parent.parent / "seed" / "price_ranges.yaml"
LANGUAGE_BY_COUNTRY = {
    "US": "en", "GB": "en", "CA": "en", "AU": "en", "BR": "pt", "DE": "de", "FR": "fr", "ES": "es",
    "MX": "es", "IT": "it", "PL": "pl", "NL": "nl", "RU": "ru", "BY": "ru", "JP": "ja",
}
DEFAULT_LANGUAGES = ["de", "ja"]
DEFAULT_TOP_COUNTRIES = ["US", "DE", "GB"]
TOP_COUNTRIES = 3
TOP_STORES = 3
COMPARABLE_DAYS = 90
MIN_COMPARABLES = 3
MIN_ALIAS = 4


@cache
def _ranges() -> dict:
    with open(RANGES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ranking(session: Session, day: date) -> list[CountryRank]:
    last = session.exec(select(func.max(CountryRank.day)).where(CountryRank.day <= day)).first()
    if last is None:
        return []
    return list(session.exec(select(CountryRank).where(CountryRank.day == last).order_by(CountryRank.position)))


def target_languages(session: Session, day: date) -> list[str]:
    """As 2 primeiras línguas (≠ inglês e português) na ordem do ranking de países."""
    languages: list[str] = []
    for row in _ranking(session, day):
        lang = LANGUAGE_BY_COUNTRY.get(row.country)
        if lang and lang not in ("en", "pt") and lang not in languages:
            languages.append(lang)
    for lang in DEFAULT_LANGUAGES:
        if len(languages) >= 2:
            break
        if lang not in languages:
            languages.append(lang)
    return languages[:2]


def rank_stores(session: Session, day: date, category: str, market: str) -> list[str]:
    """As 3 lojas que vendem com maior força nos 3 primeiros países do ranking, no mercado."""
    ranking = _ranking(session, day)[:TOP_COUNTRIES]
    weights = {r.country: r.score for r in ranking} or dict.fromkeys(DEFAULT_TOP_COUNTRIES, 1.0)
    scored = []
    for p in session.exec(select(Platform).where(Platform.sells)).all():
        if market not in json.loads(p.markets_json):
            continue
        strength = json.loads(p.strength_json)
        categories = json.loads(p.categories_json)
        value = sum(w * formulas.platform_fit(strength.get(c, 0.0), categories, category) for c, w in weights.items())
        if value > 0:
            scored.append((value, p.name))
    scored.sort(key=lambda v: (-v[0], v[1]))
    return [name for _, name in scored[:TOP_STORES]]


def _quality_factor(overall: float | None) -> float:
    return 1.0 if overall is None else 0.7 + 0.06 * overall


def _comparables(session: Session, day: date, phrases: list[str]) -> list[float]:
    selling = set(session.exec(select(Platform.slug).where(Platform.sells)).all())
    rows = session.exec(
        select(RawItem).where(
            RawItem.price_usd > 0,
            RawItem.day >= day - timedelta(days=COMPARABLE_DAYS),
            RawItem.day <= day,
        )
    ).all()
    prices = []
    for row in rows:
        if row.source not in selling:
            continue
        text = normalize(" ".join([row.title, *json.loads(row.tags_json or "[]")]))
        if any(matches_phrase(text, p) for p in phrases):
            prices.append(row.price_usd)
    return prices


def estimate_price(
    session: Session,
    day: date,
    *,
    query: str,
    character: str | None,
    category: str,
    overall: float | None,
    rates: dict[str, float],
    fx_source: str,
) -> dict:
    """Preço estimado em euro: mediana de ≥ 3 anúncios parecidos, senão a faixa típica da
    categoria; × fator de qualidade da nota; convertido pelo câmbio dado."""
    phrases = [normalize(p) for p in (query, character) if p and len(normalize(p)) >= MIN_ALIAS]
    prices = _comparables(session, day, phrases) if phrases else []
    factor = _quality_factor(overall)
    usd_per_eur = rates["USD"]
    if len(prices) >= MIN_COMPARABLES:
        base, low, high = median(prices) * factor, min(prices), max(prices)
        basis, sample = "comparaveis", len(prices)
        basis_text = f"baseado em {len(prices)} anúncios parecidos coletados pelo app"
    else:
        ranges = _ranges()
        cat = ranges["categories"].get(category) or ranges["categories"]["outros"]
        base, low, high = cat["typical_usd"] * factor, cat["low_usd"] * factor, cat["high_usd"] * factor
        basis, sample = "faixa_categoria", 0
        basis_text = f"{ranges['source']}: {cat['label']}"
    return {
        "eur": round(base / usd_per_eur, 2),
        "low_eur": round(low / usd_per_eur, 2),
        "high_eur": round(high / usd_per_eur, 2),
        "basis": basis,
        "basis_text": basis_text,
        "sample": sample,
        "quality_factor": round(factor, 2),
        "fx_source": fx_source,
    }


def estimate_chance(
    session: Session, day: date, *, theme: str, character: str | None, query: str, overall: float | None
) -> tuple[dict | None, str | None]:
    """Chance = oportunidade do tema no radar (1º país do ranking) × nota/10."""
    if overall is None:
        return None, "Sem nota da análise para estimar"
    texts = [normalize(t) for t in (theme, character, query) if t]
    best: TopicScore | None = None
    ranking = _ranking(session, day)
    country = ranking[0].country if ranking else None
    last = session.exec(select(func.max(TopicScore.day)).where(TopicScore.day <= day)).first()
    for topic in session.exec(select(Topic)).all():
        names = [normalize(topic.name), *(normalize(a) for a in json.loads(topic.aliases_json or "[]"))]
        names = [n for n in names if len(n) >= MIN_ALIAS]
        if not any(matches_phrase(t, n) for t in texts for n in names):
            continue
        query_scores = select(TopicScore).where(TopicScore.topic_id == topic.id, TopicScore.day == last)
        if country:
            query_scores = query_scores.where(TopicScore.country == country)
        for row in session.exec(query_scores).all():
            if best is None or row.opportunity > best.opportunity:
                best = row
    if best is None:
        return None, "Tema ainda sem dados no radar"
    score = round(best.opportunity * overall / 10, 1)
    return {"score": score, "label": formulas.sale_chance(score)}, None
