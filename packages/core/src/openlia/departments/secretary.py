from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openlia.departments.base import Tier


_SUGGEST_REDIRECT_TOOL: dict[str, Any] = {
    "name": "suggest_redirect",
    "description": (
        "Suggest that the user move to a specialist department for tasks "
        "that need a full report, dashboard, or automated monitoring."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "department": {
                "type": "string",
                "enum": [
                    "equity_research",
                    "earnings_update",
                    "morning_briefing",
                    "retail_sentiment",
                    "macro_research",
                    "portfolio",
                ],
            },
            "reason": {
                "type": "string",
                "description": "One short sentence explaining why this department fits.",
            },
            "prefill": {
                "type": "string",
                "description": "Optional payload to preload (usually a ticker).",
            },
        },
        "required": ["department", "reason"],
        "additionalProperties": False,
    },
}


@dataclass(frozen=True)
class SecretaryDepartment:
    name: str = "secretary"
    display_name: str = "Secretary"
    prompt_name: str = "secretary"
    tier: Tier = "everyday"
    data_requirement_types: tuple[str, ...] = (
        "stock_quote",
        "company_profile",
    )
    optional_requirement_types: tuple[str, ...] = (
        "company_news",
        "historical_prices",
        "economic_events",
    )
    extra_tools: tuple[dict[str, Any], ...] = (
        _SUGGEST_REDIRECT_TOOL,
    )
