from datetime import timedelta

import pytest

from app import clock
from app.sale.pricing import comparable_items, price_for_store, round_99, sales_to_cover
from tests.sale_helpers import add_items, add_platform, add_topic


@pytest.fixture()
def stores(session):
    add_platform(session, "cults3d")
    add_platform(session, "etsy")
    add_platform(session, "sketchfab", sells=False)


def test_layer1_same_topic_same_store(session, stores):
    topic = add_topic(session, "Frieren")
    add_items(session, topic, "cults3d", [4, 5, 6, 7, 8])
    items, basis = comparable_items(session, topic=topic, platform="cults3d", platform_name="Cults3D", category="anime")
    assert len(items) == 5
    assert basis == "mediana de 5 anúncios de Frieren no Cults3D"


def test_layer2_same_topic_any_selling_store(session, stores):
    topic = add_topic(session, "Frieren")
    add_items(session, topic, "cults3d", [4, 5])
    add_items(session, topic, "etsy", [6, 7])
    add_items(session, topic, "sketchfab", [50, 60])  # loja fechada não conta
    add_items(session, topic, "etsy", [8])
    items, basis = comparable_items(session, topic=topic, platform="cults3d", platform_name="Cults3D", category="anime")
    assert sorted(i.price_usd for i in items) == [4, 5, 6, 7, 8]
    assert basis == "mediana de 5 anúncios de Frieren em todas as lojas"


def test_layer3_same_category_same_store(session, stores):
    topic = add_topic(session, "Frieren")
    other = add_topic(session, "Naruto")
    decor = add_topic(session, "Vaso", category="decoracao")
    add_items(session, other, "cults3d", [3, 4, 5, 6, 7])
    add_items(session, decor, "cults3d", [90, 90])
    items, basis = comparable_items(session, topic=topic, platform="cults3d", platform_name="Cults3D", category="anime")
    assert sorted(i.price_usd for i in items) == [3, 4, 5, 6, 7]
    assert basis == "mediana de 5 anúncios de Anime no Cults3D"


def test_without_topic_uses_category(session, stores):
    other = add_topic(session, "Naruto")
    add_items(session, other, "cults3d", [3, 4, 5, 6, 7])
    items, _ = comparable_items(session, topic=None, platform="cults3d", platform_name="Cults3D", category="anime")
    assert len(items) == 5


def test_fewer_than_five_returns_nothing(session, stores):
    topic = add_topic(session, "Frieren")
    add_items(session, topic, "cults3d", [4, 5, 6, 7])
    items, basis = comparable_items(session, topic=topic, platform="cults3d", platform_name="Cults3D", category="anime")
    assert items == []
    assert basis == "sem dados suficientes para esta loja"


def test_same_item_on_several_days_counts_once_with_latest_price(session, stores):
    topic = add_topic(session, "Frieren")
    today = clock.today()
    from app.models import RawItem, TopicItem
    for offset, price in ((2, 1.0), (0, 9.0)):
        item = RawItem(source="cults3d", external_id="same", country="BR", day=today - timedelta(days=offset),
                       title="x", price_usd=price, metric=1)
        session.add(item)
        session.commit()
        session.refresh(item)
        session.add(TopicItem(topic_id=topic.id, raw_item_id=item.id))
        session.commit()
    add_items(session, topic, "cults3d", [4, 5, 6, 7])
    items, _ = comparable_items(session, topic=topic, platform="cults3d", platform_name="Cults3D", category="anime")
    assert sorted(i.price_usd for i in items) == [4, 5, 6, 7, 9]


def test_items_older_than_90_days_are_ignored(session, stores):
    topic = add_topic(session, "Frieren")
    add_items(session, topic, "cults3d", [4, 5, 6, 7, 8], day=clock.today() - timedelta(days=91))
    items, _ = comparable_items(session, topic=topic, platform="cults3d", platform_name="Cults3D", category="anime")
    assert items == []


def test_round_99():
    assert round_99(7.6) == 7.99
    assert round_99(7.4) == 6.99
    assert round_99(7.5) == 7.99
    assert round_99(0.2) == 0.99


def test_price_with_quality_and_fee():
    price = price_for_store([4, 5, 6, 7, 8], overall=10, fee_pct=20, basis="b")
    # mediana 6 × 1,3 = 7,8 → 7,99; faixa 5×1,3=6,5 → 6,99 e 7×1,3=9,1 → 8,99
    assert price == {"suggested": 7.99, "low": 6.99, "high": 8.99, "launch": 5.99, "net": 6.39, "basis": "b"}


def test_price_without_overall_and_fee():
    price = price_for_store([4, 5, 6, 7, 8], overall=None, fee_pct=None, basis="b")
    assert price["suggested"] == 5.99
    assert price["net"] is None


def test_price_without_data_is_none():
    assert price_for_store([], overall=6, fee_pct=None, basis="sem dados") is None


def test_sales_to_cover():
    assert sales_to_cover(hours=10, hourly_rate=10, price=7.99) == 13
    assert sales_to_cover(hours=None, hourly_rate=10, price=7.99) is None
    assert sales_to_cover(hours=0, hourly_rate=10, price=7.99) is None
    assert sales_to_cover(hours=10, hourly_rate=10, price=None) is None
