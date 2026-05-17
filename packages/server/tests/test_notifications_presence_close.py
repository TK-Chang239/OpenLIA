from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.services.user_presence_registry import UserPresenceRegistry

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_app(db_session, monkeypatch):
    from openlia_server.app import create_app
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
    return create_app(db_session_factory=session_mod.SessionLocal)


@pytest.fixture
def _app(db_session, monkeypatch):
    return _make_app(db_session, monkeypatch)


@pytest.fixture
def test_client(_app):
    # Startup populates app.state.user_presence_registry. The TestClient
    # context must enter before reading app.state, otherwise we'd grab the
    # pre-startup registry which the routes never touch.
    with TestClient(_app) as client:
        yield client


@pytest.fixture
def app_presence(_app, test_client) -> UserPresenceRegistry:
    return _app.state.user_presence_registry


@pytest.fixture
def test_user(db_session):
    from openlia_server.db.models.auth import User

    return db_session.get(User, "local")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_presence_close_fast_forwards_disconnect_timestamp(
    test_client: TestClient, app_presence, test_user
) -> None:
    # Simulate the user having an open queue, then disconnecting.
    q = app_presence.attach(test_user.id)
    app_presence.detach(test_user.id, q)
    original_ts = app_presence.users_with_no_connections()[test_user.id]
    resp = test_client.post("/notifications/presence-close")
    assert resp.status_code == 200
    new_ts = app_presence.users_with_no_connections()[test_user.id]
    assert (original_ts - new_ts).total_seconds() >= 60
