"""O radar fica pronto antes da parte lenta: notas primeiro, concorrência depois."""

from app import pipeline, runner


def _record(monkeypatch, listings_written=5):
    calls = []
    monkeypatch.setattr(pipeline, "extract_topics", lambda s, d: calls.append("extract"))
    monkeypatch.setattr(pipeline, "update_seasonal_signals", lambda s, d: calls.append("seasonal_signals"))
    monkeypatch.setattr(pipeline, "compute_scores", lambda s, d: calls.append("scores"))
    monkeypatch.setattr(pipeline, "compute_country_ranks", lambda s, d: calls.append("ranks"))
    monkeypatch.setattr(pipeline, "set_collect_phase", lambda phase: calls.append(f"fase:{phase}"))
    monkeypatch.setattr(pipeline, "update_listings", lambda s, c, d, n: calls.append("listings") or listings_written)
    monkeypatch.setattr(pipeline, "update_hype_listings", lambda s, c, d: calls.append("hype_listings") or 0)
    monkeypatch.setattr(pipeline, "update_seasonal_listings",
                        lambda s, c, d, lead_days, modeling_days: calls.append("seasonal_listings") or 0)
    return calls


def test_scores_come_before_the_slow_listing_counts(session, monkeypatch):
    calls = _record(monkeypatch)
    pipeline.run_pipeline(session, {}, enrich=lambda s: calls.append("enrich"))
    assert calls == ["extract", "seasonal_signals", "scores", "ranks", "fase:concorrencia",
                     "listings", "hype_listings", "seasonal_listings", "scores", "ranks", "enrich"]


def test_no_recompute_when_nothing_was_measured(session, monkeypatch):
    calls = _record(monkeypatch, listings_written=0)
    pipeline.run_pipeline(session, {})
    assert calls.count("scores") == 1


def test_quiet_cycle_when_no_source_is_due(session):
    from tests.test_runner import FakeOkCollector

    runner.run_cycle(session, collectors=[FakeOkCollector], http=object())
    assert runner.collect_progress()["quiet"] is False
    assert runner.collect_progress()["total"] == 1
    # Logo depois, a mesma fonte está fora do horário: ciclo silencioso (sem faixa na tela).
    runner.run_cycle(session, collectors=[FakeOkCollector], http=object())
    assert runner.collect_progress()["quiet"] is True
    assert runner.collect_progress()["total"] == 0
