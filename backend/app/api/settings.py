"""Rotas de configuracoes (/api/settings) e plataformas (/api/platforms)."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Platform
from app.settings_store import get_settings, masked, update_settings

router = APIRouter()


@router.get("/settings")
def read_settings(session: Session = Depends(get_session)) -> dict:
    return masked(get_settings(session))


@router.put("/settings")
def write_settings(patch: dict, session: Session = Depends(get_session)) -> dict:
    try:
        updated = update_settings(session, patch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return masked(updated)


def _platform_to_dict(platform: Platform) -> dict:
    return {
        "slug": platform.slug,
        "name": platform.name,
        "markets": json.loads(platform.markets_json),
        "fee_pct": platform.fee_pct,
        "strength": json.loads(platform.strength_json),
        "notes": platform.notes,
        "sells": platform.sells,
        "categories": json.loads(platform.categories_json),
    }


@router.get("/platforms")
def read_platforms(session: Session = Depends(get_session)) -> list[dict]:
    platforms = session.exec(select(Platform)).all()
    return [_platform_to_dict(p) for p in platforms]


@router.put("/platforms/{slug}")
def write_platform(
    slug: str, patch: dict, session: Session = Depends(get_session)
) -> dict:
    platform = session.get(Platform, slug)
    if platform is None:
        raise HTTPException(status_code=404, detail="Plataforma não encontrada")

    if "strength" in patch:
        incoming_strength = patch["strength"]
        for value in incoming_strength.values():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not (
                0 <= value <= 1
            ):
                raise HTTPException(
                    status_code=422, detail="A força deve estar entre 0 e 1"
                )
        current_strength = json.loads(platform.strength_json)
        current_strength.update(incoming_strength)
        platform.strength_json = json.dumps(current_strength)

    if "fee_pct" in patch:
        fee = patch["fee_pct"]
        if fee is not None and (not isinstance(fee, (int, float)) or isinstance(fee, bool) or not 0 <= fee <= 100):
            raise HTTPException(status_code=422, detail="A taxa deve estar entre 0 e 100")
        platform.fee_pct = fee

    if "notes" in patch:
        platform.notes = patch["notes"]

    # A partir daqui o arquivo de seed não sobrescreve mais a edição do usuário.
    platform.edited = True
    session.add(platform)
    session.commit()
    session.refresh(platform)
    return _platform_to_dict(platform)
