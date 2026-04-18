"""Tests for services.auth.login — authenticate(), lockout state machine."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from openlia_server.db.models.auth import AuthEvent
from openlia_server.services.auth import login
from openlia_server.services.auth.errors import AuthError


@pytest.fixture
def enable_lockout(db_session):
    from openlia_server.db.models.infrastructure import ConfigStore
    db_session.add(ConfigStore(
        key="auth.lockout.enabled",
        value={"enabled": True},
        updated_at=datetime.now(timezone.utc),
    ))
    db_session.commit()


class TestAuthenticate:
    def test_success(self, db_session, make_user):
        u = make_user(password="correct-pw-long-enough")
        result = login.authenticate(
            db_session, email="alice@example.com", password="correct-pw-long-enough"
        )
        assert result.user.id == u.id
        assert result.must_change_password is False

    def test_wrong_password_raises_invalid_credentials(self, db_session, make_user):
        make_user()
        with pytest.raises(AuthError) as exc:
            login.authenticate(db_session, email="alice@example.com", password="wrong")
        assert exc.value.code == "invalid_credentials"

    def test_unknown_email_raises_invalid_credentials(self, db_session):
        with pytest.raises(AuthError) as exc:
            login.authenticate(db_session, email="nobody@example.com", password="whatever")
        assert exc.value.code == "invalid_credentials"

    def test_disabled_account(self, db_session, make_user):
        make_user(is_disabled=True)
        with pytest.raises(AuthError) as exc:
            login.authenticate(
                db_session, email="alice@example.com", password="correct horse battery staple"
            )
        assert exc.value.code == "account_disabled"

    def test_must_change_password_flag_returned(self, db_session, make_user):
        u = make_user()
        u.must_change_password = True
        db_session.commit()
        result = login.authenticate(
            db_session, email="alice@example.com", password="correct horse battery staple"
        )
        assert result.must_change_password is True


class TestLockout:
    def test_five_failures_lock(self, db_session, make_user, enable_lockout):
        make_user()
        for _ in range(5):
            with pytest.raises(AuthError):
                login.authenticate(db_session, email="alice@example.com", password="nope")

        with pytest.raises(AuthError) as exc:
            login.authenticate(
                db_session, email="alice@example.com", password="correct horse battery staple"
            )
        assert exc.value.code == "account_locked"

    def test_lockout_disabled_doesnt_lock(self, db_session, make_user):
        from openlia_server.db.models.infrastructure import ConfigStore
        db_session.add(ConfigStore(
            key="auth.lockout.enabled",
            value={"enabled": False},
            updated_at=datetime.now(timezone.utc),
        ))
        db_session.commit()
        make_user()
        for _ in range(6):
            with pytest.raises(AuthError):
                login.authenticate(db_session, email="alice@example.com", password="nope")
        result = login.authenticate(
            db_session, email="alice@example.com", password="correct horse battery staple"
        )
        assert result.user.email == "alice@example.com"

    def test_success_resets_failure_counter(self, db_session, make_user, enable_lockout):
        u = make_user()
        for _ in range(3):
            with pytest.raises(AuthError):
                login.authenticate(db_session, email="alice@example.com", password="nope")
        db_session.refresh(u)
        assert u.failed_login_attempts == 3

        login.authenticate(
            db_session, email="alice@example.com", password="correct horse battery staple"
        )
        db_session.refresh(u)
        assert u.failed_login_attempts == 0
        assert u.locked_until is None


def test_auth_events_emitted(db_session, make_user):
    make_user()
    with pytest.raises(AuthError):
        login.authenticate(db_session, email="alice@example.com", password="wrong")
    evts = list(db_session.execute(select(AuthEvent)).scalars())
    assert any(e.event_type == "login_failure" for e in evts)
