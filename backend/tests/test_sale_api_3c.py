import json

import httpx
import pytest
import respx
from sqlmodel import Session, select

from app.ai.provider import AIQuotaError
from app.analyzer import store
from app.api.analyze import get_analyzer_provider
from app.models import Analysis, RawItem
from app.sale.build import COVER_NO_IMAGE, COVER_NO_KEY, COVER_QUOTA
from app.sale.cover import CHECKS
from app.sale.fanart import INSPIRED_TIP
from tests.sale_helpers import add_analysis, add_items, add_platform, add_score, add_topic, clear_platforms

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
LISTING = {"listings": [{"platform": "cults3d", "lang": "pt", "title": "Busto Frieren", "tags": ["frieren"],
                         "description": "Busto."}],
           "variations": [{"type": "presuportada", "why": "Os mais vendidos já vêm suportados."},
                          {"type": "lowpoly", "why": "não é de impressão"}]}
COVER = {"checks": {slug: {"ok": slug != "fundo", "why": "visto", "fix": "Use fundo liso" if slug == "fundo" else ""}
                    for slug in CHECKS},
         "vs_top": [{"reference": 1, "text": "fundo gradiente escuro"}]}


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.images = []

    def generate_json_with_images(self, prompt, images):
        self.images.append(len(images))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    return tmp_path


def _world(engine, tmp_path, *, authorship="fanart", with_image=True):
    with Session(engine) as session:
        clear_platforms(session)
        add_platform(session, "cults3d", strength={"BR": 0.8})
        add_platform(session, "etsy", strength={"BR": 0.5}, markets=["print", "digital"])
        add_platform(session, "printables", strength={"BR": 0.4})
        topic = add_topic(session, "Frieren")
        add_score(session, topic, opportunity=70)
        add_items(session, topic, "cults3d", [4, 5, 6, 7, 8], tags=["presupported"])
        for n, item in enumerate(session.exec(select(RawItem)).all()):
            item.thumb_url = f"https://img.test/{n}.jpg"
            item.likes = n
            session.add(item)
        analysis = add_analysis(session, authorship=authorship)
        if with_image:
            folder = tmp_path / "analyses" / str(analysis.id)
            folder.mkdir(parents=True)
            (folder / "image-1.png").write_bytes(PNG)
            row = session.get(Analysis, analysis.id)
            row.files_json = json.dumps(["image-1.png"])
            session.add(row)
        session.commit()
        return analysis.id


def _use(client, provider):
    client.app.dependency_overrides[get_analyzer_provider] = lambda: provider
    return provider


@respx.mock
def test_cover_variations_and_fanart(client, engine, tmp_path):
    respx.get(url__startswith="https://img.test/").mock(
        return_value=httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"}))
    analysis_id = _world(engine, tmp_path)
    provider = _use(client, FakeProvider([LISTING, COVER]))
    sale = client.post(f"/api/analyses/{analysis_id}/sale", json={"countries": ["BR"]}).json()

    assert provider.images == [0, 4]  # anúncio só texto; capa = imagem do usuário + 3 capas
    cover = sale["cover"]
    assert cover["score"] == 8.3  # 5 de 6 itens ok
    assert cover["checks"]["fundo"]["fix"] == "Use fundo liso"
    assert [r["likes"] for r in cover["references"]] == [4, 3, 2]
    assert cover["vs_top"][0]["text"] == "fundo gradiente escuro"
    assert sale["cover_note"] is None

    assert [v["type"] for v in sale["variations"]] == ["presuportada"]
    assert sale["variations"][0]["evidence"] == "5 de 5 anúncios do tema oferecem"

    stores = {s["platform"]: s for s in sale["by_country"][0]["stores"]}
    assert stores["cults3d"]["fanart"]["level"] == "alto"
    assert stores["etsy"]["fanart"]["level"] == "medio"
    assert stores["printables"]["fanart"]["level"] is None
    assert sale["fanart_tip"] == INSPIRED_TIP


def test_autoral_has_no_fanart(client, engine, tmp_path):
    analysis_id = _world(engine, tmp_path, authorship="autoral", with_image=False)
    _use(client, None)
    sale = client.post(f"/api/analyses/{analysis_id}/sale", json={"countries": ["BR"]}).json()
    assert all(s["fanart"] is None for s in sale["by_country"][0]["stores"])
    assert sale["fanart_tip"] is None


def test_without_key_uses_default_variations(client, engine, tmp_path):
    analysis_id = _world(engine, tmp_path)
    _use(client, None)
    sale = client.post(f"/api/analyses/{analysis_id}/sale", json={"countries": ["BR"]}).json()
    assert sale["cover"] is None
    assert sale["cover_note"] == COVER_NO_KEY
    assert sale["variations"][0] == {"type": "presuportada", "label": "Versão pré-suportada",
                                     "why": "5 de 5 anúncios do tema oferecem",
                                     "evidence": "5 de 5 anúncios do tema oferecem", "flagged": False, "source": "padrao"}


def test_quota_on_listing_skips_cover(client, engine, tmp_path):
    analysis_id = _world(engine, tmp_path)
    provider = _use(client, FakeProvider([AIQuotaError("429")]))
    sale = client.post(f"/api/analyses/{analysis_id}/sale", json={"countries": ["BR"]}).json()
    assert provider.images == [0]
    assert sale["cover_note"] == COVER_QUOTA


def test_missing_image(client, engine, tmp_path):
    analysis_id = _world(engine, tmp_path, with_image=False)
    _use(client, FakeProvider([LISTING]))
    sale = client.post(f"/api/analyses/{analysis_id}/sale", json={"countries": ["BR"]}).json()
    assert sale["cover_note"] == COVER_NO_IMAGE
    assert sale["listing"] is not None


def test_bad_key_on_listing_skips_cover(client, engine, tmp_path):
    from app.ai.provider import AIKeyError
    from app.sale.build import NOTE_BAD_KEY

    analysis_id = _world(engine, tmp_path)
    provider = _use(client, FakeProvider([AIKeyError("bad")]))
    sale = client.post(f"/api/analyses/{analysis_id}/sale", json={"countries": ["BR"]}).json()
    assert provider.images == [0]
    assert sale["listing_note"] == NOTE_BAD_KEY
    assert sale["cover_note"] == NOTE_BAD_KEY
