"""Panic Thermometer panel registry."""

from openlia.panic_thermometer.panels.base import PanelBase, PanelContextBuildResult
from openlia.panic_thermometer.panels.diplomacy import DiplomacyPanel
from openlia.panic_thermometer.panels.fed_language import FedLanguagePanel
from openlia.panic_thermometer.panels.inflation import InflationPanel
from openlia.panic_thermometer.panels.oil import OilPanel
from openlia.panic_thermometer.panels.wage_growth import WageGrowthPanel

PANELS: dict[str, PanelBase] = {
    "oil": OilPanel(),
    "inflation": InflationPanel(),
    "fed_language": FedLanguagePanel(),
    "wage_growth": WageGrowthPanel(),
    "diplomacy": DiplomacyPanel(),
}

__all__ = [
    "PANELS",
    "DiplomacyPanel",
    "FedLanguagePanel",
    "InflationPanel",
    "OilPanel",
    "PanelBase",
    "PanelContextBuildResult",
    "WageGrowthPanel",
]
