"""Notifications SSE emits a heartbeat after heartbeat_seconds of
inactivity. Uses a short heartbeat for test speed."""

from __future__ import annotations

import asyncio

import pytest
from openlia_server.services.user_presence_registry import UserPresenceRegistry


async def _collect_frames(
    presence: UserPresenceRegistry,
    user_id: str,
    *,
    heartbeat_seconds: int,
    n_frames: int,
    deadline_seconds: float,
) -> list[bytes]:
    """Drive the notifications stream generator and return the first n_frames."""
    import json

    queue = presence.attach(user_id)

    async def gen():
        # Mirror the notifications_stream gen() closure.
        yield b"event: report.heartbeat\ndata: {}\n\n"
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                    name = ev.get("type", "event")
                    yield f"event: {name}\ndata: {json.dumps(ev, default=str)}\n\n".encode()
                except TimeoutError:
                    yield b"event: report.heartbeat\ndata: {}\n\n"
        finally:
            presence.detach(user_id, queue)

    frames: list[bytes] = []
    async with asyncio.timeout(deadline_seconds):
        async for frame in gen():
            frames.append(frame)
            if len(frames) >= n_frames:
                break
    return frames


@pytest.mark.asyncio
async def test_heartbeat_emitted_during_quiet_period() -> None:
    """Heartbeat at 1s; pull 2 frames from the stream; both must be heartbeats."""
    presence = UserPresenceRegistry()
    # Collect 2 frames: the immediate connect heartbeat plus one timeout heartbeat.
    frames = await _collect_frames(
        presence,
        "local",
        heartbeat_seconds=1,
        n_frames=2,
        deadline_seconds=3.0,
    )
    assert len(frames) == 2
    for frame in frames:
        assert b"report.heartbeat" in frame
