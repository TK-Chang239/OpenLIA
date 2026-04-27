from pathlib import Path

from openlia.connectors.scope import DepartmentRequirements
from openlia.departments.base import Department
from openlia.departments.earnings_update import EarningsUpdateDepartment
from openlia.departments.equity_research import (
    EquityResearchDepartment,
    EquityResearchMode,
)
from openlia.departments.macro_research import MacroResearchDepartment
from openlia.departments.morning_briefing import MorningBriefingDepartment
from openlia.departments.panic_thermometer import PanicThermometerDepartment
from openlia.departments.requirements_loader import load_department_requirements
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
    """Return a mapping of department id -> required data requirement types.

    Used by the AI review step of the setup wizard to feed the LLM the
    data that each enabled department needs.
    """
    out: dict[str, list[str]] = {}
    for name, dept in _REGISTRY.items():
        reqs = getattr(dept, "data_requirement_types", ())
        out[name] = list(reqs)
    return out


_DEPT_REQUIREMENTS_DIR = Path(__file__).parent

_DEPT_TO_REQUIREMENTS_FILE: dict[str, str] = {
    "secretary": "secretary.requirements.yaml",
    "equity_research": "equity_research.requirements.yaml",
    "earnings_update": "earnings_update.requirements.yaml",
    "morning_briefing": "morning_briefing.requirements.yaml",
    "retail_sentiment": "retail_sentiment.requirements.yaml",
    "macro_research": "macro_research.requirements.yaml",
    "panic_thermometer": "panic_thermometer.requirements.yaml",
}


def get_all_requirements() -> dict[str, DepartmentRequirements]:
    """Load every existing department requirements YAML.

    YAML files that don't exist yet (during the connector-redesign rollout)
    are silently skipped. Tasks D2-D8 fill them in.
    """

    out: dict[str, DepartmentRequirements] = {}
    for dep_id, fname in _DEPT_TO_REQUIREMENTS_FILE.items():
        path = _DEPT_REQUIREMENTS_DIR / fname
        if path.exists():
            out[dep_id] = load_department_requirements(dep_id, path)
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
    "get_all_requirements",
    "get_department",
    "get_department_data_requirements",
    "get_enabled_default_tiers",
    "get_registered_department_ids",
]
