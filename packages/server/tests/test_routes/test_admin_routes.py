"""Integration tests for /admin/* invites, users, reset-requests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.db.models.auth import PasswordResetRequest, SignupInvite
from openlia_server.middleware.auth import COOKIE_NAME
from openlia_server.services.auth import sessions


@pytest.fixture
def admin_cookie(db_session, make_user, company_client: TestClient):
    admin = make_user(email="admin@example.com", is_admin=True)
    created = sessions.create_session(db_session, user_id=admin.id, persistent=True)
    company_client.cookies.set(COOKIE_NAME, created.raw_token)
    return company_client


class TestInvites:
    def test_create_and_list(self, admin_cookie: TestClient):
        resp = admin_cookie.post("/admin/invites", json={"label": "Q2", "max_uses": 5})
        assert resp.status_code == 201
        token = resp.json()["token"]
        assert token

        resp = admin_cookie.get("/admin/invites")
        assert resp.status_code == 200
        invites = resp.json()
        assert len(invites) == 1
        assert invites[0]["label"] == "Q2"

    def test_create_returns_public_url_when_configured(self, admin_cookie: TestClient, monkeypatch):
        monkeypatch.setenv("OPENLIA_PUBLIC_URL", "https://openlia.example.com")
        resp = admin_cookie.post("/admin/invites", json={"label": "Q2"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["register_url"] == (
            f"https://openlia.example.com/register?invite={body['token']}"
        )

    def test_create_returns_relative_url_when_public_url_unset(
        self, admin_cookie: TestClient, monkeypatch
    ):
        monkeypatch.delenv("OPENLIA_PUBLIC_URL", raising=False)
        resp = admin_cookie.post("/admin/invites", json={})
        assert resp.status_code == 201
        body = resp.json()
        assert body["register_url"] == f"/register?invite={body['token']}"

    def test_revoke(self, admin_cookie: TestClient, db_session):
        invite = SignupInvite(id="inv-x", token_hash="tok-x", created_at=datetime.now(UTC))
        db_session.add(invite)
        db_session.commit()
        resp = admin_cookie.post(f"/admin/invites/{invite.id}/revoke")
        assert resp.status_code == 204
        db_session.refresh(invite)
        assert invite.revoked_at is not None

    def test_non_admin_rejected(self, company_client: TestClient, make_user, db_session):
        user = make_user()
        created = sessions.create_session(db_session, user_id=user.id, persistent=True)
        company_client.cookies.set(COOKIE_NAME, created.raw_token)
        resp = company_client.get("/admin/invites")
        assert resp.status_code == 403


class TestPasswordResetRequests:
    def test_list_approve(self, admin_cookie: TestClient, db_session, make_user):
        user = make_user(email="alice@example.com")
        req = PasswordResetRequest(
            id="req-1",
            user_id=user.id,
            status="pending",
            requested_at=datetime.now(UTC),
        )
        db_session.add(req)
        db_session.commit()

        resp = admin_cookie.get("/admin/password-reset-requests")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = admin_cookie.post(f"/admin/password-reset-requests/{req.id}/approve")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reset_token"]

    def test_reject(self, admin_cookie: TestClient, db_session, make_user):
        user = make_user(email="alice@example.com")
        req = PasswordResetRequest(
            id="req-2",
            user_id=user.id,
            status="pending",
            requested_at=datetime.now(UTC),
        )
        db_session.add(req)
        db_session.commit()

        resp = admin_cookie.post(f"/admin/password-reset-requests/{req.id}/reject")
        assert resp.status_code == 204
        db_session.refresh(req)
        assert req.status == "rejected"


class TestUserManagement:
    def test_list(self, admin_cookie: TestClient, make_user):
        make_user(email="alice@example.com")
        resp = admin_cookie.get("/admin/users")
        assert resp.status_code == 200
        emails = {u["email"] for u in resp.json()}
        assert "alice@example.com" in emails
        assert "admin@example.com" in emails

    def test_disable_and_enable(self, admin_cookie: TestClient, make_user, db_session):
        alice = make_user(email="alice@example.com")
        resp = admin_cookie.post(f"/admin/users/{alice.id}/disable")
        assert resp.status_code == 204
        db_session.refresh(alice)
        assert alice.is_disabled is True

        resp = admin_cookie.post(f"/admin/users/{alice.id}/enable")
        assert resp.status_code == 204
        db_session.refresh(alice)
        assert alice.is_disabled is False

    def test_direct_reset_password(self, admin_cookie: TestClient, make_user, db_session):
        alice = make_user(email="alice@example.com")
        resp = admin_cookie.post(
            f"/admin/users/{alice.id}/reset-password",
            json={},
        )
        assert resp.status_code == 200
        body = resp.json()
        temp_password = body["temporary_password"]
        assert isinstance(temp_password, str)
        assert len(temp_password) >= 8
        db_session.refresh(alice)
        assert alice.must_change_password is True

    def test_direct_reset_does_not_leak_temp_password_on_get(
        self, admin_cookie: TestClient, make_user, db_session
    ):
        alice = make_user(email="alice2@example.com")
        admin_cookie.post(f"/admin/users/{alice.id}/reset-password", json={})
        resp = admin_cookie.get("/admin/users")
        assert resp.status_code == 200
        # No reset payloads ever returned by listing endpoint.
        assert "temporary_password" not in resp.text

    def test_direct_reset_revokes_sessions(
        self, admin_cookie: TestClient, make_user, db_session, company_client: TestClient
    ):
        alice = make_user(email="alice3@example.com")
        # Establish an active session for alice.
        existing = sessions.create_session(db_session, user_id=alice.id, persistent=True)
        assert existing.raw_token
        db_session.commit()
        resp = admin_cookie.post(f"/admin/users/{alice.id}/reset-password", json={})
        assert resp.status_code == 200
        from openlia_server.db.models.auth import Session as DBSessionRow

        db_session.expire_all()
        rows = db_session.query(DBSessionRow).filter_by(user_id=alice.id).all()
        assert rows
        assert all(r.revoked_at is not None for r in rows)

    def test_admin_invites_blocks_must_change_admin(
        self, company_client: TestClient, make_user, db_session
    ):
        admin = make_user(email="forced-admin-x@example.com", is_admin=True)
        admin.must_change_password = True
        db_session.commit()
        created = sessions.create_session(db_session, user_id=admin.id, persistent=True)
        company_client.cookies.set(COOKIE_NAME, created.raw_token)
        resp = company_client.get("/admin/invites")
        assert resp.status_code == 403
        body = resp.json()
        assert body["detail"] == {"code": "must_change_password"}

    def test_disable_user_revokes_sessions(self, admin_cookie: TestClient, make_user, db_session):
        alice = make_user(email="alice4@example.com")
        existing = sessions.create_session(db_session, user_id=alice.id, persistent=True)
        assert existing.raw_token
        db_session.commit()
        resp = admin_cookie.post(f"/admin/users/{alice.id}/disable")
        assert resp.status_code == 204
        from openlia_server.db.models.auth import Session as DBSessionRow

        db_session.expire_all()
        rows = db_session.query(DBSessionRow).filter_by(user_id=alice.id).all()
        assert rows
        assert all(r.revoked_at is not None for r in rows)

    def test_invite_token_round_trips_via_hash(self, admin_cookie: TestClient, db_session):
        from openlia_server.services.auth import tokens

        resp = admin_cookie.post("/admin/invites", json={"label": "Q3"})
        assert resp.status_code == 201
        token = resp.json()["token"]
        assert isinstance(token, str) and len(token) >= 16
        # Token is opaque; only a hash is stored. Listing never leaks raw token.
        resp_list = admin_cookie.get("/admin/invites")
        assert resp_list.status_code == 200
        rows = resp_list.json()
        assert all("token" not in r for r in rows)
        # Hash must match exactly one stored row.
        invite = (
            db_session.query(SignupInvite)
            .filter_by(token_hash=tokens.hash_token(token))
            .one_or_none()
        )
        assert invite is not None

    def test_approve_reset_request_is_one_shot(
        self, admin_cookie: TestClient, make_user, db_session
    ):
        user = make_user(email="approve@example.com")
        req = PasswordResetRequest(
            id="req-once",
            user_id=user.id,
            status="pending",
            requested_at=datetime.now(UTC),
        )
        db_session.add(req)
        db_session.commit()
        resp = admin_cookie.post(f"/admin/password-reset-requests/{req.id}/approve")
        assert resp.status_code == 200
        # Approving the same request again must fail (status moved off pending).
        resp_again = admin_cookie.post(f"/admin/password-reset-requests/{req.id}/approve")
        assert resp_again.status_code == 404


def _admin_session(company_client: TestClient, db_session, admin) -> TestClient:
    created = sessions.create_session(db_session, user_id=admin.id, persistent=True)
    company_client.cookies.set(COOKIE_NAME, created.raw_token)
    return company_client


class TestAdminLifecycle:
    def test_self_disable_blocked(self, company_client: TestClient, make_user, db_session):
        admin = make_user(email="root@example.com", is_admin=True)
        # A second active admin keeps this from being the last-admin path.
        make_user(email="backup-admin@example.com", is_admin=True)
        client = _admin_session(company_client, db_session, admin)
        resp = client.post(f"/admin/users/{admin.id}/disable")
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "cannot_disable_self"
        db_session.refresh(admin)
        assert admin.is_disabled is False

    def test_last_admin_disable_blocked(self, company_client: TestClient, make_user, db_session):
        admin = make_user(email="solo@example.com", is_admin=True)
        client = _admin_session(company_client, db_session, admin)
        resp = client.post(f"/admin/users/{admin.id}/disable")
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "last_admin"
        db_session.refresh(admin)
        assert admin.is_disabled is False

    def test_promote_then_demote(self, admin_cookie: TestClient, make_user, db_session):
        alice = make_user(email="alice@example.com")
        resp = admin_cookie.post(f"/admin/users/{alice.id}/role", json={"is_admin": True})
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True
        db_session.refresh(alice)
        assert alice.is_admin is True

        # admin@example.com (fixture) is still an admin, so alice is not the last.
        resp = admin_cookie.post(f"/admin/users/{alice.id}/role", json={"is_admin": False})
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is False
        db_session.refresh(alice)
        assert alice.is_admin is False

    def test_last_admin_demote_blocked(self, company_client: TestClient, make_user, db_session):
        admin = make_user(email="onlyadmin@example.com", is_admin=True)
        client = _admin_session(company_client, db_session, admin)
        resp = client.post(f"/admin/users/{admin.id}/role", json={"is_admin": False})
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "last_admin"
        db_session.refresh(admin)
        assert admin.is_admin is True

    def test_role_unknown_user_404(self, admin_cookie: TestClient):
        resp = admin_cookie.post("/admin/users/nope/role", json={"is_admin": True})
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "user_not_found"


class TestAdminRateLimit:
    def test_write_endpoint_throttled(self, admin_cookie: TestClient):
        from openlia_server.routes.admin import ADMIN_WRITE_LIMIT

        for _ in range(ADMIN_WRITE_LIMIT):
            assert admin_cookie.post("/admin/invites", json={}).status_code == 201
        resp = admin_cookie.post("/admin/invites", json={})
        assert resp.status_code == 429
        assert resp.json()["detail"]["code"] == "rate_limited"
