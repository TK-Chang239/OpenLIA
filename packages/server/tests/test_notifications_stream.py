from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from openlia_server.services.user_presence_registry import UserPresenceRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_request(presence: UserPresenceRegistry) -> MagicMock:
    """Minimal fake FastAPI Request with presence in app.state."""
    req = MagicMock()
    req.app.state.user_presence_registry = presence
    return req


def _make_fake_user(user_id: str = "local") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    return user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def presence() -> UserPresenceRegistry:
    return UserPresenceRegistry()


@pytest.fixture
def test_user(db_session):
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
    return db_session.get(User, "local")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_notifications_stream_returns_eventstream(
    presence: UserPresenceRegistry,
) -> None:
    """The SSE handler returns a StreamingResponse with text/event-stream
    media type and immediately yields a connect heartbeat as the first frame."""
    from fastapi.responses import StreamingResponse

    # Build a minimal router to access the handler directly.
    from openlia_server.db import session as session_mod
    from openlia_server.routes.notifications_stream import build_notifications_stream_router

    router = build_notifications_stream_router(
        db_session_factory=session_mod.SessionLocal,
        mode="personal",
        heartbeat_seconds=30,
    )

    # The handler is the first (and only GET) route endpoint.
    handler = next(r.endpoint for r in router.routes if getattr(r, "methods", None) == {"GET"})

    req = _make_fake_request(presence)
    user = _make_fake_user()
    response = await handler(request=req, user=user)

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"

    # Collect the first frame from the generator.
    frames: list[bytes] = []
    async for chunk in response.body_iterator:
        frames.append(chunk)
        break  # Stop after the first frame (initial heartbeat).

    assert frames, "Generator yielded no frames"
    assert b"heartbeat" in frames[0]


@pytest.mark.asyncio
async def test_open_notification_stream_registers_user_in_presence(
    presence: UserPresenceRegistry, test_user
) -> None:
    """Calling the handler attaches the user to the presence registry;
    exiting the generator detaches them."""
    from openlia_server.db import session as session_mod
    from openlia_server.routes.notifications_stream import build_notifications_stream_router

    router = build_notifications_stream_router(
        db_session_factory=session_mod.SessionLocal,
        mode="personal",
        heartbeat_seconds=30,
    )
    handler = next(r.endpoint for r in router.routes if getattr(r, "methods", None) == {"GET"})

    req = _make_fake_request(presence)
    user = _make_fake_user(test_user.id)
    response = await handler(request=req, user=user)

    # Consume the generator to just after the first yield; attach() must
    # have been called by then.
    gen: AsyncIterator[bytes] = response.body_iterator
    await gen.__anext__()  # consume initial heartbeat

    # User has an active connection — not in disconnect map.
    assert test_user.id not in presence.users_with_no_connections()

    # Close the generator (triggers finally: presence.detach).
    await gen.aclose()

    # User's connection is gone — now in disconnect map.
    assert test_user.id in presence.users_with_no_connections()
