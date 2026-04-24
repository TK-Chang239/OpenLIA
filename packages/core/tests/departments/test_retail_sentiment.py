from openlia.departments.retail_sentiment import RetailSentimentDepartment


def test_rs_identifies_itself():
    d = RetailSentimentDepartment()
    assert d.name == "retail_sentiment"
    assert d.display_name == "Retail Sentiment"
    assert d.prompt_name == "retail_sentiment"


def test_rs_tier_is_quick():
    assert RetailSentimentDepartment().tier == "quick"


def test_rs_basic_data_requirements():
    reqs = RetailSentimentDepartment().data_requirement_types
    for name in ("social_sentiment", "company_news", "stock_quote"):
        assert name in reqs


def test_rs_optional_data_requirements():
    soft = RetailSentimentDepartment().optional_requirement_types
    for name in (
        "historical_prices",
        "options_data",
        "short_interest",
        "institutional_holdings",
    ):
        assert name in soft


def test_rs_is_dashboard_department():
    d = RetailSentimentDepartment()
    assert d.department_type == "dashboard"
    assert d.valid_modes == ()


def test_rs_has_no_extra_tools():
    assert RetailSentimentDepartment().extra_tools == ()
