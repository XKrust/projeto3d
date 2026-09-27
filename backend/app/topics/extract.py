"""Extracao diaria de topicos a partir dos `RawItem` coletados.

Algoritmo (fixo, ver `docs/arquitetura.md#formacao-de-topicos`):
1. Carrega os `RawItem` de `day`.
2. Todo `Topic` ja existente no banco (entidade, termo do Trends ou candidato de
   dias anteriores) e trazido para a rodada primeiro, usando seu nome e
   `aliases_json` atual (que pode ter ganhado aliases de uma fusao na Tarefa
   13). Isso garante que um topico continua recebendo `TopicItem`/`TopicSignal`
   mesmo em dias em que nao seria "descoberto" de novo pelas regras 3/4, e que
   um termo de hoje que so bate com um alias (nao o nome) de um topico
   existente resolve para ele em vez de criar um duplicado.
3. **Topicos-semente:** todas as entidades de `entities.yaml` (mesmo sem itens)
   e um termo inteiro por titulo do Google Trends. Um termo do Trends que bate
   com o nome/alias de uma entidade (ou de um topico ja existente) nao vira um
   topico separado.
4. **Candidatos:** unigramas/bigramas (fora do Trends) em >=3 itens de >=2
   fontes, tambem excluindo termos ja cobertos por uma entidade ou topico
   existente.
5. Todo draft (semente de hoje ou topico existente) e indexado pelo `slug` do
   seu nome; duas sementes cujo nome normalizado difere mas cujo slug colide
   (ex.: "Spider-Man" e "Spider Man") sao fundidas num so draft, nunca viram
   dois `Topic` com o mesmo slug (o que violaria a unicidade e derrubaria a
   rodada inteira).
6. **Casamento:** cada item contra nome+aliases de cada draft (limite de
   palavra para frases latinas, substring para frases com CJK).
7. **Filtro de ruido:** um termo do Trends que nao e entidade nem topico-
   candidato so vira/continua topico se casou com >=1 item de outra fonte
   hoje, ou com algum `RawItem` de outra fonte nos ultimos 7 dias
   (day-6..day-1). Um topico-candidato (novo ou ja existente) nunca passa por
   esse filtro: e casado e recebe sinal todo dia, sem reconferir o limiar de
   mineracao.
8. **Sinais:** upsert de `TopicSignal` por (topico, fonte, pais, dia) com
   `value` = soma de `metric` dos itens casados daquela fonte/pais.
9. `slug` e definido na criacao. `image_url`/`categoria` sao definidos na
   criacao e, se ainda vazios (`image_url is None` / `category == "outros"`),
   preenchidos em dias seguintes assim que houver item casado que os resolva —
   sem nunca sobrescrever um valor ja definido (edicao manual ou fusao).

Idempotente: rodar duas vezes no mesmo dia produz o mesmo `TopicItem`/`TopicSignal`.
"""

import json
from collections import defaultdict
from collections.abc import Callable
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
PLATFORM_SOURCES = frozenset({"sketchfab", "cults3d", "printables", "booth", "artstation", "etsy", "thingiverse", "myminifactory", "cgtrader"})

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
    """Um topico ainda em memoria, durante a extracao de um dia. Indexado por
    slug em `drafts` — nunca duas instancias com o mesmo slug (regra 5)."""

    name: str
    aliases: list[str]  # ja normalizados; aliases[0] e o proprio nome normalizado
    is_entity: bool = False
    is_candidate: bool = False
    is_trends_term: bool = False
    entity_category: str | None = None
    existing_topic: Topic | None = None
    matched_items: list[RawItem] = field(default_factory=list)


def _register(drafts: dict[str, _Draft], slug: str, alias: str, make: Callable[[], _Draft]) -> _Draft:
    """Registra `alias` no draft de `slug`, criando-o com `make()` se ainda nao
    existir, ou apenas somando o alias se ja existir (nunca sobrescreve flags
    de um draft ja registrado — regra 5)."""
    draft = drafts.get(slug)
    if draft is None:
        draft = make()
        drafts[slug] = draft
    elif alias not in draft.aliases:
        draft.aliases.append(alias)
    return draft


