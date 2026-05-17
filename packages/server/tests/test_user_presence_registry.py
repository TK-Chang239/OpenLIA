from __future__ import annotations

import asyncio

import pytest
from openlia_server.services.user_presence_registry import UserPresenceRegistry


@pytest.mark.asyncio
async def test_attach_registers_user_and_clears_disconnect() -> None:
    presence = UserPresenceRegistry()
    queue = presence.attach("u1")
    assert isinstance(queue, asyncio.Queue)
    # After attach, user is NOT in the disconnect map.
    assert "u1" not in presence.users_with_no_connections()


@pytest.mark.asyncio
async def test_detach_records_disconnect_when_last_connection_closes() -> None:
    presence = UserPresenceRegistry()
    q1 = presence.attach("u1")
    q2 = presence.attach("u1")
    presence.detach("u1", q1)
    # Still has q2 — not in disconnect map.
    assert "u1" not in presence.users_with_no_connections()
    presence.detach("u1", q2)
    # No more connections — now in disconnect map.
    assert "u1" in presence.users_with_no_connections()


@pytest.mark.asyncio
async def test_fanout_delivers_to_all_open_connections() -> None:
    presence = UserPresenceRegistry()
    q1 = presence.attach("u1")
    q2 = presence.attach("u1")
    presence.fanout("u1", {"type": "test", "x": 1})
    assert q1.get_nowait() == {"type": "test", "x": 1}
    assert q2.get_nowait() == {"type": "test", "x": 1}


@pytest.mark.asyncio
async def test_set_imminent_disconnect_fast_forwards_timestamp() -> None:
    presence = UserPresenceRegistry()
    q = presence.attach("u1")
    presence.detach("u1", q)
    original_ts = presence.users_with_no_connections()["u1"]
    presence.set_imminent_disconnect("u1", grace_seconds=90)
    new_ts = presence.users_with_no_connections()["u1"]
    # New timestamp should be ~90s earlier than original.
    assert (original_ts - new_ts).total_seconds() >= 80
