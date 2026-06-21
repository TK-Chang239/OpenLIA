"""Cancellation primitives for the runtime.

Driven by client disconnect: the server route flips the token when
`request.is_disconnected()` returns True. Runners poll the flag between
yields; in-flight tool calls get a bounded grace period before being
cancelled.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable


class CancellationToken:
    """Single-shot boolean flag + event. Idempotent on repeated cancel()."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()


async def await_with_grace[T](
    awaitable: Awaitable[T],
    *,
    token: CancellationToken,
    grace_seconds: float = 2.0,
) -> T:
    """Await `awaitable`; if `token` is flipped, allow at most `grace_seconds`.

    Behavior:
      - Token never flips -> returns the coroutine's result normally.
      - Token flips AND coroutine finishes within grace -> returns the result.
      - Token flips AND coroutine does not finish within grace -> raises
        asyncio.CancelledError after cancelling the underlying task.
    """
    task: asyncio.Task[T] = asyncio.ensure_future(awaitable)
    cancel_waiter = asyncio.ensure_future(token.wait())

    try:
        done, _ = await asyncio.wait(
            {task, cancel_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if task in done:
            cancel_waiter.cancel()
            return task.result()

        # Token flipped; give the task the grace window.
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=grace_seconds)
        except TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            raise asyncio.CancelledError() from None
    finally:
        if not cancel_waiter.done():
            cancel_waiter.cancel()
