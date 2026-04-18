from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    from openlia_server.db.base import Base
    import openlia_server.db.models.auth  # noqa: F401

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_users_columns(create_tables, engine) -> None:
    from openlia_server.db.models.auth import User

    cols = {c.name: c for c in User.__table__.columns}
    expected = {
        "id", "email", "display_name", "password_hash", "is_admin", "is_disabled",
        "must_change_password", "created_at", "updated_at", "last_login_at",
        "failed_login_attempts", "locked_until",
    }
    assert set(cols.keys()) == expected
    assert cols["id"].primary_key
    assert cols["email"].unique is True
    assert cols["password_hash"].nullable is True
    assert cols["is_admin"].default.arg is False
    assert cols["failed_login_attempts"].default.arg == 0


def test_users_email_unique(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User

    db_session.add(User(id="u1", email="a@example.com", display_name="A"))
    db_session.add(User(id="u2", email="a@example.com", display_name="B"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_sessions_cascade_delete_on_user(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import Session as SessionModel, User

    u = User(id="u1", email="u1@example.com", display_name="U1")
    s = SessionModel(
        id="s1",
        user_id="u1",
        token_hash="a" * 64,
        last_seen_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    db_session.add_all([u, s])
    db_session.commit()

    db_session.delete(u)
    db_session.commit()

    assert db_session.execute(select(SessionModel)).scalar_one_or_none() is None


def test_auth_events_user_id_set_null_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import AuthEvent, User

    u = User(id="u1", email="u1@example.com", display_name="U1")
    ev = AuthEvent(id="e1", user_id="u1", event_type="login_success")
    db_session.add_all([u, ev])
    db_session.commit()

    db_session.delete(u)
    db_session.commit()

    row = db_session.execute(select(AuthEvent)).scalar_one()
    assert row.user_id is None


def test_signup_invites_token_unique(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import SignupInvite

    db_session.add(SignupInvite(id="i1", token="tok-a"))
    db_session.add(SignupInvite(id="i2", token="tok-a"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_signup_policy_singleton_constraint(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import SignupPolicy

    db_session.add(SignupPolicy(id=1, mode="closed"))
    db_session.commit()

    db_session.add(SignupPolicy(id=2, mode="invite_only"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_password_reset_requests_columns(create_tables) -> None:
    from openlia_server.db.models.auth import PasswordResetRequest

    cols = {c.name: c for c in PasswordResetRequest.__table__.columns}
    assert {"id", "user_id", "status", "requested_at", "requested_ip",
            "approved_by_user_id", "approved_at", "token_hash", "expires_at",
            "consumed_at"} <= set(cols.keys())
