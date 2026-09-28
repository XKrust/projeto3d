import json
from datetime import date, timedelta

import pytest

from app.constants import GLOBAL
from app.models import CountryRank, RawItem, Topic, TopicScore
from app.platforms import seed_platforms
from app.sale.pricing import estimate_chance, estimate_price, rank_stores, target_languages

DAY = date(2026, 9, 28)
RATES = {"EUR": 1.0, "USD": 1.25}
FX = "cotação do Banco Central Europeu de 2026-09-25"


@pytest.fixture(autouse=True)
def _platforms(session):
    seed_platforms(session)


def _rank(session, *codes):
    for position, code in enumerate(codes, start=1):
        session.add(CountryRank(day=DAY, country=code, score=100 - position * 10, position=position,
                                audience=50, demand=50, payment=1.0))
    session.commit()


def _item(session, title, price, source="cgtrader", day=DAY):
    session.add(RawItem(source=source, external_id=f"{source}-{title}-{price}", country=GLOBAL, day=day,
                        title=title, metric=1.0, price_usd=price))
    session.commit()


def _price(session, **kw):
    args = {"query": "frieren bust", "character": "Frieren", "category": "anime", "overall": 5.0,
            "rates": RATES, "fx_source": FX}
    args.update(kw)
    return estimate_price(session, DAY, **args)


def test_languages_follow_the_country_ranking(session):
    _rank(session, "US", "DE", "GB", "RU", "BR")

    assert target_languages(session, DAY) == ["de", "ru"]


def test_languages_default_without_ranking(session):
    assert target_languages(session, DAY) == ["de", "ja"]


def test_stores_for_rpg_miniatures_in_print(session):
    _rank(session, "US", "GB", "DE")

    stores = rank_stores(session, DAY, "rpg_miniaturas", "print")

    assert len(stores) == 3
    assert "MyMiniFactory" in stores
    assert "Sketchfab" not in stores and "Mercado Livre" not in stores


def test_digital_market_only_lists_digital_stores(session):
    _rank(session, "JP", "US")

    stores = rank_stores(session, DAY, "anime", "digital")

    assert set(stores) <= {"Fab", "BOOTH", "CGTrader", "Etsy"}
    assert stores[0] == "BOOTH"  # anime no Japão


def test_price_from_three_comparables(session):
    for price in (5.0, 10.0, 20.0):
        _item(session, f"Frieren bust {price}", price)
    _item(session, "Dragon lamp", 99.0)  # não é parecido
    _item(session, "Frieren bust velho", 99.0, day=DAY - timedelta(days=120))  # velho demais

    price = _price(session)

    assert price["basis"] == "comparaveis"
    assert price["sample"] == 3
    assert price["eur"] == pytest.approx(10.0 / 1.25)  # nota 5 → fator 1,0
    assert (price["low_eur"], price["high_eur"]) == (pytest.approx(4.0), pytest.approx(16.0))
    assert price["fx_source"] == FX


def test_two_comparables_fall_back_to_category_range(session):
    _item(session, "Frieren bust a", 5.0)
    _item(session, "Frieren bust b", 50.0)

    price = _price(session, overall=8.0)

    assert price["basis"] == "faixa_categoria"
    assert price["sample"] == 0
    assert price["eur"] == pytest.approx(round(6.9 * 1.18 / 1.25, 2))
    assert "figuras e bustos de anime" in price["basis_text"]


def test_price_without_overall_uses_factor_one(session):
    assert _price(session, overall=None)["eur"] == pytest.approx(round(6.9 / 1.25, 2))


def test_unknown_category_uses_general_range(session):
    assert _price(session, category="xyz")["basis"] == "faixa_categoria"


def _topic_score(session, name, aliases, opportunity, country="US"):
    topic = Topic(slug=name.lower().replace(" ", "-"), name=name, category="anime", is_candidate=False,
                  created_day=DAY, aliases_json=json.dumps(aliases))
    session.add(topic)
    session.commit()
    session.add(TopicScore(topic_id=topic.id, country=country, platform="cults3d", day=DAY, demand=50,
                           momentum=50, momentum_raw=0, saturation=50, peak_day=DAY, fit_window=1,
                           fit_platform=1, opportunity=opportunity))
    session.commit()


def test_chance_uses_radar_topic_matched_by_alias(session):
    _rank(session, "US")
    _topic_score(session, "Sousou no Frieren", ["frieren"], opportunity=80.0)

    chance, note = estimate_chance(session, DAY, theme="Busto da Frieren", character="Frieren",
                                   query="frieren bust", overall=7.0)

    assert chance == {"score": 56.0, "label": "Média"}
    assert note is None


def test_chance_without_radar_topic(session):
    chance, note = estimate_chance(session, DAY, theme="Caveira", character=None, query="skull", overall=7.0)

    assert chance is None
    assert note == "Tema ainda sem dados no radar"


def test_chance_without_overall(session):
    _topic_score(session, "Sousou no Frieren", ["frieren"], opportunity=80.0)

    chance, note = estimate_chance(session, DAY, theme="Frieren", character=None, query="frieren", overall=None)

    assert chance is None
    assert note == "Sem nota da análise para estimar"
