"""Earnings Update — report-producing department with a single earnings_analysis mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openlia.departments.base import Tier

EarningsUpdateMode = Literal["earnings_analysis"]


@dataclass(frozen=True)
class EarningsUpdateDepartment:
    name: str = "earnings_update"
    display_name: str = "Earnings Updates"
    prompt_name: str = "earnings_update"
    tier: Tier = "everyday"
    data_requirement_types: tuple[str, ...] = (
        "earnings_data",
        "financial_statements",
        "stock_quote",
    )
    optional_requirement_types: tuple[str, ...] = (
        "earnings_transcripts",
        "company_news",
        "historical_prices",
        "analyst_ratings",
    )
    extra_tools: tuple[dict[str, Any], ...] = ()

    @property
    def valid_modes(self) -> tuple[EarningsUpdateMode, ...]:
        return ("earnings_analysis",)

    def tier_for(self, mode: str) -> Tier:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown EU mode: {mode}")
        return "everyday"

    def framework_name(self, mode: str) -> str:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown EU mode: {mode}")
        return "earnings_update"
