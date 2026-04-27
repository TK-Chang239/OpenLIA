"""Runtime dispatch helper: envelope shaping over connectors.Dispatcher.

`connectors.dispatch.Dispatcher.dispatch_tool_use` only routes; it returns
whatever the connector emits. The runners (chat / report) need a shaped
envelope with `ok`, a one-line `summary`, a normalized `payload`, and a
`structured` field for UI-consumable tools. This module supplies that
shaping plus parallel-fan-out, mirroring the behavior previously hosted by
`openlia.llm.runtime.tools.ToolDispatcher` so consumers can swap import
paths without behavior change.

Field names match the legacy `ToolCallResult` (`call_id`, `ok`, `summary`,
`payload`, `structured`) so ChatRunner / ReportRunner only need an import
swap during the H3.3 cutover.

This module is core-pure: it depends only on `openlia.connectors.*` and
`openlia.llm.types` — no FastAPI / SQLAlchemy / HTTP imports.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from openlia.connectors.dispatch import Dispatcher
from openlia.connectors.types import Category
from openlia.llm.types import ToolSchema

_ALL_CATEGORIES: frozenset[Category] = frozenset(
    {Category.FINANCIAL, Category.NEWS, Category.SOCIAL, Category.WEB_SEARCH}
)
_NON_SEARCH: frozenset[Category] = _ALL_CATEGORIES - {Category.WEB_SEARCH}


@dataclass(frozen=True)
class ToolCallResult:
    """Shaped envelope for a single tool call.

    `summary` is UI-ready (suitable for SSE); `payload` goes back to the LLM.
    `structured` carries argument-echo data for UI-consumable tools (e.g.
    `suggest_redirect`); `None` for data-provider tools whose payload is
    meant for the LLM, not the UI.
    """

    call_id: str
    ok: bool
    summary: str
    payload: dict[str, Any]
    structured: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolCallRequest:
    """Single dispatch request for `dispatch_many`."""

    prefixed_name: str
    arguments: dict[str, Any]
    call_id: str


def _normalize_payload(payload: Any, *, max_array_len: int = 50) -> dict[str, Any]:
    """Strip nulls, cap arrays, convert recursively. Marks truncation.

    Mirrors `openlia.llm.runtime.tools._normalize_payload` exactly: non-dict
    payloads become `{"value": payload}`; dict entries with `None` values
    are dropped; list entries longer than `max_array_len` are capped and a
    `"truncated": True` marker is added.
    """
    if not isinstance(payload, dict):
        return {"value": payload}
    out: dict[str, Any] = {}
    truncated = False
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, list) and len(v) > max_array_len:
            out[k] = v[:max_array_len]
            truncated = True
        else:
            out[k] = v
    if truncated:
        out["truncated"] = True
    return out


def _short_args(arguments: dict[str, Any], *, max_len: int = 80) -> str:
    try:
        text = json.dumps(arguments, separators=(",", ":"))
    except (TypeError, ValueError):
        text = str(arguments)
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def _summary_for(prefixed_name: str, arguments: dict[str, Any]) -> str:
    """One-line human summary for a successful dispatch.

    Mirrors `_summarize_requirement` from the legacy tools module: prefer
    a recognizable subject from common argument keys; fall back to the
    bare tool name.
    """
    for key in ("symbol", "ticker", "query", "name"):
        if key in arguments:
            return f"Fetched {prefixed_name} for {arguments[key]}"
    return f"Fetched {prefixed_name}"


def tools_for_run(
    dispatcher: Dispatcher,
    department_id: str,
    *,
    has_web_search: bool,
    extra_tools: Iterable[dict[str, Any]] = (),
) -> list[ToolSchema]:
    """Build the per-run tool list for a runner.

    Pulls connector-backed tools from `dispatcher.tools_for_department`
    (filtered by category — drop `web_search` connectors when the run has
    no web search), then appends any department-supplied `extra_tools`
    (e.g. Secretary's `suggest_redirect`). Returns `ToolSchema` objects so
    LLM adapters can consume them directly.

    Connector tool dicts use `input_schema`; legacy `extra_tools` dicts use
    `parameters`. This helper normalizes both into `ToolSchema.parameters`.
    """
    include = _ALL_CATEGORIES if has_web_search else _NON_SEARCH
    raw = dispatcher.tools_for_department(department_id, include_categories=set(include))
    tools: list[ToolSchema] = [
        ToolSchema(
            name=entry["name"],
            description=entry.get("description", ""),
            parameters=entry.get("input_schema") or entry.get("parameters") or {},
        )
        for entry in raw
    ]
    for entry in extra_tools:
        tools.append(
            ToolSchema(
                name=entry["name"],
                description=entry.get("description", ""),
                parameters=entry.get("parameters") or entry.get("input_schema") or {},
            )
        )
    return tools


async def dispatch_with_envelope(
    dispatcher: Dispatcher,
    *,
    prefixed_name: str,
    arguments: dict[str, Any],
    call_id: str,
) -> ToolCallResult:
    """Dispatch one tool call and produce a shaped envelope.

    Wraps `Dispatcher.dispatch_tool_use`. On exception sets `ok=False`,
    a human-readable `summary`, and an `{"error": <str>}` payload. On
    success returns `ok=True` with a normalized payload and a one-line
    summary.
    """
    try:
        raw = await dispatcher.dispatch_tool_use(prefixed_name, arguments)
    except Exception as exc:  # surface any failure to the model as a tool error
        return ToolCallResult(
            call_id=call_id,
            ok=False,
            summary=f"Failed to fetch {prefixed_name}: {exc!s}",
            payload={"error": str(exc)},
        )
    return ToolCallResult(
        call_id=call_id,
        ok=True,
        summary=_summary_for(prefixed_name, arguments),
        payload=_normalize_payload(raw),
    )


async def dispatch_many(
    dispatcher: Dispatcher,
    calls: list[ToolCallRequest],
) -> list[ToolCallResult]:
    """Parallel dispatch via asyncio.gather, preserving input order.

    Per-call exceptions are caught inside `dispatch_with_envelope`, so the
    corresponding `ToolCallResult` has `ok=False` and other calls still
    complete. `return_exceptions=True` is unnecessary.
    """
    coros = [
        dispatch_with_envelope(
            dispatcher,
            prefixed_name=c.prefixed_name,
            arguments=c.arguments,
            call_id=c.call_id,
        )
        for c in calls
    ]
    return await asyncio.gather(*coros)