def _seed_entities(drafts: dict[str, _Draft]) -> set[str]:
    """Registra as entidades de `entities.yaml` como topicos-semente (mesmo sem itens).

    Retorna o conjunto de nome+aliases normalizados de todas as entidades, usado
    para nao gerar termos do Trends nem candidatos duplicados de algo ja coberto
    por uma entidade.
    """
    entity_alias_pool: set[str] = set()
    for entity in _load_entities():
        name = entity["name"]
        key = normalize(name)
        aliases = [normalize(a) for a in entity.get("aliases", [])]
        slug = _slugify(name)

        draft = _register(
            drafts,
            slug,
            key,
            lambda name=name, key=key, aliases=aliases, entity=entity: _Draft(
                name=name,
                aliases=[key, *aliases],
                is_entity=True,
                entity_category=entity.get("category") or "outros",
            ),
        )
        for alias in aliases:
            if alias not in draft.aliases:
                draft.aliases.append(alias)

        entity_alias_pool.add(key)
        entity_alias_pool.update(aliases)
    return entity_alias_pool


def _seed_existing_topics(session: Session, drafts: dict[str, _Draft]) -> set[str]:
    """Traz todo `Topic` ja existente no banco para dentro de `drafts`, **antes**
    de semear termos do Trends/candidatos do dia (regra 2).

    Um topico cujo slug ja foi semeado (por ora, so uma entidade pode ter sido)
    so ganha o vinculo `existing_topic` e tem seus aliases atuais incorporados,
    sem alterar as flags do draft (uma entidade continua entidade). Um topico
    cujo slug ainda nao foi semeado vira um draft novo, com `is_candidate`
    herdado do banco e `is_trends_term = not is_candidate` (unica forma hoje de
    um topico nao-entidade existir sem ser candidato).

    Retorna o pool de nome+aliases normalizados de todo topico existente, para
    que um termo de hoje que bata com um alias dele (nao so com o nome) seja
    resolvido para ele em vez de criar um duplicado.
    """
    existing_alias_pool: set[str] = set()

    for topic in session.exec(select(Topic)).all():
        aliases = [normalize(topic.name)]
        aliases.extend(normalize(a) for a in json.loads(topic.aliases_json or "[]"))
        existing_alias_pool.update(aliases)

        draft = drafts.get(topic.slug)
        if draft is not None:
            draft.existing_topic = topic
            for alias in aliases:
                if alias not in draft.aliases:
                    draft.aliases.append(alias)
            continue

        drafts[topic.slug] = _Draft(
            name=topic.name,
            aliases=aliases,
            is_candidate=topic.is_candidate,
            is_trends_term=not topic.is_candidate,
            existing_topic=topic,
        )

    return existing_alias_pool


def _seed_trends_terms(drafts: dict[str, _Draft], items: list[RawItem], known_alias_pool: set[str]) -> None:
    """Cada titulo do Google Trends vira um termo-semente inteiro, a nao ser que
    bata com o nome/alias de uma entidade ou de um topico ja existente (esse e
    que casa com o item). Duas sementes cujo slug colide (ex.: hifen vs espaco)
    sao fundidas num so draft."""
    for item in items:
        if item.source != TRENDS_SOURCE:
            continue
        key = normalize(item.title)
        if key in known_alias_pool:
            continue
        slug = _slugify(item.title)
        _register(drafts, slug, key, lambda item=item, key=key: _Draft(name=item.title, aliases=[key], is_trends_term=True))


def _seed_candidates(drafts: dict[str, _Draft], items: list[RawItem], known_alias_pool: set[str]) -> None:
    """Unigramas/bigramas fora do Trends em >=3 itens de >=2 fontes viram
    candidatos, a nao ser que ja batam com uma entidade ou topico existente."""
    ngram_items: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for item in items:
        if item.source == TRENDS_SOURCE:
            continue
        toks = tokens(_item_text(item))
        grams = set(toks) | {f"{a} {b}" for a, b in zip(toks, toks[1:])}
        for gram in grams:
            ngram_items[gram][item.source].add(item.id)

    for gram, by_source in ngram_items.items():
        if gram in known_alias_pool:
            continue
        total_ids = {item_id for ids in by_source.values() for item_id in ids}
        if len(total_ids) >= _CANDIDATE_MIN_ITEMS and len(by_source) >= _CANDIDATE_MIN_SOURCES:
            name = gram if is_cjk(gram) else gram.title()
            slug = _slugify(name)
            _register(drafts, slug, gram, lambda name=name, gram=gram: _Draft(name=name, aliases=[gram], is_candidate=True))


