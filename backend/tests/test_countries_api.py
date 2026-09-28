from datetime import date, timedelta

from sqlmodel import Session

from app.models import CountryRank, Topic, TopicScore
from app.platforms import seed_platforms
from app.settings_store import update_settings

DAY = date(2026, 9, 27)


def _topic(session, name):
    topic = Topic(slug=name.lower().replace(" ", "-"), name=name, category="anime",
                  is_candidate=False, created_day=DAY)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def _score(session, topic, *, country="BR", platform="cults3d", opportunity=50.0,
           fit_platform=1.0, day=DAY):
    session.add(
        TopicScore(topic_id=topic.id, country=country, platform=platform, day=day,
                   demand=50, momentum=50, momentum_raw=0, saturation=50, peak_day=day,
                   fit_window=1, fit_platform=fit_platform, opportunity=opportunity)
    )
    session.commit()


def _countries(client):
    return {c["code"]: c for c in client.get("/api/countries").json()}


def test_countries_without_ranking_keep_the_default_order(client):
    body = client.get("/api/countries").json()

    assert [c["code"] for c in body][:7] == ["BR", "US", "GB", "DE", "FR", "ES", "JP"]
    assert body[0]["name"] == "Brasil"


def test_country_shows_its_top3_themes_instead_of_a_percentage(client, engine):
    # A "% de chance" era a média do top 5 de percentis e dava ~80% em todo país:
    # não ajudava. Agora cada país mostra os 3 melhores temas.
    with Session(engine) as session:
        for i, opp in enumerate([90, 80, 70, 60, 50, 10]):
            _score(session, _topic(session, f"Tema {i}"), opportunity=opp)

    br = _countries(client)["BR"]

    assert "chance" not in br
    assert br["top_topics"] == ["Tema 0", "Tema 1", "Tema 2"]
    assert br["topics"] == 6


def test_country_lists_its_strongest_stores(client, engine):
    with Session(engine) as session:
        seed_platforms(session)

    countries = _countries(client)

    assert countries["BR"]["stores"][0] == "Cults3D"
    assert "Mercado Livre" not in countries["BR"]["stores"]  # vende peça física, não arquivo
    assert countries["JP"]["stores"][0] == "BOOTH"
    assert "Sketchfab" not in countries["US"]["stores"]  # loja fechada
    assert len(countries["US"]["stores"]) == 3


def test_country_without_scores_has_no_themes(client):
    jp = _countries(client)["JP"]

    assert jp["top_topics"] == []
    assert jp["topics"] == 0


def test_topic_counted_once_per_country(client, engine):
    with Session(engine) as session:
        topic = _topic(session, "Tema")
        _score(session, topic, platform="cults3d", opportunity=80)
        _score(session, topic, platform="etsy", opportunity=40, fit_platform=0.5)

    br = _countries(client)["BR"]

    assert br["topics"] == 1
    assert br["top_topics"] == ["Tema"]


def test_only_latest_day_counts(client, engine):
    with Session(engine) as session:
        old = _topic(session, "Antigo")
        _score(session, old, opportunity=99, day=DAY - timedelta(days=1))
        _score(session, _topic(session, "Hoje"), opportunity=40)

    assert _countries(client)["BR"]["top_topics"] == ["Hoje"]


def test_country_active_flag(client, engine):
    with Session(engine) as session:
        update_settings(session, {"countries": ["BR", "JP"]})

    countries = _countries(client)

    assert countries["BR"]["active"] is True
    assert countries["JP"]["active"] is True
    assert countries["US"]["active"] is False


def test_inactive_country_has_no_themes_even_with_old_scores(client, engine):
    with Session(engine) as session:
        topic = _topic(session, "Frieren")
        _score(session, topic, country="US", opportunity=80.0)
        update_settings(session, {"countries": ["BR"]})

    us = _countries(client)["US"]

    assert us["active"] is False
    assert us["top_topics"] == []


def test_closed_store_scores_do_not_count(client, engine):
    with Session(engine) as session:
        seed_platforms(session)
        closed_only = _topic(session, "So Sketchfab")
        _score(session, closed_only, platform="sketchfab", opportunity=95.0)
        _score(session, _topic(session, "Frieren"), platform="cults3d", opportunity=60.0)

    assert _countries(client)["BR"]["top_topics"] == ["Frieren"]


def _rank(session, country, day, position, score=50.0):
    session.add(CountryRank(day=day, country=country, score=score, position=position, audience=50, demand=50,
                            payment=1.0))
    session.commit()


def test_countries_come_ranked_with_weekly_movement(client, engine):
    with Session(engine) as session:
        update_settings(session, {"countries": ["BR", "US", "JP"]})
        for d in range(8):
            day = DAY - timedelta(days=7 - d)
            # Há 7 dias: JP 1º, US 2º, BR 3º. De 5 dias atrás até hoje: US 1º.
            if d < 2:
                order = ["JP", "US", "BR"]
            else:
                order = ["US", "BR", "JP"]
            for pos, code in enumerate(order, start=1):
                _rank(session, code, day, pos)

    body = client.get("/api/countries").json()

    assert [c["code"] for c in body[:3]] == ["US", "BR", "JP"]
    us, br, jp = body[:3]
    assert us["rank"]["position"] == 1
    assert us["rank"]["change_week"] == 1  # subiu 1 posição em 7 dias
    assert us["rank"]["days_at_position"] == 6  # 1º há 6 dias (inclui hoje)
    assert br["rank"]["change_week"] == 1
    assert jp["rank"]["change_week"] == -2
    assert set(us["rank"]) >= {"score", "audience", "demand", "payment"}
    assert body[3]["rank"] is None  # país inativo vem depois, sem posição


def test_all_fifteen_countries_are_listed(client):
    codes = [c["code"] for c in client.get("/api/countries").json()]

    assert set(codes) == {"BR", "US", "GB", "DE", "FR", "ES", "JP", "RU", "BY", "MX", "IT", "CA", "AU", "PL", "NL"}
