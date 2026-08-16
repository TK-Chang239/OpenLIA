"""Regression tests for the setup-wizard takeover spoof (audit 2026-08-16, Stage 0.2).

Two independent defects are covered:

1. The ``/setup/*`` loopback gate must consult the *true* transport peer, never
   a proxy-forwarded ``X-Forwarded-For``. A spoofed ``X-Forwarded-For: 127.0.0.1``
   from a non-loopback peer must not pass the gate, whether or not
   ``OPENLIA_TRUST_PROXY_HEADERS`` is enabled (the documented Caddy /
   Cloudflare Tunnel recipes enable it).
2. ``POST /setup/takeover`` must require an active wizard, so a completed wizard
   cannot be re-taken-over.

The FastAPI ``TestClient`` presents a non-loopback peer (``"testclient"``), so
these tests exercise the real ``_is_loopback_request`` without stubbing it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.db.session import SessionLocal


def _fresh_env(monkeypatch, tmp_path, *, trust_proxy: bool) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)
    if trust_proxy:
        monkeypatch.setenv("OPENLIA_TRUST_PROXY_HEADERS", "true")
    else:
        monkeypatch.delenv("OPENLIA_TRUST_PROXY_HEADERS", raising=False)


def test_spoofed_forwarded_for_blocked_when_trust_disabled(monkeypatch, tmp_path) -> None:
    """Trust OFF: X-Forwarded-For is ignored; a non-loopback peer is rejected."""
    _fresh_env(monkeypatch, tmp_path, trust_proxy=False)
    app = create_app()
    with TestClient(app) as client:
        resp = client.post(
            "/setup/mode",
            json={"mode": "personal"},
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "loopback_required"


def test_spoofed_forwarded_for_blocked_when_trust_enabled(monkeypatch, tmp_path) -> None:
    """Trust ON (documented proxy recipes): a spoofed X-Forwarded-For: 127.0.0.1
    from a non-loopback peer still must NOT pass the loopback gate. This is the
    core takeover-spoof fix: the gate reads the true transport peer.
    """
    _fresh_env(monkeypatch, tmp_path, trust_proxy=True)
    app = create_app()
    with TestClient(app) as client:
        resp = client.post(
            "/setup/takeover",
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "loopback_required"


def test_genuine_loopback_peer_still_allowed(monkeypatch, tmp_path) -> None:
    """Behavior preservation: a real loopback peer still passes the gate so
    local setup works (personal mode, no proxy trust).
    """
    _fresh_env(monkeypatch, tmp_path, trust_proxy=False)
    app = create_app()
    with TestClient(app, client=("127.0.0.1", 40000)) as client:
        resp = client.post("/setup/mode", json={"mode": "personal"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["mode"] == "personal"


def test_takeover_requires_active_wizard(monkeypatch, tmp_path) -> None:
    """Once the wizard is completed, /setup/takeover returns 410 Gone."""
    _fresh_env(monkeypatch, tmp_path, trust_proxy=False)
    app = create_app(is_loopback_request=lambda _: True)
    with TestClient(app) as client:
        db = SessionLocal()
        db.merge(ConfigStore(key="wizard.completed", value="true"))
        db.commit()
        db.close()
        resp = client.post("/setup/takeover")
    assert resp.status_code == 410
    assert resp.json()["detail"]["code"] == "wizard_completed"


def test_takeover_allowed_while_wizard_active(monkeypatch, tmp_path) -> None:
    """Behavior preservation: takeover still works on an active (incomplete) wizard."""
    _fresh_env(monkeypatch, tmp_path, trust_proxy=False)
    app = create_app(is_loopback_request=lambda _: True)
    with TestClient(app) as client:
        resp = client.post("/setup/takeover")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert "openlia_wizard_session" in resp.cookies
