from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from openlia_server.services.auto_cancel_sweep import auto_cancel_tick
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.user_presence_registry import UserPresenceRegistry


@pytest.mark.asyncio
async def test_tick_cancels_users_disconnected_beyond_grace() -> None:
    presence = UserPresenceRegistry()
    registry = BackgroundReportRegistry()

    async def long_runner():
        await asyncio.sleep(10)
        yield {"type": "noop"}

    t = registry.submit(user_id="u1", report_id="r1", runner_coro=long_runner())
    # Simulate: user attached briefly then detached >grace ago.
    q = presence.attach("u1")
    presence.detach("u1", q)
    # Fast-forward the disconnect timestamp manually for determinism.
    presence._last_disconnect_at["u1"] = datetime.now(UTC) - timedelta(seconds=120)

    cancelled = await auto_cancel_tick(
        presence=presence,
        registry=registry,
        db_session_factory=_noop_session_factory,
        grace_seconds=90,
    )
    assert cancelled == ["r1"]
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(t.asyncio_task, timeout=1.0)


@pytest.mark.asyncio
async def test_tick_ignores_users_with_open_connections() -> None:
    presence = UserPresenceRegistry()
    registry = BackgroundReportRegistry()

    async def long_runner():
        await asyncio.sleep(10)
        yield {"type": "noop"}

    t = registry.submit(user_id="u1", report_id="r1", runner_coro=long_runner())
    presence.attach("u1")  # keep open

    cancelled = await auto_cancel_tick(
        presence=presence,
        registry=registry,
        db_session_factory=_noop_session_factory,
        grace_seconds=90,
    )
    assert cancelled == []
    # Cleanup.
    registry.cancel("r1")
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(t.asyncio_task, timeout=1.0)


def _noop_session_factory():
    class _CM:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **kw):
            return None

        def commit(self):
            pass

    return _CM()
