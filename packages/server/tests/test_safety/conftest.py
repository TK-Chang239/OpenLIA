"""Fixtures for safety route tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.middleware.rate_limit import limiter


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    limiter().clear()
    yield
    limiter().clear()


@pytest.fixture
def personal_client(db_session, make_user, monkeypatch):
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User

    user = User(
        id="local",
        email="local@openlia.local",
        display_name="Local",
        is_admin=True,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    from openlia_server.app import create_app

    app = create_app(db_session_factory=session_mod.SessionLocal)
    with TestClient(app) as client:
        yield client
