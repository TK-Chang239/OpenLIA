from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardState
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session


@pytest.fixture
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


def test_mr_dashboard_state_has_schedule_columns(engine) -> None:
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("mr_dashboard_state")}
    assert "assessment_schedule" in cols
    assert "last_assessment_at" in cols


def test_insert_row_with_schedule_cols(engine) -> None:
    with Session(engine) as s:
        u = User(id="u-1", email="a@b", password_hash="x", display_name="A")
        s.add(u)
        s.commit()
        row = MrDashboardState(
            id="mrs-1",
            user_id="u-1",
            dashboard="world_order",
            view_config={},
            threshold_overrides={},
            assessment_schedule="0 0 * * 0",
            last_assessment_at=datetime.now(UTC),
        )
        s.add(row)
        s.commit()
        fetched = s.get(MrDashboardState, "mrs-1")
        assert fetched is not None
        assert fetched.assessment_schedule == "0 0 * * 0"
        assert fetched.last_assessment_at is not None


def test_schedule_cols_nullable(engine) -> None:
    with Session(engine) as s:
        u = User(id="u-2", email="b@b", password_hash="x", display_name="B")
        s.add(u)
        s.commit()
        row = MrDashboardState(
            id="mrs-2",
            user_id="u-2",
            dashboard="four_seasons",
            view_config={},
            threshold_overrides={},
        )
        s.add(row)
        s.commit()
        fetched = s.get(MrDashboardState, "mrs-2")
        assert fetched.assessment_schedule is None
        assert fetched.last_assessment_at is None
