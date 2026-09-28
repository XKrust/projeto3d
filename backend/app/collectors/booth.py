"""Coletor BOOTH (booth.pm): modelos 3D mais favoritados do Japao, por scraping de HTML.

A listagem `https://booth.pm/ja/browse/3Dモデル?sort=wish_list` (ordenada por favoritos)
traz cada produto num `li.item-card` com atributos `data-product-*`. A contagem de
favoritos nao vem no HTML: o proprio site busca em
`https://accounts.booth.pm/wish_lists.json?item_ids[]=...`. O robots.txt de booth.pm so
bloqueia `/terms` e o carrinho, e o de accounts.booth.pm tambem (confirmado em 27/09/2026,
ver `docs/coletores.md`).
"""

import logging
import re
from urllib.parse import quote

from selectolax.parser import HTMLParser

from app.collectors.base import CollectedItem, Collector, CollectorError
from app.collectors.polite import check_robots, polite_delay
from app.fx import convert, fetch_rates
from app.http import get_with_retry

logger = logging.getLogger(__name__)

BROWSE_URL = "https://booth.pm/ja/browse/3D%E3%83%A2%E3%83%87%E3%83%AB?sort=wish_list"
WISH_URL = "https://accounts.booth.pm/wish_lists.json"
SEARCH_URL = "https://booth.pm/ja/search/{q}"
ROBOTS_URL = "https://booth.pm/robots.txt"
ACCOUNTS_ROBOTS_URL = "https://accounts.booth.pm/robots.txt"
ITEM_URL = "https://booth.pm/ja/items/{id}"
COUNTRY = "JP"

_TOTAL_RE = re.compile(r"対象商品\s*([\d,]+)\s*件")


def parse_browse(html: str) -> list[dict]:
    """Cards da listagem: `{id, name, price_jpy, brand, thumb_url}`. Cards sem id ou
    sem nome sao descartados."""
    cards = []
    for node in HTMLParser(html).css("li.item-card"):
        attrs = node.attributes
        product_id = attrs.get("data-product-id")
        name = attrs.get("data-product-name")
        if not product_id or not name:
            continue
        price = attrs.get("data-product-price")
        thumb = node.css_first("a.js-thumbnail-image")
        cards.append(
            {
                "id": product_id,
                "name": name,
                "price_jpy": int(price) if price and price.isdigit() else None,
                "brand": attrs.get("data-product-brand"),
                "thumb_url": thumb.attributes.get("data-original") if thumb else None,
            }
        )
    return cards


def parse_wish_counts(data: dict) -> dict[str, int]:
    return {str(k): int(v) for k, v in (data.get("wishlists_counts") or {}).items()}


def parse_search_count(html: str) -> int:
    match = _TOTAL_RE.search(html)
    if match is None:
        raise CollectorError("Formato da página de busca do BOOTH mudou")
    return int(match.group(1).replace(",", ""))


def _yen_to_usd(price_jpy: int | None, rates: dict[str, float] | None) -> float | None:
    if not price_jpy or not rates:
        return None
    return round(convert(price_jpy, "JPY", "USD", rates), 2)


class BoothCollector(Collector):
    """Modelos 3D mais favoritados do BOOTH (Japao) e contagem de anuncios por termo."""

    name = "booth"
    label = "BOOTH"
    kind = "scrape"
    platform = "booth"
    needs_key = ()
    interval_minutes = 1440

    def _wish_counts(self, ids: list[str]) -> dict[str, int] | None:
        """Favoritos por id, ou `None` se a chamada falhar ou o robots.txt de
        accounts.booth.pm bloquear (os itens seguem sem eles, ranqueados pela posicao)."""
        try:
            check_robots(self.http, ACCOUNTS_ROBOTS_URL, WISH_URL)
            response = get_with_retry(
                self.http, "GET", WISH_URL, params=[("item_ids[]", i) for i in ids]
            )
            if response.status_code != 200:
                return None
            return parse_wish_counts(response.json())
        except Exception:  # favoritos sao opcionais: qualquer falha cai no ranking por posicao
            return None

    def collect(self) -> list[CollectedItem]:
        check_robots(self.http, ROBOTS_URL, BROWSE_URL)
        polite_delay()
        response = get_with_retry(self.http, "GET", BROWSE_URL)
        cards = parse_browse(response.text)
        if not cards:
            raise CollectorError("Formato da página do BOOTH mudou")

        polite_delay()
        wishes = self._wish_counts([c["id"] for c in cards])
        rates = self._rates()

        items = []
        for position, card in enumerate(cards):
            likes = wishes.get(card["id"]) if wishes is not None else None
            metric = likes if likes is not None else len(cards) - position
            items.append(
                CollectedItem(
                    external_id=card["id"],
                    title=card["name"],
                    country=COUNTRY,
                    metric=metric,
                    url=ITEM_URL.format(id=card["id"]),
                    thumb_url=card["thumb_url"],
                    likes=likes,
                    # preco do card em iene, convertido pelo cambio do BCE (sem cambio: None)
                    price_usd=_yen_to_usd(card["price_jpy"], rates),
                )
            )
        return items

    def _rates(self) -> dict[str, float] | None:
        """Câmbio do BCE para converter o iene; falhando, os itens ficam sem preço."""
        try:
            rates, _ = fetch_rates(self.http)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Câmbio do BCE falhou no BOOTH: %s", exc)
            return None
        return rates if "JPY" in rates else None

    def count_listings(self, query: str) -> int:
        url = SEARCH_URL.format(q=quote(query, safe=""))
        check_robots(self.http, ROBOTS_URL, url)
        polite_delay()
        response = get_with_retry(self.http, "GET", url)
        return parse_search_count(response.text)
