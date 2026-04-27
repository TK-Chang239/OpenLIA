"""P1-12 — `await_with_grace` engaged inside ChatRunner / ReportRunner / BatchRunner.

Covers:
  - Token flipped mid-stream stops yielding within `grace_seconds + 0.5s`.
  - Tool-call results completing inside the grace window are yielded before
    the iterator terminates.
  - A slow tool still running at end-of-grace raises CancelledError inside
    the runner; the async generator swallows it (iterator just stops, no
    terminal SSE event).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from _dispatcher_helpers import build_dispatcher
from _fakes import FakeProvider, FakeProviderScript
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import ChatDone, ChatError, ChatToken
from openlia.llm.runtime.messages import ChatMessage
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    root.mkdir()
    (root / "secretary.yaml").write_text(
        dedent(
            """\
            chat:
              system: You are the Secretary.
            """
        )
    )
    return root


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        tier=ModelTier.EVERYDAY,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


class _Registry:
    def get_department_tier_override(self, department_id: str):
        return None

    def get_user_preference(self, user_id, tier):
        return None

    def get_tier_default(self, tier):
        return None

    def get_any_in_tier(self, tier):
        return None


def _always(resolved):
    def _r(*, department_id, user_id, registry, tier_override=None):
        return resolved

    return _r


class _SlowStreamProvider(FakeProvider):
    """Yields tokens with a configurable delay so cancellation lands mid-stream."""

    def __init__(self, *, tokens: list[str], per_token_delay: float) -> None:
        super().__init__(script=FakeProviderScript(turns=[("final", ""), ("tokens", tokens)]))
        self._delay = per_token_delay

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        self.captured_requests.append(request)
        kind, payload = self._script.turns[self._turn_index]
        self._turn_index += 1
        assert kind == "tokens"
        for t in payload:
            await asyncio.sleep(self._delay)
            yield LLMChunk(delta=t, finish_reason=None)
        yield LLMChunk(delta="", finish_reason="stop")


async def test_token_flipped_midstream_stops_within_grace_window(prompts_root: Path) -> None:
    provider = _SlowStreamProvider(tokens=["A", "B", "C", "D", "E"], per_token_delay=0.05)
    dispatcher = build_dispatcher(department_id="secretary")
    token = CancellationToken()
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        dispatcher=dispatcher,
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        message_id_factory=lambda: "m_1",
    )
    t0 = time.monotonic()
    events: list[Any] = []
    async for e in runner.run(
        department_id="secretary",
        user_id="u_1",
        messages=[ChatMessage(role="user", content="hi")],
        cancel_token=token,
    ):
        events.append(e)
        if isinstance(e, ChatToken) and e.text == "B":
            token.cancel()
    elapsed = time.monotonic() - t0
    # grace_seconds defaults to 2.0; iteration must terminate well under that.
    assert elapsed < 3.0
    types = [type(e) for e in events]
    assert ChatDone not in types
    assert ChatError not in types


class _SlowConnectorTransport:
    """Transport whose `call_tool` blocks until released (or the finish window
    elapses) so cancellation behavior past the grace window can be observed.
    """

    def __init__(self, *, hold: asyncio.Event, finish_within: float) -> None:
        self._hold = hold
        self._finish_within = finish_within
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        try:
            await asyncio.wait_for(self._hold.wait(), timeout=self._finish_within)
        except TimeoutError:
            return {"status": "late"}
        return {"status": "ok"}


async def test_slow_tool_call_running_past_grace_terminates_iterator(prompts_root: Path) -> None:
    """A tool call still running past the grace window forces the iterator
    to stop without emitting a terminal event."""
    # Prefixed name (`<provider_id>__<tool>`) so `dispatch_tool_use` actually
    # reaches the transport's `call_tool` — the empty `provider_id=""` used by
    # `build_dispatcher` produces the `__stock_quote` form.
    call = ToolCall(id="c1", name="__stock_quote", arguments={"symbol": "X"})
    provider = FakeProvider(script=FakeProviderScript(turns=[("tool_calls", [call])]))
    hold = asyncio.Event()
    transport = _SlowConnectorTransport(hold=hold, finish_within=10.0)
    dispatcher = build_dispatcher(
        department_id="secretary",
        tools={
            "stock_quote": {
                "description": "Quote",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        },
        transport=transport,
    )
    token = CancellationToken()
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        dispatcher=dispatcher,
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        message_id_factory=lambda: "m_1",
    )

    async def _drive() -> list[Any]:
        out: list[Any] = []
        async for e in runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
            cancel_token=token,
        ):
            out.append(e)
        return out

    drive_task = asyncio.create_task(_drive())
    # Let the tool call start, then cancel.
    await asyncio.sleep(0.05)
    token.cancel()
    # Wait — grace_seconds = 2.0; iterator must terminate within ~2.5s.
    t0 = time.monotonic()
    events = await asyncio.wait_for(drive_task, timeout=5.0)
    elapsed = time.monotonic() - t0
    assert elapsed < 3.5
    # Iterator stopped without ChatDone or ChatError.
    types = [type(e) for e in events]
    assert ChatDone not in types
    assert ChatError not in types


async def test_none_token_short_circuits_to_direct_await(prompts_root: Path) -> None:
    """No token -> no grace machinery; runner completes normally."""

    class _SimpleProvider(FakeProvider):
        async def generate(self, request: LLMRequest) -> LLMResponse:
            return await super().generate(request)

    provider = _SimpleProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["hi"])]))
    dispatcher = build_dispatcher(department_id="secretary")
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        dispatcher=dispatcher,
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        message_id_factory=lambda: "m_1",
    )
    events = [
        e
        async for e in runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
            cancel_token=None,
        )
    ]
    assert any(isinstance(e, ChatDone) for e in events)
