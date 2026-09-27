from app.models import Platform
from app.platforms import seed_platforms


def test_seed_platforms_idempotent_and_preserves_edits(session):
    seed_platforms(session)
    p = session.get(Platform, "cults3d")
    p.fee_pct = 15.0
    session.add(p)
    session.commit()

    seed_platforms(session)

    p2 = session.get(Platform, "cults3d")
    assert p2.fee_pct == 15.0


def test_get_platforms_returns_seeded(client):
    r = client.get("/api/platforms")
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()}
    assert slugs == {"cults3d", "sketchfab", "printables"}


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
