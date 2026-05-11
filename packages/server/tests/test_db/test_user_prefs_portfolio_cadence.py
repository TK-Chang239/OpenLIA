"""Phase 2: portfolio_refresh_cadence column on user_prefs."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_default_is_daily(create_tables, db_session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.config import UserPrefs

    db_session.add(
        User(
            id="u1",
            email="u1@example.com",
            display_name="u1",
            password_hash=None,
            is_admin=False,
            is_disabled=False,
        )
    )
    db_session.add(UserPrefs(user_id="u1"))
    db_session.commit()

    row = db_session.get(UserPrefs, "u1")
    assert row.portfolio_refresh_cadence == "daily"


def test_accepts_all_four_values(create_tables, db_session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.config import UserPrefs

    db_session.add(
        User(
            id="u1",
            email="u1@example.com",
            display_name="u1",
            password_hash=None,
            is_admin=False,
            is_disabled=False,
        )
    )
    db_session.commit()

    for cadence in ("hourly", "daily", "weekly", "manual"):
        row = db_session.get(UserPrefs, "u1")
        if row is None:
            row = UserPrefs(user_id="u1")
            db_session.add(row)
        row.portfolio_refresh_cadence = cadence
        db_session.commit()
        db_session.refresh(row)
        assert row.portfolio_refresh_cadence == cadence


def test_rejects_unknown_value(create_tables, db_session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.config import UserPrefs

    db_session.add(
        User(
            id="u1",
            email="u1@example.com",
            display_name="u1",
            password_hash=None,
            is_admin=False,
            is_disabled=False,
        )
    )
    db_session.add(UserPrefs(user_id="u1", portfolio_refresh_cadence="continuous"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
