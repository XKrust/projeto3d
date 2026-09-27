"""Interface comum a todos os coletores de dados (fontes)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
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


@dataclass
class Release:
    """Um lançamento (anime, filme, série ou jogo) coletado por uma fonte de hype.

    `release_date` é `None` quando a fonte não tem a data exata (só ano/mês).
    `characters` são dicts `{name, native, favourites, image_url}` (só anime).
    """

    external_id: str
    kind: str  # "anime" | "filme" | "serie" | "jogo"
    title: str
    release_date: date | None
    popularity: float
    country: str
    url: str | None = None
    image_url: str | None = None
    aliases: list[str] = field(default_factory=list)
    characters: list[dict] = field(default_factory=list)


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

    def releases(self) -> list[Release]:
        """Lançamentos encontrados no último `collect()` (só coletores de hype).
        O runner grava em `HypeRelease` depois de um `collect()` bem-sucedido."""
        return []


class ListingCounter(Protocol):
    def count_listings(self, query: str) -> int: ...
