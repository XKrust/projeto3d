"""Coletor MyMiniFactory: objetos populares e contagem de anuncios via API v2 (com chave).

Formato confirmado no OpenAPI oficial do MyMiniFactory
(`https://github.com/MyMiniFactory/api-documentation`, arquivo `myminifactory-api.yaml`), em
27/09/2026: `GET https://www.myminifactory.com/api/v2/search` com `q` (obrigatorio),
`per_page`, `sort` (`visits`, `date` ou `popularity`) e a chave em `key=` na query
(`ApiKeyAuth`). Resposta `{"total_count", "items": [Object]}`. O schema `Object` nao tem
campo de preco. Nao validado com chave real (ver `docs/coletores.md`).
"""

from app.collectors.base import CollectedItem, Collector
from app.constants import GLOBAL
from app.http import get_with_retry

SEARCH_URL = "https://www.myminifactory.com/api/v2/search"
PER_PAGE = 30


def _thumb_url(images: list) -> str | None:
    if not images:
        return None
    image = next((i for i in images if i.get("is_primary")), images[0])
    return (image.get("thumbnail") or {}).get("url")


def _to_item(obj: dict) -> CollectedItem:
    likes = int(obj.get("likes") or 0)
    views = int(obj.get("views") or 0)
    return CollectedItem(
        external_id=str(obj["id"]),
        title=obj.get("name", ""),
        country=GLOBAL,
        metric=likes + views / 100,
        tags=list(obj.get("tags") or []),
        url=obj.get("url"),
        thumb_url=_thumb_url(obj.get("images") or []),
        likes=likes,
        views=views,
    )


def parse_items(data: dict) -> list[CollectedItem]:
    return [_to_item(obj) for obj in data.get("items") or [] if "id" in obj]


class MyMiniFactoryCollector(Collector):
    """Objetos populares do MyMiniFactory e contagem de anuncios por termo."""

    name = "myminifactory"
    label = "MyMiniFactory"
    kind = "api"
    platform = "myminifactory"
    needs_key = ("myminifactory",)
    interval_minutes = 60

    def _search(self, query: str, per_page: int, sort: str | None = None) -> dict:
        params = {"q": query, "per_page": per_page, "key": self.settings["api_keys"]["myminifactory"]}
        if sort:
            params["sort"] = sort
        # A chave vai na URL, mas `get_with_retry` so poe o status nas mensagens de erro.
        return get_with_retry(self.http, "GET", SEARCH_URL, params=params).json()

    def collect(self) -> list[CollectedItem]:
        return parse_items(self._search("", PER_PAGE, sort="popularity"))

    def count_listings(self, query: str) -> int:
        return int(self._search(query, 1)["total_count"])
