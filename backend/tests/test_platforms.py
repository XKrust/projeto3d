import json

from sqlmodel import Session, create_engine, select

from app.db import init_db
from app.models import Platform
from app.platforms import seed_platforms

SELLING = {"cults3d", "printables", "myminifactory", "etsy", "cgtrader", "booth", "fab"}


def test_seed_platforms_idempotent_and_preserves_edits(session):
    seed_platforms(session)
    p = session.get(Platform, "cults3d")
    p.fee_pct = 15.0
    p.edited = True
    session.add(p)
    session.commit()

    seed_platforms(session)

    p2 = session.get(Platform, "cults3d")
    assert p2.fee_pct == 15.0


def test_get_platforms_returns_seeded(client):
    r = client.get("/api/platforms")
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()}
    assert slugs == SELLING | {"sketchfab", "artstation", "mercadolivre"}
    sketchfab = next(p for p in r.json() if p["slug"] == "sketchfab")
    assert sketchfab["sells"] is False


def test_put_platform_unknown_slug_404(client):
    r = client.put("/api/platforms/unknown", json={"fee_pct": 10})
    assert r.status_code == 404
    assert r.json()["detail"] == "Plataforma não encontrada"


def test_put_platform_invalid_strength_422(client):
    r = client.put("/api/platforms/cults3d", json={"strength": {"BR": 1.5}})
    assert r.status_code == 422
    assert r.json()["detail"] == "A força deve estar entre 0 e 1"


def test_put_platform_updates_fields_and_preserves_others(client):
    r = client.put(
        "/api/platforms/cults3d", json={"fee_pct": 18.5, "notes": "atualizado"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["fee_pct"] == 18.5
    assert body["notes"] == "atualizado"
    assert body["strength"]["FR"] == 0.9

    r2 = client.put("/api/platforms/cults3d", json={"strength": {"BR": 0.9}})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["strength"]["BR"] == 0.9
    assert body2["strength"]["FR"] == 0.9


def test_closed_stores_do_not_sell(session):
    # Sketchfab Store fechou em 2024 e ArtStation Marketplace migrou em 2025 (para a Fab).
    seed_platforms(session)

    assert session.get(Platform, "sketchfab").sells is False
    assert session.get(Platform, "artstation").sells is False
    assert {p.slug for p in session.exec(select(Platform)).all() if p.sells} == SELLING


def test_seed_updates_platforms_the_user_never_edited(session):
    # Banco antigo: Sketchfab ainda como loja, com a força chutada.
    session.add(Platform(slug="sketchfab", name="Sketchfab Store", markets_json='["digital"]',
                         strength_json='{"BR": 0.5, "US": 0.8}'))
    session.commit()

    seed_platforms(session)

    sketchfab = session.get(Platform, "sketchfab")
    assert sketchfab.sells is False
    assert json.loads(sketchfab.strength_json)["US"] == 0.0


def test_seed_keeps_what_the_user_edited(client, engine):
    client.put("/api/platforms/cults3d", json={"strength": {"BR": 0.1}})

    with Session(engine) as session:
        seed_platforms(session)
        cults = session.get(Platform, "cults3d")
        assert cults.edited is True
        assert json.loads(cults.strength_json)["BR"] == 0.1


def test_every_selling_platform_explains_its_strength(session):
    seed_platforms(session)
    for platform in session.exec(select(Platform)).all():
        assert platform.notes, platform.slug


def test_init_db_adds_new_columns_to_an_old_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE platform (slug VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, "
            "markets_json VARCHAR NOT NULL, fee_pct FLOAT, strength_json VARCHAR NOT NULL, "
            "notes VARCHAR NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO platform VALUES ('cults3d', 'Cults3D', '[\"print\"]', NULL, '{}', '')"
        )

    init_db(engine)

    with Session(engine) as session:
        cults = session.get(Platform, "cults3d")
        assert cults.sells is True
        assert cults.edited is False
        assert cults.categories_json == "[]"
