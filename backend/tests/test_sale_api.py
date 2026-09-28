from datetime import timedelta

import pytest
from sqlmodel import Session

from app import clock
from app.ai.provider import AIQuotaError
from app.api.analyze import get_analyzer_provider
from app.models import Analysis, FxRate
from app.sale.build import NOTE_INVALID, NOTE_NO_KEY, NOTE_NO_STORES, NOTE_QUOTA
from tests.sale_helpers import add_analysis, clear_platforms, add_items, add_platform, add_score, add_topic

LISTING = {"listings": [
    {"platform": "cults3d", "lang": "en", "title": "Frieren Bust STL", "tags": ["frieren", "bust"],
     "description": "Bust of Frieren, split for printing."},
    {"platform": "cults3d", "lang": "pt", "title": "Busto Frieren STL", "tags": ["frieren"],
     "description": "Busto da Frieren."},
]}


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_json_with_images(self, prompt, images):
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _use(client, provider):
    client.app.dependency_overrides[get_analyzer_provider] = lambda: provider
    return provider


@pytest.fixture()
def world(client, engine):
    """Frieren no radar, com preços no Cults3D e duas lojas de impressão."""
    with Session(engine) as session:
        clear_platforms(session)
        add_platform(session, "cults3d", strength={"BR": 0.8, "US": 0.8}, fee_pct=20)
        add_platform(session, "etsy", strength={"BR": 0.3, "US": 0.9}, categories=["decoracao"])
        add_platform(session, "fab", markets=["digital"], strength={"BR": 0.9, "US": 0.9})
        topic = add_topic(session, "Frieren", aliases=["sousou no frieren"])
        add_score(session, topic, country="BR", platform="cults3d", opportunity=80,
                  peak_day=clock.today() + timedelta(days=10))
        add_score(session, topic, country="US", platform="etsy", opportunity=70)
        add_items(session, topic, "cults3d", [4, 5, 6, 7, 8], tags=["Frieren", "anime bust"])
        session.add(FxRate(day=clock.today() - timedelta(days=2), currency="BRL", rate=5.43))
        session.commit()
        analysis = add_analysis(session, overall=6.0, hours=10)
        return analysis.id


def test_full_sale(client, world):
    provider = _use(client, FakeProvider([LISTING]))
    response = client.post(f"/api/analyses/{world}/sale", json={"countries": ["BR", "US"]})
    assert response.status_code == 200
    sale = response.json()
    assert sale["estimate"] is True
    assert sale["topic"]["name"] == "Frieren"
    br = sale["by_country"][0]
    assert br["country"] == "BR"
    assert [s["platform"] for s in br["stores"]] == ["cults3d", "etsy"]
    cults = br["stores"][0]
    # mediana 6 × (0,7 + 0,06·6 = 1,06) = 6,36 → 5,99; líquido com 20% de taxa
    assert cults["price"]["suggested"] == 5.99
    assert cults["price"]["net"] == 4.79
    assert cults["price"]["basis"] == "mediana de 5 anúncios de Frieren no Cults3d"
    assert cults["chance"] == {"value": 64, "label": "Média", "why": "oportunidade 80 no Cults3d (Brasil) × qualidade 6,0"}
    etsy = br["stores"][1]
    # sem anúncios no Etsy: usa os de Frieren em todas as lojas (camada 2); sem taxa conhecida
    assert etsy["price"]["basis"] == "mediana de 5 anúncios de Frieren em todas as lojas"
    assert etsy["price"]["net"] is None
    assert etsy["price_note"] is None
    assert sale["hours_to_cover"] == {"sales": 21, "hours": 10.0, "hourly_rate_usd": 10, "price": 4.79}
    assert [(l["platform"], l["lang"]) for l in sale["listing"]["listings"]] == [("cults3d", "en"), ("cults3d", "pt")]
    assert sale["listing"]["listings"][0]["title"] == "Frieren Bust STL (fan art)"
    assert sale["listing_note"] is None
    assert sale["checklist"][0] == "Publique primeiro no Cults3d (melhor encaixe no Brasil)."
    assert "US$ 4,99" in sale["checklist"][1] and "US$ 5,99" in sale["checklist"][1]
    assert sale["checklist"][2] == "Em até 2 dias, publique também no Etsy."
    # sem posts do tema no Reddit: comunidades do tipo de modelo (anime + impressão)
    assert sale["checklist"][3] == ("Divulgue em r/anime e r/3Dprinting no dia da publicação "
                                    "(leia as regras de autopromoção).")
    assert "publique antes disso" in sale["checklist"][4]
    assert sale["peak_day"] == (clock.today() + timedelta(days=10)).isoformat()
    assert br["fx"] == {"currency": "BRL", "rate": 5.43, "day": (clock.today() - timedelta(days=2)).isoformat()}
    assert sale["by_country"][1]["fx"] is None  # EUA: já é dólar
    assert [c["name"] for c in sale["promotion"]["communities"]] == ["r/anime", "r/3Dprinting", "r/PrintedMinis"]
    assert sale["promotion"]["hashtags"][:3] == ["#frieren", "#animebust", "#sousounofrieren"]
    assert "autopromoção" in sale["promotion"]["note"]
    assert "frieren" in provider.prompts[0] and "anime bust" in provider.prompts[0]

    saved = client.get(f"/api/analyses/{world}").json()
    assert saved["sale"] == sale


