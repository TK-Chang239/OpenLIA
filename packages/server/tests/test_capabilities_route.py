"""Tests for GET /api/capabilities endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient
from openlia_server.app import create_app


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)
    return TestClient(create_app())


def test_get_capabilities_returns_engine_version_22(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    r = client.get("/api/capabilities")
    assert r.status_code == 200
    assert r.json()["engine_version"] == "2.2"


def test_get_capabilities_includes_supported_list(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    r = client.get("/api/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert "supported" in body
    assert isinstance(body["supported"], list)
    assert len(body["supported"]) > 0
    first = body["supported"][0]
    assert "id" in first
    assert "summary" in first


def test_get_capabilities_includes_unsupported_with_user_message(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    r = client.get("/api/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert "unsupported" in body
    assert isinstance(body["unsupported"], list)
    assert len(body["unsupported"]) > 0
    first = body["unsupported"][0]
    assert "id" in first
    assert "user_message" in first
