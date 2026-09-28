"""Engine e sessao SQLModel para o banco SQLite local."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import DB_URL
from app import models  # noqa: F401  garante que as tabelas sejam registradas nos metadados

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})


# Colunas criadas depois da primeira versao do banco: (tabela, coluna, definicao SQL).
# `create_all` nao altera tabela existente, entao elas entram com ALTER TABLE.
_ADDED_COLUMNS = [
    ("platform", "sells", "BOOLEAN NOT NULL DEFAULT 1"),
    ("platform", "categories_json", "VARCHAR NOT NULL DEFAULT '[]'"),
    ("platform", "edited", "BOOLEAN NOT NULL DEFAULT 0"),
    ("countryrank", "demand_measured", "BOOLEAN NOT NULL DEFAULT 0"),
    ("analysis", "sale_json", "VARCHAR"),
    ("analysis", "sale_at", "DATETIME"),
]


def init_db(engine) -> None:
    """Cria as tabelas que ainda nao existem e acrescenta as colunas novas."""
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        for table, column, definition in _ADDED_COLUMNS:
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def get_session() -> Iterator[Session]:
    """Dependencia FastAPI: fornece uma sessao do banco por requisicao."""
    with Session(engine) as session:
        yield session
