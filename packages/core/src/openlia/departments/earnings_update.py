"""Earnings Update — report-producing department with a single earnings_analysis mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openlia.departments.base import Tier


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
    valid_modes: tuple[str, ...] = ("earnings_analysis",)
