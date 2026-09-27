"""Scraping educado, compartilhado pelos coletores de `kind="scrape"`.

Regra do projeto: respeitar o robots.txt da fonte e esperar 3 a 5 segundos entre
requisicoes (ver `docs/coletores.md`).
"""

import random
import time

import httpx

from app.collectors.base import CollectorError
from app.collectors.robots import is_allowed
from app.http import USER_AGENT, get_with_retry

DELAY_RANGE_SECONDS = (3.0, 5.0)


def polite_delay() -> None:
    """Espera de 3 a 5s (aleatorio) entre requisicoes a uma mesma fonte."""
    time.sleep(random.uniform(*DELAY_RANGE_SECONDS))


def check_robots(http: httpx.Client, robots_url: str, url: str) -> None:
    """Lanca `CollectorError` se o robots.txt de `robots_url` bloquear `url`.
    Um robots.txt ausente (404) conta como "sem regras"."""
    response = get_with_retry(http, "GET", robots_url)
    robots_txt = "" if response.status_code == 404 else response.text
    if not is_allowed(robots_txt, url, USER_AGENT):
        raise CollectorError(f"Bloqueado pelo robots.txt: {url}")
