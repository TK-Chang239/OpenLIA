"""Shared fixtures for test_services tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import User


@pytest.fixture(autouse=True)
def _seed_test_users(db_session) -> None:
    """Insert synthetic users used across service-layer tests.

    ``db_session`` creates a fresh SQLite DB per test, so this fixture runs
    once per test and populates the rows needed to satisfy FK constraints
    (e.g. UserLLMPreference.user_id → users.id).
    """
    now = datetime.now(UTC)
    for uid, email in [("u-1", "u1@test.example"), ("u-2", "u2@test.example")]:
        if db_session.get(User, uid) is None:
            db_session.add(
                User(
                    id=uid,
                    email=email,
                    display_name=uid,
                    password_hash=None,
                    is_admin=False,
                    is_disabled=False,
                    created_at=now,
                    updated_at=now,
                )
            )
    db_session.flush()


@pytest.fixture
def seeded_user(db_session):
    from openlia_server.db.models.auth import User

    return db_session.get(User, "u-1")


@pytest.fixture
def other_user(db_session):
    from openlia_server.db.models.auth import User

    return db_session.get(User, "u-2")


@pytest.fixture
def llm_model_factory(db_session):
    """Build an LLMProvider + LLMModel pair and return the model row."""
    from openlia_server.db.models.config import LLMModel, LLMProvider

    def _make(
        *,
        provider_kind: str = "openai",
        model_ref: str | None = None,
        display_name: str | None = None,
    ) -> LLMModel:
        provider_id = f"p-{uuid.uuid4().hex[:8]}"
        model_id = f"m-{uuid.uuid4().hex[:8]}"
        provider = LLMProvider(
            id=provider_id,
            kind=provider_kind,
            label=f"label-{provider_id}",
            api_key=None,
            env_var_name=None,
            base_url=None,
            extra_config=None,
            is_enabled=True,
        )
        db_session.add(provider)
        db_session.flush()
        model = LLMModel(
            id=model_id,
            provider_id=provider_id,
            model_ref=model_ref or f"ref-{model_id}",
            display_name=display_name or f"Model {model_id}",
            is_enabled=True,
            overrides=None,
        )
        db_session.add(model)
        db_session.commit()
        return model

    return _make
