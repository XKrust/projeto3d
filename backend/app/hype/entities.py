"""Lançamentos do hype viram entidades do radar.

Cada `HypeRelease` recente e popular vira uma entidade `{name, category, aliases}` para
`extract_topics`, junto com as de `seed/entities.yaml`. Os títulos alternativos
(inclusive em japonês, vindos do AniList) viram aliases. Assim, um anúncio do BOOTH
escrito em japonês casa com o tópico em inglês. Os 2 personagens mais favoritados de
cada anime (com nome de 2+ palavras ou 3+ caracteres CJK) também viram entidades.
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
MIN_CHARACTER_WORDS = 2
MIN_CJK_CHARACTER = 3

KIND_CATEGORY = {
    "anime": "anime",
    "filme": "filmes_series",
    "serie": "filmes_series",
    "jogo": "games",
}

# Marcas de temporada/parte no fim do título: "Season 3", "3rd Season", "第3期",
# "Part 2". Tirá-las deixa o alias casar com anúncios que não citam a temporada.
_SEASON_PATTERNS = [
    re.compile(r"\s*\b(season|temporada)\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"\s*\b\d+(st|nd|rd|th)\s+season\s*$", re.IGNORECASE),
    re.compile(r"\s*\bpart\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"\s*第\s*\d+\s*期\s*$"),
]
# "2" solto no fim só é temporada em anime ("Cyberpunk: Edgerunners 2"). Em jogo e filme
# faz parte do nome ("Persona 5", "Toy Story 5"), e "No. 8" também ("Kaiju No. 8").
_ANIME_BARE_NUMBER = re.compile(r"(?<!no\.)(?<!no)(?<!#)\s+\d\s*$", re.IGNORECASE)


def base_title(title: str, kind: str) -> str:
    """Título sem a marca de temporada ou parte no fim."""
    patterns = _SEASON_PATTERNS + ([_ANIME_BARE_NUMBER] if kind == "anime" else [])
    result = title.strip()
    changed = True
    while changed:
        changed = False
        for pattern in patterns:
            stripped = pattern.sub("", result).strip()
            if stripped and stripped != result:
                result, changed = stripped, True
    return result


def usable(name: str | None) -> bool:
    """Nome longo o bastante para não casar com qualquer texto ("D", "Rem")."""
    if not name:
        return False
    key = normalize(name)
    return len(key) >= (MIN_CJK_ALIAS if is_cjk(key) else MIN_LATIN_ALIAS)


def usable_character(name: str | None) -> bool:
    """Nome de personagem distinto o bastante: 2+ palavras ("Anya Forger") ou 3+
    caracteres CJK ("早川アキ"). Nome de uma palavra comum ("Power", "Fern", "Stark")
    e nativo curto ("レゼ" está dentro de "プレゼント") casariam com anúncios sem relação."""
    if not usable(name):
        return False
    key = normalize(name)
    if is_cjk(key):
        return sum(is_cjk(ch) for ch in key) >= MIN_CJK_CHARACTER
    return len(key.split()) >= MIN_CHARACTER_WORDS


def _unique(values: list[str], exclude: str) -> list[str]:
    seen = {normalize(exclude)}
    result = []
    for value in values:
        key = normalize(value)
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def interleave_by_kind(rows: list[HypeRelease]) -> list[HypeRelease]:
    """Intercala os tipos: o 1º de cada tipo, depois o 2º de cada... Cada fonte tem sua
    escala de popularidade (AniList ~100 mil, TMDB e IGDB ~500), então ordenar tudo junto
    deixaria filmes e jogos sempre atrás dos animes. `rows` vem do mais popular."""
    by_kind: dict[str, list[HypeRelease]] = {}
    for row in rows:
        by_kind.setdefault(row.kind, []).append(row)
    result: list[HypeRelease] = []
    for rank in range(max((len(group) for group in by_kind.values()), default=0)):
        result.extend(group[rank] for group in by_kind.values() if rank < len(group))
    return result


def recent_releases(session: Session, day: date) -> list[HypeRelease]:
    """Lançamentos com estreia entre 60 dias atrás e 180 dias à frente (ou sem data),
    coletados nos últimos 7 dias, intercalando os tipos do mais popular para o menos."""
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
    return interleave_by_kind(list(rows))


def top_characters(characters_json: str) -> list[dict]:
    """Os 2 personagens mais favoritados entre os de nome distinto (`usable_character`)
    e ≥ 500 favoritos."""
    characters = sorted(
        json.loads(characters_json or "[]"), key=lambda c: -int(c.get("favourites") or 0)
    )
    return [
        c
        for c in characters
        if int(c.get("favourites") or 0) >= MIN_CHARACTER_FAVOURITES
        and usable_character(c.get("name"))
    ][:TOP_CHARACTERS]


def hype_entities(session: Session, day: date, limit: int = 25) -> list[dict]:
    """Entidades dos `limit` primeiros lançamentos de `recent_releases`."""
    rows = recent_releases(session, day)

    entities: list[dict] = []
    seen: set[str] = set()

    def add(name: str, category: str, aliases: list[str]) -> None:
        key = normalize(name)
        if not usable(name) or key in seen:
            return
        seen.add(key)
        entities.append(
            {"name": name, "category": category, "aliases": _unique([a for a in aliases if usable(a)], name)}
        )

    releases_used = 0
    for row in rows:
        if releases_used >= limit:
            break
        name = base_title(row.title, row.kind)
        if not usable(name) or normalize(name) in seen:
            continue
        releases_used += 1
        category = KIND_CATEGORY.get(row.kind, "outros")
        raw_aliases = json.loads(row.aliases_json or "[]")
        aliases = [base_title(a, row.kind) for a in raw_aliases] + raw_aliases
        if row.title != name:
            aliases.append(row.title)
        add(name, category, aliases)

        for character in top_characters(row.characters_json):
            native = character.get("native")
            add(character.get("name") or "", category, [native] if usable_character(native) else [])
    return entities
