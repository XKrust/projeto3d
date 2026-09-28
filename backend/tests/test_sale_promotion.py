import json
from datetime import timedelta

from app import clock
from app.models import RawItem, TopicItem
from app.sale.promotion import NOTE, build_promotion, hashtags
from tests.sale_helpers import add_topic


def _post(session, topic, subreddit, metric, *, days_ago=0, external_id=None):
    item = RawItem(source="reddit", external_id=external_id or f"{subreddit}-{metric}-{days_ago}", country="GLOBAL",
                   day=clock.today() - timedelta(days=days_ago), title="post",
                   tags_json=json.dumps([subreddit, "Fan Art"]), metric=metric)
    session.add(item)
    session.commit()
    session.refresh(item)
    session.add(TopicItem(topic_id=topic.id, raw_item_id=item.id))
    session.commit()


def test_topic_communities_ranked_by_engagement(session):
    topic = add_topic(session, "Frieren")
    _post(session, topic, "anime", 500)
    _post(session, topic, "anime", 300)
    _post(session, topic, "3Dprinting", 900)
    _post(session, topic, "ActionFigures", 100)
    _post(session, topic, "blender", 50)
    promo = build_promotion(session, topic=topic, market="print", category="anime", tags=[])
    assert promo["communities"] == [
        {"name": "r/3Dprinting", "url": "https://www.reddit.com/r/3Dprinting/", "source": "tema",
         "why": "1 post do tema em alta nos últimos 30 dias"},
        {"name": "r/anime", "url": "https://www.reddit.com/r/anime/", "source": "tema",
         "why": "2 posts do tema em alta nos últimos 30 dias"},
        {"name": "r/ActionFigures", "url": "https://www.reddit.com/r/ActionFigures/", "source": "tema",
         "why": "1 post do tema em alta nos últimos 30 dias"},
    ]
    assert promo["note"] == NOTE


def test_old_posts_and_same_post_on_several_days(session):
    topic = add_topic(session, "Frieren")
    _post(session, topic, "gaming", 999, days_ago=31)
    _post(session, topic, "anime", 10, days_ago=2, external_id="same")
    _post(session, topic, "anime", 20, days_ago=0, external_id="same")
    promo = build_promotion(session, topic=topic, market="print", category="anime", tags=[])
    assert [c["name"] for c in promo["communities"]] == ["r/anime"]
    assert promo["communities"][0]["why"] == "1 post do tema em alta nos últimos 30 dias"


def test_fallback_by_category_and_market(session):
    promo = build_promotion(session, topic=None, market="print", category="anime", tags=[])
    assert [(c["name"], c["source"]) for c in promo["communities"]] == [
        ("r/anime", "tipo"), ("r/3Dprinting", "tipo"), ("r/PrintedMinis", "tipo")]
    assert promo["communities"][0]["why"] == "comunidade de anime"
    assert promo["communities"][1]["why"] == "comunidade de impressão 3D"

    digital = build_promotion(session, topic=add_topic(session, "Nada"), market="digital", category="outros", tags=[])
    assert [c["name"] for c in digital["communities"]] == ["r/blender", "r/3Dmodeling", "r/ZBrush"]

    rpg = build_promotion(session, topic=None, market="print", category="rpg_miniaturas", tags=[])
    assert [c["name"] for c in rpg["communities"]] == ["r/DnD", "r/boardgames", "r/3Dprinting"]


def test_hashtags():
    assert hashtags(["frieren", "anime bust", "Pokémon", "#elf", "", "anime-bust", "フリーレン"]) == [
        "#frieren", "#animebust", "#pokemon", "#elf", "#フリーレン"]
    assert len(hashtags([f"tag{n}" for n in range(20)])) == 8
