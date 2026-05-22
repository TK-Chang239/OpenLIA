"""Tests for PR 0.2: 8 helper migrations into v2.2 schema.

Covers:
- All 8 helpers register successfully on import (boot test)
- Produced artifact types all exist in the ArtifactType registry
- Implementations are the same callables as in report_v2 (re-export check)
- Eager registration: importing the library_helpers package registers all 8
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers: expected names and their report_v2 impl import paths
# ---------------------------------------------------------------------------

HELPER_NAMES = [
    "budget_variance",
    "business_investment",
    "chart_builder",
    "dcf_valuation",
    "excel_builder",
    "forecast_builder",
    "ratio_calculator",
    "saas_metrics",
]

# Map v2.2 name -> (report_v2 module path, function name in that module)
_V2_IMPL_MAP = {
    "budget_variance": (
        "openlia.llm.runtime.report_v2.tools.library_helpers.budget_variance",
        "execute",
    ),
    "business_investment": (
        "openlia.llm.runtime.report_v2.tools.library_helpers.business_investment",
        "execute",
    ),
    "chart_builder": (
        "openlia.llm.runtime.report_v2.tools.library_helpers.chart_builder",
        "execute",
    ),
    "dcf_valuation": (
        "openlia.llm.runtime.report_v2.tools.library_helpers.dcf_valuation",
        "execute",
    ),
    "excel_builder": (
        "openlia.llm.runtime.report_v2.tools.library_helpers.excel_builder",
        "execute",
    ),
    "forecast_builder": (
        "openlia.llm.runtime.report_v2.tools.library_helpers.forecast_builder",
        "execute",
    ),
    "ratio_calculator": (
        "openlia.llm.runtime.report_v2.tools.library_helpers.ratio_calculator",
        "execute",
    ),
    "saas_metrics": (
        "openlia.llm.runtime.report_v2.tools.library_helpers.saas_metrics",
        "execute",
    ),
}


# ---------------------------------------------------------------------------
# Eager registration: importing the package triggers all 8 registrations
# ---------------------------------------------------------------------------


def test_eager_registration_all_8_present() -> None:
    """Importing library_helpers package registers all 8 helpers at boot."""
    import openlia.llm.runtime.report_v2_2.tools.library_helpers as lh

    registered_names = {h.schema.directory.name for h in lh.list_helpers()}
    for name in HELPER_NAMES:
        assert name in registered_names, f"Helper {name!r} not found in registry after boot"


# ---------------------------------------------------------------------------
# Per-helper: get_helper returns a valid RegisteredHelper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", HELPER_NAMES)
def test_get_helper_returns_registered(name: str) -> None:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None, f"get_helper({name!r}) returned None"
    assert h.schema.directory.name == name


# ---------------------------------------------------------------------------
# Per-helper: produces_artifacts all exist in ArtifactType registry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", HELPER_NAMES)
def test_produced_artifact_types_in_registry(name: str) -> None:
    from openlia.llm.runtime.report_v2_2.artifact_types import _registry as art_reg
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None
    for artifact_id in h.schema.contract.produces_artifacts:
        assert art_reg.get(artifact_id) is not None, (
            f"Helper {name!r} declares artifact_type {artifact_id!r} "
            "which is not in the ArtifactType registry"
        )


# ---------------------------------------------------------------------------
# Re-export check: v2.2 impl IS the report_v2 execute function (no copy)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", HELPER_NAMES)
def test_impl_is_report_v2_execute(name: str) -> None:
    import importlib

    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None

    module_path, fn_name = _V2_IMPL_MAP[name]
    v2_module = importlib.import_module(module_path)
    original_impl = getattr(v2_module, fn_name)

    assert h.impl is original_impl, (
        f"Helper {name!r}: v2.2 impl is not the same object as report_v2 {fn_name}. "
        "Wrapper must import-and-bind, not copy."
    )


# ---------------------------------------------------------------------------
# Schema structural checks: category, version, produces_artifacts non-empty
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", HELPER_NAMES)
def test_schema_is_well_formed(name: str) -> None:
    from openlia.llm.runtime.report_v2_2.enums import Category
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None
    schema = h.schema

    assert schema.version, f"{name}: version must be set"
    assert isinstance(schema.directory.category, Category), (
        f"{name}: category must be a Category enum value"
    )
    assert schema.directory.one_liner, f"{name}: one_liner must not be empty"
    assert len(schema.contract.produces_artifacts) >= 1, (
        f"{name}: must declare at least one produces_artifacts entry"
    )
    assert schema.contract.params, f"{name}: params must not be empty"


# ---------------------------------------------------------------------------
# Artifact type registry count: 4 Stage-7a + 8 helper-produced = 12
# ---------------------------------------------------------------------------


def test_artifact_type_registry_count() -> None:
    from openlia.llm.runtime.report_v2_2.artifact_types import _registry

    all_types = _registry.list_all()
    names = [t.name for t in all_types]
    # 4 Stage-7a + 8 original helpers (PR 0.2) + 18 EODHD adapters (PR 1.1)
    # + 15 FinanceToolkit helpers + 1 FRED helper (PR 1.2)
    # + 1 comparables_output (PR 2.1)
    # + 6 DCF/COC/sensitivity bundle (PR 2.2)
    # + 3 alternative valuation (PR 2.3): ddm_output, justified_multiples_output, sotp_output
    # + 6 decision layer (PR 2.4): price_target_blended, expected_total_return_output,
    #   risk_reward_output, implied_upside_downside_output, rating_assignment,
    #   football_field_chart_output
    # + 20 business quality bundle (PR 2.5)
    # + 4 forensic/credit integrity (PR 2.6): altman_z_variants_output, dividend_safety_output,
    #   beneish_m_score_output, statement_integrity_bundle_output
    # + 3 credit/solvency (PR 2.7): credit_solvency_output, five_step_dupont_output,
    #   debt_maturity_ladder_output
    # + 3 signals (PR 2.8): insider_signal_output, moving_average_panel_output,
    #   historical_multiple_trends_output
    # + 1 SaaS KPI panel (PR 2.9): saas_kpi_panel_output
    # + 1 output bundle (PR 2.10): waterfall_chart_output
    # + 3 risk/macro (PR 2.11): drawdown_panel_output, yield_curve_shape_output,
    #   commodity_exposure_output
    # + 1 sector banks (PR 3.1): banks_sector_panel_output
    # + 1 sector REITs (PR 3.2): reit_valuation_panel_output
    # + 1 sector pharma (PR 3.3): rnpv_pipeline_output
    # = 100
    assert len(all_types) == 100, f"Expected 100 artifact types, got {len(all_types)}: {names}"


def test_artifact_type_registry_contains_expected_names() -> None:
    from openlia.llm.runtime.report_v2_2.artifact_types import _registry

    expected = {
        # Stage-7a core
        "section_plan",
        "materialized_section",
        "fidelity_hint",
        "rendered_artifact",
        # Helper-produced (PR 0.2)
        "dcf_valuation_output",
        "chart_artifact",
        "ratio_panel",
        "saas_metrics_output",
        "budget_variance_output",
        "business_investment_output",
        "forecast_output",
        "workbook_artifact",
        # EODHD adapters (PR 1.1)
        "eodhd_fundamentals_output",
        "eodhd_balance_sheet_output",
        "eodhd_income_statement_output",
        "eodhd_cash_flow_output",
        "eodhd_eod_prices_output",
        "eodhd_intraday_output",
        "eodhd_real_time_quote_output",
        "eodhd_dividends_output",
        "eodhd_splits_output",
        "eodhd_market_cap_history_output",
        "eodhd_insider_transactions_output",
        "eodhd_news_output",
        "eodhd_sentiment_output",
        "eodhd_company_info_output",
        "eodhd_earnings_history_output",
        "eodhd_upcoming_earnings_output",
        "eodhd_technical_indicators_output",
        "eodhd_macro_indicator_output",
        # FinanceToolkit ratio helpers (PR 1.2)
        "ft_liquidity_ratios_output",
        "ft_solvency_ratios_output",
        "ft_profitability_ratios_output",
        "ft_efficiency_ratios_output",
        "ft_valuation_ratios_output",
        "ft_dupont_output",
        "ft_altman_z_score_output",
        "ft_piotroski_f_score_output",
        "ft_growth_metrics_output",
        "ft_per_share_metrics_output",
        "ft_cash_flow_metrics_output",
        "ft_dividend_metrics_output",
        "ft_working_capital_metrics_output",
        "ft_capital_structure_output",
        "ft_quality_metrics_output",
        # FRED credit spreads (PR 1.2)
        "fred_credit_spreads_output",
        # Comparables suite (PR 2.1)
        "comparables_output",
        # DCF engine + cost of capital + sensitivity bundle (PR 2.2)
        "cost_of_capital_output",
        "dcf_output",
        "sensitivity_matrix",
        "tornado_diagram_output",
        "scenario_panel",
        "reverse_dcf_output",
        # Alternative valuation helpers (PR 2.3)
        "ddm_output",
        "justified_multiples_output",
        "sotp_output",
        # Decision layer helpers (PR 2.4)
        "price_target_blended",
        "expected_total_return_output",
        "risk_reward_output",
        "implied_upside_downside_output",
        "rating_assignment",
        "football_field_chart_output",
        # Business quality bundle (PR 2.5)
        "roic_panel_output",
        "quality_of_earnings_output",
        "capital_allocation_history_output",
        "earnings_surprise_tracker_output",
        "analyst_revision_momentum_output",
        "common_size_statements_output",
        "fcf_conversion_output",
        "total_shareholder_yield_output",
        "cross_statement_validation_output",
        "one_time_item_output",
        "organic_vs_inorganic_growth_output",
        "currency_neutral_growth_output",
        "margin_trajectory_output",
        "operating_leverage_output",
        "sbc_intensity_output",
        "cap_table_dilution_output",
        "piotroski_f_score_output",
        "cash_conversion_cycle_output",
        "sustainable_growth_rate_output",
        "forensic_panel_output",
        # Forensic / credit integrity helpers (PR 2.6)
        "altman_z_variants_output",
        "dividend_safety_output",
        "beneish_m_score_output",
        "statement_integrity_bundle_output",
        # Credit / solvency helpers (PR 2.7)
        "credit_solvency_output",
        "five_step_dupont_output",
        "debt_maturity_ladder_output",
        # Signals helpers (PR 2.8)
        "insider_signal_output",
        "moving_average_panel_output",
        "historical_multiple_trends_output",
        # SaaS KPI panel (PR 2.9)
        "saas_kpi_panel_output",
        # Output bundle (PR 2.10)
        "waterfall_chart_output",
        # Risk / macro helpers (PR 2.11)
        "drawdown_panel_output",
        "yield_curve_shape_output",
        "commodity_exposure_output",
        # Sector modules Wave 1 (PR 3.1)
        "banks_sector_panel_output",
        # Sector modules Wave 1 (PR 3.2)
        "reit_valuation_panel_output",
        # Sector modules Wave 1 (PR 3.3)
        "rnpv_pipeline_output",
    }
    registered = {t.name for t in _registry.list_all()}
    assert expected == registered, (
        f"Missing: {expected - registered}; Extra: {registered - expected}"
    )


# ---------------------------------------------------------------------------
# DAG still passes after adding workbook_artifact
# ---------------------------------------------------------------------------


def test_dag_validation_passes() -> None:
    from openlia.llm.runtime.report_v2_2.artifact_types import _registry

    # Should not raise
    _registry.validate_dag()


# ---------------------------------------------------------------------------
# Callable: impl can be called with valid minimal params (smoke tests)
# ---------------------------------------------------------------------------


def test_ratio_calculator_callable() -> None:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("ratio_calculator")
    assert h is not None
    result = h.impl(income_statement={"revenue": 1000, "net_income": 100})
    assert "categories" in result
    assert "profitability" in result["categories"]


def test_saas_metrics_callable() -> None:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("saas_metrics")
    assert h is not None
    result = h.impl(mode="metrics", mrr=100000, customers=500)
    assert "MRR" in result or "ARR" in result


def test_dcf_valuation_callable() -> None:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("dcf_valuation")
    assert h is not None
    result = h.impl(base_revenue=[100.0, 110.0, 121.0])
    assert "wacc" in result
    assert "value_per_share" in result


def test_budget_variance_callable() -> None:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("budget_variance")
    assert h is not None
    line_items = [
        {
            "name": "Revenue",
            "type": "revenue",
            "department": "Sales",
            "category": "Core",
            "actual": 1100,
            "budget": 1000,
        }
    ]
    result = h.impl(line_items=line_items)
    assert "executive_summary" in result
    assert "all_variances" in result


def test_business_investment_callable() -> None:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("business_investment")
    assert h is not None
    result = h.impl(
        total_investment=500000,
        annual_net_cash_flow=150000,
        useful_life_years=5,
    )
    assert "summary" in result
    assert "scoring" in result


def test_forecast_builder_callable() -> None:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("forecast_builder")
    assert h is not None
    result = h.impl(historical_periods=[{"revenue": 100}, {"revenue": 110}, {"revenue": 121}])
    assert "trend_analysis" in result
    assert "scenario_comparison" in result
