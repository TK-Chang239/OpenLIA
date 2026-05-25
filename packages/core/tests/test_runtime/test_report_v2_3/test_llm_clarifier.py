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
from openlia.llm.runtime.report_v2_3.templates import (
    SectionSpec,
    TemplateSpec,
    get_builtin,
)


def _request() -> ClarifierRequest:
    return ClarifierRequest(
        raw_prompt="write initiation on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
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
    user = fake.calls[0]["user"]
    assert user["raw_prompt"] == "write initiation on NVDA"
    assert user["language"] == "en"
    assert user["tickers"] == ["NVDA"]
    # CLARIFY is fed the template's id + a brief shape description so
    # the LLM can ask questions specific to the chosen template
    # instead of generic ones.
    assert user["template"]["id"] == "initiation"
    assert isinstance(user["template"]["shape"], str)
    assert len(user["template"]["shape"]) > 0


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


def test_clarifier_prompt_no_longer_caps_question_count() -> None:
    """The CLARIFY prompt no longer dictates an arbitrary cap on
    question count (deleted in Phase 2). The LLM judges how many
    questions are genuinely needed."""
    # The exact phrasing that referenced the cap should be gone.
    assert "cap at 3" not in SYSTEM_PROMPT.lower()
    assert "MAX_CLARIFY_QUESTIONS" not in SYSTEM_PROMPT


def test_clarifier_prompt_includes_template_shape_description() -> None:
    """The clarifier prompt must surface the template's
    shape_description so the LLM understands what kind of report the
    user is building. Replaces the hardcoded _BUILTIN_TEMPLATE_SHAPES
    lookup."""
    custom = TemplateSpec(
        template_id="custom_x",
        name="Custom",
        shape_description="UNIQUE_SHAPE_MARKER for prompt assertion.",
        sections=[SectionSpec(id="a", title="A", intent="A section.")],
    )
    req = ClarifierRequest(
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=custom,
    )
    prompt = LLMClarifierClient._build_user_prompt(req)
    assert "UNIQUE_SHAPE_MARKER for prompt assertion." in prompt


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
