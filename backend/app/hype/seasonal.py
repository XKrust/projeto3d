"""Calendário sazonal: próximas datas que vendem em cada país e até quando começar a
modelar. Puro cálculo sobre `seed/seasonal_events.yaml`, sem rede. Ver
docs/hype-sazonal.md."""

from calendar import monthrange
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

_EVENTS_FILE = Path(__file__).resolve().parent.parent / "seed" / "seasonal_events.yaml"
ALL_COUNTRIES = "ALL"
AGORA_DAYS = 7


@lru_cache(maxsize=1)
def _load_file() -> dict:
    with open(_EVENTS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_events() -> tuple[dict, ...]:
    return tuple(_load_file().get("events") or [])


def event_ideas(event: dict) -> list[dict]:
    """Ideias de modelo da data: `{name, query, keywords}` do `idea_set` do evento."""
    return list((_load_file().get("idea_sets") or {}).get(event.get("ideas"), []))


def easter(year: int) -> date:
    """Domingo de Páscoa (calendário gregoriano, algoritmo de Meeus/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741  nomes do algoritmo original
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """O n-ésimo `weekday` (0=segunda) do mês; n=-1 é o último."""
    if n > 0:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (n - 1))
    last = date(year, month, monthrange(year, month)[1])
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset + 7 * (-n - 1))


def resolve(rule: dict, year: int) -> date:
    """Data de um evento no ano `year`, segundo a regra do YAML."""
    if "fixed" in rule:
        month, day = (int(part) for part in rule["fixed"].split("-"))
        return date(year, month, day)
    if "easter_offset" in rule:
        return easter(year) + timedelta(days=int(rule["easter_offset"]))
    if "nth_weekday" in rule:
        r = rule["nth_weekday"]
        return _nth_weekday(year, r["month"], r["weekday"], r["n"])
    if "after_nth_weekday" in rule:
        r = rule["after_nth_weekday"]
        return _nth_weekday(year, r["month"], r["weekday"], r["n"]) + timedelta(days=r["plus_days"])
    raise ValueError(f"Regra de data desconhecida: {rule}")


def next_occurrence(rule: dict, today: date) -> date:
    """A ocorrência deste ano, se ainda não passou (hoje conta); senão a do próximo."""
    this_year = resolve(rule, today.year)
    return this_year if this_year >= today else resolve(rule, today.year + 1)


def _status(days_to_start: int) -> str:
    if days_to_start < 0:
        return "atrasado"
    if days_to_start <= AGORA_DAYS:
        return "agora"
    return "em_breve"


def upcoming_events(
    country: str, today: date, lead_days: int, modeling_days: int, limit: int = 20
) -> list[dict]:
    """Próximos eventos do país, ordenados pelo dia de começar a modelar.

    `start_by` = data do evento − antecedência de compra − tempo de modelagem.
    """
    events = []
    for event in load_events():
        countries = event.get("countries") or []
        if ALL_COUNTRIES not in countries and country not in countries:
            continue
        when = next_occurrence(event["rule"], today)
        start_by = when - timedelta(days=lead_days + modeling_days)
        days_to_start = (start_by - today).days
        events.append(
            {
                "slug": event["slug"],
                "name": event["name"],
                "date": when,
                "start_by": start_by,
                "days_to_event": (when - today).days,
                "days_to_start": days_to_start,
                "status": _status(days_to_start),
                "themes": [idea["name"] for idea in event_ideas(event)],
                "_event": event,
            }
        )
    events.sort(key=lambda e: (e["start_by"], e["slug"]))
    return events[:limit]


TOP_MODELS = 5
NEUTRAL_MOMENTUM = 50.0
UNMEASURED_SATURATION = 50.0


def top_models(
    session,
    event: dict,
    country: str,
    today: date,
    event_date: date,
    *,
    lead_days: int,
    modeling_days: int,
    weights: dict,
    names: dict[str, str],
) -> list[dict]:
    """As 5 ideias com mais chance de vender na data, no país.

    Mesma fórmula de oportunidade do radar (docs/score.md): demanda = percentil do sinal
    entre as ideias da data; saturação = percentil dos anúncios entre as ideias medidas;
    momentum neutro; janela = (evento − antecedência) contra (hoje + modelagem). Ideias
    sem sinal nem contagem ficam sem nota (nada de número inventado) e vão por último,
    na ordem do YAML. Se nenhuma ideia da data tem procura, ninguém ganha nota.
    """
    from app.hype.seasonal_ideas import latest_competition, latest_signals
    from app.scoring import formulas

    ideas = event_ideas(event)
    signals = latest_signals(session, country, today)
    competition = latest_competition(session, today)

    idea_signal = {idea["name"]: signals.get(idea["name"], 0.0) for idea in ideas}
    idea_counts = {idea["name"]: competition.get(idea["query"], {}) for idea in ideas}
    measured = {
        name for name in idea_signal if idea_signal[name] > 0 or idea_counts[name]
    }
    demand = formulas.percentile_ranks({name: idea_signal[name] for name in measured})
    saturation = formulas.percentile_ranks(
        {name: float(sum(idea_counts[name].values())) for name in measured if idea_counts[name]}
    )
    peak = formulas.peak_day(today, 0.0, event_day=event_date, lead_days=lead_days)
    fit = formulas.window_fit(peak, today + timedelta(days=modeling_days))
    # Só contagem de anúncios, sem procura em nenhuma ideia da data: não há o que ranquear
    # na demanda, então nenhuma nota (a concorrência continua aparecendo).
    has_demand = any(signal > 0 for signal in idea_signal.values())

    models = []
    for position, idea in enumerate(ideas):
        name = idea["name"]
        is_measured = name in measured
        opportunity = None
        chance = None
        if is_measured and has_demand:
            opportunity = formulas.opportunity(
                demand.get(name, 0.0), NEUTRAL_MOMENTUM,
                saturation.get(name, UNMEASURED_SATURATION), fit, weights,
            )
            chance = formulas.sale_chance(opportunity)
        counts = sorted(idea_counts[name].items(), key=lambda kv: (-kv[1], kv[0]))
        models.append(
            {
                "name": name,
                "query": idea["query"],
                "opportunity": opportunity,
                "sale_chance": chance,
                "measured": is_measured,
                "competition": {names.get(slug, slug): count for slug, count in counts},
                "signal": idea_signal[name],
                "_position": position,
            }
        )
    models.sort(key=lambda m: (not m["measured"], -(m["opportunity"] or 0), m["_position"]))
    for model in models:
        del model["_position"]
    return models[:TOP_MODELS]
