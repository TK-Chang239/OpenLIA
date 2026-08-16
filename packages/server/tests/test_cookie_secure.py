"""Cookie `Secure` flag propagation across mode + override matrix.

Three scenarios:

1. ``personal_mode_default``: OPENLIA_MODE=personal with no override → no
   ``Secure`` flag (auth router is not mounted in personal mode, so we
   verify the helper directly).
2. ``company_mode_default``: OPENLIA_MODE=company with no override →
   ``Secure`` flag is set on the login cookie (production-safe behind a
   TLS-terminating proxy).
3. ``override_off``: OPENLIA_MODE=company AND OPENLIA_COOKIE_SECURE=false
   → no ``Secure`` flag (e.g. LAN-only deployment).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.db import session as session_mod
from openlia_server.db.models.auth import SignupInvite
from openlia_server.routes.auth import build_auth_router, resolve_cookie_secure
from openlia_server.services.auth import signup_policy, tokens


@pytest.mark.parametrize(
    ("mode", "override", "expected"),
    [
        # personal mode, no override -> not secure
        ("personal", None, False),
        # company mode, no override -> secure (production-safe default)
        ("company", None, True),
        # explicit override wins in either mode
        ("company", "false", False),
        ("company", "0", False),
        ("company", "no", False),
        ("company", "true", True),
        ("company", "1", True),
        ("personal", "true", True),
        ("personal", "yes", True),
    ],
)
def test_resolve_cookie_secure_matrix(monkeypatch, mode, override, expected):
    """The single shared helper decides Secure across mode + env-override."""
    monkeypatch.setenv("OPENLIA_MODE", mode)
    if override is None:
        monkeypatch.delenv("OPENLIA_COOKIE_SECURE", raising=False)
    else:
        monkeypatch.setenv("OPENLIA_COOKIE_SECURE", override)
    assert resolve_cookie_secure() is expected


@pytest.fixture
def _seed_invite(db_session):
    db_session.add(
        SignupInvite(
            id="inv-cookie-secure",
            token_hash=tokens.hash_token("invite-cookie-secure"),
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()


def _build_company_client(db_session) -> TestClient:
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)


def _register_and_login_secure_flag(client: TestClient) -> str:
    client.post(
        "/auth/register",
        json={
            "email": "cookie@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": "Cookie",
            "invite_token": "invite-cookie-secure",
        },
    )
    client.cookies.clear()
    resp = client.post(
        "/auth/login",
        json={
            "email": "cookie@example.com",
            "password": "correct-horse-battery-staple",
            "persistent": False,
        },
    )
    assert resp.status_code == 200, resp.text
    header = resp.headers.get("set-cookie")
    assert header is not None
    return header


def test_personal_mode_default(monkeypatch):
    """Auth router is not mounted in personal mode; assert the helper's
    decision matches the documented contract (no Secure flag)."""
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.delenv("OPENLIA_COOKIE_SECURE", raising=False)
    # Probe the shared helper to keep the personal-mode contract testable
    # without mounting a non-existent /auth router.
    assert resolve_cookie_secure() is False
    # Sanity check: the auth router builder still constructs successfully so
    # company-mode wiring is not silently broken.
    router = build_auth_router(db_session_factory=session_mod.SessionLocal)
    assert router.prefix == "/auth"


def test_company_mode_default(monkeypatch, db_session, _seed_invite):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.delenv("OPENLIA_COOKIE_SECURE", raising=False)
    client = _build_company_client(db_session)
    header = _register_and_login_secure_flag(client)
    assert "secure" in header.lower()
    assert "httponly" in header.lower()


def test_override_off(monkeypatch, db_session, _seed_invite):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    client = _build_company_client(db_session)
    header = _register_and_login_secure_flag(client)
    assert "secure" not in header.lower()
    assert "httponly" in header.lower()
