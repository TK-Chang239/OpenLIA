from openlia.departments.base import Department
from openlia.departments.earnings_update import (
    EarningsUpdateDepartment,
    EarningsUpdateMode,
)
from openlia.departments.equity_research import (
    EquityResearchDepartment,
    EquityResearchMode,
)
from openlia.departments.morning_briefing import (
    MorningBriefingDepartment,
    MorningBriefingMode,
)
from openlia.departments.secretary import SecretaryDepartment

_REGISTRY: dict[str, Department] = {
    "secretary": SecretaryDepartment(),
    "equity_research": EquityResearchDepartment(),
    "earnings_update": EarningsUpdateDepartment(),
    "morning_briefing": MorningBriefingDepartment(),
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
    "MorningBriefingDepartment",
    "MorningBriefingMode",
    "SecretaryDepartment",
    "get_department",
]
