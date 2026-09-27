"""Rota do calendário sazonal (/api/seasonal): datas, "comece a modelar até" e o top 5
de modelos com mais chance de vender em cada data."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app import clock
from app.constants import COUNTRIES
from app.db import get_session
from app.hype.seasonal import top_models, upcoming_events
from app.models import Platform
from app.settings_store import get_settings

router = APIRouter()


@router.get("/seasonal")
def read_seasonal(country: str = "BR", session: Session = Depends(get_session)) -> dict:
    if country not in COUNTRIES:
        raise HTTPException(status_code=422, detail="País inválido")
    settings = get_settings(session)
    lead_days = int(settings["lead_days"])
    modeling_days = int(settings["modeling_days"])
    today = clock.today()
    names = {p.slug: p.name for p in session.exec(select(Platform)).all()}

    events = []
    for e in upcoming_events(country, today, lead_days, modeling_days):
        event = e.pop("_event")
        models = top_models(
            session, event, country, today, e["date"],
            lead_days=lead_days, modeling_days=modeling_days,
            weights=settings["weights"], names=names,
        )
        events.append(
            {
                **e,
                "date": e["date"].isoformat(),
                "start_by": e["start_by"].isoformat(),
                "top_models": models,
            }
        )
    return {"country": country, "lead_days": lead_days, "modeling_days": modeling_days, "events": events}
