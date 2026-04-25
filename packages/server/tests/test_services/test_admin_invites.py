"""Service-level coverage for invite token hashing (Phase 11)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import SignupInvite, User
from openlia_server.services.auth import passwords, registration, signup_policy, tokens


@pytest.fixture
def admin_user(db_session) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email="invite-admin@example.com",
        display_name="invite-admin",
        password_hash=passwords.hash_password("initial-strong-pass"),
        is_admin=True,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_invite(db_session, admin_user: User, *, label: str | None = None) -> tuple[str, str]:
    raw = tokens.generate_opaque_token()
    invite = SignupInvite(
        id=str(uuid.uuid4()),
        token_hash=tokens.hash_token(raw),
        label=label,
        max_uses=None,
        use_count=0,
        expires_at=None,
        created_by_user_id=admin_user.id,
        created_at=datetime.now(UTC),
    )
    db_session.add(invite)
    db_session.commit()
    return invite.id, raw


class TestInviteTokenHashing:
    def test_only_hash_persisted(self, db_session, admin_user):
        invite_id, raw = _create_invite(db_session, admin_user)
        invite = db_session.get(SignupInvite, invite_id)
        assert invite.token_hash != raw
        assert invite.token_hash == tokens.hash_token(raw)

    def test_lookup_by_hash_round_trip(self, db_session, admin_user):
        _, raw = _create_invite(db_session, admin_user)
        match = (
            db_session.query(SignupInvite)
            .filter_by(token_hash=tokens.hash_token(raw))
            .one_or_none()
        )
        assert match is not None

    def test_invite_consumption_increments_use_count(self, db_session, admin_user):
        signup_policy.seed_signup_policy(db_session, mode_flag="company")
        _, raw = _create_invite(db_session, admin_user)
        registration.register(
            db_session,
            email="signup@example.com",
            password="brand-new-strong-pass",
            display_name="Signup",
            invite_token=raw,
        )
        invite = db_session.query(SignupInvite).filter_by(token_hash=tokens.hash_token(raw)).one()
        assert invite.use_count == 1
