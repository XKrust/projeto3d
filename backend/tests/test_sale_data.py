import pytest
from sqlalchemy import create_engine, text

from app import clock
from app.db import init_db
from app.models import Analysis
from app.settings_store import get_settings, update_settings


def test_analysis_has_sale_columns(session):
    row = Analysis(created_at=clock.now(), authorship="autoral", market="print", theme="Dragão",
                   category="outros", image_count=1, has_wireframe=False, result_json="{}",
                   sale_json='{"ok": true}', sale_at=clock.now())
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.sale_json == '{"ok": true}'
    assert row.sale_at is not None


def test_old_database_gets_sale_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE analysis (id INTEGER PRIMARY KEY, theme VARCHAR)")
    init_db(engine)
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(analysis)"))}
    assert {"sale_json", "sale_at"} <= columns


def test_hourly_rate_default_and_validation(session):
    assert get_settings(session)["hourly_rate_usd"] == 10
    assert update_settings(session, {"hourly_rate_usd": 25})["hourly_rate_usd"] == 25
    for bad in (0, 5000, "dez", True):
        with pytest.raises(ValueError, match="valor da hora"):
            update_settings(session, {"hourly_rate_usd": bad})
