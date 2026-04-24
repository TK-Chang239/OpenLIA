"""OPENLIA_TRUST_PROXY_HEADERS wiring for reverse-proxy deployments."""

from __future__ import annotations

from fastapi.testclient import TestClient
from openlia_server.app import create_app


def test_forwarded_headers_ignored_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.delenv("OPENLIA_TRUST_PROXY_HEADERS", raising=False)
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)

    app = create_app()
    client = TestClient(app)

    r = client.get(
        "/_debug/client_host",
        headers={
            "X-Forwarded-For": "203.0.113.42",
            "X-Forwarded-Proto": "https",
        },
    )
    assert r.status_code == 200
    assert r.json()["host"] != "203.0.113.42"


def test_forwarded_headers_honored_when_flag_set(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.setenv("OPENLIA_TRUST_PROXY_HEADERS", "true")
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)

    app = create_app()
    client = TestClient(app)

    r = client.get(
        "/_debug/client_host",
        headers={
            "X-Forwarded-For": "203.0.113.42",
            "X-Forwarded-Proto": "https",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["host"] == "203.0.113.42"
    assert body["scheme"] == "https"
