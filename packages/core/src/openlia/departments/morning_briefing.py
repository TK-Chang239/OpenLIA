"""Morning Briefing — report-producing department with a single morning_briefing mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from openlia.connectors.types import Category


@dataclass(frozen=True)
class MorningBriefingDepartment:
    name: str = "morning_briefing"
    display_name: str = "Morning Briefings"
    prompt_name: str = "morning_briefing"

    # Connector dependencies (spec §10.1). FINANCIAL is the sole hard
    # requirement. Headlines come from the model's native web search by
    # default, so a NEWS provider or a WEB_SEARCH scraping connector (e.g.
    # Firecrawl) is optional enrichment rather than a required-any-of group.
    required_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL,)
    required_any_of: ClassVar[tuple[tuple[Category, ...], ...]] = ()
    optional_categories: ClassVar[tuple[Category, ...]] = (
        Category.NEWS,
        Category.WEB_SEARCH,
    )

    # Runtime behavior (spec §5.2).
    disable_runtime_routing: ClassVar[bool] = False

    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ("morning_briefing",)
