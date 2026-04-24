from __future__ import annotations


def test_package_imports() -> None:
    from openlia.macro_research import (
        DashboardResult,
        DashboardTierOutput,
        MRSnapshot,
    )

    assert MRSnapshot is not None
    assert DashboardResult is not None
    assert DashboardTierOutput is not None


def test_base_protocol_present() -> None:
    from openlia.macro_research.dashboards.base import Dashboard

    # Protocol attributes live on __annotations__.
    assert "slug" in Dashboard.__annotations__


def test_registry_exports_five_dashboards() -> None:
    from openlia.macro_research.dashboards import DASHBOARDS

    assert set(DASHBOARDS.keys()) == {
        "debt_cycle",
        "four_seasons",
        "all_weather",
        "world_order",
        "five_forces",
    }


def test_department_registered() -> None:
    from openlia.departments import get_department
    from openlia.departments.macro_research import MacroResearchDepartment

    dept = get_department("macro_research")
    assert isinstance(dept, MacroResearchDepartment)


def test_department_metadata() -> None:
    from openlia.departments.macro_research import MacroResearchDepartment

    dept = MacroResearchDepartment()
    assert dept.slug == "macro_research"
    assert dept.display_name == "Macro Research"
    assert dept.has_chat is False
    assert set(dept.dashboard_slugs()) == {
        "debt_cycle",
        "four_seasons",
        "all_weather",
        "world_order",
        "five_forces",
    }
