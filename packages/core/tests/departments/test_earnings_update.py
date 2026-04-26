from openlia.departments.earnings_update import EarningsUpdateDepartment


def test_eu_identifies_itself():
    d = EarningsUpdateDepartment()
    assert d.name == "earnings_update"
    assert d.display_name == "Earnings Updates"
    assert d.prompt_name == "earnings_update"


def test_eu_single_mode():
    assert set(EarningsUpdateDepartment().valid_modes) == {"earnings_analysis"}


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


def test_eu_has_no_extra_tools():
    assert EarningsUpdateDepartment().extra_tools == ()


def test_eu_tier_is_everyday():
    assert EarningsUpdateDepartment().tier == "everyday"
