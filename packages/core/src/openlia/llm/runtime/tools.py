"""Tool dispatcher: build the tool list + route calls.

Three sources:
  1. Mapped requirement tools — loaded from DataProviderDispatcher
     (which reads ~/.openlia/mappings/<department>.yaml).
  2. `find_more_data` meta-tool — always present when any data tools exist.
  3. `web_search` — present only when resolve_web_search() returned available.

Dispatch:
  - Routes by call.name; unknown names get ok=False.
  - `dispatch_many` runs parallel tool calls with asyncio.gather.
  - Response payloads pass through `_normalize_payload` (nulls dropped,
    arrays capped). Summaries are one-line human strings suitable for SSE.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import ToolCall, ToolSchema

_FIND_MORE_DATA_SCHEMA = ToolSchema(
    name="find_more_data",
    description=(
        "Search all configured data providers for an endpoint matching a "
        "description. If found, the endpoint becomes available as a new tool "
        "you can call in a follow-up turn."
    ),
    parameters={
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Plain-language description of the data you need.",
            }
        },
        "required": ["description"],
    },
)

_WEB_SEARCH_SCHEMA = ToolSchema(
    name="web_search",
    description="Search the web for recent information not covered by configured data providers.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)


@runtime_checkable
class DataProviderDispatcher(Protocol):
    """Plan 3 implements this.

    `list_requirement_tools(department_id)` returns the mapped-tool entries
    from `~/.openlia/mappings/<department>.yaml` (name/description/parameters).

    `dispatch_requirement(tool_name, arguments)` invokes the winning data
    provider for this requirement and returns its normalized JSON payload.

    `find_more_data(department_id, description)` runs the Quick-tier LLM
    catalog search; returns a mapping-tool entry on hit, None on miss.
    """

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]: ...

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def find_more_data(
        self, *, department_id: str, description: str
    ) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class ToolCallResult:
    """Dispatcher output. `summary` is UI-ready; `payload` goes back to the LLM."""

    call_id: str
    ok: bool
    summary: str
    payload: dict[str, Any]


def _normalize_payload(payload: Any, *, max_array_len: int = 50) -> dict[str, Any]:
    """Strip nulls, cap arrays, convert recursively. Marks truncation."""
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


def _summarize_requirement(tool_name: str, arguments: dict[str, Any]) -> str:
    for key in ("symbol", "ticker", "query", "name"):
        if key in arguments:
            return f"Fetched {tool_name} for {arguments[key]}"
    return f"Fetched {tool_name}"


class ToolDispatcher:
    def __init__(
        self,
        *,
        data_dispatcher: DataProviderDispatcher,
        web_search: WebSearchResolution,
    ) -> None:
        self._data = data_dispatcher
        self._web_search = web_search
        self._expanded: dict[str, list[ToolSchema]] = {}  # per-department

    async def build(self, department_id: str, *, has_web_search: bool) -> list[ToolSchema]:
        mapped_raw = await self._data.list_requirement_tools(department_id)
        mapped: list[ToolSchema] = [
            ToolSchema(
                name=entry["name"],
                description=entry["description"],
                parameters=entry["parameters"],
            )
            for entry in mapped_raw
        ]
        mapped.extend(self._expanded.get(department_id, []))
        tools: list[ToolSchema] = list(mapped)

        if mapped:
            tools.append(_FIND_MORE_DATA_SCHEMA)
        if has_web_search and self._web_search.available:
            tools.append(_WEB_SEARCH_SCHEMA)
        return tools

    async def dispatch(self, *, department_id: str, call: ToolCall) -> ToolCallResult:
        name = call.name
        if name == "find_more_data":
            return await self._dispatch_find_more_data(department_id, call)
        if name == "web_search":
            return await self._dispatch_web_search(call)
        return await self._dispatch_requirement(call)

    async def dispatch_many(
        self, *, department_id: str, calls: list[ToolCall]
    ) -> list[ToolCallResult]:
        coros = [self.dispatch(department_id=department_id, call=c) for c in calls]
        return await asyncio.gather(*coros)

    async def _dispatch_requirement(self, call: ToolCall) -> ToolCallResult:
        try:
            payload = await self._data.dispatch_requirement(
                tool_name=call.name, arguments=call.arguments
            )
        except Exception as exc:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"Failed to fetch {call.name}: {exc!s}",
                payload={"error": str(exc)},
            )
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=_summarize_requirement(call.name, call.arguments),
            payload=_normalize_payload(payload),
        )

    async def _dispatch_find_more_data(self, department_id: str, call: ToolCall) -> ToolCallResult:
        description = str(call.arguments.get("description", ""))
        try:
            entry = await self._data.find_more_data(
                department_id=department_id, description=description
            )
        except Exception as exc:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"find_more_data failed: {exc!s}",
                payload={"error": str(exc)},
            )
        if entry is None:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"No matching endpoint available for '{description}'",
                payload={"found": False},
            )
        schema = ToolSchema(
            name=entry["name"],
            description=entry["description"],
            parameters=entry["parameters"],
        )
        self._expanded.setdefault(department_id, []).append(schema)
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=f"Added tool: {schema.name}",
            payload={"added_tool": schema.name, "found": True},
        )

    async def _dispatch_web_search(self, call: ToolCall) -> ToolCallResult:
        if not self._web_search.available or self._web_search.variant != "configured":
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary="web_search unavailable",
                payload={"error": "web_search not available"},
            )
        adapter = self._web_search.adapter
        assert adapter is not None  # available + configured => adapter present
        query = str(call.arguments.get("query", ""))
        try:
            results = await adapter.search(query)
        except Exception as exc:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"web_search failed: {exc!s}",
                payload={"error": str(exc)},
            )
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=f"Searched the web for: {query}",
            payload={
                "results": [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]
            },
        )
