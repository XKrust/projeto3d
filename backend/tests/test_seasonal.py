from datetime import date

import pytest

from app import clock
from app.hype.seasonal import load_events, next_occurrence, resolve, upcoming_events


def test_resolve_fixed():
    assert resolve({"fixed": "10-31"}, 2026) == date(2026, 10, 31)


def test_resolve_easter_2027():
    assert resolve({"easter_offset": 0}, 2027) == date(2027, 3, 28)


def test_resolve_carnival_is_easter_minus_47():
    assert resolve({"easter_offset": -47}, 2027) == date(2027, 2, 9)


def test_resolve_nth_weekday_mothers_day_br_2027():
    rule = {"nth_weekday": {"month": 5, "weekday": 6, "n": 2}}
    assert resolve(rule, 2027) == date(2027, 5, 9)


def test_resolve_last_sunday_may_fr_2027():
    rule = {"nth_weekday": {"month": 5, "weekday": 6, "n": -1}}
    assert resolve(rule, 2027) == date(2027, 5, 30)


def test_resolve_black_friday_2026():
    rule = {"after_nth_weekday": {"month": 11, "weekday": 3, "n": 4, "plus_days": 1}}
    assert resolve(rule, 2026) == date(2026, 11, 27)


def test_next_occurrence_rolls_to_next_year():
    assert next_occurrence({"fixed": "06-12"}, date(2026, 9, 27)) == date(2027, 6, 12)


def test_next_occurrence_today_counts():
    assert next_occurrence({"fixed": "09-27"}, date(2026, 9, 27)) == date(2026, 9, 27)


def _by_slug(events):
    return {e["slug"]: e for e in events}


def test_upcoming_events_start_by_subtracts_lead_and_modeling():
    events = _by_slug(upcoming_events("BR", date(2026, 9, 1), lead_days=21, modeling_days=7))

    halloween = events["halloween"]
    assert halloween["date"] == date(2026, 10, 31)
    assert halloween["start_by"] == date(2026, 10, 3)
    assert halloween["days_to_start"] == 32
    assert halloween["days_to_event"] == 60
    assert halloween["status"] == "em_breve"


def test_status_atrasado_when_start_by_passed_but_event_not():
    events = _by_slug(upcoming_events("BR", date(2026, 10, 20), lead_days=21, modeling_days=7))

    halloween = events["halloween"]
    assert halloween["date"] == date(2026, 10, 31)
    assert halloween["status"] == "atrasado"
    assert halloween["days_to_start"] < 0


def test_status_agora_when_start_within_7_days():
    events = _by_slug(upcoming_events("BR", date(2026, 9, 30), lead_days=21, modeling_days=7))

    assert events["halloween"]["status"] == "agora"


def test_upcoming_filters_by_country():
    jp = _by_slug(upcoming_events("JP", date(2026, 9, 1), lead_days=21, modeling_days=7))
    br = _by_slug(upcoming_events("BR", date(2026, 9, 1), lead_days=21, modeling_days=7))

    assert "tanabata" in jp
    assert "tanabata" not in br
    assert "dia_das_criancas_br" in br
    assert "halloween" in jp and "halloween" in br


def test_upcoming_sorted_by_start_by_and_has_themes():
    events = upcoming_events("BR", date(2026, 9, 1), lead_days=21, modeling_days=7)

    starts = [e["start_by"] for e in events]
    assert starts == sorted(starts)
    assert all(e["themes"] for e in events)


def test_api_seasonal_returns_events_sorted(client, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2026, 9, 1))

    response = client.get("/api/seasonal?country=BR")

    assert response.status_code == 200
    body = response.json()
    assert body["country"] == "BR"
    assert body["lead_days"] == 21
    assert body["modeling_days"] == 7
    starts = [e["start_by"] for e in body["events"]]
    assert starts == sorted(starts)
    halloween = next(e for e in body["events"] if e["slug"] == "halloween")
    assert halloween["start_by"] == "2026-10-03"


def test_api_seasonal_invalid_country_422(client):
    response = client.get("/api/seasonal?country=XX")

    assert response.status_code == 422
    assert response.json()["detail"] == "País inválido"


@pytest.mark.parametrize("country", ["BR", "US", "GB", "DE", "FR", "ES", "JP"])
def test_every_country_has_events(country):
    assert upcoming_events(country, date(2026, 9, 1), lead_days=21, modeling_days=7)


def test_fete_des_meres_moves_when_pentecost():
    # Último domingo de maio, exceto quando cai no Pentecostes: vai para o 1º de junho.
    event = next(e for e in load_events() if e["slug"] == "fete_des_meres_fr")
    assert resolve(event["rule"], 2027) == date(2027, 5, 30)
    assert resolve(event["rule"], 2023) == date(2023, 6, 4)
    assert resolve(event["rule"], 2034) == date(2034, 6, 4)


@pytest.mark.parametrize(
    ("country", "slug"),
    [
        ("MX", "dia_de_muertos"),
        ("MX", "dia_de_las_madres_mx"),
        ("RU", "dia_da_mulher_ru_by"),
        ("BY", "ano_novo_ru_by"),
        ("IT", "dia_das_maes"),
        ("PL", "dzien_matki_pl"),
        ("CA", "thanksgiving_ca"),
    ],
)
def test_new_countries_have_their_own_dates(country, slug):
    slugs = {e["slug"] for e in load_events() if country in e["countries"]}
    assert slug in slugs
