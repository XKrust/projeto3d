"""Interface comum a todos os coletores de dados (fontes)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, Protocol

import httpx


@dataclass
class CollectedItem:
    """Um item bruto coletado de uma fonte, pronto para ser persistido."""

    external_id: str
    title: str
    country: str
    metric: float
    tags: list[str] = field(default_factory=list)
    url: str | None = None
    thumb_url: str | None = None
    likes: int | None = None
    downloads: int | None = None
    views: int | None = None
    comments: int | None = None
    price_usd: float | None = None


class CollectorError(Exception):
    """Erro esperado de um coletor. Mensagem em portugues, exibida na interface."""


class Collector(ABC):
    """Classe base de um coletor de dados (fonte)."""

    name: ClassVar[str]
    label: ClassVar[str]
    kind: ClassVar[str]  # "api" | "rss" | "scrape"
    platform: ClassVar[str | None] = None  # slug em Platform, se for marketplace
    needs_key: ClassVar[tuple[str, ...]] = ()  # nomes em settings["api_keys"]
    interval_minutes: ClassVar[int] = 60

    def __init__(self, settings: dict, http: httpx.Client):
        self.settings = settings
        self.http = http

    @abstractmethod
    def collect(self) -> list[CollectedItem]: ...


class ListingCounter(Protocol):
    def count_listings(self, query: str) -> int: ...
