"""Tests for Stage 1 Clarifier (Task P1)."""

from unittest.mock import Mock

import pytest
from openlia.llm.runtime.report_v2.pipeline.stage_1_clarify import (
    Clarifier,
    build_clarifier_system_prompt,
)
from openlia.llm.runtime.report_v2.schemas.clarifier import (
    ClarifierOutput,
)


def test_clarifier_output_has_blocking_warnings_field():
    out = ClarifierOutput(
        questions=[],
        blocking_warnings=[],
        notices=[],
        detected_intents=[],
    )
    assert hasattr(out, "blocking_warnings")


def test_clarifier_emits_warning_when_extras_detected_in_prompt():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "questions": [],
        "blocking_warnings": [
            {
                "capability_id": "extra_passes",
                "detected_phrase": "have a devil's advocate pass",
                "user_message": "Extra LLM review/check passes are not supported in this version.",
                "available_actions": ["proceed_without", "cancel_and_edit", "clarify"],
            }
        ],
        "notices": [],
        "detected_intents": ["extras"],
    }
    c = Clarifier(llm=fake_llm)
    out = c.clarify(
        composer_inputs={
            "ticker": "NVDA",
            "prompt": "have a devil's advocate pass after drafting",
        },
        template_spec=Mock(template_id="t1"),
    )
    assert len(out.blocking_warnings) == 1
    assert out.blocking_warnings[0].capability_id == "extra_passes"


def test_clarifier_max_3_rounds():
    c = Clarifier(llm=Mock())
    assert c.MAX_ROUNDS == 3


def test_clarifier_raises_on_round_4():
    fake_llm = Mock()
    c = Clarifier(llm=fake_llm)
    with pytest.raises(ValueError):
        c.clarify(
            composer_inputs={"ticker": "NVDA"},
            template_spec=Mock(template_id="t1"),
            clarification_history=["q1_answer", "q2_answer", "q3_answer"],
        )


def test_system_prompt_includes_engine_version_and_capabilities():
    prompt = build_clarifier_system_prompt()
    assert "2.2" in prompt
    assert "supported" in prompt.lower()
    assert "unsupported" in prompt.lower()
    # at least one capability id from the manifest must appear
    assert "extra_passes" in prompt
    # FAIL LOUD rule must be present
    assert "FAIL LOUD" in prompt
