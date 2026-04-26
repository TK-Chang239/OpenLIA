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
        body = resp.json()
        assert body["email"] == "alice@example.com"
        assert body["is_admin"] is False
        assert body["must_change_password"] is False

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

    def test_login_rotates_prior_session(
        self, company_client: TestClient, db_session, seeded_invite
    ):
        from openlia_server.services.auth import sessions

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

        # Seed a stale session for the same user, attach the cookie to the client.
        from openlia_server.db.models.auth import User

        alice = db_session.query(User).filter_by(email="alice@example.com").one()
        stale = sessions.create_session(db_session, user_id=alice.id, persistent=False)
        company_client.cookies.set(COOKIE_NAME, stale.raw_token)

        resp = company_client.post(
            "/auth/login",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "persistent": False,
            },
        )
        assert resp.status_code == 200

        # Prior session must be revoked. Expire local entities so the
        # identity-map cache doesn't mask the cross-session commit.
        db_session.expire_all()
        assert sessions.validate_session(db_session, stale.raw_token) is None
        # New cookie value differs from the stale one.
        new_cookie = resp.cookies.get(COOKIE_NAME)
        assert new_cookie is not None
        assert new_cookie != stale.raw_token


class TestSignupPolicyEndpoint:
    def test_returns_mode(self, company_client: TestClient):
        resp = company_client.get("/auth/signup-policy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "invite_only"
        assert data["invite_required"] is True


class TestRegisterDisplayName:
    def test_register_accepts_missing_display_name(
        self, company_client: TestClient, seeded_invite, db_session
    ):
        from openlia_server.db.models.auth import User

        resp = company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "invite_token": "valid-invite",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        # Backend defaults display_name to email local-part on blank input.
        assert body["display_name"] == "alice"
        # All five fields are present on the register response (NEW-9-04 shape).
        assert set(body.keys()) >= {
            "user_id",
            "email",
            "display_name",
            "is_admin",
            "must_change_password",
        }
        assert body["is_admin"] is False
        assert body["must_change_password"] is False

        db_session.expire_all()
        user = db_session.query(User).filter_by(email="alice@example.com").one()
        assert user.display_name == "alice"

    def test_register_accepts_blank_display_name(self, company_client: TestClient, seeded_invite):
        resp = company_client.post(
            "/auth/register",
            json={
                "email": "bob@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "   ",
                "invite_token": "valid-invite",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["display_name"] == "bob"


class TestLoginLockoutPayload:
    def test_account_locked_payload_three_keys(self, company_client: TestClient, seeded_invite):
        # Register a user, then bombard with bad-password attempts to trigger
        # AccountLockedError. Threshold is 5 (see services/auth/login.py).
        company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "invite_token": "valid-invite",
            },
        )
        company_client.post("/auth/logout")

        last = None
        for _ in range(6):
            last = company_client.post(
                "/auth/login",
                json={
                    "email": "alice@example.com",
                    "password": "wrong",
                    "persistent": False,
                },
            )
        assert last is not None
        assert last.status_code == 423
        body = last.json()
        assert body["code"] == "account_locked"
        assert body["message"] == "Account is temporarily locked."
        assert isinstance(body["metadata"], dict)
        assert "retry_after_seconds" in body["metadata"]
        assert isinstance(body["metadata"]["retry_after_seconds"], int)
        assert body["metadata"]["retry_after_seconds"] > 0


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

    def test_email_domain_rejected(self, company_client: TestClient, db_session, seeded_invite):
        from openlia_server.db.models.auth import SignupPolicy
        from sqlalchemy import select

        policy = db_session.execute(select(SignupPolicy)).scalar_one()
        policy.allowed_email_domains = ["company.com"]
        db_session.commit()

        resp = company_client.post(
            "/auth/register",
            json={
                "email": "alice@otherdomain.com",
                "password": "correct-horse-battery-staple",
                "display_name": "Alice",
                "invite_token": "valid-invite",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "email_domain_not_allowed"


class TestPasswordResetFlow:
    def test_request_always_200(self, company_client: TestClient):
        resp = company_client.post(
            "/auth/password-reset/request", json={"email": "nobody@example.com"}
        )
        assert resp.status_code == 200

    def test_request_approve_consume_revokes_sessions_and_replay_blocked(
        self, company_client: TestClient, db_session, seeded_invite, make_user
    ):
        from openlia_server.services.auth import password_reset, sessions

        user = make_user(email="reset-me@example.com", is_admin=False)
        # Seed an active session for the user — it must be revoked on consume.
        active = sessions.create_session(db_session, user_id=user.id, persistent=False)

        # 1) Request a reset.
        resp = company_client.post("/auth/password-reset/request", json={"email": user.email})
        assert resp.status_code == 200

        # 2) Approve via the service (no admin route needed for this regression).
        from openlia_server.db.models.auth import PasswordResetRequest

        req = (
            db_session.query(PasswordResetRequest)
            .filter_by(user_id=user.id, status="pending")
            .one()
        )
        raw_token = password_reset.approve_request(
            db_session, request_id=req.id, admin_user_id=user.id
        )

        # 3) Consume the token.
        resp = company_client.post(
            "/auth/password-reset/consume",
            json={"token": raw_token, "new_password": "brand-new-strong-pass-2026"},
        )
        assert resp.status_code == 200, resp.text

        # Active session must be revoked.
        db_session.expire_all()
        assert sessions.validate_session(db_session, active.raw_token) is None

        # 4) Replay the same token — must fail with token_invalid.
        resp = company_client.post(
            "/auth/password-reset/consume",
            json={"token": raw_token, "new_password": "another-strong-pass-2026"},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "token_invalid"


class TestRateLimits:
    def test_login_ip_429_after_20(self, company_client: TestClient):
        # Distinct emails so the per-email bucket never trips first.
        for i in range(20):
            company_client.post(
                "/auth/login",
                json={"email": f"u{i}@example.com", "password": "x", "persistent": False},
            )
        resp = company_client.post(
            "/auth/login",
            json={"email": "u-final@example.com", "password": "x", "persistent": False},
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "rate_limited"

    def test_login_email_429_after_10(self, company_client: TestClient):
        # Force-trip the email bucket for one address. Each call also ticks the
        # IP bucket; 10 < 20 so the IP cap does not trigger first.
        for _ in range(10):
            company_client.post(
                "/auth/login",
                json={"email": "alice@example.com", "password": "x", "persistent": False},
            )
        resp = company_client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "x", "persistent": False},
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "rate_limited"

    def test_register_429_after_5(self, company_client: TestClient):
        for i in range(5):
            company_client.post(
                "/auth/register",
                json={
                    "email": f"u{i}@example.com",
                    "password": "correct-horse-battery-staple",
                    "display_name": "X",
                    "invite_token": "x",
                },
            )
        resp = company_client.post(
            "/auth/register",
            json={
                "email": "u-final@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "X",
                "invite_token": "x",
            },
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "rate_limited"

    def test_password_reset_429_after_5(self, company_client: TestClient):
        for i in range(5):
            company_client.post("/auth/password-reset/request", json={"email": f"u{i}@example.com"})
        resp = company_client.post(
            "/auth/password-reset/request", json={"email": "u-final@example.com"}
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "rate_limited"


def _login_and_get_set_cookie(client: TestClient, *, persistent: bool) -> str:
    client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": "Alice",
            "invite_token": "valid-invite",
        },
    )
    client.cookies.clear()
    resp = client.post(
        "/auth/login",
        json={
            "email": "alice@example.com",
            "password": "correct-horse-battery-staple",
            "persistent": persistent,
        },
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie")
    assert set_cookie is not None, resp.headers
    return set_cookie


class TestCookieFlags:
    def test_login_sets_httponly_lax_path_persistent(
        self, company_client: TestClient, seeded_invite
    ):
        header = _login_and_get_set_cookie(company_client, persistent=True)
        lowered = header.lower()
        assert "httponly" in lowered
        assert "samesite=lax" in lowered
        assert "path=/" in lowered
        # 30-day Max-Age = 2592000
        assert "max-age=2592000" in lowered

    def test_login_no_max_age_when_not_persistent(self, company_client: TestClient, seeded_invite):
        header = _login_and_get_set_cookie(company_client, persistent=False)
        assert "max-age" not in header.lower()

    def test_login_sets_secure_when_env_true(self, db_session, monkeypatch):
        monkeypatch.setenv("OPENLIA_MODE", "company")
        monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "true")
        from openlia_server.app import create_app
        from openlia_server.db import session as session_mod
        from openlia_server.services.auth import signup_policy

        signup_policy.seed_signup_policy(db_session, mode_flag="company")
        # Seed the invite directly — the seeded_invite fixture is bound to a
        # different DB session and we need it visible here.
        from datetime import UTC, datetime

        from openlia_server.db.models.auth import SignupInvite
        from openlia_server.services.auth import tokens

        db_session.add(
            SignupInvite(
                id="inv-secure",
                token_hash=tokens.hash_token("valid-invite"),
                created_at=datetime.now(UTC),
            )
        )
        db_session.commit()

        app = create_app(db_session_factory=session_mod.SessionLocal)
        # `Secure` cookies are dropped by httpx over http://testserver, so
        # don't use the cookie jar — read the header directly off the response.
        client = TestClient(app)
        client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "Alice",
                "invite_token": "valid-invite",
            },
        )
        client.cookies.clear()
        resp = client.post(
            "/auth/login",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "persistent": False,
            },
        )
        assert resp.status_code == 200
        header = resp.headers.get("set-cookie")
        assert header is not None
        assert "secure" in header.lower()

    def test_login_omits_secure_when_env_false(self, company_client: TestClient, seeded_invite):
        # The default company_client fixture sets OPENLIA_COOKIE_SECURE=false.
        header = _login_and_get_set_cookie(company_client, persistent=False)
        assert "secure" not in header.lower()


# Tests use /api/* paths because that's how real browsers call the API —
# the strip-prefix middleware turns /api/... into /... before routing, and
# tags the scope so the SPA fallback knows not to serve index.html on miss.
_AUTH_ROUTE_CASES = [
    ("post", "/api/auth/register", {"email": "x@y.z", "password": "x", "display_name": "X"}),
    ("post", "/api/auth/login", {"email": "x@y.z", "password": "x", "persistent": False}),
    ("post", "/api/auth/logout", None),
    ("post", "/api/auth/logout-all", None),
    ("get", "/api/auth/session", None),
    ("get", "/api/auth/signup-policy", None),
    ("post", "/api/auth/password-reset/request", {"email": "x@y.z"}),
    ("post", "/api/auth/password-reset/consume", {"token": "x", "new_password": "12345678"}),
    ("post", "/api/auth/change-password", {"current_password": "x", "new_password": "12345678"}),
]

_ADMIN_ROUTE_CASES = [
    ("get", "/api/admin/invites", None),
    ("post", "/api/admin/invites", {"label": "x"}),
    ("post", "/api/admin/invites/x/revoke", None),
    ("get", "/api/admin/users", None),
    ("post", "/api/admin/users/x/disable", None),
    ("post", "/api/admin/users/x/enable", None),
    ("post", "/api/admin/users/x/reset-password", None),
    ("get", "/api/admin/password-reset-requests", None),
    ("post", "/api/admin/password-reset-requests/x/approve", None),
    ("post", "/api/admin/password-reset-requests/x/reject", None),
]


class TestPersonalModeNoAuthRoutes:
    @pytest.mark.parametrize(("method", "path", "body"), _AUTH_ROUTE_CASES)
    def test_personal_mode_auth_routes_404(
        self, personal_client: TestClient, method: str, path: str, body
    ):
        resp = (
            getattr(personal_client, method)(path, json=body)
            if body
            else getattr(personal_client, method)(path)
        )
        assert resp.status_code == 404, (path, resp.status_code, resp.text)

    @pytest.mark.parametrize(("method", "path", "body"), _ADMIN_ROUTE_CASES)
    def test_personal_mode_admin_routes_404(
        self, personal_client: TestClient, method: str, path: str, body
    ):
        resp = (
            getattr(personal_client, method)(path, json=body)
            if body
            else getattr(personal_client, method)(path)
        )
        assert resp.status_code == 404, (path, resp.status_code, resp.text)
