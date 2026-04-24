"""Registry of all five MR dashboards."""

from __future__ import annotations

from openlia.macro_research.dashboards.all_weather import AllWeatherDashboard
from openlia.macro_research.dashboards.base import Dashboard
from openlia.macro_research.dashboards.debt_cycle import DebtCycleDashboard
from openlia.macro_research.dashboards.five_forces import FiveForcesDashboard
from openlia.macro_research.dashboards.four_seasons import FourSeasonsDashboard
from openlia.macro_research.dashboards.world_order import WorldOrderDashboard

DASHBOARDS: dict[str, Dashboard] = {
    "debt_cycle": DebtCycleDashboard(),
    "four_seasons": FourSeasonsDashboard(),
    "all_weather": AllWeatherDashboard(),
    "world_order": WorldOrderDashboard(),
    "five_forces": FiveForcesDashboard(),
}

__all__ = ["DASHBOARDS", "Dashboard"]
