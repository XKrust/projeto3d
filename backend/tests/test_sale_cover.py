import httpx
import respx

from app import clock
from app.http import make_client
from app.models import RawItem
from app.sale.cover import CHECKS, build_prompt, top_covers, validate_cover

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def _checks(**overrides):
    base = {slug: {"ok": True, "why": "ok", "fix": ""} for slug in CHECKS}
    base.update(overrides)
    return base


def test_score_is_computed_by_app():
    raw = {"checks": _checks(fundo={"ok": False, "why": "mesa ao fundo", "fix": "Use fundo liso"},
                             luz={"ok": None, "why": "escuro demais para ver"})}
    cover = validate_cover(raw, market="print", n_refs=0)
    # 4 ok de 5 avaliados
    assert cover["score"] == 8.0
    assert cover["checks"]["fundo"] == {"label": CHECKS["fundo"], "ok": False, "why": "mesa ao fundo",
                                        "fix": "Use fundo liso", "flagged": False}
    assert cover["checks"]["luz"]["ok"] is None


def test_false_without_fix_and_bad_values_become_null():
    raw = {"checks": _checks(fundo={"ok": False, "why": "x"}, luz={"ok": "sim", "why": "y"}, inventado={"ok": True})}
    cover = validate_cover(raw, market="print", n_refs=0)
    assert cover["checks"]["fundo"]["ok"] is None
    assert cover["checks"]["luz"]["ok"] is None
    assert "inventado" not in cover["checks"]


def test_scale_is_null_for_digital():
    cover = validate_cover({"checks": _checks()}, market="digital", n_refs=0)
    assert cover["checks"]["escala"]["ok"] is None
    assert cover["score"] == 10.0
    assert "escala" not in build_prompt(market="digital", n_refs=0)
    assert "escala" in build_prompt(market="print", n_refs=2)


def test_no_answers_means_no_score():
    cover = validate_cover({"checks": {}}, market="print", n_refs=0)
    assert cover["score"] is None


def test_comparisons_and_flattery():
    raw = {"checks": _checks(angulo={"ok": True, "why": "ângulo perfeito"}),
           "vs_top": [{"reference": 1, "text": "fundo gradiente"}, {"reference": 3, "text": "x"},
                      {"reference": 2, "text": " "}, {"reference": "1", "text": "y"}, {"reference": 2, "text": "escala com moeda"}]}
    cover = validate_cover(raw, market="print", n_refs=2)
    assert [c["text"] for c in cover["vs_top"]] == ["fundo gradiente", "escala com moeda"]
    assert cover["checks"]["angulo"]["flagged"] is True


@respx.mock
def test_top_covers_most_liked_that_download():
    respx.get("https://img/a.jpg").mock(return_value=httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"}))
    respx.get("https://img/b.jpg").mock(return_value=httpx.Response(404))
    respx.get("https://img/c.jpg").mock(return_value=httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"}))
    items = [RawItem(source="cults3d", external_id=n, country="BR", day=clock.today(), title=n, metric=1,
                     thumb_url=url, likes=likes, url=f"https://x/{n}")
             for n, url, likes in (("a", "https://img/a.jpg", 10), ("b", "https://img/b.jpg", 50),
                                   ("c", "https://img/c.jpg", 5), ("d", None, 99))]
    with make_client() as http:
        refs, images = top_covers(http, items)
    assert [r["title"] for r in refs] == ["a", "c"]
    assert len(images) == 2
