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

    return {
        "clarifier": clarifier,
        "research_planner": research_planner,
        "strand_dispatcher": strand_dispatcher,
        "model_planner": model_planner,
        "model_builder": model_builder,
        "section_drafter": section_drafter,
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
        (StageStarted, PipelineStage.ASSEMBLE),
        (StageCompleted, PipelineStage.ASSEMBLE),
    ]
    for idx, (cls, stage) in enumerate(stage_pairs):
        assert isinstance(events[idx], cls)
        assert events[idx].stage == stage

    final = events[-1]
    assert isinstance(final, Completed)
    assert "<article" in final.html
    assert final.run_summary.template_id == "stock_research_v2"
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
    events = list(
        runner.execute({"ticker": "AAPL"}, template, resume_state=resume)
    )

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
    notes = [o.notes for o in final.run_summary.outcomes]
    assert "LLM call timed out" in notes
