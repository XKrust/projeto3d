from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from app.constants import COUNTRIES
from app.country_rank import (
    AUDIENCE_WEIGHT,
    DEMAND_WEIGHT,
    PAYMENT_WEIGHT,
    audience_index,
    compute_country_ranks,
    payment_factor,
)
from app.models import CountryRank, Topic, TopicScore
from app.settings_store import update_settings

DAY = date(2026, 9, 27)


def _topic(session, name):
    topic = Topic(slug=name.lower().replace(" ", "-"), name=name, category="anime", is_candidate=False,
                  created_day=DAY)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def _score(session, topic, country, *, momentum, opportunity=60.0, day=DAY, history_days=5):
    # Por padrão o tema tem 5 dias de nota (histórico suficiente para a procura contar).
    for back in range(history_days):
        session.add(TopicScore(topic_id=topic.id, country=country, platform="cults3d",
                               day=day - timedelta(days=back), demand=50, momentum=momentum, momentum_raw=0,
                               saturation=50, peak_day=day, fit_window=1, fit_platform=1,
                               opportunity=opportunity))
    session.commit()


def test_audience_index_uses_real_marketplace_audience():
    index = audience_index()

    assert set(COUNTRIES) <= set(index)
    assert index["US"] == 100.0  # maior público em todas as lojas
    assert index["RU"] > index["GB"]  # Rússia é o 2º público do Cults3D
    assert index["DE"] > index["BR"]
    # Fora do top 5 de todas as lojas: estimativa baixa, mas não zero.
    assert 0 < index["BY"] < index["RU"]


def test_payment_is_harder_in_sanctioned_countries():
    assert payment_factor("RU") == 0.5
    assert payment_factor("BY") == 0.5
    assert payment_factor("BR") == 1.0


def test_score_combines_audience_demand_and_payment(session):
    update_settings(session, {"countries": ["US", "BR"]})
    _score(session, _topic(session, "Frieren"), "US", momentum=80)
    _score(session, _topic(session, "Dandadan"), "BR", momentum=20)

    compute_country_ranks(session, DAY)

    us = session.exec(select(CountryRank).where(CountryRank.country == "US")).one()
    assert us.demand == 80
    assert us.demand_measured is True
    assert us.score == pytest.approx(
        round(AUDIENCE_WEIGHT * 100 + DEMAND_WEIGHT * 80 + PAYMENT_WEIGHT * 100, 1)
    )
    assert us.position == 1


def test_rising_demand_can_overtake_a_bigger_market(session):
    # Mesmo público: quem está com a procura subindo fica na frente.
    update_settings(session, {"countries": ["FR", "GB"]})
    _score(session, _topic(session, "Tema Um"), "FR", momentum=100)
    _score(session, _topic(session, "Tema Dois"), "GB", momentum=0)
    index = audience_index()
    gap = AUDIENCE_WEIGHT * abs(index["FR"] - index["GB"])
    assert gap < DEMAND_WEIGHT * 100  # a procura consegue virar o jogo entre FR e GB

    compute_country_ranks(session, DAY)

    ranks = {r.country: r.position for r in session.exec(select(CountryRank)).all()}
    assert ranks["FR"] < ranks["GB"]


def test_country_without_themes_gets_neutral_demand(session):
    update_settings(session, {"countries": ["DE"]})

    compute_country_ranks(session, DAY)

    de = session.exec(select(CountryRank).where(CountryRank.country == "DE")).one()
    assert de.demand == 50.0


def test_only_active_countries_are_ranked_and_rerun_does_not_duplicate(session):
    update_settings(session, {"countries": ["BR", "JP"]})

    compute_country_ranks(session, DAY)
    compute_country_ranks(session, DAY)

    rows = session.exec(select(CountryRank)).all()
    assert sorted(r.country for r in rows) == ["BR", "JP"]
    assert sorted(r.position for r in rows) == [1, 2]


def test_demand_uses_top10_themes_by_opportunity(session):
    update_settings(session, {"countries": ["BR"]})
    for i in range(12):
        # os 10 de maior oportunidade têm momentum 90; os 2 piores, 0
        _score(session, _topic(session, f"Tema {i:02d}"), "BR", momentum=90 if i < 10 else 0,
               opportunity=100 - i)

    compute_country_ranks(session, DAY)

    br = session.exec(select(CountryRank).where(CountryRank.country == "BR")).one()
    assert br.demand == 90.0


def test_new_themes_without_history_do_not_count_as_rising(session):
    # Tema criado hoje: "de zero para algo" parece subida máxima, mas é só falta de histórico.
    update_settings(session, {"countries": ["BR"]})
    _score(session, _topic(session, "Tema Novo"), "BR", momentum=100, history_days=1)

    compute_country_ranks(session, DAY)

    br = session.exec(select(CountryRank).where(CountryRank.country == "BR")).one()
    assert br.demand == 50.0
    assert br.demand_measured is False
