from __future__ import annotations

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import EuUserConfig, EuWatchlistEntry
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _mk_user(db: Session, email: str = "u@x") -> User:
    u = User(id="u_eu_1", email=email, display_name="EU User", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def test_watchlist_columns(create_tables) -> None:
    cols = {c.name for c in inspect(EuWatchlistEntry).columns}
    for expected in {
        "id",
        "user_id",
        "ticker",
        "company_name",
        "next_earnings_date",
        "release_timing",
        "created_at",
        "updated_at",
    }:
        assert expected in cols


def test_watchlist_unique_on_user_and_ticker(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        EuWatchlistEntry(
            id="w1",
            user_id="u_eu_1",
            ticker="AAPL",
            company_name="Apple Inc.",
            next_earnings_date=None,
            release_timing=None,
        )
    )
    db_session.commit()
    db_session.add(
        EuWatchlistEntry(
            id="w2",
            user_id="u_eu_1",
            ticker="AAPL",
            company_name="Apple Inc.",
            next_earnings_date=None,
            release_timing=None,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_watchlist_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        EuWatchlistEntry(
            id="w3",
            user_id="u_eu_1",
            ticker="TSLA",
            company_name="Tesla",
        )
    )
    db_session.commit()
    db_session.query(User).filter_by(id="u_eu_1").delete()
    db_session.commit()
    assert db_session.query(EuWatchlistEntry).count() == 0


def test_release_timing_check_constraint(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        EuWatchlistEntry(
            id="w4",
            user_id="u_eu_1",
            ticker="NVDA",
            company_name="NVIDIA",
            release_timing="midday",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_config_one_per_user(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        EuUserConfig(
            id="c1",
            user_id="u_eu_1",
            report_length="normal",
            enabled_section_ids=["quick_take", "key_financials"],
            custom_sections=[],
        )
    )
    db_session.commit()
    db_session.add(
        EuUserConfig(
            id="c2",
            user_id="u_eu_1",
            report_length="normal",
            enabled_section_ids=[],
            custom_sections=[],
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_eu_full_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    """Deleting a user must remove watchlist + config + schedules rows."""
    import json
    from datetime import UTC, datetime

    from openlia_server.db.models.scheduler import EuSchedule

    _mk_user(db_session)
    db_session.add(
        EuWatchlistEntry(
            id="w_cascade",
            user_id="u_eu_1",
            ticker="AAPL",
            company_name="Apple",
        )
    )
    db_session.add(
        EuUserConfig(
            id="c_cascade",
            user_id="u_eu_1",
            report_length="normal",
            enabled_section_ids=["quick_take"],
            custom_sections=[],
        )
    )
    db_session.add(
        EuSchedule(
            id="s_cascade",
            user_id="u_eu_1",
            time="06:00",
            timezone="UTC",
            days_of_week=json.dumps([0, 1]),
            label=None,
            is_enabled=True,
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    db_session.query(User).filter_by(id="u_eu_1").delete()
    db_session.commit()

    assert db_session.query(EuWatchlistEntry).filter_by(user_id="u_eu_1").count() == 0
    assert db_session.query(EuUserConfig).filter_by(user_id="u_eu_1").count() == 0
    assert db_session.query(EuSchedule).filter_by(user_id="u_eu_1").count() == 0


def test_config_length_check_constraint(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        EuUserConfig(
            id="c3",
            user_id="u_eu_1",
            report_length="tiny",  # invalid
            enabled_section_ids=[],
            custom_sections=[],
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
