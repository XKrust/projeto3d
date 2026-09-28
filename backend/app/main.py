"""Aplicacao FastAPI do Radar 3D."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from app import scheduler as scheduler_mod
from app.api import analyze as analyze_api
from app.api import countries as countries_api
from app.api import health
from app.api import hype as hype_api
from app.api import radar as radar_api
from app.api import seasonal as seasonal_api
from app.api import settings as settings_api
from app.api import sources as sources_api
from app.db import engine as default_engine
from app.db import init_db
from app.platforms import seed_platforms


def create_app(engine=None) -> FastAPI:
    """Cria a aplicacao FastAPI.

    `engine` permite injetar um engine diferente (usado nos testes, com SQLite
    em memoria). Quando omitido, usa o engine padrao (`app.db.engine`).
    """
    db_engine = engine if engine is not None else default_engine

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(db_engine)
        with Session(db_engine) as session:
            seed_platforms(session)

        # RADAR_NO_SCHEDULER=1 (usado nos testes) nao inicia o agendador.
        scheduler = None
        if os.environ.get("RADAR_NO_SCHEDULER") != "1":
            scheduler = scheduler_mod.start_scheduler(app.state.session_factory)
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)

    app = FastAPI(title="Radar 3D", lifespan=lifespan)
    app.state.engine = db_engine
    app.state.session_factory = lambda: Session(db_engine)

    app.include_router(health.router, prefix="/api")
    app.include_router(settings_api.router, prefix="/api")
    app.include_router(sources_api.router, prefix="/api")
    app.include_router(radar_api.router, prefix="/api")
    app.include_router(seasonal_api.router, prefix="/api")
    app.include_router(hype_api.router, prefix="/api")
    app.include_router(countries_api.router, prefix="/api")
    app.include_router(analyze_api.router, prefix="/api")

    return app


app = create_app()
