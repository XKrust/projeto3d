"""Tarefas que só podem rodar 1x por dia (regra de scraping educado)."""

from datetime import date

from sqlmodel import Session, select

from app.models import DailyAttempt


def claim_daily(session: Session, task: str, day: date) -> bool:
    """Registra a tentativa de `task` hoje. Devolve False se já foi tentada hoje."""
    exists = session.exec(
        select(DailyAttempt.id).where(DailyAttempt.task == task, DailyAttempt.day == day)
    ).first()
    if exists is not None:
        return False
    session.add(DailyAttempt(task=task, day=day))
    session.commit()
    return True
