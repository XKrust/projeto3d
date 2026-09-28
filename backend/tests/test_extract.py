import json
from datetime import date, timedelta

from sqlmodel import select

from app.constants import GLOBAL
from app.models import RawItem, Topic, TopicItem, TopicSignal
from app.topics.extract import _load_entities, extract_topics

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
    assert len(topics) == len(_load_entities())
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


# --- Fix round 1: revisao ---


def test_trends_term_passes_filter_via_in_window_history_match(session):
    """Fix 1: um item de outra fonte de ate 7 dias atras (nao so do proprio dia
    ou de um TopicItem ja existente) deve valer para o filtro de ruido."""
    yesterday = DAY - timedelta(days=1)
    _raw_item(
        session,
        source="reddit",
        external_id="gachiakuta-reddit",
        country=GLOBAL,
        title="Gachiakuta figure",
        metric=20.0,
        day=yesterday,
    )

    _raw_item(
        session,
        source="google_trends",
        external_id="gachiakuta-trend",
        country="JP",
        title="Gachiakuta",
        metric=300.0,
        day=DAY,
    )

    count = extract_topics(session, DAY)

    topic = session.exec(select(Topic).where(Topic.slug == "gachiakuta")).one()
    assert count >= 1
    signal = session.exec(
        select(TopicSignal).where(
            TopicSignal.topic_id == topic.id, TopicSignal.day == DAY, TopicSignal.source == "google_trends"
        )
    ).one()
    assert signal.value == 300.0
    assert signal.country == "JP"


def test_trends_term_matching_entity_alias_resolves_to_the_entity_not_a_duplicate(session):
    """Fix 2: um termo do Trends igual a um alias de entidade nao deve virar um
    segundo topico; deve casar com a entidade."""
    _raw_item(
        session,
        source="google_trends",
        external_id="zelda-trend",
        country="US",
        title="Zelda",
        metric=80.0,
    )
    _raw_item(
        session,
        source="reddit",
        external_id="zelda-reddit",
        country=GLOBAL,
        title="Zelda sword",
        metric=15.0,
    )

    extract_topics(session, DAY)

    assert session.exec(select(Topic).where(Topic.slug == "zelda")).first() is None
    topic = session.exec(select(Topic).where(Topic.slug == "the-legend-of-zelda")).one()

    signals = session.exec(select(TopicSignal).where(TopicSignal.topic_id == topic.id)).all()
    assert {(s.source, s.country): s.value for s in signals} == {
        ("google_trends", "US"): 80.0,
        ("reddit", GLOBAL): 15.0,
    }


def test_existing_candidate_topic_gets_signal_next_day_without_requalifying(session):
    """Fix 3: um topico-candidato ja existente e casado/recebe sinal todo dia,
    sem precisar bater o limiar de mineracao (>=3 itens/>=2 fontes) de novo."""
    yesterday = DAY - timedelta(days=1)
    _raw_item(session, source="reddit", external_id="r1", country=GLOBAL, title="Gojo satoru figure", metric=5.0, day=yesterday)
    _raw_item(session, source="reddit", external_id="r2", country=GLOBAL, title="gojo infinity void", metric=6.0, day=yesterday)
    _raw_item(session, source="sketchfab", external_id="sk1", country=GLOBAL, title="Gojo bust model", metric=7.0, day=yesterday)
    extract_topics(session, yesterday)
    topic = session.exec(select(Topic).where(Topic.slug == "gojo")).one()
    assert topic.is_candidate is True

    # hoje: so 2 itens de 1 fonte, bem abaixo do limiar de mineracao de candidato.
    _raw_item(session, source="reddit", external_id="r3", country=GLOBAL, title="Gojo domain expansion", metric=50.0, day=DAY)
    _raw_item(session, source="reddit", external_id="r4", country=GLOBAL, title="gojo strongest sorcerer", metric=50.0, day=DAY)

    extract_topics(session, DAY)

    signal = session.exec(
        select(TopicSignal).where(
            TopicSignal.topic_id == topic.id, TopicSignal.day == DAY, TopicSignal.source == "reddit"
        )
    ).one()
    assert signal.value == 100.0


def test_existing_topic_matches_item_via_alias_added_by_a_merge(session):
    """Fix 3: aliases_json de um topico ja existente (ex.: fusao da Tarefa 13)
    tambem sao usados no casamento do dia, nao so o nome."""
    topic = Topic(
        slug="jjk-arc",
        name="JJK Arc",
        category="anime",
        aliases_json=json.dumps(["shibuya arc"]),
        is_candidate=True,
        created_day=DAY - timedelta(days=1),
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)

    _raw_item(session, source="reddit", external_id="r1", country=GLOBAL, title="Shibuya Arc figure", metric=30.0)

    extract_topics(session, DAY)

    signal = session.exec(
        select(TopicSignal).where(TopicSignal.topic_id == topic.id, TopicSignal.day == DAY)
    ).one()
    assert signal.value == 30.0


