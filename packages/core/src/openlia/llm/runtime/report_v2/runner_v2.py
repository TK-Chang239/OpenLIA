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
"""

from __future__ import annotations

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
    assemble_report,
)
from openlia.llm.runtime.report_v2.schemas.clarifier import ClarifierOutput
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
    MODEL_BUILD = "model_build"
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
    html: str
    run_summary: RunSummary
    verification_history: VerificationHistory


@dataclass(frozen=True)
class Failed:
    stage: PipelineStage
    reason: str


RunEvent = (
    StageStarted | StageCompleted | ClarifierPaused | Completed | Failed
)


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
    """

    clarifier: Clarifier | None = None
    research_planner: ResearchPlanner | None = None
    strand_dispatcher: StrandDispatcher | None = None
    model_planner: ModelPlanner | None = None
    model_builder: ModelBuilder | None = None
    section_drafter: SectionDrafter | None = None
    verifier: Verifier | None = None

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
            raise RuntimeError(
                f"RunnerV2.execute() requires injected stages: missing {missing}"
            )

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

            research_pool = yield from self._stage_gather(
                plan, composer_inputs
            )

            plan = yield from self._stage_model_plan(plan, research_pool)

            model_artifacts = yield from self._stage_model_build(
                plan, research_pool
            )

            section_outputs = yield from self._stage_draft(
                template_spec, plan, composer_inputs, research_pool, model_artifacts
            )

            section_outputs, verification_history = yield from self._stage_verify(
                template_spec=template_spec,
                plan=plan,
                section_outputs=section_outputs,
                research_pool=research_pool,
                model_artifacts=model_artifacts,
                composer_inputs=composer_inputs,
            )

            html, run_summary = yield from self._stage_assemble(
                template_spec, section_outputs, research_pool, verification_history
            )

            # Preserve DEGRADED if any section failed; otherwise mark COMPLETED.
            if self.state != RunState.DEGRADED:
                self.state = RunState.COMPLETED
            yield Completed(
                html=html,
                run_summary=run_summary,
                verification_history=verification_history,
            )
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

    def _stage_gather(
        self, plan: Any, composer_inputs: dict[str, Any]
    ) -> Iterator[RunEvent]:
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

    def _stage_model_build(
        self, plan: Any, research_pool: Any
    ) -> Iterator[RunEvent]:
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
    ) -> Iterator[RunEvent]:
        self.current_stage = PipelineStage.DRAFT
        yield StageStarted(PipelineStage.DRAFT)
        outputs = self.section_drafter.draft_all(
            sections=template_spec.sections,
            dag=plan.section_dag,
            composer_inputs=composer_inputs,
            research_pool=research_pool,
            model_artifacts=model_artifacts,
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
                blocker_types = sorted({
                    i.issue_type
                    for r in result.rounds
                    for i in r.issues
                    if i.severity == "blocker"
                })
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
    ) -> Iterator[RunEvent]:
        self.current_stage = PipelineStage.ASSEMBLE
        yield StageStarted(PipelineStage.ASSEMBLE)

        # OK sections render their blocks; SKIPPED sections render a banner.
        # DEGRADED sections fall through with whatever the drafter produced.
        sections_dicts: list[dict[str, Any]] = []
        for s in section_outputs:
            if s.status == "SKIPPED":
                sections_dicts.append({
                    "id": s.section_id,
                    "name": s.section_name,
                    "blocks": [{
                        "type": "skip_banner",
                        "section_name": s.section_name,
                        "reason": s.skip_reason or "",
                    }],
                })
            else:
                sections_dicts.append({
                    "id": s.section_id,
                    "name": s.section_name,
                    "blocks": s.blocks,
                })

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
            composer_inputs={},
            outcomes=list(self.outcomes),
        )
        pool_citations = {c.id: c for c in research_pool.citations}

        html = assemble_report(
            sections=sections_dicts,
            pool_citations=pool_citations,
            run_summary=run_summary,
            verification_history=verification_history,
            dev_mode=manifest.dev_mode,
        )

        yield StageCompleted(PipelineStage.ASSEMBLE)
        return (html, run_summary)

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

        last_round_sigs = {
            (i.issue_type, i.evidence) for i in sr.rounds[-1].issues
        }

        for sig, issue in sig_to_issue.items():
            if sig in last_round_sigs:
                if (
                    issue.severity == "blocker"
                    and sr.final_status == "DEGRADED"
                ):
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


