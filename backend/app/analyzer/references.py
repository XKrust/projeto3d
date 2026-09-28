"""Referências da análise: modelos de grandes artistas do mesmo tema no Sketchfab.

Busca pública (`/v3/search`, token opcional): primeiro os escolhidos pela equipe
(`staffpicked`) mais curtidos; faltando, completa com os mais curtidos em geral. Links que o
usuário colou entram primeiro. Máximo 3. Qualquer falha só tira aquela referência: a análise
nunca falha por causa delas. Uma tentativa por chamada, 8 s por chamada e 25 s no total (o
usuário está esperando a tela).
"""

import logging
import re
import time
from collections.abc import Callable

import httpx

from app.ai.provider import ImageInput

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.sketchfab.com/v3/search"
MODEL_URL = "https://api.sketchfab.com/v3/models/{uid}"
MAX_REFERENCES = 3
MAX_THUMB_WIDTH = 1024
NO_REFERENCES_NOTE = "Sem referências desta vez: comparado ao padrão profissional do tema."
# O usuário está esperando a tela: cada chamada espera no máximo 8 s, e as referências todas
# no máximo 25 s. Passou disso, a análise segue com o que já tiver.
CALL_TIMEOUT_SECONDS = 8.0
BUDGET_SECONDS = 25.0

_MODEL_LINK = re.compile(r"^https://(?:www\.)?sketchfab\.com/3d-models/[\w-]*?([0-9a-f]{32})/?(?:[?#].*)?$")


def parse_reference_url(url: str) -> str | None:
    """uid (32 hex) de um link de modelo do Sketchfab; qualquer outro link → None."""
    match = _MODEL_LINK.match((url or "").strip())
    return match.group(1) if match else None


def _thumb_url(model: dict) -> str | None:
    images = (model.get("thumbnails") or {}).get("images") or []
    if not images:
        return None
    pool = [img for img in images if img.get("width", 0) <= MAX_THUMB_WIDTH] or images
    return max(pool, key=lambda img: img.get("width", 0))["url"]


def _to_reference(model: dict, source: str) -> dict:
    user = model.get("user") or {}
    return {
        "name": model.get("name") or "",
        "artist": user.get("displayName") or user.get("username") or "",
        "url": model.get("viewerUrl") or f"https://sketchfab.com/3d-models/{model.get('uid')}",
        "thumb_url": _thumb_url(model),
        "likes": int(model.get("likeCount") or 0),
        "source": source,
        "_uid": model.get("uid"),
    }


def _get_json(http: httpx.Client, url: str, headers: dict, **params) -> dict | None:
    try:
        response = http.get(url, params=params or None, headers=headers, timeout=CALL_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001 — referência nunca derruba a análise
        logger.warning("Sketchfab falhou em %s: %s", url, exc)
        return None


def _download(http: httpx.Client, url: str | None) -> ImageInput | None:
    if not url:
        return None
    try:
        response = http.get(url, timeout=CALL_TIMEOUT_SECONDS)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Miniatura não baixou (%s): %s", url, exc)
        return None
    mime = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    return {"data": response.content, "mime_type": mime if mime.startswith("image/") else "image/jpeg"}


def find_references(
    http: httpx.Client,
    query: str,
    user_urls: list[str],
    token: str = "",
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[list[dict], list[ImageInput], str | None]:
    """(referências, miniaturas na mesma ordem, nota ou None)."""
    headers = {"Authorization": f"Token {token}"} if token else {}
    deadline = monotonic() + BUDGET_SECONDS

    def time_left() -> bool:
        return monotonic() < deadline

    candidates: list[dict] = []
    for url in user_urls:
        uid = parse_reference_url(url)
        model = _get_json(http, MODEL_URL.format(uid=uid), headers) if uid and time_left() else None
        if model:
            candidates.append(_to_reference(model, "usuario"))
    for extra in ({"staffpicked": "true"}, {}):
        if len(candidates) >= MAX_REFERENCES or not time_left():
            break
        data = _get_json(http, SEARCH_URL, headers, type="models", q=query, sort_by="-likeCount",
                         count=MAX_REFERENCES, **extra)
        for model in (data or {}).get("results", []):
            candidates.append(_to_reference(model, "auto"))

    references, images, seen = [], [], set()
    for ref in candidates:
        uid = ref.pop("_uid")
        if uid in seen or len(references) >= MAX_REFERENCES or not time_left():
            continue
        seen.add(uid)
        image = _download(http, ref["thumb_url"])
        if image is not None:
            references.append(ref)
            images.append(image)
    return references, images, (None if references else NO_REFERENCES_NOTE)
