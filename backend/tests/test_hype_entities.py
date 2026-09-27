import json
from datetime import date, timedelta

from sqlmodel import select

from app.constants import GLOBAL
from app.hype.entities import base_title, hype_entities
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
        characters=[_char("Maomao", "猫猫"), _char("Jinshi", "壬氏"), _char("Gaoshun", "高順")],
    )

    entities = {e["name"]: e for e in hype_entities(session, DAY)}

    assert set(entities) == {"The Apothecary Diaries", "Maomao", "Jinshi"}
    title = entities["The Apothecary Diaries"]
    assert title["category"] == "anime"
    assert "薬屋のひとりごと" in title["aliases"]
    assert "Kusuriya no Hitorigoto" in title["aliases"]
    assert entities["Maomao"]["aliases"] == ["猫猫"]
    assert entities["Maomao"]["category"] == "anime"


def test_hype_entities_skip_short_unpopular_and_duplicate_names(session):
    _release(
        session,
        external_id="1",
        title="Cyberpunk: Edgerunners 2",
        characters=[_char("D", "D", 9000), _char("Talia Yang", "タリア・ヤン", 35), _char("Rebecca", None, 9000)],
    )
    _release(session, external_id="2", title="Cyberpunk: Edgerunners", popularity=10.0)

    names = [e["name"] for e in hype_entities(session, DAY)]

    assert names.count("Cyberpunk: Edgerunners") == 1
    assert "D" not in names  # nome curto demais: casaria com qualquer "d"
    assert "Talia Yang" not in names  # poucos favoritos
    assert "Rebecca" in names


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
        characters=[_char("Maomao", "猫猫")],
    )
    item = RawItem(
        source="booth",
        external_id="7657840",
        country="JP",
        day=DAY,
        title="薬屋のひとりごと 猫猫 アクリルスタンド 3Dモデル",
        metric=500.0,
    )
    session.add(item)
    session.commit()

    extract_topics(session, DAY)

    topic = session.exec(select(Topic).where(Topic.name == "The Apothecary Diaries")).one()
    assert topic.category == "anime"
    links = session.exec(select(TopicItem).where(TopicItem.topic_id == topic.id)).all()
    assert [link.raw_item_id for link in links] == [item.id]
    maomao = session.exec(select(Topic).where(Topic.name == "Maomao")).one()
    assert session.exec(select(TopicItem).where(TopicItem.topic_id == maomao.id)).all()
