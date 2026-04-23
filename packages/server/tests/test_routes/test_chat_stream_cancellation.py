"""Cancelling the _event_source task must flip the cancel token.

Uses asyncio.create_task + task.cancel() to simulate a client disconnect
without the httpx.ASGITransport deadlock (in-process transport blocks the
event loop when the server generator is waiting, preventing the client
context-exit from completing).
"""

from __future__ import annotations

import asyncio

import pytest
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ChatStart, ChatToken


class _InfiniteRunner:
    """Yields two events then blocks until cancelled."""

    def __init__(self) -> None:
        self.captured_token: CancellationToken | None = None

    async def run(
        self, *, department_id, user_id, messages, attachments=None, cancel_token=None
    ):
        self.captured_token = cancel_token
        yield ChatStart(message_id="m1")
        yield ChatToken(message_id="m1", text="hello")
        await asyncio.Event().wait()  # blocks until the task is cancelled


@pytest.mark.asyncio
async def test_cancel_token_flipped_on_task_cancellation() -> None:
    """CancelledError at the generator boundary must call token.cancel()."""
    from openlia_server.routes.chat_stream import (
        SecretaryChatMessage,
        SecretaryChatRequest,
        _event_source,
    )

    class _FakeUser:
        id = "local"

    runner = _InfiniteRunner()
    payload = SecretaryChatRequest(
        messages=[SecretaryChatMessage(role="user", content="hi")]
    )

    consumed: list[bytes] = []

    async def _consume() -> None:
        async for chunk in _event_source(payload, _FakeUser(), lambda: runner):  # type: ignore[arg-type]
            consumed.append(chunk)

    task = asyncio.create_task(_consume())

    # Yield control so the generator runs through the first two events.
    for _ in range(20):
        await asyncio.sleep(0)
        if runner.captured_token is not None:
            break

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert runner.captured_token is not None
    assert runner.captured_token.is_cancelled is True
    # At least the two non-blocking events should have been emitted.
    assert len(consumed) >= 2
