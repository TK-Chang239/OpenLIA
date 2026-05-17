from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.services.user_presence_registry import UserPresenceRegistry

# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _app_and_client(db_session, monkeypatch):
    app = _make_app(db_session, monkeypatch)
    presence = UserPresenceRegistry()
    # Enter the TestClient context so the lifespan runs (populates app.state),
    # then overwrite with a test-controlled presence instance so route handlers
    # and app_presence fixture share the same object.
    with TestClient(app) as client:
        app.state.user_presence_registry = presence
        app.state.user_presence = presence
        yield client, presence


@pytest.fixture
def test_client(_app_and_client) -> TestClient:
    client, _ = _app_and_client
    return client


@pytest.fixture
def app_presence(_app_and_client) -> UserPresenceRegistry:
    _, presence = _app_and_client
    return presence


@pytest.fixture
def test_user(db_session):
    from openlia_server.db.models.auth import User

    return db_session.get(User, "local")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_notifications_stream_returns_eventstream(
    test_client: TestClient,
) -> None:
    # The endpoint yields an immediate connect heartbeat so TestClient.stream
    # unblocks as soon as that first byte arrives.
    with test_client.stream("GET", "/notifications/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        # Consume the initial heartbeat so the context is fully entered.
        next(resp.iter_bytes(chunk_size=4096), None)


def test_open_notification_stream_registers_user_in_presence(
    test_client: TestClient, app_presence: UserPresenceRegistry, test_user
) -> None:
    with test_client.stream("GET", "/notifications/stream") as resp:
        # Consuming the initial heartbeat confirms that presence.attach() has run.
        next(resp.iter_bytes(chunk_size=4096), None)
        # User has an open connection — must NOT be in the disconnect map.
        assert test_user.id not in app_presence.users_with_no_connections()
    # Stream closed → presence.detach() ran → user IS in the disconnect map.
    assert test_user.id in app_presence.users_with_no_connections()
