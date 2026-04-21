"""Integration tests for /auth/* — registration, login, logout, session."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.db.models.auth import SignupInvite
from openlia_server.middleware.auth import COOKIE_NAME
from openlia_server.services.auth import tokens


@pytest.fixture
def seeded_invite(db_session):
    row = SignupInvite(
        id="inv-1",
        token="valid-invite",
        token_hash=tokens.hash_token("valid-invite"),
        created_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    return row


class TestRegisterLoginLogout:
    def test_full_cycle(self, company_client: TestClient, seeded_invite):
        resp = company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "Alice",
                "invite_token": "valid-invite",
            },
        )
        assert resp.status_code == 201
        assert COOKIE_NAME in resp.cookies

        resp = company_client.get("/auth/session")
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"

        resp = company_client.post("/auth/logout")
        assert resp.status_code == 204

        resp = company_client.get("/auth/session")
        assert resp.status_code == 401

    def test_login_with_keep_me_signed_in(self, company_client: TestClient, seeded_invite):
        company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "Alice",
                "invite_token": "valid-invite",
            },
        )
        company_client.post("/auth/logout")

        resp = company_client.post(
            "/auth/login",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "persistent": True,
            },
        )
        assert resp.status_code == 200

    def test_login_invalid_credentials(self, company_client: TestClient, seeded_invite):
        resp = company_client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "nope", "persistent": False},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "invalid_credentials"


class TestSignupPolicyEndpoint:
    def test_returns_mode(self, company_client: TestClient):
        resp = company_client.get("/auth/signup-policy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "invite_only"
        assert data["invite_required"] is True


class TestRegisterErrors:
    def test_without_invite(self, company_client: TestClient):
        resp = company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "Alice",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "invite_required"

    def test_weak_password(self, company_client: TestClient, seeded_invite):
        resp = company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "short",
                "display_name": "Alice",
                "invite_token": "valid-invite",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "weak_password"


class TestPasswordResetFlow:
    def test_request_always_200(self, company_client: TestClient):
        resp = company_client.post(
            "/auth/password-reset/request", json={"email": "nobody@example.com"}
        )
        assert resp.status_code == 200


class TestPersonalModeNoAuthRoutes:
    def test_register_returns_404(self, personal_client: TestClient):
        resp = personal_client.post(
            "/auth/register",
            json={
                "email": "x@y.z",
                "password": "12345678",
                "display_name": "X",
                "invite_token": "x",
            },
        )
        assert resp.status_code == 404

    def test_session_resolves_local(self, personal_client: TestClient):
        resp = personal_client.get("/auth/session")
        assert resp.status_code == 404
