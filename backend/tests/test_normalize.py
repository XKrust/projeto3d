from app.topics.normalize import is_cjk, matches_phrase, normalize, tokens


def test_normalize_strips_accents_lowercases_and_collapses_spaces():
    assert normalize("Pokémon  Fire") == "pokemon fire"


def test_normalize_keeps_cjk_intact():
    assert normalize("葬送のフリーレン") == "葬送のフリーレン"


def test_normalize_handles_empty_string():
    assert normalize("") == ""


def test_normalize_nfkc_and_collapses_multiple_whitespace_kinds():
    assert normalize("  Über\t Cool  ") == "uber cool"


def test_is_cjk_true_for_japanese_and_false_for_latin():
    assert is_cjk("葬送のフリーレン") is True
    assert is_cjk("labubu") is False
    assert is_cjk("") is False


def test_tokens_removes_stopwords_and_short_latin_tokens():
    result = tokens("A Free STL Bust of the Hero")
    assert "a" not in result
    assert "the" not in result
    assert "stl" not in result
    assert "free" not in result
    assert "bust" not in result
    assert "hero" in result


def test_tokens_keeps_three_letter_latin_tokens():
    assert "40k" in tokens("Warhammer 40k army")


def test_tokens_drops_two_letter_latin_tokens():
    assert "ai" not in tokens("um robo de ai")


def test_tokens_on_pure_cjk_phrase_without_spaces_is_not_dropped_for_being_short():
    result = tokens("忍")
    assert result == ["忍"]


def test_matches_phrase_latin_uses_word_boundaries():
    haystack = normalize("Labubu keychain 3d model")
    assert matches_phrase(haystack, normalize("labubu")) is True
    assert matches_phrase(haystack, normalize("labub")) is False
    assert matches_phrase(haystack, normalize("bubu")) is False


def test_matches_phrase_cjk_uses_substring():
    haystack = normalize("葬送のフリーレン figure")
    assert matches_phrase(haystack, normalize("葬送のフリーレン")) is True
    assert matches_phrase(haystack, normalize("フリーレン")) is True
    assert matches_phrase(haystack, normalize("ワンピース")) is False


def test_matches_phrase_empty_phrase_never_matches():
    assert matches_phrase(normalize("qualquer coisa"), "") is False
