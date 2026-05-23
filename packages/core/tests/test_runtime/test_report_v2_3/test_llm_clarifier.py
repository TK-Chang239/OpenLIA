"""Unit tests for the provider-agnostic LLMClarifierClient."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.clients.clarifier import ClarifierRequest
from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import (
    SYSTEM_PROMPT,
    LLMClarifierClient,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyNeedsInput,
    ClarifyProceed,
    Language,
    ReportType,
)


def _request() -> ClarifierRequest:
    return ClarifierRequest(
        raw_prompt="write initiation on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )


class _RecordingCall:
    """Captures the (system, user) args and returns a canned JSON object."""

    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    def __call__(self, *, system: str, user: object) -> dict:
        self.calls.append({"system": system, "user": user})
        return self.response


def test_proceed_path_parses_assumptions() -> None:
    fake = _RecordingCall({"outcome": "proceed", "assumptions": ["audience: PM"]})
    client = LLMClarifierClient(fake)

    result = client.clarify(_request())

    assert isinstance(result, ClarifyProceed)
    assert result.assumptions == ["audience: PM"]
    # The system prompt and the structured user payload reach the underlying call.
    assert fake.calls[0]["system"] == SYSTEM_PROMPT
    assert fake.calls[0]["user"] == {
        "raw_prompt": "write initiation on NVDA",
        "language": "en",
        "report_type": "initiation",
        "tickers": ["NVDA"],
    }


def test_needs_input_path_parses_questions() -> None:
    fake = _RecordingCall(
        {
            "outcome": "needs_input",
            "questions": [
                {
                    "id": "horizon",
                    "question": "What investment horizon?",
                    "why_blocking": "Drives the DCF.",
                    "default": "12 months",
                }
            ],
        }
    )
    result = LLMClarifierClient(fake).clarify(_request())
    assert isinstance(result, ClarifyNeedsInput)
    assert len(result.questions) == 1
    assert result.questions[0].id == "horizon"


def test_malformed_response_raises_runtime_error_with_head() -> None:
    fake = _RecordingCall({"outcome": "nonsense"})
    with pytest.raises(RuntimeError, match=r"malformed JSON for ClarifyResult"):
        LLMClarifierClient(fake).clarify(_request())


def test_needs_input_with_too_many_questions_rejected() -> None:
    """MAX_CLARIFY_QUESTIONS is enforced by the schema; the client must
    surface that as a clear failure, not silently truncate."""
    questions = [
        {
            "id": f"q{i}",
            "question": "?",
            "why_blocking": "x",
            "default": "y",
        }
        for i in range(4)
    ]
    fake = _RecordingCall({"outcome": "needs_input", "questions": questions})
    with pytest.raises(RuntimeError, match=r"malformed JSON for ClarifyResult"):
        LLMClarifierClient(fake).clarify(_request())


def test_question_missing_required_field_rejected() -> None:
    fake = _RecordingCall(
        {
            "outcome": "needs_input",
            "questions": [
                {"id": "q1", "question": "?", "default": "y"}  # missing why_blocking
            ],
        }
    )
    with pytest.raises(RuntimeError, match=r"malformed JSON for ClarifyResult"):
        LLMClarifierClient(fake).clarify(_request())
