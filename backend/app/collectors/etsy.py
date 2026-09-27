"""Coletor Etsy: anuncios ativos de impressao 3D via Open API v3 (com chave).

Endpoint `findAllListingsActive` (`GET /v3/application/listings/active`). A autenticacao
e o header `x-api-key: <keystring>:<shared_secret>` — confirmado pela mensagem de erro real
da API ("incorrect shared secret for API key"), em 27/09/2026. As fixtures foram montadas a
mao a partir da doc oficial (`https://developers.etsy.com/documentation/reference/`), por
falta de chave real. Validar com chave real (ver `docs/coletores.md`).
"""

from app.collectors.base import CollectedItem, Collector
from app.constants import GLOBAL
from app.http import get_with_retry

ACTIVE_URL = "https://openapi.etsy.com/v3/application/listings/active"
KEYWORDS = ("3d printed", "3d print", "stl file")
LIMIT = 100


def _price_usd(listing: dict) -> float | None:
    """So devolve preco quando a moeda do anuncio e USD (sem conversao de cambio)."""
    price = listing.get("price") or {}
    if price.get("currency_code") != "USD" or not price.get("divisor"):
        return None
    return price["amount"] / price["divisor"]


def _to_item(listing: dict) -> CollectedItem:
    favorers = int(listing.get("num_favorers") or 0)
    views = listing.get("views")
    return CollectedItem(
        external_id=str(listing["listing_id"]),
        title=listing.get("title", ""),
        country=GLOBAL,
        metric=favorers + (views or 0) / 100,
        tags=list(listing.get("tags") or []),
        url=listing.get("url"),
        likes=favorers,
        views=int(views) if views is not None else None,
        price_usd=_price_usd(listing),
    )


def parse_listings(data: dict) -> list[CollectedItem]:
    return [_to_item(listing) for listing in data.get("results") or [] if "listing_id" in listing]


class EtsyCollector(Collector):
    """Anuncios ativos do Etsy para termos de impressao 3D, e contagem de anuncios."""

    name = "etsy"
    label = "Etsy"
    kind = "api"
    platform = "etsy"
    needs_key = ("etsy_keystring", "etsy_shared_secret")
    interval_minutes = 60

    def _get(self, keywords: str, limit: int) -> dict:
        keys = self.settings["api_keys"]
        response = get_with_retry(
            self.http,
            "GET",
            ACTIVE_URL,
            params={"keywords": keywords, "sort_on": "score", "limit": limit},
            headers={"x-api-key": f"{keys['etsy_keystring']}:{keys['etsy_shared_secret']}"},
        )
        return response.json()

    def collect(self) -> list[CollectedItem]:
        by_id: dict[str, CollectedItem] = {}
        for keyword in KEYWORDS:
            for item in parse_listings(self._get(keyword, LIMIT)):
                by_id.setdefault(item.external_id, item)
        return list(by_id.values())

    def count_listings(self, query: str) -> int:
        return int(self._get(f"{query} 3d", 1)["count"])
