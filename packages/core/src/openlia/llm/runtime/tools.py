"""Tool dispatcher: build the tool list + route calls.

Three sources:
  1. Mapped requirement tools — loaded from DataProviderDispatcher
     (which reads ~/.openlia/mappings/<department>.yaml).
  2. `request_additional_tools` meta-tool — always present when any data
     tools exist; lets the LLM pull the rest of the inventory mid-run.
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
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from openlia.skills import SkillRegistry

from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import ToolCall, ToolSchema

# Hard outer cap on tool-loop iterations to prevent runaway provider calls
# when a model loops on the same tool without convergence.
MAX_TOOL_TURNS = 32

# Hard provider cap on tools per request. OpenAI rejects requests whose
# `tools` array exceeds 128 with `invalid_request_error`; Anthropic and
# Gemini accept more but degrade routing accuracy past this point. We
# enforce this across all providers via `ToolDispatcher.build()`.
MAX_TOOLS_PER_REQUEST = 128

_REQUEST_ADDITIONAL_TOOLS_NAME = "request_additional_tools"

_REQUEST_ADDITIONAL_TOOLS_SCHEMA = ToolSchema(
    name=_REQUEST_ADDITIONAL_TOOLS_NAME,
    description=(
        "Call this if you realize you need a capability that's not in your "
        "current toolset. Provide a one-sentence reason describing what you "
        "want to do; matching tools will be added to your toolset for the "
        "rest of this run."
    ),
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "One-sentence description of the missing capability.",
            },
            "category_hint": {
                "type": "string",
                "description": ("Optional connector category hint (financial, news, social, ...)."),
            },
        },
        "required": ["reason"],
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

LOAD_SKILL_SCHEMA = ToolSchema(
    name="load_skill",
    description=(
        "Load the full instructions/playbook for an installed skill. Returns the "
        "skill's markdown body. Call this when the user's question matches a skill "
        "from the menu and you want its detailed guidance before answering."
    ),
    parameters={
        "type": "object",
        "properties": {"skill_id": {"type": "string", "description": "Id from the skill menu."}},
        "required": ["skill_id"],
        "additionalProperties": False,
    },
)


@runtime_checkable
class DataProviderDispatcher(Protocol):
    """v1 dispatcher Protocol consumed by ``ToolDispatcher``.

    ``list_requirement_tools(department_id)`` returns the active subset of
    tool entries (name/description/parameters) — for the report path this
    is the cache-filtered list, for chat it's the legacy mapped set.

    ``dispatch_requirement(tool_name, arguments)`` invokes the underlying
    provider/connector and returns its normalized JSON payload.

    ``expand_tools(department_id, reason, category_hint)`` is the
    escalation surface bound to ``request_additional_tools``: returns
    additional tool entries the LLM may call on the next turn.
    """

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]: ...

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def expand_tools(
        self,
        *,
        department_id: str,
        reason: str,
        category_hint: str | None = None,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ToolCallResult:
    """Dispatcher output. `summary` is UI-ready; `payload` goes back to the LLM.

    `structured` carries JSON for UI-consumable tools (e.g. `suggest_redirect`
    echoes `{department, reason, prefill}` so the frontend can render a
    RedirectCard). It is `None` for data-provider tools whose `payload` is
    meant for the LLM, not the UI.
    """

    call_id: str
    ok: bool
    summary: str
    payload: dict[str, Any]
    structured: dict[str, Any] | None = None


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


class _EscalationCache:
    """Per-department working set of tools added via request_additional_tools.

    Provides two views for downstream consumers:
      * for_emission(dept) — addition order, stable for prompt-cache prefix.
      * lru_order(dept) — names in LRU order (MRU last), used for eviction priority.
    `touch(dept, name)` marks a tool MRU; not yet called in this PR.
    """

    def __init__(self) -> None:
        # per-department: insertion-order dict keyed by tool name
        self._addition_order: dict[str, dict[str, ToolSchema]] = {}
        # per-department: list of names in LRU order (MRU last)
        self._lru_order: dict[str, list[str]] = {}

    def add(self, department_id: str, schemas: Iterable[ToolSchema]) -> list[str]:
        """Add schemas; return names newly added. Already-present names are skipped."""
        added: list[str] = []
        for schema in schemas:
            addition = self._addition_order.setdefault(department_id, {})
            lru = self._lru_order.setdefault(department_id, [])
            if schema.name in addition:
                continue
            addition[schema.name] = schema
            lru.append(schema.name)
            added.append(schema.name)
        return added

    def touch(self, department_id: str, name: str) -> None:
        """Mark `name` as most-recently-used. No-op if not in cache.
        Wired up in a later PR; defined here for the structure."""
        lru = self._lru_order.get(department_id)
        if lru is None:
            return
        try:
            lru.remove(name)
        except ValueError:
            return
        lru.append(name)

    def for_emission(self, department_id: str) -> list[ToolSchema]:
        """Return all tools for this department in addition order."""
        addition = self._addition_order.get(department_id)
        if not addition:
            return []
        return list(addition.values())

    def lru_order(self, department_id: str) -> list[str]:
        """Return tool names in LRU order (MRU last)."""
        lru = self._lru_order.get(department_id)
        if not lru:
            return []
        return list(lru)

    def has_any(self, department_id: str) -> bool:
        """True if at least one tool has been added for this department.
        Used by ToolDispatcher.build() to decide whether the escalation
        meta-tool should still be exposed."""
        return bool(self._addition_order.get(department_id))


class ToolDispatcher:
    def __init__(
        self,
        *,
        data_dispatcher: DataProviderDispatcher,
        web_search: WebSearchResolution,
    ) -> None:
        self._data = data_dispatcher
        self._web_search = web_search
        self._escalation_cache = _EscalationCache()

    async def build(
        self,
        department_id: str,
        *,
        has_web_search: bool,
        extra_tools: tuple[dict[str, Any], ...] = (),
    ) -> list[ToolSchema]:
        mapped_raw = await self._data.list_requirement_tools(department_id)
        mapped: list[ToolSchema] = [
            ToolSchema(
                name=entry["name"],
                description=entry["description"],
                parameters=entry["parameters"],
            )
            for entry in mapped_raw
        ]
        expanded = self._escalation_cache.for_emission(department_id)

        # Tail items always preserved: escalation, web_search, extra_tools.
        # If mapped+expanded is empty there's nothing to escalate from, so
        # `request_additional_tools` is also dropped (matches prior behaviour).
        has_data_tools = bool(mapped) or self._escalation_cache.has_any(department_id)
        tail: list[ToolSchema] = []
        if has_data_tools:
            tail.append(_REQUEST_ADDITIONAL_TOOLS_SCHEMA)
        if has_web_search and self._web_search.available:
            tail.append(_WEB_SEARCH_SCHEMA)
        # Department-provided structured tools (e.g. Secretary's suggest_redirect).
        # Dispatch echoes their arguments back as `structured` data so the
        # frontend can render UI cards without a separate event type.
        for entry in extra_tools:
            tail.append(
                ToolSchema(
                    name=entry["name"],
                    description=entry["description"],
                    parameters=entry["parameters"],
                )
            )

        # Enforce the provider cap. Prefer keeping `expanded` (LLM
        # explicitly escalated for these mid-run) over `mapped` (warm-up
        # full inventory or cache-promoted). Truncate from the mapped
        # tail. If after that we still don't fit, drop expanded too.
        budget = MAX_TOOLS_PER_REQUEST - len(tail)
        if budget < 0:
            # Pathological: tail alone exceeds the cap. Truncate tail.
            return tail[:MAX_TOOLS_PER_REQUEST]
        if len(mapped) + len(expanded) > budget:
            keep_expanded = expanded[: min(len(expanded), budget)]
            keep_mapped = mapped[: budget - len(keep_expanded)]
            data_tools: list[ToolSchema] = keep_mapped + keep_expanded
        else:
            data_tools = mapped + expanded
        return data_tools + tail

    async def dispatch(
        self,
        *,
        department_id: str,
        call: ToolCall,
        extra_tool_names: frozenset[str] = frozenset(),
    ) -> ToolCallResult:
        name = call.name
        if name in extra_tool_names:
            return self._dispatch_structured_echo(call)
        if name == _REQUEST_ADDITIONAL_TOOLS_NAME:
            return await self._dispatch_request_additional_tools(department_id, call)
        if name == "web_search":
            return await self._dispatch_web_search(call)
        return await self._dispatch_requirement(call)

    async def dispatch_many(
        self,
        *,
        department_id: str,
        calls: list[ToolCall],
        extra_tool_names: frozenset[str] = frozenset(),
    ) -> list[ToolCallResult]:
        coros = [
            self.dispatch(
                department_id=department_id,
                call=c,
                extra_tool_names=extra_tool_names,
            )
            for c in calls
        ]
        return await asyncio.gather(*coros)

    @staticmethod
    def _dispatch_structured_echo(call: ToolCall) -> ToolCallResult:
        """Echo the LLM's arguments back as a structured payload. Used for
        UI-consumable tools (redirect cards, etc.) whose value IS the
        argument dict — no backend work beyond surfacing it."""
        args = dict(call.arguments)
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=f"{call.name} suggested",
            payload={"ack": True},
            structured=args,
        )

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

    async def _dispatch_request_additional_tools(
        self,
        department_id: str,
        call: ToolCall,
    ) -> ToolCallResult:
        reason = str(call.arguments.get("reason", "")).strip()
        category_hint_raw = call.arguments.get("category_hint")
        category_hint = (
            str(category_hint_raw).strip()
            if isinstance(category_hint_raw, str) and category_hint_raw.strip()
            else None
        )
        try:
            entries = await self._data.expand_tools(
                department_id=department_id,
                reason=reason,
                category_hint=category_hint,
            )
        except Exception as exc:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"request_additional_tools failed: {exc!s}",
                payload={"error": str(exc)},
            )
        added = self._escalation_cache.add(
            department_id,
            [
                ToolSchema(
                    name=e["name"],
                    description=e.get("description", ""),
                    parameters=e.get("parameters") or {},
                )
                for e in entries
            ],
        )
        if not added:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary="No additional tools matched the request.",
                payload={"added_tools": [], "found": False},
            )
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=f"Added tools: {', '.join(added)}",
            payload={"added_tools": added, "found": True},
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


async def dispatch_load_skill(
    registry: SkillRegistry,
    *,
    user_id: str | None,
    skill_id: str,
    call_id: str,
) -> ToolCallResult:
    """Look up `skill_id` in the registry and return its body as a tool result."""
    skill = registry.get(skill_id, user_id=user_id)
    if skill is None:
        return ToolCallResult(
            call_id=call_id,
            ok=False,
            summary=f"Unknown skill: {skill_id}",
            payload={"error": f"Unknown skill: {skill_id}"},
        )
    display = skill.manifest.display_name or skill.manifest.name
    return ToolCallResult(
        call_id=call_id,
        ok=True,
        summary=f"Loaded skill: {display}",
        payload={"body": skill.body, "skill_id": skill.manifest.name},
        structured={
            "skill_id": skill.manifest.name,
            "display_name": display,
        },
    )
