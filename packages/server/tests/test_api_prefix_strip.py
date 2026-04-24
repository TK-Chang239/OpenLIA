"""`/api` prefix stripping in production (mirror of Vite dev proxy)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from openlia_server.app import create_app


def test_api_prefix_is_stripped_in_production(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)
    app = create_app()
    client = TestClient(app)

    bare = client.get("/healthz")
    prefixed = client.get("/api/healthz")

    assert bare.status_code == 200
    assert prefixed.status_code == 200
    assert bare.json() == prefixed.json()


def test_api_prefix_strip_leaves_non_api_paths_untouched(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)
    app = create_app()
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200
    # /api-ish but not /api/ — must not be stripped.
    assert client.get("/apidoc").status_code == 404
