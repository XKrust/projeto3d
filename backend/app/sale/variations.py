"""Variações que vendem (Etapa 3c): tipos fixos, prova nos anúncios do tema e checagem da IA."""

import json

from app.analyzer.validate import _flagged
from app.models import RawItem
from app.topics.normalize import matches_phrase, normalize

MAX_VARIATIONS = 5
MIN_ITEMS_FOR_EVIDENCE = 5

# slug → (rótulo, mercados, palavras que identificam o tipo num anúncio)
TYPES: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "presuportada": ("Versão pré-suportada", ("print",), ("presupported", "pre-supported", "pre supported")),
    "partes": ("Versão dividida em partes", ("print",), ("split", "multipart", "multi-part", "parts")),
    "busto": ("Busto", ("print", "digital"), ("bust", "busto")),
    "chibi": ("Versão chibi", ("print", "digital"), ("chibi",)),
    "pose": ("Pose alternativa", ("print", "digital"), ("pose", "alternate", "variant")),
    "base": ("Base temática", ("print",), ("base", "diorama")),
    "bundle": ("Kit ou bundle", ("print", "digital"), ("bundle", "pack", "collection")),
    "lowpoly": ("Versão low poly / game-ready", ("digital",), ("low poly", "lowpoly", "game ready", "game-ready")),
    "licenca": ("Licença comercial", ("print", "digital"), ("commercial", "merchant")),
}


def types_for(market: str) -> list[str]:
    return [slug for slug, (_, markets, _) in TYPES.items() if market in markets]


def _haystack(item: RawItem) -> str:
    return normalize(" ".join([item.title, *json.loads(item.tags_json or "[]")]))


SCOPES = {"tema": "do tema", "parecidos": "parecidos"}


def evidence(items: list[RawItem], market: str, scope: str = "tema") -> dict[str, dict]:
    """tipo → {count, total, scope}: quantos anúncios comparáveis citam o tipo (só com ≥ 5).
    `scope`: "tema" (anúncios do tema) ou "parecidos" (mesma categoria, tema fora do radar)."""
    if len(items) < MIN_ITEMS_FOR_EVIDENCE:
        return {}
    texts = [_haystack(item) for item in items]
    result = {}
    for slug in types_for(market):
        words = [normalize(w) for w in TYPES[slug][2]]
        count = sum(1 for text in texts if any(matches_phrase(text, w) for w in words))
        result[slug] = {"count": count, "total": len(items), "scope": scope}
    return result


def _proof(slug: str, proof: dict[str, dict]) -> str | None:
    data = proof.get(slug)
    if not data:
        return None
    return f"{data['count']} de {data['total']} anúncios {SCOPES[data.get('scope', 'tema')]} oferecem"


def validate_variations(raw: object, *, market: str, proof: dict[str, dict]) -> list[dict]:
    allowed = set(types_for(market))
    result: list[dict] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        slug = item.get("type")
        why = item.get("why").strip() if isinstance(item.get("why"), str) else ""
        if slug not in allowed or not why or any(v["type"] == slug for v in result):
            continue
        result.append({"type": slug, "label": TYPES[slug][0], "why": why, "evidence": _proof(slug, proof),
                       "flagged": _flagged(why), "source": "ia"})
    return result[:MAX_VARIATIONS]


def default_variations(*, market: str, proof: dict[str, dict]) -> list[dict]:
    """Sem IA: os tipos mais oferecidos nos anúncios do tema; sem dados, os primeiros do mercado."""
    offered = sorted((s for s in types_for(market) if proof.get(s, {}).get("count")),
                     key=lambda s: -proof[s]["count"])
    kind = "impressão 3D" if market == "print" else "assets digitais"
    chosen = offered[:3] or types_for(market)[:3]
    return [{"type": s, "label": TYPES[s][0],
             "why": _proof(s, proof) if s in offered else f"sugestão padrão para {kind}",
             "evidence": _proof(s, proof), "flagged": False, "source": "padrao"} for s in chosen]


def prompt_types(market: str) -> str:
    return ", ".join(f'"{slug}" ({TYPES[slug][0]})' for slug in types_for(market))
