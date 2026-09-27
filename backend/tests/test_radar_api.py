import json
from datetime import date, timedelta

import pytest

from app import clock
from app.models import Platform, RawItem, Topic, TopicItem, TopicScore
from app.platforms import seed_platforms
from app.settings_store import update_settings

DAY = date(2026, 9, 26)


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: DAY)


@pytest.fixture()
def platforms(session):
    seed_platforms(session)


def _topic(session, name, *, category="outros", slug=None, image_url=None, reason=None):
    topic = Topic(
        slug=slug or name.lower().replace(" ", "-"),
        name=name,
        category=category,
        is_candidate=False,
        created_day=DAY,
        image_url=image_url,
        reason=reason,
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def _score(
    session,
    topic,
    *,
    country="BR",
    platform="cults3d",
    day=DAY,
    opportunity=50.0,
    momentum_raw=0.0,
    fit_platform=1.0,
    peak_day=None,
):
    session.add(
        TopicScore(
            topic_id=topic.id,
            country=country,
            platform=platform,
            day=day,
            demand=50.0,
            momentum=50.0,
            momentum_raw=momentum_raw,
            saturation=50.0,
            peak_day=peak_day or day,
            fit_window=1.0,
            fit_platform=fit_platform,
            opportunity=opportunity,
        )
    )
    session.commit()


def _raw_item(session, *, source, external_id="x", country="BR", day=DAY, price_usd=None):
    item = RawItem(
        source=source,
        external_id=external_id,
        country=country,
        day=day,
        title="Item",
        metric=1.0,
        price_usd=price_usd,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def _link(session, topic, raw_item):
    session.add(TopicItem(topic_id=topic.id, raw_item_id=raw_item.id))
    session.commit()


# ---------------------------------------------------------------- meta


def test_meta_lists_constants_and_platforms(client, platforms):
    r = client.get("/api/radar/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["countries"] == ["BR", "US", "GB", "DE", "FR", "ES", "JP"]
    assert body["country_groups"] == {"Europa": ["GB", "DE", "FR", "ES"]}
    assert "toys_memes" in body["categories"]
    assert body["markets"] == ["print", "digital"]
    slugs = {p["slug"] for p in body["platforms"]}
    assert slugs == {"cults3d", "sketchfab", "printables", "booth", "artstation"}
    assert body["last_updated"] is None


def test_meta_last_updated_is_max_source_last_run(client, session):
    from app.models import Source

    session.add(Source(name="youtube", status="ok", last_run=clock.now()))
    session.commit()
    r = client.get("/api/radar/meta")
    assert r.json()["last_updated"] is not None


# ---------------------------------------------------------------- /api/radar basics


def test_empty_db_returns_empty_list(client, platforms):
    r = client.get("/api/radar", params={"country": "BR"})
    assert r.status_code == 200
    assert r.json() == []


def test_country_invalid_returns_422(client, platforms):
    r = client.get("/api/radar", params={"country": "XX"})
    assert r.status_code == 422
    assert r.json()["detail"] == "País inválido"


def test_country_valid_but_not_active_returns_empty_list(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, country="BR", opportunity=90.0)
    update_settings(session, {"countries": ["US"]})

    r = client.get("/api/radar", params={"country": "BR"})
    assert r.status_code == 200
    assert r.json() == []


def test_platform_invalid_returns_422(client, platforms):
    r = client.get("/api/radar", params={"country": "BR", "platform": "nope"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Plataforma inválida"


def test_market_invalid_returns_422(client, platforms):
    r = client.get("/api/radar", params={"country": "BR", "market": "nope"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Mercado inválido"


def test_category_invalid_returns_422(client, platforms):
    r = client.get("/api/radar", params={"country": "BR", "category": "nope"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Categoria inválida"


def test_brief_example_url_with_empty_filters_returns_200(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, opportunity=90.0)

    r = client.get(
        "/api/radar?country=BR&platform=&market=&category=&limit=50"
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "Labubu"


def test_limit_out_of_range_returns_422_pt_message(client, platforms):
    r = client.get("/api/radar", params={"country": "BR", "limit": 0})
    assert r.status_code == 422
    assert r.json()["detail"] == "Limite deve estar entre 1 e 200"

    r = client.get("/api/radar", params={"country": "BR", "limit": 201})
    assert r.status_code == 422
    assert r.json()["detail"] == "Limite deve estar entre 1 e 200"


# ---------------------------------------------------------------- ordering / shape


def test_sorted_by_opportunity_descending(session, client, platforms):
    low = _topic(session, "Baixo")
    high = _topic(session, "Alto")
    _score(session, low, opportunity=30.0)
    _score(session, high, opportunity=90.0)

    r = client.get("/api/radar", params={"country": "BR"})
    body = r.json()
    assert [item["name"] for item in body] == ["Alto", "Baixo"]
    assert body[0]["opportunity"] == 90.0
    assert body[0]["sale_chance"] == "Alta"
    assert body[0]["estimate"] is True


def test_uses_last_scored_day_for_country(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, day=DAY - timedelta(days=2), opportunity=10.0)
    _score(session, topic, day=DAY - timedelta(days=1), opportunity=95.0)

    r = client.get("/api/radar", params={"country": "BR"})
    body = r.json()
    assert len(body) == 1
    assert body[0]["opportunity"] == 95.0


def test_item_shape_matches_brief(session, client, platforms):
    topic = _topic(session, "Labubu", category="toys_memes", image_url="http://img", reason="motivo")
    _score(
        session,
        topic,
        opportunity=72.5,
        momentum_raw=0.5,
        peak_day=DAY + timedelta(days=10),
    )

    r = client.get("/api/radar", params={"country": "BR"})
    item = r.json()[0]
    assert item["topic_id"] == topic.id
    assert item["slug"] == "labubu"
    assert item["name"] == "Labubu"
    assert item["category"] == "toys_memes"
    assert item["image_url"] == "http://img"
    assert item["reason"] == "motivo"
    assert item["opportunity"] == 72.5
    assert item["sale_chance"] == "Alta"
    assert item["estimate"] is True
    assert item["momentum_arrow"] == "up"
    assert item["days_to_peak"] == 10
    assert item["best_platform"] == {"slug": "cults3d", "name": "Cults3D"}
    assert item["median_price_usd"] is None
    assert item["sparkline"] == [{"day": DAY.isoformat(), "value": 72.5}]


def test_days_to_peak_can_be_non_positive(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, peak_day=DAY - timedelta(days=3))

    r = client.get("/api/radar", params={"country": "BR"})
    assert r.json()[0]["days_to_peak"] == -3


# ---------------------------------------------------------------- filters


def test_market_filter_only_returns_sketchfab_rows(session, client, platforms):
    cults_only = _topic(session, "So Impressao")
    digital_only = _topic(session, "So Digital")
    _score(session, cults_only, platform="cults3d", opportunity=90.0)
    _score(session, digital_only, platform="sketchfab", opportunity=50.0)

    r = client.get("/api/radar", params={"country": "BR", "market": "digital"})
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "So Digital"
    assert body[0]["best_platform"]["slug"] == "sketchfab"


def test_platform_filter(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, platform="cults3d", opportunity=90.0)
    _score(session, topic, platform="sketchfab", opportunity=95.0)

    r = client.get("/api/radar", params={"country": "BR", "platform": "cults3d"})
    body = r.json()
    assert len(body) == 1
    assert body[0]["opportunity"] == 90.0
    assert body[0]["best_platform"]["slug"] == "cults3d"


def test_category_filter(session, client, platforms):
    toys = _topic(session, "Boneco", category="toys_memes")
    anime = _topic(session, "Naruto", category="anime")
    _score(session, toys, opportunity=50.0)
    _score(session, anime, opportunity=90.0)

    r = client.get("/api/radar", params={"country": "BR", "category": "toys_memes"})
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "Boneco"


def test_filter_leaving_no_row_omits_topic(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, platform="cults3d", opportunity=90.0)

    r = client.get("/api/radar", params={"country": "BR", "platform": "sketchfab"})
    assert r.json() == []


def test_best_platform_is_highest_opportunity_times_fit(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, platform="cults3d", opportunity=80.0, fit_platform=0.5)
    _score(session, topic, platform="sketchfab", opportunity=80.0, fit_platform=1.0)

    r = client.get("/api/radar", params={"country": "BR"})
    body = r.json()
    assert len(body) == 1
    assert body[0]["best_platform"]["slug"] == "sketchfab"


def test_limit_param(session, client, platforms):
    for i in range(5):
        topic = _topic(session, f"Topico {i}")
        _score(session, topic, opportunity=float(i))

    r = client.get("/api/radar", params={"country": "BR", "limit": 2})
    assert len(r.json()) == 2


# ---------------------------------------------------------------- median price


def test_median_price_of_raw_items_at_best_platform(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, platform="cults3d", opportunity=90.0)
    for external_id, price in [("a", 2.0), ("b", 4.0), ("c", 10.0)]:
        item = _raw_item(session, source="cults3d", external_id=external_id, price_usd=price)
        _link(session, topic, item)
    # a zero-price item should be excluded from the median
    zero_item = _raw_item(session, source="cults3d", external_id="d", price_usd=0.0)
    _link(session, topic, zero_item)
    # an item at a different platform should be excluded
    other_item = _raw_item(session, source="sketchfab", external_id="e", price_usd=1000.0)
    _link(session, topic, other_item)

    r = client.get("/api/radar", params={"country": "BR"})
    assert r.json()[0]["median_price_usd"] == 4.0


def test_median_price_null_when_no_raw_items(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, opportunity=90.0)

    r = client.get("/api/radar", params={"country": "BR"})
    assert r.json()[0]["median_price_usd"] is None


def test_median_price_rounds_to_two_decimals(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, platform="cults3d", opportunity=90.0)
    for external_id, price in [("a", 1.0), ("b", 2.0)]:
        item = _raw_item(session, source="cults3d", external_id=external_id, price_usd=price)
        _link(session, topic, item)

    r = client.get("/api/radar", params={"country": "BR"})
    assert r.json()[0]["median_price_usd"] == 1.5


# ---------------------------------------------------------------- sparkline


def test_sparkline_has_at_most_30_points_and_is_ascending(session, client, platforms):
    topic = _topic(session, "Labubu")
    for i in range(40):
        _score(session, topic, day=DAY - timedelta(days=i), opportunity=float(i))

    r = client.get("/api/radar", params={"country": "BR"})
    sparkline = r.json()[0]["sparkline"]
    assert len(sparkline) <= 30
    days = [point["day"] for point in sparkline]
    assert days == sorted(days)
    assert sparkline[-1]["day"] == DAY.isoformat()
    assert sparkline[-1]["value"] == 0.0


def test_sparkline_skips_days_without_scores(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, day=DAY, opportunity=10.0)
    _score(session, topic, day=DAY - timedelta(days=5), opportunity=20.0)

    r = client.get("/api/radar", params={"country": "BR"})
    sparkline = r.json()[0]["sparkline"]
    assert len(sparkline) == 2
    assert sparkline[0]["day"] == (DAY - timedelta(days=5)).isoformat()
    assert sparkline[1]["day"] == DAY.isoformat()


def test_sparkline_takes_max_opportunity_per_day_across_platforms(session, client, platforms):
    topic = _topic(session, "Labubu")
    _score(session, topic, platform="cults3d", day=DAY, opportunity=10.0)
    _score(session, topic, platform="sketchfab", day=DAY, opportunity=30.0)

    r = client.get("/api/radar", params={"country": "BR"})
    sparkline = r.json()[0]["sparkline"]
    assert sparkline == [{"day": DAY.isoformat(), "value": 30.0}]
