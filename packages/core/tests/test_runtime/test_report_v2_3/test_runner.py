"""Unit tests for ReportRunner — state-machine transitions + retry."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.runner import ReportRunner
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyAnswers,
    ClarifyQuestion,
    IssueKind,
    IssueSeverity,
    Language,
    ReportType,
    RunStatus,
    VerifyIssue,
    VerifyResult,
)
from openlia.llm.runtime.report_v2_3.slots import V23Slot
from openlia.llm.runtime.report_v2_3.stages import (
    PIPELINE_ORDER,
    NoOpAssembleStage,
    NoOpStage,
    StageContext,
)
from openlia.llm.runtime.report_v2_3.state import ReportState


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def _fresh_state() -> ReportState:
    return ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )


def _all_noop_stages(
    hooks: dict[V23Slot, callable] | None = None,
) -> dict[V23Slot, NoOpStage]:
    hooks = hooks or {}
    return {slot: NoOpStage(slot, hooks.get(slot)) for slot in PIPELINE_ORDER}


def _runner(
    hooks: dict[V23Slot, callable] | None = None,
    assemble_hook: callable | None = None,
) -> ReportRunner:
    return ReportRunner(
        stages=_all_noop_stages(hooks),
        assemble=NoOpAssembleStage(assemble_hook),
        ctx=_ctx(),
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_runner_rejects_missing_slot_stages() -> None:
    partial = _all_noop_stages()
    del partial[V23Slot.SYNTHESIZE]
    with pytest.raises(ValueError, match="missing stages"):
        ReportRunner(stages=partial, assemble=NoOpAssembleStage(), ctx=_ctx())


def test_runner_rejects_slot_mismatch() -> None:
    stages = _all_noop_stages()
    stages[V23Slot.WRITE] = NoOpStage(V23Slot.PLAN)  # wrong slot for this key
    with pytest.raises(ValueError, match="reports slot"):
        ReportRunner(stages=stages, assemble=NoOpAssembleStage(), ctx=_ctx())


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_runs_all_stages_and_completes() -> None:
    visited: list[str] = []

    def record(slot_name: str):
        def hook(state, ctx):
            visited.append(slot_name)

        return hook

    hooks = {slot: record(slot.value) for slot in PIPELINE_ORDER}
    runner = ReportRunner(
        stages={slot: NoOpStage(slot, hooks[slot]) for slot in PIPELINE_ORDER},
        assemble=NoOpAssembleStage(lambda s, c: visited.append("assemble")),
        ctx=_ctx(),
    )
    state = runner.start(_fresh_state())

    assert state.status == RunStatus.COMPLETE
    assert visited == [slot.value for slot in PIPELINE_ORDER] + ["assemble"]
    assert state.current_stage == V23Slot.VERIFY


def test_start_requires_running_status() -> None:
    state = _fresh_state()
    state.complete()
    with pytest.raises(ValueError, match="status=RUNNING"):
        _runner().start(state)


# ---------------------------------------------------------------------------
# Suspend / resume
# ---------------------------------------------------------------------------


def _suspend_hook(state, ctx) -> None:
    state.suspend_for_clarify(
        [
            ClarifyQuestion(
                id="horizon",
                question="horizon?",
                why_blocking="drives model",
                default="12 months",
            )
        ]
    )


def test_clarify_suspend_returns_state_with_pending_questions() -> None:
    runner = _runner(hooks={V23Slot.CLARIFY: _suspend_hook})
    state = runner.start(_fresh_state())

    assert state.status == RunStatus.WAITING_ON_USER
    assert state.current_stage == V23Slot.CLARIFY
    assert len(state.pending_questions) == 1
    assert state.pending_questions[0].id == "horizon"


def test_resume_continues_through_remaining_stages() -> None:
    visited: list[str] = []

    # First time CLARIFY runs: suspend. On resume, the test toggles a flag to
    # let CLARIFY through without suspending again.
    clarify_calls = {"n": 0}

    def clarify_hook(state, ctx) -> None:
        clarify_calls["n"] += 1
        visited.append("clarify")
        if clarify_calls["n"] == 1:
            _suspend_hook(state, ctx)

    def record(slot_name: str):
        def hook(state, ctx) -> None:
            visited.append(slot_name)

        return hook

    hooks: dict[V23Slot, callable] = {V23Slot.CLARIFY: clarify_hook}
    for slot in PIPELINE_ORDER:
        if slot != V23Slot.CLARIFY:
            hooks[slot] = record(slot.value)

    runner = ReportRunner(
        stages={slot: NoOpStage(slot, hooks[slot]) for slot in PIPELINE_ORDER},
        assemble=NoOpAssembleStage(lambda s, c: visited.append("assemble")),
        ctx=_ctx(),
    )

    state = runner.start(_fresh_state())
    assert state.status == RunStatus.WAITING_ON_USER
    assert visited == ["clarify"]

    state = runner.resume(state, ClarifyAnswers(answers={"horizon": "12 months"}))
    assert state.status == RunStatus.COMPLETE
    assert state.clarify_answers is not None
    assert state.clarify_answers.answers == {"horizon": "12 months"}
    # CLARIFY ran twice (suspend + finalize), then the rest of the pipeline.
    assert visited == [
        "clarify",
        "clarify",
        "plan",
        "research",
        "compute",
        "synthesize",
        "write",
        "visualize",
        "verify",
        "assemble",
    ]


def test_resume_requires_waiting_on_user() -> None:
    runner = _runner()
    state = _fresh_state()
    with pytest.raises(ValueError, match="WAITING_ON_USER"):
        runner.resume(state, ClarifyAnswers())


def test_resume_requires_current_stage() -> None:
    runner = _runner()
    state = _fresh_state()
    state.status = RunStatus.WAITING_ON_USER  # contrived: no current_stage set
    with pytest.raises(ValueError, match="current_stage"):
        runner.resume(state, ClarifyAnswers())


# ---------------------------------------------------------------------------
# Failure
# ---------------------------------------------------------------------------


def test_stage_exception_marks_state_failed() -> None:
    def boom(state, ctx) -> None:
        raise RuntimeError("kaboom")

    runner = _runner(hooks={V23Slot.RESEARCH: boom})
    state = runner.start(_fresh_state())
    assert state.status == RunStatus.FAILED
    assert state.last_error is not None
    assert "research" in state.last_error
    assert "kaboom" in state.last_error


def test_assemble_exception_marks_state_failed() -> None:
    def boom(state, ctx) -> None:
        raise RuntimeError("docx broke")

    runner = _runner(assemble_hook=boom)
    state = runner.start(_fresh_state())
    assert state.status == RunStatus.FAILED
    assert state.last_error is not None
    assert "docx broke" in state.last_error


# ---------------------------------------------------------------------------
# Verify -> write bounded retry
# ---------------------------------------------------------------------------


def _high_severity_verify(state, ctx) -> None:
    state.verify_result = VerifyResult(
        issues=[
            VerifyIssue(
                section_id="overview",
                kind=IssueKind.VALUE_MISMATCH,
                severity=IssueSeverity.HIGH,
                detail="stated 14% but bundle says 14.2%",
            )
        ]
    )


def test_verify_high_severity_routes_back_to_write_once() -> None:
    write_calls = {"n": 0}
    verify_calls = {"n": 0}

    def write_hook(state, ctx) -> None:
        write_calls["n"] += 1

    def verify_hook(state, ctx) -> None:
        verify_calls["n"] += 1
        _high_severity_verify(state, ctx)

    runner = _runner(hooks={V23Slot.WRITE: write_hook, V23Slot.VERIFY: verify_hook})
    state = runner.start(_fresh_state())

    assert state.status == RunStatus.COMPLETE
    assert state.retry_count == 1
    assert write_calls["n"] == 2  # initial + one retry
    assert verify_calls["n"] == 2  # initial + after retry


def test_verify_low_severity_does_not_retry() -> None:
    def verify_hook(state, ctx) -> None:
        state.verify_result = VerifyResult(
            issues=[
                VerifyIssue(
                    section_id=None,
                    kind=IssueKind.REDUNDANCY,
                    severity=IssueSeverity.LOW,
                    detail="minor overlap",
                )
            ]
        )

    runner = _runner(hooks={V23Slot.VERIFY: verify_hook})
    state = runner.start(_fresh_state())
    assert state.status == RunStatus.COMPLETE
    assert state.retry_count == 0
