"""Pipeline pos-coleta: topicos -> saturacao (contagem de anuncios) -> scores.

Roda ao final de cada ciclo de coleta (callback `after` de `run_cycle`), ver o
fluxo em `docs/arquitetura.md#ciclo-de-coleta` e as formulas em `docs/score.md`.
"""

import json
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta

import httpx
from sqlalchemy import func
from sqlmodel import Session, select

import app.collectors as collectors_pkg
from app import clock
from app.ai.provider import get_text_provider
from app.collectors.base import ListingCounter
from app.constants import GLOBAL
from app.fx import update_fx_rates
from app.http import make_client
from app.runner import set_collect_phase
from app.models import Platform, RawItem, Topic, TopicItem, TopicListing, TopicScore, TopicSignal
from app.scoring import formulas
from app.settings_store import get_settings
from app.country_rank import compute_country_ranks
from app.daily import claim_daily
from app.hype.competition import update_hype_listings
from app.hype.seasonal_ideas import update_seasonal_listings, update_seasonal_signals
from app.topics.extract import PLATFORM_SOURCES, entity_names, entity_words, extract_topics, is_not_a_theme

logger = logging.getLogger(__name__)

PLATFORMS_GROUP = "platforms"
MAX_CONSECUTIVE_COUNT_FAILURES = 3
MOMENTUM_DAYS = 10
NO_LISTING_SATURATION = 50.0


# ---------------------------------------------------------------- saturacao


def _top_topic_ids(session: Session, day: date, top_n: int) -> list[int]:
    """Os `top_n` topicos pela maior oportunidade do ultimo dia com score; sem
    nenhum score ainda, pela soma dos sinais de `day`."""
    last_scored_day = session.exec(select(func.max(TopicScore.day)).where(TopicScore.day <= day)).first()
    if last_scored_day is not None:
        ranking = session.exec(
            select(TopicScore.topic_id, func.max(TopicScore.opportunity))
            .where(TopicScore.day == last_scored_day)
            .group_by(TopicScore.topic_id)
        ).all()
    else:
        ranking = session.exec(
            select(TopicSignal.topic_id, func.sum(TopicSignal.value))
            .where(TopicSignal.day == day)
            .group_by(TopicSignal.topic_id)
        ).all()

    ordered = sorted(ranking, key=lambda row: (-row[1], row[0]))
    return [topic_id for topic_id, _ in ordered[:top_n]]


def update_listings(session: Session, counters: dict[str, ListingCounter], day: date, top_n: int) -> int:
    """Grava `TopicListing` (contagem de anuncios por plataforma) dos `top_n`
    topicos principais. A consulta usa o `name` do topico. A falha de um termo
    so pula aquele topico; depois de `MAX_CONSECUTIVE_COUNT_FAILURES` falhas
    seguidas, a plataforma e abandonada no dia (fonte fora do ar ou chave
    invalida). Retorna o numero de linhas gravadas."""
    topic_ids = _top_topic_ids(session, day, top_n)
    if not topic_ids or not counters or not claim_daily(session, "radar_listings", day):
        return 0

    topics = {t.id: t for t in session.exec(select(Topic).where(Topic.id.in_(topic_ids))).all()}
    written = 0

    for platform, counter in counters.items():
        counts: dict[int, int] = {}
        failures = 0
        for topic_id in topic_ids:
            try:
                counts[topic_id] = counter.count_listings(topics[topic_id].name)
                failures = 0
            except Exception:
                logger.exception("Contagem de anuncios falhou em %s para %r", platform, topics[topic_id].name)
                failures += 1
                if failures >= MAX_CONSECUTIVE_COUNT_FAILURES:
                    logger.warning("Contagem de anuncios abandonada na plataforma %s", platform)
                    break

        existing = {
            row.topic_id: row
            for row in session.exec(
                select(TopicListing).where(TopicListing.platform == platform, TopicListing.day == day)
            ).all()
        }
        for topic_id, count in counts.items():
            row = existing.get(topic_id) or TopicListing(topic_id=topic_id, platform=platform, day=day, count=count)
            row.count = count
            session.add(row)
            written += 1
        session.commit()

    return written


# ---------------------------------------------------------------- scores


def _raw_demand_by_day(
    values: dict[date, dict[int, dict[str, float]]], source_weights: dict[str, float]
) -> dict[date, dict[int, float]]:
    """Demanda bruta por dia e topico: percentil do valor do dia por grupo de
    fonte, somado com os `source_weights` renormalizados sobre os grupos
    presentes naquele dia. So entram os topicos com sinal no dia."""
    result: dict[date, dict[int, float]] = {}
    for day, by_topic in values.items():
        groups = {group for by_group in by_topic.values() for group in by_group}
        weights = {group: source_weights.get(group, 0.0) for group in groups}
        total_weight = sum(weights.values())
        raw: dict[int, float] = {topic_id: 0.0 for topic_id in by_topic}
        if total_weight > 0:
            for group, weight in weights.items():
                ranks = formulas.percentile_ranks(
                    {topic_id: by_group.get(group, 0.0) for topic_id, by_group in by_topic.items()}
                )
                for topic_id, rank in ranks.items():
                    raw[topic_id] += weight * rank / total_weight
        result[day] = raw
    return result


