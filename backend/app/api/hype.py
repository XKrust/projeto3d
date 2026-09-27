"""Rota do hype (/api/hype): estreias com pico, concorrência e chance de venda.

A nota de cada lançamento usa a mesma fórmula de oportunidade do radar (docs/score.md):
- `demanda` = percentil da popularidade entre os lançamentos do mesmo tipo;
- `momentum` = 50 (neutro — não há série histórica de estreia);
- `saturação` = percentil dos anúncios somados entre os termos medidos (50 sem medição);
- `fit_janela` = pico (estreia − antecedência) contra entrega (hoje + tempo de modelagem).
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, or_, select

from app import clock
from app.constants import COUNTRIES, GLOBAL
from app.db import get_session
from app.hype.entities import base_title, top_characters
from app.models import HypeListing, HypeRelease, Platform
from app.scoring import formulas
from app.settings_store import get_settings

router = APIRouter()

KINDS = ("anime", "filme", "serie", "jogo")
PAST_DAYS = 30
STALE_DAYS = 7
MAX_RELEASES = 40
NEUTRAL_MOMENTUM = 50.0
UNMEASURED_SATURATION = 50.0


def _latest_competition(session: Session, today: date) -> dict[str, dict[str, int]]:
    """term → {slug da plataforma: contagem} do dia mais recente medido (até hoje)."""
    latest: dict[tuple[str, str], tuple[date, int]] = {}
    for row in session.exec(select(HypeListing).where(HypeListing.day <= today)).all():
        key = (row.term, row.platform)
        if key not in latest or row.day > latest[key][0]:
            latest[key] = (row.day, row.count)
    result: dict[str, dict[str, int]] = {}
    for (term, platform), (_, count) in latest.items():
        result.setdefault(term, {})[platform] = count
    return result


def _named(competition: dict[str, int], names: dict[str, str]) -> dict[str, int]:
    ordered = sorted(competition.items(), key=lambda kv: (-kv[1], kv[0]))
    return {names.get(slug, slug): count for slug, count in ordered}


def _reason(days_to_release: int | None, competition: dict[str, int]) -> str:
    if days_to_release is None:
        timing = "Data de estreia a confirmar"
    elif days_to_release > 1:
        timing = f"Estreia em {days_to_release} dias"
    elif days_to_release == 1:
        timing = "Estreia amanhã"
    elif days_to_release == 0:
        timing = "Estreia hoje"
    else:
        timing = f"Estreou há {-days_to_release} dias"
    if not competition:
        return f"{timing} · concorrência ainda não medida"
    platform, count = next(iter(competition.items()))
    if count == 0:
        return f"{timing} · nenhum anúncio nas lojas medidas"
    return f"{timing} · {count} anúncios no {platform}"


@router.get("/hype")
def read_hype(
    country: str = "BR", kind: str | None = None, session: Session = Depends(get_session)
) -> dict:
    if country not in COUNTRIES:
        raise HTTPException(status_code=422, detail="País inválido")
    if kind is not None and kind not in KINDS:
        raise HTTPException(status_code=422, detail="Tipo inválido")

    today = clock.today()
    settings = get_settings(session)
    lead_days = int(settings["lead_days"])
    delivery = today + timedelta(days=int(settings["modeling_days"]))
    weights = settings["weights"]

    query = select(HypeRelease).where(
        HypeRelease.country.in_([GLOBAL, country]),
        HypeRelease.updated_day >= today - timedelta(days=STALE_DAYS),
        or_(
            HypeRelease.release_date.is_(None),
            HypeRelease.release_date >= today - timedelta(days=PAST_DAYS),
        ),
    )
    if kind is not None:
        query = query.where(HypeRelease.kind == kind)
    rows = session.exec(query.order_by(HypeRelease.popularity.desc())).all()[:MAX_RELEASES]

    names = {p.slug: p.name for p in session.exec(select(Platform)).all()}
    competition = _latest_competition(session, today)
    saturation = formulas.percentile_ranks(
        {term: float(sum(counts.values())) for term, counts in competition.items()}
    )

    demand_by_kind: dict[str, dict[int, float]] = {}
    for k in {row.kind for row in rows}:
        demand_by_kind[k] = formulas.percentile_ranks(
            {row.id: row.popularity for row in rows if row.kind == k}
        )
    all_characters = {
        (row.id, c["name"]): float(c.get("favourites") or 0)
        for row in rows
        for c in top_characters(row.characters_json)
    }
    character_demand = formulas.percentile_ranks(all_characters)

    def score(demand: float, term: str, fit: float) -> tuple[float, str]:
        sat = saturation.get(term, UNMEASURED_SATURATION)
        opp = formulas.opportunity(demand, NEUTRAL_MOMENTUM, sat, fit, weights)
        return opp, formulas.sale_chance(opp)

    releases = []
    for row in rows:
        term = base_title(row.title)
        if row.release_date is not None:
            days_to_release = (row.release_date - today).days
            peak = formulas.peak_day(today, 0.0, event_day=row.release_date, lead_days=lead_days)
            fit = round(formulas.window_fit(peak, delivery), 4)
        else:
            days_to_release, peak, fit = None, None, 1.0
        opp, chance = score(demand_by_kind[row.kind][row.id], term, fit)
        release_competition = _named(competition.get(term, {}), names)

        characters = []
        for c in top_characters(row.characters_json):
            c_opp, c_chance = score(character_demand[(row.id, c["name"])], c["name"], fit)
            characters.append(
                {
                    "name": c["name"],
                    "image_url": c.get("image_url"),
                    "favourites": int(c.get("favourites") or 0),
                    "competition": _named(competition.get(c["name"], {}), names),
                    "opportunity": c_opp,
                    "sale_chance": c_chance,
                }
            )

        releases.append(
            {
                "id": row.id,
                "title": row.title,
                "term": term,
                "kind": row.kind,
                "source": row.source,
                "release_date": row.release_date.isoformat() if row.release_date else None,
                "days_to_release": days_to_release,
                "peak": peak.isoformat() if peak else None,
                "fit_window": fit,
                "image_url": row.image_url,
                "url": row.url,
                "popularity": row.popularity,
                "competition": release_competition,
                "opportunity": opp,
                "sale_chance": chance,
                "reason": _reason(days_to_release, release_competition),
                "characters": characters,
            }
        )

    return {"country": country, "releases": releases}
