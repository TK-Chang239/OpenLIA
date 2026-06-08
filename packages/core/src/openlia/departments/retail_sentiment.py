"""Retail Sentiment department — dashboard, no report generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from openlia.connectors.types import Category


@dataclass(frozen=True)
class RetailSentimentDepartment:
    name: str = "retail_sentiment"
    display_name: str = "Retail Sentiment"
    prompt_name: str = "retail_sentiment"
    department_type: str = "dashboard"

    # Connector dependencies (spec §10.1, §9.5). WEB_SEARCH is the required
    # backbone for the web-search-driven sentiment dashboard engine
    # (report_dash_rs). FINANCIAL (live quotes + sentiment endpoints) and NEWS
    # are optional enrichment. RS is dashboard-routed (report_dash_rs via the
    # connector dispatcher), NOT a runner department.
    required_categories: ClassVar[tuple[Category, ...]] = (Category.WEB_SEARCH,)
    optional_categories: ClassVar[tuple[Category, ...]] = (
        Category.FINANCIAL,
        Category.NEWS,
    )
    required_any_of: ClassVar[tuple[tuple[Category, ...], ...]] = ()

    # Runtime behavior: dashboard engine.
    disable_runtime_routing: ClassVar[bool] = False

    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ()
    is_dashboard: bool = True