def _latest_listing_saturation(session: Session, day: date, platforms: list[str]) -> dict[str, dict[int, float]]:
    """Percentil do `TopicListing.count` mais recente (ate `day`) entre os
    topicos de cada plataforma."""
    latest: dict[str, dict[int, tuple[date, int]]] = defaultdict(dict)
    rows = session.exec(
        select(TopicListing).where(TopicListing.platform.in_(platforms), TopicListing.day <= day)
    ).all()
    for row in rows:
        current = latest[row.platform].get(row.topic_id)
        if current is None or row.day > current[0]:
            latest[row.platform][row.topic_id] = (row.day, row.count)

    return {
        platform: formulas.percentile_ranks({topic_id: float(count) for topic_id, (_, count) in by_topic.items()})
        for platform, by_topic in latest.items()
    }


def compute_scores(session: Session, day: date) -> int:
    """Calcula e grava (upsert) `TopicScore` por (topico, pais ativo, plataforma
    com dado) em `day`. Retorna o numero de linhas gravadas. Ver `docs/score.md`."""
    settings = get_settings(session)
    countries: list[str] = settings["countries"]
    weights = settings["weights"]
    source_weights = settings["source_weights"]
    delivery = day + timedelta(days=int(settings["modeling_days"]))
    window_days = [day - timedelta(days=MOMENTUM_DAYS - 1 - i) for i in range(MOMENTUM_DAYS)]

    # Toda loja que vende concorre, mesmo sem dado coletado dela (o Cults3D sem chave é
    # onde muita gente vende). Loja fechada (`sells` falso) fica só como sinal.
    platforms = [p for p in session.exec(select(Platform)).all() if p.sells]
    if not platforms:
        return 0
    platform_slugs = [p.slug for p in platforms]
    strengths = {p.slug: json.loads(p.strength_json) for p in platforms}
    platform_categories = {p.slug: json.loads(p.categories_json) for p in platforms}

    saturation = _latest_listing_saturation(session, day, platform_slugs)

    # Palavra comum de dicionário ("Game") ou pedaço de tema ("Meshi") não é tema: sem
    # nota, e as linhas de hoje que sobraram de antes da regra são apagadas.
    entities = entity_names(session, day)
    known_words = entity_words(session, day)
    generic_ids = {
        topic.id
        for topic in session.exec(select(Topic)).all()
        if is_not_a_theme(topic.name, entities, known_words)
    }
    if generic_ids:
        for row in session.exec(
            select(TopicScore).where(TopicScore.day == day, TopicScore.topic_id.in_(generic_ids))
        ).all():
            session.delete(row)
        session.flush()

    # Todos os sinais da janela de 10 dias, numa consulta so.
    signals = session.exec(
        select(TopicSignal).where(
            TopicSignal.day >= window_days[0],
            TopicSignal.day <= day,
            TopicSignal.country.in_([*countries, GLOBAL]),
        )
    ).all()

    existing = {
        (row.topic_id, row.country, row.platform): row
        for row in session.exec(select(TopicScore).where(TopicScore.day == day)).all()
    }
    written = 0

    for country in countries:
        # dia -> topico -> grupo de fonte -> valor (pais + GLOBAL somados)
        values: dict[date, dict[int, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        # dia -> fonte de plataforma -> topico -> valor bruto
        platform_raw: dict[date, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        for signal in signals:
            if signal.country not in (country, GLOBAL):
                continue
            if signal.source in PLATFORM_SOURCES:
                platform_raw[signal.day][signal.source][signal.topic_id] += signal.value
            else:
                values[signal.day][signal.topic_id][signal.source] += signal.value
        # Cada fonte de plataforma mede numa escala propria (favoritos, downloads, posicao no
        # ranking...): vira percentil entre os topicos daquela fonte antes de somar no grupo
        # "platforms", para nenhuma fonte decidir sozinha pela escala.
        for day_, by_source in platform_raw.items():
            for by_topic in by_source.values():
                for topic_id, rank in formulas.percentile_ranks(dict(by_topic)).items():
                    values[day_][topic_id][PLATFORMS_GROUP] += rank

        topic_ids = {topic_id for by_topic in values.values() for topic_id in by_topic} - generic_ids
        if not topic_ids:
            continue

        categories = dict(
            session.exec(select(Topic.id, Topic.category).where(Topic.id.in_(topic_ids))).all()
        )
        raw_by_day = _raw_demand_by_day(values, source_weights)
        today_raw = raw_by_day.get(day, {})
        demand = formulas.percentile_ranks({topic_id: today_raw.get(topic_id, 0.0) for topic_id in topic_ids})

        for topic_id in topic_ids:
            series = [raw_by_day.get(d, {}).get(topic_id, 0.0) for d in window_days]
            m_raw = formulas.momentum_raw(series)
            momentum = formulas.momentum_score(m_raw)
            peak = formulas.peak_day(day, m_raw)
            fit_window = formulas.window_fit(peak, delivery)

            for platform in platform_slugs:
                sat = saturation.get(platform, {}).get(topic_id, NO_LISTING_SATURATION)
                # O filtro de mercado (impressão/digital) é aplicado na API.
                fit_platform = formulas.platform_fit(
                    float(strengths[platform].get(country, 0.0)),
                    platform_categories[platform],
                    categories.get(topic_id, "outros"),
                )
                opp = formulas.opportunity(demand[topic_id], momentum, sat, fit_window, weights)

                key = (topic_id, country, platform)
                row = existing.get(key)
                if row is None:
                    row = TopicScore(
                        topic_id=topic_id, country=country, platform=platform, day=day,
                        demand=0, momentum=0, momentum_raw=0, saturation=0, peak_day=day,
                        fit_window=0, fit_platform=0, opportunity=0,
                    )
                    existing[key] = row
                row.demand = demand[topic_id]
                row.momentum = momentum
                row.momentum_raw = m_raw
                row.saturation = sat
                row.peak_day = peak
                row.fit_window = fit_window
                row.fit_platform = fit_platform
                row.opportunity = opp
                session.add(row)
                written += 1

    session.commit()
    return written


# ---------------------------------------------------------------- orquestracao


def run_pipeline(
    session: Session,
    counters: dict[str, ListingCounter],
    *,
    enrich: Callable[[Session], None] | None = None,
) -> None:
    """extract_topics -> notas (compute_scores + ranking de países) -> concorrência (contagem de
    anúncios nas lojas, 1x por dia) -> notas de novo -> enrich.

    As notas vêm antes da concorrência de propósito: contar anúncios faz centenas de buscas com
    3–5 s de pausa entre elas (coleta educada) e leva mais de 10 minutos na primeira vez. Antes,
    o radar ficava vazio esse tempo todo; agora fica pronto em segundos e a concorrência só
    refina a saturação quando termina."""
    day = clock.today()
    extract_topics(session, day)
    # Top 5 de modelos por data sazonal: procura (local, rápido).
    update_seasonal_signals(session, day)

    compute_scores(session, day)
    # Ranking de países (usa as notas de hoje): quem subiu, quem caiu.
    compute_country_ranks(session, day)

    set_collect_phase("concorrencia")
    measured = False
    has_listing_today = session.exec(select(TopicListing.id).where(TopicListing.day == day)).first() is not None
    if not has_listing_today:
        top_n = int(get_settings(session)["top_n_saturation"])
        measured = update_listings(session, counters, day, top_n) > 0 or measured
    # Concorrência dos lançamentos do hype (1x por dia; a função se protege sozinha).
    measured = bool(update_hype_listings(session, counters, day)) or measured
    settings = get_settings(session)
    measured = bool(update_seasonal_listings(
        session,
        counters,
        day,
        lead_days=int(settings["lead_days"]),
        modeling_days=int(settings["modeling_days"]),
    )) or measured

    if measured:
        # Com a concorrência medida, a saturação muda: recalcula notas e ranking.
        compute_scores(session, day)
        compute_country_ranks(session, day)

    if enrich is not None:
        enrich(session)


def make_after(settings: dict, http: httpx.Client) -> Callable[[Session], None]:
    """Monta o callback `after` do ciclo: contadores de anuncios (`{platform:
    coletor}`) dos coletores de plataforma que implementam `count_listings` e
    tem todas as chaves exigidas."""
    api_keys = settings.get("api_keys", {})
    counters: dict[str, ListingCounter] = {}
    for cls in collectors_pkg.ALL_COLLECTORS:
        if not cls.platform or not callable(getattr(cls, "count_listings", None)):
            continue
        if not all(api_keys.get(key) for key in cls.needs_key):
            continue
        counters[cls.platform] = cls(settings, http)

    provider = get_text_provider(settings)
    enrich: Callable[[Session], None] | None = None
    if provider is not None:
        from app.topics.enrich import enrich_topics

        def enrich(session: Session) -> None:
            enrich_topics(session, provider, clock.today())

    return lambda session: run_pipeline(session, counters, enrich=enrich)


def run_after_cycle(session: Session) -> None:
    """Callback `after` usado pelo agendador e por POST /api/collect: le as
    configuracoes atuais e roda o pipeline com um cliente HTTP proprio (o do
    ciclo ja foi fechado quando `after` e chamado)."""
    settings = get_settings(session)
    with make_client() as http:
        # Câmbio do dia (1x por dia; falha só vai para o log) antes do pipeline.
        update_fx_rates(session, http, clock.today())
        make_after(settings, http)(session)
