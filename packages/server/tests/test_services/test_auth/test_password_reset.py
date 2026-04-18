"""Tests for services.auth.password_reset."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from openlia_server.db.models.auth import PasswordResetRequest
from openlia_server.services.auth import password_reset, sessions
from openlia_server.services.auth.errors import AuthError
from sqlalchemy import select


class TestRequestReset:
    def test_creates_pending_row(self, db_session, make_user):
        u = make_user()
        password_reset.request_reset(db_session, email="alice@example.com", ip_address="1.1.1.1")
        row = db_session.execute(select(PasswordResetRequest)).scalar_one()
        assert row.user_id == u.id
        assert row.status == "pending"
        assert row.token_hash is None

    def test_unknown_email_is_silent(self, db_session):
        password_reset.request_reset(db_session, email="nobody@example.com")
        rows = list(db_session.execute(select(PasswordResetRequest)).scalars())
        assert rows == []

    def test_second_request_replaces_pending(self, db_session, make_user):
        make_user()
        password_reset.request_reset(db_session, email="alice@example.com")
        password_reset.request_reset(db_session, email="alice@example.com")
        pending = list(
            db_session.execute(
                select(PasswordResetRequest).where(PasswordResetRequest.status == "pending")
            ).scalars()
        )
        assert len(pending) == 1


class TestApproveReject:
    def test_approve_generates_single_use_token(self, db_session, make_user):
        make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()

        raw = password_reset.approve_request(db_session, request_id=req.id, admin_user_id=admin.id)
        assert len(raw) > 40
        db_session.refresh(req)
        assert req.status == "approved"
        assert req.token_hash is not None
        assert req.expires_at is not None
        assert req.approved_by_user_id == admin.id

    def test_reject_marks_rejected(self, db_session, make_user):
        make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()

        password_reset.reject_request(db_session, request_id=req.id, admin_user_id=admin.id)
        db_session.refresh(req)
        assert req.status == "rejected"


class TestConsume:
    def test_happy_path_updates_password_and_revokes_sessions(self, db_session, make_user):
        u = make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        old_hash = u.password_hash

        s = sessions.create_session(db_session, user_id=u.id, persistent=True)

        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()
        token = password_reset.approve_request(
            db_session, request_id=req.id, admin_user_id=admin.id
        )

        password_reset.consume_token(db_session, token=token, new_password="new-strong-password")

        db_session.refresh(u)
        assert u.password_hash != old_hash
        assert sessions.validate_session(db_session, s.raw_token) is None

    def test_expired_token_rejected(self, db_session, make_user):
        make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()
        token = password_reset.approve_request(
            db_session, request_id=req.id, admin_user_id=admin.id
        )

        req.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db_session.commit()

        with pytest.raises(AuthError) as exc:
            password_reset.consume_token(
                db_session, token=token, new_password="new-strong-password"
            )
        assert exc.value.code == "token_expired"

    def test_unknown_token_rejected(self, db_session):
        with pytest.raises(AuthError) as exc:
            password_reset.consume_token(
                db_session, token="nope", new_password="new-strong-password"
            )
        assert exc.value.code == "token_invalid"

    def test_consumed_token_cannot_replay(self, db_session, make_user):
        make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()
        token = password_reset.approve_request(
            db_session, request_id=req.id, admin_user_id=admin.id
        )

        password_reset.consume_token(db_session, token=token, new_password="new-strong-password")
        with pytest.raises(AuthError):
            password_reset.consume_token(
                db_session, token=token, new_password="other-strong-password"
            )


class TestAdminDirectReset:
    def test_sets_must_change_and_revokes_sessions(self, db_session, make_user):
        u = make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        s = sessions.create_session(db_session, user_id=u.id, persistent=True)

        password_reset.admin_direct_reset(
            db_session, user_id=u.id, new_password="temp-password-here", admin_user_id=admin.id
        )
        db_session.refresh(u)
        assert u.must_change_password is True
        assert sessions.validate_session(db_session, s.raw_token) is None


class TestChangePassword:
    def test_requires_current_password(self, db_session, make_user):
        u = make_user()
        with pytest.raises(AuthError):
            password_reset.change_password(
                db_session,
                user_id=u.id,
                current_password="wrong",
                new_password="new-strong-password",
            )

    def test_clears_must_change_flag(self, db_session, make_user):
        u = make_user()
        u.must_change_password = True
        db_session.commit()
        password_reset.change_password(
            db_session,
            user_id=u.id,
            current_password="correct horse battery staple",
            new_password="new-strong-password",
        )
        db_session.refresh(u)
        assert u.must_change_password is False
