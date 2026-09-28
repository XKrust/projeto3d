"""Coletor Google Trends RSS: buscas em alta por pais, sem necessidade de chave."""

import logging

from defusedxml import ElementTree as ET

from app.collectors.base import CollectedItem, Collector
from app.http import get_with_retry

logger = logging.getLogger(__name__)

FEED_URL = "https://trends.google.com/trending/rss?geo={country}"
NS = {"ht": "https://trends.google.com/trending/rss"}
MAX_NEWS_TAGS = 3


def parse_traffic(s: str) -> int:
    """Converte o texto de `ht:approx_traffic` (ex.: "200K+", "2M+", "1,000+") em int.

    String vazia (ou nao numerica) vira 0.
    """
    if not s:
        return 0

    text = s.strip().rstrip("+").replace(",", "")
    if not text:
        return 0

    multiplier = 1
    suffix = text[-1].upper()
    if suffix == "K":
        multiplier = 1_000
        text = text[:-1]
    elif suffix == "M":
        multiplier = 1_000_000
        text = text[:-1]

    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0


def _external_id(title: str) -> str:
    """Identificador estavel do topico a partir do titulo (normalizacao definitiva na Tarefa 10)."""
    return title.strip().lower()


def parse_feed(xml: str, country: str) -> list[CollectedItem]:
    """Converte o RSS de `https://trends.google.com/trending/rss?geo=<pais>` em itens."""
    root = ET.fromstring(xml)

    items: list[CollectedItem] = []
    for item in root.iter("item"):
        title_el = item.find("title")
        title = title_el.text if title_el is not None and title_el.text else ""

        traffic_el = item.find("ht:approx_traffic", NS)
        traffic_text = traffic_el.text if traffic_el is not None else ""

        picture_el = item.find("ht:picture", NS)
        thumb_url = picture_el.text if picture_el is not None else None

        tags = []
        for news_item in item.findall("ht:news_item", NS)[:MAX_NEWS_TAGS]:
            news_title_el = news_item.find("ht:news_item_title", NS)
            if news_title_el is not None and news_title_el.text:
                tags.append(news_title_el.text)

        items.append(
            CollectedItem(
                external_id=_external_id(title),
                title=title,
                country=country,
                metric=float(parse_traffic(traffic_text)),
                tags=tags,
                thumb_url=thumb_url,
            )
        )
    return items


class GoogleTrendsCollector(Collector):
    """Buscas em alta do Google Trends, por pais (feed RSS publico, sem chave)."""

    name = "google_trends"
    label = "Google Trends"
    kind = "rss"
    needs_key = ()
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        """Um feed por país. Falha num país só pula aquele país; falhando todos, a
        coleta falha (e aparece como erro em /config)."""
        items: list[CollectedItem] = []
        errors: list[Exception] = []
        countries = self.settings["countries"]
        for country in countries:
            try:
                response = get_with_retry(self.http, "GET", FEED_URL.format(country=country))
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001 — um país não derruba os outros
                logger.warning("Google Trends falhou para %s: %s", country, exc)
                errors.append(exc)
                continue
            items.extend(parse_feed(response.text, country))
        if countries and len(errors) == len(countries):
            raise errors[0]
        return items