def test_regenerating_overwrites(client, world):
    _use(client, FakeProvider([LISTING, LISTING]))
    client.post(f"/api/analyses/{world}/sale", json={"countries": ["BR"]})
    second = client.post(f"/api/analyses/{world}/sale", json={"countries": ["US"]}).json()
    assert client.get(f"/api/analyses/{world}").json()["sale"]["countries"] == second["countries"] == ["US"]


def test_empty_body_uses_default_countries(client, world):
    _use(client, None)
    response = client.post(f"/api/analyses/{world}/sale")
    assert response.status_code == 200
    assert response.json()["countries"] == ["BR", "US", "GB"]


@pytest.mark.parametrize("provider, note", [
    (None, NOTE_NO_KEY),
    (FakeProvider([AIQuotaError("429")]), NOTE_QUOTA),
    (FakeProvider([ValueError("json"), ValueError("json")]), NOTE_INVALID),
    (FakeProvider([RuntimeError("503")]), "A IA não respondeu agora. Lojas, preço e chance estão prontos; "
                                         "tente o anúncio de novo mais tarde."),
])
def test_ai_failure_still_returns_sale(client, world, provider, note):
    _use(client, provider)
    response = client.post(f"/api/analyses/{world}/sale", json={"countries": ["BR"]})
    assert response.status_code == 200
    sale = response.json()
    assert sale["listing"] is None
    assert sale["listing_note"] == note
    assert sale["by_country"][0]["stores"][0]["price"]["suggested"] == 5.99


def test_listing_with_no_valid_items_counts_as_invalid(client, world):
    _use(client, FakeProvider([{"listings": [{"platform": "booth", "lang": "ja", "title": "x"}]}]))
    sale = client.post(f"/api/analyses/{world}/sale", json={"countries": ["BR"]}).json()
    assert sale["listing"] is None
    assert sale["listing_note"] == NOTE_INVALID


def test_no_store_for_market(client, engine):
    with Session(engine) as session:
        clear_platforms(session)
        add_platform(session, "cults3d", markets=["print"], strength={"BR": 0.8})
        analysis_id = add_analysis(session, market="digital").id
    _use(client, FakeProvider([]))
    sale = client.post(f"/api/analyses/{analysis_id}/sale", json={"countries": ["BR"]}).json()
    assert sale["by_country"] == [{"country": "BR", "fx": None, "stores": []}]
    assert sale["listing_note"] == NOTE_NO_STORES
    assert sale["checklist"] == [NOTE_NO_STORES]
    assert sale["hours_to_cover"] is None


def test_analysis_without_topic(client, engine):
    with Session(engine) as session:
        clear_platforms(session)
        add_platform(session, "cults3d", strength={"BR": 0.8})
        analysis_id = add_analysis(session, theme="Dragão", character=None, search_query="dragon").id
    _use(client, None)
    sale = client.post(f"/api/analyses/{analysis_id}/sale", json={"countries": ["BR"]}).json()
    assert sale["topic"] is None
    store = sale["by_country"][0]["stores"][0]
    assert store["chance"]["value"] is None
    assert store["price"] is None
    assert sale["checklist"][0].startswith("Publique primeiro no Cults3d")
    assert sale["checklist"][1].startswith("Divulgue em r/anime")
    assert len(sale["checklist"]) == 2


@pytest.mark.parametrize("countries, message", [
    (["BR", "US", "GB", "DE", "FR", "JP"], "Escolha de 1 a 5 países"),
    (["XX"], "País inválido"),
])
def test_invalid_countries(client, world, countries, message):
    _use(client, None)
    response = client.post(f"/api/analyses/{world}/sale", json={"countries": countries})
    assert response.status_code == 422
    assert response.json()["detail"] == message


def test_duplicate_countries_are_merged(client, world):
    _use(client, None)
    sale = client.post(f"/api/analyses/{world}/sale", json={"countries": ["BR", "BR"]}).json()
    assert sale["countries"] == ["BR"]


def test_unknown_analysis(client):
    _use(client, None)
    assert client.post("/api/analyses/999/sale", json={}).status_code == 404
    assert client.get("/api/analyses/999/sale/countries").status_code == 404


def test_analysis_without_sale_has_null(client, world):
    assert client.get(f"/api/analyses/{world}").json()["sale"] is None


def test_sale_countries(client, world):
    body = client.get(f"/api/analyses/{world}/sale/countries").json()
    assert body["max"] == 5
    assert body["defaults"] == ["BR", "US", "GB"]
    assert [c["code"] for c in body["countries"]][:4] == ["BR", "US", "GB", "DE"]
    assert body["countries"][0] == {"code": "BR", "name": "Brasil"}
