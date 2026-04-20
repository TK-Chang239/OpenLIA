"""Startup-time validation that every department declares its expected slots.

Keeps prompt typos loud: if someone renames `report.stock_initiation.user` to
`report.stock_initiation.user_prompt` without updating ReportRunner, this test
fails in CI instead of failing a user's report generation at runtime.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.prompts import PromptLoader, PromptSlotNotFound

EXPECTED: dict[str, list[str]] = {
    "secretary": ["chat.system"],
    "equity_research": [
        "chat.system",
        "report.system",
        "report.stock_initiation.user",
        "report.stock_update.user",
        "report.sector_research.user",
    ],
    "earnings_update": [
        "report.system",
        "report.earnings_update.user",
    ],
    "morning_briefing": [
        "report.system",
        "report.morning_briefing.user",
    ],
    "macro_research": [
        "batch.t4_assessment.system",
        "batch.t4_assessment.user",
        "batch.t5_assessment.system",
        "batch.t5_assessment.user",
    ],
    "retail_sentiment": [
        "batch.classify_sentiment.system",
        "batch.classify_sentiment.user",
    ],
}


@pytest.mark.parametrize("department_id,slots", list(EXPECTED.items()))
def test_every_department_declares_expected_slots(department_id: str, slots: list[str]) -> None:
    loader = PromptLoader()  # default root: openlia.prompts
    loader.validate_department_slots(department_id, expected=slots)


def test_shared_include_voice_is_rendered_into_secretary_system() -> None:
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system")
    assert "clear, professional tone" in out


def test_shared_include_output_discipline_is_rendered_into_report_system() -> None:
    loader = PromptLoader()
    out = loader.render("equity_research", "report.system", style_guide="x")
    assert "Output discipline" in out


def test_missing_slot_surfaces_prompt_slot_not_found() -> None:
    loader = PromptLoader()
    with pytest.raises(PromptSlotNotFound):
        loader.render("secretary", "report.system")
