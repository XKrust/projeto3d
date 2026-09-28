"""Limites de anúncio por loja (spec 3b §7).

Um limite só entra aqui depois de confirmado na página oficial da loja, com a URL e a data
da consulta no comentário (mesma regra de `fee_pct` em docs/plataformas.md). Loja sem
entrada usa `DEFAULT`, que é o limite do próprio app.
"""

import re
from typing import TypedDict


class Limits(TypedDict):
    title: int  # caracteres
    tags: int  # quantidade
    tag: int  # caracteres por tag
    tag_chars: re.Pattern | None  # caracteres proibidos numa tag (None = qualquer um)


DEFAULT: Limits = {"title": 100, "tags": 15, "tag": 30, "tag_chars": None}

LIMITS: dict[str, Limits] = {
    # https://help.etsy.com/hc/en-us/articles/115015628707-How-to-Create-a-Listing (28/09/2026):
    # título até 140 caracteres; até 13 tags de até 20 caracteres; tag só com letras,
    # números, espaço, ' e -.
    "etsy": {"title": 140, "tags": 13, "tag": 20, "tag_chars": re.compile(r"[^\w '\-]|_")},
}


def limits_for(platform: str) -> Limits:
    return LIMITS.get(platform, DEFAULT)
