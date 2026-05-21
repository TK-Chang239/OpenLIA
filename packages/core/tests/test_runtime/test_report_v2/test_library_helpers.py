from __future__ import annotations

# Import all helper modules so registration side-effects fire.
import openlia.llm.runtime.report_v2.tools.library_helpers.budget_variance
import openlia.llm.runtime.report_v2.tools.library_helpers.business_investment
import openlia.llm.runtime.report_v2.tools.library_helpers.chart_builder
import openlia.llm.runtime.report_v2.tools.library_helpers.dcf_valuation
import openlia.llm.runtime.report_v2.tools.library_helpers.excel_builder
import openlia.llm.runtime.report_v2.tools.library_helpers.forecast_builder
import openlia.llm.runtime.report_v2.tools.library_helpers.ratio_calculator
import openlia.llm.runtime.report_v2.tools.library_helpers.saas_metrics  # noqa: F401
import pytest
from openlia.llm.runtime.report_v2.tools.library_helpers import (
    get_helper,
    list_helpers,
    register_deferred_categories,
)


def test_vendored_helpers_registered():
    names = {h.schema.name for h in list_helpers()}
    for required in (
        "dcf_valuation",
        "ratio_calculator",
        "forecast_builder",
        "budget_variance",
        "business_investment",
        "saas_metrics",
        "make_chart",
        "make_excel",
    ):
        assert required in names, f"helper {required!r} not registered"


def test_deferred_categories_marked_unavailable():
    register_deferred_categories()
    assert get_helper("var_calculator").available is False
    assert get_helper("var_calculator").deferred_category == "risk_metrics"


def test_deferred_helper_raises_when_executed():
    register_deferred_categories()
    h = get_helper("var_calculator")
    with pytest.raises(NotImplementedError):
        h.execute()


def test_dcf_helper_schema_has_required_params():
    h = get_helper("dcf_valuation")
    p = h.schema.params
    assert "base_revenue" in p
    assert p["base_revenue"].required
