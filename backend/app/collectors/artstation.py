"""Coletor ArtStation: artworks em alta e contagem de anuncios do marketplace.

Usa o JSON que o proprio site consome (nao ha API publica documentada), por isso
`kind="scrape"`, com robots.txt e espera educada. Confirmado por chamada real em
27/09/2026 (ver `docs/coletores.md`):
- `projects.json?sorting=trending&page=N` devolve 50 artworks por pagina;
- `api/v2/marketplace/products.json` exige `visibility`, `page` e `per_page >= 5`, e traz
  `total_count`. O parametro `sorting` do marketplace e ignorado, por isso as tendencias vem
  dos artworks, e o marketplace so e usado para contar anuncios.
"""

from app.collectors.base import CollectedItem, Collector, CollectorError
from app.collectors.polite import check_robots, polite_delay
from app.constants import GLOBAL
from app.http import get_with_retry

PROJECTS_URL = "https://www.artstation.com/projects.json"
MARKETPLACE_URL = "https://www.artstation.com/api/v2/marketplace/products.json"
ROBOTS_URL = "https://www.artstation.com/robots.txt"
TRENDING_PAGES = (1, 2)


def _to_item(project: dict) -> CollectedItem | None:
    if "id" not in project or not project.get("title"):
        return None
    if project.get("adult_content") or project.get("hide_as_adult"):
        return None
    likes = int(project.get("likes_count") or 0)
    views = int(project.get("views_count") or 0)
    return CollectedItem(
        external_id=str(project["id"]),
        title=project["title"],
        country=GLOBAL,
        metric=likes + views / 100,
        tags=list(project.get("tag_list") or []),
        url=project.get("permalink"),
        thumb_url=(project.get("cover") or {}).get("thumb_url"),
        likes=likes,
        views=views,
    )


def parse_trending(data: dict) -> list[CollectedItem]:
    """`data` e a resposta de `projects.json`. Artworks adultos ou incompletos sao descartados."""
    return [item for item in map(_to_item, data.get("data") or []) if item is not None]


def parse_count(data: dict) -> int:
    return int(data["total_count"])


class ArtStationCollector(Collector):
    """Artworks em alta do ArtStation e contagem de anuncios do marketplace."""

    name = "artstation"
    label = "ArtStation"
    kind = "scrape"
    platform = "artstation"
    needs_key = ()
    interval_minutes = 1440

    def collect(self) -> list[CollectedItem]:
        check_robots(self.http, ROBOTS_URL, PROJECTS_URL)
        items: list[CollectedItem] = []
        for page in TRENDING_PAGES:
            polite_delay()
            response = get_with_retry(
                self.http, "GET", PROJECTS_URL, params={"sorting": "trending", "page": page}
            )
            items.extend(parse_trending(response.json()))
        if not items:
            raise CollectorError("Formato da página do ArtStation mudou")
        return items

    def count_listings(self, query: str) -> int:
        check_robots(self.http, ROBOTS_URL, MARKETPLACE_URL)
        polite_delay()
        response = get_with_retry(
            self.http,
            "GET",
            MARKETPLACE_URL,
            params={"visibility": "profile", "page": 1, "per_page": 5, "q": query},
        )
        return parse_count(response.json())
