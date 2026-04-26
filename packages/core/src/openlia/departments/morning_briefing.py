"""Morning Briefing — report-producing department with a single morning_briefing mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openlia.departments.base import Tier

MorningBriefingMode = Literal["morning_briefing"]


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

    @property
    def valid_modes(self) -> tuple[MorningBriefingMode, ...]:
        return ("morning_briefing",)

    def tier_for(self, mode: str) -> Tier:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown MB mode: {mode}")
        return "everyday"

    def framework_name(self, mode: str) -> str:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown MB mode: {mode}")
        return "morning_briefing"
