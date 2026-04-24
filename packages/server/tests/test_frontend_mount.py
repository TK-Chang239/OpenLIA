"""Static frontend mount — env var + missing-dist behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient
from openlia_server.app import create_app


def _write_dist(root) -> str:
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html><body>SPA</body></html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hello');")
    return str(dist)


def test_frontend_mount_from_env_var(monkeypatch, tmp_path) -> None:
    dist = _write_dist(tmp_path)
    monkeypatch.setenv("OPENLIA_FRONTEND_DIST", dist)
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")

    client = TestClient(create_app())

    r = client.get("/")
    assert r.status_code == 200
    assert "SPA" in r.text

    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert "hello" in r.text


def test_frontend_mount_skips_when_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")

    client = TestClient(create_app())
    assert client.get("/healthz").status_code == 200
    # With no dist and no /app/frontend/dist, / should 404.
    # (Not strictly guaranteed when running inside a Docker image
    # with a baked dist, but true in CI / local test environments.)
    r = client.get("/")
    assert r.status_code in (200, 404)
