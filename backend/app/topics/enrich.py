"""Enriquecimento diario de topicos via IA (Gemini, opcional): fusao de duplicatas e
motivo do hype (`Topic.reason`). Roda ao final do pipeline (`app/pipeline.py`), uma vez
por dia, so quando ha uma chave de Gemini configurada (`app.ai.provider.get_text_provider`).

Um unico prompt (`PROMPT_TEMPLATE`) leva os `top_n` topicos principais (slug, nome e ate
3 titulos de exemplo) e pede duas coisas ao modelo:
1. fundir nomes que sao o mesmo personagem, obra ou produto (`merges`);
2. um motivo de 1 frase, em portugues, por que o topico esta em alta, sem inventar fatos
   que nao estejam nos titulos (`reasons`).

`enrich_topics` nunca deixa uma excecao do provedor (cota excedida, rede, JSON invalido)
subir para o pipeline: registra em log e devolve `(0, 0)`. So marca `last_enrich_day`
(gravado como `Setting`, fora de `settings_store.DEFAULTS`) depois de aplicar uma resposta
com sucesso, para que uma falha seja tentada de novo no proximo ciclo do mesmo dia.
"""

import json
import logging
from datetime import date

from sqlmodel import Session, select

from app.ai.provider import AIQuotaError, TextProvider
from app.models import RawItem, Setting, Topic, TopicItem, TopicListing, TopicScore, TopicSignal
from app.topics.extract import _load_entities, _slugify
from app.topics.normalize import normalize

logger = logging.getLogger(__name__)

LAST_ENRICH_DAY_KEY = "last_enrich_day"
REASON_MAX_LEN = 140
EXAMPLE_TITLES_LIMIT = 3

PROMPT_TEMPLATE = """Voce analisa topicos de tendencias para um radar de vendas de \
modelos 3D (impressao e digital).

Tarefa 1 - fundir duplicatas: alguns topicos abaixo podem ser o mesmo personagem, obra \
ou produto, escrito de formas diferentes. Aponte para fundir SOMENTE quando tiver certeza \
de que sao a mesma coisa; na duvida, nao funda.

Tarefa 2 - motivo do hype: para cada topico, escreva em portugues, em 1 frase curta, por \
que ele pode estar em alta. Baseie-se SOMENTE nos titulos de exemplo fornecidos; nao \
invente fatos que nao estejam nos titulos.

Topicos (slug, nome, ate 3 titulos de exemplo de itens coletados):
{topics_json}

Responda SOMENTE com um JSON no formato exato abaixo, sem texto adicional, sem markdown:
{{"merges": [{{"keep": "<slug>", "merge": ["<slug>", "<slug>"]}}], "reasons": \
{{"<slug>": "<texto>"}}}}
"""


def _entity_slugs() -> set[str]:
    """Slugs de todas as entidades de `seed/entities.yaml`. Uma entidade e sempre
    re-semeada em `extract_topics`, entao ela nunca pode ser o lado removido de uma
    fusao (a fusao seria desfeita no proximo ciclo)."""
    return {_slugify(entity["name"]) for entity in _load_entities()}


def merge_topics(session: Session, keep_id: int, merge_id: int) -> None:
    """Funde `merge_id` em `keep_id`: reaponta sinais (somando em conflito), itens e
    listagens (fica a maior contagem), apaga os scores do topico removido, junta os
    aliases e apaga o topico removido."""
    keep = session.get(Topic, keep_id)
    merge = session.get(Topic, merge_id)
    if keep is None or merge is None or keep_id == merge_id:
        return

    keep_signals = {
        (row.source, row.country, row.day): row
        for row in session.exec(select(TopicSignal).where(TopicSignal.topic_id == keep_id)).all()
    }
    for signal in session.exec(select(TopicSignal).where(TopicSignal.topic_id == merge_id)).all():
        key = (signal.source, signal.country, signal.day)
        existing = keep_signals.get(key)
        if existing is not None:
            existing.value += signal.value
            session.add(existing)
            session.delete(signal)
        else:
            signal.topic_id = keep_id
            session.add(signal)
            keep_signals[key] = signal

    keep_item_ids = {
        row.raw_item_id
        for row in session.exec(select(TopicItem).where(TopicItem.topic_id == keep_id)).all()
    }
    for item in session.exec(select(TopicItem).where(TopicItem.topic_id == merge_id)).all():
        session.delete(item)
        if item.raw_item_id not in keep_item_ids:
            session.add(TopicItem(topic_id=keep_id, raw_item_id=item.raw_item_id))
            keep_item_ids.add(item.raw_item_id)

    keep_listings = {
        (row.platform, row.day): row
        for row in session.exec(select(TopicListing).where(TopicListing.topic_id == keep_id)).all()
    }
    for listing in session.exec(select(TopicListing).where(TopicListing.topic_id == merge_id)).all():
        key = (listing.platform, listing.day)
        existing = keep_listings.get(key)
        if existing is not None:
            if listing.count > existing.count:
                existing.count = listing.count
                session.add(existing)
            session.delete(listing)
        else:
            listing.topic_id = keep_id
            session.add(listing)
            keep_listings[key] = listing

    for score in session.exec(select(TopicScore).where(TopicScore.topic_id == merge_id)).all():
        session.delete(score)

    keep_aliases = json.loads(keep.aliases_json or "[]")
    merge_aliases = json.loads(merge.aliases_json or "[]")
    keep_name_norm = normalize(keep.name)
    for alias in [normalize(merge.name), *merge_aliases]:
        if alias and alias != keep_name_norm and alias not in keep_aliases:
            keep_aliases.append(alias)
    keep.aliases_json = json.dumps(keep_aliases)
    session.add(keep)

    session.delete(merge)
    session.commit()


