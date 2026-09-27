"""Lançamentos do hype viram entidades do radar.

Cada `HypeRelease` recente e popular vira uma entidade `{name, category, aliases}` para
`extract_topics`, junto com as de `seed/entities.yaml`. Os títulos alternativos
(inclusive em japonês, vindos do AniList) viram aliases. Assim, um anúncio do BOOTH
escrito em japonês casa com o tópico em inglês. Os 2 personagens mais favoritados de
cada anime também viram entidades.
"""

import json
import re
from datetime import date, timedelta

from sqlmodel import Session, or_, select

from app.models import HypeRelease
from app.topics.normalize import is_cjk, normalize

WINDOW_BEFORE_DAYS = 60
WINDOW_AFTER_DAYS = 180
STALE_DAYS = 7
TOP_CHARACTERS = 2
MIN_CHARACTER_FAVOURITES = 500
MIN_LATIN_ALIAS = 4
MIN_CJK_ALIAS = 2

KIND_CATEGORY = {
    "anime": "anime",
    "filme": "filmes_series",
    "serie": "filmes_series",
    "jogo": "games",
}

# Marcas de temporada/parte no fim do título: "Season 3", "3rd Season", "第3期",
# "Part 2", "2" solto. Tirá-las deixa o alias casar com anúncios que não citam a
# temporada.
_SEASON_PATTERNS = [
    re.compile(r"\s*\b(season|temporada)\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"\s*\b\d+(st|nd|rd|th)\s+season\s*$", re.IGNORECASE),
    re.compile(r"\s*\bpart\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"\s*第\s*\d+\s*期\s*$"),
    re.compile(r"\s+\d\s*$"),
]


def base_title(title: str) -> str:
    """Título sem a marca de temporada ou parte no fim."""
    result = title.strip()
    changed = True
    while changed:
        changed = False
        for pattern in _SEASON_PATTERNS:
            stripped = pattern.sub("", result).strip()
            if stripped and stripped != result:
                result, changed = stripped, True
    return result


def _usable(name: str | None) -> bool:
    """Nome longo o bastante para não casar com qualquer texto ("D", "Rem")."""
    if not name:
        return False
    key = normalize(name)
    return len(key) >= (MIN_CJK_ALIAS if is_cjk(key) else MIN_LATIN_ALIAS)


def _unique(values: list[str], exclude: str) -> list[str]:
    seen = {normalize(exclude)}
    result = []
    for value in values:
        key = normalize(value)
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def hype_entities(session: Session, day: date, limit: int = 25) -> list[dict]:
    """Entidades dos `limit` lançamentos mais populares, com estreia entre 60 dias
    atrás e 180 dias à frente (ou sem data) e coletados nos últimos 7 dias."""
    rows = session.exec(
        select(HypeRelease)
        .where(
            HypeRelease.updated_day >= day - timedelta(days=STALE_DAYS),
            or_(
                HypeRelease.release_date.is_(None),
                HypeRelease.release_date.between(
                    day - timedelta(days=WINDOW_BEFORE_DAYS), day + timedelta(days=WINDOW_AFTER_DAYS)
                ),
            ),
        )
        .order_by(HypeRelease.popularity.desc())
    ).all()

    entities: list[dict] = []
    seen: set[str] = set()

    def add(name: str, category: str, aliases: list[str]) -> None:
        key = normalize(name)
        if not _usable(name) or key in seen:
            return
        seen.add(key)
        entities.append(
            {"name": name, "category": category, "aliases": _unique([a for a in aliases if _usable(a)], name)}
        )

    releases_used = 0
    for row in rows:
        if releases_used >= limit:
            break
        name = base_title(row.title)
        if not _usable(name) or normalize(name) in seen:
            continue
        releases_used += 1
        category = KIND_CATEGORY.get(row.kind, "outros")
        raw_aliases = json.loads(row.aliases_json or "[]")
        aliases = [base_title(a) for a in raw_aliases] + raw_aliases
        if row.title != name:
            aliases.append(row.title)
        add(name, category, aliases)

        characters = sorted(
            json.loads(row.characters_json or "[]"), key=lambda c: -int(c.get("favourites") or 0)
        )[:TOP_CHARACTERS]
        for character in characters:
            if int(character.get("favourites") or 0) < MIN_CHARACTER_FAVOURITES:
                continue
            native = character.get("native")
            add(character.get("name") or "", category, [native] if native else [])
    return entities
