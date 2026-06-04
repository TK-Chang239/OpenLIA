from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from openlia.connectors.types import Category

EquityResearchMode = Literal["stock_initiation", "stock_update", "sector_research"]


@dataclass(frozen=True)
class EquityResearchDepartment:
    name: str = "equity_research"
    display_name: str = "Equity Research"
    prompt_name: str = "equity_research"

    # Connector dependencies (spec §10.1).
    required_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL,)
    optional_categories: ClassVar[tuple[Category, ...]] = (
        Category.NEWS,
        Category.SOCIAL,
        Category.WEB_SEARCH,
    )

    # Runtime behavior (spec §5.2).
    disable_runtime_routing: ClassVar[bool] = False

    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[EquityResearchMode, ...] = (
        "stock_initiation",
        "stock_update",
        "sector_research",
    )
