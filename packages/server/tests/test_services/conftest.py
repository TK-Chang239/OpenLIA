"""Shared fixtures for test_services tests."""

from __future__ import annotations

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
