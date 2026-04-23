"""Verify wizard_state shape after the reshape migration: current_step is a string,
completed_steps is a JSON array, and active_session_token is nullable text."""

from __future__ import annotations

import pytest
from openlia_server.db.models.infrastructure import WizardState
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models.infrastructure  # noqa: F401
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_wizard_state_accepts_named_step_and_completed_list(
    create_tables, db_session: Session
) -> None:
    row = WizardState(
        id=1,
        current_step="mode",
        completed_steps=[],
        step_data={},
        active_session_token="abc",
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.get(WizardState, 1)
    assert fetched is not None
    assert fetched.current_step == "mode"
    assert fetched.completed_steps == []
    assert fetched.active_session_token == "abc"


def test_wizard_state_active_session_token_nullable(create_tables, db_session: Session) -> None:
    row = WizardState(id=1, current_step="mode", completed_steps=[], step_data={})
    db_session.add(row)
    db_session.commit()

    fetched = db_session.get(WizardState, 1)
    assert fetched is not None
    assert fetched.active_session_token is None


def test_wizard_state_completed_steps_round_trips_entries(
    create_tables, db_session: Session
) -> None:
    row = WizardState(
        id=1,
        current_step="providers",
        completed_steps=["mode", "admin"],
        step_data={},
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.get(WizardState, 1)
    assert fetched is not None
    assert fetched.completed_steps == ["mode", "admin"]
