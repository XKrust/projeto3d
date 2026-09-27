"""Rota do calendário sazonal (/api/seasonal)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app import clock
from app.constants import COUNTRIES
from app.db import get_session
from app.hype.seasonal import upcoming_events
from app.settings_store import get_settings

router = APIRouter()


@router.get("/seasonal")
def read_seasonal(country: str = "BR", session: Session = Depends(get_session)) -> dict:
    if country not in COUNTRIES:
        raise HTTPException(status_code=422, detail="País inválido")
    settings = get_settings(session)
    lead_days = int(settings["lead_days"])
    modeling_days = int(settings["modeling_days"])
    events = upcoming_events(country, clock.today(), lead_days, modeling_days)
    return {
        "country": country,
        "lead_days": lead_days,
        "modeling_days": modeling_days,
        "events": [
            {**e, "date": e["date"].isoformat(), "start_by": e["start_by"].isoformat()}
            for e in events
        ],
    }
