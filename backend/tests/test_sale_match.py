from app.sale.match import match_topic
from tests.sale_helpers import add_analysis, add_score, add_topic


def test_character_wins_over_theme(session):
    frieren = add_topic(session, "Frieren")
    add_topic(session, "Bust")
    analysis = add_analysis(session, theme="Bust", character="Frieren", search_query="bust")
    assert match_topic(session, analysis).id == frieren.id


def test_alias_matches(session):
    topic = add_topic(session, "Sousou no Frieren", aliases=["frieren", "葬送のフリーレン"])
    analysis = add_analysis(session, theme="Busto da Frieren", character=None, search_query="elf mage bust")
    assert match_topic(session, analysis).id == topic.id


def test_accents_and_case_do_not_matter(session):
    topic = add_topic(session, "Pokémon")
    analysis = add_analysis(session, theme="pikachu POKEMON", character=None, search_query="")
    assert match_topic(session, analysis).id == topic.id


def test_no_match_returns_none(session):
    add_topic(session, "Frieren")
    analysis = add_analysis(session, theme="Dragão de pedra", character=None, search_query="stone dragon")
    assert match_topic(session, analysis) is None


def test_candidate_topics_are_ignored(session):
    add_topic(session, "Frieren", candidate=True)
    analysis = add_analysis(session)
    assert match_topic(session, analysis) is None


def test_tie_goes_to_highest_opportunity(session):
    low = add_topic(session, "Frieren")
    high = add_topic(session, "Frieren Fern", aliases=["frieren"])
    add_score(session, low, opportunity=30)
    add_score(session, high, opportunity=80)
    analysis = add_analysis(session, character="Frieren")
    assert match_topic(session, analysis).id == high.id


def test_word_boundary_prevents_partial_match(session):
    add_topic(session, "Link")
    analysis = add_analysis(session, theme="Linkin mascot", character=None, search_query="")
    assert match_topic(session, analysis) is None
