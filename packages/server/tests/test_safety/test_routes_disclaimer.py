"""GET /api/disclaimer and POST /api/disclaimer/accept."""

from __future__ import annotations

from openlia.safety.disclaimer import DISCLAIMER_TEXT, DISCLAIMER_VERSION


def test_get_disclaimer_returns_text_and_version(personal_client) -> None:
    resp = personal_client.get("/api/disclaimer")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == DISCLAIMER_VERSION
    assert body["text"] == DISCLAIMER_TEXT


def test_get_disclaimer_status_unaccepted(personal_client) -> None:
    resp = personal_client.get("/api/disclaimer/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is False
    assert body["current_version"] == DISCLAIMER_VERSION


def test_post_accept_then_status_accepted(personal_client) -> None:
    accept = personal_client.post("/api/disclaimer/accept", json={"version": DISCLAIMER_VERSION})
    assert accept.status_code == 200
    status = personal_client.get("/api/disclaimer/status").json()
    assert status["accepted"] is True
    assert status["accepted_version"] == DISCLAIMER_VERSION


def test_post_accept_with_stale_version_400(personal_client) -> None:
    resp = personal_client.post("/api/disclaimer/accept", json={"version": "0.0.1"})
    assert resp.status_code == 400
