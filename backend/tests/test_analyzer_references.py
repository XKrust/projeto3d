import json
from pathlib import Path

import httpx
import respx

from app.analyzer.references import NO_REFERENCES_NOTE, find_references, parse_reference_url
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "sketchfab"
SEARCH = "https://api.sketchfab.com/v3/search"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
MODEL_URL = "https://sketchfab.com/3d-models/porsche-911-537f06116f1f40d7bc0de28a7ab653da"


def _json(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _mock_search_and_thumbs(thumb_status=200):
    respx.get(SEARCH, params__contains={"staffpicked": "true"}).mock(
        return_value=httpx.Response(200, json=_json("analyzer_search_staffpicked.json"))
    )
    respx.get(SEARCH).mock(return_value=httpx.Response(200, json=_json("analyzer_search_all.json")))
    respx.get(url__startswith="https://media.sketchfab.com/").mock(
        return_value=httpx.Response(thumb_status, content=JPEG, headers={"content-type": "image/jpeg"})
    )


def test_parse_reference_url_accepts_only_model_links():
    assert parse_reference_url(MODEL_URL) == "537f06116f1f40d7bc0de28a7ab653da"
    assert parse_reference_url("https://sketchfab.com/noorhassan99") is None
    assert parse_reference_url("https://example.com/3d-models/x-537f06116f1f40d7bc0de28a7ab653da") is None
    assert parse_reference_url("nada") is None


@respx.mock
def test_staff_picks_first_then_completes_with_most_liked_without_repeating():
    _mock_search_and_thumbs()

    with make_client() as http:
        refs, images, note = find_references(http, "skull", [])

    uids = [r["url"].rsplit("-", 1)[-1] for r in refs]
    assert uids == ["4f0078f665184cdc8b52e0b0c9539bac", "d6fd490f6ce344e7ac56be699f959618",
                    "9cfa16e77684424faa102aa779278e0d"]
    assert len(images) == 3 and images[0] == {"data": JPEG, "mime_type": "image/jpeg"}
    assert refs[0]["artist"] == "Noor Hassan"
    assert refs[0]["source"] == "auto"
    assert note is None
    first_search = respx.calls[0].request.url.params
    assert first_search["q"] == "skull" and first_search["sort_by"] == "-likeCount"


@respx.mock
def test_user_link_comes_first():
    model = respx.get("https://api.sketchfab.com/v3/models/537f06116f1f40d7bc0de28a7ab653da").mock(
        return_value=httpx.Response(200, json=_json("analyzer_model.json"))
    )
    _mock_search_and_thumbs()

    with make_client() as http:
        refs, images, _ = find_references(http, "skull", [MODEL_URL])

    assert model.called
    assert refs[0]["source"] == "usuario"
    assert refs[0]["name"].startswith("2000 Porsche")
    assert len(refs) == 3


@respx.mock
def test_sketchfab_down_gives_note_and_no_references():
    respx.get(SEARCH).mock(return_value=httpx.Response(500))

    with make_client() as http:
        refs, images, note = find_references(http, "skull", [])

    assert refs == [] and images == []
    assert note == NO_REFERENCES_NOTE == "Sem referências desta vez: comparado ao padrão profissional do tema."


@respx.mock
def test_reference_whose_thumbnail_fails_is_left_out():
    _mock_search_and_thumbs(thumb_status=404)

    with make_client() as http:
        refs, images, note = find_references(http, "skull", [])

    assert refs == [] and images == []
    assert note == NO_REFERENCES_NOTE
