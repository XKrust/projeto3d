import os

# Nunca iniciar o agendador (thread do APScheduler) durante os testes.
os.environ["RADAR_NO_SCHEDULER"] = "1"

import pytest  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import init_db, get_session
from app.main import create_app


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)


@pytest.fixture()
def session(engine):
    with Session(engine) as sess:
        yield sess


@pytest.fixture()
def client(engine):
    app = create_app(engine=engine)

    def override_get_session():
        with Session(engine) as sess:
            yield sess

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
