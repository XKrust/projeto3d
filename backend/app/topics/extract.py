"""Extracao diaria de topicos a partir dos `RawItem` coletados.

Algoritmo (fixo, ver `docs/arquitetura.md#formacao-de-topicos`):
1. Carrega os `RawItem` de `day`.
2. Topicos-semente: todas as entidades de `entities.yaml` (mesmo sem itens) e um
   termo inteiro por titulo do Google Trends.
3. Candidatos: unigramas/bigramas (fora do Trends) em >=3 itens de >=2 fontes.
4. Casamento: cada item contra nome+aliases de cada topico (limite de palavra
   para frases latinas, substring para frases com CJK).
5. Filtro de ruido: um termo do Trends que nao e entidade so vira/continua
   topico se casou com >=1 item de outra fonte nos ultimos 7 dias (day-6..day).
6. Sinais: upsert de `TopicSignal` por (topico, fonte, pais, dia) com `value` =
   soma de `metric` dos itens casados daquela fonte/pais.
7. `slug`/`image_url`/categoria do topico sao definidos na criacao.

Idempotente: rodar duas vezes no mesmo dia produz o mesmo `TopicItem`/`TopicSignal`.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml
from sqlmodel import Session, select

from app.models import RawItem, Topic, TopicItem, TopicSignal
from app.topics.category import guess_category
from app.topics.normalize import is_cjk, matches_phrase, normalize, tokens

_SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
_ENTITIES_FILE = _SEED_DIR / "entities.yaml"

TRENDS_SOURCE = "google_trends"
PLATFORM_SOURCES = frozenset({"sketchfab", "cults3d", "printables"})

_CANDIDATE_MIN_ITEMS = 3
_CANDIDATE_MIN_SOURCES = 2
_NOISE_WINDOW_DAYS = 7


def _load_entities() -> list[dict]:
    with open(_ENTITIES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _item_text(item: RawItem) -> str:
    """Titulo + tags de um item, para normalizacao/casamento (`titulo + tags`)."""
    tags = json.loads(item.tags_json or "[]")
    return " ".join([item.title, *tags])


def _slugify(name: str) -> str:
    return normalize(name).replace(" ", "-")


@dataclass
class _Draft:
    """Um topico ainda em memoria, durante a extracao de um dia."""

    name: str
    aliases: list[str]  # ja normalizados; aliases[0] e o proprio nome normalizado
    is_entity: bool = False
    is_candidate: bool = False
    is_trends_term: bool = False
    entity_category: str | None = None
    matched_items: list[RawItem] = field(default_factory=list)


def _seed_entities(drafts: dict[str, _Draft]) -> set[str]:
    """Registra as entidades de `entities.yaml` como topicos-semente (mesmo sem itens).

    Retorna o conjunto de nome+aliases normalizados de todas as entidades, usado
    para nao gerar candidatos duplicados de termos ja cobertos por uma entidade.
    """
    entity_alias_pool: set[str] = set()
    for entity in _load_entities():
        key = normalize(entity["name"])
        aliases = [normalize(a) for a in entity.get("aliases", [])]
        drafts[key] = _Draft(
            name=entity["name"],
            aliases=[key, *aliases],
            is_entity=True,
            entity_category=entity.get("category") or "outros",
        )
        entity_alias_pool.add(key)
        entity_alias_pool.update(aliases)
    return entity_alias_pool


def _seed_trends_terms(drafts: dict[str, _Draft], items: list[RawItem]) -> None:
    """Cada titulo do Google Trends vira um termo-semente inteiro."""
    for item in items:
        if item.source != TRENDS_SOURCE:
            continue
        key = normalize(item.title)
        if key in drafts:
            continue
        drafts[key] = _Draft(name=item.title, aliases=[key], is_trends_term=True)


def _seed_candidates(drafts: dict[str, _Draft], items: list[RawItem], entity_alias_pool: set[str]) -> None:
    """Unigramas/bigramas fora do Trends em >=3 itens de >=2 fontes viram candidatos."""
    ngram_items: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for item in items:
        if item.source == TRENDS_SOURCE:
            continue
        toks = tokens(_item_text(item))
        grams = set(toks) | {f"{a} {b}" for a, b in zip(toks, toks[1:])}
        for gram in grams:
            ngram_items[gram][item.source].add(item.id)

    for gram, by_source in ngram_items.items():
        if gram in drafts or gram in entity_alias_pool:
            continue
        total_ids = {item_id for ids in by_source.values() for item_id in ids}
        if len(total_ids) >= _CANDIDATE_MIN_ITEMS and len(by_source) >= _CANDIDATE_MIN_SOURCES:
            name = gram if is_cjk(gram) else gram.title()
            drafts[gram] = _Draft(name=name, aliases=[gram], is_candidate=True)


def _match_items(drafts: dict[str, _Draft], items: list[RawItem]) -> None:
    """Casa cada item contra nome+aliases de cada topico, gravando o casamento em memoria."""
    for item in items:
        haystack = normalize(_item_text(item))
        for draft in drafts.values():
            if any(matches_phrase(haystack, alias) for alias in draft.aliases):
                draft.matched_items.append(item)


def _passes_noise_filter(
    session: Session, draft: _Draft, day: date, existing_topic_id: int | None
) -> bool:
    """Um termo do Trends (nao entidade) so vira/continua topico se casou com >=1
    item de outra fonte hoje, ou nos ultimos 7 dias (day-6..day-1) se ja existia."""
    if any(item.source != TRENDS_SOURCE for item in draft.matched_items):
        return True
    if existing_topic_id is None:
        return False

    window_start = day - timedelta(days=_NOISE_WINDOW_DAYS - 1)
    stmt = (
        select(TopicItem.raw_item_id)
        .join(RawItem, RawItem.id == TopicItem.raw_item_id)
        .where(
            TopicItem.topic_id == existing_topic_id,
            RawItem.source != TRENDS_SOURCE,
            RawItem.day >= window_start,
            RawItem.day < day,
        )
        .limit(1)
    )
    return session.exec(stmt).first() is not None


def _pick_image(matched_items: list[RawItem]) -> str | None:
    """Primeiro `thumb_url` de item de plataforma; se nao houver, o do Trends."""
    for item in matched_items:
        if item.source in PLATFORM_SOURCES and item.thumb_url:
            return item.thumb_url
    for item in matched_items:
        if item.source == TRENDS_SOURCE and item.thumb_url:
            return item.thumb_url
    return None


def _create_topic(session: Session, draft: _Draft, slug: str, day: date) -> Topic:
    if draft.is_entity:
        category = draft.entity_category or "outros"
    else:
        category = guess_category([item.title for item in draft.matched_items])

    topic = Topic(
        slug=slug,
        name=draft.name,
        category=category,
        aliases_json=json.dumps(draft.aliases[1:]),
        image_url=_pick_image(draft.matched_items),
        is_candidate=draft.is_candidate,
        created_day=day,
    )
    session.add(topic)
    session.flush()
    return topic


def _sync_topic_items(session: Session, topic: Topic, matched_items: list[RawItem]) -> None:
    for item in matched_items:
        existing_link = session.exec(
            select(TopicItem).where(
                TopicItem.topic_id == topic.id, TopicItem.raw_item_id == item.id
            )
        ).first()
        if existing_link is None:
            session.add(TopicItem(topic_id=topic.id, raw_item_id=item.id))


def _sync_topic_signals(
    session: Session, topic: Topic, matched_items: list[RawItem], day: date
) -> bool:
    """Upsert de `TopicSignal` por (fonte, pais). Retorna se algum sinal foi gravado."""
    signal_values: dict[tuple[str, str], float] = defaultdict(float)
    for item in matched_items:
        signal_values[(item.source, item.country)] += item.metric

    for (source, country), value in signal_values.items():
        existing_signal = session.exec(
            select(TopicSignal).where(
                TopicSignal.topic_id == topic.id,
                TopicSignal.source == source,
                TopicSignal.country == country,
                TopicSignal.day == day,
            )
        ).first()
        if existing_signal is None:
            session.add(
                TopicSignal(topic_id=topic.id, source=source, country=country, day=day, value=value)
            )
        else:
            existing_signal.value = value
            session.add(existing_signal)

    return bool(signal_values)


def extract_topics(session: Session, day: date) -> int:
    """Extrai topicos, `TopicItem` e `TopicSignal` de `day`. Retorna o numero de
    topicos com sinal gravado hoje. Ver o algoritmo fixo no topo do arquivo."""
    items = list(session.exec(select(RawItem).where(RawItem.day == day)))

    drafts: dict[str, _Draft] = {}
    entity_alias_pool = _seed_entities(drafts)
    _seed_trends_terms(drafts, items)
    _seed_candidates(drafts, items, entity_alias_pool)

    _match_items(drafts, items)

    topics_with_signal: set[int] = set()

    for draft in drafts.values():
        slug = _slugify(draft.name)
        topic = session.exec(select(Topic).where(Topic.slug == slug)).first()

        if draft.is_trends_term and not _passes_noise_filter(
            session, draft, day, topic.id if topic else None
        ):
            continue

        if topic is None:
            if not draft.is_entity and not draft.matched_items:
                # Candidatos e termos do Trends so existem se casaram com algo;
                # entidades sao semeadas mesmo sem itens (regra 2).
                continue
            topic = _create_topic(session, draft, slug, day)

        _sync_topic_items(session, topic, draft.matched_items)
        if _sync_topic_signals(session, topic, draft.matched_items, day):
            topics_with_signal.add(topic.id)

    session.commit()
    return len(topics_with_signal)