def _match_items(drafts: dict[str, _Draft], items: list[RawItem]) -> None:
    """Casa cada item contra nome+aliases de cada topico, gravando o casamento em memoria."""
    for item in items:
        haystack = normalize(_item_text(item))
        for draft in drafts.values():
            if any(matches_phrase(haystack, alias) for alias in draft.aliases):
                draft.matched_items.append(item)


def _load_history_haystacks(session: Session, day: date) -> list[str]:
    """Texto normalizado (titulo+tags) dos itens de outras fontes dos ultimos 7
    dias (day-6..day-1), usado pelo filtro de ruido dos termos do Trends."""
    window_start = day - timedelta(days=_NOISE_WINDOW_DAYS - 1)
    history_items = session.exec(
        select(RawItem).where(
            RawItem.source != TRENDS_SOURCE,
            RawItem.day >= window_start,
            RawItem.day < day,
        )
    ).all()
    return [normalize(_item_text(item)) for item in history_items]


def _passes_noise_filter(draft: _Draft, history_haystacks: list[str]) -> bool:
    """Um termo do Trends (nao entidade) so vira/continua topico se casou com
    >=1 item de outra fonte hoje, ou com algum item de outra fonte nos ultimos
    7 dias (`history_haystacks`, ja restrito a day-6..day-1)."""
    if any(item.source != TRENDS_SOURCE for item in draft.matched_items):
        return True
    return any(
        matches_phrase(haystack, alias) for haystack in history_haystacks for alias in draft.aliases
    )


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
    category = draft.entity_category if draft.is_entity else "outros"
    topic = Topic(
        slug=slug,
        name=draft.name,
        category=category or "outros",
        aliases_json=json.dumps(draft.aliases[1:]),
        image_url=None,
        is_candidate=draft.is_candidate,
        created_day=day,
    )
    session.add(topic)
    session.flush()
    return topic


def _backfill_topic_metadata(topic: Topic, draft: _Draft) -> None:
    """Preenche `image_url`/`category` se ainda estiverem vazios (ex.: entidade
    sem nenhum item casado no dia em que foi criada). Nunca sobrescreve um
    valor ja definido (seja da criacao, de edicao manual ou de fusao)."""
    if topic.image_url is None:
        image = _pick_image(draft.matched_items)
        if image:
            topic.image_url = image

    if not draft.is_entity and topic.category == "outros" and draft.matched_items:
        category = guess_category([item.title for item in draft.matched_items])
        if category != "outros":
            topic.category = category


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
    existing_alias_pool = _seed_existing_topics(session, drafts)
    known_alias_pool = entity_alias_pool | existing_alias_pool
    _seed_trends_terms(drafts, items, known_alias_pool)
    _seed_candidates(drafts, items, known_alias_pool)

    _match_items(drafts, items)
    history_haystacks = _load_history_haystacks(session, day)

    topics_with_signal: set[int] = set()

    for slug, draft in drafts.items():
        if draft.is_trends_term and not _passes_noise_filter(draft, history_haystacks):
            continue

        topic = draft.existing_topic
        if topic is None:
            if not draft.is_entity and not draft.matched_items:
                # Candidatos e termos do Trends so existem se casaram com algo;
                # entidades sao semeadas mesmo sem itens (regra 3).
                continue
            topic = _create_topic(session, draft, slug, day)

        _backfill_topic_metadata(topic, draft)
        _sync_topic_items(session, topic, draft.matched_items)
        if _sync_topic_signals(session, topic, draft.matched_items, day):
            topics_with_signal.add(topic.id)

    session.commit()
    return len(topics_with_signal)
