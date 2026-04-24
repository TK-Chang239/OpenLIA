from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openlia.departments.base import Tier

EquityResearchMode = Literal["stock_initiation", "stock_update", "sector_research"]

_TIER_BY_MODE: dict[str, Tier] = {
    "stock_initiation": "thinking",
    "stock_update": "everyday",
    "sector_research": "thinking",
}


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

    def tier_for(self, mode: str) -> Tier:
        if mode not in _TIER_BY_MODE:
            raise ValueError(f"Unknown equity research mode: {mode}")
        return _TIER_BY_MODE[mode]

    def framework_name(self, mode: str) -> str:
        if mode not in _TIER_BY_MODE:
            raise ValueError(f"Unknown equity research mode: {mode}")
        return mode
