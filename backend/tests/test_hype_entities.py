import json
from datetime import date, timedelta

from sqlmodel import select

from app.constants import GLOBAL
from app.hype.entities import base_title, hype_entities, recent_releases, top_characters
from app.models import HypeRelease, RawItem, Topic, TopicItem
from app.topics.extract import extract_topics

DAY = date(2026, 9, 27)


def _release(session, *, external_id, title, kind="anime", popularity=1000.0,
             release_date=DAY + timedelta(days=10), aliases=(), characters=(), updated_day=DAY):
    row = HypeRelease(
        source="anilist",
        external_id=external_id,
        kind=kind,
        title=title,
        release_date=release_date,
        popularity=popularity,
        country=GLOBAL,
        aliases_json=json.dumps(list(aliases), ensure_ascii=False),
        characters_json=json.dumps(list(characters), ensure_ascii=False),
        updated_day=updated_day,
    )
    session.add(row)
    session.commit()
    return row


def _char(name, native=None, favourites=5000):
    return {"name": name, "native": native, "favourites": favourites, "image_url": None}


def test_base_title_strips_season_markers():
    assert base_title("The Apothecary Diaries Season 3") == "The Apothecary Diaries"
    assert base_title("Kusuriya no Hitorigoto 3rd Season") == "Kusuriya no Hitorigoto"
    assert base_title("薬屋のひとりごと 第3期") == "薬屋のひとりごと"
    assert base_title("Black Clover 2nd Season") == "Black Clover"
    assert base_title("Cyberpunk: Edgerunners 2") == "Cyberpunk: Edgerunners"
    assert base_title("Frieren") == "Frieren"


def test_hype_entities_include_title_and_top2_characters(session):
    _release(
        session,
        external_id="1",
        title="The Apothecary Diaries Season 3",
        aliases=["Kusuriya no Hitorigoto 3rd Season", "薬屋のひとりごと 第3期"],
        characters=[
            _char("Anya Forger", "アーニャ・フォージャー", 9000),
            _char("Loid Forger", "ロイド・フォージャー", 8000),
            _char("Yor Forger", "ヨル・フォージャー", 7000),
        ],
    )

    entities = {e["name"]: e for e in hype_entities(session, DAY)}

    assert set(entities) == {"The Apothecary Diaries", "Anya Forger", "Loid Forger"}
    title = entities["The Apothecary Diaries"]
    assert title["category"] == "anime"
    assert "薬屋のひとりごと" in title["aliases"]
    assert "Kusuriya no Hitorigoto" in title["aliases"]
    assert entities["Anya Forger"]["aliases"] == ["アーニャ・フォージャー"]
    assert entities["Anya Forger"]["category"] == "anime"


def test_hype_entities_skip_short_unpopular_and_duplicate_names(session):
    _release(
        session,
        external_id="1",
        title="Cyberpunk: Edgerunners 2",
        characters=[
            _char("D", "D", 9000),
            _char("Talia Yang", "タリア・ヤン", 35),
            _char("David Martinez", None, 9000),
        ],
    )
    _release(session, external_id="2", title="Cyberpunk: Edgerunners", popularity=10.0)

    names = [e["name"] for e in hype_entities(session, DAY)]

    assert names.count("Cyberpunk: Edgerunners") == 1
    assert "D" not in names  # nome curto demais: casaria com qualquer "d"
    assert "Talia Yang" not in names  # poucos favoritos
    assert "David Martinez" in names


def test_hype_entities_category_by_kind(session):
    _release(session, external_id="f", title="Vingadores: Guerras Secretas", kind="filme")
    _release(session, external_id="j", title="Monster Hunter Stories 3", kind="jogo")

    categories = {e["name"]: e["category"] for e in hype_entities(session, DAY)}

    assert categories["Vingadores: Guerras Secretas"] == "filmes_series"
    assert categories["Monster Hunter Stories"] == "games"


