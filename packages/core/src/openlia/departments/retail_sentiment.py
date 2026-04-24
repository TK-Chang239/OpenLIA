"""Retail Sentiment department — dashboard, no report generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openlia.departments.base import Tier


@dataclass(frozen=True)
class RetailSentimentDepartment:
    name: str = "retail_sentiment"
    display_name: str = "Retail Sentiment"
    prompt_name: str = "retail_sentiment"
    department_type: str = "dashboard"
    tier: Tier = "quick"
    data_requirement_types: tuple[str, ...] = (
        "social_sentiment",
        "company_news",
        "stock_quote",
    )
    optional_requirement_types: tuple[str, ...] = (
        "historical_prices",
        "options_data",
        "short_interest",
        "institutional_holdings",
    )
    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ()
    is_dashboard: bool = True