def test_entity_image_url_is_backfilled_once_a_thumb_appears_on_a_later_day(session):
    """Fix 4: image_url de uma entidade criada sem itens fica None ate um item
    com thumb casar; nunca fica preso em None para sempre."""
    extract_topics(session, DAY)
    topic = session.exec(select(Topic).where(Topic.slug == "labubu")).one()
    assert topic.image_url is None

    next_day = DAY + timedelta(days=1)
    _raw_item(
        session,
        source="sketchfab",
        external_id="labubu-sk",
        country=GLOBAL,
        title="Labubu figure",
        metric=10.0,
        day=next_day,
        thumb_url="https://sketchfab.example/labubu.png",
    )
    extract_topics(session, next_day)

    updated = session.exec(select(Topic).where(Topic.slug == "labubu")).one()
    assert updated.image_url == "https://sketchfab.example/labubu.png"


# --- Fix round 2: revisao ---


def test_trends_terms_with_hyphen_and_space_variants_share_one_topic(session):
    """Fix 1: duas sementes cujo nome normalizado difere mas cujo slug colide
    (hifen vs espaco) devem se fundir num so topico, sem IntegrityError."""
    _raw_item(session, source="google_trends", external_id="sm-us", country="US", title="Spider-Man", metric=200.0)
    _raw_item(session, source="google_trends", external_id="sm-br", country="BR", title="Spider Man", metric=150.0)
    _raw_item(session, source="reddit", external_id="sm-reddit", country=GLOBAL, title="Spider-Man movie", metric=20.0)

    count = extract_topics(session, DAY)

    topics = session.exec(select(Topic).where(Topic.slug == "spider-man")).all()
    assert len(topics) == 1
    assert count == 1
    signals = session.exec(select(TopicSignal).where(TopicSignal.topic_id == topics[0].id)).all()
    assert {(s.source, s.country): s.value for s in signals} == {
        ("google_trends", "US"): 200.0,
        ("google_trends", "BR"): 150.0,
        ("reddit", GLOBAL): 20.0,
    }


def test_trends_term_hyphen_variant_of_an_entity_name_does_not_duplicate_it(session):
    """Fix 1: um termo do Trends com hifen que colide no slug com uma entidade
    nao deve crashar nem virar um topico separado dela."""
    _raw_item(session, source="google_trends", external_id="sw-trend", country="US", title="Star-Wars", metric=90.0)
    _raw_item(session, source="reddit", external_id="sw-reddit", country=GLOBAL, title="star-wars helmet", metric=25.0)

    extract_topics(session, DAY)

    topics = session.exec(select(Topic).where(Topic.slug == "star-wars")).all()
    assert len(topics) == 1
    assert topics[0].name == "Star Wars"
    assert topics[0].is_candidate is False

    signals = session.exec(select(TopicSignal).where(TopicSignal.topic_id == topics[0].id)).all()
    assert {(s.source, s.country): s.value for s in signals} == {
        ("google_trends", "US"): 90.0,
        ("reddit", GLOBAL): 25.0,
    }


def test_trends_term_matching_an_existing_topics_alias_resolves_to_it_not_a_duplicate(session):
    """Fix 2: um termo do Trends que so bate com um alias (nao o nome) de um
    topico ja existente deve resolver para ele, sem criar um duplicado nem
    contar o sinal duas vezes."""
    topic = Topic(
        slug="jjk-arc",
        name="JJK Arc",
        category="anime",
        aliases_json=json.dumps(["shibuya arc"]),
        is_candidate=True,
        created_day=DAY - timedelta(days=1),
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)

    _raw_item(session, source="google_trends", external_id="shibuya-trend", country="JP", title="Shibuya Arc", metric=100.0)
    _raw_item(session, source="reddit", external_id="shibuya-reddit", country=GLOBAL, title="Shibuya Arc figure", metric=10.0)

    extract_topics(session, DAY)

    assert session.exec(select(Topic).where(Topic.slug == "shibuya-arc")).first() is None
    signals = session.exec(
        select(TopicSignal).where(TopicSignal.topic_id == topic.id, TopicSignal.day == DAY)
    ).all()
    assert {(s.source, s.country): s.value for s in signals} == {
        ("google_trends", "JP"): 100.0,
        ("reddit", GLOBAL): 10.0,
    }


