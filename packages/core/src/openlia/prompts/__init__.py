"""Prompt templates and the canonical department-label map."""

from __future__ import annotations

DEPARTMENT_LABELS: dict[str, str] = {
    "secretary": "Secretary",
    "equity_research": "Equity Research",
    "earnings_update": "Earnings Update",
    "morning_briefing": "Morning Briefing",
    "retail_sentiment": "Retail Sentiment",
    "macro_research": "Macro Research",
    "panic_thermometer": "Panic Thermometer",
}

__all__ = ["DEPARTMENT_LABELS"]
