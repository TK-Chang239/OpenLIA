"""SubagentReportRunner - plan + eager fetch + subagents + editor.

This file ships in vertical slices: Task 12 implements the planning
phase only. Tasks 13-15 add eager fetch, section drafting, and the
editor pass.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.events import (
    ReportError,
    ReportPhase,
    ReportStart,
    SseEvent,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.plan_schema import DataPath, ReportPlan
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ToolSchema,
)

PLAN_REPORT_TOOL_NAME = "plan_report"


ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


def _plan_report_tool() -> ToolSchema:
    return ToolSchema(
        name=PLAN_REPORT_TOOL_NAME,
        description=(
            "Emit the report plan. Call exactly once with a ReportPlan: "
            "company_thesis, cross_section_themes (2-4), sections."
        ),
        parameters=ReportPlan.model_json_schema(),
    )


def _force_plan_choice(provider_kind: str) -> dict[str, Any]:
    if provider_kind == "anthropic":
        return {"type": "tool", "name": PLAN_REPORT_TOOL_NAME}
    if provider_kind == "gemini":
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [PLAN_REPORT_TOOL_NAME],
            }
        }
    return {"type": "function", "function": {"name": PLAN_REPORT_TOOL_NAME}}


def _default_frameworks_root() -> Path:
    return Path(str(resources.files("openlia.reports.frameworks")))


def _load_framework(frameworks_root: Path, mode: str) -> dict[str, Any]:
    path = frameworks_root / f"{mode}.json"
    return json.loads(path.read_text())


def _load_style_guide(frameworks_root: Path, mode: str) -> str:
    path = frameworks_root / f"{mode}_style_guide.md"
    return path.read_text() if path.exists() else ""


def _framework_summary(framework: dict[str, Any]) -> str:
    sections = framework.get("sections", []) or []
    lines = [f"- {s.get('id')}: {s.get('title')}" for s in sections]
    return "Sections (render order):\n" + "\n".join(lines)


def _section_ids_in_framework(framework: dict[str, Any]) -> set[str]:
    return {str(s.get("id")) for s in (framework.get("sections") or [])}


def _section_titles(framework: dict[str, Any]) -> list[str]:
    return [str(s.get("title", "")) for s in (framework.get("sections") or [])]


class SubagentReportRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        tools: ToolDispatcher,
        resolve: ResolveFn,
        registry: Any,
        flagship_provider_factory: ProviderFactory,
        subagent_provider_factory: ProviderFactory,
        report_id_factory: Callable[[], str] | None = None,
        frameworks_root: Path | None = None,
        plan_repair_turns: int = 1,
    ) -> None:
        self._prompts = prompts
        self._tools = tools
        self._resolve = resolve
        self._registry = registry
        self._flagship_factory = flagship_provider_factory
        self._subagent_factory = subagent_provider_factory
        self._report_id_factory = report_id_factory or (lambda: f"r_{uuid.uuid4().hex[:12]}")
        self._frameworks_root = frameworks_root or _default_frameworks_root()
        self._plan_repair_turns = plan_repair_turns

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
    ) -> AsyncIterator[SseEvent]:
        from datetime import UTC, datetime

        from openlia.llm.runtime.editor_client import (
            EDITOR_TOOL_NAME,  # noqa: F401  -- imported for symmetry
            EditorClient,
            EditorRequest,
        )
        from openlia.llm.runtime.events import (
            ReportComplete,
            ReportSectionComplete,
        )
        from openlia.llm.runtime.prior_section_summarizer import summarize_section_draft
        from openlia.llm.runtime.report import _finalize_submit_payload
        from openlia.llm.runtime.section_draft import OpenQuestion, PriorSection, SectionDraft
        from openlia.llm.runtime.subagent_client import (
            SECTION_DRAFT_TOOL_NAME,  # noqa: F401
            SubagentClient,
            SubagentRequest,
        )
        from openlia.reports.validator import validate_report_payload

        report_id = self._report_id_factory()
        framework = _load_framework(self._frameworks_root, request.mode)
        style_guide = _load_style_guide(self._frameworks_root, request.mode)

        yield ReportStart(
            report_id=report_id,
            department=department_id,
            mode=request.mode,
            section_titles=_section_titles(framework),
        )

        yield ReportPhase(report_id=report_id, phase="planning")
        resolved_flag = self._resolve(
            department_id=department_id,
            user_id=user_id,
            registry=self._registry,
            role="flagship",
        )
        flagship = self._flagship_factory(resolved_flag)
        planning_system = self._prompts.render(
            department_id,
            "report.subagent_planning",
            style_guide=style_guide,
            framework_summary=_framework_summary(framework),
            user_input=request.user_input,
        )
        plan_or_err = await self._run_planning(
            flagship=flagship,
            system=planning_system,
            framework=framework,
        )
        if isinstance(plan_or_err, ReportError):
            yield ReportError(
                report_id=report_id,
                error_class=plan_or_err.error_class,
                message=plan_or_err.message,
            )
            return
        plan = plan_or_err

        yield ReportPhase(report_id=report_id, phase="eager_fetch")
        fetched_data = await self._eager_fetch(plan, department_id=department_id)

        yield ReportPhase(report_id=report_id, phase="section_drafting")
        resolved_sub = self._resolve(
            department_id=department_id,
            user_id=user_id,
            registry=self._registry,
            role="subagent",
        )
        subagent_provider = self._subagent_factory(resolved_sub)
        subagent = SubagentClient(provider=subagent_provider)
        prior_summaries: list[PriorSection] = []
        drafts: list[SectionDraft] = []
        sections_by_id = {s.section_id: s for s in plan.sections}
        role_prompt = (
            self._prompts.render_partial("shared/section_subagent_role.yaml.j2")
            if hasattr(self._prompts, "render_partial")
            else ""
        )
        for section in plan.sections:
            section_data = self._slice_for_section(section, fetched_data)
            req = SubagentRequest(
                role_prompt=role_prompt,
                style_guide=style_guide,
                schema_strictness="",
                company_thesis=plan.company_thesis,
                cross_section_themes=list(plan.cross_section_themes),
                this_section=section,
                fetched_data=section_data,
                prior_section_summaries=list(prior_summaries),
            )
            draft = await subagent.draft(req)
            drafts.append(draft)
            yield ReportSectionComplete(
                report_id=report_id,
                section_id=section.section_id,
                blocks=draft.blocks,
            )
            prior_summaries.append(
                summarize_section_draft(draft, title=sections_by_id[section.section_id].title)
            )

        yield ReportPhase(report_id=report_id, phase="editing")
        editor = EditorClient(provider=flagship, repair_budget=1, max_output_tokens=8192)
        open_qs: list[OpenQuestion] = [
            OpenQuestion(section_id=d.section_id, question=q)
            for d in drafts
            for q in d.open_questions
        ]
        editor_payload = await editor.compose(
            EditorRequest(
                role_prompt="",
                style_guide=style_guide,
                schema_strictness="",
                company_thesis=plan.company_thesis,
                cross_section_themes=list(plan.cross_section_themes),
                section_drafts=drafts,
                open_questions=open_qs,
                framework_cover_instructions=str(
                    framework.get("cover", {}).get("instructions", "")
                ),
            )
        )

        finalized = _finalize_submit_payload(
            editor_payload,
            department_id=department_id,
            generated_at=datetime.now(UTC),
            provider_citations=[],
            model_id=resolved_flag.model_ref,
            total_input_tokens=0,
            total_output_tokens=0,
            web_search_count=0,
        )
        validate_report_payload(finalized)
        yield ReportComplete(report_id=report_id, schema=finalized)

    async def _eager_fetch(self, plan: ReportPlan, *, department_id: str) -> dict[str, Any]:
        """Dispatch every unique tool call from the plan, resolve every
        DataPath into a flat ``{"<ref-or-tool>:<path>": value}`` map."""
        from openlia.llm.runtime.payload_path import apply_path
        from openlia.llm.types import ToolCall as _TC

        results: dict[str, Any] = {}
        unique = dedupe_data_paths(plan)
        for entry in unique:
            call = _TC(
                id=f"eager_{uuid.uuid4().hex[:6]}",
                name=entry.tool_name,
                arguments=dict(entry.tool_arguments),
            )
            res_list = await self._tools.dispatch_many(
                department_id=department_id,
                calls=[call],
            )
            res = res_list[0]
            payload = res.payload
            for dp in entry.attached:
                key = (
                    f"{entry.tool_name}"
                    f"({json.dumps(entry.tool_arguments, sort_keys=True)})"
                    f":{dp.path or ''}"
                )
                value = payload if dp.path is None else apply_path(payload, dp.path)
                results[key] = value
        return results

    def _slice_for_section(self, section: Any, fetched_data: dict[str, Any]) -> dict[str, Any]:
        slice_out: dict[str, Any] = {}
        for dp in section.data_paths:
            if dp.tool_name is None:
                continue
            key = f"{dp.tool_name}({json.dumps(dp.tool_arguments, sort_keys=True)}):{dp.path or ''}"
            if key in fetched_data:
                slice_out[key] = fetched_data[key]
        return slice_out

    async def _run_planning(
        self,
        *,
        flagship: LLMProvider,
        system: str,
        framework: dict[str, Any],
    ) -> ReportPlan | ReportError:
        tools = [_plan_report_tool()]
        tool_choice = _force_plan_choice(flagship.kind)
        messages: list[Message] = [Message(role="user", content="Plan this report now.")]
        last_err: str | None = None
        valid_section_ids = _section_ids_in_framework(framework)
        for attempt in range(self._plan_repair_turns + 1):
            response = await flagship.generate(
                LLMRequest(
                    system=system,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=4096,
                )
            )
            call = next(
                (c for c in response.tool_calls if c.name == PLAN_REPORT_TOOL_NAME),
                None,
            )
            if call is None:
                last_err = "flagship did not call plan_report"
            else:
                try:
                    plan = ReportPlan.model_validate(call.arguments)
                    # Cross-check section_ids against framework.
                    unknown = [
                        s.section_id for s in plan.sections if s.section_id not in valid_section_ids
                    ]
                    if unknown:
                        raise ValueError(f"unknown section_ids: {unknown}")
                    return plan
                except Exception as exc:
                    last_err = str(exc)
            if attempt == self._plan_repair_turns:
                break
            # Append assistant + repair tool message.
            if call is not None:
                messages.append(Message(role="assistant", content="", tool_calls=(call,)))
                messages.append(
                    Message(
                        role="tool",
                        content=json.dumps(
                            {"error": last_err, "hint": "Fix the plan and re-submit."}
                        ),
                        tool_call_id=call.id,
                    )
                )
        return ReportError(
            report_id="r_pending",
            error_class="plan_invalid",
            message=str(last_err or "plan invalid"),
        )


@dataclass
class UniqueToolCall:
    tool_name: str
    tool_arguments: dict[str, Any]
    attached: list[DataPath] = field(default_factory=list)


def dedupe_data_paths(plan: ReportPlan) -> list[UniqueToolCall]:
    """Walk every section's data_paths, dedupe by (tool_name, args),
    return one ``UniqueToolCall`` per distinct dispatch. Each entry's
    ``attached`` list holds every DataPath that wanted that ref so the
    caller can later slice the result by ``path`` and assign each subagent
    its own slice."""
    by_key: dict[tuple[str, frozenset[tuple[str, Any]]], UniqueToolCall] = {}
    for section in plan.sections:
        for dp in section.data_paths:
            if dp.tool_name is None:
                continue  # `ref`-only paths resolve against earlier dispatches
            key = (dp.tool_name, frozenset((dp.tool_arguments or {}).items()))
            entry = by_key.setdefault(
                key,
                UniqueToolCall(tool_name=dp.tool_name, tool_arguments=dp.tool_arguments or {}),
            )
            entry.attached.append(dp)
    return list(by_key.values())
