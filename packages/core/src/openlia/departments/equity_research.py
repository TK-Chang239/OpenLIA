from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openlia.departments.base import Tier

EquityResearchMode = Literal["stock_initiation", "stock_update", "sector_research"]


@dataclass(frozen=True)
class EquityResearchDepartment:
    name: str = "equity_research"
    display_name: str = "Equity Research"
    prompt_name: str = "equity_research"
    tier: Tier = "thinking"
    data_requirement_types: tuple[str, ...] = (
        "stock_quote",
        "company_profile",
        "financial_statements",
    )
    optional_requirement_types: tuple[str, ...] = (
        "company_news",
        "historical_prices",
        "analyst_ratings",
        "insider_transactions",
        "earnings_data",
    )
    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[EquityResearchMode, ...] = (
        "stock_initiation",
        "stock_update",
        "sector_research",
    )
