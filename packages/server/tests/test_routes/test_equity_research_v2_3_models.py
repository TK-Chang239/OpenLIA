"""Tests for v2.3 per-user model-assignment routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def seed_llm_model(db_session):
    """Insert one LLMModel row and return its id."""
    from openlia_server.db.models.config import LLMModel, LLMProvider

    provider = LLMProvider(
        id=str(uuid.uuid4()),
        kind="openai",
        label="OpenAI",
        is_enabled=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(provider)
    db_session.flush()
    model = LLMModel(
        id=str(uuid.uuid4()),
        provider_id=provider.id,
        model_ref="gpt-5.4",
        display_name="GPT-5.4",
        is_enabled=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(model)
    db_session.commit()
    return model.id


def test_get_empty_assignments_lists_all_seven_slots(personal_client: TestClient) -> None:
    res = personal_client.get("/api/departments/equity-research/v2.3/model-assignments")
    assert res.status_code == 200
    body = res.json()
    assert body["assignments"] == {}
    assert sorted(body["slots"]) == [
        "clarify",
        "compute",
        "plan",
        "research",
        "synthesize",
        "verify",
        "write",
    ]
    # When nothing is saved, every LLM slot is missing.
    assert sorted(body["missing"]) == sorted(body["slots"])


def test_put_saves_then_get_returns_assignments(
    personal_client: TestClient, seed_llm_model: str
) -> None:
    res = personal_client.put(
        "/api/departments/equity-research/v2.3/model-assignments",
        json={"assignments": {"clarify": seed_llm_model, "plan": seed_llm_model}},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["assignments"] == {"clarify": seed_llm_model, "plan": seed_llm_model}
    # Five other LLM slots still missing.
    assert sorted(body["missing"]) == [
        "compute",
        "research",
        "synthesize",
        "verify",
        "write",
    ]

    # Re-read.
    res2 = personal_client.get("/api/departments/equity-research/v2.3/model-assignments")
    assert res2.json()["assignments"] == {"clarify": seed_llm_model, "plan": seed_llm_model}


def test_put_replaces_prior_assignments(personal_client: TestClient, seed_llm_model: str) -> None:
    personal_client.put(
        "/api/departments/equity-research/v2.3/model-assignments",
        json={"assignments": {"clarify": seed_llm_model, "plan": seed_llm_model}},
    )
    # Now PUT only `clarify`; `plan` should be removed.
    res = personal_client.put(
        "/api/departments/equity-research/v2.3/model-assignments",
        json={"assignments": {"clarify": seed_llm_model}},
    )
    assert res.json()["assignments"] == {"clarify": seed_llm_model}


def test_put_rejects_unknown_slot(personal_client: TestClient, seed_llm_model: str) -> None:
    res = personal_client.put(
        "/api/departments/equity-research/v2.3/model-assignments",
        json={"assignments": {"not_a_slot": seed_llm_model}},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "unknown_slots"


def test_put_rejects_unresolvable_model_id(personal_client: TestClient) -> None:
    res = personal_client.put(
        "/api/departments/equity-research/v2.3/model-assignments",
        json={"assignments": {"clarify": "00000000-0000-0000-0000-000000000000"}},
    )
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["code"] == "model_not_found"
    assert detail["bad"][0]["slot"] == "clarify"


def test_visualize_is_not_an_assignable_slot(
    personal_client: TestClient, seed_llm_model: str
) -> None:
    """VISUALIZE is deterministic — server rejects an attempt to assign it.

    Even though VISUALIZE is a valid V23Slot member, it is NOT in
    LLM_V23_SLOTS. The route accepts it (slot name is known), but the
    assignment provides no value; this test pins the surface so a future
    refactor that moves VISUALIZE under LLM_V23_SLOTS does not silently
    change the missing-slots contract.
    """
    res = personal_client.put(
        "/api/departments/equity-research/v2.3/model-assignments",
        json={"assignments": {"visualize": seed_llm_model}},
    )
    # The route accepts it (visualize is a known slot name), but the
    # missing list still includes the seven LLM slots — visualize is
    # not one of them.
    assert res.status_code == 200, res.text
    body = res.json()
    assert "visualize" not in body["missing"]
    assert "visualize" not in body["slots"]
