"""Unit tests for ClarifyStage — proceed, suspend, resume-finalize."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.clients.clarifier import (
    ClarifierRequest,
    FakeClarifierClient,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyAnswers,
    ClarifyNeedsInput,
    ClarifyProceed,
    ClarifyQuestion,
    Language,
    ReportType,
    RunStatus,
)
from openlia.llm.runtime.report_v2_3.stages import ClarifyStage, StageContext
from openlia.llm.runtime.report_v2_3.state import ReportState


def _state() -> ReportState:
    return ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="write an initiation on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def test_proceed_path_records_result_and_does_not_suspend() -> None:
    client = FakeClarifierClient(
        result=ClarifyProceed(assumptions=["audience: PM", "horizon: 12 months"])
    )
    stage = ClarifyStage(client)

    state = stage.run(_state(), _ctx())

    assert state.status == RunStatus.RUNNING
    assert isinstance(state.clarify_result, ClarifyProceed)
    assert state.clarify_result.assumptions == ["audience: PM", "horizon: 12 months"]
    assert state.pending_questions == []
    assert len(client.calls) == 1
    assert client.calls[0].raw_prompt == "write an initiation on NVDA"
    assert client.calls[0].tickers == ["NVDA"]


def test_needs_input_path_suspends_with_questions() -> None:
    question = ClarifyQuestion(
        id="horizon",
        question="what horizon?",
        why_blocking="drives the model",
        default="12 months",
    )
    client = FakeClarifierClient(result=ClarifyNeedsInput(questions=[question]))
    stage = ClarifyStage(client)

    state = stage.run(_state(), _ctx())

    assert state.status == RunStatus.WAITING_ON_USER
    assert state.pending_questions == [question]
    # clarify_result is intentionally NOT yet set — finalize happens on resume.
    assert state.clarify_result is None


def test_resume_finalizes_to_proceed_from_answers() -> None:
    """When clarify_answers is present, the stage emits a ClarifyProceed
    whose assumptions reflect resolved answer-or-default values, and does
    NOT re-invoke the client."""
    question = ClarifyQuestion(
        id="horizon",
        question="what horizon?",
        why_blocking="drives the model",
        default="12 months",
    )
    client = FakeClarifierClient(result=ClarifyNeedsInput(questions=[question]))
    stage = ClarifyStage(client)

    # First call — suspend.
    state = stage.run(_state(), _ctx())
    assert state.status == RunStatus.WAITING_ON_USER
    assert len(client.calls) == 1

    # Resume — user answered.
    # The runner normally drives this transition; we set it up by hand here
    # because this test isolates the stage from the runner.
    state.clarify_result = ClarifyNeedsInput(questions=[question])  # what would persist
    state.resume_with_answers(ClarifyAnswers(answers={"horizon": "24 months"}))

    state = stage.run(state, _ctx())

    assert isinstance(state.clarify_result, ClarifyProceed)
    assert state.clarify_result.assumptions == ["horizon: 24 months"]
    # The client is NOT re-invoked.
    assert len(client.calls) == 1


def test_resume_with_partial_answers_uses_defaults() -> None:
    """Unanswered questions should resolve to their stated defaults."""
    q1 = ClarifyQuestion(
        id="horizon",
        question="?",
        why_blocking="model",
        default="12 months",
    )
    q2 = ClarifyQuestion(
        id="audience",
        question="?",
        why_blocking="depth",
        default="PM",
    )
    stage = ClarifyStage(FakeClarifierClient(result=ClarifyProceed()))

    state = _state()
    state.clarify_result = ClarifyNeedsInput(questions=[q1, q2])
    state.suspend_for_clarify([q1, q2])
    state.resume_with_answers(ClarifyAnswers(answers={"audience": "buyside"}))

    state = stage.run(state, _ctx())

    assert isinstance(state.clarify_result, ClarifyProceed)
    assert sorted(state.clarify_result.assumptions) == [
        "audience: buyside",
        "horizon: 12 months",
    ]


def test_proceed_copies_inferred_tickers_when_state_has_none() -> None:
    """Single-textarea path: run starts with tickers=[], CLARIFY extracts
    them from the prompt and the stage copies them onto state.tickers
    so PLAN/RESEARCH see a populated subject list."""
    state = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="write an initiation on Nvidia, focus on AI infra margins",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=[],
    )
    client = FakeClarifierClient(
        result=ClarifyProceed(inferred_tickers=["NVDA"], assumptions=["focus: AI"])
    )
    stage = ClarifyStage(client)

    state = stage.run(state, _ctx())

    assert state.tickers == ["NVDA"]
    assert isinstance(state.clarify_result, ClarifyProceed)
    assert state.clarify_result.inferred_tickers == ["NVDA"]


def test_proceed_does_not_overwrite_explicit_tickers() -> None:
    """When the caller pinned tickers explicitly (two-field path), the
    stage must NOT replace them even if the LLM returned a different
    inferred list — the caller's choice wins."""
    state = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiation on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )
    client = FakeClarifierClient(
        result=ClarifyProceed(inferred_tickers=["AMD"])  # disagreement
    )
    stage = ClarifyStage(client)

    state = stage.run(state, _ctx())

    assert state.tickers == ["NVDA"]


def test_resume_with_ticker_answer_populates_state_tickers() -> None:
    """When CLARIFY suspended asking for the subject ticker, the resume
    path must lift the answer onto state.tickers so the run can continue."""
    q = ClarifyQuestion(
        id="ticker",
        question="Which ticker should this report cover?",
        why_blocking="pipeline needs a subject",
        default="SPY",
    )
    stage = ClarifyStage(FakeClarifierClient(result=ClarifyProceed()))

    state = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="report on the AI infra space",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=[],
    )
    state.clarify_result = ClarifyNeedsInput(questions=[q])
    state.suspend_for_clarify([q])
    state.resume_with_answers(ClarifyAnswers(answers={"ticker": "NVDA AMD"}))

    state = stage.run(state, _ctx())

    assert state.tickers == ["NVDA", "AMD"]
    assert isinstance(state.clarify_result, ClarifyProceed)


def test_fake_clarifier_rejects_double_config() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        FakeClarifierClient(
            result=ClarifyProceed(),
            responder=lambda req: ClarifyProceed(),
        )
    with pytest.raises(ValueError, match="exactly one"):
        FakeClarifierClient()  # type: ignore[call-arg]


def test_fake_clarifier_responder_varies_by_call() -> None:
    """Useful for tests where CLARIFY suspends on call 1 and proceeds on call 2."""
    seq: list[ClarifyProceed | ClarifyNeedsInput] = [
        ClarifyNeedsInput(
            questions=[
                ClarifyQuestion(
                    id="q1",
                    question="?",
                    why_blocking="x",
                    default="y",
                )
            ]
        ),
        ClarifyProceed(assumptions=["resolved"]),
    ]
    client = FakeClarifierClient(responder=lambda req: seq.pop(0))

    req = ClarifierRequest(
        raw_prompt="p",
        language=Language.EN,
        report_type=ReportType.UPDATE,
        tickers=["X"],
    )
    assert isinstance(client.clarify(req), ClarifyNeedsInput)
    assert isinstance(client.clarify(req), ClarifyProceed)
