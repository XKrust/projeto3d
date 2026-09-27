def test_rawitem_unique_per_day(session):
    from app.models import RawItem
    from datetime import date

    session.add(RawItem(source="x", external_id="1", country="BR", day=date(2026, 9, 26), title="a", metric=1))
    session.commit()
    session.add(RawItem(source="x", external_id="1", country="BR", day=date(2026, 9, 26), title="b", metric=2))
    import pytest, sqlalchemy

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        session.commit()
