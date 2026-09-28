"""Coletor Sketchfab: modelos em alta e contagem de anuncios via busca publica.

A busca (`/v3/search`) e publica; um token, se configurado, so aumenta limites
de uso e vai no header `Authorization`. Confirmado por chamada real (26/09/2026):
a resposta da busca nunca traz preco (o campo `price` so existe nos schemas de
`ModelDetail`/`ModelList`, nao no de busca) nem um total explicito de resultados
(so `cursors`/`next`/`previous`/`results`) — ver `docs/coletores.md`.
"""

from app.collectors.base import CollectorError, CollectedItem, Collector
from app.constants import GLOBAL
from app.http import get_with_retry

SEARCH_URL = "https://api.sketchfab.com/v3/search"
TRENDING_PARAMS = {"type": "models", "sort_by": "-likeCount", "date": 7, "count": 24}
MAX_TRENDING_PAGES = 4
COUNT_LISTINGS_CAP = 200
MAX_THUMB_WIDTH = 640


def _headers(settings: dict) -> dict:
    token = settings.get("api_keys", {}).get("sketchfab")
    if token:
        return {"Authorization": f"Token {token}"}
    return {}


def _best_thumb_url(thumbnails: dict) -> str | None:
    """A maior imagem com largura ate `MAX_THUMB_WIDTH`px (ou a menor disponivel, se todas forem maiores)."""
    images = thumbnails.get("images") or []
    if not images:
        return None
    candidates = [img for img in images if img.get("width", 0) <= MAX_THUMB_WIDTH]
    pool = candidates or images
    return max(pool, key=lambda img: img.get("width", 0))["url"]


def _price_usd(model: dict) -> float | None:
    """Preco da store, se o modelo tiver (nunca observado na busca real; ver docs/coletores.md)."""
    price = model.get("price")
    if price is None:
        return None
    return float(price)


def _to_item(model: dict) -> CollectedItem:
    likes = int(model.get("likeCount", 0))
    views = int(model.get("viewCount", 0))

    return CollectedItem(
        external_id=model["uid"],
        title=model.get("name", ""),
        country=GLOBAL,
        metric=likes + views / 100,
        tags=[tag.get("name", "") for tag in model.get("tags", [])],
        url=model.get("viewerUrl"),
        thumb_url=_best_thumb_url(model.get("thumbnails") or {}),
        likes=likes,
        views=views,
        price_usd=_price_usd(model),
    )


class SketchfabCollector(Collector):
    """Modelos em alta do Sketchfab (busca publica; token opcional so para limites de uso)."""

    name = "sketchfab"
    label = "Sketchfab"
    kind = "api"
    platform = "sketchfab"
    needs_key = ()
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        headers = _headers(self.settings)
        items: list[CollectedItem] = []

        url: str | None = SEARCH_URL
        params: dict | None = dict(TRENDING_PARAMS)
        for _ in range(MAX_TRENDING_PAGES):
            response = get_with_retry(self.http, "GET", url, params=params, headers=headers)
            data = response.json()
            items.extend(_to_item(model) for model in data.get("results", []))

            url = data.get("next")
            params = None
            if not url:
                break

        return items

    def count_listings(self, query: str) -> int:
        headers = _headers(self.settings)
        total = 0

        url: str | None = SEARCH_URL
        params: dict | None = {"type": "models", "q": query, "count": 24}
        while url:
            response = get_with_retry(self.http, "GET", url, params=params, headers=headers)
            try:
                data = response.json()
            except ValueError as exc:  # página de bloqueio/desafio no lugar do JSON
                raise CollectorError(f"Sketchfab respondeu sem JSON ({response.status_code})") from exc

            if "count" in data:
                return int(data["count"])

            total += len(data.get("results", []))
            if total >= COUNT_LISTINGS_CAP:
                return COUNT_LISTINGS_CAP

            url = data.get("next")
            params = None

        return total
