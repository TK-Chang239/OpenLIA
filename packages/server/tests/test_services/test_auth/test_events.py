"""Tests for services.auth.events.log_auth_event."""
from __future__ import annotations

from sqlalchemy import select

from openlia_server.db.models.auth import AuthEvent
from openlia_server.services.auth import events


def test_log_basic_event(db_session, make_user):
    user = make_user()
    events.log_auth_event(
        db_session,
        event_type="login_success",
        user_id=user.id,
        actor_user_id=user.id,
        ip_address="10.0.0.1",
        user_agent="pytest",
        metadata={"source": "web"},
    )
    rows = list(db_session.execute(select(AuthEvent)).scalars())
    assert len(rows) == 1
    assert rows[0].event_type == "login_success"
    assert rows[0].user_id == user.id
    assert rows[0].event_metadata == {"source": "web"}


def test_log_event_without_user(db_session):
    events.log_auth_event(
        db_session,
        event_type="login_failure",
        ip_address="10.0.0.1",
    )
    rows = list(db_session.execute(select(AuthEvent)).scalars())
    assert len(rows) == 1
    assert rows[0].user_id is None


def test_user_agent_truncated_to_512(db_session, make_user):
    user = make_user()
    events.log_auth_event(
        db_session,
        event_type="login_success",
        user_id=user.id,
        user_agent="x" * 1000,
    )
    rows = list(db_session.execute(select(AuthEvent)).scalars())
    assert len(rows[0].user_agent) == 512