def _get_last_enrich_day(session: Session) -> str | None:
    row = session.get(Setting, LAST_ENRICH_DAY_KEY)
    if row is None:
        return None
    return json.loads(row.value_json)


def _set_last_enrich_day(session: Session, day: date) -> None:
    payload = json.dumps(day.isoformat())
    row = session.get(Setting, LAST_ENRICH_DAY_KEY)
    if row is None:
        row = Setting(key=LAST_ENRICH_DAY_KEY, value_json=payload)
    else:
        row.value_json = payload
    session.add(row)
    session.commit()


def _example_titles(session: Session, topic_id: int, limit: int = EXAMPLE_TITLES_LIMIT) -> list[str]:
    rows = session.exec(
        select(RawItem.title)
        .join(TopicItem, TopicItem.raw_item_id == RawItem.id)
        .where(TopicItem.topic_id == topic_id)
        .order_by(RawItem.day.desc())
        .limit(limit)
    ).all()
    return list(rows)


def _build_prompt(session: Session, topics: list[Topic]) -> str:
    payload = [
        {"slug": topic.slug, "nome": topic.name, "titulos": _example_titles(session, topic.id)}
        for topic in topics
    ]
    return PROMPT_TEMPLATE.format(topics_json=json.dumps(payload, ensure_ascii=False, indent=2))


def enrich_topics(session: Session, provider: TextProvider, day: date, top_n: int = 50) -> tuple[int, int]:
    """Roda uma vez por dia: pede fusoes e motivos ao `provider` para os `top_n`
    topicos principais e aplica a resposta. Retorna `(fundidos, motivos_gravados)`.
    Nunca propaga um erro do provedor: registra em log e devolve `(0, 0)`, sem marcar
    `last_enrich_day` (para tentar de novo num proximo ciclo do mesmo dia)."""
    if _get_last_enrich_day(session) == day.isoformat():
        return (0, 0)

    from app.pipeline import _top_topic_ids

    topic_ids = _top_topic_ids(session, day, top_n)
    if not topic_ids:
        _set_last_enrich_day(session, day)
        return (0, 0)

    topics = session.exec(select(Topic).where(Topic.id.in_(topic_ids))).all()
    prompt = _build_prompt(session, topics)

    try:
        response = provider.generate_json(prompt)
    except AIQuotaError:
        logger.warning("Cota do provedor de IA excedida; enriquecimento adiado")
        return (0, 0)
    except Exception:
        logger.exception("Falha ao consultar o provedor de IA; enriquecimento adiado")
        return (0, 0)

    if not isinstance(response, dict):
        logger.error("Resposta do provedor de IA nao e um objeto JSON; enriquecimento adiado")
        return (0, 0)

    entity_slugs = _entity_slugs()
    slug_to_topic = {topic.slug: topic for topic in topics}

    merged = 0
    for merge_entry in response.get("merges") or []:
        keep_slug = merge_entry.get("keep")
        keep_topic = slug_to_topic.get(keep_slug)
        if keep_topic is None:
            continue
        for merge_slug in merge_entry.get("merge") or []:
            if merge_slug == keep_slug or merge_slug in entity_slugs:
                continue
            merge_topic = slug_to_topic.get(merge_slug)
            if merge_topic is None:
                continue
            merge_topics(session, keep_topic.id, merge_topic.id)
            del slug_to_topic[merge_slug]
            merged += 1

    reasons_written = 0
    for slug, reason_text in (response.get("reasons") or {}).items():
        topic = slug_to_topic.get(slug)
        if topic is None or not isinstance(reason_text, str):
            continue
        topic.reason = reason_text[:REASON_MAX_LEN]
        topic.reason_day = day
        session.add(topic)
        reasons_written += 1

    session.commit()
    _set_last_enrich_day(session, day)
    return (merged, reasons_written)
