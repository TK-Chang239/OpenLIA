"""SubagentReportRunner - plan + eager fetch + subagents + editor.

This file ships in vertical slices: Task 12 implements the planning
phase only. Tasks 13-15 add eager fetch, section drafting, and the
editor pass.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable
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
from openlia.llm.runtime.plan_schema import ReportPlan
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

        # Resolve flagship for planning.
        resolved = self._resolve(
            department_id=department_id,
            user_id=user_id,
            registry=self._registry,
            role="flagship",
        )
        flagship = self._flagship_factory(resolved)

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
            yield plan_or_err
            return

        # Plan validated. Eager fetch + drafting + editing land in later tasks.
        # For now: this slice ends after planning.
        return

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