def test_existing_candidate_is_not_treated_as_trends_term_when_a_trends_seed_lands_on_its_slug(session):
    """Fix 3 (ruling): um topico-candidato ja existente continua sem passar
    pelo filtro de ruido mesmo quando um termo do Trends de hoje cai no mesmo
    slug dele."""
    old_day = DAY - timedelta(days=10)
    _raw_item(session, source="reddit", external_id="r1", country=GLOBAL, title="Gojo satoru figure", metric=5.0, day=old_day)
    _raw_item(session, source="reddit", external_id="r2", country=GLOBAL, title="gojo infinity void", metric=6.0, day=old_day)
    _raw_item(session, source="sketchfab", external_id="sk1", country=GLOBAL, title="Gojo bust model", metric=7.0, day=old_day)
    extract_topics(session, old_day)
    topic = session.exec(select(Topic).where(Topic.slug == "gojo")).one()
    assert topic.is_candidate is True

    _raw_item(session, source="google_trends", external_id="gojo-trend", country="JP", title="Gojo", metric=500.0, day=DAY)

    extract_topics(session, DAY)

    signal = session.exec(
        select(TopicSignal).where(TopicSignal.topic_id == topic.id, TopicSignal.day == DAY)
    ).one()
    assert signal.value == 500.0


def test_common_word_does_not_become_a_candidate_topic(session):
    # "Dragon" aparece em 3 itens de 2 fontes, mas é palavra de dicionário: não é tema.
    _raw_item(session, source="reddit", external_id="r1", country=GLOBAL, title="Dragon figure", metric=5.0)
    _raw_item(session, source="reddit", external_id="r2", country=GLOBAL, title="dragon lamp", metric=6.0)
    _raw_item(session, source="sketchfab", external_id="sk1", country=GLOBAL, title="Dragon bust", metric=7.0)

    extract_topics(session, DAY)

    assert session.exec(select(Topic).where(Topic.slug == "dragon")).first() is None


def test_generic_trends_search_does_not_become_a_topic(session):
    # Busca em alta que não é tema de modelo 3D ("germany") casando com um item qualquer.
    _raw_item(session, source="google_trends", external_id="g1", country="BR", title="germany", metric=300.0)
    _raw_item(session, source="sketchfab", external_id="sk1", country=GLOBAL, title="Germany tank", metric=5.0)

    extract_topics(session, DAY)

    assert session.exec(select(Topic).where(Topic.slug == "germany")).first() is None


def test_existing_generic_topic_stops_receiving_signals(session):
    game = Topic(slug="game", name="Game", category="outros", is_candidate=True, created_day=DAY - timedelta(days=3))
    session.add(game)
    session.commit()
    _raw_item(session, source="sketchfab", external_id="sk1", country=GLOBAL, title="Game controller", metric=5.0)

    extract_topics(session, DAY)

    assert session.exec(select(TopicSignal).where(TopicSignal.topic_id == game.id)).all() == []


def test_entity_with_common_name_still_counts(session):
    # "Pokemon" é palavra comum no dicionário, mas é tema curado: continua valendo.
    _raw_item(session, source="sketchfab", external_id="sk1", country=GLOBAL, title="Pokemon planter", metric=5.0)

    extract_topics(session, DAY)

    topic = session.exec(select(Topic).where(Topic.slug == "pokemon")).one()
    assert session.exec(select(TopicSignal).where(TopicSignal.topic_id == topic.id)).all()


def test_single_word_fragment_of_a_known_theme_is_not_a_topic(session):
    # "Meshi" é pedaço de "Dungeon Meshi" (tema conhecido): não vira tema separado.
    session.add(Topic(slug="meshi", name="Meshi", category="outros", is_candidate=True,
                      created_day=DAY - timedelta(days=3)))
    session.commit()
    _raw_item(session, source="sketchfab", external_id="sk1", country=GLOBAL, title="Dungeon Meshi Marcille",
              metric=5.0)

    extract_topics(session, DAY)

    meshi = session.exec(select(Topic).where(Topic.slug == "meshi")).one()
    assert session.exec(select(TopicSignal).where(TopicSignal.topic_id == meshi.id)).all() == []


def test_old_topic_named_like_an_entity_alias_is_merged_into_the_entity(session):
    # "Dungeon Meshi" ficou de uma versão anterior; hoje é apelido de "Delicious in Dungeon".
    old = Topic(slug="dungeon-meshi", name="Dungeon Meshi", category="anime", is_candidate=False,
                created_day=DAY - timedelta(days=2))
    session.add(old)
    session.commit()
    session.add(TopicSignal(topic_id=old.id, source="reddit", country=GLOBAL, day=DAY - timedelta(days=1), value=9.0))
    session.commit()

    extract_topics(session, DAY)

    assert session.exec(select(Topic).where(Topic.slug == "dungeon-meshi")).first() is None
    entity = session.exec(select(Topic).where(Topic.slug == "delicious-in-dungeon")).one()
    moved = session.exec(select(TopicSignal).where(TopicSignal.topic_id == entity.id)).all()
    assert [s.value for s in moved] == [9.0]
