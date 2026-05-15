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
import logging
import os
import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from openlia.skills import SkillRegistry

from openlia.llm.runtime.payload_path import (
    PathParseError,
    PathResolveError,
    apply_path,
)
from openlia.llm.runtime.payload_stub import generate_stub
from openlia.llm.runtime.schema_slim import SchemaSlimSystemicFailure, slim_tool_schema
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import ToolCall, ToolSchema

log = logging.getLogger(__name__)

_SLIM_SYSTEMIC_FAILURE_MIN_COUNT = 5
_SLIM_SYSTEMIC_FAILURE_MIN_RATIO = 0.20

TraceRecorder = Callable[[str, str, dict[str, Any] | None], None]


def _noop_trace(_category: str, _message: str, _payload: dict[str, Any] | None) -> None:
    return None


# Hard outer cap on tool-loop iterations to prevent runaway provider calls
# when a model loops on the same tool without convergence.
MAX_TOOL_TURNS = 32


# Hard provider cap on tools per request. OpenAI rejects requests whose
# `tools` array exceeds 128 with `invalid_request_error`; Anthropic and
# Gemini accept more but degrade routing accuracy past this point. We
# enforce this across all providers via `ToolDispatcher.build()`.
# Default lowered to 48 for accuracy; override via OPENLIA_MAX_TOOLS_PER_REQUEST.
def _get_max_tools_per_request() -> int:
    raw = os.environ.get("OPENLIA_MAX_TOOLS_PER_REQUEST")
    if raw is None:
        return 48
    try:
        v = int(raw)
        if v < 1:
            raise ValueError
        return v
    except ValueError:
        log.warning("Invalid OPENLIA_MAX_TOOLS_PER_REQUEST=%r; using default 48", raw)
        return 48


MAX_TOOLS_PER_REQUEST = _get_max_tools_per_request()


def _get_payload_stub_threshold_chars() -> int:
    raw = os.environ.get("OPENLIA_PAYLOAD_STUB_THRESHOLD_CHARS")
    if raw is None:
        return 8000
    try:
        v = int(raw)
        if v < 1:
            raise ValueError
        return v
    except ValueError:
        log.warning("Invalid OPENLIA_PAYLOAD_STUB_THRESHOLD_CHARS=%r; using default 8000", raw)
        return 8000


def _get_read_payload_cap_chars() -> int:
    raw = os.environ.get("OPENLIA_READ_PAYLOAD_CAP_CHARS")
    if raw is None:
        return 50_000  # 50KB
    try:
        v = int(raw)
        if v < 1:
            raise ValueError
        return v
    except ValueError:
        log.warning("Invalid OPENLIA_READ_PAYLOAD_CAP_CHARS=%r; using default 50000", raw)
        return 50_000


PAYLOAD_STUB_THRESHOLD_CHARS = _get_payload_stub_threshold_chars()
READ_PAYLOAD_CAP_CHARS = _get_read_payload_cap_chars()

_ESCALATION_FAILURE_THRESHOLD = 3

_REQUEST_ADDITIONAL_TOOLS_NAME = "request_additional_tools"

