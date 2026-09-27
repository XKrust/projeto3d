"""Coletor CGTrader: modelos mais vendidos e contagem de anuncios via API oficial (com chave).

O site bloqueia acesso automatizado (resposta 202 vazia, desafio anti-robo) e o robots.txt
proibe `/search*` e `*/api/internal/*`, entao nada de scraping: usamos a API oficial
`https://api.cgtrader.com` (doc: `https://api.cgtrader.com/docs`, consultada em 27/09/2026).
`GET /v1/models` aceita `keywords`, `page`, `per_page` e `sort` (`best_match`, `sales`,
`newest`...) e devolve `{"total", "models": [...]}`. A autenticacao e Doorkeeper (a resposta
sem token traz `WWW-Authenticate: Bearer realm="Doorkeeper"`), com a chave gerada na conta do
usuario. Nao validado com chave real (ver `docs/coletores.md`).
"""

from app.collectors.base import CollectedItem, Collector
from app.constants import GLOBAL
from app.http import get_with_retry

MODELS_URL = "https://api.cgtrader.com/v1/models"
PER_PAGE = 50


def _to_item(model: dict, metric: int) -> CollectedItem:
    thumbnails = model.get("thumbnails") or []
    price = (model.get("prices") or {}).get("download")
    return CollectedItem(
        external_id=str(model["id"]),
        title=model.get("title", ""),
        country=GLOBAL,
        # A API nao traz curtidas nem vendas: a lista vem ordenada por vendas, e a metrica
        # e a posicao invertida (o primeiro de N vale N).
        metric=metric,
        tags=list(model.get("tags") or []),
        url=model.get("url"),
        thumb_url=thumbnails[0] if thumbnails else None,
        price_usd=float(price) if price is not None else None,
    )


def parse_models(data: dict) -> list[CollectedItem]:
    models = [m for m in data.get("models") or [] if "id" in m]
    return [_to_item(model, len(models) - position) for position, model in enumerate(models)]


class CGTraderCollector(Collector):
    """Modelos mais vendidos do CGTrader e contagem de anuncios por termo."""

    name = "cgtrader"
    label = "CGTrader"
    kind = "api"
    platform = "cgtrader"
    needs_key = ("cgtrader",)
    interval_minutes = 60

    def _get(self, params: dict) -> dict:
        token = self.settings["api_keys"]["cgtrader"]
        response = get_with_retry(
            self.http, "GET", MODELS_URL, params=params, headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()

    def collect(self) -> list[CollectedItem]:
        return parse_models(self._get({"sort": "sales", "per_page": PER_PAGE, "page": 1}))

    def count_listings(self, query: str) -> int:
        return int(self._get({"keywords": query, "per_page": 1})["total"])
