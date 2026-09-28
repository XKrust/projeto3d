import pytest

from app.analyzer import store
from app.analyzer.store import analysis_to_dict, image_path, list_analyses, save_analysis

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
FORM = {"authorship": "fanart", "market": "print", "hours": 12.0}
RESULT = {"criteria": {}, "strengths": [], "improvements": [], "to_check": [], "reference_comparison": [],
          "top_actions": [], "overall": 6.2}


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    return tmp_path


def _save(session, theme="Busto Frieren", overall=6.2):
    return save_analysis(
        session,
        form=FORM,
        identified={"theme": theme, "category": "anime", "style": "anime", "character": "Frieren",
                    "search_query": "frieren bust"},
        references=[{"name": "Ref", "artist": "A", "url": "https://sketchfab.com/3d-models/x", "thumb_url": None,
                     "likes": 3, "source": "auto"}],
        references_note=None,
        result={**RESULT, "overall": overall},
        images=[("image-1.png", PNG), ("wireframe.png", PNG)],
    )


def test_save_writes_row_and_files(session, _data_dir):
    row = _save(session)

    assert row.id is not None
    assert row.overall == 6.2
    assert row.image_count == 1 and row.has_wireframe is True
    assert (_data_dir / "analyses" / str(row.id) / "image-1.png").read_bytes() == PNG
    body = analysis_to_dict(session, row)
    assert body["input"] == {**FORM, "images": ["image-1.png"], "wireframe": "wireframe.png"}
    assert body["identified"]["theme"] == "Busto Frieren"
    assert body["result"]["overall"] == 6.2
    assert body["previous"] is None


def test_previous_is_last_analysis_of_the_same_theme(session):
    first = _save(session, overall=5.8)
    _save(session, theme="Caveira")
    second = _save(session, theme="busto frieren", overall=6.9)

    assert analysis_to_dict(session, second)["previous"] == {"id": first.id, "overall": 5.8}


def test_image_path_refuses_other_files(session):
    row = _save(session)

    assert image_path(row.id, "image-1.png") is not None
    assert image_path(row.id, "../radar.db") is None
    assert image_path(row.id, "image-9.png") is None
    assert image_path(999, "image-1.png") is None


def test_list_is_newest_first_with_thumb(session):
    a = _save(session, theme="A")
    b = _save(session, theme="B")

    items = list_analyses(session)

    assert [i["id"] for i in items] == [b.id, a.id]
    assert items[0]["thumb"] == f"/api/analyses/{b.id}/images/image-1.png"
    assert items[0]["theme"] == "B" and items[0]["overall"] == 6.2
