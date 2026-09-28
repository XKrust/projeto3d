from app.sale.listing import (FAN_ART, build_prompt, generate_listing, languages_for, top_tags,
                              trim_words)
from app.sale.validate import validate_listings


def test_languages_per_store():
    by_country = {"BR": ["cults3d", "etsy"], "US": ["etsy", "fab"], "JP": ["booth", "cults3d"]}
    pairs = languages_for(by_country)
    assert pairs == [("booth", "en"), ("booth", "ja"), ("cults3d", "en"), ("cults3d", "pt"), ("cults3d", "ja"),
                     ("etsy", "en"), ("etsy", "pt"), ("fab", "en")]


def test_booth_always_gets_japanese():
    assert languages_for({"US": ["booth"]}) == [("booth", "en"), ("booth", "ja")]


def test_top_tags_prefers_most_liked_and_frequent():
    items = [(["Frieren", "#anime", "bust"], 100), (["frieren", "elf"], 50), (["other"], 0)]
    assert top_tags(items, aliases=["Sousou no Frieren"], limit=4) == ["frieren", "anime", "bust", "elf"]


def test_prompt_mentions_everything():
    prompt = build_prompt(identified={"theme": "Busto Frieren", "character": "Frieren", "style": "anime",
                                      "category": "anime"}, market="print", authorship="fanart",
                          strengths=["mechas do cabelo"], tags=["frieren", "bust"],
                          pairs=[("cults3d", "en"), ("cults3d", "pt")])
    for text in ("Busto Frieren", "fan art", "mechas do cabelo", "frieren, bust", '"cults3d" em en', '"cults3d" em pt'):
        assert text in prompt


def test_trim_words():
    assert trim_words("abc def ghi", 9) == ("abc def", True)
    assert trim_words("abc def", 20) == ("abc def", False)
    assert trim_words("abcdefghij", 5) == ("abcde", True)
    assert trim_words("フリーレンのフィギュア", 5) == ("フリーレン", True)


PAIRS = {("etsy", "en"), ("cults3d", "pt")}


def _listing(**overrides):
    item = {"platform": "cults3d", "lang": "pt", "title": "Busto Frieren para impressão 3D",
            "tags": ["frieren", "anime"], "description": "Busto com mechas separadas."}
    item.update(overrides)
    return item


def test_unrequested_pairs_and_empty_titles_are_dropped():
    raw = {"listings": [_listing(), _listing(platform="booth"), _listing(lang="ja"), _listing(title=" "),
                        "lixo"]}
    result = validate_listings(raw, PAIRS, authorship="autoral")
    assert [(r["platform"], r["lang"]) for r in result] == [("cults3d", "pt")]


def test_duplicate_pair_keeps_first():
    raw = {"listings": [_listing(), _listing(title="Outro título")]}
    assert validate_listings(raw, PAIRS, authorship="autoral")[0]["title"] == "Busto Frieren para impressão 3D"


def test_tags_are_normalized():
    raw = {"listings": [_listing(tags=["#Frieren", "frieren", " ", "Anime Bust", 3])]}
    result = validate_listings(raw, PAIRS, authorship="autoral")[0]
    assert result["tags"] == ["frieren", "anime bust"]
    assert result["trimmed"] is False


def test_etsy_limits():
    long_title = "Frieren bust " * 20
    tags = [f"tag number {n}" for n in range(20)] + ["a very long tag with many words"]
    raw = {"listings": [_listing(platform="etsy", lang="en", title=long_title, tags=["frieren_3d!", *tags])]}
    result = validate_listings(raw, PAIRS, authorship="autoral")[0]
    assert len(result["title"]) <= 140
    assert not result["title"].endswith(" ")
    assert len(result["tags"]) == 13
    assert all(len(tag) <= 20 for tag in result["tags"])
    assert result["tags"][0] == "frieren3d"
    assert result["trimmed"] is True


def test_default_limits_for_other_stores():
    raw = {"listings": [_listing(title="x " * 80, tags=[f"t{n}" for n in range(20)])]}
    result = validate_listings(raw, PAIRS, authorship="autoral")[0]
    assert len(result["title"]) <= 100
    assert len(result["tags"]) == 15


def test_fan_art_marker_added_when_missing():
    raw = {"listings": [_listing(), _listing(platform="etsy", lang="en", title="Frieren Fan Art Bust")]}
    result = validate_listings(raw, PAIRS, authorship="fanart")
    assert result[0]["title"] == f"Busto Frieren para impressão 3D ({FAN_ART['pt']})"
    assert result[1]["title"] == "Frieren Fan Art Bust"


def test_fan_art_marker_fits_in_limit():
    raw = {"listings": [_listing(platform="etsy", lang="en", title="word " * 40)]}
    title = validate_listings(raw, PAIRS, authorship="fanart")[0]["title"]
    assert len(title) <= 140
    assert title.endswith("(fan art)")


def test_flattery_is_flagged():
    raw = {"listings": [_listing(description="Um busto incrível e perfeito.")]}
    assert validate_listings(raw, PAIRS, authorship="autoral")[0]["flagged"] is True


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_json_with_images(self, prompt, images):
        self.prompts.append(prompt)
        assert images == []
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_generate_listing_retries_invalid_json():
    provider = FakeProvider([ValueError("json"), {"listings": [_listing()]}])
    result, variations = generate_listing(provider, identified={"theme": "Busto", "character": None, "style": "",
                                                    "category": "anime"},
                              market="print", authorship="autoral", strengths=[], tags=[], pairs=[("cults3d", "pt")])
    assert result[0]["title"] == "Busto Frieren para impressão 3D"
    assert variations is None
    assert len(provider.prompts) == 2
    assert '"presuportada"' in provider.prompts[0]
