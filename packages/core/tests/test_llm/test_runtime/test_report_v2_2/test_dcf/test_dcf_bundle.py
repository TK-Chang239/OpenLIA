"""Tests for PR 2.2: DCF engine + cost of capital + sensitivity bundle.

Covers:
- cost_of_capital_builder: CAPM with known inputs returns known re.
- cost_of_capital_builder: WACC formula correct.
- cost_of_capital_builder: Hamada relevering formula.
- dcf_engine: known FCFF inputs reproduce known EV.
- dcf_engine: TV/EV > 75% emits warning.
- dcf_engine: terminal_growth >= WACC raises ValueError.
- sensitivity_table: 3x3 matrix for f(x,y)=x+y produces correct values.
- sensitivity_table: Plotly HTML output is parseable JSON.
- tornado_diagram: ranks correctly by impact magnitude.
- tornado_diagram: low >= high raises ValueError.
- scenario_weighting: known inputs return correct weighted value.
- scenario_weighting: probabilities not summing to 1.0 raises ValueError.
- reverse_dcf: implied growth rate found by bisection, converges within tolerance.
- reverse_dcf: invalid mode raises ValueError.
- All 7 helpers are registered after module import.
- Both skill docs exist at declared paths.
"""

from __future__ import annotations

import json
import pathlib
from typing import ClassVar

import pytest

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_SKILLS_ROOT = (
    pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
    / "src"
    / "openlia"
    / "llm"
    / "runtime"
    / "report_v2_2"
    / "tools"
    / "library_helpers"
    / "skills"
)

_COC_DEFAULTS = dict(
    risk_free_rate=0.04,
    equity_risk_premium=0.05,
    marginal_tax_rate=0.21,
    pretax_cost_of_debt=0.05,
    equity_weight=0.80,
    debt_weight=0.20,
    method="capm",
    beta=1.0,
)

# Simple 3-year DCF with round numbers for easy hand-verification
# Revenue: [100, 110, 121], op_margin=0.20, tax=0.21, da=0.05, capex=0.06, nwc=0.0
# Year 1: NOPAT = 100*0.20*(1-0.21) = 15.8, D&A=5, Capex=6, dNWC=(100-0)*0=0
#          FCFF = 15.8+5-6-0 = 14.8
# Year 2: NOPAT = 110*0.20*(1-0.21)=17.38, D&A=5.5, Capex=6.6, dNWC=0
#          FCFF = 17.38+5.5-6.6 = 16.28
# Year 3: NOPAT = 121*0.20*(1-0.21)=19.118, D&A=6.05, Capex=7.26, dNWC=0
#          FCFF = 19.118+6.05-7.26 = 17.908

_DCF_COC = {
    "wacc": 0.10,
    "cost_of_equity": 0.09,
    "method_used": "capm",
}

_SIMPLE_DCF_PARAMS = dict(
    revenue_path=[100.0, 110.0, 121.0],
    operating_margin_path=0.20,
    tax_rate_path=0.21,
    da_pct_of_revenue=0.05,
    capex_pct_of_revenue=0.06,
    nwc_pct_of_revenue=0.0,
    cost_of_capital=_DCF_COC,
    terminal_method="perpetuity",
    terminal_growth=0.025,
    mid_year_convention=False,  # end-of-year for simpler arithmetic
    net_debt=0.0,
    shares_outstanding=0.0,
)


# ---------------------------------------------------------------------------
# cost_of_capital_builder tests
# ---------------------------------------------------------------------------


