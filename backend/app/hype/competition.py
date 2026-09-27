"""Concorrência dos lançamentos do hype: quantos anúncios cada título ou personagem já tem
em cada plataforma. Roda 1x por dia, dentro do pipeline, com os mesmos contadores
(`count_listings`) usados na saturação do radar."""

import logging
from datetime import date

from sqlmodel import Session, select

from app.collectors.base import ListingCounter
from app.hype.entities import base_title, recent_releases, top_characters, usable
from app.models import HypeListing

logger = logging.getLogger(__name__)

DEFAULT_TERMS = 15
MAX_CONSECUTIVE_FAILURES = 3


def hype_terms(session: Session, day: date, limit: int = DEFAULT_TERMS) -> list[str]:
    """Título (sem marca de temporada) + 2 personagens de cada lançamento, do mais
    popular para o menos, até `limit` termos distintos."""
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> bool:
        key = term.casefold()
        if usable(term) and key not in seen:
            seen.add(key)
            terms.append(term)
        return len(terms) >= limit

    for row in recent_releases(session, day):
        if add(base_title(row.title)):
            break
        if any(add(c["name"]) for c in top_characters(row.characters_json)):
            break
    return terms


def update_hype_listings(
    session: Session, counters: dict[str, ListingCounter], day: date, limit: int = DEFAULT_TERMS
) -> int:
    """Grava `HypeListing` de hoje para cada termo × plataforma. Não roda de novo se já
    houver contagem de hoje. A falha de um termo só pula aquele termo; 3 falhas seguidas
    abandonam a plataforma no dia. Retorna o número de linhas gravadas."""
    already = session.exec(select(HypeListing.id).where(HypeListing.day == day)).first()
    if already is not None or not counters:
        return 0

    terms = hype_terms(session, day, limit)
    written = 0
    for platform, counter in counters.items():
        failures = 0
        for term in terms:
            try:
                count = counter.count_listings(term)
            except Exception:
                logger.exception("Contagem do hype falhou em %s para %r", platform, term)
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    break
                continue
            failures = 0
            session.add(HypeListing(term=term, platform=platform, day=day, count=int(count)))
            written += 1
        session.commit()
    return written
