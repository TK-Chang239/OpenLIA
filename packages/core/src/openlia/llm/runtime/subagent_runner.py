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

import openlia.prompts as _prompts_pkg
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


def load_section_subagent_role() -> str:
    p = Path(_prompts_pkg.__file__).parent / "shared" / "section_subagent_role.yaml.j2"
    return p.read_text()


def load_editor_role() -> str:
    p = Path(_prompts_pkg.__file__).parent / "shared" / "editor_role.yaml.j2"
    return p.read_text()


def _load_schema_strictness() -> str:
    p = Path(_prompts_pkg.__file__).parent / "shared" / "report_schema_strictness.yaml.j2"
    return p.read_text() if p.exists() else ""


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
    """Render the framework's section list with per-section instructions
    so the flagship planner has enough context to write a real plan
    rather than emitting empty arguments. Earlier versions returned only
    `<id>: <title>` pairs; the planner then truncated mid-tool-call on
    every run because the prompt didn't give it enough substance to
    anchor the plan for len(template.sections) sections."""
    sections = framework.get("sections", []) or []
    lines: list[str] = ["Sections (render order):"]
    for s in sections:
        sid = s.get("id")
        title = s.get("title")
        instr = (s.get("instructions") or "").strip()
        if instr:
            lines.append(f"- {sid} ({title}): {instr}")
        else:
            lines.append(f"- {sid}: {title}")
    return "\n".join(lines)


def _section_ids_in_framework(framework: dict[str, Any]) -> set[str]:
    return {str(s.get("id")) for s in (framework.get("sections") or [])}


def _section_titles(framework: dict[str, Any]) -> list[str]:
    return [str(s.get("title", "")) for s in (framework.get("sections") or [])]


TraceFn = Callable[[str, str, "dict[str, Any] | None"], None]


