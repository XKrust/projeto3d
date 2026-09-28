from datetime import date, timedelta

from app import clock
from app.sale.chance import chance_for_store, peak_for_topic
from tests.sale_helpers import add_score, add_topic


def _chance(session, topic, platform="cults3d", fit=0.8, overall=6.0):
    return chance_for_store(session, topic=topic, country="BR", platform=platform, platform_name="Cults3D",
                            fit=fit, overall=overall)


def test_uses_store_row(session):
    topic = add_topic(session, "Frieren")
    add_score(session, topic, platform="cults3d", opportunity=80)
    add_score(session, topic, platform="etsy", opportunity=90)
    chance = _chance(session, topic, overall=10)
    assert chance == {"value": 80, "label": "Alta", "why": "oportunidade 80 no Cults3D (Brasil) × qualidade 10,0"}


def test_quality_factor_and_labels(session):
    topic = add_topic(session, "Frieren")
    add_score(session, topic, opportunity=80)
    assert _chance(session, topic, overall=5)["value"] == 60  # 80 × 0,75
    assert _chance(session, topic, overall=5)["label"] == "Média"
    assert _chance(session, topic, overall=None)["value"] == 60
    assert "qualidade não avaliada" in _chance(session, topic, overall=None)["why"]
    assert _chance(session, topic, overall=0)["value"] == 40
    assert _chance(session, topic, overall=0)["label"] == "Média"


def test_low_label(session):
    topic = add_topic(session, "Frieren")
    add_score(session, topic, opportunity=50)
    assert _chance(session, topic, overall=5) == {
        "value": 38, "label": "Baixa", "why": "oportunidade 50 no Cults3D (Brasil) × qualidade 5,0"}


def test_without_store_row_uses_best_row_times_fit(session):
    topic = add_topic(session, "Frieren")
    add_score(session, topic, platform="etsy", opportunity=90)
    add_score(session, topic, platform="booth", opportunity=70)
    chance = _chance(session, topic, platform="fab", fit=0.5, overall=10)
    assert chance["value"] == 45
    assert chance["why"] == "oportunidade 90 do tema no Brasil × encaixe 0,5 da loja × qualidade 10,0"


def test_only_last_day_counts(session):
    topic = add_topic(session, "Frieren")
    add_score(session, topic, opportunity=90, day=clock.today() - timedelta(days=1))
    add_score(session, topic, platform="etsy", opportunity=40)
    assert _chance(session, topic, fit=1.0, overall=10)["value"] == 40


def test_without_topic(session):
    chance = _chance(session, None)
    assert chance == {"value": None, "label": None, "why": "tema ainda não está no radar: sem dado de procura"}


def test_topic_without_score_in_country(session):
    topic = add_topic(session, "Frieren")
    chance = _chance(session, topic)
    assert chance["value"] is None
    assert chance["why"] == "o tema ainda não tem nota no Brasil"


def test_peak_for_topic(session):
    topic = add_topic(session, "Frieren")
    peak = clock.today() + timedelta(days=12)
    add_score(session, topic, opportunity=90, peak_day=peak)
    assert peak_for_topic(session, topic, "BR") == peak
    assert peak_for_topic(session, None, "BR") is None
    assert peak_for_topic(session, topic, "US") is None


def test_country_preposition(session):
    topic = add_topic(session, "Frieren")
    chance = chance_for_store(session, topic=topic, country="US", platform="etsy", platform_name="Etsy",
                              fit=0.5, overall=6)
    assert chance["why"] == "o tema ainda não tem nota nos EUA"
