import json
from pathlib import Path

import httpx
import pytest
import respx

from app.ai.provider import AIQuotaError
from app.analyzer import store
from app.analyzer.validate import CRITERIA
from app.api.analyze import get_analyzer_provider

FIXTURES = Path(__file__).parent / "fixtures" / "sketchfab"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 16
IDENTIFIED = {"theme": "Busto Frieren", "category": "anime", "style": "anime", "character": "Frieren",
              "search_query": "frieren bust"}
CRITIQUE = {
    "criteria": {slug: {"score": 6, "why": "ok"} for slug in CRITERIA},
    "strengths": [{"text": "cabelo com mechas separadas", "image": 1, "area": "cabelo"}],
    "improvements": [{"image": 2, "area": "mão esquerda", "problem": "dedos iguais", "fix": "Move",
                      "gain": "natural", "confidence": "alta", "criterion": "anatomia"}],
    "reference_comparison": [{"reference": 1, "text": "mechas em 3 níveis"}],
    "top_actions": ["corrigir mão"],
}


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json_with_images(self, prompt, images):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    return tmp_path


def _use(client, provider):
    client.app.dependency_overrides[get_analyzer_provider] = lambda: provider
    return provider


def _mock_sketchfab(status=200):
    search = json.loads((FIXTURES / "analyzer_search_all.json").read_text(encoding="utf-8"))
    respx.get("https://api.sketchfab.com/v3/search").mock(return_value=httpx.Response(status, json=search))
    if status != 200:
        return
    respx.get(url__startswith="https://media.sketchfab.com/").mock(
        return_value=httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
    )


def _post(client, images=None, **data):
    images = [PNG, PNG] if images is None else images
    files = [("images", (f"img{i}.png", content, "image/png")) for i, content in enumerate(images)]
    form = {"authorship": "fanart", "market": "print", "hours": "12"}
    form.update(data)
    return client.post("/api/analyze", data=form, files=files)


@respx.mock
def test_valid_submission_returns_full_analysis(client, _data_dir):
    provider = _use(client, FakeProvider([IDENTIFIED, CRITIQUE]))
    _mock_sketchfab()

    response = _post(client)

    assert response.status_code == 201
    body = response.json()
    assert body["result"]["overall"] == 6.0
    assert body["identified"]["theme"] == "Busto Frieren"
    assert len(body["references"]) == 3
    assert body["input"]["images"] == ["image-1.png", "image-2.png"]
    assert (_data_dir / "analyses" / str(body["id"]) / "image-2.png").exists()
    assert provider.calls == 2


@pytest.mark.parametrize("count", [0, 5])
def test_image_count_must_be_1_to_4(client, count):
    provider = _use(client, FakeProvider([]))

    response = _post(client, images=[PNG] * count)

    assert response.status_code == 422
    assert response.json()["detail"] == "Envie de 1 a 4 imagens"
    assert provider.calls == 0


def test_image_over_10mb_is_refused(client):
    _use(client, FakeProvider([]))

    response = _post(client, images=[PNG + b"\x00" * (10 * 1024 * 1024)])

    assert response.status_code == 422
    assert response.json()["detail"] == "Imagem maior que 10 MB"


def test_fake_jpg_is_refused_before_spending_quota(client):
    provider = _use(client, FakeProvider([]))
    files = [("images", ("foto.jpg", b"hello, not an image", "image/jpeg"))]

    response = client.post("/api/analyze", data={"authorship": "autoral", "market": "print"}, files=files)

    assert response.status_code == 422
    assert response.json()["detail"] == "Formato não aceito: use JPG, PNG ou WEBP"
    assert provider.calls == 0


def test_webp_and_jpeg_are_accepted_formats(client):
    _use(client, FakeProvider([AIQuotaError("x")]))

    response = _post(client, images=[WEBP, JPEG])

    assert response.status_code == 429  # passou da validação e chegou na IA


def test_invalid_reference_link_is_refused(client):
    _use(client, FakeProvider([]))

    response = _post(client, reference_urls="https://sketchfab.com/usuario")

    assert response.status_code == 422
    assert response.json()["detail"] == "Link de referência inválido: use um link de modelo do Sketchfab"


@pytest.mark.parametrize("field", ["authorship", "market"])
def test_invalid_choices_are_refused(client, field):
    _use(client, FakeProvider([]))

    assert _post(client, **{field: "x"}).status_code == 422


def test_without_gemini_key_explains_what_to_do(client):
    _use(client, None)

    response = _post(client)

    assert response.status_code == 409
    assert response.json()["detail"] == "Configure a chave do Gemini em Configurações para analisar modelos"


def test_quota_exhausted(client):
    _use(client, FakeProvider([AIQuotaError("cota")]))

    response = _post(client)

    assert response.status_code == 429
    assert response.json()["detail"] == "A cota grátis da IA acabou por hoje. Tente de novo mais tarde."


def test_invalid_ai_answer_twice(client):
    _use(client, FakeProvider([{}, {}]))

    response = _post(client)

    assert response.status_code == 424
    assert response.json()["detail"] == "A IA devolveu uma resposta inválida. Tente de novo."


@respx.mock
def test_sketchfab_down_still_analyzes(client):
    _use(client, FakeProvider([IDENTIFIED, CRITIQUE]))
    _mock_sketchfab(status=500)

    response = _post(client)

    assert response.status_code == 201
    assert response.json()["references"] == []
    assert response.json()["references_note"] == "Sem referências desta vez: comparado ao padrão profissional do tema."


@respx.mock
def test_history_detail_images_and_not_found(client):
    _use(client, FakeProvider([IDENTIFIED, CRITIQUE]))
    _mock_sketchfab()
    created = _post(client).json()

    listed = client.get("/api/analyses").json()
    detail = client.get(f"/api/analyses/{created['id']}")
    image = client.get(f"/api/analyses/{created['id']}/images/image-1.png")

    assert [a["id"] for a in listed] == [created["id"]]
    assert detail.status_code == 200 and detail.json()["id"] == created["id"]
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert client.get("/api/analyses/999").json()["detail"] == "Análise não encontrada"
    assert client.get("/api/analyses/999").status_code == 404
    assert client.get(f"/api/analyses/{created['id']}/images/..%2Fradar.db").status_code == 404


@respx.mock
def test_wireframe_is_saved_and_counts_for_topology(client):
    _use(client, FakeProvider([IDENTIFIED, CRITIQUE]))
    _mock_sketchfab()

    files = [("images", ("a.png", PNG, "image/png")), ("wireframe", ("w.png", PNG, "image/png"))]
    body = client.post("/api/analyze", data={"authorship": "autoral", "market": "digital"}, files=files).json()

    assert body["input"]["wireframe"] == "wireframe.png"
    assert body["result"]["criteria"]["topologia"]["score"] == 6
    assert body["result"]["criteria"]["imprimibilidade"]["score"] is None  # digital
