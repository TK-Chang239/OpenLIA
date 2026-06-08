"""Panic Thermometer — dashboard-only department (no reports, no chat)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from openlia.connectors.types import Category


@dataclass(frozen=True)
class PanicThermometerDepartment:
    name: str = "panic_thermometer"
    display_name: str = "Panic Thermometer"
    is_dashboard: bool = True

    # Connector dependencies (spec §10.1).
    required_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL,)
    optional_categories: ClassVar[tuple[Category, ...]] = (Category.NEWS,)

    # Runtime behavior (spec §5.2). PT is dashboard-only with no chat surface
    # today; runtime routing flag stays False.
    disable_runtime_routing: ClassVar[bool] = False

    panel_ids: tuple[str, ...] = (
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    )
    valid_modes: tuple[str, ...] = ()
    extra_tools: tuple[str, ...] = ()
