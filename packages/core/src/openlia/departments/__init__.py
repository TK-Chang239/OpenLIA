from openlia.departments.base import Department
from openlia.departments.earnings_update import EarningsUpdateDepartment
from openlia.departments.equity_research import (
    EquityResearchDepartment,
    EquityResearchMode,
)
from openlia.departments.macro_research import MacroResearchDepartment
from openlia.departments.morning_briefing import MorningBriefingDepartment
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


def get_registered_department_ids() -> list[str]:
    """Return the canonical list of registered department ids."""
    return list(_REGISTRY.keys())


def get_enabled_default_tiers(enabled: list[str] | None = None) -> set[str]:
    """Return the union of `DEFAULT_TIER`s for the given enabled department ids.

    When `enabled` is None, returns the union across all registered departments.
    Each department's tier is read from `Department.tier` (a Tier literal).
    Used by the wizard to decide which model tiers must be configured.
    """
    ids = enabled if enabled is not None else list(_REGISTRY.keys())
    out: set[str] = set()
    for name in ids:
        dept = _REGISTRY.get(name)
        if dept is None:
            continue
        tier = getattr(dept, "tier", None)
        if isinstance(tier, str):
            out.add(tier)
    return out


def get_department_data_requirements() -> dict[str, list[str]]:
    """Return a mapping of department id -> required-category value strings.

    Post connector-redesign-v2 (spec §10.1): the unit of "what a dept needs"
    is now `Category` (financial / news / social / web_search), declared on
    the dept's `required_categories` ClassVar. The legacy free-form
    `data_requirement_types` strings have been removed.

    Used by the AI review step of the setup wizard to surface the categories
    each enabled department depends on.
    """
    out: dict[str, list[str]] = {}
    for name, dept in _REGISTRY.items():
        cats = getattr(dept, "required_categories", ())
        out[name] = [c.value for c in cats]
    return out


__all__ = [
    "Department",
    "EarningsUpdateDepartment",
    "EquityResearchDepartment",
    "EquityResearchMode",
    "MacroResearchDepartment",
    "MorningBriefingDepartment",
    "PanicThermometerDepartment",
    "RetailSentimentDepartment",
    "SecretaryDepartment",
    "get_department",
    "get_department_data_requirements",
    "get_enabled_default_tiers",
    "get_registered_department_ids",
]
