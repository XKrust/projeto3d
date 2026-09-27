from pathlib import Path

import httpx
import respx

from app.collectors.google_trends import GoogleTrendsCollector, parse_feed, parse_traffic
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "google_trends"
COUNTRIES = ["BR", "US", "GB", "DE", "FR", "ES", "JP"]


def test_parse_traffic():
    assert parse_traffic("200K+") == 200000
    assert parse_traffic("2M+") == 2000000
    assert parse_traffic("1,000+") == 1000
    assert parse_traffic("") == 0


def test_parse_feed_br_has_five_items_with_country_and_metric():
    xml = (FIXTURES / "br.xml").read_text(encoding="utf-8")
    items = parse_feed(xml, "BR")

    assert len(items) == 5
    assert all(item.country == "BR" for item in items)
    assert all(item.metric > 0 for item in items)
    assert all(item.external_id == item.title.strip().lower() for item in items)
    assert all(0 < len(item.tags) <= 3 for item in items)


def test_parse_feed_jp_preserves_japanese_titles():
    xml = (FIXTURES / "jp.xml").read_text(encoding="utf-8")
    items = parse_feed(xml, "JP")

    assert len(items) == 5
    titles = {item.title for item in items}
    assert "パドレス 対 dバックス" in titles
    assert all(item.country == "JP" for item in items)


@respx.mock
def test_collect_generates_items_for_each_country():
    br_xml = (FIXTURES / "br.xml").read_text(encoding="utf-8")
    for country in COUNTRIES:
        respx.get(f"https://trends.google.com/trending/rss?geo={country}").mock(
            return_value=httpx.Response(200, text=br_xml)
        )

    settings = {"countries": COUNTRIES}
    with make_client() as http:
        items = GoogleTrendsCollector(settings, http).collect()

    assert {item.country for item in items} == set(COUNTRIES)
    assert len(items) == 5 * len(COUNTRIES)
