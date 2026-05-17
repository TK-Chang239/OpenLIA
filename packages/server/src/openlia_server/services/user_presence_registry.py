"""Per-process registry of open notifications-SSE connections per user.

When a user has zero connections for >grace_seconds, the auto-cancel
sweep cancels all their in-flight background reports."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta


class UserPresenceRegistry:
    def __init__(self) -> None:
        self._user_connections: dict[str, set[asyncio.Queue]] = {}
        self._last_disconnect_at: dict[str, datetime] = {}

    def attach(self, user_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._user_connections.setdefault(user_id, set()).add(queue)
        self._last_disconnect_at.pop(user_id, None)
        return queue

    def detach(self, user_id: str, queue: asyncio.Queue) -> None:
        conns = self._user_connections.get(user_id, set())
        conns.discard(queue)
        if not conns:
            self._user_connections.pop(user_id, None)
            self._last_disconnect_at[user_id] = datetime.now(UTC)

    def fanout(self, user_id: str, event: dict) -> None:
        for queue in list(self._user_connections.get(user_id, set())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def users_with_no_connections(self) -> dict[str, datetime]:
        return dict(self._last_disconnect_at)

    def set_imminent_disconnect(self, user_id: str, *, grace_seconds: int = 90) -> None:
        """Fast-forward this user's last_disconnect timestamp so the
        next sweep tick will pick them up. Called by the beforeunload
        beacon endpoint."""
        self._last_disconnect_at[user_id] = datetime.now(UTC) - timedelta(seconds=grace_seconds + 1)
