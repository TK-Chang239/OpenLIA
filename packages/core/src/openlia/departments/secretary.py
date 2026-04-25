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


_SAVE_REPORT_TO_REPO_TOOL: dict[str, Any] = {
    "name": "save_report_to_repo",
    "description": (
        "Save an existing report into the user's repository so they can "
        "find it again later. Provide the report id from the current "
        "conversation context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "report_id": {
                "type": "string",
                "description": "The id of an existing Report owned by the user.",
            }
        },
        "required": ["report_id"],
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
        _SAVE_REPORT_TO_REPO_TOOL,
    )
