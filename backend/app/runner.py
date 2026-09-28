"""Ciclo de coleta: roda cada coletor, atualiza o status e persiste os itens."""

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

import httpx
from sqlmodel import Session, select

import app.collectors as collectors_pkg
from app.clock import now, today
from app.collectors.base import Collector, CollectedItem, CollectorError, Release
from app.http import make_client
from app.models import HypeRelease, RawItem, Source
from app.settings_store import get_settings

logger = logging.getLogger(__name__)

_cycle_lock = threading.Lock()


@dataclass
class CycleResult:
    """Resultado de uma execucao de `run_cycle`."""

    ran: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)


def _get_or_create_source(session: Session, name: str) -> Source:
    source = session.get(Source, name)
    if source is None:
        source = Source(name=name)
    return source


def _mark_error(session: Session, name: str, message: str) -> None:
    """Desfaz qualquer alteracao pendente da fonte (ex.: itens parcialmente gravados) e
    marca a fonte como erro, isolando a falha do resto do ciclo."""
    session.rollback()
    source_row = _get_or_create_source(session, name)
    source_row.status = "error"
    source_row.last_error = message
    source_row.last_run = now()
    session.add(source_row)
    session.commit()


def _upsert_raw_item(session: Session, *, source_name: str, day, item: CollectedItem) -> None:
    existing = session.exec(
        select(RawItem).where(
            RawItem.source == source_name,
            RawItem.external_id == item.external_id,
            RawItem.country == item.country,
            RawItem.day == day,
        )
    ).first()
    if existing is None:
        existing = RawItem(
            source=source_name,
            external_id=item.external_id,
            country=item.country,
            day=day,
            title=item.title,
            metric=item.metric,
        )

    existing.title = item.title
    existing.tags_json = json.dumps(item.tags)
    existing.url = item.url
    existing.thumb_url = item.thumb_url
    existing.likes = item.likes
    existing.downloads = item.downloads
    existing.views = item.views
    existing.comments = item.comments
    existing.price_usd = item.price_usd
    existing.metric = item.metric
    session.add(existing)


def _upsert_release(session: Session, *, source_name: str, day, release: Release) -> None:
    existing = session.exec(
        select(HypeRelease).where(
            HypeRelease.source == source_name,
            HypeRelease.external_id == release.external_id,
            HypeRelease.country == release.country,
        )
    ).first()
    row = existing or HypeRelease(
        source=source_name,
        external_id=release.external_id,
        country=release.country,
        kind=release.kind,
        title=release.title,
        updated_day=day,
    )
    row.kind = release.kind
    row.title = release.title
    row.release_date = release.release_date
    row.popularity = release.popularity
    row.url = release.url
    row.image_url = release.image_url
    row.aliases_json = json.dumps(release.aliases, ensure_ascii=False)
    row.characters_json = json.dumps(release.characters, ensure_ascii=False)
    row.updated_day = day
    session.add(row)


def run_cycle(
    session: Session,
    *,
    force: bool = False,
    only: str | None = None,
    http=None,
    collectors: list[type[Collector]] | None = None,
    after: Callable[[Session], None] | None = None,
) -> CycleResult:
    """Roda um ciclo de coleta sobre `collectors` (ou `ALL_COLLECTORS`).

    Cada coletor sem alguma chave necessaria fica `no_key`. Um coletor fora do
    horario (`now - last_run < interval_minutes`) e pulado, a menos que
    `force=True`. Coletores que rodam tem o status atualizado (`ok` ou
    `error`) e, em caso de sucesso, seus itens sao gravados (upsert por
    fonte/external_id/pais/dia). Uma falha em um coletor nunca impede os
    outros de rodar. Ao final, chama `after(session)` se foi passado.
    """
    result = CycleResult()
    collector_classes = collectors if collectors is not None else collectors_pkg.ALL_COLLECTORS
    settings = get_settings(session)

    owns_http = http is None
    client = http if http is not None else make_client()
    try:
        for cls in collector_classes:
            if only is not None and cls.name != only:
                continue

            source_row = _get_or_create_source(session, cls.name)

            api_keys = settings.get("api_keys", {})
            missing_keys = [key for key in cls.needs_key if not api_keys.get(key)]
            if missing_keys:
                source_row.status = "no_key"
                session.add(source_row)
                session.commit()
                result.skipped[cls.name] = "sem chave"
                continue

            if not force and source_row.last_run is not None:
                elapsed = now() - source_row.last_run
                if elapsed < timedelta(minutes=cls.interval_minutes):
                    result.skipped[cls.name] = "fora do horário"
                    continue

            source_row.last_run = now()
            try:
                collector = cls(settings, client)
                items = collector.collect()

                day = today()
                for item in items:
                    _upsert_raw_item(session, source_name=cls.name, day=day, item=item)
                for release in collector.releases():
                    _upsert_release(session, source_name=cls.name, day=day, release=release)

                source_row.status = "ok"
                source_row.last_error = None
                source_row.items_last_run = len(items)
                session.add(source_row)
                session.commit()
                result.ran.append(cls.name)
            except CollectorError as exc:
                message = str(exc)
                logger.error("Coletor %s falhou: %s", cls.name, message)
                result.failed[cls.name] = message
                _mark_error(session, cls.name, message)
            except httpx.TransportError as exc:  # sem internet, proxy, DNS, tempo esgotado
                message = "Sem conexão com o site (confira a internet); tenta de novo na próxima coleta"
                logger.warning("Coletor %s sem conexão: %s", cls.name, exc)
                result.failed[cls.name] = message
                _mark_error(session, cls.name, message)
            except Exception as exc:  # nunca deixar um coletor derrubar o ciclo
                message = f"Erro inesperado: {type(exc).__name__}"
                logger.exception("Coletor %s falhou de forma inesperada", cls.name)
                result.failed[cls.name] = message
                _mark_error(session, cls.name, message)
    finally:
        if owns_http:
            client.close()

    if after is not None:
        try:
            after(session)
        except Exception:
            logger.exception("Erro ao executar callback 'after' do ciclo de coleta")

    return result


def start_cycle_in_background(session_factory, **kwargs) -> bool:
    """Roda `run_cycle` em uma thread daemon, com uma sessao nova de `session_factory`.

    Usa um lock global para impedir dois ciclos simultaneos: retorna `False`
    (sem iniciar nada) se ja houver um ciclo em andamento.
    """
    if not _cycle_lock.acquire(blocking=False):
        return False

    def _run() -> None:
        try:
            session = session_factory()
            try:
                run_cycle(session, **kwargs)
            finally:
                session.close()
        except Exception:
            logger.exception("Erro ao rodar ciclo de coleta em segundo plano")
        finally:
            _cycle_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return True
