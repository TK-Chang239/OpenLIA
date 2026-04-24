import pytest

from openlia.departments.earnings_update import (
    EarningsUpdateDepartment,
    EarningsUpdateMode,
)


def test_eu_identifies_itself():
    d = EarningsUpdateDepartment()
    assert d.name == "earnings_update"
    assert d.display_name == "Earnings Updates"
    assert d.prompt_name == "earnings_update"


def test_eu_single_mode():
    assert set(EarningsUpdateDepartment().valid_modes) == {"earnings_analysis"}


def test_eu_tier_is_everyday():
    d = EarningsUpdateDepartment()
    assert d.tier_for("earnings_analysis") == "everyday"


def test_eu_tier_for_unknown_mode_raises():
    with pytest.raises(ValueError):
        EarningsUpdateDepartment().tier_for("bogus")


def test_eu_basic_data_requirements():
    reqs = EarningsUpdateDepartment().data_requirement_types
    for name in ("earnings_data", "financial_statements", "stock_quote"):
        assert name in reqs


def test_eu_optional_data_requirements():
    soft = EarningsUpdateDepartment().optional_requirement_types
    for name in (
        "earnings_transcripts",
        "company_news",
        "historical_prices",
        "analyst_ratings",
    ):
        assert name in soft


def test_eu_framework_name():
    assert EarningsUpdateDepartment().framework_name("earnings_analysis") == "earnings_update"


def test_eu_has_no_extra_tools():
    assert EarningsUpdateDepartment().extra_tools == ()


def test_eu_mode_literal_type():
    from typing import get_args
    assert set(get_args(EarningsUpdateMode)) == {"earnings_analysis"}
