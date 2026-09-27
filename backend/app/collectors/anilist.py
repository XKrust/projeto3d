"""Coletor AniList: animes que vão estrear ou estrearam há pouco, com personagens.

API GraphQL pública (`https://graphql.anilist.co`), sem chave. Séries antigas ainda "em
exibição" (ex.: ONE PIECE, desde 1999) não são hype: filtramos `startDate_greater` em
hoje − 90 dias. Formato confirmado por chamada real em 27/09/2026 (ver
docs/coletores.md).
"""

from datetime import date, timedelta

from app import clock
from app.collectors.base import CollectedItem, Collector, CollectorError, Release
from app.constants import GLOBAL
from app.http import get_with_retry

GRAPHQL_URL = "https://graphql.anilist.co"
PER_PAGE = 50
RECENT_START_DAYS = 90
TOP_CHARACTERS = 3

QUERY = """
query ($page: Int, $perPage: Int, $startAfter: FuzzyDateInt) {
  Page(page: $page, perPage: $perPage) {
    media(type: ANIME, status_in: [NOT_YET_RELEASED, RELEASING], startDate_greater: $startAfter, sort: POPULARITY_DESC, isAdult: false) {
      id
      title { romaji english native }
      siteUrl
      status
      format
      popularity
      startDate { year month day }
      coverImage { large }
      genres
      characters(sort: FAVOURITES_DESC, perPage: 3) {
        nodes { id name { full native } favourites image { medium } }
      }
    }
  }
}
"""


def _fuzzy_date_int(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def _start_date(start: dict | None) -> date | None:
    """Só devolve data quando ano, mês e dia existem (AniList às vezes só tem ano/mês)."""
    start = start or {}
    if not (start.get("year") and start.get("month") and start.get("day")):
        return None
    return date(start["year"], start["month"], start["day"])


def _titles(title: dict) -> tuple[str, list[str]]:
    """Título principal (inglês, senão romaji, senão nativo) e os demais como aliases."""
    candidates = [title.get("english"), title.get("romaji"), title.get("native")]
    present = [t for t in candidates if t]
    main = present[0] if present else ""
    aliases: list[str] = []
    for alias in present[1:]:
        if alias != main and alias not in aliases:
            aliases.append(alias)
    return main, aliases


def _characters(media: dict) -> list[dict]:
    nodes = ((media.get("characters") or {}).get("nodes") or [])[:TOP_CHARACTERS]
    return [
        {
            "name": (node.get("name") or {}).get("full") or "",
            "native": (node.get("name") or {}).get("native"),
            "favourites": int(node.get("favourites") or 0),
            "image_url": (node.get("image") or {}).get("medium"),
        }
        for node in nodes
        if (node.get("name") or {}).get("full")
    ]


def parse_media(data: dict) -> tuple[list[CollectedItem], list[Release]]:
    """`data` é a resposta JSON completa (com o envelope `data`)."""
    items: list[CollectedItem] = []
    releases: list[Release] = []
    for media in data["data"]["Page"]["media"]:
        title, aliases = _titles(media.get("title") or {})
        if not title:
            continue
        external_id = str(media["id"])
        popularity = float(media.get("popularity") or 0)
        image_url = (media.get("coverImage") or {}).get("large")
        releases.append(
            Release(
                external_id=external_id,
                kind="anime",
                title=title,
                release_date=_start_date(media.get("startDate")),
                popularity=popularity,
                country=GLOBAL,
                url=media.get("siteUrl"),
                image_url=image_url,
                aliases=aliases,
                characters=_characters(media),
            )
        )
        items.append(
            CollectedItem(
                external_id=external_id,
                title=title,
                country=GLOBAL,
                metric=popularity / 1000,
                tags=aliases,
                url=media.get("siteUrl"),
                thumb_url=image_url,
            )
        )
    return items, releases


class AniListCollector(Collector):
    """Estreias de anime (futuras e recentes) com os personagens mais favoritados."""

    name = "anilist"
    label = "AniList"
    kind = "api"
    needs_key = ()
    interval_minutes = 360

    def collect(self) -> list[CollectedItem]:
        start_after = _fuzzy_date_int(clock.today() - timedelta(days=RECENT_START_DAYS))
        response = get_with_retry(
            self.http,
            "POST",
            GRAPHQL_URL,
            json={
                "query": QUERY,
                "variables": {"page": 1, "perPage": PER_PAGE, "startAfter": start_after},
            },
            headers={"Accept": "application/json"},
        )
        data = response.json()
        errors = data.get("errors")
        if errors:
            raise CollectorError(f"Erro na API do AniList: {errors[0].get('message', 'desconhecido')}")
        items, self._releases = parse_media(data)
        return items

    def releases(self) -> list[Release]:
        return getattr(self, "_releases", [])
