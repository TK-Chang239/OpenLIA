"""Integration: company-mode behind TLS-terminating proxy.

Combines the three production toggles in one assertion path:

- ``OPENLIA_MODE=company`` (auth required).
- ``OPENLIA_TRUST_PROXY_HEADERS=true`` (X-Forwarded-* honoured).
- ``OPENLIA_COOKIE_SECURE=true`` (Secure flag on every session cookie).

The /api prefix strip is exercised by hitting ``/api/auth/login`` rather
than the bare ``/auth/login``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.db import session as session_mod
from openlia_server.db.models.auth import SignupInvite
from openlia_server.services.auth import signup_policy, tokens


def test_company_mode_behind_tls_proxy(monkeypatch, db_session) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "true")

    db_session.add(
        SignupInvite(
            id="inv-proxy-integration",
            token_hash=tokens.hash_token("invite-proxy"),
            created_at=datetime.now(UTC),
        )
    )
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    db_session.commit()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    client = TestClient(app)

    register = client.post(
        "/api/auth/register",
        json={
            "email": "proxy@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": "Proxy",
            "invite_token": "invite-proxy",
        },
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "203.0.113.1",
        },
    )
    assert register.status_code in {200, 201}, register.text

    client.cookies.clear()
    resp = client.post(
        "/api/auth/login",
        json={
            "email": "proxy@example.com",
            "password": "correct-horse-battery-staple",
            "persistent": False,
        },
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "203.0.113.1",
        },
    )
    assert resp.status_code == 200, resp.text
    header = resp.headers.get("set-cookie")
    assert header is not None
    lowered = header.lower()
    assert "secure" in lowered
    assert "httponly" in lowered
