"""Checagem do anúncio devolvido pela IA (spec 3b §7) — funções puras."""

import re

from app.analyzer.validate import _flagged  # mesma lista de bajulação da análise (3a)
from app.sale.limits import limits_for
from app.topics.normalize import is_cjk, normalize

_IMAGE_REF = re.compile(
    r"\s*\(?\b(?:na|da|nas|das|em|in|on)?\s*(?:image(?:m|ns)|images?)\s+\d+(?:\s*(?:e|and|,)\s*\d+)*\)?",
    re.IGNORECASE,
)


def clean_strength(text: str) -> str:
    """Tira "na imagem 1" dos pontos fortes: é referência interna da análise, não pode
    aparecer num anúncio público."""
    return " ".join(_IMAGE_REF.sub("", text).split()).strip(" ,.;")


FAN_ART = {"en": "fan art", "pt": "fan art", "ja": "ファンアート"}
_FAN_ART_SPELLINGS = ("fan art", "fanart", "fan-art", "ファンアート")


def trim_words(text: str, limit: int) -> tuple[str, bool]:
    """Corta `text` em até `limit` caracteres, na última palavra inteira. Texto sem espaço
    (ou em japonês) é cortado no limite. Devolve (texto, se cortou)."""
    text = text.strip()
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    if not is_cjk(cut) and text[limit] != " " and " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.strip(), True


def _with_fan_art(title: str, lang: str, limit: int) -> tuple[str, bool]:
    if any(spelling in normalize(title) for spelling in _FAN_ART_SPELLINGS):
        return title, False
    suffix = f" ({FAN_ART.get(lang, FAN_ART['en'])})"
    base, trimmed = trim_words(title, limit - len(suffix))
    return base + suffix, trimmed


def _tags(raw: object, platform: str) -> tuple[list[str], bool]:
    limits = limits_for(platform)
    tags: list[str] = []
    trimmed = False
    for value in raw if isinstance(raw, list) else []:
        if not isinstance(value, str):
            continue
        tag = " ".join(value.replace("#", " ").lower().split())
        if limits["tag_chars"] is not None:
            tag = " ".join(limits["tag_chars"].sub("", tag).split())
        tag, cut = trim_words(tag, limits["tag"])
        trimmed = trimmed or cut
        if tag and tag not in tags:
            tags.append(tag)
    if len(tags) > limits["tags"]:
        tags, trimmed = tags[: limits["tags"]], True
    return tags, trimmed


def validate_listings(raw: dict, requested: set[tuple[str, str]], *, authorship: str) -> list[dict]:
    """Só pares loja+idioma pedidos (o primeiro de cada), título obrigatório, limites da loja,
    "fan art" no título de fan-art e aviso de bajulação na descrição."""
    result: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in raw.get("listings", []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        pair = (item.get("platform"), item.get("lang"))
        title = item.get("title").strip() if isinstance(item.get("title"), str) else ""
        if pair not in requested or pair in seen or not title:
            continue
        seen.add(pair)
        platform, lang = pair
        limit = limits_for(platform)["title"]
        if authorship == "fanart":
            title, title_cut = _with_fan_art(title, lang, limit)
        else:
            title, title_cut = trim_words(title, limit)
        tags, tags_cut = _tags(item.get("tags"), platform)
        description = item.get("description").strip() if isinstance(item.get("description"), str) else ""
        description = " ".join(_IMAGE_REF.sub("", description).split())
        result.append({
            "platform": platform, "lang": lang, "title": title, "tags": tags, "description": description,
            "trimmed": title_cut or tags_cut, "flagged": _flagged(title, description),
        })
    return result
