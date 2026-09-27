"""Cadastro/seed das plataformas de venda (tabela `Platform`)."""

import json
from pathlib import Path

import yaml
from sqlmodel import Session

from app.models import Platform

SEED_FILE = Path(__file__).resolve().parent / "seed" / "platforms.yaml"


def seed_platforms(session: Session) -> None:
    """Insere as plataformas do arquivo de seed que ainda nao existem no banco.

    Nunca sobrescreve uma plataforma ja cadastrada (idempotente, preserva edicoes).
    """
    with open(SEED_FILE, encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []

    for entry in entries:
        if session.get(Platform, entry["slug"]) is not None:
            continue
        session.add(
            Platform(
                slug=entry["slug"],
                name=entry["name"],
                markets_json=json.dumps(entry["markets"]),
                fee_pct=entry.get("fee_pct"),
                strength_json=json.dumps(entry["strength"]),
                notes=entry.get("notes", ""),
            )
        )
    session.commit()
