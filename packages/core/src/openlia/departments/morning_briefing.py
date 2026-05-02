"""Morning Briefing — report-producing department with a single morning_briefing mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from openlia.connectors.types import Category
from openlia.departments.base import Tier


@dataclass(frozen=True)
class MorningBriefingDepartment:
    name: str = "morning_briefing"
    display_name: str = "Morning Briefings"
    prompt_name: str = "morning_briefing"
    tier: Tier = "everyday"

    # Connector dependencies (spec §10.1).
    # Headlines may come from a NEWS provider OR a WEB_SEARCH provider
    # (the LLM can scrape news pages with Firecrawl), so the headline
    # source is expressed as a required-any-of group rather than
    # listing NEWS as a hard requirement.
    required_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL,)
    required_any_of: ClassVar[tuple[tuple[Category, ...], ...]] = (
        (Category.NEWS, Category.WEB_SEARCH),
    )
    optional_categories: ClassVar[tuple[Category, ...]] = ()

    # Runtime behavior (spec §5.2).
    requires_runner: ClassVar[bool] = False
    disable_runtime_routing: ClassVar[bool] = False

    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ("morning_briefing",)
