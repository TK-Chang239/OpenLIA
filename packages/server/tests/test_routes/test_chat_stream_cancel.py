"""P1-12b — `_event_source` spawns a watcher that flips the cancel token
when `request.is_disconnected()` returns True.

The deeper ASGI-level disconnect dance is exercised by the existing
test_chat_stream_cancellation.py; this module verifies the watcher itself:
when the request reports disconnected, the runner's token flips within
roughly the polling interval, and the iterator stops without persisting
an assistant message.
"""

from __future__ import annotations

import asyncio

import pytest
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ChatStart, ChatToken
from openlia.llm.runtime.messages import ChatMessage as RuntimeChatMessage


class _InfiniteRunner:
    def __init__(self) -> None:
        self.captured_token: CancellationToken | None = None

    async def run(self, *, department_id, user_id, messages, attachments=None, cancel_token=None):
        self.captured_token = cancel_token
        yield ChatStart(message_id="m1")
        yield ChatToken(message_id="m1", text="hello")
        # Block until the token is flipped.
        if cancel_token is not None:
            await cancel_token.wait()
        # No terminal event — spec says iterator just stops.


class _DisconnectingRequest:
    """Stand-in for FastAPI's Request that flips `is_disconnected` after a delay."""

    def __init__(self, *, after: float) -> None:
        self._t0 = asyncio.get_event_loop().time() + after

    async def is_disconnected(self) -> bool:
        return asyncio.get_event_loop().time() >= self._t0


class _SavingPersist:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def save_assistant(self, *, content, tool_calls):  # type: ignore[no-untyped-def]
        self.calls.append({"content": content, "tool_calls": tool_calls})


@pytest.mark.asyncio
async def test_disconnect_watcher_flips_cancel_token() -> None:
    from openlia_server.routes.chat_stream import _event_source

    class _FakeUser:
        id = "local"

    runner = _InfiniteRunner()
    persist = _SavingPersist()
    fake_request = _DisconnectingRequest(after=0.3)
    messages = [RuntimeChatMessage(role="user", content="hi")]

    consumed = []

    async def _consume() -> None:
        async for chunk in _event_source(
            messages=messages,
            user=_FakeUser(),  # type: ignore[arg-type]
            factory=lambda: runner,
            department="secretary",
            persist=persist,
            request=fake_request,  # type: ignore[arg-type]
        ):
            consumed.append(chunk)

    await asyncio.wait_for(_consume(), timeout=3.0)

    # The watcher polled is_disconnected, observed True, and flipped the
    # runner's cancel token, which unblocked the runner's wait().
    assert runner.captured_token is not None
    assert runner.captured_token.is_cancelled is True
    # No assistant persistence after a disconnect — the iterator stops mid-flight.
    assert persist.calls == []


@pytest.mark.asyncio
async def test_no_disconnect_no_token_flip() -> None:
    """Control: when the request never disconnects and the runner finishes
    cleanly, the cancel token is *not* flipped by the watcher."""
    from openlia.llm.runtime.events import ChatDone
    from openlia_server.routes.chat_stream import _event_source

    class _FastRunner:
        def __init__(self) -> None:
            self.captured_token: CancellationToken | None = None

        async def run(
            self, *, department_id, user_id, messages, attachments=None, cancel_token=None
        ):
            self.captured_token = cancel_token
            yield ChatStart(message_id="m1")
            yield ChatToken(message_id="m1", text="hi")
            yield ChatDone(message_id="m1", stop_reason="complete")

    class _FakeUser:
        id = "local"

    class _NoDisconnect:
        async def is_disconnected(self) -> bool:
            return False

    runner = _FastRunner()
    persist = _SavingPersist()
    messages = [RuntimeChatMessage(role="user", content="hi")]

    consumed = []
    async for chunk in _event_source(
        messages=messages,
        user=_FakeUser(),  # type: ignore[arg-type]
        factory=lambda: runner,
        department="secretary",
        persist=persist,
        request=_NoDisconnect(),  # type: ignore[arg-type]
    ):
        consumed.append(chunk)

    assert runner.captured_token is not None
    assert runner.captured_token.is_cancelled is False
    # Clean completion -> assistant text persisted.
    assert len(persist.calls) == 1
    assert persist.calls[0]["content"] == "hi"
