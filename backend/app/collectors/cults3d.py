"""Coletor Cults3D: criacoes via GraphQL (chave obrigatoria).

**Chave real ainda nao disponivel nesta etapa.** As queries seguem o formato
documentado publicamente para a API GraphQL do Cults (`https://cults3d.com/graphql`,
basic auth com usuario/chave); a doc oficial (`https://cults3d.com/en/api`) fica
atras do Cloudflare e nao pode ser acessada por chamada automatizada, entao os
nomes de campo abaixo vem do gist publico do proprio criador da API e de notas
publicas de terceiros (ver `docs/coletores.md` para as fontes e os links). As
fixtures de teste foram montadas a mao nesse formato — **validar com chave real
e regravar as fixtures assim que houver uma disponivel.**
"""

from app.collectors.base import CollectedItem, Collector, CollectorError
from app.constants import GLOBAL
from app.http import get_with_retry

GRAPHQL_URL = "https://cults3d.com/graphql"
TRENDING_LIMIT = 100

TRENDING_QUERY = f"""
{{
  creationsBatch(sort: BY_LIKES, limit: {TRENDING_LIMIT}) {{
    results {{
      identifier
      name(locale: EN)
      shortUrl
      illustrationImageUrl
      likesCount
      downloadsCount
      tags(locale: EN)
      price(currency: USD) {{
        cents
      }}
    }}
  }}
}}
"""

COUNT_QUERY = """
query($query: String!) {
  creationsSearchBatch(query: $query, limit: 1) {
    total
  }
}
"""


def _price_usd(creation: dict) -> float | None:
    """Preco em USD a partir de `price.cents` (a API usa centavos); `None` se gratuito/ausente."""
    price = creation.get("price")
    if not price:
        return None
    cents = price.get("cents")
    if cents is None:
        return None
    return cents / 100


def _to_item(creation: dict) -> CollectedItem:
    likes = int(creation.get("likesCount", 0))
    downloads = int(creation.get("downloadsCount", 0))

    return CollectedItem(
        external_id=creation["identifier"],
        title=creation.get("name", ""),
        country=GLOBAL,
        metric=likes + 2 * downloads,
        tags=creation.get("tags") or [],
        url=creation.get("shortUrl"),
        thumb_url=creation.get("illustrationImageUrl"),
        likes=likes,
        downloads=downloads,
        price_usd=_price_usd(creation),
    )


class Cults3DCollector(Collector):
    """Criacoes em alta do Cults3D e contagem de anuncios, via GraphQL."""

    name = "cults3d"
    label = "Cults3D"
    kind = "api"
    platform = "cults3d"
    needs_key = ("cults3d_user", "cults3d_key")
    interval_minutes = 60

    def _query(self, query: str, variables: dict | None = None) -> dict:
        api_keys = self.settings["api_keys"]
        payload: dict = {"query": query}
        if variables is not None:
            payload["variables"] = variables

        response = get_with_retry(
            self.http,
            "POST",
            GRAPHQL_URL,
            json=payload,
            auth=(api_keys["cults3d_user"], api_keys["cults3d_key"]),
        )
        body = response.json()

        errors = body.get("errors")
        if errors:
            raise CollectorError(f"Erro na API do Cults3D: {errors[0]['message']}")

        return body["data"]

    def collect(self) -> list[CollectedItem]:
        data = self._query(TRENDING_QUERY)
        results = data["creationsBatch"]["results"]
        return [_to_item(creation) for creation in results]

    def count_listings(self, query: str) -> int:
        data = self._query(COUNT_QUERY, {"query": query})
        return int(data["creationsSearchBatch"]["total"])
