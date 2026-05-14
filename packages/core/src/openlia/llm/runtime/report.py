"""ReportRunner — single-pass structured report generation.

Flow per run():
  report.start
  → report.phase("fetching_data")
    → tool loop until the LLM returns no more tool calls
      (emit report.tool_call per dispatched tool)
  → report.phase("writing")
    → one structured-output turn (response_format=json_schema)
  → report.phase("finalizing")
  → report.complete(schema=parsed_json)

On LLMProviderError: report.error, stop.
On cancellation: stop yielding, no terminal event.
"""

from __future__ import annotations

import asyncio
import copy
import json
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
    SseEvent,
)
from openlia.llm.runtime.messages import Attachment, ContentBlock, ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import MAX_TOOL_TURNS, ToolDispatcher
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ToolSchema,
)
from openlia.reports.schema import ReportSchema
from openlia.skills import SkillRegistry

_SUBMIT_REPORT_TOOL_NAME = "submit_report"
_SUBMIT_REPORT_DESCRIPTION = (
    "Submit the final report. Call exactly once with the structured payload. "
    "Keys MUST be `cover` and `sections` matching the framework. "
    "Server fills schema_version, department, generated_at — omit them."
)


def _submit_report_input_schema() -> dict[str, Any]:
    """JSON Schema for `submit_report.arguments` derived from `ReportSchema`.

    Server-controlled meta fields (`schema_version`, `department`,
    `generated_at`) are stripped — the runner injects them post-LLM.
    """
    schema = copy.deepcopy(ReportSchema.model_json_schema())
    props = schema.get("properties", {})
    for stripped in ("schema_version", "department", "generated_at"):
        props.pop(stripped, None)
    required = schema.get("required") or []
    schema["required"] = [
        r for r in required if r not in {"schema_version", "department", "generated_at"}
    ]
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
    if provider_kind == "anthropic":
        return {"type": "tool", "name": _SUBMIT_REPORT_TOOL_NAME}
    if provider_kind == "gemini":
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [_SUBMIT_REPORT_TOOL_NAME],
            }
        }
    # OpenAI, OpenRouter, openai_compat, ollama (OpenAI-compatible) all use
    # the chat-completions tool_choice shape.
    return {"type": "function", "function": {"name": _SUBMIT_REPORT_TOOL_NAME}}


def _unicode_safe_truncate(s: str, *, max_len: int = 120) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len]


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _normalize_schema_payload(
    payload: dict[str, Any], *, department_id: str, generated_at: datetime
) -> dict[str, Any]:
    """Force server-controlled top-level fields and forgive common LLM drift.

    The strict ReportSchema requires exactly five top-level keys. Models
    sometimes wrap the payload (`{"report": {...}}`), invent meta wrappers
    (`{"report_metadata": {...}, ...}`), or simply forget meta fields.
    Strip those, hoist `cover`/`sections` if needed, and overwrite the
    server-controlled fields.
    """
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

    payload["schema_version"] = "2.0"
    payload["department"] = department_id
    payload["generated_at"] = generated_at.isoformat()
    payload.setdefault("cover", {})
    payload.setdefault("sections", [])

    cover = payload["cover"] if isinstance(payload["cover"], dict) else {}
    _coerce_metric_list(cover.get("key_metrics"))
    cover.pop("stats_panel", None)
    rail = payload.get("rail")
    if isinstance(rail, dict):
        _coerce_metric_list(rail.get("quick_stats"))
    sections = payload["sections"] if isinstance(payload["sections"], list) else []
    for section in sections:
        if isinstance(section, dict):
            _coerce_blocks(section.get("blocks"))
    return payload


def _coerce_metric_value(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    return v


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
    loader: PromptLoader | None = None,
) -> str:
    """Render the report.system slot with the user's visible skills menu."""
    loader = loader or PromptLoader()
    visible = registry.visible(department_id=department_id, user_id=user_id)
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
        department_id, "report.system", style_guide=style_guide, skills_menu=skills_menu
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
    ) -> AsyncIterator[SseEvent]:
        report_id = self._report_id_factory()

        using_user_template = bool(request.user_template_text)
        if using_user_template:
            framework: dict[str, Any] = {"sections": [], "length_preference": request.length}
            style_guide = ""
        else:
            framework_raw = _load_framework(self._frameworks_root, request.mode)
            framework = _customize_framework(framework_raw, request)
            style_guide = _load_style_guide(self._frameworks_root, request.mode)

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

        system = build_report_system_prompt(
            department_id=department_id,
            user_id=user_id,
            registry=self._skill_registry,
            style_guide=style_guide,
            loader=self._prompts,
        )
        tools = await self._tools.build(department_id, has_web_search=True)
        now = datetime.now(UTC)
        current_date = now.date().isoformat()
        current_date_long = f"{now.strftime('%A')}, {now.strftime('%B')} {now.day}, {now.year}"
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

        for turn_idx in range(MAX_TOOL_TURNS) if tools else range(0):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            self._trace(
                "llm.call.start",
                f"tool turn {turn_idx} (tools={len(tools or [])})",
                {"report_id": report_id, "phase": "fetching_data", "turn": turn_idx},
            )
            try:
                response = await self._await(
                    provider.generate(
                        LLMRequest(
                            messages=conversation,
                            system=system,
                            tools=tools or None,
                            max_tokens=2048,
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
            self._trace(
                "llm.call.done",
                f"tool turn {turn_idx} done tool_calls={len(response.tool_calls)}",
                {
                    "report_id": report_id,
                    "turn": turn_idx,
                    "tool_calls": [c.name for c in response.tool_calls],
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
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
            tools = await self._tools.build(department_id, has_web_search=True)

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
        self._trace(
            "llm.call.start",
            f"writing turn max_tokens={writing_max_tokens} (forced submit_report)",
            {"report_id": report_id, "phase": "writing", "max_tokens": writing_max_tokens},
        )
        try:
            final = await self._await(
                provider.generate(
                    LLMRequest(
                        messages=conversation,
                        system=system,
                        tools=[submit_tool],
                        tool_choice=submit_choice,
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
                {"report_id": report_id, "error_class": type(exc).__name__},
            )
            yield ReportError(
                report_id=report_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return
        self._trace(
            "llm.call.done",
            f"writing turn done tool_calls={len(final.tool_calls)}",
            {
                "report_id": report_id,
                "phase": "writing",
                "input_tokens": final.input_tokens,
                "output_tokens": final.output_tokens,
                "finish_reason": final.finish_reason,
                "tool_call_names": [c.name for c in final.tool_calls],
                "text_preview": _unicode_safe_truncate(final.text or "", max_len=200),
            },
        )

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
                    f"{len(final.tool_calls)} tool_calls and {len(final.text or '')} chars of text "
                    f"(starts with: {preview!r})"
                ),
            )
            return

        schema_payload = _normalize_schema_payload(
            schema_payload,
            department_id=department_id,
            generated_at=datetime.now(UTC),
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
        yield ReportComplete(report_id=report_id, schema=schema_payload)

    @staticmethod
    async def _await(awaitable, *, cancel_token: CancellationToken | None):
        if cancel_token is None:
            return await awaitable
        return await await_with_grace(awaitable, token=cancel_token)
