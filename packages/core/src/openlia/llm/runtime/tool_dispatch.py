"""Bounded, off-thread tool dispatch shared by the v3-family runners.

Earnings Update v2 (``report_eu``), Morning Briefing (``report_mb``), and
the Macro Research / Retail Sentiment dashboards (``report_dash_mr`` /
``report_dash_rs``) are forks of the v3 engine. Each runs a single LLM
tool-use loop and dispatched each tool call *inline* on the asyncio event
loop with no per-call timeout. The curated EODHD data tools call a
synchronous SDK that issues un-timed HTTP, so a single hung request froze
the whole worker and let one call stall a run indefinitely — the
wall-time guard only checks between turns (audit-2026-06-21 deferred item;
v3 already fixed this at ``report_v3/runner.py``).

This module mirrors v3's fix as one shared helper the four forks reuse:

  * Sync tools run in a worker thread so a blocking SDK call can't freeze
    the event loop.
  * Connector tools return a coroutine; creating it in the thread is cheap
    (an ``async def`` body runs only when awaited) and it is awaited back
    on the loop so it drives against the running loop as usual.
  * The whole dispatch is bounded by ``asyncio.wait_for``. A tool that
    overruns surfaces a structured timeout error to the model — exactly
    like any other tool failure — so the loop continues instead of hanging.

``report_v3`` keeps its own copy (its dispatch is sync-only and its runner
is out of scope for the change that introduced this helper).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os

from ..types import Message, ToolCall
from .report_v2_3.research import ResearchTool, ToolExecutionError, ToolResult

_TOOL_TIMEOUT_ENV = "REPORT_V3_TOOL_TIMEOUT_SECONDS"
_DEFAULT_TOOL_TIMEOUT_SECONDS = 120.0


def resolve_tool_timeout_seconds() -> float:
    """Per-tool-call cap in seconds, env-tunable.

    Reads ``REPORT_V3_TOOL_TIMEOUT_SECONDS`` (the same knob v3 honors, so
    ops tunes one variable for the whole engine family). Falls back to
    120.0 — generous for one EODHD GET — when the env var is unset or not
    a positive number.
    """
    raw = os.environ.get(_TOOL_TIMEOUT_ENV, "").strip()
    if raw:
        try:
            value = float(raw)
        except ValueError:
            return _DEFAULT_TOOL_TIMEOUT_SECONDS
        if value > 0:
            return value
    return _DEFAULT_TOOL_TIMEOUT_SECONDS


async def dispatch_tool_call(
    call: ToolCall,
    tools_by_name: dict[str, ResearchTool],
    *,
    timeout_seconds: float,
    engine_label: str,
    logger: logging.Logger,
) -> Message:
    """Execute one tool call off the event loop, bounded by a timeout.

    Returns the matching tool ``Message``. Every failure — unknown tool,
    a raise from ``execute``, or a timeout — comes back as a structured
    tool-error message so the model can correct itself or try a different
    tool; the loop never crashes on a single bad call.

    ``engine_label`` prefixes the unexpected-error log line (e.g.
    ``"EU v2"`` → ``"EU v2 tool <name> raised unexpectedly"``); ``logger``
    is the calling runner's logger so provenance is preserved.
    """
    tool = tools_by_name.get(call.name)
    if tool is None:
        body = json.dumps(
            {
                "error": (
                    f"Unknown tool {call.name!r}. "
                    f"Valid tools: {sorted(tools_by_name)}. "
                    f"Only the enabled tools are available this run."
                )
            }
        )
        return Message(role="tool", content=body, tool_call_id=call.id)

    try:
        result = await asyncio.wait_for(
            _execute_off_thread(tool, call.arguments),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "%s tool %s exceeded %.0fs cap; surfacing as a tool error",
            engine_label,
            call.name,
            timeout_seconds,
        )
        body = json.dumps(
            {
                "error": (
                    f"Tool {call.name!r} timed out after {timeout_seconds:.0f}s. "
                    f"The data source may be slow or unreachable; try a "
                    f"different tool or proceed without this data."
                )
            }
        )
        return Message(role="tool", content=body, tool_call_id=call.id)
    except ToolExecutionError as exc:
        body = json.dumps({"error": str(exc)})
        return Message(role="tool", content=body, tool_call_id=call.id)
    except Exception as exc:
        logger.exception("%s tool %s raised unexpectedly", engine_label, call.name)
        body = json.dumps({"error": f"unexpected: {exc}"})
        return Message(role="tool", content=body, tool_call_id=call.id)

    return Message(role="tool", content=_serialize_result(result), tool_call_id=call.id)


async def _execute_off_thread(tool: ResearchTool, arguments: dict) -> ToolResult:
    """Run a possibly-sync-or-async tool without blocking the event loop.

    Sync tools (curated EODHD + output tools) run their blocking SDK in a
    worker thread. Connector tools' ``execute`` returns a coroutine; that
    coroutine is created cheaply in the thread and awaited back on the loop
    so a raise from either the sync call or the awaited coroutine surfaces
    through the caller's single try/except.
    """
    result = await asyncio.to_thread(tool.execute, arguments)
    if inspect.isawaitable(result):
        result = await result
    return result


def _serialize_result(result: ToolResult) -> str:
    try:
        return json.dumps(result.payload, default=str)
    except TypeError:
        return json.dumps({"summary": result.summary, "payload": str(result.payload)})


__all__ = ["dispatch_tool_call", "resolve_tool_timeout_seconds"]
