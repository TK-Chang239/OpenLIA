"""Service-level coverage for admin user management primitives (Phase 11).

The admin user-disable / enable flows live in the route handler today and lean
on `services.auth.sessions.revoke_all_sessions`. These tests pin that
contract.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import User
from openlia_server.services.auth import passwords, sessions


@pytest.fixture
def make_user(db_session):
    def _make(email: str, *, is_admin: bool = False) -> User:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            display_name=email.split("@")[0],
            password_hash=passwords.hash_password("initial-strong-pass"),
            is_admin=is_admin,
            is_disabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _make


class TestRevokeAllSessions:
    def test_revokes_each_active_session(self, db_session, make_user):
        u = make_user("alice@example.com")
        s1 = sessions.create_session(db_session, user_id=u.id, persistent=True)
        s2 = sessions.create_session(db_session, user_id=u.id, persistent=False)

        sessions.revoke_all_sessions(db_session, user_id=u.id)

        assert sessions.validate_session(db_session, s1.raw_token) is None
        assert sessions.validate_session(db_session, s2.raw_token) is None

    def test_does_not_touch_other_users_sessions(self, db_session, make_user):
        a = make_user("alice@example.com")
        b = make_user("bob@example.com")
        sa = sessions.create_session(db_session, user_id=a.id, persistent=True)
        sb = sessions.create_session(db_session, user_id=b.id, persistent=True)

        sessions.revoke_all_sessions(db_session, user_id=a.id)

        assert sessions.validate_session(db_session, sa.raw_token) is None
        assert sessions.validate_session(db_session, sb.raw_token) is not None
