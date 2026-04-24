import pytest
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


def test_er_tier_per_mode_matches_spec():
    d = EquityResearchDepartment()
    assert d.tier_for("stock_initiation") == "thinking"
    assert d.tier_for("sector_research") == "thinking"
    assert d.tier_for("stock_update") == "everyday"


def test_er_tier_for_unknown_mode_raises():
    with pytest.raises(ValueError):
        EquityResearchDepartment().tier_for("bogus")


def test_er_basic_data_requirements():
    reqs = EquityResearchDepartment().data_requirement_types
    assert "stock_quote" in reqs
    assert "company_profile" in reqs
    assert "financial_statements" in reqs


def test_er_optional_data_requirements():
    soft = EquityResearchDepartment().optional_requirement_types
    for name in (
        "company_news",
        "historical_prices",
        "analyst_ratings",
        "insider_transactions",
        "earnings_data",
    ):
        assert name in soft


def test_er_has_no_extra_tools_by_default():
    assert EquityResearchDepartment().extra_tools == ()


def test_er_framework_name_per_mode():
    d = EquityResearchDepartment()
    assert d.framework_name("stock_initiation") == "stock_initiation"
    assert d.framework_name("stock_update") == "stock_update"
    assert d.framework_name("sector_research") == "sector_research"


def test_er_mode_literal_type_import():
    from typing import get_args

    assert set(get_args(EquityResearchMode)) == {
        "stock_initiation",
        "stock_update",
        "sector_research",
    }
