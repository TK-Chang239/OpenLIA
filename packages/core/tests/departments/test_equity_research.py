from openlia.connectors.types import Category
from openlia.departments.equity_research import (
    EquityResearchDepartment,
    EquityResearchMode,
)


def test_er_identifies_itself():
    d = EquityResearchDepartment()
    assert d.name == "equity_research"
    assert d.display_name == "Equity Research"
    assert d.prompt_name == "equity_research"


def test_er_exposes_three_modes():
    modes = set(EquityResearchDepartment().valid_modes)
    assert modes == {"stock_initiation", "stock_update", "sector_research"}


def test_er_required_categories():
    # Spec §10.1.
    assert EquityResearchDepartment.required_categories == (Category.FINANCIAL,)


def test_er_optional_categories():
    soft = set(EquityResearchDepartment.optional_categories)
    assert {Category.NEWS, Category.SOCIAL, Category.WEB_SEARCH}.issubset(soft)


def test_er_disable_runtime_routing():
    assert EquityResearchDepartment.disable_runtime_routing is False


def test_er_has_no_extra_tools_by_default():
    assert EquityResearchDepartment().extra_tools == ()


def test_er_mode_literal_type_import():
    from typing import get_args

    assert set(get_args(EquityResearchMode)) == {
        "stock_initiation",
        "stock_update",
        "sector_research",
    }
