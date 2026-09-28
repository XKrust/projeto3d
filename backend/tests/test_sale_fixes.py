"""Testes das correções da revisão de bugs (28/09/2026)."""

import pytest

from app import clock
from app.api.hype import _reason
from app.models import RawItem
from app.sale import cover
from app.sale.build import _checklist


def test_hype_yesterday_is_singular():
    assert _reason(-1, {}).startswith("Estreou ontem")
    assert _reason(-3, {}).startswith("Estreou há 3 dias")


@pytest.mark.parametrize("fee", [150, -1, "vinte", True])
def test_platform_fee_is_validated(client, fee):
    response = client.put("/api/platforms/cults3d", json={"fee_pct": fee})
    assert response.status_code == 422
    assert response.json()["detail"] == "A taxa deve estar entre 0 e 100"


def test_platform_fee_accepts_valid_and_null(client):
    assert client.put("/api/platforms/cults3d", json={"fee_pct": 12.5}).json()["fee_pct"] == 12.5
    assert client.put("/api/platforms/cults3d", json={"fee_pct": None}).json()["fee_pct"] is None


def test_checklist_names_country_of_first_store():
    by_country = [{"country": "JP", "stores": []},
                  {"country": "BR", "stores": [{"name": "Cults3D", "price": None}]}]
    assert _checklist(by_country, None, [])[0] == "Publique primeiro no Cults3D (melhor encaixe no Brasil)."


def test_top_covers_respects_attempts_and_time_budget(monkeypatch):
    calls = []
    monkeypatch.setattr(cover, "download_image", lambda http, url: calls.append(url) or None)
    items = [RawItem(source="etsy", external_id=str(n), country="US", day=clock.today(), title=str(n), metric=1,
                     thumb_url=f"https://x/{n}.jpg", likes=n) for n in range(40)]
    refs, _ = cover.top_covers(None, items)
    assert refs == [] and len(calls) == 6  # no máximo 6 tentativas

    calls.clear()
    ticks = iter([0.0, 0.0, 10.0, 25.0, 30.0])
    cover.top_covers(None, items, monotonic=lambda: next(ticks))
    assert len(calls) == 2  # parou quando passou de 20 s
