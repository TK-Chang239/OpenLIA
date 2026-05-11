"""Tests for Slice 3 (graph-memory runtime) HTTP routes:

- ``PUT /settings/timezone``
- ``PUT /settings/graph-extraction-time``

Plus regression on ``GET /settings/prefs`` to ensure the new fields surface.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_prefs_returns_timezone_fields(company_client: TestClient, auth_user) -> None:
    """GET /settings/prefs must expose timezone, timezone_source, and graph_extraction_time."""
    resp = company_client.get("/settings/prefs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "UTC"
    assert body["timezone_source"] == "auto"
    assert body["graph_extraction_time"] == "03:00"


def test_put_timezone_auto_updates_when_unset(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/timezone",
        json={"timezone": "America/Los_Angeles", "source": "auto"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "America/Los_Angeles"
    assert body["timezone_source"] == "auto"


def test_put_timezone_manual_locks_out_auto(company_client: TestClient, auth_user) -> None:
    company_client.put(
        "/settings/timezone",
        json={"timezone": "Asia/Taipei", "source": "manual"},
    )
    resp = company_client.put(
        "/settings/timezone",
        json={"timezone": "America/Los_Angeles", "source": "auto"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "Asia/Taipei"
    assert body["timezone_source"] == "manual"


def test_put_timezone_rejects_invalid_iana(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/timezone",
        json={"timezone": "Pacific/Atlantis", "source": "auto"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "invalid_pref"


def test_put_timezone_rejects_invalid_source(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/timezone",
        json={"timezone": "UTC", "source": "guess"},
    )
    assert resp.status_code == 422


def test_put_timezone_requires_auth(company_client_anon: TestClient) -> None:
    resp = company_client_anon.put(
        "/settings/timezone",
        json={"timezone": "UTC", "source": "auto"},
    )
    assert resp.status_code == 401


def test_put_graph_extraction_time_persists(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/graph-extraction-time",
        json={"time": "04:30"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["graph_extraction_time"] == "04:30"


def test_put_graph_extraction_time_rejects_malformed(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/graph-extraction-time",
        json={"time": "25:99"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "invalid_pref"


def test_put_graph_extraction_time_requires_auth(company_client_anon: TestClient) -> None:
    resp = company_client_anon.put(
        "/settings/graph-extraction-time",
        json={"time": "03:00"},
    )
    assert resp.status_code == 401
