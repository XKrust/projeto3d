"""Risco de fan-art por loja (Etapa 3c), a partir de `seed/fanart_policies.yaml`.

Só entra nível confirmado na página oficial da loja (URL no arquivo). Leitura do app,
não é conselho jurídico.
"""

from functools import lru_cache
from pathlib import Path

import yaml

SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "fanart_policies.yaml"
UNKNOWN = "Política de fan-art não confirmada pelo app: confira a política da loja antes de publicar."
INSPIRED_TIP = ("Considere uma versão inspirada, autoral (sem nome, logo ou traços exclusivos do "
                "personagem) para as lojas de risco alto.")
LEVEL_LABELS = {"alto": "risco alto", "medio": "risco médio"}


@lru_cache(maxsize=1)
def _policies() -> dict[str, dict]:
    with open(SEED_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fanart_for_store(platform: str) -> dict:
    policy = _policies().get(platform)
    if not policy:
        return {"level": None, "label": "risco não confirmado", "summary": UNKNOWN, "url": None}
    return {"level": policy["level"], "label": LEVEL_LABELS[policy["level"]], "summary": policy["summary"],
            "url": policy["url"]}


def inspired_tip(stores: list[dict]) -> str | None:
    return INSPIRED_TIP if any((s.get("fanart") or {}).get("level") == "alto" for s in stores) else None
