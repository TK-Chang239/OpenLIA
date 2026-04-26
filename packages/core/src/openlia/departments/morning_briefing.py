"""Morning Briefing — report-producing department with a single morning_briefing mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openlia.departments.base import Tier


@dataclass(frozen=True)
class MorningBriefingDepartment:
    name: str = "morning_briefing"
    display_name: str = "Morning Briefings"
    prompt_name: str = "morning_briefing"
    tier: Tier = "everyday"
    data_requirement_types: tuple[str, ...] = (
        "company_news",
        "economic_events",
    )
    optional_requirement_types: tuple[str, ...] = (
        "stock_quote",
        "historical_prices",
        "macro_indicator",
    )
    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ("morning_briefing",)
