# packages/server/tests/test_notifications_stream.py
from __future__ import annotations

import threading
import time
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
    app = create_app(db_session_factory=session_mod.SessionLocal)
    presence = UserPresenceRegistry()
    app.state.user_presence_registry = presence
    return app, presence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _app_and_presence(db_session, monkeypatch):
    return _make_app(db_session, monkeypatch)


@pytest.fixture
def test_client(_app_and_presence):
    app, _ = _app_and_presence
    with TestClient(app) as client:
        yield client


@pytest.fixture
def app_presence(_app_and_presence):
    _, presence = _app_and_presence
    return presence


@pytest.fixture
def test_user(db_session):
    from openlia_server.db.models.auth import User

    return db_session.get(User, "local")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_notifications_stream_returns_eventstream(
    test_client: TestClient, app_presence: UserPresenceRegistry
) -> None:
    results: dict = {}
    stop = threading.Event()

    def opener():
        with test_client.stream("GET", "/notifications/stream") as resp:
            results["status_code"] = resp.status_code
            results["content_type"] = resp.headers.get("content-type", "")
            stop.wait(timeout=2.0)

    t = threading.Thread(target=opener, daemon=True)
    t.start()
    # Give the handler time to call presence.attach() and enter the queue-wait,
    # then inject an event so the generator yields and the stream unblocks.
    time.sleep(0.2)
    app_presence.fanout("local", {"type": "test.ping"})
    # Give the stream thread time to receive the chunk and record headers.
    time.sleep(0.2)
    stop.set()
    t.join(timeout=3.0)
    assert results.get("status_code") == 200
    assert results.get("content_type", "").startswith("text/event-stream")


def test_open_notification_stream_registers_user_in_presence(
    test_client: TestClient, app_presence: UserPresenceRegistry, test_user
) -> None:
    # Open the stream in a background thread; check presence registers.
    stop = threading.Event()

    def opener():
        with test_client.stream("GET", "/notifications/stream") as resp:
            while not stop.is_set():
                time.sleep(0.05)

    t = threading.Thread(target=opener, daemon=True)
    t.start()
    time.sleep(0.3)
    assert test_user.id not in app_presence.users_with_no_connections()
    stop.set()
    t.join(timeout=2.0)