def test_hype_entities_ignore_old_or_stale_releases(session):
    _release(session, external_id="old", title="Estreou Faz Tempo", release_date=DAY - timedelta(days=200))
    _release(session, external_id="stale", title="Coleta Velha", updated_day=DAY - timedelta(days=30))
    _release(session, external_id="nodate", title="Sem Data Ainda", release_date=None)

    names = {e["name"] for e in hype_entities(session, DAY)}

    assert names == {"Sem Data Ainda"}


def test_hype_entities_limit_by_popularity(session):
    for i in range(5):
        _release(session, external_id=str(i), title=f"Anime Numero {chr(65 + i)}", popularity=float(i))

    names = [e["name"] for e in hype_entities(session, DAY, limit=2)]

    assert names == ["Anime Numero E", "Anime Numero D"]


def test_booth_japanese_title_matches_hype_topic_by_native_alias(session):
    _release(
        session,
        external_id="1",
        title="The Apothecary Diaries Season 3",
        aliases=["薬屋のひとりごと 第3期"],
        characters=[_char("Anya Forger", "アーニャ・フォージャー")],
    )
    item = RawItem(
        source="booth",
        external_id="7657840",
        country="JP",
        day=DAY,
        title="薬屋のひとりごと アーニャ・フォージャー アクリルスタンド 3Dモデル",
        metric=500.0,
    )
    session.add(item)
    session.commit()

    extract_topics(session, DAY)

    topic = session.exec(select(Topic).where(Topic.name == "The Apothecary Diaries")).one()
    assert topic.category == "anime"
    links = session.exec(select(TopicItem).where(TopicItem.topic_id == topic.id)).all()
    assert [link.raw_item_id for link in links] == [item.id]
    anya = session.exec(select(Topic).where(Topic.name == "Anya Forger")).one()
    assert session.exec(select(TopicItem).where(TopicItem.topic_id == anya.id)).all()


def test_recent_releases_interleave_kinds(session):
    # AniList mede popularidade em ~100 mil; TMDB e IGDB em ~500. Sem intercalar,
    # filmes e jogos nunca entrariam no corte dos N primeiros.
    for i, pop in enumerate((100_000.0, 90_000.0, 80_000.0)):
        _release(session, external_id=f"a{i}", title=f"Anime Numero {chr(65 + i)}", popularity=pop)
    _release(session, external_id="f", title="Filme Grande", kind="filme", popularity=500.0)
    _release(session, external_id="j", title="Jogo Grande", kind="jogo", popularity=400.0)

    titles = [r.title for r in recent_releases(session, DAY)]

    assert titles == ["Anime Numero A", "Filme Grande", "Jogo Grande", "Anime Numero B", "Anime Numero C"]
    names = [e["name"] for e in hype_entities(session, DAY, limit=3)]
    assert names == ["Anime Numero A", "Filme Grande", "Jogo Grande"]


def test_single_word_characters_are_skipped(session):
    # "Power", "Fern" e "Stark" são palavras comuns: casariam com anúncios sem relação.
    _release(
        session,
        external_id="1",
        title="Chainsaw Man",
        characters=[_char("Power", "パワー", 9000), _char("Fern", "フェルン", 8000), _char("Aki Hayakawa", "早川アキ", 500)],
    )

    names = [e["name"] for e in hype_entities(session, DAY)]

    assert "Power" not in names
    assert "Fern" not in names
    assert "Aki Hayakawa" in names  # 2 palavras; entra no lugar dos de 1 palavra


def test_short_native_character_name_is_not_an_alias(session):
    # "レゼ" (2 caracteres) casaria com "プレゼント" (presente).
    _release(session, external_id="1", title="Chainsaw Man", characters=[_char("Reze Bomb", "レゼ", 9000)])

    entities = {e["name"]: e for e in hype_entities(session, DAY)}

    assert entities["Reze Bomb"]["aliases"] == []


def test_top_characters_rules():
    raw = json.dumps([
        _char("Power", None, 9000),
        _char("早川アキ", None, 8000),
        _char("レゼ", None, 7000),
        _char("Anya Forger", None, 6000),
    ])

    assert [c["name"] for c in top_characters(raw)] == ["早川アキ", "Anya Forger"]
