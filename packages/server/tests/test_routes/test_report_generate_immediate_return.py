"""POST /reports/generate (background path) returns immediately with
report_id and status='generating'. Actual generation runs as a registry
task; response does NOT stream."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


def test_generate_returns_immediately_under_flag(
    monkeypatch: pytest.MonkeyPatch, personal_client: TestClient
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    body = {
        "department_id": "equity_research",
        "mode": "stock_initiation",
        "user_input": "MSFT",
        "enabled_sections": ["company_overview"],
        "length": "standard",
    }
    start = time.monotonic()
    resp = personal_client.post("/reports/generate", json=body)
    elapsed = time.monotonic() - start
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "report_id" in payload
    assert payload["status"] == "generating"
    assert elapsed < 2.0, f"expected fast return; got {elapsed:.2f}s"


def test_generate_persists_original_request_for_retry(
    monkeypatch: pytest.MonkeyPatch, personal_client: TestClient
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    body = {
        "department_id": "equity_research",
        "mode": "stock_initiation",
        "user_input": "AAPL",
        "enabled_sections": ["overview"],
        "length": "brief",
    }
    resp = personal_client.post("/reports/generate", json=body)
    assert resp.status_code == 200, resp.text
    rid = resp.json()["report_id"]
    # Look up the row via the existing reports detail endpoint.
    get_resp = personal_client.get(f"/reports/{rid}")
    assert get_resp.status_code == 200
    body_back = get_resp.json()
    assert body_back["original_request"]["user_input"] == "AAPL"
    assert body_back["original_request"]["length"] == "brief"