_REQUEST_ADDITIONAL_TOOLS_SCHEMA = ToolSchema(
    name=_REQUEST_ADDITIONAL_TOOLS_NAME,
    description=(
        "Call this if you realize you need a capability that's not in your "
        "current toolset. Provide a one-sentence reason describing what you "
        "want to do; matching tools will be added to your toolset."
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

_READ_PAYLOAD_NAME = "read_payload"
_READ_PAYLOAD_SCHEMA = ToolSchema(
    name=_READ_PAYLOAD_NAME,
    description=(
        "Read a slice of a previously-stored tool-result payload. Call when "
        "you've received a stub (a result with a `ref` field) and need "
        "specific values from it."
    ),
    parameters={
        "type": "object",
        "properties": {
            "ref": {
                "type": "string",
                "description": "The `ref` from a stub.",
            },
            "path": {
                "type": "string",
                "description": (
                    "Optional path. Forms: key, key.subkey, rows[i], rows[i:j], "
                    "rows.column. Composable. Omit for entire payload."
                ),
            },
        },
        "required": ["ref"],
        "additionalProperties": False,
    },
)

LOAD_SKILL_SCHEMA = ToolSchema(
    name="load_skill",
    description=(
        "Load the full instructions/playbook for an installed skill. Returns the "
        "skill's markdown body. Call this when the user's question matches a skill "
        "from the menu and you want its detailed guidance."
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

    async def available_categories(self) -> list[str]:
        """Return the list of category strings the dispatcher exposes
        (for category_hint guidance in the prompt). Returns the empty
        list if no categorized inventory is available."""


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


_BuiltinHandler = Callable[["ToolDispatcher", str, ToolCall], Awaitable[ToolCallResult]]


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
        """Add schemas; return names newly added.

        Already-present names (by name field) are skipped."""
        added: list[str] = []
        addition: dict[str, ToolSchema] | None = None
        lru: list[str] | None = None
        for schema in schemas:
            if addition is None:
                addition = self._addition_order.setdefault(department_id, {})
                lru = self._lru_order.setdefault(department_id, [])
            if schema.name in addition:
                continue
            addition[schema.name] = schema
            assert lru is not None
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
        trace: TraceRecorder | None = None,
    ) -> None:
        self._data = data_dispatcher
        self._web_search = web_search
        self._escalation_cache = _EscalationCache()
        self._trace: TraceRecorder = trace if trace is not None else _noop_trace
        self._consecutive_escalation_failures: dict[str, int] = {}
        self._payload_store: dict[str, dict[str, Any]] = {}
        # Per-run scope: dispatcher is per-run, so the store dies with the
        # dispatcher instance. No cleanup needed.
        self._payload_seq = 0  # monotonic per dispatcher for short refs
        self._ref_prefix = uuid.uuid4().hex[:4]  # 4 hex chars; sufficient within a run
        self._builtin_handlers: dict[str, _BuiltinHandler] = {
            _REQUEST_ADDITIONAL_TOOLS_NAME: type(self)._dispatch_request_additional_tools,
            "web_search": type(self)._dispatch_web_search,
            _READ_PAYLOAD_NAME: type(self)._dispatch_read_payload,
        }

    async def available_categories(self) -> list[str]:
        """Delegate to the underlying data dispatcher."""
        return await self._data.available_categories()

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

        # Header items always preserved: escalation, web_search, extra_tools.
        # `request_additional_tools` is always exposed: under the Phase B
        # empty-starter-pack contract the data dispatcher returns no
        # mapped tools and the LLM must escalate to load any data tool.
        # Gating the meta-tool on a non-empty mapped/expanded set breaks
        # that bootstrap — the model sees no entry point and refuses to
        # fabricate. The dispatcher is the source of truth for whether
        # escalation actually yields candidates; if it doesn't, the
        # `request_additional_tools` dispatch returns `ok=False` with
        # a "no tools matched" message, which the model handles.
        header: list[ToolSchema] = [_REQUEST_ADDITIONAL_TOOLS_SCHEMA]
        if has_web_search and self._web_search.available:
            header.append(_WEB_SEARCH_SCHEMA)
        # read_payload is always included: the payload store is always wired.
        header.append(_READ_PAYLOAD_SCHEMA)
        # Department-provided structured tools (e.g. Secretary's suggest_redirect).
        # Dispatch echoes their arguments back as `structured` data so the
        # frontend can render UI cards without a separate event type.
        for entry in extra_tools:
            header.append(
                ToolSchema(
                    name=entry["name"],
                    description=entry["description"],
                    parameters=entry["parameters"],
                )
            )

        return self._pack_for_provider(
            mapped=mapped, expanded=expanded, header=header, department_id=department_id
        )

    def _pack_for_provider(
        self,
        *,
        mapped: list[ToolSchema],
        expanded: list[ToolSchema],
        header: list[ToolSchema],
        department_id: str | None = None,
    ) -> list[ToolSchema]:
        """Slim, sort, cap, and emit in header+mapped+expanded order.

        Cap priority: header > expanded > mapped. Header always preserved
        (unless pathologically large). Mapped truncated from its end.
        """
        chars_before = 0
        chars_after = 0
        failures: list[tuple[str, Exception]] = []

        def _slim_one(t: ToolSchema) -> ToolSchema:
            nonlocal chars_before, chars_after
            before = len(
                json.dumps(
                    {"d": t.description, "p": t.parameters},
                    separators=(",", ":"),
                )
            )
            try:
                slimmed = slim_tool_schema(t)
            except Exception as exc:
                failures.append((t.name, exc))
                log.warning("slim_tool_schema failed for %s: %s", t.name, exc)
                chars_before += before
                chars_after += before  # passthrough — no savings
                return t
            after = len(
                json.dumps(
                    {"d": slimmed.description, "p": slimmed.parameters},
                    separators=(",", ":"),
                )
            )
            chars_before += before
            chars_after += after
            return slimmed

        header_slim = [_slim_one(t) for t in header]
        mapped_slim = [_slim_one(t) for t in mapped]
        expanded_slim = [_slim_one(t) for t in expanded]

        # Threshold check
        n = len(header) + len(mapped) + len(expanded)
        if len(failures) >= _SLIM_SYSTEMIC_FAILURE_MIN_COUNT and (
            n > 0 and len(failures) / n > _SLIM_SYSTEMIC_FAILURE_MIN_RATIO
        ):
            raise SchemaSlimSystemicFailure(
                f"slim failed on {len(failures)}/{n} schemas: {[name for name, _ in failures[:10]]}"
            )

        # Per-section sort: mapped alphabetical; header and expanded preserve order.
        mapped_sorted = sorted(mapped_slim, key=lambda t: t.name)

        # Apply cap: header > expanded > mapped; emit order header+mapped+expanded.
        budget = MAX_TOOLS_PER_REQUEST - len(header_slim)
        if budget < 0:
            result = header_slim[:MAX_TOOLS_PER_REQUEST]
            self._emit_slim_summary(n, len(failures), chars_before, chars_after)
            n_emitted = len(result)
            n_evicted = len(mapped_sorted) + len(expanded_slim)
            n_builtins_path = len(header_slim)
            n_expanded_path = len(expanded_slim)
            self._trace(
                "escalation_cache.summary",
                (
                    f"emitted={n_emitted} builtins={n_builtins_path}"
                    f" expanded={n_expanded_path} evicted={n_evicted}"
                ),
                {
                    "expanded": n_expanded_path,
                    "builtins": n_builtins_path,
                    "emitted": n_emitted,
                    "evicted": n_evicted,
                },
            )
            if n_evicted > 0:
                evicted_names = [t.name for t in mapped_sorted + expanded_slim]
                self._trace(
                    "escalation_cache.evict",
                    (
                        f"evicted={n_evicted} working_set={n_expanded_path}"
                        f" cap={MAX_TOOLS_PER_REQUEST}"
                    ),
                    {
                        "working_set_size": n_expanded_path,
                        "cap": MAX_TOOLS_PER_REQUEST,
                        "evicted_names": evicted_names,
                    },
                )
            return result
        total_data = len(mapped_sorted) + len(expanded_slim)
        if total_data > budget:
            over = total_data - budget
            if over <= len(mapped_sorted):
                # Evict only from mapped (alphabetical-tail first).
                keep_mapped = mapped_sorted[: len(mapped_sorted) - over]
                keep_expanded = expanded_slim
            else:
                # Mapped fully dropped; evict remainder from expanded by LRU.
                keep_mapped = []
                evict_count = over - len(mapped_sorted)
                if department_id is not None:
                    lru_names = self._escalation_cache.lru_order(department_id)
                    to_drop = set(lru_names[:evict_count])
                    keep_expanded = [t for t in expanded_slim if t.name not in to_drop]
                else:
                    keep_expanded = expanded_slim[evict_count:]
            data_tools: list[ToolSchema] = keep_mapped + keep_expanded
        else:
            keep_mapped = mapped_sorted
            keep_expanded = expanded_slim
            data_tools = mapped_sorted + expanded_slim
        result = header_slim + data_tools

        self._emit_slim_summary(n, len(failures), chars_before, chars_after)

        # Task C: escalation_cache.summary and escalation_cache.evict traces
        n_emitted = len(result)
        n_evicted = total_data - len(data_tools) if total_data > budget else 0
        n_expanded = len(expanded_slim)
        n_builtins = len(header_slim)
        self._trace(
            "escalation_cache.summary",
            f"emitted={n_emitted} builtins={n_builtins} expanded={n_expanded} evicted={n_evicted}",
            {
                "expanded": n_expanded,
                "builtins": n_builtins,
                "emitted": n_emitted,
                "evicted": n_evicted,
            },
        )
        if n_evicted > 0:
            # Compute evicted names: tools in expanded_slim that were not kept.
            keep_expanded_names = {t.name for t in keep_expanded}
            evicted_names = [t.name for t in expanded_slim if t.name not in keep_expanded_names]
            # Also add mapped tools that were evicted.
            keep_mapped_names = {t.name for t in keep_mapped}
            evicted_names += [t.name for t in mapped_sorted if t.name not in keep_mapped_names]
            self._trace(
                "escalation_cache.evict",
                f"evicted={n_evicted} working_set={n_expanded} cap={MAX_TOOLS_PER_REQUEST}",
                {
                    "working_set_size": n_expanded,
                    "cap": MAX_TOOLS_PER_REQUEST,
                    "evicted_names": evicted_names,
                },
            )
        return result

    def _emit_slim_summary(
        self,
        n_tools: int,
        n_failures: int,
        chars_before: int,
        chars_after: int,
    ) -> None:
        ratio = (chars_after / chars_before) if chars_before > 0 else 1.0
        self._trace(
            "slim.summary",
            f"slim {n_tools} tools failures={n_failures} ratio={ratio:.2f}",
            {
                "n_tools": n_tools,
                "n_failures": n_failures,
                "chars_before": chars_before,
                "chars_after": chars_after,
                "ratio": ratio,
            },
        )

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
        handler = self._builtin_handlers.get(name)
        if handler is not None:
            return await handler(self, department_id, call)
        return await self._dispatch_requirement(department_id, call)

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

    async def _dispatch_requirement(self, department_id: str, call: ToolCall) -> ToolCallResult:
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
        # Mark MRU so future LRU eviction keeps recently-dispatched tools.
        # No-op if the tool was never added to the escalation cache.
        self._escalation_cache.touch(department_id, call.name)
        normalized = _normalize_payload(payload)

        # Threshold check: if normalized payload is large, externalize it.
        size_chars = len(json.dumps(normalized, default=str))
        stubbed = False
        final_payload: dict[str, Any] = normalized
        shape: str | None = None
        n_rows: int | None = None

        if size_chars > PAYLOAD_STUB_THRESHOLD_CHARS:
            self._payload_seq += 1
            ref = f"r_{self._ref_prefix}_{self._payload_seq:02d}"
            self._payload_store[ref] = normalized
            stub = generate_stub(normalized, ref=ref, tool_name=call.name)
            final_payload = stub
            stubbed = True
            shape = stub.get("shape")
            n_rows = stub.get("n_rows")

        self._trace(
            "payload.stub",
            f"{call.name} size={size_chars} stubbed={stubbed}",
            {
                "tool": call.name,
                "size_chars": size_chars,
                "stubbed": stubbed,
                "shape": shape,
                "n_rows": n_rows,
            },
        )

        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=_summarize_requirement(call.name, call.arguments),
            payload=final_payload,
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

        # Task C: expand_tools.request trace
        reason_trimmed = reason[:500]
        self._trace(
            "expand_tools.request",
            f"reason={reason_trimmed!r} hint={category_hint}",
            {
                "reason": reason_trimmed,
                "category_hint": category_hint,
                "candidate_count": -1,
                "filtered_count": -1,
                "already_loaded": len(self._escalation_cache.for_emission(department_id)),
            },
        )

        try:
            entries = await self._data.expand_tools(
                department_id=department_id,
                reason=reason,
                category_hint=category_hint,
            )
        except Exception as exc:
            # Task C: failure_reason="exception" branch
            self._trace(
                "expand_tools.result",
                "matched=0 added=0 reason=exception",
                {
                    "matched_count": 0,
                    "added_count": 0,
                    "top_names": [],
                    "scores": [],
                    "failure_reason": "exception",
                },
            )
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

        # Task C: compute failure_reason for expand_tools.result trace
        top_names = [e["name"] for e in entries]
        failure_reason: str | None = None
        if not added:
            if not entries:
                failure_reason = "no_match"
            else:
                failure_reason = "all_already_loaded"

        self._trace(
            "expand_tools.result",
            f"matched={len(entries)} added={len(added)} reason={failure_reason}",
            {
                "matched_count": len(entries),
                "added_count": len(added),
                "top_names": top_names,
                "scores": [],
                "failure_reason": failure_reason,
            },
        )

        if not added:
            # Task B: re-escalation loop guard
            self._consecutive_escalation_failures[department_id] = (
                self._consecutive_escalation_failures.get(department_id, 0) + 1
            )
            if (
                self._consecutive_escalation_failures[department_id]
                >= _ESCALATION_FAILURE_THRESHOLD
            ):
                n_consec = self._consecutive_escalation_failures[department_id]
                self._trace(
                    "expand_tools.directive_fired",
                    f"directive fired after {n_consec} consecutive failures",
                    {
                        "consecutive_failures": n_consec,
                        "department_id": department_id,
                    },
                )
                return ToolCallResult(
                    call_id=call.id,
                    ok=False,
                    summary="Repeated escalation failures.",
                    payload={
                        "added_tools": [],
                        "found": False,
                        "directive": (
                            f"You've made {n_consec} consecutive escalation"
                            " requests with no new tools added. Stop escalating."
                            " Either use the tools already in your working set,"
                            " call `web_search` if this needs unstructured data,"
                            " or write the report with what you have and"
                            " note the data gap explicitly."
                        ),
                    },
                )
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary="No additional tools matched the request.",
                payload={"added_tools": [], "found": False},
            )

        # Success: reset the counter.
        self._consecutive_escalation_failures[department_id] = 0
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=f"Added tools: {', '.join(added)}",
            payload={"added_tools": added, "found": True},
        )

    async def _dispatch_web_search(self, department_id: str, call: ToolCall) -> ToolCallResult:
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

    async def _dispatch_read_payload(self, department_id: str, call: ToolCall) -> ToolCallResult:
        """Look up a stored payload by ref and apply an optional path slice."""
        ref = str(call.arguments.get("ref", "")).strip()
        path_raw = call.arguments.get("path")
        path: str | None = (
            str(path_raw).strip() if isinstance(path_raw, str) and path_raw.strip() else None
        )

        self._trace(
            "read_payload.call",
            f"ref={ref} path={path!r}",
            {"ref": ref, "path": path},
        )

        if ref not in self._payload_store:
            msg = (
                f"Unknown ref: {ref!r}. Refs are run-scoped — only refs returned in "
                "the current run are valid."
            )
            self._emit_read_payload_result(ref, path, "ref_not_found", 0, False)
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"read_payload: unknown ref {ref!r}",
                payload={"error": msg},
            )

        payload = self._payload_store[ref]
        try:
            result = apply_path(payload, path)
        except PathParseError:
            msg = (
                f"Invalid path syntax: {path!r}. Supported forms: key, key.subkey, "
                "rows[i], rows[i:j], rows.column."
            )
            self._emit_read_payload_result(ref, path, "parse_error", 0, False)
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary="read_payload: parse error",
                payload={"error": msg},
            )
        except PathResolveError as exc:
            msg = f"Path {path!r} did not match payload structure: {exc!s}"
            self._emit_read_payload_result(ref, path, "no_match", 0, False)
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary="read_payload: no match",
                payload={"error": msg},
            )

        result_size = len(json.dumps(result, default=str))
        if result_size > READ_PAYLOAD_CAP_CHARS:
            # Sub-stub on oversized result; reuse original ref.
            sub_stub = generate_stub(result, ref=ref, tool_name=call.name)
            sub_stub["path"] = path
            sub_stub["hint"] = "Slice with rows[i:j] or project with rows.column to narrow."
            self._emit_read_payload_result(ref, path, "sub_stub_returned", result_size, True)
            return ToolCallResult(
                call_id=call.id,
                ok=True,
                summary=f"read_payload: sub-stub returned ({result_size} chars)",
                payload=sub_stub,
            )

        self._emit_read_payload_result(ref, path, "ok", result_size, False)
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=f"read_payload: {result_size} chars",
            payload={"value": result} if not isinstance(result, dict) else result,
        )

    def _emit_read_payload_result(
        self,
        ref: str,
        path: str | None,
        outcome: str,
        result_size_chars: int,
        sub_stub: bool,
    ) -> None:
        self._trace(
            "read_payload.result",
            f"ref={ref} path={path!r} outcome={outcome} size={result_size_chars}",
            {
                "ref": ref,
                "path": path,
                "outcome": outcome,
                "result_size_chars": result_size_chars,
                "sub_stub": sub_stub,
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
