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


def test_get_enabled_models_returns_flat_list(
    company_client: TestClient, auth_user, db_session
) -> None:
    from openlia_server.db.models.config import LLMModel, LLMProvider

    prov = LLMProvider(
        id="p-test", kind="openai", label="Test", api_key=None, is_enabled=True
    )
    db_session.add(prov)
    db_session.flush()
    db_session.add(
        LLMModel(
            id="m-on",
            provider_id="p-test",
            model_ref="gpt-x",
            display_name="GPT X",
            is_enabled=True,
        )
    )
    db_session.add(
        LLMModel(
            id="m-off",
            provider_id="p-test",
            model_ref="gpt-off",
            display_name="GPT Off",
            is_enabled=False,
        )
    )
    db_session.commit()

    resp = company_client.get("/settings/models")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    ids = {m["id"] for m in body}
    assert "m-on" in ids
    assert "m-off" not in ids
    on_row = next(m for m in body if m["id"] == "m-on")
    assert on_row["model_ref"] == "gpt-x"
    assert on_row["display_name"] == "GPT X"
    assert on_row["provider_id"] == "p-test"
    assert on_row["provider_kind"] == "openai"
    assert on_row["is_enabled"] is True


def test_get_enabled_models_requires_auth(company_client_anon: TestClient) -> None:
    resp = company_client_anon.get("/settings/models")
    assert resp.status_code == 401
