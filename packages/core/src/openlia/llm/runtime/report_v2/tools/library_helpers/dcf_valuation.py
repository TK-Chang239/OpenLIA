"""
Vendored from alirezarezvani/claude-skills (MIT License).
Original: finance/skills/financial-analyst/scripts/dcf_valuation.py
Vendored on 2026-05-21 for OpenLIA report_v2 library helpers.

Adapted to expose a HelperSchema via SCHEMA module-level constant and an
execute(**params) entry point.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperParam,
    HelperSchema,
    register_library_helper,
)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


class DCFModel:
    """Discounted Cash Flow valuation model."""

    def __init__(self) -> None:
        self.historical: dict[str, Any] = {}
        self.assumptions: dict[str, Any] = {}
        self.wacc: float = 0.0
        self.projected_revenue: list[float] = []
        self.projected_fcf: list[float] = []
        self.projection_years: int = 5
        self.terminal_value_perpetuity: float = 0.0
        self.terminal_value_exit_multiple: float = 0.0
        self.enterprise_value_perpetuity: float = 0.0
        self.enterprise_value_exit_multiple: float = 0.0
        self.equity_value_perpetuity: float = 0.0
        self.equity_value_exit_multiple: float = 0.0
        self.value_per_share_perpetuity: float = 0.0
        self.value_per_share_exit_multiple: float = 0.0

    def set_historical_financials(self, historical: dict[str, Any]) -> None:
        self.historical = historical

    def set_assumptions(self, assumptions: dict[str, Any]) -> None:
        self.assumptions = assumptions
        self.projection_years = assumptions.get("projection_years", 5)

    def calculate_wacc(self) -> float:
        """Calculate Weighted Average Cost of Capital via CAPM."""
        wacc_inputs = self.assumptions.get("wacc_inputs", {})

        risk_free_rate = wacc_inputs.get("risk_free_rate", 0.04)
        equity_risk_premium = wacc_inputs.get("equity_risk_premium", 0.06)
        beta = wacc_inputs.get("beta", 1.0)
        cost_of_debt = wacc_inputs.get("cost_of_debt", 0.05)
        tax_rate = wacc_inputs.get("tax_rate", 0.25)
        debt_weight = wacc_inputs.get("debt_weight", 0.30)
        equity_weight = wacc_inputs.get("equity_weight", 0.70)

        cost_of_equity = risk_free_rate + beta * equity_risk_premium
        after_tax_cost_of_debt = cost_of_debt * (1 - tax_rate)
        self.wacc = (equity_weight * cost_of_equity) + (debt_weight * after_tax_cost_of_debt)

        return self.wacc

    def project_cash_flows(self) -> tuple[list[float], list[float]]:
        """Project revenue and free cash flow over the projection period."""
        base_revenue = self.historical.get("revenue", [])
        if not base_revenue:
            raise ValueError("Historical revenue data is required")

        last_revenue = base_revenue[-1]
        revenue_growth_rates = self.assumptions.get("revenue_growth_rates", [])
        fcf_margins = self.assumptions.get("fcf_margins", [])
        default_growth = self.assumptions.get("default_revenue_growth", 0.05)
        default_fcf_margin = self.assumptions.get("default_fcf_margin", 0.10)

        self.projected_revenue = []
        self.projected_fcf = []
        current_revenue = last_revenue

        for year in range(self.projection_years):
            growth = (
                revenue_growth_rates[year] if year < len(revenue_growth_rates) else default_growth
            )
            fcf_margin = fcf_margins[year] if year < len(fcf_margins) else default_fcf_margin
            current_revenue = current_revenue * (1 + growth)
            fcf = current_revenue * fcf_margin
            self.projected_revenue.append(current_revenue)
            self.projected_fcf.append(fcf)

        return self.projected_revenue, self.projected_fcf

    def calculate_terminal_value(self) -> tuple[float, float]:
        """Calculate terminal value using perpetuity growth and exit multiple."""
        if not self.projected_fcf:
            raise ValueError("Must project cash flows before terminal value")

        terminal_fcf = self.projected_fcf[-1]
        terminal_growth = self.assumptions.get("terminal_growth_rate", 0.025)
        exit_multiple = self.assumptions.get("exit_ev_ebitda_multiple", 12.0)

        if self.wacc > terminal_growth:
            self.terminal_value_perpetuity = (terminal_fcf * (1 + terminal_growth)) / (
                self.wacc - terminal_growth
            )
        else:
            self.terminal_value_perpetuity = 0.0

        terminal_revenue = self.projected_revenue[-1]
        ebitda_margin = self.assumptions.get("terminal_ebitda_margin", 0.20)
        terminal_ebitda = terminal_revenue * ebitda_margin
        self.terminal_value_exit_multiple = terminal_ebitda * exit_multiple

        return self.terminal_value_perpetuity, self.terminal_value_exit_multiple

    def calculate_enterprise_value(self) -> tuple[float, float]:
        """Calculate enterprise value by discounting projected FCFs and terminal value."""
        if not self.projected_fcf:
            raise ValueError("Must project cash flows first")

        pv_fcf = 0.0
        for i, fcf in enumerate(self.projected_fcf):
            discount_factor = (1 + self.wacc) ** (i + 1)
            pv_fcf += fcf / discount_factor

        terminal_discount = (1 + self.wacc) ** self.projection_years
        pv_tv_perpetuity = self.terminal_value_perpetuity / terminal_discount
        pv_tv_exit = self.terminal_value_exit_multiple / terminal_discount

        self.enterprise_value_perpetuity = pv_fcf + pv_tv_perpetuity
        self.enterprise_value_exit_multiple = pv_fcf + pv_tv_exit

        return self.enterprise_value_perpetuity, self.enterprise_value_exit_multiple

    def calculate_equity_value(self) -> tuple[float, float]:
        """Calculate equity value from enterprise value."""
        net_debt = self.historical.get("net_debt", 0)
        shares_outstanding = self.historical.get("shares_outstanding", 1)

        self.equity_value_perpetuity = self.enterprise_value_perpetuity - net_debt
        self.equity_value_exit_multiple = self.enterprise_value_exit_multiple - net_debt

        self.value_per_share_perpetuity = safe_divide(
            self.equity_value_perpetuity, shares_outstanding
        )
        self.value_per_share_exit_multiple = safe_divide(
            self.equity_value_exit_multiple, shares_outstanding
        )

        return self.equity_value_perpetuity, self.equity_value_exit_multiple

    def sensitivity_analysis(
        self,
        wacc_range: list[float] | None = None,
        growth_range: list[float] | None = None,
    ) -> dict[str, Any]:
        """Two-way sensitivity analysis: WACC vs terminal growth rate."""
        if wacc_range is None:
            base_wacc = self.wacc
            wacc_range = [
                round(base_wacc - 0.02, 4),
                round(base_wacc - 0.01, 4),
                round(base_wacc, 4),
                round(base_wacc + 0.01, 4),
                round(base_wacc + 0.02, 4),
            ]

        if growth_range is None:
            base_growth = self.assumptions.get("terminal_growth_rate", 0.025)
            growth_range = [
                round(base_growth - 0.01, 4),
                round(base_growth - 0.005, 4),
                round(base_growth, 4),
                round(base_growth + 0.005, 4),
                round(base_growth + 0.01, 4),
            ]

        rows = len(wacc_range)
        cols = len(growth_range)
        ev_table = [[0.0] * cols for _ in range(rows)]
        share_price_table = [[0.0] * cols for _ in range(rows)]
        terminal_fcf = self.projected_fcf[-1] if self.projected_fcf else 0

        for i, wacc_val in enumerate(wacc_range):
            for j, growth_val in enumerate(growth_range):
                if wacc_val <= growth_val:
                    ev_table[i][j] = float("inf")
                    share_price_table[i][j] = float("inf")
                    continue

                pv_fcf = 0.0
                for k, fcf in enumerate(self.projected_fcf):
                    pv_fcf += fcf / ((1 + wacc_val) ** (k + 1))

                tv = (terminal_fcf * (1 + growth_val)) / (wacc_val - growth_val)
                pv_tv = tv / ((1 + wacc_val) ** self.projection_years)
                ev = pv_fcf + pv_tv
                ev_table[i][j] = round(ev, 2)

                net_debt = self.historical.get("net_debt", 0)
                shares = self.historical.get("shares_outstanding", 1)
                equity = ev - net_debt
                share_price_table[i][j] = round(safe_divide(equity, shares), 2)

        return {
            "wacc_values": wacc_range,
            "growth_values": growth_range,
            "enterprise_value_table": ev_table,
            "share_price_table": share_price_table,
        }

    def run_full_valuation(self) -> dict[str, Any]:
        """Run the complete DCF valuation."""
        self.calculate_wacc()
        self.project_cash_flows()
        self.calculate_terminal_value()
        self.calculate_enterprise_value()
        self.calculate_equity_value()
        sensitivity = self.sensitivity_analysis()

        return {
            "wacc": self.wacc,
            "projected_revenue": self.projected_revenue,
            "projected_fcf": self.projected_fcf,
            "terminal_value": {
                "perpetuity_growth": self.terminal_value_perpetuity,
                "exit_multiple": self.terminal_value_exit_multiple,
            },
            "enterprise_value": {
                "perpetuity_growth": self.enterprise_value_perpetuity,
                "exit_multiple": self.enterprise_value_exit_multiple,
            },
            "equity_value": {
                "perpetuity_growth": self.equity_value_perpetuity,
                "exit_multiple": self.equity_value_exit_multiple,
            },
            "value_per_share": {
                "perpetuity_growth": self.value_per_share_perpetuity,
                "exit_multiple": self.value_per_share_exit_multiple,
            },
            "sensitivity_analysis": sensitivity,
        }


def execute(**params: Any) -> dict[str, Any]:
    """Run DCF valuation.

    Params:
        base_revenue: list of historical revenue values (required)
        projection_years: number of years to project (default 5)
        revenue_growth_rates: per-year growth rates list
        fcf_margins: per-year FCF margin list
        terminal_growth_rate: terminal growth rate (default 0.025)
        net_debt: net debt (default 0)
        shares_outstanding: diluted shares (default 1)
        wacc_inputs: dict with risk_free_rate, beta, etc.
    """
    historical = {
        "revenue": params["base_revenue"],
        "net_debt": params.get("net_debt", 0),
        "shares_outstanding": params.get("shares_outstanding", 1),
    }
    assumptions: dict[str, Any] = {
        "projection_years": params.get("projection_years", 5),
        "terminal_growth_rate": params.get("terminal_growth_rate", 0.025),
    }
    for key in (
        "revenue_growth_rates",
        "fcf_margins",
        "default_revenue_growth",
        "default_fcf_margin",
        "exit_ev_ebitda_multiple",
        "terminal_ebitda_margin",
        "wacc_inputs",
    ):
        if key in params:
            assumptions[key] = params[key]

    model = DCFModel()
    model.set_historical_financials(historical)
    model.set_assumptions(assumptions)
    return model.run_full_valuation()


SCHEMA = HelperSchema(
    name="dcf_valuation",
    description=(
        "Discounted Cash Flow enterprise and equity valuation with WACC calculation, "
        "terminal value estimation, and two-way sensitivity analysis."
    ),
    params={
        "base_revenue": HelperParam(
            type="list[float]",
            description="Historical revenue series; last value is the base for projections.",
            required=True,
        ),
        "projection_years": HelperParam(
            type="int",
            default=5,
            description="Number of years to project free cash flows.",
            required=False,
        ),
        "revenue_growth_rates": HelperParam(
            type="list[float]",
            default=None,
            description="Per-year revenue growth rates. Defaults to default_revenue_growth.",
            required=False,
        ),
        "fcf_margins": HelperParam(
            type="list[float]",
            default=None,
            description="Per-year FCF margin. Defaults to default_fcf_margin.",
            required=False,
        ),
        "terminal_growth_rate": HelperParam(
            type="float",
            default=0.025,
            description="Perpetuity terminal growth rate (Gordon Growth).",
            required=False,
        ),
        "net_debt": HelperParam(
            type="float",
            default=0.0,
            description="Net debt (total debt minus cash) for equity bridge.",
            required=False,
        ),
        "shares_outstanding": HelperParam(
            type="float",
            default=1.0,
            description="Diluted shares outstanding for per-share value.",
            required=False,
        ),
        "wacc_inputs": HelperParam(
            type="dict",
            default=None,
            description=(
                "WACC inputs: risk_free_rate, equity_risk_premium, beta, "
                "cost_of_debt, tax_rate, debt_weight, equity_weight."
            ),
            required=False,
        ),
    },
)

register_library_helper("dcf_valuation", execute, SCHEMA)
