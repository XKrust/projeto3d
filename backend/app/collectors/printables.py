"""Coletor Printables: modelos em alta e contagem de anuncios via GraphQL nao oficial.

O site (`www.printables.com`) fica atras de um desafio Cloudflare que bloqueia acesso
automatizado — confirmado por chamada HTTP simples e por Chromium headless via Playwright,
sem nenhuma tecnica de evasao de bot-detection (ver `docs/coletores.md`). O endpoint GraphQL
usado pelo proprio frontend do site (`https://api.printables.com/graphql/`), porem, responde
normalmente, sem desafio (confirmado por chamada real, 26/09/2026). A introspeccao do schema
esta desabilitada nesse endpoint; o formato das queries abaixo vem de projetos publicos que
documentam essa API nao oficial (ver `docs/coletores.md` para as fontes) e foi confirmado
batendo as queries contra o endpoint real. `robots.txt` desse host (`api.printables.com`)
devolve 404 — sem regras, `is_allowed` libera tudo.
"""

from app.collectors.base import CollectedItem, Collector, CollectorError
from app.collectors.polite import check_robots, polite_delay
from app.constants import GLOBAL
from app.http import get_with_retry

GRAPHQL_URL = "https://api.printables.com/graphql/"
ROBOTS_URL = "https://api.printables.com/robots.txt"
MEDIA_BASE_URL = "https://media.printables.com/"
MODEL_URL_TEMPLATE = "https://www.printables.com/model/{id}-{slug}"

# `searchPrints2` e a query de busca do proprio frontend do Printables. Sem termo de busca
# (`query=""`) e ordenada por `popular`, funciona como a listagem de "modelos em alta" — nao
# ha uma query dedicada de "trending" separada confirmada. `totalCount` da o total exato de
# resultados de uma busca, sem precisar paginar (ao contrario do Sketchfab).
SEARCH_QUERY = """
query SearchModels($query: String!, $limit: Int, $ordering: SearchChoicesEnum) {
  result: searchPrints2(query: $query, printType: print, limit: $limit, ordering: $ordering) {
    items {
      id
      name
      slug
      likesCount
      downloadCount
      price
      image { filePath }
    }
    totalCount
  }
}
"""

TRENDING_ORDERING = "popular"
TRENDING_LIMIT = 24
SEARCH_ORDERING = "best_match"
SEARCH_LIMIT = 1


def _thumb_url(item: dict) -> str | None:
    path = (item.get("image") or {}).get("filePath")
    return MEDIA_BASE_URL + path if path else None


def _model_url(item: dict) -> str:
    return MODEL_URL_TEMPLATE.format(id=item["id"], slug=item.get("slug", ""))


def _price_usd(item: dict) -> float | None:
    """Preco do modelo, se houver (nunca observado em chamadas reais — todos os modelos
    vistos, inclusive buscas por termos tipicos de modelos pagos, tinham `price: null`; o
    campo e lido defensivamente, e a unidade/moeda fica sem confirmacao)."""
    price = item.get("price")
    return float(price) if price is not None else None


def _to_item(item: dict) -> CollectedItem:
    likes = int(item.get("likesCount", 0))
    downloads = int(item.get("downloadCount", 0))

    return CollectedItem(
        external_id=str(item["id"]),
        title=item.get("name", ""),
        country=GLOBAL,
        metric=likes + 2 * downloads,
        url=_model_url(item),
        thumb_url=_thumb_url(item),
        likes=likes,
        downloads=downloads,
        price_usd=_price_usd(item),
    )


def parse_trending(data: dict) -> list[CollectedItem]:
    """`data` e a resposta JSON completa (com o envelope `data`) de `SEARCH_QUERY`."""
    items = data["data"]["result"]["items"]
    return [_to_item(item) for item in items]


def parse_count(data: dict) -> int:
    """`data` e a resposta JSON completa (com o envelope `data`) de `SEARCH_QUERY`."""
    return int(data["data"]["result"]["totalCount"])


class PrintablesCollector(Collector):
    """Modelos em alta do Printables e contagem de anuncios, via GraphQL nao oficial."""

    name = "printables"
    label = "Printables"
    kind = "scrape"
    platform = "printables"
    needs_key = ()
    interval_minutes = 1440

    def _query(self, variables: dict) -> dict:
        response = get_with_retry(
            self.http,
            "POST",
            GRAPHQL_URL,
            json={"operationName": "SearchModels", "query": SEARCH_QUERY, "variables": variables},
        )
        data = response.json()

        errors = data.get("errors")
        if errors:
            raise CollectorError(f"Erro na API do Printables: {errors[0]['message']}")

        return data

    def collect(self) -> list[CollectedItem]:
        check_robots(self.http, ROBOTS_URL, GRAPHQL_URL)
        polite_delay()

        data = self._query({"query": "", "limit": TRENDING_LIMIT, "ordering": TRENDING_ORDERING})
        return parse_trending(data)

    def count_listings(self, query: str) -> int:
        check_robots(self.http, ROBOTS_URL, GRAPHQL_URL)
        polite_delay()

        data = self._query({"query": query, "limit": SEARCH_LIMIT, "ordering": SEARCH_ORDERING})
        return parse_count(data)
