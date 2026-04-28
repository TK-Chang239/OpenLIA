"""Earnings Update — report-producing department with a single earnings_analysis mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from openlia.connectors.types import Category
from openlia.departments.base import Tier


@dataclass(frozen=True)
class EarningsUpdateDepartment:
    name: str = "earnings_update"
    display_name: str = "Earnings Updates"
    prompt_name: str = "earnings_update"
    tier: Tier = "everyday"

    # Connector dependencies (spec §10.1).
    required_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL,)
    optional_categories: ClassVar[tuple[Category, ...]] = (Category.NEWS,)

    # Runtime behavior (spec §5.2).
    requires_runner: ClassVar[bool] = False
    disable_runtime_routing: ClassVar[bool] = False

    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ("earnings_analysis",)
