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


def test_invalid_gemini_key_is_reported(client, monkeypatch):
    """Chave errada não pode virar "a IA não respondeu, tente de novo"."""
    from google.genai.errors import ClientError

    from app.ai.provider import AIKeyError, GeminiTextProvider

    class FakeModels:
        def generate_content(self, **kwargs):
            raise ClientError(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                                              "status": "INVALID_ARGUMENT"}}, None)

    class FakeClient:
        def __init__(self, api_key, **kwargs):
            self.models = FakeModels()

    monkeypatch.setattr("app.ai.provider.Client", FakeClient)
    with pytest.raises(AIKeyError):
        GeminiTextProvider("errada", "gemini-2.5-flash").generate_json("oi")


def test_analyze_with_bad_key_returns_409(client):
    from app.ai.provider import AIKeyError
    from app.api.analyze import MSG_BAD_KEY, get_analyzer_provider

    class Provider:
        def generate_json_with_images(self, prompt, images):
            raise AIKeyError("bad")

    client.app.dependency_overrides[get_analyzer_provider] = lambda: Provider()
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    response = client.post("/api/analyze", data={"authorship": "autoral", "market": "print"},
                           files=[("images", ("a.png", png, "image/png"))])
    assert response.status_code == 409
    assert response.json()["detail"] == MSG_BAD_KEY
