"""Aplicacao FastAPI do Radar 3D."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.db import engine as default_engine
from app.db import init_db


def create_app(engine=None) -> FastAPI:
    """Cria a aplicacao FastAPI.

    `engine` permite injetar um engine diferente (usado nos testes, com SQLite
    em memoria). Quando omitido, usa o engine padrao (`app.db.engine`).
    """
    db_engine = engine if engine is not None else default_engine

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(db_engine)
        yield

    app = FastAPI(title="Radar 3D", lifespan=lifespan)
    app.state.engine = db_engine

    app.include_router(health.router, prefix="/api")

    return app


app = create_app()