class TestCostOfCapitalBuilder:
    def test_capm_cost_of_equity_known_values(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        result = cost_of_capital_builder.execute(**_COC_DEFAULTS)
        # re = rf + beta * ERP = 0.04 + 1.0 * 0.05 = 0.09
        assert abs(result["cost_of_equity"] - 0.09) < 1e-9

    def test_capm_wacc_formula(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        result = cost_of_capital_builder.execute(**_COC_DEFAULTS)
        # after_tax_rd = 0.05 * (1 - 0.21) = 0.0395
        # WACC = 0.80 * 0.09 + 0.20 * 0.0395 = 0.072 + 0.0079 = 0.0799
        expected_wacc = 0.80 * 0.09 + 0.20 * (0.05 * 0.79)
        assert abs(result["wacc"] - expected_wacc) < 1e-9

    def test_capm_after_tax_cost_of_debt(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        result = cost_of_capital_builder.execute(**_COC_DEFAULTS)
        expected_rd = 0.05 * (1 - 0.21)
        assert abs(result["after_tax_cost_of_debt"] - expected_rd) < 1e-9

    def test_hamada_relever(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers.cost_of_capital_builder import (
            _hamada_relever,
        )

        # beta_L = beta_U * [1 + (1-T) * D/E]
        beta_u = 0.80
        tax = 0.21
        d_e = 0.50  # D/E = 50%
        expected = beta_u * (1.0 + (1.0 - tax) * d_e)
        assert abs(_hamada_relever(beta_u, tax, d_e) - expected) < 1e-9

    def test_hamada_method_execute(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        params = {
            **_COC_DEFAULTS,
            "method": "hamada",
            "unlevered_beta": 0.80,
            # D/E = 0.20/0.80 = 0.25
        }
        result = cost_of_capital_builder.execute(**params)
        # beta_L = 0.80 * [1 + (1-0.21) * 0.25] = 0.80 * 1.1975 = 0.9580
        expected_beta_l = 0.80 * (1.0 + 0.79 * 0.25)
        expected_re = 0.04 + expected_beta_l * 0.05
        assert abs(result["cost_of_equity"] - expected_re) < 1e-6

    def test_build_up_method(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        params = {
            **_COC_DEFAULTS,
            "method": "build_up",
            "size_premium": 0.02,
            "specific_risk_premium": 0.01,
        }
        result = cost_of_capital_builder.execute(**params)
        # re = 0.04 + 0.05 + 0.02 + 0.01 = 0.12
        assert abs(result["cost_of_equity"] - 0.12) < 1e-9

    def test_weights_must_sum_to_one(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        with pytest.raises(ValueError, match=r"sum to 1\.0"):
            cost_of_capital_builder.execute(
                **{**_COC_DEFAULTS, "equity_weight": 0.70, "debt_weight": 0.20}
            )

    def test_invalid_method_raises(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        with pytest.raises(ValueError, match="method must be"):
            cost_of_capital_builder.execute(**{**_COC_DEFAULTS, "method": "xyzzy"})

    def test_low_r2_warning(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        result = cost_of_capital_builder.execute(**{**_COC_DEFAULTS, "beta_r_squared": 0.10})
        assert any("R²" in w and "0.10" in w for w in result["warnings"])

    def test_crp_applied(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        result = cost_of_capital_builder.execute(
            **{**_COC_DEFAULTS, "country_risk_premium": 0.03, "country_risk_lambda": 1.0}
        )
        # re = 0.04 + 1.0 * 0.05 + 1.0 * 0.03 = 0.12
        assert abs(result["cost_of_equity"] - 0.12) < 1e-9

    def test_output_has_required_keys(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            cost_of_capital_builder,
        )

        result = cost_of_capital_builder.execute(**_COC_DEFAULTS)
        for key in (
            "cost_of_equity",
            "wacc",
            "after_tax_cost_of_debt",
            "capital_structure",
            "narrative",
        ):
            assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# dcf_engine tests
# ---------------------------------------------------------------------------


class TestDcfEngine:
    def test_known_inputs_ev(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        result = dcf_engine.execute(**_SIMPLE_DCF_PARAMS)
        # Hand-calculate EV for end-of-year discounting, WACC=0.10, g=0.025
        # FCFF: year1=14.8, year2=16.28, year3=17.908 (nwc=0)
        fcffs = [14.8, 16.28, 17.908]
        wacc = 0.10
        pv_sum = sum(f / (1 + wacc) ** t for t, f in enumerate(fcffs, 1))
        tv_fcff4 = fcffs[-1] * (1 + 0.025)
        tv = tv_fcff4 / (wacc - 0.025)
        pv_tv = tv / (1 + wacc) ** 3
        expected_ev = pv_sum + pv_tv
        assert abs(result["enterprise_value"] - expected_ev) < 0.01

    def test_tv_pct_warning_fires(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        # Very low near-term FCFF so TV dominates
        result = dcf_engine.execute(
            revenue_path=[1.0, 1.0, 1.0],
            operating_margin_path=0.01,
            tax_rate_path=0.21,
            da_pct_of_revenue=0.0,
            capex_pct_of_revenue=0.0,
            nwc_pct_of_revenue=0.0,
            cost_of_capital={"wacc": 0.10},
            terminal_method="perpetuity",
            terminal_growth=0.025,
            tv_pct_warn_threshold=0.50,
            mid_year_convention=False,
        )
        assert result["terminal_value"]["tv_pct_of_ev"] > 0.50
        assert any("Terminal value" in w for w in result["warnings"])

    def test_terminal_growth_gte_wacc_raises(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        with pytest.raises(ValueError, match="terminal_growth"):
            dcf_engine.execute(
                **{**_SIMPLE_DCF_PARAMS, "terminal_growth": 0.10}
            )  # WACC is 0.10, g = 0.10 → error

    def test_mid_year_increases_ev(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        end_year = dcf_engine.execute(**{**_SIMPLE_DCF_PARAMS, "mid_year_convention": False})
        mid_year = dcf_engine.execute(**{**_SIMPLE_DCF_PARAMS, "mid_year_convention": True})
        # Mid-year discounts less aggressively → higher EV
        assert mid_year["enterprise_value"] > end_year["enterprise_value"]

    def test_per_share_computed(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        result = dcf_engine.execute(**{**_SIMPLE_DCF_PARAMS, "shares_outstanding": 10.0})
        assert result["implied_value_per_share"] is not None
        assert abs(result["implied_value_per_share"] - result["implied_equity_value"] / 10.0) < 1e-6

    def test_fcff_schedule_length(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        result = dcf_engine.execute(**_SIMPLE_DCF_PARAMS)
        assert len(result["fcff_schedule"]) == 3

    def test_negative_terminal_growth_allowed(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        result = dcf_engine.execute(**{**_SIMPLE_DCF_PARAMS, "terminal_growth": -0.02})
        assert result["enterprise_value"] > 0

    def test_output_keys_present(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        result = dcf_engine.execute(**_SIMPLE_DCF_PARAMS)
        for key in (
            "fcff_schedule",
            "sum_pv_fcff",
            "terminal_value",
            "enterprise_value",
            "implied_equity_value",
            "warnings",
            "narrative",
        ):
            assert key in result, f"Missing key: {key}"

    def test_exit_multiple_method(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import dcf_engine

        result = dcf_engine.execute(
            **{
                **_SIMPLE_DCF_PARAMS,
                "terminal_method": "exit_multiple",
                "terminal_exit_multiple": 10.0,
            }
        )
        # EBITDA_3 = EBIT_3 + DA_3 = 121*0.20 + 121*0.05 = 24.2 + 6.05 = 30.25
        expected_tv_nom = 30.25 * 10.0
        assert abs(result["terminal_value"]["terminal_value_nominal"] - expected_tv_nom) < 0.01


# ---------------------------------------------------------------------------
# sensitivity_table tests
# ---------------------------------------------------------------------------


class TestSensitivityTable:
    def test_3x3_matrix_sum_function(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import sensitivity_table

        result = sensitivity_table.execute(
            base_fn=lambda x, y: x + y,
            var1_name="x",
            var1_values=[1.0, 2.0, 3.0],
            var2_name="y",
            var2_values=[10.0, 20.0, 30.0],
        )
        expected = [[11.0, 21.0, 31.0], [12.0, 22.0, 32.0], [13.0, 23.0, 33.0]]
        for r, row in enumerate(expected):
            for c, val in enumerate(row):
                assert abs(result["matrix"][r][c] - val) < 1e-9

    def test_plotly_html_parseable_json(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import sensitivity_table

        result = sensitivity_table.execute(
            base_fn=lambda x, y: x * y,
            var1_name="x",
            var1_values=[1.0, 2.0],
            var2_name="y",
            var2_values=[3.0, 4.0],
        )
        # html is either valid Plotly JSON or error JSON — both must parse
        parsed = json.loads(result["html"])
        assert isinstance(parsed, dict)

    def test_markdown_table_present(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import sensitivity_table

        result = sensitivity_table.execute(
            base_fn=lambda x, y: x + y,
            var1_name="x",
            var1_values=[1.0, 2.0],
            var2_name="y",
            var2_values=[10.0, 20.0],
        )
        assert "x" in result["markdown_table"]
        assert "y" in result["markdown_table"]

    def test_base_value_lookup(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import sensitivity_table

        result = sensitivity_table.execute(
            base_fn=lambda x, y: x + y,
            var1_name="x",
            var1_values=[1.0, 2.0, 3.0],
            var2_name="y",
            var2_values=[10.0, 20.0, 30.0],
            base_var1=2.0,
            base_var2=20.0,
        )
        # f(2, 20) = 22
        assert abs(result["base_value"] - 22.0) < 1e-9

    def test_precomputed_matrix(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import sensitivity_table

        matrix = [[5.0, 6.0], [7.0, 8.0]]
        result = sensitivity_table.execute(
            precomputed_matrix=matrix,
            var1_name="a",
            var1_values=[0.1, 0.2],
            var2_name="b",
            var2_values=[0.3, 0.4],
        )
        assert result["matrix"] == matrix

    def test_empty_var1_raises(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import sensitivity_table

        with pytest.raises(ValueError):
            sensitivity_table.execute(
                base_fn=lambda x, y: x + y,
                var1_name="x",
                var1_values=[],
                var2_name="y",
                var2_values=[1.0],
            )


# ---------------------------------------------------------------------------
# tornado_diagram tests
# ---------------------------------------------------------------------------


class TestTornadoDiagram:
    def test_ranks_by_impact_magnitude(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import tornado_diagram

        def fn(wacc: float = 0.10, growth: float = 0.025, margin: float = 0.20) -> float:
            return margin * 100 - wacc * 50 + growth * 200

        result = tornado_diagram.execute(
            base_fn=fn,
            base_kwargs={"wacc": 0.10, "growth": 0.025, "margin": 0.20},
            variables=[
                {"name": "wacc", "low": 0.07, "high": 0.13},
                {"name": "growth", "low": 0.01, "high": 0.04},
                {"name": "margin", "low": 0.15, "high": 0.30},  # largest range
            ],
        )
        # Check sorted descending by impact_magnitude
        mags = [r["impact_magnitude"] for r in result["results"]]
        assert mags == sorted(mags, reverse=True)

    def test_correct_low_high_values(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import tornado_diagram

        # Simple: f(x) = 2*x; base x=5 → base=10
        def fn(x: float = 5.0) -> float:
            return 2.0 * x

        result = tornado_diagram.execute(
            base_fn=fn,
            base_kwargs={"x": 5.0},
            variables=[{"name": "x", "low": 3.0, "high": 7.0}],
        )
        r = result["results"][0]
        assert abs(r["low_value"] - 6.0) < 1e-9  # 2*3
        assert abs(r["high_value"] - 14.0) < 1e-9  # 2*7
        assert abs(r["base_value"] - 10.0) < 1e-9  # 2*5

    def test_low_gte_high_raises(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import tornado_diagram

        with pytest.raises(ValueError, match=r"low.*<.*high|low.*must be.*<.*high"):
            tornado_diagram.execute(
                base_fn=lambda x: x,
                base_kwargs={"x": 5.0},
                variables=[{"name": "x", "low": 7.0, "high": 3.0}],
            )

    def test_plotly_html_parseable(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import tornado_diagram

        result = tornado_diagram.execute(
            base_fn=lambda x: x,
            base_kwargs={"x": 10.0},
            variables=[{"name": "x", "low": 5.0, "high": 15.0}],
        )
        parsed = json.loads(result["html"])
        assert isinstance(parsed, dict)

    def test_top_driver_is_highest_magnitude(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import tornado_diagram

        def fn(a: float = 1.0, b: float = 1.0) -> float:
            return a + b * 10

        result = tornado_diagram.execute(
            base_fn=fn,
            base_kwargs={"a": 1.0, "b": 1.0},
            variables=[
                {"name": "a", "low": 0.5, "high": 1.5},  # small range
                {"name": "b", "low": 0.5, "high": 2.0},  # larger range
            ],
        )
        assert result["top_driver"] == "b"


# ---------------------------------------------------------------------------
# scenario_weighting tests
# ---------------------------------------------------------------------------


class TestScenarioWeighting:
    def test_known_weighted_value(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import scenario_weighting

        result = scenario_weighting.execute(
            scenarios=[
                {"name": "base", "value": 100.0, "probability": 0.60},
                {"name": "bull", "value": 150.0, "probability": 0.25},
                {"name": "bear", "value": 60.0, "probability": 0.15},
            ]
        )
        expected = 100.0 * 0.60 + 150.0 * 0.25 + 60.0 * 0.15
        assert abs(result["weighted_value"] - expected) < 1e-9

    def test_probs_not_summing_raises(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import scenario_weighting

        with pytest.raises(ValueError, match=r"sum to 1\.0"):
            scenario_weighting.execute(
                scenarios=[
                    {"name": "base", "value": 100.0, "probability": 0.50},
                    {"name": "bull", "value": 150.0, "probability": 0.30},
                    # total = 0.80, missing 0.20
                ]
            )

    def test_single_scenario_prob_1(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import scenario_weighting

        result = scenario_weighting.execute(
            scenarios=[{"name": "base", "value": 75.0, "probability": 1.0}]
        )
        assert abs(result["weighted_value"] - 75.0) < 1e-9

    def test_breakdown_contributions(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import scenario_weighting

        result = scenario_weighting.execute(
            scenarios=[
                {"name": "base", "value": 100.0, "probability": 0.60},
                {"name": "bull", "value": 200.0, "probability": 0.40},
            ]
        )
        # contributions: 60 + 80 = 140
        total_contrib = sum(b["weighted_contribution"] for b in result["scenario_breakdown"])
        assert abs(total_contrib - 140.0) < 1e-9

    def test_empty_scenarios_raises(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import scenario_weighting

        with pytest.raises(ValueError):
            scenario_weighting.execute(scenarios=[])

    def test_markdown_table_present(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import scenario_weighting

        result = scenario_weighting.execute(
            scenarios=[
                {"name": "base", "value": 100.0, "probability": 0.70},
                {"name": "bear", "value": 60.0, "probability": 0.30},
            ]
        )
        assert "Scenario" in result["markdown_table"]
        assert "base" in result["markdown_table"]


# ---------------------------------------------------------------------------
# reverse_dcf tests
# ---------------------------------------------------------------------------


class TestReverseDcf:
    """Tests for reverse_dcf helper."""

    _FCFF: ClassVar[list[float]] = [10.0, 11.0, 12.0]  # simple schedule for testing
    _NET_DEBT: ClassVar[float] = 0.0
    _SHARES: ClassVar[float] = 10.0

    def test_implied_growth_roundtrip(self) -> None:
        """If we know the growth rate used to compute a price, reversing should recover it."""
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            dcf_engine,
            reverse_dcf,
        )

        wacc = 0.10
        known_growth = 0.03

        # Build a price using the known growth rate
        forward_result = dcf_engine.execute(
            revenue_path=[100.0, 110.0, 121.0],
            operating_margin_path=0.20,
            tax_rate_path=0.21,
            da_pct_of_revenue=0.05,
            capex_pct_of_revenue=0.06,
            nwc_pct_of_revenue=0.0,
            cost_of_capital={"wacc": wacc},
            terminal_method="perpetuity",
            terminal_growth=known_growth,
            mid_year_convention=False,
            net_debt=0.0,
            shares_outstanding=10.0,
        )
        price = forward_result["implied_value_per_share"]
        fcff_schedule = [row["fcff"] for row in forward_result["fcff_schedule"]]

        # Reverse: given the price, recover the growth rate
        reverse_result = reverse_dcf.execute(
            current_price=price,
            fcff_schedule=fcff_schedule,
            net_debt=0.0,
            shares_outstanding=10.0,
            mode="solve_growth",
            fixed_wacc=wacc,
            mid_year_convention=False,
        )
        assert abs(reverse_result["implied_growth_rate"] - known_growth) < 1e-4

    def test_convergence_residual_small(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import reverse_dcf

        result = reverse_dcf.execute(
            current_price=50.0,
            fcff_schedule=self._FCFF,
            net_debt=self._NET_DEBT,
            shares_outstanding=self._SHARES,
            mode="solve_growth",
            fixed_wacc=0.10,
            mid_year_convention=False,
        )
        assert result["convergence"]["converged"]
        assert result["convergence"]["residual"] < 0.01

    def test_invalid_mode_raises(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import reverse_dcf

        with pytest.raises(ValueError, match="mode must be"):
            reverse_dcf.execute(
                current_price=50.0,
                fcff_schedule=self._FCFF,
                net_debt=self._NET_DEBT,
                shares_outstanding=self._SHARES,
                mode="unknown",
                fixed_wacc=0.10,
            )

    def test_solve_wacc_mode(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            dcf_engine,
            reverse_dcf,
        )

        known_wacc = 0.10
        growth = 0.025

        forward_result = dcf_engine.execute(
            revenue_path=[100.0, 110.0, 121.0],
            operating_margin_path=0.20,
            tax_rate_path=0.21,
            da_pct_of_revenue=0.05,
            capex_pct_of_revenue=0.06,
            nwc_pct_of_revenue=0.0,
            cost_of_capital={"wacc": known_wacc},
            terminal_method="perpetuity",
            terminal_growth=growth,
            mid_year_convention=False,
            net_debt=0.0,
            shares_outstanding=10.0,
        )
        price = forward_result["implied_value_per_share"]
        fcff_schedule = [row["fcff"] for row in forward_result["fcff_schedule"]]

        reverse_result = reverse_dcf.execute(
            current_price=price,
            fcff_schedule=fcff_schedule,
            net_debt=0.0,
            shares_outstanding=10.0,
            mode="solve_wacc",
            fixed_terminal_growth=growth,
            mid_year_convention=False,
        )
        assert abs(reverse_result["implied_wacc"] - known_wacc) < 1e-4

    def test_negative_price_raises(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import reverse_dcf

        with pytest.raises(ValueError, match="current_price must be > 0"):
            reverse_dcf.execute(
                current_price=-10.0,
                fcff_schedule=self._FCFF,
                net_debt=self._NET_DEBT,
                shares_outstanding=self._SHARES,
                mode="solve_growth",
                fixed_wacc=0.10,
            )


# ---------------------------------------------------------------------------
# Registry tests — all 7 helpers registered
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_all_new_helpers_registered(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            get_helper,
        )

        new_helpers = [
            "cost_of_capital_builder",
            "dcf_engine",
            "sensitivity_table",
            "tornado_diagram",
            "scenario_weighting",
            "reverse_dcf",
        ]
        for name in new_helpers:
            assert get_helper(name) is not None, f"Helper {name!r} not registered"

    def test_dcf_valuation_still_registered(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            get_helper,
        )

        assert get_helper("dcf_valuation") is not None

    def test_skill_doc_cost_of_capital_exists(self) -> None:
        assert (_SKILLS_ROOT / "cost_of_capital_builder.md").exists()

    def test_skill_doc_dcf_engine_exists(self) -> None:
        assert (_SKILLS_ROOT / "dcf_engine.md").exists()

    def test_skill_doc_ref_path_matches_file(self) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
            get_helper,
        )

        for helper_name, expected_filename in [
            ("cost_of_capital_builder", "cost_of_capital_builder.md"),
            ("dcf_engine", "dcf_engine.md"),
        ]:
            h = get_helper(helper_name)
            assert h is not None
            assert h.schema.skill_doc is not None
            assert h.schema.skill_doc.path.endswith(expected_filename)
            skill_path = _SKILLS_ROOT / expected_filename
            assert skill_path.exists(), f"Skill doc missing: {skill_path}"

    def test_artifact_types_registered(self) -> None:
        from openlia.llm.runtime.report_v2_2.artifact_types import _registry

        new_types = [
            "cost_of_capital_output",
            "dcf_output",
            "sensitivity_matrix",
            "tornado_diagram_output",
            "scenario_panel",
            "reverse_dcf_output",
        ]
        for t in new_types:
            assert _registry.get(t) is not None, f"Artifact type {t!r} not in registry"
