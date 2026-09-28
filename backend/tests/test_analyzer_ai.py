import pytest

from app.analyzer.critique import critique
from app.analyzer.errors import AIInvalidResponse
from app.analyzer.identify import identify
from app.analyzer.validate import CRITERIA

USER = {"data": b"user", "mime_type": "image/png"}
REF = {"data": b"ref", "mime_type": "image/jpeg"}
IDENTIFIED = {"theme": "Busto Frieren", "category": "anime", "style": "anime", "character": "Frieren",
              "search_query": "frieren bust"}
VALID_CRITIQUE = {"criteria": {"anatomia": {"score": 6, "why": "x"}}, "strengths": [], "improvements": [],
                  "reference_comparison": [], "top_actions": []}


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, list]] = []

    def generate_json_with_images(self, prompt, images):
        self.calls.append((prompt, images))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_identify_normalizes_category_and_fills_query():
    provider = FakeProvider([{"theme": "Caveira decorativa", "category": "gótico", "style": "realista",
                              "character": None, "search_query": ""}])

    result = identify(provider, [USER])

    assert result == {"theme": "Caveira decorativa", "category": "outros", "style": "realista",
                      "character": None, "search_query": "Caveira decorativa"}
    assert provider.calls[0][1] == [USER]


def test_identify_retries_once_on_invalid_json():
    provider = FakeProvider([{}, {"theme": "Dragão", "category": "toys_memes", "style": "cartoon",
                                  "character": None, "search_query": "dragon"}])

    assert identify(provider, [USER])["theme"] == "Dragão"
    assert len(provider.calls) == 2


def test_identify_gives_up_after_two_invalid_answers():
    with pytest.raises(AIInvalidResponse):
        identify(FakeProvider([{}, {"foo": 1}]), [USER])


def test_critique_gives_up_after_two_invalid_answers():
    provider = FakeProvider([{"x": 1}, ValueError("json quebrado")])

    with pytest.raises(AIInvalidResponse):
        critique(provider, [USER], [REF], identified=IDENTIFIED, market="print", authorship="fanart",
                 has_wireframe=False)


def test_critique_prompt_carries_rubric_and_honesty_rules():
    provider = FakeProvider([VALID_CRITIQUE])

    result = critique(provider, [USER, USER], [REF], identified=IDENTIFIED, market="print", authorship="autoral",
                      has_wireframe=True)

    assert result == VALID_CRITIQUE
    prompt, images = provider.calls[0]
    for anchor in ("0–3", "4–6", "7–8", "9–10"):
        assert anchor in prompt
    for slug in CRITERIA:
        assert slug in prompt
    assert "não dá para avaliar" in prompt
    assert "confidence" in prompt
    assert "Não invente" in prompt
    assert "referência 1" in prompt
    assert "Busto Frieren" in prompt
    # imagens do usuário primeiro, depois as referências
    assert images == [USER, USER, REF]


def test_critique_without_references_compares_with_professional_standard():
    provider = FakeProvider([VALID_CRITIQUE])

    critique(provider, [USER], [], identified=IDENTIFIED, market="digital", authorship="autoral",
             has_wireframe=False)

    prompt = provider.calls[0][0]
    assert "padrão profissional" in prompt
    assert "referência 1" not in prompt
