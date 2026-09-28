from datetime import date

from app.models import CountryRank
from app.sale.stores import default_countries, rank_stores
from app.settings_store import update_settings
from tests.sale_helpers import add_platform


def _rank(session, country, position, day=date(2026, 9, 28)):
    session.add(CountryRank(day=day, country=country, score=90 - position, position=position,
                            audience=50, demand=50, payment=1))
    session.commit()


def test_incompatible_market_and_closed_stores_are_out(session):
    add_platform(session, "cults3d", markets=["print"], strength={"BR": 0.8})
    add_platform(session, "fab", markets=["digital"], strength={"BR": 0.9})
    add_platform(session, "sketchfab", markets=["digital", "print"], strength={"BR": 1.0}, sells=False)
    stores = rank_stores(session, "BR", market="print", category="anime")
    assert [s["platform"] for s in stores] == ["cults3d"]


def test_category_affinity_and_top_three(session):
    add_platform(session, "cults3d", strength={"BR": 0.8})
    add_platform(session, "booth", strength={"BR": 0.9}, categories=["anime"])
    add_platform(session, "etsy", strength={"BR": 0.9}, categories=["decoracao"])
    add_platform(session, "mmf", strength={"BR": 0.5})
    stores = rank_stores(session, "BR", market="print", category="anime")
    assert [s["platform"] for s in stores] == ["booth", "cults3d", "etsy"]
    assert stores[2]["fit"] == 0.63
    assert stores[0]["why"] == "Força de venda no Brasil: 0,9 · forte em Anime"
    assert stores[1]["why"] == "Força de venda no Brasil: 0,8 · generalista"
    assert stores[2]["why"] == "Força de venda no Brasil: 0,9 · Anime não é o forte da loja"


def test_tie_is_broken_by_slug(session):
    add_platform(session, "zeta", strength={"BR": 0.5})
    add_platform(session, "alfa", strength={"BR": 0.5})
    assert [s["platform"] for s in rank_stores(session, "BR", market="print", category="anime")] == ["alfa", "zeta"]


def test_store_without_strength_in_country_is_out(session):
    add_platform(session, "cults3d", strength={"US": 0.8})
    assert rank_stores(session, "BR", market="print", category="anime") == []


def test_default_countries_top3_plus_br(session):
    for position, country in enumerate(["US", "DE", "GB", "BR", "FR"], start=1):
        _rank(session, country, position)
    assert default_countries(session) == ["US", "DE", "GB", "BR"]


def test_default_countries_br_already_in_top3(session):
    for position, country in enumerate(["BR", "US", "DE", "GB"], start=1):
        _rank(session, country, position)
    assert default_countries(session) == ["BR", "US", "DE"]


def test_default_countries_skip_inactive(session):
    update_settings(session, {"countries": ["US", "GB", "FR"]})
    for position, country in enumerate(["US", "DE", "GB", "BR", "FR"], start=1):
        _rank(session, country, position)
    assert default_countries(session) == ["US", "GB", "FR"]


def test_default_countries_without_ranking(session):
    assert default_countries(session) == ["BR", "US", "GB"]
