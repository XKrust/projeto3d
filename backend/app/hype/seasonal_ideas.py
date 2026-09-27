"""Procura e concorrência das ideias de modelo de cada data sazonal.

Rodam 1x por dia dentro do pipeline:
- `update_seasonal_signals`: para cada ideia e país ativo, soma o `metric` dos itens dos
  últimos 30 dias cujo título+tags cita alguma keyword da ideia, fonte por fonte. Entram
  as fontes de plataforma (qualquer país) e as demais fontes do próprio país (ou GLOBAL);
  fontes de estreia (AniList, TMDB, IGDB) não contam como procura. Cada fonte vira
  percentil entre as ideias que ela cita antes de somar (como no radar), para um vídeo
  viral ou uma fonte de escala grande não decidir sozinha.
- `update_seasonal_listings`: conta anúncios do termo de busca (`query`) das ideias das
  datas próximas (começar a modelar nos próximos 60 dias, ou atrasadas com o evento ainda
  por vir), no máximo 20 termos, com os mesmos contadores da saturação do radar.
"""

import json
import logging
from collections import defaultdict
from datetime import date, timedelta

from sqlmodel import Session, select

from app.collectors.base import ListingCounter
from app.constants import GLOBAL
from app.daily import claim_daily
from app.hype.seasonal import event_ideas, load_events, upcoming_events
from app.models import RawItem, SeasonalIdeaSignal, SeasonalListing
from app.scoring import formulas
from app.settings_store import get_settings
from app.topics.normalize import matches_phrase, normalize

logger = logging.getLogger(__name__)

SIGNAL_DAYS = 30
LISTING_WINDOW_DAYS = 60
MAX_TERMS = 20
MAX_CONSECUTIVE_FAILURES = 3
# Fontes de estreias: o título do lançamento não é procura por modelo 3D.
RELEASE_SOURCES = frozenset({"anilist", "tmdb", "igdb"})


def _all_ideas() -> list[dict]:
    """Ideias únicas (por nome) de todas as datas."""
    seen: dict[str, dict] = {}
    for event in load_events():
        for idea in event_ideas(event):
            seen.setdefault(idea["name"], idea)
    return list(seen.values())


def update_seasonal_signals(session: Session, day: date) -> int:
    """Grava `SeasonalIdeaSignal` de hoje (1x por dia). Retorna o número de linhas."""
    from app.topics.extract import PLATFORM_SOURCES

    if session.exec(select(SeasonalIdeaSignal.id).where(SeasonalIdeaSignal.day == day)).first():
        return 0

    countries = get_settings(session).get("countries", [])
    start = day - timedelta(days=SIGNAL_DAYS - 1)
    items = session.exec(
        select(RawItem).where(
            RawItem.day >= start, RawItem.day <= day, RawItem.source.not_in(RELEASE_SOURCES)
        )
    ).all()
    haystacks = [
        (normalize(" ".join([item.title, *json.loads(item.tags_json or "[]")])), item)
        for item in items
    ]
    ideas = _all_ideas()
    matched: dict[str, list[RawItem]] = {}
    for idea in ideas:
        keywords = [normalize(k) for k in idea.get("keywords", []) if k]
        matched[idea["name"]] = [
            item for text, item in haystacks if any(matches_phrase(text, k) for k in keywords)
        ]

    written = 0
    for country in countries:
        # fonte → ideia → soma do metric dos itens que valem para o país
        by_source: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for name, idea_items in matched.items():
            for item in idea_items:
                if item.source in PLATFORM_SOURCES or item.country in (country, GLOBAL):
                    by_source[item.source][name] += item.metric
        signal: dict[str, float] = defaultdict(float)
        for by_idea in by_source.values():
            for name, rank in formulas.percentile_ranks(dict(by_idea)).items():
                signal[name] += rank
        for idea in ideas:
            session.add(
                SeasonalIdeaSignal(
                    idea=idea["name"], country=country, day=day, signal=round(signal[idea["name"]], 4)
                )
            )
            written += 1
    session.commit()
    return written


def _upcoming_terms(session: Session, day: date, lead_days: int, modeling_days: int) -> list[str]:
    countries = get_settings(session).get("countries", [])
    events: dict[str, dict] = {}
    for country in countries:
        for event in upcoming_events(country, day, lead_days, modeling_days):
            upcoming = event["days_to_start"] <= LISTING_WINDOW_DAYS and event["days_to_event"] >= 0
            if upcoming:
                events.setdefault(event["slug"], event)
    terms: list[str] = []
    for event in sorted(events.values(), key=lambda e: e["start_by"]):
        for idea in event_ideas(event["_event"]):
            if idea["query"] not in terms:
                terms.append(idea["query"])
    return terms[:MAX_TERMS]


def update_seasonal_listings(
    session: Session,
    counters: dict[str, ListingCounter],
    day: date,
    *,
    lead_days: int,
    modeling_days: int,
) -> int:
    """Grava `SeasonalListing` de hoje (1x por dia). A falha de um termo só pula aquele
    termo; 3 falhas seguidas abandonam a plataforma no dia."""
    if not counters or session.exec(select(SeasonalListing.id).where(SeasonalListing.day == day)).first():
        return 0
    if not claim_daily(session, "seasonal_listings", day):
        return 0
    terms = _upcoming_terms(session, day, lead_days, modeling_days)
    written = 0
    for platform, counter in counters.items():
        failures = 0
        for term in terms:
            try:
                count = counter.count_listings(term)
            except Exception:
                logger.exception("Contagem sazonal falhou em %s para %r", platform, term)
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    break
                continue
            failures = 0
            session.add(SeasonalListing(term=term, platform=platform, day=day, count=int(count)))
            written += 1
        session.commit()
    return written


def latest_signals(session: Session, country: str, today: date) -> dict[str, float]:
    """idea → sinal do dia mais recente medido (até hoje) no país."""
    latest: dict[str, tuple[date, float]] = {}
    rows = session.exec(
        select(SeasonalIdeaSignal).where(SeasonalIdeaSignal.country == country, SeasonalIdeaSignal.day <= today)
    ).all()
    for row in rows:
        if row.idea not in latest or row.day > latest[row.idea][0]:
            latest[row.idea] = (row.day, row.signal)
    return {idea: signal for idea, (_, signal) in latest.items()}


def latest_competition(session: Session, today: date) -> dict[str, dict[str, int]]:
    """termo → {plataforma: anúncios} do dia mais recente medido (até hoje)."""
    latest: dict[tuple[str, str], tuple[date, int]] = {}
    for row in session.exec(select(SeasonalListing).where(SeasonalListing.day <= today)).all():
        key = (row.term, row.platform)
        if key not in latest or row.day > latest[key][0]:
            latest[key] = (row.day, row.count)
    result: dict[str, dict[str, int]] = {}
    for (term, platform), (_, count) in latest.items():
        result.setdefault(term, {})[platform] = count
    return result
