"""Nota da capa (Etapa 3c): a imagem 1 da análise contra as capas dos anúncios mais curtidos.

A IA marca cada item do checklist (ok / não / não dá para ver) e diz como corrigir; a nota é
calculada pelo app (10 × itens ok / itens avaliados).
"""

import json

import httpx

from app.ai.provider import ImageInput, TextProvider
from app.analyzer.errors import ask_json
from app.analyzer.references import download_image
from app.analyzer.store import image_path
from app.analyzer.validate import _flagged
from app.models import Analysis, RawItem

MAX_REFERENCES = 3
MAX_COMPARISONS = 3

CHECKS: dict[str, str] = {
    "fundo": "Fundo limpo, sem distrair",
    "angulo": "Ângulo que mostra volume (3/4)",
    "luz": "Luz que mostra a forma",
    "enquadramento": "Modelo ocupa a imagem",
    "miniatura": "Dá para entender em miniatura",
    "escala": "Referência de tamanho",
}
_MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def cover_image(analysis: Analysis) -> ImageInput | None:
    """A primeira imagem salva da análise (a capa)."""
    name = next((n for n in json.loads(analysis.files_json or "[]") if n.startswith("image-")), None)
    path = image_path(analysis.id, name) if name else None
    if path is None:
        return None
    return {"data": path.read_bytes(), "mime_type": _MIME.get(path.suffix.lstrip("."), "image/jpeg")}


def top_covers(http: httpx.Client, items: list[RawItem]) -> tuple[list[dict], list[ImageInput]]:
    """Até 3 capas dos anúncios comparáveis mais curtidos que baixarem."""
    refs: list[dict] = []
    images: list[ImageInput] = []
    for item in sorted((i for i in items if i.thumb_url), key=lambda i: i.likes or 0, reverse=True):
        image = download_image(http, item.thumb_url)
        if image is None:
            continue
        refs.append({"title": item.title, "url": item.url, "thumb_url": item.thumb_url, "likes": item.likes})
        images.append(image)
        if len(refs) == MAX_REFERENCES:
            break
    return refs, images


def build_prompt(*, market: str, n_refs: int) -> str:
    checks = "\n".join(f'- "{slug}": {label}' for slug, label in CHECKS.items()
                       if slug != "escala" or market == "print")
    refs = (f"As {n_refs} imagens seguintes são capas dos anúncios mais curtidos do mesmo tema "
            f"(referência 1 a {n_refs})." if n_refs else "Não há capas de referência desta vez.")
    return f"""Você revisa a CAPA (imagem principal) de um anúncio de modelo 3D. A primeira imagem é a
capa do usuário. {refs}

Para cada item do checklist, diga se a capa do usuário cumpre (ok true/false) ou null se não
dá para ver. Sempre explique onde (why). Se ok for false, diga como corrigir (fix), em uma
frase prática. Tom profissional, sem elogio genérico nem exagero.
{checks}

Depois, até 3 coisas concretas que as capas de referência fazem e a do usuário não, citando a
referência pelo número.

Responda só com JSON:
{{"checks": {{"fundo": {{"ok": true, "why": "...", "fix": ""}}}},
  "vs_top": [{{"reference": 1, "text": "..."}}]}}"""


def validate_cover(raw: dict, *, market: str, n_refs: int) -> dict:
    checks: dict[str, dict] = {}
    raw_checks = raw.get("checks") if isinstance(raw.get("checks"), dict) else {}
    for slug, label in CHECKS.items():
        item = raw_checks.get(slug) if isinstance(raw_checks.get(slug), dict) else {}
        ok = item.get("ok") if isinstance(item.get("ok"), bool) else None
        why = item.get("why").strip() if isinstance(item.get("why"), str) else ""
        fix = item.get("fix").strip() if isinstance(item.get("fix"), str) else ""
        if slug == "escala" and market != "print":
            ok, why, fix = None, "não se aplica a assets digitais", ""
        if ok is False and not fix:
            ok = None
        checks[slug] = {"label": label, "ok": ok, "why": why, "fix": fix if ok is False else "",
                        "flagged": _flagged(why, fix)}
    answered = [c for c in checks.values() if c["ok"] is not None]
    score = round(10 * sum(c["ok"] for c in answered) / len(answered), 1) if answered else None
    vs_top = []
    for item in raw.get("vs_top", []) if isinstance(raw.get("vs_top"), list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
            continue
        if not isinstance(item.get("reference"), int) or not 1 <= item["reference"] <= n_refs:
            continue
        vs_top.append({"reference": item["reference"], "text": item["text"].strip(), "flagged": _flagged(item["text"])})
    return {"score": score, "checks": checks, "vs_top": vs_top[:MAX_COMPARISONS]}


def evaluate_cover(provider: TextProvider, cover: ImageInput, refs: list[dict], ref_images: list[ImageInput],
                   *, market: str) -> dict:
    raw = ask_json(provider, build_prompt(market=market, n_refs=len(refs)), [cover, *ref_images], required="checks")
    return {**validate_cover(raw, market=market, n_refs=len(refs)), "references": refs}
