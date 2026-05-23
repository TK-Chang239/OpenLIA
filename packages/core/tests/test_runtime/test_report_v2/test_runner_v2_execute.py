"""Tests for RunnerV2.execute() — the v2.2 pipeline orchestrator.

Each test exercises one event-flow path through the generator: happy
path, clarifier pause, resume from pause, and failure propagation. Stage
objects are injected as mocks so the orchestrator is verified in
isolation from real LLM calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
from openlia.llm.runtime.report_v2.pipeline.stage_7_draft import SectionOutput
from openlia.llm.runtime.report_v2.pipeline.stage_8_verify import (
    SectionVerificationResult,
    VerificationRound,
)
from openlia.llm.runtime.report_v2.runner_v2 import (
    ClarifierPaused,
    Completed,
    Failed,
    PipelineStage,
    ResumeState,
    RunnerV2,
    RunState,
    StageCompleted,
    StageStarted,
)
from openlia.llm.runtime.report_v2.schemas.clarifier import (
    CapabilityWarning,
    ClarifierOutput,
)
from openlia.llm.runtime.report_v2.schemas.plan import Plan, ResearchStrand
from openlia.llm.runtime.report_v2.schemas.research_pool import ResearchPool
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


def _empty_template() -> Any:
    """Return a minimal duck-typed template_spec for the orchestrator."""
    template = Mock()
    template.template_id = "stock_research_v2"
    template.template_name = "Stock Research (v2)"
    template.sections = []
    return template


def _wire_stage_mocks(
    *,
    clarifier_output: ClarifierOutput,
    section_outputs: list[SectionOutput] | None = None,
    verifier_results: dict[str, SectionVerificationResult] | None = None,
) -> dict[str, Mock]:
    """Construct stage mocks that return sane defaults for the happy path."""
    clarifier = Mock()
    clarifier.clarify.return_value = clarifier_output

    research_planner = Mock()
    plan = Plan(
        research_strands=[
            ResearchStrand(id="fundamentals", purpose="x", allowed_tools=[]),
        ],
        required_artifacts=[],
        optional_artifacts=[],
        section_dag={},
        slipped_requests=[],
    )
    research_planner.plan.return_value = plan

    strand_dispatcher = Mock()
    strand_dispatcher.dispatch.return_value = ResearchPool()

    model_planner = Mock()
    model_planner.plan.return_value = plan  # no optional artifacts added

    model_builder = Mock()
    model_builder.build.return_value = []

    section_drafter = Mock()
    section_drafter.draft_all.return_value = section_outputs or []

    # By default the verifier returns each section unchanged with status OK.
    verifier = Mock()

    def _default_verify(*, section_id, blocks, **_kw):
        if verifier_results and section_id in verifier_results:
            return verifier_results[section_id]
        return SectionVerificationResult(
            section_id=section_id,
            final_status="OK",
            rounds=[VerificationRound(round_num=0, issues=[])],
            all_issues_ever=[],
            final_blocks=blocks,
        )

    verifier.verify_with_retry.side_effect = _default_verify

    return {
        "clarifier": clarifier,
        "research_planner": research_planner,
        "strand_dispatcher": strand_dispatcher,
        "model_planner": model_planner,
        "model_builder": model_builder,
        "section_drafter": section_drafter,
        "verifier": verifier,
    }


def _ok_clarifier_output() -> ClarifierOutput:
    return ClarifierOutput(
        questions=[],
        blocking_warnings=[],
        notices=[],
        detected_intents=[],
    )


def _blocking_clarifier_output() -> ClarifierOutput:
    return ClarifierOutput(
        questions=[],
        blocking_warnings=[
            CapabilityWarning(
                capability_id="extra_passes",
                detected_phrase="devil's advocate",
                user_message="Extra LLM passes are not supported in this version.",
                available_actions=["proceed_without", "cancel_and_edit", "clarify"],
            )
        ],
        notices=[],
        detected_intents=["extra_passes"],
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_yields_all_stages_and_completes() -> None:
    """No blocking warnings → generator drives every stage and yields Completed."""
    template = _empty_template()
    stages = _wire_stage_mocks(clarifier_output=_ok_clarifier_output())
    runner = RunnerV2(**stages)

    events = list(runner.execute({"ticker": "AAPL"}, template))

    stage_pairs = [
        (StageStarted, PipelineStage.CLARIFY),
        (StageCompleted, PipelineStage.CLARIFY),
        (StageStarted, PipelineStage.RESEARCH_PLAN),
        (StageCompleted, PipelineStage.RESEARCH_PLAN),
        (StageStarted, PipelineStage.GATHER),
        (StageCompleted, PipelineStage.GATHER),
        (StageStarted, PipelineStage.MODEL_PLAN),
        (StageCompleted, PipelineStage.MODEL_PLAN),
        (StageStarted, PipelineStage.MODEL_BUILD),
        (StageCompleted, PipelineStage.MODEL_BUILD),
        (StageStarted, PipelineStage.DRAFT),
        (StageCompleted, PipelineStage.DRAFT),
        (StageStarted, PipelineStage.VERIFY),
        (StageCompleted, PipelineStage.VERIFY),
        (StageStarted, PipelineStage.ASSEMBLE),
        (StageCompleted, PipelineStage.ASSEMBLE),
    ]
    for idx, (cls, stage) in enumerate(stage_pairs):
        assert isinstance(events[idx], cls)
        assert events[idx].stage == stage

    final = events[-1]
    assert isinstance(final, Completed)
    # Report shape — engine + run summary should always be populated.
    assert final.report.engine_version
    assert final.report.run_summary.template_id == "stock_research_v2"
    assert final.report.run_summary.template_id == "stock_research_v2"
    assert runner.state == RunState.COMPLETED


# ---------------------------------------------------------------------------
# Pause
# ---------------------------------------------------------------------------


def test_pauses_when_clarifier_returns_blocking_warnings() -> None:
    """Blocking warnings short-circuit the run; later stages are not called."""
    template = _empty_template()
    stages = _wire_stage_mocks(clarifier_output=_blocking_clarifier_output())
    runner = RunnerV2(**stages)

    events = list(runner.execute({"ticker": "AAPL"}, template))

    paused = [e for e in events if isinstance(e, ClarifierPaused)]
    assert len(paused) == 1
    assert paused[0].round == 1
    assert paused[0].output.blocking_warnings[0].capability_id == "extra_passes"
    assert paused[0].clarification_history == [paused[0].output]

    # Downstream stages were not entered.
    stages["research_planner"].plan.assert_not_called()
    stages["strand_dispatcher"].dispatch.assert_not_called()
    stages["section_drafter"].draft_all.assert_not_called()

    assert runner.state == RunState.CLARIFY_AWAITING_USER
    assert not any(isinstance(e, Completed) for e in events)


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------


def test_resume_skips_clarifier_and_drives_remaining_stages() -> None:
    """resume_state populated → Stage 1 is skipped, Stage 3+ run with the answers."""
    template = _empty_template()
    # The clarifier mock would fail the test if invoked.
    stages = _wire_stage_mocks(clarifier_output=_ok_clarifier_output())
    runner = RunnerV2(**stages)

    resume = ResumeState(
        clarification_history=[_blocking_clarifier_output()],
        answers={
            "warning_actions": {"extra_passes": "proceed_without"},
            "clarifications": {},
            "question_answers": {},
        },
    )
    events = list(runner.execute({"ticker": "AAPL"}, template, resume_state=resume))

    stages["clarifier"].clarify.assert_not_called()
    stages["research_planner"].plan.assert_called_once()
    # Research planner receives the user's answer payload on resume.
    kwargs = stages["research_planner"].plan.call_args.kwargs
    assert kwargs["clarifier_answers"] == resume.answers

    assert isinstance(events[0], StageStarted)
    assert events[0].stage == PipelineStage.RESEARCH_PLAN
    assert isinstance(events[-1], Completed)
    assert runner.state == RunState.COMPLETED


# ---------------------------------------------------------------------------
# Failure
# ---------------------------------------------------------------------------


def test_failed_event_when_a_stage_raises() -> None:
    """Exception inside a stage surfaces as a Failed event tagged to that stage."""
    template = _empty_template()
    stages = _wire_stage_mocks(clarifier_output=_ok_clarifier_output())
    stages["research_planner"].plan.side_effect = RuntimeError("planner blew up")
    runner = RunnerV2(**stages)

    events = list(runner.execute({"ticker": "AAPL"}, template))

    failed = [e for e in events if isinstance(e, Failed)]
    assert len(failed) == 1
    assert failed[0].stage == PipelineStage.RESEARCH_PLAN
    assert "planner blew up" in failed[0].reason
    assert runner.state == RunState.FAILED
    # Subsequent stages must not have been entered.
    stages["strand_dispatcher"].dispatch.assert_not_called()


def test_execute_requires_all_stages_injected() -> None:
    """Construction without stage objects raises a clear error from execute()."""
    runner = RunnerV2()  # all stage fields default None
    with pytest.raises(RuntimeError, match="missing"):
        list(runner.execute({"ticker": "AAPL"}, _empty_template()))


# ---------------------------------------------------------------------------
# Degraded propagation through outcomes
# ---------------------------------------------------------------------------


def test_degraded_section_marks_run_state_degraded() -> None:
    """A DEGRADED section drags the runner state to DEGRADED but still completes."""
    template = _empty_template()
    degraded = SectionOutput(
        section_id="thesis",
        section_name="Investment Thesis",
        status="DEGRADED",
        blocks=[],
        degraded_reason="LLM call timed out",
    )
    stages = _wire_stage_mocks(
        clarifier_output=_ok_clarifier_output(),
        section_outputs=[degraded],
    )
    runner = RunnerV2(**stages)

    events = list(runner.execute({"ticker": "AAPL"}, template))

    assert isinstance(events[-1], Completed)
    assert runner.state == RunState.DEGRADED
    final: Completed = events[-1]  # type: ignore[assignment]
    notes = [o.notes for o in final.report.run_summary.outcomes]
    assert "LLM call timed out" in notes
    # Drafter-degraded sections must not be re-verified.
    stages["verifier"].verify_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# Verifier integration (Stage 8)
# ---------------------------------------------------------------------------


def test_verifier_promotes_persisted_blocker_section_to_degraded() -> None:
    """An OK draft that the verifier can't fix becomes DEGRADED before assemble."""
    template = _empty_template()
    ok_section = SectionOutput(
        section_id="thesis",
        section_name="Investment Thesis",
        status="OK",
        blocks=[{"type": "prose", "text": "draft"}],
    )
    persisted_issue = VerifierIssue(
        issue_type="content_too_sparse",
        section_id="thesis",
        severity="blocker",
        evidence="Single sentence.",
        suggested_fix="Add depth.",
        detector="llm",
    )
    degraded_result = SectionVerificationResult(
        section_id="thesis",
        final_status="DEGRADED",
        rounds=[
            VerificationRound(round_num=0, issues=[persisted_issue]),
            VerificationRound(round_num=1, issues=[persisted_issue]),
        ],
        all_issues_ever=[persisted_issue, persisted_issue],
        final_blocks=[{"type": "prose", "text": "still thin"}],
    )

    stages = _wire_stage_mocks(
        clarifier_output=_ok_clarifier_output(),
        section_outputs=[ok_section],
        verifier_results={"thesis": degraded_result},
    )
    runner = RunnerV2(**stages)

    events = list(runner.execute({"ticker": "AAPL"}, template))

    final: Completed = events[-1]  # type: ignore[assignment]
    assert isinstance(final, Completed)
    assert runner.state == RunState.DEGRADED
    thesis_outcomes = [o for o in final.report.run_summary.outcomes if o.task_name == "Investment Thesis"]
    assert thesis_outcomes and thesis_outcomes[0].status == "DEGRADED"
    assert "content_too_sparse" in (thesis_outcomes[0].notes or "")

    history = final.report.verification_history
    assert history is not None
    assert history.total_issues_raised == 1
    assert history.persisted_to_degraded == 1


