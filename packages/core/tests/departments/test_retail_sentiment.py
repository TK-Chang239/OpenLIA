from openlia.connectors.types import Category
from openlia.departments.retail_sentiment import RetailSentimentDepartment


def test_rs_identifies_itself():
    d = RetailSentimentDepartment()
    assert d.name == "retail_sentiment"
    assert d.display_name == "Retail Sentiment"
    assert d.prompt_name == "retail_sentiment"


def test_rs_required_categories():
    # Web-search-backbone dashboard: WEB_SEARCH is the sole required category.
    assert RetailSentimentDepartment.required_categories == (Category.WEB_SEARCH,)


def test_rs_optional_categories():
    soft = set(RetailSentimentDepartment.optional_categories)
    assert {Category.FINANCIAL, Category.NEWS}.issubset(soft)


def test_rs_disable_runtime_routing():
    # Dashboard engine.
    assert RetailSentimentDepartment.disable_runtime_routing is False


def test_rs_is_dashboard_department():
    d = RetailSentimentDepartment()
    assert d.department_type == "dashboard"
    assert d.valid_modes == ()


def test_rs_has_no_extra_tools():
    assert RetailSentimentDepartment().extra_tools == ()
