"""Tests for GET /api/report-templates/conversion_prompt."""

from __future__ import annotations

from fastapi.testclient import TestClient
from openlia_server.app import create_app


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)
    return TestClient(create_app())


def test_get_conversion_prompt_returns_text(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    r = client.get("/api/report-templates/conversion_prompt")
    assert r.status_code == 200
    body = r.json()
    assert "prompt" in body
    assert isinstance(body["prompt"], str)
    assert len(body["prompt"]) > 0


def test_conversion_prompt_mentions_reserved_keys(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    r = client.get("/api/report-templates/conversion_prompt")
    assert r.status_code == 200
    prompt = r.json()["prompt"]
    assert "extra_passes" in prompt
    assert "loops" in prompt
