"""Rotas da venda (Etapa 3b): preparar a venda de uma análise e os países do seletor."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app import clock
from app.ai.provider import TextProvider
from app.api.analyze import get_analyzer_provider
from app.constants import COUNTRIES, COUNTRY_NAMES
from app.db import get_session
from app.models import Analysis
from app.sale.build import build_sale
from app.sale.stores import default_countries
from app.settings_store import get_settings

router = APIRouter()

MAX_COUNTRIES = 5


class SaleRequest(BaseModel):
    countries: list[str] = []


def _get(session: Session, analysis_id: int) -> Analysis:
    row = session.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    return row


@router.post("/analyses/{analysis_id}/sale")
def prepare_sale(
    analysis_id: int,
    body: SaleRequest | None = None,
    session: Session = Depends(get_session),
    provider: TextProvider | None = Depends(get_analyzer_provider),
) -> dict:
    row = _get(session, analysis_id)
    countries = list(dict.fromkeys(body.countries if body else [])) or default_countries(session)
    if any(code not in COUNTRIES for code in countries):
        raise HTTPException(status_code=422, detail="País inválido")
    if not 1 <= len(countries) <= MAX_COUNTRIES:
        raise HTTPException(status_code=422, detail="Escolha de 1 a 5 países")
    sale = build_sale(session, row, countries, provider)
    row.sale_json = json.dumps(sale, ensure_ascii=False)
    row.sale_at = clock.now()
    session.add(row)
    session.commit()
    return sale


@router.get("/analyses/{analysis_id}/sale/countries")
def read_sale_countries(analysis_id: int, session: Session = Depends(get_session)) -> dict:
    """Países ativos para o seletor, na ordem do ranking do dia, com os padrões marcados."""
    _get(session, analysis_id)
    defaults = default_countries(session)
    active = [c for c in COUNTRIES if c in get_settings(session).get("countries", [])]
    ordered = defaults + [c for c in active if c not in defaults]
    return {
        "max": MAX_COUNTRIES,
        "defaults": defaults,
        "countries": [{"code": code, "name": COUNTRY_NAMES[code]} for code in ordered],
    }
