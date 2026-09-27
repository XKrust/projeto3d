import json
from datetime import date, timedelta

import pytest
from sqlmodel import Session

from app import clock
from app.constants import GLOBAL
from app.models import HypeListing, HypeRelease

DAY = date(2026, 9, 27)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: DAY)


def _add(engine, *rows):
    with Session(engine) as session:
        for row in rows:
            session.add(row)
        session.commit()


def _release(external_id, title, *, kind="anime", popularity=100.0, days=40, country=GLOBAL,
             characters=(), source="anilist", no_date=False):
    return HypeRelease(
        source=source,
        external_id=external_id,
        kind=kind,
        title=title,
        release_date=None if no_date else DAY + timedelta(days=days),
        popularity=popularity,
        country=country,
        image_url=f"https://img/{external_id}.jpg",
        url=f"https://site/{external_id}",
        characters_json=json.dumps(list(characters), ensure_ascii=False),
        updated_day=DAY,
    )


def _char(name, favourites=5000):
    return {"name": name, "native": None, "favourites": favourites, "image_url": f"https://img/{name}.jpg"}


def test_api_hype_orders_by_popularity_and_filters_country(client, engine):
    _add(
        engine,
        _release("a", "Anime Popular", popularity=900),
        _release("b", "Anime Menor", popularity=100),
        _release("f-br", "Filme No Brasil", kind="filme", popularity=500, country="BR", source="tmdb"),
        _release("f-jp", "Filme No Japao", kind="filme", popularity=800, country="JP", source="tmdb"),
    )

    body = client.get("/api/hype?country=BR").json()

    assert [r["title"] for r in body["releases"]] == ["Anime Popular", "Filme No Brasil", "Anime Menor"]


def test_api_hype_filters_kind(client, engine):
    _add(engine, _release("a", "Anime Um"), _release("j", "Jogo Um", kind="jogo", source="igdb"))

    body = client.get("/api/hype?country=BR&kind=jogo").json()

    assert [r["title"] for r in body["releases"]] == ["Jogo Um"]


def test_api_hype_release_fields_and_reason_with_competition(client, engine):
    _add(
        engine,
        _release("a", "Frieren Season 2", days=40),
        HypeListing(term="Frieren", platform="cults3d", day=DAY, count=34),
        HypeListing(term="Frieren", platform="booth", day=DAY, count=7),
    )

    release = client.get("/api/hype?country=BR").json()["releases"][0]

    assert release["release_date"] == "2026-11-06"
    assert release["days_to_release"] == 40
    assert release["peak"] == "2026-10-16"  # estreia − 21 dias
    assert release["fit_window"] == 1.0
    assert release["competition"] == {"Cults3D": 34, "BOOTH": 7}
    assert release["sale_chance"] in {"Alta", "Média", "Baixa"}
    assert release["reason"] == "Estreia em 40 dias · 34 anúncios no Cults3D"
    assert release["kind"] == "anime"
    assert release["image_url"] == "https://img/a.jpg"


def test_api_hype_release_without_date_says_a_confirmar(client, engine):
    _add(engine, _release("a", "Sem Data", no_date=True))

    release = client.get("/api/hype?country=BR").json()["releases"][0]

    assert release["release_date"] is None
    assert release["days_to_release"] is None
    assert release["peak"] is None
    assert release["fit_window"] == 1.0
    assert release["reason"] == "Data de estreia a confirmar · concorrência ainda não medida"


def test_api_hype_late_release_has_low_fit_window(client, engine):
    # estreia em 10 dias: pico = hoje − 11; entrega = hoje + 7 → 18 dias de atraso
    _add(engine, _release("a", "Estreia Logo", days=10))

    release = client.get("/api/hype?country=BR").json()["releases"][0]

    assert release["fit_window"] == pytest.approx(0.5 ** (18 / 7), abs=0.001)


def test_api_hype_drops_old_releases(client, engine):
    _add(engine, _release("a", "Estreou Ha Muito", days=-45), _release("b", "Estreia Futura", days=5))

    titles = [r["title"] for r in client.get("/api/hype?country=BR").json()["releases"]]

    assert titles == ["Estreia Futura"]


def test_api_hype_character_has_sale_chance(client, engine):
    _add(
        engine,
        _release("a", "The Apothecary Diaries", characters=[_char("Maomao", 22000), _char("Jinshi", 4000)]),
        HypeListing(term="Maomao", platform="cults3d", day=DAY, count=12),
    )

    release = client.get("/api/hype?country=BR").json()["releases"][0]

    assert [c["name"] for c in release["characters"]] == ["Maomao", "Jinshi"]
    maomao = release["characters"][0]
    assert maomao["competition"] == {"Cults3D": 12}
    assert maomao["sale_chance"] in {"Alta", "Média", "Baixa"}
    assert maomao["image_url"] == "https://img/Maomao.jpg"


def test_api_hype_invalid_country_422(client):
    response = client.get("/api/hype?country=XX")

    assert response.status_code == 422
    assert response.json()["detail"] == "País inválido"
