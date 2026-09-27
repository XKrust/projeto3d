import json
from datetime import date, timedelta

from sqlmodel import select

from app.constants import GLOBAL
from app.models import RawItem, Topic, TopicItem, TopicSignal
from app.topics.extract import extract_topics

DAY = date(2026, 9, 26)


def _raw_item(session, *, source, external_id, country, title, metric, day=DAY, tags=None, thumb_url=None):
    item = RawItem(
        source=source,
        external_id=external_id,
        country=country,
        day=day,
        title=title,
        tags_json=json.dumps(tags or []),
        metric=metric,
        thumb_url=thumb_url,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def test_entities_are_seeded_even_without_matching_items(session):
    count = extract_topics(session, DAY)

    topics = session.exec(select(Topic)).all()
    assert len(topics) == 20
    assert all(t.is_candidate is False for t in topics)
    assert count == 0
    assert session.exec(select(TopicItem)).all() == []
    assert session.exec(select(TopicSignal)).all() == []


def test_trends_jp_and_reddit_merge_into_one_topic_with_jp_and_global_signals(session):
    _raw_item(
        session,
        source="google_trends",
        external_id="frieren-jp",
        country="JP",
        title="葬送のフリーレン",
        metric=500.0,
    )
    _raw_item(
        session,
        source="reddit",
        external_id="t3_abc",
        country=GLOBAL,
        title="葬送のフリーレン figure",
        metric=42.0,
    )

    count = extract_topics(session, DAY)

    topic = session.exec(select(Topic).where(Topic.name == "葬送のフリーレン")).one()
    assert topic.is_candidate is False
    assert count == 1

    signals = session.exec(select(TopicSignal).where(TopicSignal.topic_id == topic.id)).all()
    assert {s.country: s.value for s in signals} == {"JP": 500.0, GLOBAL: 42.0}

    linked_items = session.exec(select(TopicItem).where(TopicItem.topic_id == topic.id)).all()
    assert len(linked_items) == 2


def test_trends_term_without_cross_source_match_does_not_become_a_topic(session):
    _raw_item(
        session,
        source="google_trends",
        external_id="fla-pal",
        country="BR",
        title="Flamengo x Palmeiras",
        metric=100.0,
    )

    count = extract_topics(session, DAY)

    assert count == 0
    assert session.exec(select(Topic).where(Topic.name == "Flamengo x Palmeiras")).first() is None
    assert session.exec(select(TopicItem)).all() == []
    assert session.exec(select(TopicSignal)).all() == []


def test_trends_term_topic_persists_but_gets_no_new_signal_once_it_stops_passing_the_filter(session):
    old_day = DAY - timedelta(days=10)
    _raw_item(
        session,
        source="google_trends",
        external_id="fla-pal-old",
        country="BR",
        title="Flamengo x Palmeiras",
        day=old_day,
        metric=100.0,
    )
    _raw_item(
        session,
        source="reddit",
        external_id="r-old",
        country=GLOBAL,
        title="Flamengo x Palmeiras reaction",
        day=old_day,
        metric=20.0,
    )
    extract_topics(session, old_day)
    topic = session.exec(select(Topic).where(Topic.name == "Flamengo x Palmeiras")).one()

    _raw_item(
        session,
        source="google_trends",
        external_id="fla-pal-today",
        country="BR",
        title="Flamengo x Palmeiras",
        day=DAY,
        metric=90.0,
    )
    extract_topics(session, DAY)

    still_there = session.exec(select(Topic).where(Topic.name == "Flamengo x Palmeiras")).one()
    assert still_there.id == topic.id
    assert (
        session.exec(
            select(TopicSignal).where(TopicSignal.topic_id == topic.id, TopicSignal.day == DAY)
        ).first()
        is None
    )


def test_entity_labubu_gets_signal_from_single_platform_item(session):
    _raw_item(
        session,
        source="sketchfab",
        external_id="sk-1",
        country=GLOBAL,
        title="Labubu keychain 3d model",
        metric=10.0,
    )

    count = extract_topics(session, DAY)

    topic = session.exec(select(Topic).where(Topic.slug == "labubu")).one()
    assert topic.is_candidate is False
    assert count >= 1

    signal = session.exec(
        select(TopicSignal).where(TopicSignal.topic_id == topic.id, TopicSignal.source == "sketchfab")
    ).one()
    assert signal.value == 10.0
    assert signal.country == GLOBAL


def test_candidate_gojo_becomes_topic_with_three_items_from_two_sources(session):
    _raw_item(session, source="reddit", external_id="r1", country=GLOBAL, title="Gojo satoru figure", metric=5.0)
    _raw_item(session, source="reddit", external_id="r2", country=GLOBAL, title="gojo infinity void", metric=6.0)
    _raw_item(session, source="sketchfab", external_id="sk1", country=GLOBAL, title="Gojo bust model", metric=7.0)

    extract_topics(session, DAY)

    topic = session.exec(select(Topic).where(Topic.slug == "gojo")).one()
    assert topic.is_candidate is True


def test_candidate_gojo_does_not_become_topic_with_a_single_source(session):
    _raw_item(session, source="reddit", external_id="r1", country=GLOBAL, title="Gojo satoru figure", metric=5.0)
    _raw_item(session, source="reddit", external_id="r2", country=GLOBAL, title="gojo infinity void", metric=6.0)
    _raw_item(session, source="reddit", external_id="r3", country=GLOBAL, title="gojo domain expansion", metric=7.0)

    extract_topics(session, DAY)

    assert session.exec(select(Topic).where(Topic.slug == "gojo")).first() is None


def test_extract_topics_is_idempotent(session):
    _raw_item(session, source="sketchfab", external_id="sk-1", country=GLOBAL, title="Labubu keychain", metric=10.0)
    _raw_item(session, source="reddit", external_id="r1", country=GLOBAL, title="Gojo satoru figure", metric=5.0)
    _raw_item(session, source="reddit", external_id="r2", country=GLOBAL, title="gojo infinity void", metric=6.0)
    _raw_item(session, source="sketchfab", external_id="sk2", country=GLOBAL, title="Gojo bust model", metric=7.0)

    first = extract_topics(session, DAY)
    topic_items_1 = session.exec(select(TopicItem)).all()
    signals_1 = session.exec(select(TopicSignal)).all()

    second = extract_topics(session, DAY)
    topic_items_2 = session.exec(select(TopicItem)).all()
    signals_2 = session.exec(select(TopicSignal)).all()

    assert first == second
    assert len(topic_items_1) == len(topic_items_2)
    assert len(signals_1) == len(signals_2)
    assert {(ti.topic_id, ti.raw_item_id) for ti in topic_items_1} == {
        (ti.topic_id, ti.raw_item_id) for ti in topic_items_2
    }


def test_topic_image_prefers_platform_thumb_over_trends_thumb(session):
    _raw_item(
        session,
        source="google_trends",
        external_id="labubu-trend",
        country="BR",
        title="labubu",
        metric=50.0,
        thumb_url="https://trends.example/labubu.png",
    )
    _raw_item(
        session,
        source="sketchfab",
        external_id="labubu-sk",
        country=GLOBAL,
        title="Labubu figure",
        metric=10.0,
        thumb_url="https://sketchfab.example/labubu.png",
    )

    extract_topics(session, DAY)

    topic = session.exec(select(Topic).where(Topic.slug == "labubu")).one()
    assert topic.image_url == "https://sketchfab.example/labubu.png"
