import json

from app import clock
from app.models import RawItem
from app.sale.fanart import INSPIRED_TIP, UNKNOWN, fanart_for_store, inspired_tip
from app.sale.variations import default_variations, evidence, types_for, validate_variations


def _item(title, tags=()):
    return RawItem(source="cults3d", external_id=title, country="BR", day=clock.today(), title=title,
                   tags_json=json.dumps(list(tags)), metric=1)


ITEMS = [_item("Frieren bust presupported"), _item("Frieren chibi", ["Pre-Supported"]), _item("Frieren statue"),
         _item("Frieren bust split", ["bundle"]), _item("Fern figure")]


def test_types_by_market():
    assert "presuportada" in types_for("print") and "lowpoly" not in types_for("print")
    assert "lowpoly" in types_for("digital") and "presuportada" not in types_for("digital")


def test_evidence_counts_offers():
    proof = evidence(ITEMS, "print")
    assert proof["presuportada"] == {"count": 2, "total": 5, "scope": "tema"}
    assert proof["busto"]["count"] == 2
    assert proof["chibi"]["count"] == 1
    assert proof["partes"]["count"] == 1
    assert "lowpoly" not in proof
    assert evidence(ITEMS[:4], "print") == {}


def test_validate_variations():
    proof = evidence(ITEMS, "print")
    raw = [{"type": "presuportada", "why": "Metade dos anúncios já vem suportada."},
           {"type": "presuportada", "why": "repetido"},
           {"type": "lowpoly", "why": "outro mercado"},
           {"type": "inventado", "why": "x"},
           {"type": "busto", "why": ""},
           {"type": "chibi", "why": "Um chibi perfeito vende bem."}, "lixo"]
    result = validate_variations(raw, market="print", proof=proof)
    assert [v["type"] for v in result] == ["presuportada", "chibi"]
    assert result[0]["label"] == "Versão pré-suportada"
    assert result[0]["evidence"] == "2 de 5 anúncios do tema oferecem"
    assert result[1]["flagged"] is True


def test_default_variations_use_evidence_then_defaults():
    proof = evidence(ITEMS, "print")
    result = default_variations(market="print", proof=proof)
    assert [v["type"] for v in result][:2] == ["presuportada", "busto"]
    assert result[0]["why"] == "2 de 5 anúncios do tema oferecem"
    empty = default_variations(market="digital", proof={})
    assert [v["type"] for v in empty] == ["busto", "chibi", "pose"]
    assert empty[0]["why"] == "sugestão padrão para assets digitais"
    assert empty[0]["evidence"] is None


def test_fanart_policies():
    assert fanart_for_store("myminifactory")["level"] == "alto"
    assert fanart_for_store("etsy")["label"] == "risco médio"
    assert fanart_for_store("etsy")["url"].startswith("https://www.etsy.com/")
    unknown = fanart_for_store("printables")
    assert unknown == {"level": None, "label": "risco não confirmado", "summary": UNKNOWN, "url": None}


def test_inspired_tip_only_with_high_risk():
    assert inspired_tip([{"fanart": fanart_for_store("etsy")}]) is None
    assert inspired_tip([{"fanart": fanart_for_store("etsy")}, {"fanart": fanart_for_store("fab")}]) == INSPIRED_TIP
    assert inspired_tip([{"fanart": None}]) is None


def test_evidence_scope_wording_for_similar_listings():
    proof = evidence(ITEMS, "print", "parecidos")
    result = default_variations(market="print", proof=proof)
    assert result[0]["why"] == "2 de 5 anúncios parecidos oferecem"
