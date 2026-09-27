from datetime import date

from app.collectors.base import CollectorError
from app.hype.competition import update_hype_listings
from app.hype.seasonal_ideas import update_seasonal_listings
from app.models import HypeRelease
from app.pipeline import update_listings
from app.models import Topic, TopicSignal

DAY = date(2026, 9, 27)


class AlwaysFails:
    def __init__(self):
        self.queries = []

    def count_listings(self, query):
        self.queries.append(query)
        raise CollectorError("Loja bloqueou")


def test_hype_listings_not_retried_same_day_when_everything_fails(session):
    session.add(HypeRelease(source="anilist", external_id="1", kind="anime", title="Frieren",
                            release_date=DAY, popularity=10, country="GLOBAL", updated_day=DAY))
    session.commit()
    counter = AlwaysFails()

    update_hype_listings(session, {"booth": counter}, DAY)
    first = len(counter.queries)
    update_hype_listings(session, {"booth": counter}, DAY)

    assert first == 1
    assert len(counter.queries) == first  # nada de tentar de novo no mesmo dia


def test_seasonal_listings_not_retried_same_day_when_everything_fails(session):
    counter = AlwaysFails()

    update_seasonal_listings(session, {"booth": counter}, DAY, lead_days=21, modeling_days=7)
    first = len(counter.queries)
    update_seasonal_listings(session, {"booth": counter}, DAY, lead_days=21, modeling_days=7)

    assert first == 3  # abandona a plataforma após 3 falhas seguidas
    assert len(counter.queries) == first


def test_radar_listings_not_retried_same_day_when_everything_fails(session):
    topic = Topic(slug="tema", name="Tema", is_candidate=False, created_day=DAY)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    session.add(TopicSignal(topic_id=topic.id, source="google_trends", country="BR", day=DAY, value=10))
    session.commit()
    counter = AlwaysFails()

    update_listings(session, {"booth": counter}, DAY, 50)
    update_listings(session, {"booth": counter}, DAY, 50)

    assert counter.queries == ["Tema"]
