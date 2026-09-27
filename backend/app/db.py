"""Engine e sessao SQLModel para o banco SQLite local."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import DB_URL
from app import models  # noqa: F401  garante que as tabelas sejam registradas nos metadados

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})


def init_db(engine) -> None:
    """Cria as tabelas que ainda nao existem no banco."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """Dependencia FastAPI: fornece uma sessao do banco por requisicao."""
    with Session(engine) as session:
        yield session
