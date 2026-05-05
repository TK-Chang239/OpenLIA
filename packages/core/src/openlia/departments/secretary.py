from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from openlia.connectors.types import Category
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

    # Connector dependencies (spec §10.1). Secretary now answers questions
    # itself end-to-end, so it claims every connector category any
    # department uses — all optional, so it stays zero-config and never
    # gets disabled by a missing provider.
    required_categories: ClassVar[tuple[Category, ...]] = ()
    optional_categories: ClassVar[tuple[Category, ...]] = (
        Category.FINANCIAL,
        Category.NEWS,
        Category.SOCIAL,
        Category.WEB_SEARCH,
    )

    # Runtime behavior (spec §5.2).
    requires_runner: ClassVar[bool] = False
    disable_runtime_routing: ClassVar[bool] = False

    extra_tools: tuple[dict[str, Any], ...] = (
        _SUGGEST_REDIRECT_TOOL,
        _SAVE_REPORT_TO_REPO_TOOL,
    )
