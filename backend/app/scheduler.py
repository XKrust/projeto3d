"""Agendador (APScheduler 3.x): dispara o ciclo de coleta + pipeline periodicamente."""

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.pipeline import run_after_cycle
from app.runner import start_cycle_in_background

INTERVAL_MINUTES = 10
FIRST_RUN_DELAY_SECONDS = 30


def run_scheduled_cycle(session_factory) -> None:
    """Um tique do agendador: inicia o ciclo em segundo plano (cada coletor so
    roda se estiver no horario) e o pipeline ao final. Se ja houver um ciclo em
    andamento, nao faz nada."""
    start_cycle_in_background(session_factory, after=run_after_cycle)


def build_scheduler(session_factory) -> BackgroundScheduler:
    """Monta o agendador (sem iniciar): um job a cada 10 minutos e uma execucao
    30 segundos depois de iniciar."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_scheduled_cycle,
        "interval",
        minutes=INTERVAL_MINUTES,
        args=[session_factory],
        id="coleta_periodica",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_scheduled_cycle,
        "date",
        run_date=datetime.now() + timedelta(seconds=FIRST_RUN_DELAY_SECONDS),
        args=[session_factory],
        id="coleta_inicial",
    )
    return scheduler


def start_scheduler(session_factory) -> BackgroundScheduler:
    """Monta e inicia o agendador. Quem chama deve fazer `shutdown()` ao sair."""
    scheduler = build_scheduler(session_factory)
    scheduler.start()
    return scheduler
