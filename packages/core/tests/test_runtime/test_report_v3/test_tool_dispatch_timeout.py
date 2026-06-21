"""Tool dispatch must be bounded and must not block the event loop.

A v3 tool (notably the EODHD data tools) calls a synchronous SDK that
issues un-timed HTTP. Dispatching it inline on the asyncio event loop
froze the whole worker and let a single hung call hang the run
indefinitely (the wall-time guard only checks between turns). These
tests pin the two required properties of the fixed dispatcher:

  1. A tool that overruns the per-call cap surfaces a structured
     timeout error to the model instead of hanging the run.
  2. Dispatch runs off the event loop, so other coroutines keep making
     progress while a tool blocks.
"""

from __future__ import annotations

import json
import threading
import time

import pytest
from openlia.llm.runtime.report_v2_3.research.tools import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
)
from openlia.llm.runtime.report_v3.runner import _dispatch_one_async
from openlia.llm.types import ToolCall


def _tool(name: str, execute) -> ResearchTool:
    return ResearchTool(
        descriptor=ToolDescriptor(name=name, description="test tool", parameters={}),
        execute=execute,
    )


@pytest.mark.asyncio
async def test_blocking_tool_surfaces_timeout_error_within_cap() -> None:
    """A tool stuck far longer than the cap returns a timeout error fast."""

    def execute(_args: dict) -> None:
        # Never signalled; self-releases after 2s so the worker thread
        # doesn't linger past the test rather than leaking forever.
        threading.Event().wait(timeout=2.0)
        raise AssertionError("tool should have been timed out before returning")

    call = ToolCall(id="c1", name="get_fundamentals", arguments={"ticker": "AVGO"})

    started = time.monotonic()
    message = await _dispatch_one_async(
        call, {"get_fundamentals": _tool("get_fundamentals", execute)}, timeout_seconds=0.1
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
    """While a tool blocks, a concurrent coroutine must still run.

    The tool waits on a threading.Event that only a *coroutine* sets.
    If dispatch ran inline on the single-threaded loop, that coroutine
    could never run, the event would never fire, and the tool would
    block until its own 2s fallback -> the assertion below would fail.
    """
    import asyncio

    unblock = threading.Event()

    def execute(_args: dict) -> None:
        if not unblock.wait(timeout=2.0):
            raise ToolExecutionError("event loop was blocked; coroutine never ran")
        raise ToolExecutionError("unblocked-by-coroutine")

    async def unblocker() -> None:
        await asyncio.sleep(0.05)
        unblock.set()

    call = ToolCall(id="c2", name="get_prices", arguments={})

    message, _ = await asyncio.gather(
        _dispatch_one_async(
            call, {"get_prices": _tool("get_prices", execute)}, timeout_seconds=1.0
        ),
        unblocker(),
    )

    body = json.loads(message.content)
    assert body["error"] == "unblocked-by-coroutine"
