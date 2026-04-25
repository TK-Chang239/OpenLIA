"""Service-level coverage for admin direct password resets (Phase 11)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import AuthEvent, User
from openlia_server.services.auth import password_reset, passwords, sessions


@pytest.fixture
def make_user(db_session):
    def _make(
        email: str = "user@example.com",
        is_admin: bool = False,
        is_disabled: bool = False,
    ) -> User:
        existing = db_session.query(User).filter_by(email=email).one_or_none()
        if existing is not None:
            return existing
        user = User(
            id=f"user-{email}",
            email=email,
            display_name=email.split("@")[0],
            password_hash=passwords.hash_password("initial-strong-pass"),
            is_admin=is_admin,
            is_disabled=is_disabled,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _make


class TestAdminDirectResetGeneratesRandomTempPassword:
    def test_returns_random_password_when_omitted(self, db_session, make_user):
        u = make_user(email="alice@example.com")
        admin = make_user(email="admin@example.com", is_admin=True)
        temp = password_reset.admin_direct_reset(db_session, user_id=u.id, admin_user_id=admin.id)
        assert isinstance(temp, str)
        # secrets.token_urlsafe(32) yields ~43 chars.
        assert len(temp) >= 32

    def test_two_invocations_yield_distinct_passwords(self, db_session, make_user):
        u = make_user(email="alice2@example.com")
        admin = make_user(email="admin2@example.com", is_admin=True)
        a = password_reset.admin_direct_reset(db_session, user_id=u.id, admin_user_id=admin.id)
        b = password_reset.admin_direct_reset(db_session, user_id=u.id, admin_user_id=admin.id)
        assert a != b

    def test_password_is_hashed_not_plaintext(self, db_session, make_user):
        u = make_user(email="alice3@example.com")
        admin = make_user(email="admin3@example.com", is_admin=True)
        temp = password_reset.admin_direct_reset(db_session, user_id=u.id, admin_user_id=admin.id)
        db_session.refresh(u)
        assert u.password_hash is not None
        assert u.password_hash != temp
        assert passwords.verify_password(u.password_hash, temp)

    def test_sets_must_change_password(self, db_session, make_user):
        u = make_user(email="alice4@example.com")
        admin = make_user(email="admin4@example.com", is_admin=True)
        u.must_change_password = False
        db_session.commit()
        password_reset.admin_direct_reset(db_session, user_id=u.id, admin_user_id=admin.id)
        db_session.refresh(u)
        assert u.must_change_password is True

    def test_revokes_active_sessions(self, db_session, make_user):
        u = make_user(email="alice5@example.com")
        admin = make_user(email="admin5@example.com", is_admin=True)
        active = sessions.create_session(db_session, user_id=u.id, persistent=True)
        password_reset.admin_direct_reset(db_session, user_id=u.id, admin_user_id=admin.id)
        assert sessions.validate_session(db_session, active.raw_token) is None

    def test_writes_audit_event(self, db_session, make_user):
        u = make_user(email="alice6@example.com")
        admin = make_user(email="admin6@example.com", is_admin=True)
        password_reset.admin_direct_reset(
            db_session,
            user_id=u.id,
            admin_user_id=admin.id,
            metadata={"source": "test"},
        )
        rows = (
            db_session.query(AuthEvent)
            .filter_by(event_type="password_reset_by_admin", user_id=u.id)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].actor_user_id == admin.id


class TestAdminDirectResetWithExplicitPassword:
    def test_explicit_password_is_used(self, db_session, make_user):
        u = make_user(email="explicit@example.com")
        admin = make_user(email="admin-x@example.com", is_admin=True)
        returned = password_reset.admin_direct_reset(
            db_session,
            user_id=u.id,
            new_password="explicit-strong-pass",
            admin_user_id=admin.id,
        )
        assert returned == "explicit-strong-pass"
        db_session.refresh(u)
        assert passwords.verify_password(u.password_hash, "explicit-strong-pass")
