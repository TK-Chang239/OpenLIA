"""Tests for services.auth.sessions — create, validate, revoke, prune."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia_server.services.auth import sessions


class TestCreateSession:
    def test_returns_raw_token_and_row(self, db_session, make_user):
        user = make_user()
        result = sessions.create_session(
            db_session,
            user_id=user.id,
            persistent=True,
            user_agent="pytest/1.0",
            ip_address="127.0.0.1",
        )
        assert len(result.raw_token) > 40
        assert result.session.user_id == user.id
        assert result.session.expires_at > datetime.now(UTC) + timedelta(days=29)
        assert result.session.revoked_at is None

    def test_persistent_sets_30d_ttl(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        delta = r.session.expires_at - datetime.now(UTC)
        assert timedelta(days=29, hours=23) <= delta <= timedelta(days=30, hours=1)

    def test_non_persistent_sets_12h_ttl(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=False)
        delta = r.session.expires_at - datetime.now(UTC)
        assert timedelta(hours=11) <= delta <= timedelta(hours=13)

    def test_token_hash_is_stored_not_plaintext(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=False)
        assert r.session.token_hash != r.raw_token
        assert len(r.session.token_hash) == 64


class TestValidateSession:
    def test_returns_user_on_valid_token(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        validated = sessions.validate_session(db_session, r.raw_token)
        assert validated is not None
        assert validated.user.id == user.id

    def test_returns_none_for_unknown_token(self, db_session):
        assert sessions.validate_session(db_session, "not-a-real-token") is None

    def test_returns_none_for_revoked_session(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        sessions.revoke_session(db_session, r.session.id)
        assert sessions.validate_session(db_session, r.raw_token) is None

    def test_returns_none_for_expired_session(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=False)
        r.session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()
        assert sessions.validate_session(db_session, r.raw_token) is None

    def test_returns_none_for_disabled_user(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        user.is_disabled = True
        db_session.commit()
        assert sessions.validate_session(db_session, r.raw_token) is None

    def test_last_seen_updates_when_stale(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        original = r.session.last_seen_at
        r.session.last_seen_at = original - timedelta(minutes=5)
        db_session.commit()
        sessions.validate_session(db_session, r.raw_token)
        db_session.refresh(r.session)
        assert r.session.last_seen_at > original - timedelta(minutes=5)

    def test_last_seen_not_updated_when_fresh(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        before = r.session.last_seen_at
        sessions.validate_session(db_session, r.raw_token)
        db_session.refresh(r.session)
        assert r.session.last_seen_at == before


class TestRevoke:
    def test_revoke_all_sessions_for_user(self, db_session, make_user):
        user = make_user()
        r1 = sessions.create_session(db_session, user_id=user.id, persistent=True)
        r2 = sessions.create_session(db_session, user_id=user.id, persistent=False)
        sessions.revoke_all_sessions(db_session, user_id=user.id)
        assert sessions.validate_session(db_session, r1.raw_token) is None
        assert sessions.validate_session(db_session, r2.raw_token) is None

    def test_prune_expired(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=False)
        r.session.expires_at = datetime.now(UTC) - timedelta(days=10)
        db_session.commit()

        removed = sessions.prune_expired(db_session, older_than_days=7)
        assert removed == 1
