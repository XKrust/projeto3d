import app.collectors as collectors_pkg
from app.collectors.base import Collector, CollectedItem, CollectorError
from app.models import RawItem, Source
from app.runner import _cycle_lock, run_cycle, start_cycle_in_background
from sqlmodel import select


class FakeOkCollector(Collector):
    name = "fake_ok"
    label = "Fake OK"
    kind = "api"
    needs_key = ()
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        return [CollectedItem(external_id="1", title="Item 1", country="BR", metric=10.0)]


class FakeFailingCollector(Collector):
    name = "fake_fail"
    label = "Fake com erro"
    kind = "api"
    needs_key = ()
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        raise CollectorError("Falha simulada")


class FakeNeedsKeyCollector(Collector):
    name = "fake_needs_key"
    label = "Fake precisa de chave"
    kind = "api"
    needs_key = ("youtube",)
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        return []


class FakeBadItemCollector(Collector):
    """Coletor que devolve um item impossivel de gravar (title=None viola NOT NULL)."""

    name = "fake_bad_item"
    label = "Fake item invalido"
    kind = "api"
    needs_key = ()
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        return [CollectedItem(external_id="1", title=None, country="BR", metric=1.0)]  # type: ignore[arg-type]


class FakeCountingCollector(Collector):
    name = "fake_counting"
    label = "Fake contador"
    kind = "api"
    needs_key = ()
    interval_minutes = 60
    calls = 0

    def collect(self) -> list[CollectedItem]:
        type(self).calls += 1
        return [
            CollectedItem(
                external_id="1", title="Item", country="BR", metric=float(type(self).calls)
            )
        ]


def test_failing_collector_isolated(session):
    result = run_cycle(
        session, collectors=[FakeFailingCollector, FakeOkCollector], http=object()
    )

    assert result.ran == ["fake_ok"]
    assert result.failed == {"fake_fail": "Falha simulada"}

    fail_row = session.get(Source, "fake_fail")
    ok_row = session.get(Source, "fake_ok")
    assert fail_row.status == "error"
    assert fail_row.last_error == "Falha simulada"
    assert ok_row.status == "ok"
    assert ok_row.items_last_run == 1

    items = session.exec(select(RawItem).where(RawItem.source == "fake_ok")).all()
    assert len(items) == 1


def test_persistence_failure_is_isolated(session):
    """Um item que nao pode ser gravado (erro no banco, nao no coletor) nao pode
    derrubar o ciclo: o proximo coletor precisa rodar normalmente."""
    result = run_cycle(
        session, collectors=[FakeBadItemCollector, FakeOkCollector], http=object()
    )

    assert result.ran == ["fake_ok"]
    assert "fake_bad_item" in result.failed
    assert result.failed["fake_bad_item"].startswith("Erro inesperado:")

    bad_row = session.get(Source, "fake_bad_item")
    ok_row = session.get(Source, "fake_ok")
    assert bad_row.status == "error"
    assert bad_row.last_error == result.failed["fake_bad_item"]
    assert bad_row.last_run is not None
    assert ok_row.status == "ok"

    ok_items = session.exec(select(RawItem).where(RawItem.source == "fake_ok")).all()
    assert len(ok_items) == 1
    bad_items = session.exec(select(RawItem).where(RawItem.source == "fake_bad_item")).all()
    assert bad_items == []


def test_missing_key_is_no_key_not_error(session):
    result = run_cycle(session, collectors=[FakeNeedsKeyCollector], http=object())

    assert result.skipped == {"fake_needs_key": "sem chave"}
    assert result.ran == []
    assert result.failed == {}

    row = session.get(Source, "fake_needs_key")
    assert row.status == "no_key"
    assert row.last_run is None


def test_not_due_skipped_unless_force(session):
    first = run_cycle(session, collectors=[FakeOkCollector], http=object())
    assert first.ran == ["fake_ok"]

    second = run_cycle(session, collectors=[FakeOkCollector], http=object())
    assert second.skipped == {"fake_ok": "fora do horário"}
    assert second.ran == []

    forced = run_cycle(session, collectors=[FakeOkCollector], http=object(), force=True)
    assert forced.ran == ["fake_ok"]


def test_upsert_same_day_no_duplicates(session):
    FakeCountingCollector.calls = 0

    run_cycle(session, collectors=[FakeCountingCollector], http=object(), force=True)
    run_cycle(session, collectors=[FakeCountingCollector], http=object(), force=True)

    items = session.exec(select(RawItem).where(RawItem.source == "fake_counting")).all()
    assert len(items) == 1
    assert items[0].metric == 2.0


def test_after_callback_is_called_and_errors_are_caught(session):
    calls: list[bool] = []

    def after(sess):
        calls.append(True)
        raise RuntimeError("boom")

    result = run_cycle(session, collectors=[FakeOkCollector], http=object(), after=after)

    assert calls == [True]
    assert result.ran == ["fake_ok"]


def test_second_background_start_returns_false(client):
    assert _cycle_lock.acquire(blocking=False)
    try:
        started = start_cycle_in_background(lambda: None)
        assert started is False

        response = client.post("/api/collect")
        assert response.status_code == 200
        assert response.json() == {
            "started": False,
            "message": "Já existe uma coleta em andamento.",
        }
    finally:
        _cycle_lock.release()


def test_get_sources_reports_status_and_key(client, monkeypatch):
    monkeypatch.setattr(
        collectors_pkg, "ALL_COLLECTORS", [FakeNeedsKeyCollector, FakeOkCollector]
    )

    response = client.get("/api/sources")
    assert response.status_code == 200
    rows = {row["name"]: row for row in response.json()}

    assert rows["fake_needs_key"]["needs_key"] is True
    assert rows["fake_needs_key"]["has_key"] is False
    assert rows["fake_needs_key"]["status"] == "no_key"

    assert rows["fake_ok"]["needs_key"] is False
    assert rows["fake_ok"]["has_key"] is True
    assert rows["fake_ok"]["status"] == "never"


def test_get_sources_reflects_run_status(client, monkeypatch, session):
    monkeypatch.setattr(collectors_pkg, "ALL_COLLECTORS", [FakeOkCollector])
    run_cycle(session, collectors=[FakeOkCollector], http=object(), force=True)

    response = client.get("/api/sources")
    rows = {row["name"]: row for row in response.json()}

    assert rows["fake_ok"]["status"] == "ok"
    assert rows["fake_ok"]["items_last_run"] == 1
