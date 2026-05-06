"""HTTP tests for /api/departments/{department}/model-pref."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def model_id(db_session):
    from openlia_server.db.models.config import LLMModel, LLMProvider

    provider_id = str(uuid.uuid4())
    db_session.add(
        LLMProvider(
            id=provider_id,
            kind="openai",
            label="OpenAI",
            is_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    mid = str(uuid.uuid4())
    db_session.add(
        LLMModel(
            id=mid,
            provider_id=provider_id,
            tier="everyday",
            model_ref="gpt-5.4",
            display_name="GPT-5.4",
            is_tier_default=True,
            is_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    return mid


def test_get_model_pref_returns_null_when_unset(company_client: TestClient, auth_user) -> None:
    r = company_client.get("/api/departments/morning-briefing/model-pref")
    assert r.status_code == 200
    body = r.json()
    assert body["department_id"] == "morning_briefing"
    assert body["model_id"] is None
    assert "effective_model_id" in body


def test_get_model_pref_effective_falls_back_to_tier_default(
    company_client: TestClient, auth_user, model_id
) -> None:
    """When no dept override and no user-global pref, GET surfaces the
    resolver-resolved model so the picker can show what's actually in use."""
    r = company_client.get("/api/departments/morning-briefing/model-pref")
    assert r.status_code == 200
    body = r.json()
    assert body["model_id"] is None
    assert body["effective_model_id"] == model_id


def test_put_model_pref_persists_and_get_returns_it(
    company_client: TestClient, auth_user, model_id
) -> None:
    r = company_client.put(
        "/api/departments/morning-briefing/model-pref",
        json={"model_id": model_id},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["department_id"] == "morning_briefing"
    assert body["model_id"] == model_id
    assert body["effective_model_id"] == model_id

    r2 = company_client.get("/api/departments/morning-briefing/model-pref")
    body2 = r2.json()
    assert body2["model_id"] == model_id
    assert body2["effective_model_id"] == model_id


def test_put_model_pref_rejects_unknown_model(company_client: TestClient, auth_user) -> None:
    r = company_client.put(
        "/api/departments/morning-briefing/model-pref",
        json={"model_id": "model-that-does-not-exist"},
    )
    assert r.status_code == 400


def test_get_model_pref_rejects_unknown_department(company_client: TestClient, auth_user) -> None:
    r = company_client.get("/api/departments/not-a-real-department/model-pref")
    assert r.status_code == 404


def test_delete_model_pref_clears_row(company_client: TestClient, auth_user, model_id) -> None:
    company_client.put(
        "/api/departments/morning-briefing/model-pref",
        json={"model_id": model_id},
    )
    r = company_client.delete("/api/departments/morning-briefing/model-pref")
    assert r.status_code == 204
    r2 = company_client.get("/api/departments/morning-briefing/model-pref")
    assert r2.json()["model_id"] is None
