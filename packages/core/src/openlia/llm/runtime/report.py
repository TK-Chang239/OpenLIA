"""ReportRunner — single-pass structured report generation.

Flow per run():
  report.start
  → report.phase("fetching_data")
    → tool loop until the LLM returns no more tool calls
      (emit report.tool_call per dispatched tool)
  → report.phase("writing")
    → bounded loop: model may call read_payload zero or more times,
      then calls submit_report; forced on the final turn.
  → report.phase("finalizing")
  → report.complete(schema=parsed_json)

On LLMProviderError: report.error, stop.
On cancellation: stop yielding, no terminal event.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import json
import os
import re
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError, ModelNotConfiguredError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.attachments import (
    AttachmentNotSupportedError,
    materialize_for_model,
)
from openlia.llm.runtime.cancellation import CancellationToken, await_with_grace
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportSectionComplete,
    ReportSectionStart,
    ReportStart,
    ReportToolCall,
    ReportToolCallStart,
    ReportWebSearchCompleted,
    ReportWebSearchInvoked,
    SseEvent,
)
from openlia.llm.runtime.messages import Attachment, ContentBlock, ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import _READ_PAYLOAD_SCHEMA, MAX_TOOL_TURNS, ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Citation,
    LLMRequest,
    LLMResponse,
    Message,
    ResolvedModel,
    ToolCall,
    ToolSchema,
)
from openlia.reports.citations import normalize_report
from openlia.reports.schema import ReportSchema
from openlia.reports.validator import (
    ReportValidationError,
    enforce_required_rail,
    enforce_uncited_concrete_claims,
    find_uncited_concrete_claims,
    validate_report_payload,
)
from openlia.skills import SkillRegistry

_SUBMIT_REPORT_TOOL_NAME = "submit_report"


def _get_max_writing_turns() -> int:
    raw = os.environ.get("OPENLIA_MAX_WRITING_TURNS")
    if raw is None:
        return 8
    try:
        v = int(raw)
        if v < 1:
            raise ValueError
        return v
    except ValueError:
        return 8


MAX_WRITING_TURNS = _get_max_writing_turns()

# Hard cap on output tokens during the fetching loop. Fetching turns
# emit only tool-call arguments (read_payload paths, eodhd__ args,
# request_additional_tools) — never prose. A 2048 ceiling is enough
# headroom for any tool's arguments while preventing the runaway
# scenario where a model that "gives up" calling tools writes a full
# inline report draft and burns the model's max_output_tokens budget.
# Observed in run r_f03c92dd8c30 turn 6: 13,151 output tokens with
# zero tool calls. Writing phase is unchanged (keeps the full budget).
FETCHING_MAX_OUTPUT_TOKENS = 2048

_SUBMIT_REPORT_DESCRIPTION = (
    "Submit the final report. Call exactly once with the structured payload. "
    "Keys MUST be `cover` and `sections` matching the framework. "
    "Server fills schema_version, department, generated_at — omit them."
)


_SERVER_CONTROLLED_FIELDS = frozenset(
    {"schema_version", "department", "generated_at", "page_furniture"}
)


def _submit_report_input_schema() -> dict[str, Any]:
    """JSON Schema for `submit_report.arguments` derived from `ReportSchema`.

    Server-controlled fields are stripped so the LLM never sees them as
    emittable: meta (`schema_version`, `department`, `generated_at`) and
    presentation (`page_furniture`, which the assembler injects).
    """
    schema = copy.deepcopy(ReportSchema.model_json_schema())
    props = schema.get("properties", {})
    for stripped in _SERVER_CONTROLLED_FIELDS:
        props.pop(stripped, None)
    required = schema.get("required") or []
    schema["required"] = [r for r in required if r not in _SERVER_CONTROLLED_FIELDS]
    schema["properties"] = props
    return schema


def _submit_report_tool() -> ToolSchema:
    return ToolSchema(
        name=_SUBMIT_REPORT_TOOL_NAME,
        description=_SUBMIT_REPORT_DESCRIPTION,
        parameters=_submit_report_input_schema(),
    )


def _extract_writing_payload(final: Any) -> dict[str, Any] | None:
    """Pull the report payload from the writing-turn LLM response.

    Preferred path: a tool_use call to `submit_report` whose `arguments`
    is the structured payload. Backward-compat fallback: parse JSON from
    `final.text`, tolerating markdown fences and prose preambles.
    Returns `None` when neither path produces a parseable payload.
    """
    for call in final.tool_calls or []:
        if call.name == _SUBMIT_REPORT_TOOL_NAME and isinstance(call.arguments, dict):
            return call.arguments
    raw_text = (final.text or "").strip()
    if not raw_text:
        return None
    try:
        return json.loads(_extract_json_object(raw_text))
    except json.JSONDecodeError:
        return None


def _submit_report_tool_choice(provider_kind: str) -> dict[str, Any]:
    """Return the provider-specific `tool_choice` payload that forces the
    model to emit a `submit_report` tool_use. Adapters forward verbatim."""
    return _force_tool_choice(provider_kind, _SUBMIT_REPORT_TOOL_NAME)


_REQUEST_ADDITIONAL_TOOLS_NAME = "request_additional_tools"


def _force_tool_choice(provider_kind: str, tool_name: str) -> dict[str, Any]:
    """Provider-specific `tool_choice` payload forcing `tool_name`.

    Adapters forward verbatim. Used both for forcing `submit_report` on the
    writing-phase final turn and for forcing `request_additional_tools` on
    fetching-phase turn 0 (the empty-starter-pack bootstrap)."""
    if provider_kind == "anthropic":
        return {"type": "tool", "name": tool_name}
    if provider_kind == "gemini":
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [tool_name],
            }
        }
    # OpenAI, OpenRouter, openai_compat, ollama (OpenAI-compatible) all use
    # the chat-completions tool_choice shape.
    return {"type": "function", "function": {"name": tool_name}}


def _unicode_safe_truncate(s: str, *, max_len: int = 120) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len]


def _rescue_failed_searches(
    response: LLMResponse,
    *,
    web_search_resolution: WebSearchResolution,
    seen: set[tuple[int, str]],
    trace: Callable[[str, str, dict[str, Any] | None], None],
) -> LLMResponse:
    """I-a rescue path: rewrite native web_search failures into synthetic
    configured-adapter ToolCalls.

    For each ``FailedSearch`` in ``response.server_tool_failures``:
      * If a configured search adapter is available, append a
        ``ToolCall(name="web_search", arguments={"query": failure.query})``
        to ``response.tool_calls``. The standard dispatch loop picks it
        up on the next turn and routes to the configured adapter.
      * Otherwise, leave the failure inline. The two-source-discipline
        prompt directs the model to write "Data not available".

    Guardrail G-1: ``seen`` is a per-run set of ``(turn_idx, query)``
    pairs that have already been rewritten. A second rewrite of the same
    pair is suppressed to prevent a native-fail → configured-fail →
    re-rewrite loop.

    Pure helper; no side effects beyond ``seen`` mutation and trace
    emission. Returned LLMResponse is a new instance when rewrites
    occur, the original instance otherwise.
    """
    if not response.server_tool_failures:
        return response

    has_configured = (
        web_search_resolution.variant == "configured" and web_search_resolution.adapter is not None
    )
    if not has_configured:
        for f in response.server_tool_failures:
            trace(
                "web_search.failed",
                f"native failed ({f.error_kind}); no configured fallback",
                {"query": f.query, "error_kind": f.error_kind, "turn_idx": f.turn_idx},
            )
        return response

    new_calls = list(response.tool_calls)
    rewrote = False
    for i, f in enumerate(response.server_tool_failures):
        key = (f.turn_idx, f.query)
        if key in seen:
            continue
        seen.add(key)
        new_calls.append(
            ToolCall(
                id=f"rescue_{f.turn_idx}_{i}",
                name="web_search",
                arguments={"query": f.query},
            )
        )
        rewrote = True
        trace(
            "web_search.rescue",
            f"native failed ({f.error_kind}); routing to configured",
            {"query": f.query, "error_kind": f.error_kind, "turn_idx": f.turn_idx},
        )
        # G-3 double-cost flag: each rescue means the provider may have
        # billed for the failed native search AND the configured fallback
        # will bill again. Emit a discrete trace so DevPanel can render
        # rescue rate x estimated double-bill cost.
        trace(
            "web_search.double_billed",
            f"rescue may double-bill ({f.error_kind})",
            {"query": f.query, "error_kind": f.error_kind, "turn_idx": f.turn_idx},
        )

    if not rewrote:
        return response
    return dataclasses.replace(response, tool_calls=new_calls)


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _word_count(node: Any) -> int:
    if isinstance(node, str):
        return len(node.split())
    if isinstance(node, dict):
        return sum(_word_count(v) for v in node.values())
    if isinstance(node, list):
        return sum(_word_count(v) for v in node)
    return 0


def _build_meta_stats(
    payload: dict[str, Any],
    *,
    model_id: str | None,
    total_input_tokens: int,
    total_output_tokens: int,
    web_search_count: int,
) -> dict[str, Any]:
    """Compute the server-authoritative MetaStats block from the
    already-merged payload. Counts are derived from the payload so
    citations from both the LLM and native web_search are included."""
    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    words = _word_count(sections) + _word_count(payload.get("cover"))
    est_minutes = max(1, round(words / 220))
    tokens_total = total_input_tokens + total_output_tokens
    return {
        "sources_count": len(citations),
        "sections_count": len(sections),
        "model_id": model_id,
        "tokens_used": tokens_total if tokens_total > 0 else None,
        "web_search_queries": web_search_count if web_search_count > 0 else None,
        "est_read_minutes": est_minutes,
    }


def _inject_server_fields(
    payload: dict[str, Any], *, department_id: str, generated_at: datetime
) -> dict[str, Any]:
    """Hoist any wrapper layer, strip server-controlled fields, and stamp the
    server-managed meta. Strict-validation candidate is built from this."""
    if not isinstance(payload, dict):
        return payload

    if "cover" not in payload and "sections" not in payload:
        for wrapper_key in ("report", "data", "payload", "result"):
            inner = payload.get(wrapper_key)
            if isinstance(inner, dict) and ("cover" in inner or "sections" in inner):
                payload = inner
                break

    payload.pop("report_metadata", None)
    payload.pop("report_mode", None)
    payload.pop("page_furniture", None)
    # meta_stats is server-computed; drop any model-authored copy at the
    # root so strict validation doesn't fail on a stale snapshot.
    payload.pop("meta_stats", None)

    rail = payload.get("rail")
    if isinstance(rail, dict):
        # Model recurrently nests `citations` and `meta_stats` under rail
        # despite the prompt rule. Hoist citations to root (root wins on
        # id collision), drop meta_stats outright.
        misplaced = rail.pop("citations", None)
        rail.pop("meta_stats", None)
        if isinstance(misplaced, list) and misplaced:
            existing = payload.get("citations")
            if not isinstance(existing, list):
                existing = []
            existing_ids = {
                c["id"]
                for c in existing
                if isinstance(c, dict) and isinstance(c.get("id"), str)
            }
            for cit in misplaced:
                if not isinstance(cit, dict):
                    continue
                cid = cit.get("id")
                if not isinstance(cid, str) or cid in existing_ids:
                    continue
                existing.append(cit)
                existing_ids.add(cid)
            payload["citations"] = existing

    payload["schema_version"] = "2.0"
    payload["department"] = department_id
    payload["generated_at"] = generated_at.isoformat()
    payload.setdefault("cover", {})
    payload.setdefault("sections", [])
    return payload


def _finalize_submit_payload(
    args: dict[str, Any],
    *,
    department_id: str,
    generated_at: datetime,
    provider_citations: list[Citation],
    model_id: str,
    total_input_tokens: int,
    total_output_tokens: int,
    web_search_count: int,
) -> dict[str, Any]:
    """Apply server-side finalization to a submit_report payload.

    Sequence: hoist+stamp server fields → rewrite inline citation tuples
    into `[N]` footnotes → append native-provider citations not already
    inline → stamp server-authoritative `meta_stats`. The result is
    ready for strict Pydantic validation by the caller.
    """
    candidate = _inject_server_fields(
        copy.deepcopy(args),
        department_id=department_id,
        generated_at=generated_at,
    )
    candidate = normalize_report(candidate)
    _merge_provider_citations(candidate, provider_citations)
    candidate["meta_stats"] = _build_meta_stats(
        candidate,
        model_id=model_id,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        web_search_count=web_search_count,
    )
    return candidate


def _merge_provider_citations(payload: dict[str, Any], provider_citations: list[Citation]) -> None:
    """Merge native-provider citations into payload['citations'] in
    place. Model-authored entries (from submit_report) win on id
    collision; provider-only entries are appended.

    ReportSchema.Citation accepts {id, title, source?, url?, date?},
    so we drop the dataclass-only fields (kind, snippet, segments,
    tool_*) when projecting.
    """
    if not provider_citations:
        return
    existing = payload.get("citations")
    if not isinstance(existing, list):
        existing = []
    existing_ids = {
        c["id"] for c in existing if isinstance(c, dict) and isinstance(c.get("id"), str)
    }
    for cit in provider_citations:
        if cit.id in existing_ids:
            continue
        projected: dict[str, Any] = {"id": cit.id, "title": cit.title or cit.id}
        if cit.source is not None:
            projected["source"] = cit.source
        if cit.url is not None:
            projected["url"] = cit.url
        if cit.date is not None:
            projected["date"] = cit.date
        existing.append(projected)
        existing_ids.add(cit.id)
    payload["citations"] = existing


def _apply_coercion_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    """Last-resort drift coercion. Used only after strict validation fails
    AND the LLM has exhausted its repair turn. Silently rewrites authorial
    intent (e.g., folds chart `note` into title) — always pair with a
    telemetry event so the rewrite is observable."""
    if not isinstance(payload, dict):
        return payload
    cover = payload.get("cover") if isinstance(payload.get("cover"), dict) else {}
    _coerce_metric_list(cover.get("key_metrics"))
    cover.pop("stats_panel", None)
    rail = payload.get("rail")
    if isinstance(rail, dict):
        _coerce_metric_list(rail.get("quick_stats"))
        _coerce_sparkline(rail.get("sparkline"))
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    for section in sections:
        if isinstance(section, dict):
            _coerce_blocks(section.get("blocks"))
    return payload


def _normalize_schema_payload(
    payload: dict[str, Any], *, department_id: str, generated_at: datetime
) -> dict[str, Any]:
    """Compatibility wrapper: server-field injection + coercion fallback.
    New writing-loop code uses the two pieces separately."""
    payload = _inject_server_fields(payload, department_id=department_id, generated_at=generated_at)
    return _apply_coercion_fallback(payload)


def _coerce_metric_value(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    return v


def _coerce_sparkline_point(idx: int, point: Any) -> Any:
    """Per-element sparkline coercion. Valid `{x, y}` dicts pass through; a
    bare number becomes `{"x": idx, "y": number}`; a 2-element list/tuple
    becomes `{"x": first, "y": second}`. Anything else is left untouched so
    strict validation surfaces a precise error."""
    if isinstance(point, dict):
        return point
    if isinstance(point, bool):
        return point
    if isinstance(point, (int, float)):
        return {"x": float(idx), "y": float(point)}
    if isinstance(point, (list, tuple)) and len(point) == 2:
        x, y = point
        if (
            isinstance(x, (int, float))
            and not isinstance(x, bool)
            and (isinstance(y, (int, float)) and not isinstance(y, bool))
        ):
            return {"x": float(x), "y": float(y)}
    return point


def _coerce_sparkline(sparkline: Any) -> None:
    if not isinstance(sparkline, dict):
        return
    points = sparkline.get("points")
    if not isinstance(points, list):
        return
    sparkline["points"] = [_coerce_sparkline_point(i, p) for i, p in enumerate(points)]


def _coerce_metric_list(metrics: Any) -> None:
    if not isinstance(metrics, list):
        return
    for m in metrics:
        if not isinstance(m, dict):
            continue
        if "value" in m:
            m["value"] = _coerce_metric_value(m["value"])
        if "delta" in m:
            m["delta"] = _coerce_metric_value(m["delta"])


_CHART_OPTION_KEYS = {"height", "show_legend", "show_grid"}
_CHART_BLOCK_TYPES = {
    "line_chart",
    "bar_chart",
    "area_chart",
    "pie_chart",
    "candlestick_chart",
    "waterfall_chart",
    "scatter_plot",
    "heatmap",
    "treemap",
    "combo_chart",
}


def _coerce_chart_options(block: dict[str, Any]) -> None:
    options = block.get("options")
    if not isinstance(options, dict):
        return
    extras = [k for k in options if k not in _CHART_OPTION_KEYS]
    if not extras:
        return
    note_parts: list[str] = []
    for k in extras:
        v = options.pop(k)
        if k == "note" and isinstance(v, str):
            note_parts.append(v)
    if note_parts and block.get("type") in _CHART_BLOCK_TYPES:
        title = block.get("title")
        suffix = " — " + " ".join(note_parts)
        if isinstance(title, str) and suffix not in title:
            block["title"] = title + suffix


def _slugify_key(label: str, fallback: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", label.lower()).strip("_") or fallback


def _coerce_table_headers(block: dict[str, Any]) -> None:
    headers = block.get("headers")
    if not isinstance(headers, list):
        return
    fixed: list[Any] = []
    for idx, h in enumerate(headers):
        fallback = f"col_{idx}"
        if isinstance(h, dict):
            if "label" in h and "key" not in h and isinstance(h["label"], str):
                h = {**h, "key": _slugify_key(h["label"], fallback)}
            fixed.append(h)
            continue
        if isinstance(h, str):
            fixed.append({"key": _slugify_key(h, fallback), "label": h})
            continue
        if isinstance(h, list) and h:
            label = str(h[-1]) if len(h) > 1 else str(h[0])
            key = str(h[0]) if len(h) > 1 else _slugify_key(label, fallback)
            fixed.append({"key": _slugify_key(key, fallback), "label": label})
            continue
        label = "" if h is None else str(h)
        fixed.append({"key": _slugify_key(label, fallback), "label": label})
    block["headers"] = fixed


def _coerce_combo_series(series: Any) -> None:
    """combo_chart series schema requires ``values``; LLM drift commonly ships
    ``data`` (the line/area-chart key) instead. Rename so strict validation
    accepts the payload."""
    if not isinstance(series, list):
        return
    for s in series:
        if isinstance(s, dict) and "values" not in s and isinstance(s.get("data"), list):
            s["values"] = s.pop("data")


def _coerce_blocks(blocks: Any) -> None:
    if not isinstance(blocks, list):
        return
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "metric_cards":
            _coerce_metric_list(block.get("metrics"))
        elif btype == "group":
            _coerce_blocks(block.get("blocks"))
        elif btype == "table":
            _coerce_table_headers(block)
        elif btype in _CHART_BLOCK_TYPES:
            _coerce_chart_options(block)
            if btype == "combo_chart":
                _coerce_combo_series(block.get("bar_series"))
                _coerce_combo_series(block.get("line_series"))


def _extract_json_object(text: str) -> str:
    s = text.strip()
    fence = _FENCE_RE.match(s)
    if fence is not None:
        s = fence.group(1).strip()
    if s.startswith("{") or s.startswith("["):
        return s
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s


def build_report_system_prompt(
    *,
    department_id: str,
    user_id: str | None,
    registry: SkillRegistry,
    style_guide: str,
    available_category_hints: list[str],
    current_date: str,
    current_date_long: str,
    search_budget: int = 8,
    connector_quirks: tuple[str, ...] = ("eodhd",),
    loader: PromptLoader | None = None,
    disabled_skill_ids: frozenset[str] = frozenset(),
) -> str:
    """Render the report.system slot with the user's visible skills menu.

    `current_date` (ISO date) and `current_date_long` (human form) anchor the
    model to today. `search_budget` feeds the two-source-discipline partial's
    per-report cap so the model knows how many web searches it has left.
    All three are consumed under StrictUndefined; the caller must always
    supply them.

    ``disabled_skill_ids`` is the per-session opt-out set from the
    chat-input "Tools" picker; matching the chat-path contract, skills
    whose ``manifest.name`` is in the set are stripped from ``skills_menu``
    so the model never knows they exist this run.
    """
    loader = loader or PromptLoader()
    visible = registry.visible(
        department_id=department_id,
        user_id=user_id,
        disabled_skill_ids=disabled_skill_ids,
    )
    skills_menu = [
        {
            "id": s.manifest.name,
            "description": s.manifest.description,
            "tools": [
                f"skill__{s.manifest.name.replace('-', '_')}__{t['name']}"
                for t in (s.manifest.tools or [])
            ],
        }
        for s in visible
    ]
    return loader.render(
        department_id,
        "report.system",
        style_guide=style_guide,
        skills_menu=skills_menu,
        available_category_hints=available_category_hints,
        current_date=current_date,
        current_date_long=current_date_long,
        search_budget=search_budget,
        connector_quirks=list(connector_quirks),
    )


ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


def _default_frameworks_root() -> Path:
    return Path(str(resources.files("openlia.reports.frameworks")))


def _load_framework(frameworks_root: Path, mode: str) -> dict[str, Any]:
    path = frameworks_root / f"{mode}.json"
    return json.loads(path.read_text())


def _load_style_guide(frameworks_root: Path, mode: str) -> str:
    path = frameworks_root / f"{mode}_style_guide.md"
    return path.read_text() if path.exists() else ""


def _customize_framework(framework: dict[str, Any], request: ReportRequest) -> dict[str, Any]:
    fw = copy.deepcopy(framework)
    sections = fw.get("sections", [])
    if request.enabled_sections:
        wanted = set(request.enabled_sections)
        sections = [s for s in sections if s.get("id") in wanted]
    for custom in request.custom_sections:
        sections.append(dict(custom))
    fw["sections"] = sections
    fw["length_preference"] = request.length
    return fw


def _section_titles(framework: dict[str, Any]) -> list[str]:
    return [s.get("title", s.get("id", "Section")) for s in framework.get("sections", [])]


_MODE_LABELS = {
    "stock_initiation": "Stock Initiation Report",
    "stock_update": "Stock Update Report",
    "sector_research": "Sector Research Report",
    "earnings_update": "Earnings Update",
    "morning_briefing": "Morning Briefing",
}


def _mode_label(mode: str) -> str:
    return _MODE_LABELS.get(mode, "Report")


def _tool_name_for_result(response: Any, call_id: str) -> str:
    for call in response.tool_calls:
        if call.id == call_id:
            return call.name
    return "unknown"


TraceRecorder = Callable[[str, str, dict[str, Any] | None], None]


def _no_trace(_category: str, _message: str, _payload: dict[str, Any] | None) -> None:
    return None


_GLOBAL_DEFAULT_SEARCH_BUDGET = 8


def _resolve_search_budget(*, framework: dict[str, Any] | None, override: int | None) -> int:
    """Pick the per-report web-search cap.

    Three-level chain: user override → framework default → 8. Bad
    values (non-int, zero, negative, bool) fall through to the next
    level so a typo'd ``"10"`` in a framework file or a stray ``0`` in
    a user pref never silently disables search.
    """

    def _is_pos_int(v: Any) -> bool:
        return isinstance(v, int) and not isinstance(v, bool) and v > 0

    if _is_pos_int(override):
        return int(override) if override is not None else _GLOBAL_DEFAULT_SEARCH_BUDGET
    if isinstance(framework, dict):
        fw_default = framework.get("web_search_budget_default")
        if _is_pos_int(fw_default):
            return int(fw_default)
    return _GLOBAL_DEFAULT_SEARCH_BUDGET


def _web_search_events_for_response(
    response: LLMResponse,
    *,
    report_id: str,
    turn_idx: int,
    provider_kind: str,
) -> list[SseEvent]:
    """Build the ReportWebSearchInvoked/Completed pair for an LLM turn
    that exercised native server-side web search.

    Emits one ``ReportWebSearchInvoked`` per ``server_tool_calls`` entry
    named ``web_search``, then a single aggregate ``ReportWebSearchCompleted``
    carrying the de-duplicated web citation URLs from the same turn.
    Returns an empty list when the response carried no native search
    activity — guards against phantom events for plain tool-calling
    turns.
    """
    search_calls = [c for c in response.server_tool_calls if c.name == "web_search"]
    if not search_calls:
        return []
    events: list[SseEvent] = []
    for call in search_calls:
        events.append(
            ReportWebSearchInvoked(
                report_id=report_id,
                query=str(call.arguments.get("query", "")),
                turn_idx=turn_idx,
                provider=provider_kind,
            )
        )
    seen: set[str] = set()
    urls: list[str] = []
    for c in response.citations:
        if c.kind != "web" or not c.url or c.url in seen:
            continue
        seen.add(c.url)
        urls.append(c.url)
    events.append(
        ReportWebSearchCompleted(
            report_id=report_id,
            n_results=len(urls),
            urls=urls,
            turn_idx=turn_idx,
            provider=provider_kind,
        )
    )
    return events


class ReportRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        tools: ToolDispatcher,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
        skill_registry: SkillRegistry,
        frameworks_root: Path | None = None,
        report_id_factory: Callable[[], str] | None = None,
        trace: TraceRecorder | None = None,
    ) -> None:
        self._prompts = prompts
        self._tools = tools
        self._resolve = resolve
        self._registry = registry
        self._provider_factory = provider_factory
        self._skill_registry = skill_registry
        self._frameworks_root = (
            frameworks_root if frameworks_root is not None else _default_frameworks_root()
        )
        self._report_id_factory = report_id_factory or (lambda: f"r_{uuid.uuid4().hex[:12]}")
        self._trace: TraceRecorder = trace or _no_trace

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
        cancel_token: CancellationToken | None = None,
        attachments: list[Attachment] | None = None,
        model_id_override: str | None = None,
        disabled_skill_ids: frozenset[str] = frozenset(),
    ) -> AsyncIterator[SseEvent]:
        report_id = self._report_id_factory()

        using_user_template = bool(request.user_template_text)
        framework_raw: dict[str, Any] | None
        if using_user_template:
            framework: dict[str, Any] = {"sections": [], "length_preference": request.length}
            framework_raw = None
            style_guide = ""
        else:
            framework_raw = _load_framework(self._frameworks_root, request.mode)
            framework = _customize_framework(framework_raw, request)
            style_guide = _load_style_guide(self._frameworks_root, request.mode)

        search_budget = _resolve_search_budget(
            framework=framework_raw,
            override=request.web_search_budget_override,
        )

        self._trace(
            "report.request",
            f"report start department={department_id} mode={request.mode}",
            {
                "report_id": report_id,
                "department_id": department_id,
                "mode": request.mode,
                "user_id": user_id,
                "length": request.length,
                "enabled_sections": list(request.enabled_sections or []),
            },
        )

        yield ReportStart(
            report_id=report_id,
            department=department_id,
            mode=request.mode,
            section_titles=_section_titles(framework),
        )

        try:
            resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
                model_id_override=model_id_override,
            )
        except (LLMProviderError, ModelNotConfiguredError) as exc:
            self._trace(
                "report.error",
                f"resolve failed: {exc}",
                {"report_id": report_id, "error_class": type(exc).__name__},
            )
            yield ReportError(
                report_id=report_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        try:
            materialized = materialize_for_model(
                attachments or (),
                capabilities=resolved.capabilities,
                available_token_budget=max(
                    1,
                    resolved.capabilities.max_context_tokens
                    - resolved.capabilities.max_output_tokens
                    - 4_000,
                ),
            )
        except AttachmentNotSupportedError as exc:
            yield ReportError(
                report_id=report_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return
        materialized_blocks: tuple[ContentBlock, ...] = tuple(materialized.blocks)
        for warning in materialized.warnings:
            self._trace("attachment.warning", warning, None)

        self._trace(
            "llm.resolved",
            f"resolved provider={resolved.provider_kind} model={resolved.model_ref}",
            {
                "report_id": report_id,
                "provider_kind": resolved.provider_kind,
                "model_ref": resolved.model_ref,
            },
        )
        provider = self._provider_factory(resolved)

        available_category_hints = await self._tools.available_categories()
        now = datetime.now(UTC)
        current_date = now.date().isoformat()
        current_date_long = f"{now.strftime('%A')}, {now.strftime('%B')} {now.day}, {now.year}"
        system = build_report_system_prompt(
            department_id=department_id,
            user_id=user_id,
            registry=self._skill_registry,
            style_guide=style_guide,
            available_category_hints=available_category_hints,
            current_date=current_date,
            current_date_long=current_date_long,
            search_budget=search_budget,
            loader=self._prompts,
            disabled_skill_ids=disabled_skill_ids,
        )
        tools = await self._tools.build(department_id, has_web_search=True)
        if using_user_template:
            user_msg = self._prompts.render(
                department_id,
                "report.user_template.user",
                user_input=request.user_input,
                length=request.length,
                user_template_text=request.user_template_text or "",
                template_name=request.user_template_name or "(unnamed)",
                mode_label=_mode_label(request.mode),
                current_date=current_date,
                current_date_long=current_date_long,
                has_tools=bool(tools),
            )
        else:
            user_msg = self._prompts.render(
                department_id,
                f"report.{request.mode}.user",
                user_input=request.user_input,
                framework=framework,
                length=request.length,
                enabled_sections=request.enabled_sections,
                custom_sections=request.custom_sections,
                section_topics=request.section_topics,
                reference_portfolio=request.reference_portfolio,
                current_date=current_date,
                current_date_long=current_date_long,
                has_tools=bool(tools),
            )

        conversation = [Message(role="user", content=user_msg, content_blocks=materialized_blocks)]

        yield ReportPhase(report_id=report_id, phase="fetching_data")

        # Phase 0 wiring: derive native_tools from the runtime's web
        # search resolution. When variant=="native", adapters will swap
        # the provider's native web_search tool block into the wire
        # payload; the dispatcher already suppresses the generic
        # ToolSchema in this case (guardrail G-6). When variant is
        # configured or unavailable, native_tools stays empty.
        native_tools: tuple[str, ...] = (
            ("web_search",) if self._tools.web_search.variant == "native" else ()
        )
        # Native path: forward the per-report budget to the provider so it
        # enforces server-side (Anthropic's `max_uses`). Configured path:
        # the dispatcher still keeps its own counter via
        # `self._tools.web_search_budget` (G-2). When neither path is
        # active, send `None` so adapters skip the cap field entirely.
        if self._tools.web_search.variant == "native":
            web_search_max_uses: int | None = search_budget
        else:
            web_search_max_uses = self._tools.web_search_budget
        # Per-run rescue set (guardrail G-1): each (turn_idx, query)
        # pair gets at most one configured-adapter rewrite. If the
        # configured retry also fails, the failure stays inline and the
        # two-source-discipline prompt instructs the model to write
        # "Data not available."
        rescue_seen: set[tuple[int, str]] = set()
        # G-9 cost telemetry accumulators. Surfaced on ReportComplete.
        web_search_count = 0
        web_search_provider_breakdown: dict[str, int] = {}
        web_search_rescues = 0
        # Aggregate token usage across all provider turns. Used to
        # populate ReportSchema.meta_stats.tokens_used so the
        # left-sidebar "Report Stats" card reflects the real cost.
        total_input_tokens = 0
        total_output_tokens = 0
        # Provider-emitted citations from LLMResponse.citations across
        # all turns. Merged into ReportSchema.citations at submit time;
        # model-authored entries (from submit_report) win on id collision.
        provider_citations: list[Citation] = []
        provider_citation_ids: set[str] = set()

        def _absorb_response_citations(resp_citations: tuple[Citation, ...]) -> None:
            for cit in resp_citations:
                if cit.id in provider_citation_ids:
                    continue
                provider_citation_ids.add(cit.id)
                provider_citations.append(cit)

        def _sub_path(provider_kind: str, has_native: bool) -> str:
            # G-8: OpenAI multiplexes; other providers use a single API.
            if provider_kind == "openai":
                return "responses" if has_native else "chat_completions"
            return provider_kind

        def _emit_provider_selected(
            turn_idx_: int, phase: str, *, turn_native_tools: tuple[str, ...]
        ) -> None:
            self._trace(
                "llm.provider.selected",
                f"turn {turn_idx_} via {resolved.provider_kind}",
                {
                    "report_id": report_id,
                    "provider_kind": resolved.provider_kind,
                    "sub_path": _sub_path(resolved.provider_kind, bool(turn_native_tools)),
                    "native_tools": list(turn_native_tools),
                    "turn_idx": turn_idx_,
                    "phase": phase,
                },
            )

        force_escalation_choice = _force_tool_choice(
            resolved.provider_kind, _REQUEST_ADDITIONAL_TOOLS_NAME
        )
        for turn_idx in range(MAX_TOOL_TURNS) if tools else range(0):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            self._trace(
                "llm.call.start",
                f"tool turn {turn_idx} (tools={len(tools or [])})",
                {"report_id": report_id, "phase": "fetching_data", "turn": turn_idx},
            )
            _emit_provider_selected(turn_idx, phase="fetching_data", turn_native_tools=native_tools)
            # Empty-starter-pack bootstrap: on turn 0 the LLM has only
            # `request_additional_tools`, `read_payload`, and (optionally)
            # `web_search` available. Without forcing, some models produce a
            # text-only refusal ("no data tools available") on turn 0 and
            # exit the loop with zero data — the writing phase then submits
            # a "no data" report. Forcing the meta-tool on turn 0 guarantees
            # at least one escalation attempt; the 3-failure directive in
            # ToolDispatcher handles graceful degradation if expansion truly
            # yields nothing.
            turn_tool_choice = force_escalation_choice if turn_idx == 0 else None
            try:
                response = await self._await(
                    provider.generate(
                        LLMRequest(
                            messages=conversation,
                            system=system,
                            tools=tools or None,
                            tool_choice=turn_tool_choice,
                            max_tokens=min(
                                resolved.capabilities.max_output_tokens,
                                FETCHING_MAX_OUTPUT_TOKENS,
                            ),
                            native_tools=native_tools,
                            web_search_max_uses=web_search_max_uses,
                        )
                    ),
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                return
            except LLMProviderError as exc:
                self._trace(
                    "llm.call.error",
                    f"provider error: {exc}",
                    {"report_id": report_id, "error_class": type(exc).__name__},
                )
                yield ReportError(
                    report_id=report_id,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return
            total_input_tokens += response.input_tokens or 0
            total_output_tokens += response.output_tokens or 0
            # G-9 accounting: count native server-side searches before
            # rescue rewriting (a rescued failure should not double-count
            # as a successful search).
            for _stc in response.server_tool_calls:
                if _stc.name == "web_search":
                    web_search_count += 1
                    web_search_provider_breakdown[resolved.provider_kind] = (
                        web_search_provider_breakdown.get(resolved.provider_kind, 0) + 1
                    )
            _absorb_response_citations(response.citations)
            _seen_before = len(rescue_seen)
            # I-a rescue: when a provider's native web_search failed
            # mid-turn and a configured fallback exists, rewrite each
            # failure into a synthetic web_search ToolCall. The
            # standard dispatch loop below picks it up next turn.
            response = _rescue_failed_searches(
                response,
                web_search_resolution=self._tools.web_search,
                seen=rescue_seen,
                trace=self._trace,
            )
            web_search_rescues += len(rescue_seen) - _seen_before
            for _ev in _web_search_events_for_response(
                response,
                report_id=report_id,
                turn_idx=turn_idx,
                provider_kind=resolved.provider_kind,
            ):
                yield _ev
            self._trace(
                "llm.call.done",
                f"tool turn {turn_idx} done tool_calls={len(response.tool_calls)}",
                {
                    "report_id": report_id,
                    "turn": turn_idx,
                    "tool_calls": [c.name for c in response.tool_calls],
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cached_input_tokens": response.cached_input_tokens,
                },
            )
            if not response.tool_calls:
                break
            # Replay the assistant's tool-call turn so the next provider
            # request preserves the standard tool-use protocol shape:
            #   user → assistant(tool_calls) → tool(result, tool_call_id) → ...
            # Without this, OpenRouter forwards the tool result with an
            # empty tool_use_id and Anthropic rejects it (regex
            # ^[a-zA-Z0-9_-]+$).
            conversation.append(
                Message(
                    role="assistant",
                    content=response.text or "",
                    tool_calls=tuple(response.tool_calls),
                )
            )
            for call in response.tool_calls:
                args_preview = _unicode_safe_truncate(
                    json.dumps(call.arguments, separators=(",", ":"), ensure_ascii=False),
                    max_len=120,
                )
                self._trace(
                    "report.tool_call",
                    f"{call.name}({args_preview})",
                    {"report_id": report_id, "call_id": call.id, "tool": call.name},
                )
                yield ReportToolCallStart(
                    report_id=report_id,
                    call_id=call.id,
                    tool_name=call.name,
                    args_preview=args_preview,
                )
            try:
                results = await self._await(
                    self._tools.dispatch_many(
                        department_id=department_id,
                        calls=response.tool_calls,
                    ),
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                return
            for r in results:
                tool_name = _tool_name_for_result(response, r.call_id)
                self._trace(
                    "report.tool_result",
                    f"{tool_name} -> {_unicode_safe_truncate(r.summary, max_len=160)}",
                    {"report_id": report_id, "call_id": r.call_id, "tool": tool_name},
                )
                yield ReportToolCall(
                    report_id=report_id,
                    tool_name=tool_name,
                    summary=r.summary,
                    call_id=r.call_id,
                )
                conversation.append(
                    Message(
                        role="tool",
                        content=json.dumps(r.payload),
                        tool_call_id=r.call_id,
                    )
                )
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            escalated = any(c.name == "request_additional_tools" for c in response.tool_calls)
            if escalated:
                tools = await self._tools.build(
                    department_id, has_web_search=True, expose_escalation=False
                )

        yield ReportPhase(report_id=report_id, phase="writing")
        if cancel_token is not None and cancel_token.is_cancelled:
            return

        sections_meta = framework.get("sections", []) or []
        total_sections = len(sections_meta)
        for idx, section in enumerate(sections_meta):
            yield ReportSectionStart(
                report_id=report_id,
                section_id=str(section.get("id", "")),
                title=str(section.get("title", section.get("id", "Section"))),
                idx=idx,
                total=total_sections,
            )

        writing_max_tokens = resolved.capabilities.max_output_tokens
        submit_tool = _submit_report_tool()
        submit_choice = _submit_report_tool_choice(resolved.provider_kind)
        writing_tools = [submit_tool, _READ_PAYLOAD_SCHEMA]

        final = None
        validated_payload: dict[str, Any] | None = None
        for writing_turn in range(MAX_WRITING_TURNS):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            is_final_turn = writing_turn == MAX_WRITING_TURNS - 1
            self._trace(
                "llm.call.start",
                f"writing turn {writing_turn} (forced={is_final_turn})",
                {
                    "report_id": report_id,
                    "phase": "writing",
                    "turn": writing_turn,
                    "forced": is_final_turn,
                },
            )
            _emit_provider_selected(writing_turn, phase="writing", turn_native_tools=())
            try:
                response = await self._await(
                    provider.generate(
                        LLMRequest(
                            messages=conversation,
                            system=system,
                            tools=writing_tools,
                            tool_choice=submit_choice if is_final_turn else None,
                            max_tokens=writing_max_tokens,
                        )
                    ),
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                return
            except LLMProviderError as exc:
                self._trace(
                    "llm.call.error",
                    f"writing-turn provider error: {exc}",
                    {"report_id": report_id},
                )
                yield ReportError(
                    report_id=report_id,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return

            total_input_tokens += response.input_tokens or 0
            total_output_tokens += response.output_tokens or 0
            for _ev in _web_search_events_for_response(
                response,
                report_id=report_id,
                turn_idx=writing_turn,
                provider_kind=resolved.provider_kind,
            ):
                yield _ev
            _absorb_response_citations(response.citations)

            # Check for submit_report call.
            submit_call = next(
                (c for c in response.tool_calls if c.name == _SUBMIT_REPORT_TOOL_NAME), None
            )
            if submit_call is not None:
                args = submit_call.arguments if isinstance(submit_call.arguments, dict) else {}
                candidate = _finalize_submit_payload(
                    args,
                    department_id=department_id,
                    generated_at=datetime.now(UTC),
                    provider_citations=provider_citations,
                    model_id=resolved.model_ref,
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    web_search_count=web_search_count,
                )
                try:
                    validated_schema = validate_report_payload(candidate)
                    enforce_required_rail(validated_schema, department_id=department_id)
                    validated_payload = candidate
                    final = response
                    # Phase 5d: surface uncited-claim warnings as traces.
                    # Phase 6a: when ``request.citations_strict`` is set,
                    # promote warnings to a ``ReportValidationError`` so
                    # the rescue/retry loop fires below; otherwise stay
                    # warn-only.
                    uncited_warnings = find_uncited_concrete_claims(validated_schema)
                    for w in uncited_warnings:
                        self._trace(
                            "report.warning.uncited_claim",
                            f"{w.path}: {w.message}",
                            {
                                "report_id": report_id,
                                "kind": w.kind,
                                "slot": w.slot,
                                "path": w.path,
                            },
                        )
                    enforce_uncited_concrete_claims(
                        validated_schema, strict=request.citations_strict
                    )
                    self._trace(
                        "llm.call.done",
                        (
                            f"writing turn {writing_turn} done (strict-valid) "
                            f"tool_calls={len(response.tool_calls)}"
                        ),
                        {
                            "report_id": report_id,
                            "phase": "writing",
                            "input_tokens": response.input_tokens,
                            "output_tokens": response.output_tokens,
                            "cached_input_tokens": response.cached_input_tokens,
                            "finish_reason": response.finish_reason,
                            "tool_call_names": [c.name for c in response.tool_calls],
                            "text_preview": _unicode_safe_truncate(
                                response.text or "", max_len=200
                            ),
                            "strict_valid": True,
                        },
                    )
                    break
                except ReportValidationError as exc:
                    self._trace(
                        "writing.validation_failed",
                        f"submit_report failed strict validation on turn {writing_turn}: {exc}",
                        {
                            "report_id": report_id,
                            "turn": writing_turn,
                            "is_final_turn": is_final_turn,
                            "errors": list(exc.details)[:20],
                        },
                    )
                    if is_final_turn:
                        final = response
                        break
                    # Push validation error back as a tool result so the
                    # model can self-repair on the next turn.
                    conversation.append(
                        Message(
                            role="assistant",
                            content=response.text or "",
                            tool_calls=tuple(response.tool_calls),
                        )
                    )
                    failing_paths = "; ".join(
                        f"{d['path']} ({d['message']})" for d in exc.details[:10]
                    )
                    error_payload = {
                        "ok": False,
                        "error": "validation_failed",
                        "message": str(exc),
                        "errors": list(exc.details),
                        "instruction": (
                            "Your submit_report payload failed strict schema validation. "
                            f"FAILING FIELDS: {failing_paths}. "
                            "Re-submit the ENTIRE payload (do not assume earlier fields are "
                            "remembered) with EVERY failing field fixed. "
                            "Required top-level keys: `cover` (object) and `sections` (array). "
                            "Required cover fields: `title` (str), `subtitle` (str), "
                            "`tagline` (str). Use the framework's cover.instructions to "
                            "decide what to write. Each section needs `id`, `title`, and "
                            "non-empty `blocks`. "
                            "Reminders: do NOT include page_furniture, schema_version, "
                            "department, or generated_at (server-set); ChartOptions accepts "
                            "only {height, show_legend, show_grid}; table headers must be "
                            "objects with {key, label}; metric value/delta must be strings. "
                            "If any failing path starts with `rail.`: `rail` accepts ONLY "
                            "`verdict`, `quick_stats`, `sparkline`. Move `citations` to the "
                            "ROOT of the payload (sibling of `cover`/`sections`), and drop "
                            "`meta_stats` entirely (server-computed)."
                        ),
                    }
                    conversation.append(
                        Message(
                            role="tool",
                            content=json.dumps(error_payload),
                            tool_call_id=submit_call.id,
                        )
                    )
                    first = exc.details[0] if exc.details else None
                    chip_summary = (
                        f"validation_failed: {first['path']}: {first['message']}"
                        if first
                        else f"validation_failed: {exc}"
                    )
                    yield ReportToolCall(
                        report_id=report_id,
                        tool_name=_SUBMIT_REPORT_TOOL_NAME,
                        summary=_unicode_safe_truncate(chip_summary, max_len=200),
                        call_id=submit_call.id,
                    )
                    continue

            # No submit_report and no tool calls at all. On the final turn the
            # caller already forced submit_report via tool_choice — so this is
            # a refusal we couldn't override; record it and break. On earlier
            # turns we push a reminder and continue: writing exists only to
            # call submit_report (or read_payload), so a text-only "I can't
            # complete this report" response is never a legitimate stop.
            if not response.tool_calls:
                self._trace(
                    "llm.call.done",
                    f"writing turn {writing_turn} done (no tool calls)",
                    {
                        "report_id": report_id,
                        "phase": "writing",
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "cached_input_tokens": response.cached_input_tokens,
                        "finish_reason": response.finish_reason,
                        "tool_call_names": [],
                        "text_preview": _unicode_safe_truncate(response.text or "", max_len=200),
                    },
                )
                if is_final_turn:
                    final = response
                    break
                conversation.append(Message(role="assistant", content=response.text or ""))
                conversation.append(
                    Message(
                        role="user",
                        content=(
                            "Your previous response had no tool calls. The writing "
                            "phase requires you to call the submit_report tool with "
                            "the report payload. Do not refuse: if data is missing, "
                            "state that plainly inside the report sections rather "
                            "than skipping the call. Call submit_report now."
                        ),
                    )
                )
                self._trace(
                    "writing.refusal_recovered",
                    f"text-only response on writing turn {writing_turn}; pushed reminder",
                    {
                        "report_id": report_id,
                        "turn": writing_turn,
                        "text_preview": _unicode_safe_truncate(response.text or "", max_len=200),
                    },
                )
                continue

            # Dispatch tool calls (read_payload, etc.) and continue.
            conversation.append(
                Message(
                    role="assistant",
                    content=response.text or "",
                    tool_calls=tuple(response.tool_calls),
                )
            )
            for call in response.tool_calls:
                args_preview = _unicode_safe_truncate(
                    json.dumps(call.arguments, separators=(",", ":"), ensure_ascii=False),
                    max_len=120,
                )
                yield ReportToolCallStart(
                    report_id=report_id,
                    call_id=call.id,
                    tool_name=call.name,
                    args_preview=args_preview,
                )
            try:
                results = await self._await(
                    self._tools.dispatch_many(
                        department_id=department_id,
                        calls=response.tool_calls,
                    ),
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                return

            for r in results:
                tool_name = _tool_name_for_result(response, r.call_id)
                if tool_name == "read_payload":
                    self._trace(
                        "writing.read_payload",
                        f"writing-phase read_payload: {r.summary}",
                        {"report_id": report_id, "call_id": r.call_id, "ok": r.ok},
                    )
                yield ReportToolCall(
                    report_id=report_id,
                    tool_name=tool_name,
                    summary=r.summary,
                    call_id=r.call_id,
                )
                conversation.append(
                    Message(
                        role="tool",
                        content=json.dumps(r.payload),
                        tool_call_id=r.call_id,
                    )
                )
        else:
            # for/else: exhausted MAX_WRITING_TURNS without submit_report.
            self._trace(
                "writing.forced_submit",
                f"writing-phase hit MAX_WRITING_TURNS={MAX_WRITING_TURNS} without submit",
                {"report_id": report_id, "max_turns": MAX_WRITING_TURNS},
            )

        if final is None:
            yield ReportError(
                report_id=report_id,
                error_class="RuntimeError",
                message="Writing phase ended with no LLM response.",
            )
            return

        yield ReportPhase(report_id=report_id, phase="finalizing")
        if cancel_token is not None and cancel_token.is_cancelled:
            return

        if final.finish_reason == "length":
            yield ReportError(
                report_id=report_id,
                error_class="OutputLimitReached",
                message=(
                    f"Model output limit reached (max_output_tokens="
                    f"{writing_max_tokens}, model={resolved.model_ref}). "
                    "Pick a model with a larger output cap from the "
                    "department's model picker, or reduce enabled sections."
                ),
            )
            return

        if validated_payload is not None:
            schema_payload = validated_payload
        else:
            schema_payload = _extract_writing_payload(final)
            if schema_payload is None:
                preview = _unicode_safe_truncate((final.text or "").strip(), max_len=200)
                self._trace(
                    "report.error",
                    "writing turn returned no submit_report tool_use",
                    {"report_id": report_id, "preview": preview},
                )
                yield ReportError(
                    report_id=report_id,
                    error_class="RuntimeError",
                    message=(
                        "LLM did not call submit_report; got "
                        f"{len(final.tool_calls)} tool_calls and "
                        f"{len(final.text or '')} chars of text "
                        f"(starts with: {preview!r})"
                    ),
                )
                return

            schema_payload = _inject_server_fields(
                schema_payload,
                department_id=department_id,
                generated_at=datetime.now(UTC),
            )
            schema_payload = normalize_report(schema_payload)
            schema_payload = _apply_coercion_fallback(schema_payload)
            _merge_provider_citations(schema_payload, provider_citations)
            schema_payload["meta_stats"] = _build_meta_stats(
                schema_payload,
                model_id=resolved.model_ref,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                web_search_count=web_search_count,
            )
            self._trace(
                "report.coercion_applied",
                "strict validation exhausted; coercion fallback applied",
                {
                    "report_id": report_id,
                    "sections": len(schema_payload.get("sections") or []),
                },
            )

        for section in schema_payload.get("sections", []) or []:
            yield ReportSectionComplete(
                report_id=report_id,
                section_id=str(section.get("id", "")),
                blocks=list(section.get("blocks", []) or []),
            )

        self._trace(
            "report.complete",
            f"report complete sections={len(schema_payload.get('sections') or [])}",
            {
                "report_id": report_id,
                "sections": len(schema_payload.get("sections") or []),
            },
        )
        yield ReportComplete(
            report_id=report_id,
            schema=schema_payload,
            web_search_count=web_search_count,
            web_search_provider_breakdown=dict(web_search_provider_breakdown),
            web_search_rescues=web_search_rescues,
        )

    @staticmethod
    async def _await(awaitable, *, cancel_token: CancellationToken | None):
        if cancel_token is None:
            return await awaitable
        return await await_with_grace(awaitable, token=cancel_token)
