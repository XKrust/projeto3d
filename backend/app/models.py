"""Tabelas SQLModel - base de dados de todas as tarefas do Radar 3D."""

from datetime import date, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Source(SQLModel, table=True):
    """Estado de cada coletor (fonte de dados)."""

    name: str = Field(primary_key=True)
    # valores possiveis: never, ok, error, no_key
    status: str = "never"
    last_run: datetime | None = None
    last_error: str | None = None
    items_last_run: int = 0


class RawItem(SQLModel, table=True):
    """Item bruto coletado de uma fonte, em um pais e dia especificos."""

    __table_args__ = (
        UniqueConstraint(
            "source", "external_id", "country", "day", name="uq_rawitem_source_external_country_day"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    source: str
    external_id: str
    country: str
    day: date
    title: str
    tags_json: str = "[]"
    url: str | None = None
    thumb_url: str | None = None
    likes: int | None = None
    downloads: int | None = None
    views: int | None = None
    comments: int | None = None
    price_usd: float | None = None
    metric: float


class Topic(SQLModel, table=True):
    """Topico/tendencia agrupando itens brutos relacionados."""

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(sa_column_kwargs={"unique": True})
    name: str
    category: str = "outros"
    aliases_json: str = "[]"
    image_url: str | None = None
    reason: str | None = None
    reason_day: date | None = None
    is_candidate: bool
    created_day: date


class TopicItem(SQLModel, table=True):
    """Associacao entre um topico e um item bruto (chave primaria composta)."""

    topic_id: int = Field(foreign_key="topic.id", primary_key=True)
    raw_item_id: int = Field(foreign_key="rawitem.id", primary_key=True)


class TopicSignal(SQLModel, table=True):
    """Sinal diario de um topico, por fonte e pais."""

    __table_args__ = (
        UniqueConstraint(
            "topic_id", "source", "country", "day", name="uq_topicsignal_topic_source_country_day"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id")
    source: str
    country: str
    day: date
    value: float


class TopicListing(SQLModel, table=True):
    """Contagem diaria de anuncios/listagens de um topico em uma plataforma."""

    __table_args__ = (
        UniqueConstraint("topic_id", "platform", "day", name="uq_topiclisting_topic_platform_day"),
    )

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id")
    platform: str
    day: date
    count: int


class TopicScore(SQLModel, table=True):
    """Score calculado de um topico, por pais, plataforma e dia."""

    __table_args__ = (
        UniqueConstraint(
            "topic_id", "country", "platform", "day", name="uq_topicscore_topic_country_platform_day"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id")
    country: str
    platform: str
    day: date
    demand: float
    momentum: float
    momentum_raw: float
    saturation: float
    peak_day: date
    fit_window: float
    fit_platform: float
    opportunity: float


class Setting(SQLModel, table=True):
    """Configuracao/segredo persistido localmente (ex.: chaves de API)."""

    key: str = Field(primary_key=True)
    value_json: str


class Platform(SQLModel, table=True):
    """Cadastro de plataformas de venda (taxas, mercados, forca por pais)."""

    slug: str = Field(primary_key=True)
    name: str
    markets_json: str
    fee_pct: float | None = None
    strength_json: str
    notes: str = ""


class HypeRelease(SQLModel, table=True):
    """Lançamento (anime, filme, série, jogo) vindo dos coletores de hype.
    Upsert por fonte/external_id/país; `updated_day` marca a última coleta."""

    __table_args__ = (
        UniqueConstraint("source", "external_id", "country", name="uq_hyperelease_source_external_country"),
    )

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    external_id: str
    kind: str
    title: str
    release_date: date | None = None
    popularity: float = 0.0
    country: str
    url: str | None = None
    image_url: str | None = None
    aliases_json: str = "[]"
    characters_json: str = "[]"
    updated_day: date
