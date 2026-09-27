"""Categoria heuristica de um topico, por contagem de palavras-chave (`category_keywords.yaml`)."""

from functools import lru_cache
from pathlib import Path

import yaml

from app.topics.normalize import matches_phrase, normalize

_SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "category_keywords.yaml"

DEFAULT_CATEGORY = "outros"


@lru_cache(maxsize=1)
def _keywords() -> dict[str, tuple[str, ...]]:
    with open(_SEED_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {category: tuple(normalize(word) for word in words) for category, words in data.items()}


def guess_category(texts: list[str]) -> str:
    """Categoria com mais palavras-chave batendo em `texts`; empate ou zero da "outros"."""
    haystack = normalize(" ".join(texts))
    counts = {
        category: sum(1 for word in words if matches_phrase(haystack, word))
        for category, words in _keywords().items()
    }
    if not counts:
        return DEFAULT_CATEGORY

    best = max(counts.values())
    if best == 0:
        return DEFAULT_CATEGORY

    winners = [category for category, count in counts.items() if count == best]
    return winners[0] if len(winners) == 1 else DEFAULT_CATEGORY
