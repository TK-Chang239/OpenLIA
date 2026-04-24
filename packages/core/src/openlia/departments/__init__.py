from openlia.departments.base import Department
from openlia.departments.earnings_update import (
    EarningsUpdateDepartment,
    EarningsUpdateMode,
)
from openlia.departments.equity_research import (
    EquityResearchDepartment,
    EquityResearchMode,
)
from openlia.departments.macro_research import MacroResearchDepartment
from openlia.departments.morning_briefing import (
    MorningBriefingDepartment,
    MorningBriefingMode,
)
from openlia.departments.panic_thermometer import PanicThermometerDepartment
from openlia.departments.retail_sentiment import RetailSentimentDepartment
from openlia.departments.secretary import SecretaryDepartment

_REGISTRY: dict[str, Department] = {
    "secretary": SecretaryDepartment(),
    "equity_research": EquityResearchDepartment(),
    "earnings_update": EarningsUpdateDepartment(),
    "morning_briefing": MorningBriefingDepartment(),
    "panic_thermometer": PanicThermometerDepartment(),
    "macro_research": MacroResearchDepartment(),
    "retail_sentiment": RetailSentimentDepartment(),
}


def get_department(name: str) -> Department | None:
    """Return the Department instance for a registered id, or None.

    Used by the chat runtime to pull `extra_tools` (e.g., Secretary's
    `suggest_redirect`) into the tool list and to route their dispatch.
    """
    return _REGISTRY.get(name)


__all__ = [
    "Department",
    "EarningsUpdateDepartment",
    "EarningsUpdateMode",
    "EquityResearchDepartment",
    "EquityResearchMode",
    "MacroResearchDepartment",
    "MorningBriefingDepartment",
    "MorningBriefingMode",
    "PanicThermometerDepartment",
    "RetailSentimentDepartment",
    "SecretaryDepartment",
    "get_department",
]
