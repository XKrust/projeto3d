"""Data/hora de negocio. Modulos simples para permitir monkeypatch nos testes."""

from datetime import date, datetime


def today() -> date:
    """Data local de hoje. Usada como fonte unica de verdade para `day` no banco."""
    return datetime.now().date()


def now() -> datetime:
    """Data/hora local atual."""
    return datetime.now()
