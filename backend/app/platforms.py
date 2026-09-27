"""Cadastro/seed das plataformas de venda (tabela `Platform`), a partir de seed/platforms.yaml."""

import json
from pathlib import Path

import yaml
from sqlmodel import Session

from app.models import Platform

SEED_FILE = Path(__file__).resolve().parent / "seed" / "platforms.yaml"


def load_seed() -> list[dict]:
    with open(SEED_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def seed_platforms(session: Session) -> None:
    """Sincroniza o banco com o arquivo de seed.

    Insere as plataformas novas e atualiza as que o usuario nunca editou em /config
    (assim uma correcao no arquivo chega a quem ja tem o banco). Plataforma editada
    (`edited`) so recebe os campos que nao sao editaveis (`sells`, `categories`).
    """
    for entry in load_seed():
        platform = session.get(Platform, entry["slug"])
        if platform is None:
            platform = Platform(slug=entry["slug"], name=entry["name"], markets_json="[]", strength_json="{}")
        if not platform.edited:
            platform.name = entry["name"]
            platform.markets_json = json.dumps(entry["markets"])
            platform.fee_pct = entry.get("fee_pct")
            platform.strength_json = json.dumps(entry["strength"])
            platform.notes = entry.get("notes", "")
        platform.sells = bool(entry.get("sells", True))
        platform.categories_json = json.dumps(entry.get("categories", []))
        session.add(platform)
    session.commit()
