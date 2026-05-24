"""Unit tests for ReportState — round-trip, suspend, resume, fail, complete."""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyAnswers,
    ClarifyQuestion,
    Language,
    ReportType,
    RunStatus,
)
from openlia.llm.runtime.report_v2_3.slots import V23Slot
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import get_builtin


def _state() -> ReportState:
    return ReportState(
        run_id="run-1",
        user_id="u-1",
        raw_prompt="write an initiation on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
        model_assignments={
            V23Slot.CLARIFY: "claude-sonnet-4-6",
            V23Slot.SYNTHESIZE: "claude-opus-4-7",
        },
    )


def test_report_state_allows_empty_tickers_for_clarify_inference() -> None:
    """Runs started via the single-textarea composer arrive with no
    tickers; CLARIFY extracts them from `raw_prompt` and the runner
    copies `inferred_tickers` onto state.tickers before PLAN."""
    state = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiation on Nvidia",
        language=Language.EN,
        report_type=ReportType.UPDATE,
        tickers=[],
        template=get_builtin(ReportType.UPDATE),
    )
    assert state.tickers == []


def test_report_state_requires_template() -> None:
    """Constructing ReportState without a template must fail loudly —
    every run needs the structure the template provides."""
    import pytest

    with pytest.raises(Exception):  # Pydantic ValidationError or TypeError
        ReportState(
            run_id="r",
            user_id="u",
            raw_prompt="p",
            language=Language.EN,
            report_type=ReportType.INITIATION,
            tickers=["NVDA"],
        )


def test_report_state_carries_template_through_serialization() -> None:
    """The template field must round-trip via the persistence layer."""
    template = get_builtin(ReportType.INITIATION)
    state = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="p",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=template,
    )

    dumped = state.model_dump_json()
    restored = ReportState.model_validate_json(dumped)
    assert restored.template == template


def test_report_state_defaults_running_with_no_current_stage() -> None:
    s = _state()
    assert s.status == RunStatus.RUNNING
    assert s.current_stage is None
    assert s.retry_count == 0


def test_suspend_for_clarify_then_resume() -> None:
    s = _state()
    qs = [
        ClarifyQuestion(
            id="horizon",
            question="horizon?",
            why_blocking="drives model",
            default="12 months",
        )
    ]
    s.suspend_for_clarify(qs)
    assert s.status == RunStatus.WAITING_ON_USER
    assert s.pending_questions == qs

    answers = ClarifyAnswers(answers={"horizon": "24 months"})
    s.resume_with_answers(answers)
    assert s.status == RunStatus.RUNNING
    assert s.pending_questions == []
    assert s.clarify_answers == answers


def test_fail_records_error_message() -> None:
    s = _state()
    s.fail("boom")
    assert s.status == RunStatus.FAILED
    assert s.last_error == "boom"


def test_complete_marks_status() -> None:
    s = _state()
    s.complete()
    assert s.status == RunStatus.COMPLETE


def test_report_state_json_round_trip() -> None:
    s = _state()
    qs = [
        ClarifyQuestion(
            id="horizon",
            question="horizon?",
            why_blocking="drives model",
            default="12 months",
        )
    ]
    s.suspend_for_clarify(qs)
    s.resume_with_answers(ClarifyAnswers(answers={"horizon": "12 months"}))

    payload = s.model_dump_json()
    restored = ReportState.model_validate_json(payload)
    assert restored.run_id == s.run_id
    assert restored.model_assignments[V23Slot.CLARIFY] == "claude-sonnet-4-6"
    assert restored.clarify_answers is not None
    assert restored.clarify_answers.answers == {"horizon": "12 months"}
    assert restored.status == RunStatus.RUNNING
