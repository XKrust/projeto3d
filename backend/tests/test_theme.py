import pytest

from app.topics.theme import is_generic


@pytest.mark.parametrize("name", ["Game", "Night", "One", "Girl", "Dragon", "germany", "Beta", "Dungeon", "Avatar"])
def test_common_single_words_are_generic(name):
    assert is_generic(name) is True


@pytest.mark.parametrize(
    "name", ["Gojo", "Frieren", "Labubu", "Kagurabachi", "Cyberpunk", "Dungeon Meshi", "Articulated Dragon"]
)
def test_proper_names_and_phrases_are_not_generic(name):
    assert is_generic(name) is False


def test_common_japanese_word_is_generic():
    assert is_generic("フィギュア") is True  # "figura"
