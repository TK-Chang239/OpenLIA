"""Tests for saas_kpi_panel helper (PR 2.9).

Covers:
- ARR YoY and QoQ growth computed from known inputs
- NRR classification thresholds
- GRR classification + implied churn rate = 1 - GRR
- Magic Number = ΔARR / S&M_prior (audit-fix formula, no x4)
- Magic Number derived from arr_prior_quarter fallback
- Magic Number using explicit new_arr_this_quarter
- Rule of 40 = revenue_growth_pct + fcf_margin_pct
- LTV/CAC computed from known inputs
- Billings = Revenue + delta_deferred_revenue
- Composite health score present and in [0, 1]
- saas_metrics wrapper has deprecated_at_version="0.2.0"
- saas_kpi_panel registered as its own helper (not a wrapper)
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _get(name: str):
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None, f"Helper {name!r} not registered"
    return h


def _run(name: str, **kwargs):
    return _get(name).impl(**kwargs)


def _schema(name: str):
    return _get(name).schema


# ---------------------------------------------------------------------------
# ARR
# ---------------------------------------------------------------------------


class TestARR:
    def test_yoy_growth(self) -> None:
        """ARR $1.2B, prior year $0.9B → YoY +33.33%."""
        result = _run("saas_kpi_panel", arr_current=1_200_000, arr_prior_year=900_000)
        arr = result["arr"]
        assert arr["current"] == 1_200_000
        assert arr["yoy_growth_pct"] == pytest.approx(1 / 3, rel=1e-4)

    def test_qoq_growth(self) -> None:
        """ARR $1.2B, prior Q $1.12B → QoQ +7.14%."""
        result = _run("saas_kpi_panel", arr_current=1_200_000, arr_prior_quarter=1_120_000)
        arr = result["arr"]
        assert arr["qoq_growth_pct"] == pytest.approx(80_000 / 1_120_000, rel=1e-4)

    def test_arr_disclosed(self) -> None:
        result = _run("saas_kpi_panel", arr_current=500_000)
        assert result["arr"]["disclosed"] is True

    def test_no_prior_year_no_yoy(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000)
        assert result["arr"]["yoy_growth_pct"] is None

    def test_no_prior_quarter_no_qoq(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000)
        assert result["arr"]["qoq_growth_pct"] is None


# ---------------------------------------------------------------------------
# NRR
# ---------------------------------------------------------------------------


class TestNRR:
    def test_nrr_best_in_class(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000, nrr=1.25)
        assert result["nrr"]["classification"] == "best_in_class"

    def test_nrr_strong(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000, nrr=1.15)
        assert result["nrr"]["classification"] == "strong"

    def test_nrr_stable(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000, nrr=1.05)
        assert result["nrr"]["classification"] == "stable"

    def test_nrr_shrinking(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000, nrr=0.92)
        assert result["nrr"]["classification"] == "shrinking"

    def test_nrr_missing_returns_none(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000)
        assert result["nrr"] is None


# ---------------------------------------------------------------------------
# GRR + implied churn
# ---------------------------------------------------------------------------


class TestGRR:
    def test_grr_strong(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000, grr=0.97)
        assert result["grr"]["classification"] == "strong"

    def test_grr_moderate(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000, grr=0.92)
        assert result["grr"]["classification"] == "moderate"

    def test_grr_weak(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000, grr=0.85)
        assert result["grr"]["classification"] == "weak"

    def test_implied_churn_rate(self) -> None:
        """Implied churn = 1 - GRR. GRR=0.92 → churn=0.08."""
        result = _run("saas_kpi_panel", arr_current=1_000_000, grr=0.92)
        churn = result["implied_churn_rate"]
        assert churn is not None
        assert churn["value"] == pytest.approx(0.08, rel=1e-6)
        assert churn["disclosed"] is False

    def test_implied_churn_not_computed_when_grr_missing(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000)
        assert result["implied_churn_rate"] is None


# ---------------------------------------------------------------------------
# Magic Number (audit-fix formula: no x4)
# ---------------------------------------------------------------------------


class TestMagicNumber:
    def test_magic_number_from_explicit_new_arr(self) -> None:
        """Magic Number = new_arr_this_quarter / sm_spend_prior_quarter.
        new_arr=100, s&m_prior=80 → 1.25 (efficient).
        """
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            new_arr_this_quarter=100.0,
            sm_spend_prior_quarter=80.0,
        )
        mn = result["magic_number"]
        assert mn is not None
        assert mn["value"] == pytest.approx(100.0 / 80.0, rel=1e-6)
        assert mn["classification"] == "efficient"

    def test_magic_number_derived_from_arr_delta(self) -> None:
        """When new_arr_this_quarter absent, uses arr_current - arr_prior_quarter.
        arr_current=1_200_000, arr_prior_Q=1_100_000 → delta=100_000.
        s&m_prior=80_000 → Magic = 1.25.
        NO x4 applied.
        """
        result = _run(
            "saas_kpi_panel",
            arr_current=1_200_000,
            arr_prior_quarter=1_100_000,
            sm_spend_prior_quarter=80_000.0,
        )
        mn = result["magic_number"]
        assert mn is not None
        expected = 100_000.0 / 80_000.0
        assert mn["value"] == pytest.approx(expected, rel=1e-6)

    def test_magic_number_no_x4_annualization(self) -> None:
        """Explicitly verify no x4 multiplier is applied.
        If x4 were applied, result would be 4x higher.
        """
        result = _run(
            "saas_kpi_panel",
            arr_current=1_400_000,
            arr_prior_quarter=1_200_000,
            sm_spend_prior_quarter=100_000.0,
        )
        mn = result["magic_number"]
        assert mn is not None
        # Correct formula: 200_000 / 100_000 = 2.0
        # Wrong formula (with x4): (200_000 x 4) / 100_000 = 8.0
        assert mn["value"] == pytest.approx(2.0, rel=1e-6)
        assert mn["value"] != pytest.approx(8.0, rel=1e-1)

    def test_magic_number_moderate(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            new_arr_this_quarter=60.0,
            sm_spend_prior_quarter=100.0,
        )
        assert result["magic_number"]["classification"] == "moderate"

    def test_magic_number_inefficient(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            new_arr_this_quarter=30.0,
            sm_spend_prior_quarter=100.0,
        )
        assert result["magic_number"]["classification"] == "inefficient"

    def test_magic_number_not_computed_without_sm_spend(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_200_000,
            arr_prior_quarter=1_100_000,
        )
        assert result["magic_number"] is None

    def test_magic_number_disclosed_false(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_200_000,
            new_arr_this_quarter=100_000.0,
            sm_spend_prior_quarter=80_000.0,
        )
        assert result["magic_number"]["disclosed"] is False

    def test_magic_number_calculation_label_mentions_no_x4(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_200_000,
            new_arr_this_quarter=100_000.0,
            sm_spend_prior_quarter=80_000.0,
        )
        calc = result["magic_number"]["calculation"]
        assert "ARR" in calc
        assert "no x4" in calc.lower() or "no x4" in calc


# ---------------------------------------------------------------------------
# Rule of 40
# ---------------------------------------------------------------------------


class TestRuleOf40:
    def test_rule_of_40_basic(self) -> None:
        """revenue_growth=32%, fcf_margin=18% → Rule of 40 = 50."""
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            revenue_growth_rate=0.32,
            fcf_margin=0.18,
        )
        ro40 = result["rule_of_40"]
        assert ro40 is not None
        assert ro40["value"] == pytest.approx(50.0, rel=1e-6)
        assert ro40["classification"] == "excellent"

    def test_rule_of_40_healthy(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            revenue_growth_rate=0.25,
            fcf_margin=0.17,
        )
        assert result["rule_of_40"]["classification"] == "healthy"

    def test_rule_of_40_acceptable(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            revenue_growth_rate=0.20,
            fcf_margin=0.15,
        )
        assert result["rule_of_40"]["classification"] == "acceptable"

    def test_rule_of_40_weak(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            revenue_growth_rate=0.10,
            fcf_margin=0.05,
        )
        assert result["rule_of_40"]["classification"] == "weak"

    def test_rule_of_40_components_are_percentages(self) -> None:
        """Components stored as pct values (e.g. 32.0, not 0.32)."""
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            revenue_growth_rate=0.32,
            fcf_margin=0.18,
        )
        comps = result["rule_of_40"]["components"]
        assert comps["revenue_growth_pct"] == pytest.approx(32.0, rel=1e-6)
        assert comps["fcf_margin_pct"] == pytest.approx(18.0, rel=1e-6)

    def test_rule_of_40_missing_when_inputs_absent(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000)
        assert result["rule_of_40"] is None

    def test_rule_of_40_with_negative_fcf_margin(self) -> None:
        """Revenue growth 50%, FCF margin -15% → Rule of 40 = 35 (acceptable)."""
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            revenue_growth_rate=0.50,
            fcf_margin=-0.15,
        )
        ro40 = result["rule_of_40"]
        assert ro40["value"] == pytest.approx(35.0, rel=1e-6)
        assert ro40["classification"] == "acceptable"


# ---------------------------------------------------------------------------
# LTV / CAC
# ---------------------------------------------------------------------------


class TestLTVCAC:
    def test_ltv_cac_healthy(self) -> None:
        """LTV=10_000, CAC=3_000 → LTV/CAC=3.33 (healthy)."""
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            ltv=10_000.0,
            cac=3_000.0,
        )
        lc = result["ltv_cac"]
        assert lc is not None
        assert lc["value"] == pytest.approx(10_000 / 3_000, rel=1e-4)
        assert lc["classification"] == "healthy"

    def test_ltv_cac_moderate(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            ltv=5_000.0,
            cac=3_000.0,
        )
        assert result["ltv_cac"]["classification"] == "moderate"

    def test_ltv_cac_weak(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            ltv=2_000.0,
            cac=3_000.0,
        )
        assert result["ltv_cac"]["classification"] == "weak"

    def test_ltv_cac_missing_when_no_inputs(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000)
        assert result["ltv_cac"] is None

    def test_ltv_cac_disclosed_true(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            ltv=9_000.0,
            cac=3_000.0,
        )
        assert result["ltv_cac"]["disclosed"] is True


# ---------------------------------------------------------------------------
# Billings
# ---------------------------------------------------------------------------


class TestBillings:
    def test_billings_positive_deferred_increase(self) -> None:
        """Billings = Revenue + ΔDeferred. Rev=100, deferred +20 → Billings=120."""
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            revenue_current_period=100.0,
            deferred_revenue_current=80.0,
            deferred_revenue_prior=60.0,
        )
        bill = result["billings"]
        assert bill is not None
        assert bill["value"] == pytest.approx(120.0, rel=1e-6)

    def test_billings_negative_deferred_decrease(self) -> None:
        """Rev=100, deferred -10 → Billings=90."""
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            revenue_current_period=100.0,
            deferred_revenue_current=50.0,
            deferred_revenue_prior=60.0,
        )
        assert result["billings"]["value"] == pytest.approx(90.0, rel=1e-6)

    def test_billings_missing_when_inputs_absent(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000)
        assert result["billings"] is None


# ---------------------------------------------------------------------------
# Composite health score
# ---------------------------------------------------------------------------


class TestHealthScore:
    def test_health_score_present_with_all_inputs(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            nrr=1.20,
            grr=0.95,
            revenue_growth_rate=0.35,
            fcf_margin=0.15,
            new_arr_this_quarter=100_000.0,
            sm_spend_prior_quarter=80_000.0,
            ltv=10_000.0,
            cac=3_000.0,
        )
        hs = result["composite_health_score"]
        assert hs["value"] is not None
        assert 0.0 <= hs["value"] <= 1.0

    def test_health_score_label_strong(self) -> None:
        """Near-perfect inputs → health label = strong."""
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            nrr=1.25,
            grr=0.97,
            revenue_growth_rate=0.50,
            fcf_margin=0.20,
            new_arr_this_quarter=200_000.0,
            sm_spend_prior_quarter=100_000.0,
            ltv=12_000.0,
            cac=3_000.0,
        )
        assert result["composite_health_score"]["label"] == "strong"

    def test_health_score_none_when_no_components(self) -> None:
        result = _run("saas_kpi_panel", arr_current=1_000_000)
        assert result["composite_health_score"]["value"] is None

    def test_health_score_components_used_listed(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            nrr=1.15,
            revenue_growth_rate=0.30,
            fcf_margin=0.12,
        )
        used = result["composite_health_score"]["components_used"]
        assert "nrr" in used
        assert "rule_of_40" in used


# ---------------------------------------------------------------------------
# Disclosure completeness
# ---------------------------------------------------------------------------


class TestDisclosureCompleteness:
    def test_completeness_increases_with_more_inputs(self) -> None:
        minimal = _run("saas_kpi_panel", arr_current=1_000_000)
        full = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            nrr=1.15,
            grr=0.93,
            revenue_growth_rate=0.30,
            fcf_margin=0.12,
            ltv=9_000.0,
            cac=3_000.0,
            cac_payback_months=18.0,
            customer_count_current=5_000,
            top_10_customer_revenue_pct=0.15,
        )
        assert full["disclosure_completeness"] > minimal["disclosure_completeness"]


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


class TestWarnings:
    def test_concentration_warning_above_30pct(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            top_10_customer_revenue_pct=0.40,
        )
        assert any("concentration" in w.lower() for w in result["warnings"])

    def test_no_concentration_warning_below_30pct(self) -> None:
        result = _run(
            "saas_kpi_panel",
            arr_current=1_000_000,
            top_10_customer_revenue_pct=0.20,
        )
        assert not any("concentration" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Deprecation check for saas_metrics
# ---------------------------------------------------------------------------


class TestSaasMetricsDeprecation:
    def test_deprecated_at_version_set(self) -> None:
        schema = _schema("saas_metrics")
        assert schema.deprecated_at_version == "0.2.0"

    def test_when_not_to_use_mentions_saas_kpi_panel(self) -> None:
        schema = _schema("saas_metrics")
        combined = " ".join(schema.selection.when_not_to_use).lower()
        assert "saas_kpi_panel" in combined

    def test_docstring_mentions_superseded(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import saas_metrics

        assert "saas_kpi_panel" in saas_metrics.__doc__.lower()


# ---------------------------------------------------------------------------
# Registration + artifact type
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_saas_kpi_panel_registered(self) -> None:
        h = _get("saas_kpi_panel")
        assert h.schema.directory.name == "saas_kpi_panel"

    def test_produces_saas_kpi_panel_output(self) -> None:
        schema = _schema("saas_kpi_panel")
        assert "saas_kpi_panel_output" in schema.contract.produces_artifacts

    def test_category_is_saas_kpis(self) -> None:
        from openlia.llm.runtime.report_v2_2 import Category

        schema = _schema("saas_kpi_panel")
        assert schema.directory.category == Category.SAAS_KPIS

    def test_version_is_1_0_0(self) -> None:
        schema = _schema("saas_kpi_panel")
        assert schema.version == "1.0.0"

    def test_not_deprecated(self) -> None:
        schema = _schema("saas_kpi_panel")
        assert schema.deprecated_at_version is None
