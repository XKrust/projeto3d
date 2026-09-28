from datetime import date

import pytest

from app.analyzer.errors import AIInvalidResponse
from app.constants import GLOBAL
from app.models import RawItem
from app.sale.copy import popular_titles, write_copy

DAY = date(2026, 9, 28)


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate_json(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)


def _analysis(authorship="fanart", printability=None):
    return {
        "input": {"authorship": authorship, "market": "print"},
        "identified": {"theme": "Busto da Frieren", "category": "anime", "style": "anime", "character": "Frieren",
                       "search_query": "frieren bust"},
        "result": {
            "criteria": {"imprimibilidade": {"score": printability, "why": ""}, "detalhe": {"score": 7, "why": ""}},
            "strengths": [{"text": "cabelo em camadas", "area": "cabelo", "image": 1, "flagged": False}],
        },
    }


GOOD = {
    "titles": {"en": "Frieren Bust - Anime Fan Art STL", "pt": "Busto da Frieren", "de": "Frieren Büste",
               "ja": "フリーレン 胸像"},
    "tags": ["Frieren", "anime", "bust", "anime", "fan art"],
    "description": "Bust of Frieren with layered hair.",
}


def test_prompt_carries_languages_examples_and_honesty_rules():
    provider = FakeProvider([GOOD])

    write_copy(provider, analysis=_analysis(), languages=["de", "ja"], examples=["Fern - Frieren bust STL"])

    prompt = provider.prompts[0]
    assert '"de"' in prompt and '"ja"' in prompt
    assert "Fern - Frieren bust STL" in prompt
    assert "fan art" in prompt
    assert "cabelo em camadas" in prompt
    # imprimibilidade não avaliada: não pode prometer que está pronto para imprimir
    assert "Não diga que está pronto para imprimir" in prompt


def test_printability_evaluated_does_not_forbid_the_claim():
    provider = FakeProvider([GOOD])

    write_copy(provider, analysis=_analysis(printability=8), languages=["de", "ja"], examples=[])

    assert "Não diga que está pronto para imprimir" not in provider.prompts[0]


def test_result_is_cleaned():
    long_title = "x" * 130
    provider = FakeProvider([{**GOOD, "titles": {**GOOD["titles"], "de": long_title},
                              "tags": [f"Tag {i}" for i in range(20)] + ["tag 1"]}])

    result = write_copy(provider, analysis=_analysis(), languages=["de", "ja"], examples=[])

    assert "de" not in result["titles"]
    assert result["titles"]["en"] == "Frieren Bust - Anime Fan Art STL"
    assert len(result["tags"]) == 15
    assert result["tags"][0] == "tag 0"
    assert len(set(result["tags"])) == 15


def test_missing_english_title_twice_is_invalid():
    with pytest.raises(AIInvalidResponse):
        write_copy(FakeProvider([{"titles": {"pt": "x"}}, {}]), analysis=_analysis(), languages=["de"], examples=[])


def test_popular_titles_match_query_most_liked_first(session):
    for i, (title, metric) in enumerate([("Frieren bust", 5), ("Frieren bust v2", 50), ("Dragon", 99)]):
        session.add(RawItem(source="sketchfab", external_id=str(i), country=GLOBAL, day=DAY, title=title,
                            metric=metric))
    session.commit()

    assert popular_titles(session, DAY, "frieren bust") == ["Frieren bust v2", "Frieren bust"]