def _threading_caps_from_request(request: Any) -> tuple[int | None, int | None]:
    """Return (summary_word_cap, facts_cap) from framework_template_spec, or (None, None).

    Carry-over wiring from PR 0.0: makes summarize_section_draft honour the
    threading block declared in the template YAML.
    Returns (None, None) when no spec / no threading block (uses function defaults).
    """
    spec_dict = getattr(request, "framework_template_spec", None)
    if not isinstance(spec_dict, dict):
        return None, None
    try:
        from openlia.llm.runtime.report_v2.template_v2.spec import TemplateSpecV2

        spec = TemplateSpecV2.model_validate(spec_dict)
        t = spec.threading
        if t is None:
            return None, None
        return t.summary_word_cap, t.facts_cap
    except (ValueError, TypeError, KeyError, AttributeError, LookupError):
        # Narrowed from bare Exception: malformed spec must never crash the runner.
        return None, None


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
        trace: TraceFn | None = None,
        bundle_dir: Path | None = None,
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
        self._trace: TraceFn = trace or (lambda *a: None)
        self._bundle_dir: Path = (
            bundle_dir if bundle_dir is not None else (Path.home() / ".openlia" / "report_bundles")
        )

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
        cancel_token: Any = None,
        attachments: Any = None,
        model_id_override: str | None = None,
        disabled_skill_ids: frozenset[str] | tuple[str, ...] = (),
        language: str | None = None,
    ) -> AsyncIterator[SseEvent]:
        # SubagentReportRunner accepts the same call surface as the classic
        # ReportRunner so the server's RefreshingReportRunner can drop in
        # either runner without branching on call style. Honored:
        #   - cancel_token: checked at phase boundaries; full mid-LLM
        #     cancellation is a v2 concern.
        # Accepted-but-ignored (v1):
        #   - attachments: subagent runner uses planned eager fetch, not
        #     user-attached docs. Wire-through is a follow-up.
        #   - model_id_override: subagent runner reads from per-role
        #     resolver. Override semantics for a two-role pipeline need a
        #     design call; treated as a future enhancement.
        #   - disabled_skill_ids: subagents have no tools, so skills don't
        #     apply. Ignored.
        del attachments, model_id_override, disabled_skill_ids
        # ``language`` is accepted for call-shape parity with v2 / ReportRunner
        # but the SubagentReportRunner doesn't yet rethread it into the planner
        # or section-writer prompts. Treated as a no-op for now.
        del language

        def _cancelled() -> bool:
            return cancel_token is not None and getattr(cancel_token, "is_cancelled", False)

        from datetime import UTC, datetime

        from openlia.llm.runtime.editor_client import (
            EDITOR_TOOL_NAME,
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
            SECTION_DRAFT_TOOL_NAME,
            SubagentClient,
            SubagentRequest,
        )
        from openlia.reports.validator import validate_report_payload

        report_id = self._report_id_factory()
        framework = _load_framework(self._frameworks_root, request.mode)
        style_guide = _load_style_guide(self._frameworks_root, request.mode)
        _summary_word_cap, _facts_cap = _threading_caps_from_request(request)

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
            report_id=report_id,
        )
        if isinstance(plan_or_err, ReportError):
            yield ReportError(
                report_id=report_id,
                error_class=plan_or_err.error_class,
                message=plan_or_err.message,
            )
            return
        plan = plan_or_err

        if _cancelled():
            yield ReportError(report_id=report_id, error_class="cancelled", message="cancelled")
            return

        yield ReportPhase(report_id=report_id, phase="eager_fetch")
        fetched_data = await self._eager_fetch(plan, department_id=department_id)

        if _cancelled():
            yield ReportError(report_id=report_id, error_class="cancelled", message="cancelled")
            return

        yield ReportPhase(report_id=report_id, phase="section_drafting")
        resolved_sub = self._resolve(
            department_id=department_id,
            user_id=user_id,
            registry=self._registry,
            role="subagent",
        )
        subagent_provider = self._subagent_factory(resolved_sub)

        def _subagent_on_done(resp: Any) -> None:
            self._trace(
                "llm.call.done",
                f"drafting ({SECTION_DRAFT_TOOL_NAME})",
                {
                    "report_id": report_id,
                    "phase": "drafting",
                    "input_tokens": resp.input_tokens,
                    "output_tokens": resp.output_tokens,
                    "cached_input_tokens": resp.cached_input_tokens,
                },
            )

        subagent = SubagentClient(
            provider=subagent_provider,
            reprompt_budget=2,  # mini-model needs 2 reprompts to land schema
            on_done=_subagent_on_done,
        )
        prior_summaries: list[PriorSection] = []
        drafts: list[SectionDraft] = []
        sections_by_id = {s.section_id: s for s in plan.sections}
        subagent_role = load_section_subagent_role()
        schema_strictness = _load_schema_strictness()
        for section in plan.sections:
            if _cancelled():
                yield ReportError(report_id=report_id, error_class="cancelled", message="cancelled")
                return
            section_data = self._slice_for_section(section, fetched_data)
            req = SubagentRequest(
                role_prompt=subagent_role,
                style_guide=style_guide,
                schema_strictness=schema_strictness,
                company_thesis=plan.company_thesis,
                cross_section_themes=list(plan.cross_section_themes),
                this_section=section,
                fetched_data=section_data,
                prior_section_summaries=list(prior_summaries),
            )
            try:
                draft = await subagent.draft(req)
            except Exception as exc:
                # Subagent exhausted retry budget without producing a
                # valid SectionDraft. Substitute a placeholder so the
                # report can still complete and the editor can paper over
                # the gap rather than the whole run failing.
                self._trace(
                    "report.warning.subagent_failed",
                    f"section {section.section_id} subagent failed: {exc!s}",
                    {"report_id": report_id, "section_id": section.section_id},
                )
                draft = SectionDraft.model_validate(
                    {
                        "section_id": section.section_id,
                        "blocks": [
                            {
                                "type": "text",
                                "content": (
                                    "Section narrative could not be produced "
                                    "by the section writer (subagent error). "
                                    "Available data for this section is "
                                    "described below in tables/charts if any."
                                ),
                            }
                        ],
                        "citations_used": [],
                        "word_count": 28,
                        "open_questions": [
                            f"subagent failed to render {section.section_id}: {exc!s}"
                        ],
                    }
                )
            drafts.append(draft)
            yield ReportSectionComplete(
                report_id=report_id,
                section_id=section.section_id,
                blocks=draft.blocks,
            )
            _summarize_kwargs: dict[str, Any] = {
                "title": sections_by_id[section.section_id].title,
            }
            if _summary_word_cap is not None:
                _summarize_kwargs["summary_word_cap"] = _summary_word_cap
            if _facts_cap is not None:
                _summarize_kwargs["facts_cap"] = _facts_cap
            prior_summaries.append(summarize_section_draft(draft, **_summarize_kwargs))

        if _cancelled():
            yield ReportError(report_id=report_id, error_class="cancelled", message="cancelled")
            return

        yield ReportPhase(report_id=report_id, phase="editing")

        def _editor_on_done(resp: Any) -> None:
            self._trace(
                "llm.call.done",
                f"editing ({EDITOR_TOOL_NAME})",
                {
                    "report_id": report_id,
                    "phase": "editing",
                    "input_tokens": resp.input_tokens,
                    "output_tokens": resp.output_tokens,
                    "cached_input_tokens": resp.cached_input_tokens,
                },
            )

        editor = EditorClient(
            provider=flagship,
            repair_budget=1,
            # Templates with many sections, plus cover + rail + citations,
            # can easily exceed 8192 tokens in JSON. iter9 hit the cap and
            # lost cover.title/etc, failing strict validation. 32768 gives
            # substantial headroom for the full report plus model reasoning
            # before tool call.
            max_output_tokens=32768,
            on_done=_editor_on_done,
        )
        open_qs: list[OpenQuestion] = [
            OpenQuestion(section_id=d.section_id, question=q)
            for d in drafts
            for q in d.open_questions
        ]
        editor_payload = await editor.compose(
            EditorRequest(
                role_prompt=load_editor_role(),
                style_guide=style_guide,
                schema_strictness=schema_strictness,
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

        from openlia.llm.runtime.report_context_bundle import (
            ReportContextBundle,
            persist_bundle,
        )

        # Persist the report context bundle for chat follow-ups.
        bundle_path = self._bundle_dir / f"{report_id}.json.gz"
        try:
            truncated = persist_bundle(
                ReportContextBundle(
                    plan=plan,
                    fetched_data=fetched_data,
                    section_drafts=drafts,
                    payload_refs={},  # Task 14 wires the eager-fetch ref store here when available
                    generation_meta={
                        "model_id": resolved_flag.model_ref,
                        "total_input_tokens": 0,  # Task 16 wires real totals
                        "total_output_tokens": 0,
                        "web_search_count": 0,
                        "schema_version": "1.0",
                    },
                ),
                path=bundle_path,
            )
            if truncated:
                self._trace(
                    "report.warning.bundle_truncated",
                    f"dropped {len(truncated)} payload_refs to fit cap",
                    {"report_id": report_id, "dropped_keys": truncated},
                )
        except Exception as exc:
            self._trace(
                "report.warning.bundle_persist_failed",
                f"failed to write bundle: {exc!s}",
                {"report_id": report_id, "error": str(exc)},
            )

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
            # ToolDispatcher externalizes large payloads into its
            # _payload_store, returning a stub with a `ref` field instead
            # of raw data. The classic ReportRunner reads through stubs
            # via read_payload tool calls. The subagent runner has no
            # tools — it needs the raw payload to slice. If the result is
            # a stub, read the full payload directly from the store.
            if (
                isinstance(payload, dict)
                and "ref" in payload
                and payload.get("ref")
                and hasattr(self._tools, "_payload_store")
                and payload["ref"] in self._tools._payload_store
            ):
                payload = self._tools._payload_store[payload["ref"]]
            for dp in entry.attached:
                key = (
                    f"{entry.tool_name}"
                    f"({json.dumps(entry.tool_arguments, sort_keys=True)})"
                    f":{dp.path or ''}"
                )
                try:
                    value = payload if dp.path is None else apply_path(payload, dp.path)
                except Exception as exc:
                    # apply_path raises PathResolveError if the key is
                    # missing. The plan may declare paths that don't
                    # exist in the actual payload (e.g., framework
                    # changed, vendor returned different shape).
                    # Substitute a small marker dict so the subagent
                    # sees the data was attempted but unavailable rather
                    # than the run dying with an opaque KeyError.
                    self._trace(
                        "report.warning.eager_fetch_slice_failed",
                        f"path {dp.path!r} not in payload: {exc!s}",
                        {
                            "tool": entry.tool_name,
                            "path": dp.path,
                            "purpose": dp.purpose,
                        },
                    )
                    value = {
                        "_unavailable": True,
                        "_reason": f"path {dp.path!r} not in payload",
                    }
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
        report_id: str,
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
                    # Planning produces one SectionPlan per template section + thesis + themes; the
                    # JSON shape needs ~3-5k tokens minimum, plus the model
                    # consumes meaningful reasoning budget before emitting. The
                    # iter-3 run with cap=4096 returned empty {} args twice
                    # because the response was truncated mid-tool-call. 16384
                    # gives substantial headroom for reasoning + structured
                    # output.
                    max_tokens=16384,
                )
            )
            self._trace(
                "llm.call.done",
                f"planning ({PLAN_REPORT_TOOL_NAME})",
                {
                    "report_id": report_id,
                    "phase": "planning",
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cached_input_tokens": response.cached_input_tokens,
                },
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
            # tool_arguments can hold list / dict values; JSON-serialize with
            # sorted keys for a hashable, deterministic dedup key. The earlier
            # frozenset(items()) approach blew up on list values
            # ("unhashable type: 'list'").
            key = (
                dp.tool_name,
                json.dumps(dp.tool_arguments or {}, sort_keys=True, default=str),
            )
            entry = by_key.setdefault(
                key,
                UniqueToolCall(tool_name=dp.tool_name, tool_arguments=dp.tool_arguments or {}),
            )
            entry.attached.append(dp)
    return list(by_key.values())