def test_verifier_redrafted_blocks_flow_into_assemble() -> None:
    """When verifier retry resolves the issue, the new blocks replace the draft output."""
    template = _empty_template()
    ok_section = SectionOutput(
        section_id="thesis",
        section_name="Investment Thesis",
        status="OK",
        blocks=[{"type": "prose", "text": "[placeholder]"}],
    )
    raised = VerifierIssue(
        issue_type="tombstone",
        section_id="thesis",
        severity="blocker",
        evidence="Placeholder text",
        detector="deterministic",
    )
    resolved_result = SectionVerificationResult(
        section_id="thesis",
        final_status="OK",
        rounds=[
            VerificationRound(round_num=0, issues=[raised]),
            VerificationRound(round_num=1, issues=[]),
        ],
        all_issues_ever=[raised],
        final_blocks=[{"type": "prose", "text": "Clean redrafted thesis."}],
    )

    stages = _wire_stage_mocks(
        clarifier_output=_ok_clarifier_output(),
        section_outputs=[ok_section],
        verifier_results={"thesis": resolved_result},
    )
    runner = RunnerV2(**stages)

    events = list(runner.execute({"ticker": "AAPL"}, template))

    final: Completed = events[-1]  # type: ignore[assignment]
    assert isinstance(final, Completed)
    assert runner.state == RunState.COMPLETED
    # Redrafted blocks land on the thesis section verbatim — the assembler
    # passes typed-block dicts through unchanged.
    thesis = next(s for s in final.report.sections if s.id == "thesis")
    block_texts = " ".join(b.get("text", "") for b in thesis.blocks)
    assert "Clean redrafted thesis." in block_texts
    assert "[placeholder]" not in block_texts

    # Verification history rides on the report payload (dev_mode=true in
    # capabilities.yaml means it's included).
    assert final.report.verification_history is not None
    assert final.report.verification_history.total_issues_raised == 1
    assert final.report.verification_history.resolved_on_first_retry == 1
