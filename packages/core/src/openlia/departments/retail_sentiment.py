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

    # Connector dependencies (spec §10.1, §9.5).
    # RS pulls social posts via the financial connectors' sentiment endpoints
    # (EODHD, FMP), so `financial` is the required category, not `social`.
    required_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL,)
    optional_categories: ClassVar[tuple[Category, ...]] = (
        Category.NEWS,
        Category.SOCIAL,
    )

    # Runtime behavior (spec §5.2).
    requires_runner: ClassVar[bool] = True
    disable_runtime_routing: ClassVar[bool] = False

    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ()
    is_dashboard: bool = True
