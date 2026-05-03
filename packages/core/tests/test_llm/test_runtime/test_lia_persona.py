"""Tests for the Lia persona wiring: department labels and identity partial."""

from __future__ import annotations

from openlia.prompts import DEPARTMENT_LABELS


def test_department_labels_cover_all_seven_desks() -> None:
    expected = {
        "secretary": "Secretary",
        "equity_research": "Equity Research",
        "earnings_update": "Earnings Update",
        "morning_briefing": "Morning Briefing",
        "retail_sentiment": "Retail Sentiment",
        "macro_research": "Macro Research",
        "panic_thermometer": "Panic Thermometer",
    }
    assert DEPARTMENT_LABELS == expected
