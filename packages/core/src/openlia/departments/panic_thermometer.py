"""Panic Thermometer — dashboard-only department (no reports, no chat)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanicThermometerDepartment:
    name: str = "panic_thermometer"
    display_name: str = "Panic Thermometer"
    is_dashboard: bool = True
    data_requirement_types: tuple[str, ...] = (
        "historical_prices",
        "stock_quote",
        "economic_events",
    )
    optional_requirement_types: tuple[str, ...] = ("company_news",)
    panel_ids: tuple[str, ...] = (
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    )
    valid_modes: tuple[str, ...] = ()
    extra_tools: tuple[str, ...] = ()
