"""Tests for services.auth.registration — register(), normalize_email()."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from openlia_server.db.models.auth import SignupInvite
from openlia_server.services.auth import registration, signup_policy, tokens
from openlia_server.services.auth.errors import AuthError


@pytest.fixture
def make_invite(db_session):
    def _make(token: str = "invite-tok", **kwargs) -> SignupInvite:
        row = SignupInvite(
            id=f"inv-{token}",
            token=token,
            token_hash=tokens.hash_token(token),
            created_at=datetime.now(UTC),
            **kwargs,
        )
        db_session.add(row)
        db_session.commit()
        # Stash raw token on the instance so tests can pass it back to register().
        row.raw_token = token  # type: ignore[attr-defined]
        return row

    return _make


@pytest.fixture(autouse=True)
def _seeded_policy(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")


class TestNormalizeEmail:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("  Alice@Example.COM ", "alice@example.com"),
            ("bob+tag@host.tld", "bob+tag@host.tld"),
        ],
    )
    def test_cases(self, raw, expected):
        assert registration.normalize_email(raw) == expected


class TestRegister:
    def test_success_inserts_user_and_increments_invite(self, db_session, make_invite):
        invite = make_invite(max_uses=5, use_count=0)
        user = registration.register(
            db_session,
            email="alice@example.com",
            password="correct-horse-battery-staple",
            display_name="Alice",
            invite_token=invite.raw_token,
        )
        assert user.email == "alice@example.com"
        db_session.refresh(invite)
        assert invite.use_count == 1

    def test_missing_invite_raises(self, db_session):
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=None,
            )
        assert exc.value.code == "invite_required"

    def test_unknown_invite_raises(self, db_session):
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token="nope",
            )
        assert exc.value.code == "invite_invalid"

    def test_revoked_invite_rejected(self, db_session, make_invite):
        invite = make_invite(
            revoked_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.raw_token,
            )
        assert exc.value.code == "invite_invalid"

    def test_expired_invite_rejected(self, db_session, make_invite):
        invite = make_invite(expires_at=datetime.now(UTC) - timedelta(days=1))
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.raw_token,
            )
        assert exc.value.code == "invite_invalid"

    def test_capped_invite_rejected(self, db_session, make_invite):
        invite = make_invite(max_uses=1, use_count=1)
        with pytest.raises(AuthError):
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.raw_token,
            )

    def test_duplicate_email_returns_generic_error(self, db_session, make_invite, make_user):
        make_user(email="alice@example.com")
        invite = make_invite()
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.raw_token,
            )
        assert exc.value.code == "registration_failed"

    def test_weak_password_rejected(self, db_session, make_invite):
        invite = make_invite()
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="short",
                display_name="Alice",
                invite_token=invite.raw_token,
            )
        assert exc.value.code == "weak_password"

    def test_closed_mode_rejects(self, db_session, make_invite):
        policy = signup_policy.get_policy(db_session)
        policy.mode = "closed"
        db_session.commit()
        invite = make_invite()
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.raw_token,
            )
        assert exc.value.code == "signup_closed"
