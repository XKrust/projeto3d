"""Coletor Thingiverse: modelos populares como sinal de demanda (com App Token).

O Thingiverse nao vende modelos, entao nao e uma plataforma de venda (`platform=None`,
sem `count_listings`): os itens so entram no grupo "platforms" da demanda (ver
`PLATFORM_SOURCES` em `app/topics/extract.py`).

Formato confirmado no OpenAPI oficial (`https://www.thingiverse.com/swagger/docs/openapi.yaml`,
`resources/search.yaml#/ByTermThings` e `schemas/thing_schema.yaml`), em 27/09/2026:
`GET /search/{term}/?type=things&sort=popular` com `Authorization: Bearer <token>` devolve
`{"total", "hits": [thing]}`. Nao validado com token real (ver `docs/coletores.md`).
"""

from app.collectors.base import CollectedItem, Collector
from app.constants import GLOBAL
from app.http import get_with_retry

SEARCH_URL = "https://api.thingiverse.com/search/"
PER_PAGE = 30


def _tag_names(tags: list) -> list[str]:
    return [t["name"] if isinstance(t, dict) else str(t) for t in tags or [] if t]


def _to_item(thing: dict) -> CollectedItem:
    likes = int(thing.get("like_count") or 0)
    collects = int(thing.get("collect_count") or 0)
    return CollectedItem(
        external_id=str(thing["id"]),
        title=thing.get("name", ""),
        country=GLOBAL,
        metric=likes + 2 * collects,
        tags=_tag_names(thing.get("tags")),
        url=thing.get("public_url"),
        thumb_url=thing.get("thumbnail"),
        likes=likes,
        downloads=collects,
    )


def parse_hits(data: dict) -> list[CollectedItem]:
    """Things da busca, sem os marcados como NSFW."""
    return [
        _to_item(thing)
        for thing in data.get("hits") or []
        if "id" in thing and not thing.get("is_nsfw")
    ]


class ThingiverseCollector(Collector):
    """Modelos populares do Thingiverse (sinal de demanda, nao loja)."""

    name = "thingiverse"
    label = "Thingiverse"
    kind = "api"
    platform = None
    needs_key = ("thingiverse",)
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        token = self.settings["api_keys"]["thingiverse"]
        response = get_with_retry(
            self.http,
            "GET",
            SEARCH_URL,
            params={"type": "things", "sort": "popular", "per_page": PER_PAGE},
            headers={"Authorization": f"Bearer {token}"},
        )
        return parse_hits(response.json())
