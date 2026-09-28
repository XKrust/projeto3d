"""Rotas de fontes: listagem de status (/api/sources) e coleta manual (/api/collect)."""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

import app.collectors as collectors_pkg
from app.db import get_session
from app.models import Source
from app.pipeline import run_after_cycle
from app.runner import collect_progress, start_cycle_in_background
from app.settings_store import get_settings

router = APIRouter()


@router.get("/sources")
def read_sources(session: Session = Depends(get_session)) -> list[dict]:
    settings = get_settings(session)
    api_keys = settings.get("api_keys", {})
    rows_by_name = {row.name: row for row in session.exec(select(Source)).all()}

    result = []
    for cls in collectors_pkg.ALL_COLLECTORS:
        has_key = all(api_keys.get(key) for key in cls.needs_key)
        row = rows_by_name.get(cls.name)
        if not has_key:
            status = "no_key"
        elif row is not None:
            status = row.status
        else:
            status = "never"

        result.append(
            {
                "name": cls.name,
                "label": cls.label,
                "kind": cls.kind,
                "needs_key": bool(cls.needs_key),
                "has_key": has_key,
                "status": status,
                "last_run": row.last_run if row else None,
                "last_error": row.last_error if row else None,
                "items_last_run": row.items_last_run if row else 0,
            }
        )
    return result


@router.post("/collect")
def start_collect(request: Request, source: str | None = None) -> dict:
    session_factory = request.app.state.session_factory
    started = start_cycle_in_background(session_factory, only=source, after=run_after_cycle)
    if started:
        return {"started": True, "message": "Coleta iniciada."}
    return {"started": False, "message": "Já existe uma coleta em andamento."}


@router.get("/collect/status")
def read_collect_status() -> dict:
    """Coleta em andamento: `running`, `phase` ("coleta" ou "notas"), fonte `current`,
    `done`/`total` e horários. A tela usa para mostrar o progresso e se atualizar no fim."""
    return collect_progress()
