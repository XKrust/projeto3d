import json
from pathlib import Path

import httpx
import pytest
import respx
from sqlmodel import Session

from app.ai.provider import AIQuotaError
from app.analyzer import store
from app.analyzer.store import save_analysis
from app.api.analyze import get_analyzer_provider
from app.fx import ECB_URL
from app.platforms import seed_platforms

XML = (Path(__file__).parent / "fixtures" / "ecb" / "eurofxref-daily.xml").read_text(encoding="utf-8")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
COPY = {"titles": {"en": "Frieren Bust STL", "pt": "Busto da Frieren", "de": "Frieren Büste", "ja": "フリーレン"},
        "tags": ["frieren", "bust"], "description": "Bust of Frieren."}


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)

    def generate_json(self, prompt):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)


@pytest.fixture()
def analysis_id(engine):
    with Session(engine) as session:
        seed_platforms(session)
        row = save_analysis(
            session,
            form={"authorship": "fanart", "market": "print", "hours": 10.0},
            identified={"theme": "Busto da Frieren", "category": "anime", "style": "anime", "character": "Frieren",
                        "search_query": "frieren bust"},
            references=[],
            references_note=None,
            result={"criteria": {}, "strengths": [], "improvements": [], "to_check": [], "reference_comparison": [],
                    "top_actions": [], "overall": 8.0},
            images=[("image-1.png", PNG)],
        )
        return row.id


def _use(client, provider):
    client.app.dependency_overrides[get_analyzer_provider] = lambda: provider


@respx.mock
def test_prepare_to_sell_returns_everything(client, analysis_id):
    respx.get(ECB_URL).mock(return_value=httpx.Response(200, text=XML))
    _use(client, FakeProvider([COPY]))

    response = client.post(f"/api/analyses/{analysis_id}/sale")

    assert response.status_code == 201
    sale = response.json()
    assert sale["titles"]["en"] == "Frieren Bust STL"
    assert sale["tags"] == ["frieren", "bust"]
    assert len(sale["stores"]) == 3 and "Cults3D" in sale["stores"]
    assert sale["price"]["basis"] == "faixa_categoria"
    assert sale["price"]["eur"] == pytest.approx(round(6.9 * 1.18 / 1.1403, 2))
    assert sale["price"]["fx_source"] == "cotação do Banco Central Europeu de 2026-09-25"
    assert sale["chance"] is None and sale["chance_note"] == "Tema ainda sem dados no radar"
    assert sale["languages"] == ["de", "ja"]
    detail = client.get(f"/api/analyses/{analysis_id}").json()
    assert detail["sale"] == sale


@respx.mock
def test_generating_again_overwrites(client, analysis_id):
    respx.get(ECB_URL).mock(return_value=httpx.Response(200, text=XML))
    _use(client, FakeProvider([COPY, {**COPY, "titles": {"en": "Frieren Bust v2"}}]))

    client.post(f"/api/analyses/{analysis_id}/sale")
    second = client.post(f"/api/analyses/{analysis_id}/sale").json()

    assert second["titles"]["en"] == "Frieren Bust v2"
    assert client.get(f"/api/analyses/{analysis_id}").json()["sale"]["titles"]["en"] == "Frieren Bust v2"


def test_analysis_without_sale_has_null(client, analysis_id):
    assert client.get(f"/api/analyses/{analysis_id}").json()["sale"] is None


def test_unknown_analysis_404(client):
    _use(client, FakeProvider([]))

    response = client.post("/api/analyses/999/sale")

    assert response.status_code == 404
    assert response.json()["detail"] == "Análise não encontrada"


def test_without_gemini_key_409(client, analysis_id):
    _use(client, None)

    assert client.post(f"/api/analyses/{analysis_id}/sale").status_code == 409


def test_quota_429(client, analysis_id):
    _use(client, FakeProvider([AIQuotaError("x")]))

    response = client.post(f"/api/analyses/{analysis_id}/sale")

    assert response.status_code == 429
    assert response.json()["detail"] == "A cota grátis da IA acabou por hoje. Tente de novo mais tarde."


def test_invalid_answer_424(client, analysis_id):
    _use(client, FakeProvider([{}, {}]))

    assert client.post(f"/api/analyses/{analysis_id}/sale").status_code == 424
