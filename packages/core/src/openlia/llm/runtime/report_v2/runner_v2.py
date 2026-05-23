"""Runner for the v2.2 9-stage pipeline.

`RunnerV2.execute()` is a generator that drives stages 1 → 9 in order and
yields ``RunEvent`` values at every transition. The generator pauses at
stage 1 if the Clarifier returns blocking warnings, in which case the
caller is expected to persist the emitted ``ClarifierPaused`` event,
collect user answers, and call ``execute()`` again with ``resume_state``
populated to pick up at stage 3.

The orchestrator does NOT speak HTTP/SSE — those translations live in
the server's route handler. This module's only contract is the event
stream.

See docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md §2.

v2.2 extension: if ``planner_v2_2_llm`` is injected at construction, two
extra stages are activated:

  Stage 5b — PLANNER_V2_2: constructs a fresh ``Planner`` using the
      per-run ticker (from ``composer_inputs``) and template sections
      (from ``template_spec``), calls ``planner.aplan()`` (async, no
      deadlock risk), and stores the resulting ``PlannerOutput``.

  Stage 7a — MATERIALIZE: resolves each ``HelperInvocation`` in the
      PlannerOutput to a registered helper, invokes it, collects artifacts
      into a dict, runs ``resolve_section_plan`` + ``materialize()``, and
      stores the resulting ``MaterializedReport`` for Stage 7b.

When ``planner_v2_2_llm is None`` both extra stages are silently skipped
so existing v2 pipelines continue to work without change.

The Planner is constructed fresh per-run (not stored on the RunnerV2
instance) so no per-run state (ticker, template sections) leaks between
concurrent reports.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from openlia.llm.runtime.report_v2.capability_manifest import load_manifest
from openlia.llm.runtime.report_v2.pipeline.stage_1_clarify import Clarifier
from openlia.llm.runtime.report_v2.pipeline.stage_3_research_plan import (
    ResearchPlanner,
)
from openlia.llm.runtime.report_v2.pipeline.stage_4_gather import StrandDispatcher
from openlia.llm.runtime.report_v2.pipeline.stage_5_model_plan import ModelPlanner
from openlia.llm.runtime.report_v2.pipeline.stage_6_model_build import ModelBuilder
from openlia.llm.runtime.report_v2.pipeline.stage_7_draft import (
    SectionDrafter,
    SectionOutput,
)
from openlia.llm.runtime.report_v2.pipeline.stage_8_verify import (
    SectionVerificationResult,
    Verifier,
)
from openlia.llm.runtime.report_v2.pipeline.stage_9_assemble import (
    build_report_v2,
)
from openlia.llm.runtime.report_v2.schemas.clarifier import ClarifierOutput
from openlia.llm.runtime.report_v2.schemas.report_v2 import ReportV2
from openlia.llm.runtime.report_v2.schemas.run_summary import (
    RunSummary,
    TaskOutcome,
)
from openlia.llm.runtime.report_v2.schemas.verification_history import (
    VerificationHistory,
    VerificationHistoryEntry,
)


class PipelineStage(StrEnum):
    CLARIFY = "clarify"
    READ_TEMPLATE = "read_template"
    RESEARCH_PLAN = "research_plan"
    GATHER = "gather"
    MODEL_PLAN = "model_plan"
    PLANNER_V2_2 = "stage_5b_planner_v2_2"
    MODEL_BUILD = "model_build"
    MATERIALIZE = "stage_7a_materialize"
    DRAFT = "draft"
    VERIFY = "verify"
    ASSEMBLE = "assemble"


class RunState(StrEnum):
    STARTED = "STARTED"
    CLARIFY_AWAITING_USER = "CLARIFY_AWAITING_USER"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Event types yielded by execute()
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageStarted:
    stage: PipelineStage


@dataclass(frozen=True)
class StageCompleted:
    stage: PipelineStage


@dataclass(frozen=True)
class ResumeState:
    """Carries the user's clarifier answers + prior history for a resumed run.

    Constructed by the caller from a persisted ClarifierPaused event plus the
    user's submitted answers. Passed back into execute() to skip Stage 1 and
    enter at Stage 3 (research planning).
    """

    clarification_history: list[ClarifierOutput]
    answers: dict[str, Any]


@dataclass(frozen=True)
class ClarifierPaused:
    output: ClarifierOutput
    round: int
    clarification_history: list[ClarifierOutput]


@dataclass(frozen=True)
class Completed:
    """Final event of a successful v2.2 run.

    Carries the structured ReportV2 payload (typed cover/sections/citations/
    run_summary/verification_history). The route persists it as JSON on
    the pipeline_runs row and forwards it to the frontend on the SSE
    `completed` event so React renders through the v1 ReportRenderer.
    """

    report: ReportV2


@dataclass(frozen=True)
class Failed:
    stage: PipelineStage
    reason: str


RunEvent = StageStarted | StageCompleted | ClarifierPaused | Completed | Failed


# ---------------------------------------------------------------------------
# RunnerV2
# ---------------------------------------------------------------------------


@dataclass
class RunnerV2:
    """Orchestrates the 9-stage v2.2 pipeline as a generator of events.

    Stage objects are injected at construction so this class is fully
    testable with mocks. Production wiring lives in the server layer and is
    expected to construct each stage with the appropriate LLM client.

    All stage fields default to None so the existing skeleton tests
    (RunnerV2() with no args) keep working; execute() raises a clear error
    if any required stage is missing when invoked.

    Optional v2.2 extension:
        planner_v2_2_llm: An ``LLMProvider`` used to construct a fresh
            ``Planner`` per-run. When set, Stage 5b (helper selection) and
            Stage 7a (materialization) are activated. When None (default),
            both stages are silently skipped for full backwards compatibility
            with existing v2 tests and routes. The Planner is constructed
            inside ``_stage_planner_v2_2()`` using the per-run ticker and
            template sections — no shared mutable state across requests.
    """

    clarifier: Clarifier | None = None
    research_planner: ResearchPlanner | None = None
    strand_dispatcher: StrandDispatcher | None = None
    model_planner: ModelPlanner | None = None
    model_builder: ModelBuilder | None = None
    section_drafter: SectionDrafter | None = None
    verifier: Verifier | None = None
    # v2.2 extension: an LLMProvider used to construct a fresh Planner per-run.
    # Typed Any to avoid a hard import of report_v2_2 in this module (keeps the
    # v2 package self-contained). When None, Stage 5b + 7a are silently skipped.
    planner_v2_2_llm: Any | None = None

    state: RunState = RunState.STARTED
    current_stage: PipelineStage | None = None
    outcomes: list[TaskOutcome] = field(default_factory=list)

    def _require_stages(self) -> None:
        missing = [
            name
            for name in (
                "clarifier",
                "research_planner",
                "strand_dispatcher",
                "model_planner",
                "model_builder",
                "section_drafter",
                "verifier",
            )
            if getattr(self, name) is None
        ]
        if missing:
            raise RuntimeError(f"RunnerV2.execute() requires injected stages: missing {missing}")

    def execute(
        self,
        composer_inputs: dict[str, Any],
        template_spec: Any,
        *,
        resume_state: ResumeState | None = None,
    ) -> Iterator[RunEvent]:
        """Run the pipeline, yielding events at each stage transition.

        Args:
            composer_inputs: User-supplied report parameters (ticker, prompt,
                etc.). Required on both initial and resumed runs.
            template_spec: Loaded ``TemplateSpecV2``. Required on both
                initial and resumed runs.
            resume_state: When set, skips Stage 1 (Clarifier) and enters at
                Stage 3 carrying the supplied answers. When None, the run
                starts fresh from Stage 1 and may pause if the Clarifier
                surfaces blocking warnings.

        Yields:
            RunEvent values in pipeline order. Terminates on ``Completed``,
            ``Failed``, or ``ClarifierPaused`` (in which case the caller is
            expected to persist state and re-invoke execute() with
            ``resume_state``).
        """
        self._require_stages()
        self.state = RunState.RUNNING

        try:
            if resume_state is None:
                clarifier_answers, paused = yield from self._stage_clarify(
                    composer_inputs, template_spec
                )
                if paused:
                    return
            else:
                clarifier_answers = resume_state.answers

            plan = yield from self._stage_research_plan(
                composer_inputs, template_spec, clarifier_answers
            )

            research_pool = yield from self._stage_gather(plan, composer_inputs)

            plan = yield from self._stage_model_plan(plan, research_pool)

            # Stage 5b: v2.2 Planner (helper selection). Skipped when
            # planner_v2_2_llm is None (backwards-compatible v2 path).
            planner_output: Any | None = None
            if self.planner_v2_2_llm is not None:
                planner_output = yield from self._stage_planner_v2_2(composer_inputs, template_spec)

            model_artifacts = yield from self._stage_model_build(plan, research_pool)

            # Stage 7a: materialization. Skipped when no planner_output.
            materialized_report: Any | None = None
            if planner_output is not None:
                materialized_report = yield from self._stage_materialize(
                    template_spec, planner_output, model_artifacts, composer_inputs
                )

            section_outputs = yield from self._stage_draft(
                template_spec,
                plan,
                composer_inputs,
                research_pool,
                model_artifacts,
                materialized_report=materialized_report,
            )

            section_outputs, verification_history = yield from self._stage_verify(
                template_spec=template_spec,
                plan=plan,
                section_outputs=section_outputs,
                research_pool=research_pool,
                model_artifacts=model_artifacts,
                composer_inputs=composer_inputs,
            )

            report = yield from self._stage_assemble(
                template_spec,
                section_outputs,
                research_pool,
                verification_history,
                composer_inputs,
            )

            # Preserve DEGRADED if any section failed; otherwise mark COMPLETED.
            if self.state != RunState.DEGRADED:
                self.state = RunState.COMPLETED
            yield Completed(report=report)
        except Exception as exc:
            stage = self.current_stage or PipelineStage.CLARIFY
            self.state = RunState.FAILED
            yield Failed(stage=stage, reason=str(exc))

    # ------------------------------------------------------------------ stages

    def _stage_clarify(
        self,
        composer_inputs: dict[str, Any],
        template_spec: Any,
    ) -> Iterator[RunEvent]:
        self.current_stage = PipelineStage.CLARIFY
        yield StageStarted(PipelineStage.CLARIFY)
        clarifier_out = self.clarifier.clarify(composer_inputs, template_spec)
        yield StageCompleted(PipelineStage.CLARIFY)

        if clarifier_out.blocking_warnings:
            self.state = RunState.CLARIFY_AWAITING_USER
            history = [clarifier_out]
            yield ClarifierPaused(
                output=clarifier_out,
                round=1,
                clarification_history=history,
            )
            return ({}, True)

        return ({}, False)

    def _stage_research_plan(
        self,
        composer_inputs: dict[str, Any],
        template_spec: Any,
        clarifier_answers: dict[str, Any],
    ) -> Iterator[RunEvent]:
        self.current_stage = PipelineStage.RESEARCH_PLAN
        yield StageStarted(PipelineStage.RESEARCH_PLAN)
        plan = self.research_planner.plan(
            composer_inputs=composer_inputs,
            template_spec=template_spec,
            clarifier_answers=clarifier_answers,
        )
        yield StageCompleted(PipelineStage.RESEARCH_PLAN)
        return plan

    def _stage_gather(self, plan: Any, composer_inputs: dict[str, Any]) -> Iterator[RunEvent]:
        self.current_stage = PipelineStage.GATHER
        yield StageStarted(PipelineStage.GATHER)
        research_pool = self.strand_dispatcher.dispatch(
            strands=plan.research_strands,
            composer_inputs=composer_inputs,
            plan=plan,
        )
        yield StageCompleted(PipelineStage.GATHER)
        return research_pool

    def _stage_model_plan(self, plan: Any, research_pool: Any) -> Iterator[RunEvent]:
        self.current_stage = PipelineStage.MODEL_PLAN
        yield StageStarted(PipelineStage.MODEL_PLAN)
        updated = self.model_planner.plan(plan=plan, research_pool=research_pool)
        yield StageCompleted(PipelineStage.MODEL_PLAN)
        return updated

    def _stage_planner_v2_2(
        self,
        composer_inputs: dict[str, Any],
        template_spec: Any,
    ) -> Iterator[RunEvent]:
        """Stage 5b: v2.2 Planner — helper selection and planner overrides.

        Constructs a fresh ``Planner`` per-run using:
          - ``planner_v2_2_llm`` injected at RunnerV2 construction
          - ``ticker`` from ``composer_inputs``
          - ``template_sections`` derived from ``template_spec.sections``
          - ``available_helpers`` from ``list_helpers()``

        This avoids storing a stateful Planner instance on RunnerV2 (no shared
        mutable state across concurrent requests).

        Calls ``planner.aplan()`` via the ThreadPoolExecutor guard so it is
        safe to call from both sync and async contexts (no bare asyncio.run).
        Returns the ``PlannerOutput`` for Stage 7a.
        """
        from openlia.llm.runtime.report_v2_2.planner import Planner, sections_from_spec
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import list_helpers

        self.current_stage = PipelineStage.PLANNER_V2_2
        yield StageStarted(PipelineStage.PLANNER_V2_2)

        ticker: str = composer_inputs.get("ticker", "")
        template_id: str = getattr(template_spec, "template_id", "stock_initiation_v2")
        template_sections = sections_from_spec(template_spec)
        available_helpers = [
            {
                "name": h.schema.directory.name,
                "category": h.schema.directory.category.value,
                "one_liner": h.schema.directory.one_liner,
            }
            for h in list_helpers()
        ]

        planner = Planner(
            llm=self.planner_v2_2_llm,
            ticker=ticker,
            template_sections=template_sections,
            available_helpers=available_helpers,
            template_id=template_id,
        )

        # Use the same ThreadPoolExecutor guard as v2_stage_factory._run_sync:
        # this avoids the asyncio.run-inside-running-loop deadlock (A-2).
        try:
            asyncio.get_running_loop()
            # Running inside an event loop — dispatch to a worker thread.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                planner_output = ex.submit(asyncio.run, planner.aplan()).result()
        except RuntimeError:
            # No running loop — safe to call asyncio.run directly.
            planner_output = asyncio.run(planner.aplan())

        yield StageCompleted(PipelineStage.PLANNER_V2_2)
        return planner_output

    def _stage_materialize(
        self,
        template_spec: Any,
        planner_output: Any,
        model_artifacts: list,
        composer_inputs: dict[str, Any],
    ) -> Iterator[RunEvent]:
        """Stage 7a: materialize helpers and render artifacts.

        For each HelperInvocation in planner_output.helper_selection:
          1. Resolve helper name via get_helper().
          2. Emit HELPER_UNAVAILABLE VerifierIssue and skip on miss (A-7).
          3. Invoke helper impl(**inv.params) and collect output keyed by
             inv.artifact_id.
        Then resolve the section plan and call materialize() to produce a
        MaterializedReport used by Stage 7b's build_drafter_prompt().
        """
        from openlia.llm.runtime.report_v2_2.enums import VerifierIssueType
        from openlia.llm.runtime.report_v2_2.materialize import (
            MaterializationError,
            MaterializedReport,
            materialize,
            resolve_section_plan,
        )
        from openlia.llm.runtime.report_v2_2.template_defaults import load_template_defaults
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper
        from openlia.llm.runtime.report_v2_2.verifier_models import VerifierIssue

        self.current_stage = PipelineStage.MATERIALIZE
        yield StageStarted(PipelineStage.MATERIALIZE)

        template_id: str = getattr(template_spec, "template_id", "unknown")
        artifacts: dict[str, Any] = {}
        unavailable_issues: list[VerifierIssue] = []

        for selection in planner_output.helper_selection:
            for inv in selection.helpers:
                helper = get_helper(inv.helper_name)
                if helper is None:
                    unavailable_issues.append(
                        VerifierIssue(
                            type=VerifierIssueType.HELPER_UNAVAILABLE,
                            detail_code="planner_named_unknown_helper",
                            helper=inv.helper_name,
                            detail=(
                                f"Planner selected helper {inv.helper_name!r} which is "
                                "not registered in the v2.2 library_helpers registry."
                            ),
                            severity="blocking",
                        )
                    )
                    continue

                try:
                    result = helper.impl(**inv.params)
                    artifacts[inv.artifact_id] = result
                except Exception as exc:
                    unavailable_issues.append(
                        VerifierIssue(
                            type=VerifierIssueType.HELPER_UNAVAILABLE,
                            detail_code="helper_invocation_error",
                            helper=inv.helper_name,
                            detail=f"Helper {inv.helper_name!r} raised: {exc}",
                            severity="blocking",
                        )
                    )

        # Resolve the section plan: load template defaults then apply overrides.
        # Fall back to an empty plan when no defaults are found for this template.
        try:
            template_defaults = load_template_defaults(template_id)
        except FileNotFoundError:
            from openlia.llm.runtime.report_v2_2.section_plan import ReportSectionPlan

            template_defaults = ReportSectionPlan(template_id=template_id, sections=[])

        # Pick the first planner_overrides entry that matches this template.
        matching_override = next(
            (o for o in planner_output.planner_overrides if o.template_id == template_id),
            None,
        )
        resolved_plan = resolve_section_plan(template_defaults, matching_override)

        # Materialize: drop any artifacts referenced in the plan that are
        # missing from our collected dict (materialization raises on missing;
        # we pre-filter to avoid a hard crash when helpers failed above).
        referenced_ids = {
            ref.artifact_id for sec in resolved_plan.sections for ref in sec.artifacts
        }
        available = {k: v for k, v in artifacts.items() if k in referenced_ids}

        # Patch the section plan to only reference available artifacts.
        from openlia.llm.runtime.report_v2_2.section_plan import (
            ReportSectionPlan,
            SectionArtifactRef,
            SectionPlan,
        )

        filtered_sections: list[SectionPlan] = []
        for sec in resolved_plan.sections:
            filtered_artifacts: list[SectionArtifactRef] = [
                ref for ref in sec.artifacts if ref.artifact_id in available
            ]
            filtered_sections.append(
                SectionPlan(
                    section_id=sec.section_id,
                    title=sec.title,
                    artifacts=filtered_artifacts,
                    drafter_brief=sec.drafter_brief,
                )
            )
        filtered_plan = ReportSectionPlan(
            template_id=resolved_plan.template_id,
            sections=filtered_sections,
            overrides_applied=resolved_plan.overrides_applied,
        )

        try:
            materialized = materialize(filtered_plan, available)
        except MaterializationError as exc:
            # Degrade gracefully: return a minimal empty MaterializedReport.
            materialized = MaterializedReport(
                template_id=template_id,
                sections=[],
                markdown="",
            )
            unavailable_issues.append(
                VerifierIssue(
                    type=VerifierIssueType.HELPER_UNAVAILABLE,
                    detail_code="materialize_error",
                    helper="__stage_7a__",
                    detail=f"Stage 7a materialize() failed: {exc}",
                    severity="blocking",
                )
            )

        # Attach any HELPER_UNAVAILABLE issues to the materialized report so
        # Stage 8 can surface them.
        materialized.__dict__["_unavailable_issues"] = unavailable_issues

        yield StageCompleted(PipelineStage.MATERIALIZE)
        return materialized

    def _stage_model_build(self, plan: Any, research_pool: Any) -> Iterator[RunEvent]:
        self.current_stage = PipelineStage.MODEL_BUILD
        yield StageStarted(PipelineStage.MODEL_BUILD)
        all_artifacts = plan.required_artifacts + plan.optional_artifacts
        artifacts = self.model_builder.build(
            artifacts=all_artifacts,
            research_pool=research_pool,
        )
        yield StageCompleted(PipelineStage.MODEL_BUILD)
        return artifacts

    def _stage_draft(
        self,
        template_spec: Any,
        plan: Any,
        composer_inputs: dict[str, Any],
        research_pool: Any,
        model_artifacts: list,
        *,
        materialized_report: Any | None = None,
    ) -> Iterator[RunEvent]:
        """Stage 7b: draft all sections.

        When ``materialized_report`` is provided (Stage 7a ran), each section
        drafter call receives a ``materialized_section`` kwarg so SectionDrafter
        can use ``build_drafter_prompt()`` for artifact-injected prompts (A-3).

        When ``materialized_report`` is None (v2 path), falls through to the
        existing v2 hand-rolled prompt path unchanged.
        """
        self.current_stage = PipelineStage.DRAFT
        yield StageStarted(PipelineStage.DRAFT)

        # Build a lookup from section_id → MaterializedSection when available.
        materialized_by_section: dict[str, Any] = {}
        if materialized_report is not None:
            for ms in getattr(materialized_report, "sections", []):
                materialized_by_section[ms.section_id] = ms

        outputs = self.section_drafter.draft_all(
            sections=template_spec.sections,
            dag=plan.section_dag,
            composer_inputs=composer_inputs,
            research_pool=research_pool,
            model_artifacts=model_artifacts,
            materialized_by_section=materialized_by_section or None,
        )
        yield StageCompleted(PipelineStage.DRAFT)
        return outputs

    def _stage_verify(
        self,
        *,
        template_spec: Any,
        plan: Any,
        section_outputs: list[SectionOutput],
        research_pool: Any,
        model_artifacts: list,
        composer_inputs: dict[str, Any],
    ) -> Iterator[RunEvent]:
        """Run the per-section verifier with retry, returning updated sections + history.

        Sections with status="SKIPPED" or already-DEGRADED (drafter exception)
        bypass verification. OK sections go through ``verify_with_retry``; if
        the result is DEGRADED, the section status is downgraded and the run
        is marked DEGRADED. Redrafted blocks from successful retries replace
        the original drafter output before assembly.
        """
        self.current_stage = PipelineStage.VERIFY
        yield StageStarted(PipelineStage.VERIFY)

        directives = {s.id: s.directive for s in template_spec.sections}
        # The verifier's directive lookup is constructor-bound; refresh per-run
        # so the same factory-built Verifier serves any template.
        self.verifier._directives = directives

        required_artifact_ids = {a.id for a in plan.required_artifacts}
        pool_citation_ids = {c.id for c in research_pool.citations}
        citations_by_id = {c.id: c for c in research_pool.citations}

        per_section_results: list[SectionVerificationResult] = []
        updated: list[SectionOutput] = []
        for s in section_outputs:
            if s.status != "OK":
                updated.append(s)
                continue

            result = self.verifier.verify_with_retry(
                section_id=s.section_id,
                blocks=s.blocks,
                research_pool=research_pool,
                model_artifacts=model_artifacts,
                citations=citations_by_id,
                pool_citation_ids=pool_citation_ids,
                required_artifact_ids=required_artifact_ids,
                embedded_artifact_ids=set(),
                retry_context={"composer_inputs": composer_inputs},
            )
            per_section_results.append(result)

            new_blocks = result.final_blocks or s.blocks
            if result.final_status == "DEGRADED":
                blocker_types = sorted(
                    {
                        i.issue_type
                        for r in result.rounds
                        for i in r.issues
                        if i.severity == "blocker"
                    }
                )
                reason = (
                    "verifier persisted blockers: " + ", ".join(blocker_types)
                    if blocker_types
                    else "verifier marked section degraded"
                )
                updated.append(
                    SectionOutput(
                        section_id=s.section_id,
                        section_name=s.section_name,
                        status="DEGRADED",
                        blocks=new_blocks,
                        degraded_reason=reason,
                    )
                )
            else:
                updated.append(
                    SectionOutput(
                        section_id=s.section_id,
                        section_name=s.section_name,
                        status="OK",
                        blocks=new_blocks,
                    )
                )

        verification_history = _build_verification_history(per_section_results)

        yield StageCompleted(PipelineStage.VERIFY)
        return (updated, verification_history)

    def _stage_assemble(
        self,
        template_spec: Any,
        section_outputs: list,
        research_pool: Any,
        verification_history: VerificationHistory,
        composer_inputs: dict[str, Any],
    ) -> Iterator[RunEvent]:
        self.current_stage = PipelineStage.ASSEMBLE
        yield StageStarted(PipelineStage.ASSEMBLE)

        # OK sections render their blocks; SKIPPED sections render a banner.
        # DEGRADED sections fall through with whatever the drafter produced.
        # Status / skip_reason / degraded_reason ride along so the frontend
        # can colour-code the section header (DEGRADED) without re-deriving
        # it from a banner block.
        sections_dicts: list[dict[str, Any]] = []
        for s in section_outputs:
            if s.status == "SKIPPED":
                sections_dicts.append(
                    {
                        "id": s.section_id,
                        "name": s.section_name,
                        "status": "SKIPPED",
                        "skip_reason": s.skip_reason,
                        "blocks": [
                            {
                                "type": "skip_banner",
                                "section_name": s.section_name,
                                "reason": s.skip_reason or "",
                            }
                        ],
                    }
                )
            else:
                sections_dicts.append(
                    {
                        "id": s.section_id,
                        "name": s.section_name,
                        "status": s.status,
                        "degraded_reason": s.degraded_reason,
                        "blocks": s.blocks,
                    }
                )

        # Accumulate per-section outcomes into the run summary.
        for s in section_outputs:
            self.outcomes.append(
                TaskOutcome(
                    task_type="section_draft",
                    task_name=s.section_name,
                    status=s.status,
                    notes=s.skip_reason or s.degraded_reason,
                )
            )
            if s.status == "DEGRADED":
                self.state = RunState.DEGRADED

        manifest = load_manifest()
        run_summary = RunSummary(
            engine_version=manifest.engine_version,
            template_id=getattr(template_spec, "template_id", "unknown"),
            template_name=getattr(template_spec, "template_name", "unknown"),
            composer_inputs=dict(composer_inputs),
            outcomes=list(self.outcomes),
        )
        pool_citations = {c.id: c for c in research_pool.citations}

        report = build_report_v2(
            sections=sections_dicts,
            composer_inputs=composer_inputs,
            template_spec=template_spec,
            pool_citations=pool_citations,
            run_summary=run_summary,
            verification_history=verification_history,
            dev_mode=manifest.dev_mode,
        )

        yield StageCompleted(PipelineStage.ASSEMBLE)
        return report

    # ------------------------------------------------------------------ legacy

    def transition(self, new_state: RunState) -> None:
        """Legacy transition helper kept for tests of the original skeleton."""
        self.state = new_state

    def enter_stage(self, stage: PipelineStage) -> None:
        """Legacy stage-entry helper kept for tests of the original skeleton."""
        self.current_stage = stage


def _build_verification_history(
    section_results: list[SectionVerificationResult],
) -> VerificationHistory:
    """Aggregate per-section verifier results into a renderable history.

    Each unique (issue_type, evidence) signature within a section becomes one
    entry. ``raised_at_round`` is the first round it appeared; if the
    signature is absent from the final round we treat it as resolved in
    ``last_seen + 1``. Surviving signatures are tagged ``persisted_degraded``
    (blockers in a degraded result) or ``still_open`` (warnings, or blockers
    in an OK result — the latter shouldn't happen but we don't drop them).
    """
    entries: list[VerificationHistoryEntry] = []
    resolved_first = 0
    resolved_later = 0
    persisted = 0
    warnings_open = 0

    for sr in section_results:
        if not sr.rounds:
            continue

        first_seen: dict[tuple[str, str], int] = {}
        last_seen: dict[tuple[str, str], int] = {}
        sig_to_issue: dict[tuple[str, str], Any] = {}
        for r_idx, round_obj in enumerate(sr.rounds):
            for issue in round_obj.issues:
                sig = (issue.issue_type, issue.evidence)
                if sig not in first_seen:
                    first_seen[sig] = r_idx
                last_seen[sig] = r_idx
                sig_to_issue[sig] = issue

        last_round_sigs = {(i.issue_type, i.evidence) for i in sr.rounds[-1].issues}

        for sig, issue in sig_to_issue.items():
            if sig in last_round_sigs:
                if issue.severity == "blocker" and sr.final_status == "DEGRADED":
                    resolution = "persisted_degraded"
                    persisted += 1
                    resolved_in = None
                else:
                    resolution = "still_open"
                    warnings_open += 1
                    resolved_in = None
            else:
                resolution = "resolved"
                resolved_in = last_seen[sig] + 1
                if resolved_in == 1:
                    resolved_first += 1
                else:
                    resolved_later += 1
            entries.append(
                VerificationHistoryEntry(
                    issue=issue,
                    raised_at_round=first_seen[sig],
                    final_resolution=resolution,
                    resolved_in_round=resolved_in,
                )
            )

    return VerificationHistory(
        entries=entries,
        total_issues_raised=len(entries),
        resolved_on_first_retry=resolved_first,
        resolved_on_subsequent_retry=resolved_later,
        persisted_to_degraded=persisted,
        warnings_open=warnings_open,
    )
