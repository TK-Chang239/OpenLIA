"""Tests for GET/PATCH /settings/prefs."""

from fastapi.testclient import TestClient


def test_get_prefs_returns_defaults(company_client: TestClient, auth_user) -> None:
    resp = company_client.get("/settings/prefs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] == "system"
    assert body["notify_inapp"] is True
    assert body["display_name"] == auth_user.display_name


def test_patch_prefs_partial_update(company_client: TestClient, auth_user) -> None:
    resp = company_client.patch(
        "/settings/prefs",
        json={"theme": "dark", "notify_email": True, "display_name": "NewName"},
    )
    assert resp.status_code == 200
    assert resp.json()["theme"] == "dark"
    assert resp.json()["notify_email"] is True
    assert resp.json()["display_name"] == "NewName"


def test_patch_prefs_rejects_invalid(company_client: TestClient, auth_user) -> None:
    resp = company_client.patch("/settings/prefs", json={"theme": "rainbow"})
    assert resp.status_code == 422


def test_get_prefs_requires_auth(company_client_anon: TestClient) -> None:
    resp = company_client_anon.get("/settings/prefs")
    assert resp.status_code == 401


def test_get_registered_departments(company_client: TestClient, auth_user) -> None:
    resp = company_client.get("/settings/departments")
    assert resp.status_code == 200
    deps = resp.json()["departments"]
    assert "secretary" in deps
    assert "equity_research" in deps


def test_get_registered_departments_requires_auth(company_client_anon: TestClient) -> None:
    resp = company_client_anon.get("/settings/departments")
    assert resp.status_code == 401
