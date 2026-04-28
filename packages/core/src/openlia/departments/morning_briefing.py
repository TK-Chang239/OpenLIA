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
    required_categories: ClassVar[tuple[Category, ...]] = (
        Category.FINANCIAL,
        Category.NEWS,
    )
    optional_categories: ClassVar[tuple[Category, ...]] = (Category.WEB_SEARCH,)

    # Runtime behavior (spec §5.2).
    requires_runner: ClassVar[bool] = False
    disable_runtime_routing: ClassVar[bool] = False

    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ("morning_briefing",)
