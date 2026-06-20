"""HTTP-level tests for the LLM slot-defaults admin router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest


def _login(client, email: str = "admin@example.com", password: str = "pw-12345678") -> None:
    client.post("/auth/login", json={"email": email, "password": password})


@pytest.fixture
def llm_model_factory(db_session):
    """Creates LLMModel rows for slot-default route tests."""

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

    def _make(**kwargs) -> LLMModel:
        model = LLMModel(
            id=kwargs.get("id", str(uuid.uuid4())),
            provider_id=provider.id,
            model_ref=kwargs.get("model_ref", "gpt-4-test"),
            display_name=kwargs.get("display_name", "GPT-4 Test"),
            is_enabled=kwargs.get("is_enabled", True),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(model)
        db_session.commit()
        return model

    return _make


@pytest.fixture
def admin_client(company_client, make_user):
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    return company_client


@pytest.fixture
def user_client(company_client, make_user):
    make_user(email="user@example.com", password="pw-12345678", is_admin=False)
    _login(company_client, email="user@example.com")
    return company_client


def test_list_slot_defaults_empty(admin_client) -> None:
    r = admin_client.get("/settings/admin/llm/slot-defaults")
    assert r.status_code == 200
    assert r.json() == {"defaults": []}


def test_put_dept_slot_default(admin_client, llm_model_factory) -> None:
    m = llm_model_factory()
    r = admin_client.put(
        "/settings/admin/llm/slot-defaults/department/secretary",
        json={"model_id": m.id},
    )
    assert r.status_code == 200
    assert r.json()["model_id"] == m.id
    assert r.json()["slot_kind"] == "department"
    assert r.json()["slot_id"] == "secretary"


def test_put_invalid_dept_400(admin_client, llm_model_factory) -> None:
    m = llm_model_factory()
    r = admin_client.put(
        "/settings/admin/llm/slot-defaults/department/ghost",
        json={"model_id": m.id},
    )
    assert r.status_code == 400


def test_put_system_role_slot(admin_client, llm_model_factory) -> None:
    m = llm_model_factory()
    r = admin_client.put(
        "/settings/admin/llm/slot-defaults/system_role/graph_extraction",
        json={"model_id": m.id},
    )
    assert r.status_code == 200


def test_delete_slot(admin_client, llm_model_factory) -> None:
    m = llm_model_factory()
    admin_client.put(
        "/settings/admin/llm/slot-defaults/department/secretary",
        json={"model_id": m.id},
    )
    r = admin_client.delete("/settings/admin/llm/slot-defaults/department/secretary")
    assert r.status_code == 204


def test_non_admin_forbidden(user_client, llm_model_factory) -> None:
    m = llm_model_factory()
    r = user_client.put(
        "/settings/admin/llm/slot-defaults/department/secretary",
        json={"model_id": m.id},
    )
    assert r.status_code == 403
