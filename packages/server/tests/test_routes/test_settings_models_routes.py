"""Tests for GET/PUT/DELETE /settings/admin/llm/preferences."""

from fastapi.testclient import TestClient


def test_get_preferences_returns_empty_when_none(company_client: TestClient, auth_user) -> None:
    resp = company_client.get("/settings/admin/llm/preferences")
    assert resp.status_code == 200
    assert resp.json()["preferences"] == {}


def test_put_preference_persists(company_client: TestClient, auth_user, seed_admin_roster) -> None:
    model = seed_admin_roster["thinking"][0]
    resp = company_client.put(
        "/settings/admin/llm/preferences",
        json={"tier": "thinking", "model_id": model.id},
    )
    assert resp.status_code == 200

    listed = company_client.get("/settings/admin/llm/preferences").json()
    assert listed["preferences"]["thinking"] == model.id


def test_delete_preference_falls_back_to_default(
    company_client: TestClient, auth_user, seed_admin_roster
) -> None:
    model = seed_admin_roster["thinking"][0]
    company_client.put(
        "/settings/admin/llm/preferences",
        json={"tier": "thinking", "model_id": model.id},
    )
    resp = company_client.delete("/settings/admin/llm/preferences/thinking")
    assert resp.status_code == 200
    assert company_client.get("/settings/admin/llm/preferences").json()["preferences"] == {}


def test_put_preference_rejects_unknown_model(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/admin/llm/preferences",
        json={"tier": "thinking", "model_id": "nope"},
    )
    assert resp.status_code == 404
