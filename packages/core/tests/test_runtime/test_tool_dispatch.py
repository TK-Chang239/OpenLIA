"""Shared bounded, off-thread tool dispatch used by the v3-family forks.

``dispatch_tool_call`` must hold the properties v3's dispatcher pins, plus
the extra one the forks need (their curated tools may be sync OR return a
coroutine):

  1. A tool that overruns the per-call cap surfaces a structured timeout
     error to the model instead of hanging the run.
  2. Dispatch runs off the event loop, so other coroutines keep making
     progress while a sync tool blocks.
  3. Sync tools and coroutine (connector) tools both succeed and serialize.
  4. Unknown tools and raising tools come back as structured errors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time

import pytest
from openlia.llm.runtime.report_v2_3.research import (
    ResearchTool,
    ToolExecutionError,
    ToolResult,
)
from openlia.llm.runtime.report_v2_3.research.tools import ToolDescriptor
from openlia.llm.runtime.report_v2_3.schemas import ComputedSource
from openlia.llm.runtime.tool_dispatch import (
    dispatch_tool_call,
    resolve_tool_timeout_seconds,
)
from openlia.llm.types import ToolCall

log = logging.getLogger(__name__)


def _tool(name: str, execute) -> ResearchTool:
    return ResearchTool(
        descriptor=ToolDescriptor(name=name, description="test tool", parameters={}),
        execute=execute,
    )


def _result(name: str, payload: dict) -> ToolResult:
    return ToolResult(
        payload=payload,
        provenance=ComputedSource(method=name, derived_from=["test"]),
        summary=f"{name} ran",
    )


async def _dispatch(call: ToolCall, tools: dict[str, ResearchTool], *, timeout: float):
    return await dispatch_tool_call(
        call,
        tools,
        timeout_seconds=timeout,
        engine_label="Test engine",
        logger=log,
    )


@pytest.mark.asyncio
async def test_blocking_tool_surfaces_timeout_error_within_cap() -> None:
    """A tool stuck far longer than the cap returns a timeout error fast."""

    def execute(_args: dict) -> ToolResult:
        # Self-releases after 2s so the worker thread doesn't linger past
        # the test rather than leaking forever.
        threading.Event().wait(timeout=2.0)
        raise AssertionError("tool should have been timed out before returning")

    call = ToolCall(id="c1", name="get_fundamentals", arguments={"ticker": "AVGO"})

    started = time.monotonic()
    message = await _dispatch(
        call, {"get_fundamentals": _tool("get_fundamentals", execute)}, timeout=0.1
    )
    elapsed = time.monotonic() - started

    assert elapsed < 1.0, "dispatch should return at the cap, not block on the tool"
    assert message.role == "tool"
    assert message.tool_call_id == "c1"
    body = json.loads(message.content)
    assert "error" in body
    assert "timed out" in body["error"].lower()


@pytest.mark.asyncio
async def test_dispatch_does_not_block_event_loop() -> None:
    """While a sync tool blocks, a concurrent coroutine must still run.

    The tool waits on a threading.Event that only a *coroutine* sets. If
    dispatch ran inline on the single-threaded loop, that coroutine could
    never run, the event would never fire, and the tool would block until
    its own 2s fallback -> the assertion below would fail.
    """
    unblock = threading.Event()

    def execute(_args: dict) -> ToolResult:
        if not unblock.wait(timeout=2.0):
            raise ToolExecutionError("event loop was blocked; coroutine never ran")
        raise ToolExecutionError("unblocked-by-coroutine")

    async def unblocker() -> None:
        await asyncio.sleep(0.05)
        unblock.set()

    call = ToolCall(id="c2", name="get_prices", arguments={})

    message, _ = await asyncio.gather(
        _dispatch(call, {"get_prices": _tool("get_prices", execute)}, timeout=1.0),
        unblocker(),
    )

    body = json.loads(message.content)
    assert body["error"] == "unblocked-by-coroutine"


@pytest.mark.asyncio
async def test_sync_tool_succeeds() -> None:
    """A well-behaved sync tool returns its serialized payload."""

    def execute(args: dict) -> ToolResult:
        return _result("get_fundamentals", {"ticker": args["ticker"], "pe": 42})

    call = ToolCall(id="c3", name="get_fundamentals", arguments={"ticker": "NVDA"})
    message = await _dispatch(
        call, {"get_fundamentals": _tool("get_fundamentals", execute)}, timeout=5.0
    )

    assert message.role == "tool"
    assert json.loads(message.content) == {"ticker": "NVDA", "pe": 42}


@pytest.mark.asyncio
async def test_async_connector_tool_succeeds() -> None:
    """A coroutine-returning (connector) tool is awaited and serialized.

    This is the fork-specific behavior v3's sync-only dispatcher lacks and
    the shared helper must preserve.
    """

    async def execute(args: dict) -> ToolResult:
        await asyncio.sleep(0)
        return _result("provider__lookup", {"echo": args})

    call = ToolCall(id="c4", name="provider__lookup", arguments={"q": "x"})
    message = await _dispatch(
        call, {"provider__lookup": _tool("provider__lookup", execute)}, timeout=5.0
    )

    assert json.loads(message.content) == {"echo": {"q": "x"}}


@pytest.mark.asyncio
async def test_unknown_tool_returns_structured_error() -> None:
    call = ToolCall(id="c5", name="nope", arguments={})
    message = await _dispatch(call, {}, timeout=5.0)
    body = json.loads(message.content)
    assert "Unknown tool" in body["error"]


@pytest.mark.asyncio
async def test_tool_execution_error_surfaces() -> None:
    def execute(_args: dict) -> ToolResult:
        raise ToolExecutionError("bad ticker")

    call = ToolCall(id="c6", name="get_prices", arguments={})
    message = await _dispatch(call, {"get_prices": _tool("get_prices", execute)}, timeout=5.0)
    assert json.loads(message.content) == {"error": "bad ticker"}


def test_resolve_tool_timeout_seconds_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPORT_V3_TOOL_TIMEOUT_SECONDS", raising=False)
    assert resolve_tool_timeout_seconds() == 120.0


def test_resolve_tool_timeout_seconds_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPORT_V3_TOOL_TIMEOUT_SECONDS", "45")
    assert resolve_tool_timeout_seconds() == 45.0


def test_resolve_tool_timeout_seconds_ignores_garbage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPORT_V3_TOOL_TIMEOUT_SECONDS", "not-a-number")
    assert resolve_tool_timeout_seconds() == 120.0
    monkeypatch.setenv("REPORT_V3_TOOL_TIMEOUT_SECONDS", "-5")
    assert resolve_tool_timeout_seconds() == 120.0
