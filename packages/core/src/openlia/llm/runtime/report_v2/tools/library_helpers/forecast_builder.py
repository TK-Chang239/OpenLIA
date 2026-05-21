"""
Vendored from alirezarezvani/claude-skills (MIT License).
Original: finance/skills/financial-analyst/scripts/forecast_builder.py
Vendored on 2026-05-21 for OpenLIA report_v2 library helpers.

Adapted to expose a HelperSchema via SCHEMA module-level constant and an
execute(**params) entry point.
"""

from __future__ import annotations

from statistics import mean
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


def simple_linear_regression(
    x_values: list[float],
    y_values: list[float],
) -> tuple[float, float, float]:
    """Simple linear regression. Returns (slope, intercept, r_squared)."""
    n = len(x_values)
    if n < 2 or n != len(y_values):
        return (0.0, 0.0, 0.0)

    x_mean = mean(x_values)
    y_mean = mean(y_values)
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values, strict=True))
    ss_xx = sum((x - x_mean) ** 2 for x in x_values)
    ss_yy = sum((y - y_mean) ** 2 for y in y_values)
    slope = safe_divide(ss_xy, ss_xx)
    intercept = y_mean - slope * x_mean
    r_squared = safe_divide(ss_xy**2, ss_xx * ss_yy) if ss_yy > 0 else 0.0
    return (slope, intercept, r_squared)


class ForecastBuilder:
    """Driver-based revenue forecasting with scenario modeling."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.historical: list[dict[str, Any]] = data.get("historical_periods", [])
        self.drivers: dict[str, Any] = data.get("drivers", {})
        self.assumptions: dict[str, Any] = data.get("assumptions", {})
        self.cash_flow_inputs: dict[str, Any] = data.get("cash_flow_inputs", {})
        self.scenarios_config: dict[str, Any] = data.get("scenarios", {})
        self.forecast_periods: int = data.get("forecast_periods", 12)

    def analyze_trends(self) -> dict[str, Any]:
        """Analyze historical trends using linear regression."""
        if not self.historical:
            return {"error": "No historical data available"}

        revenues = [p.get("revenue", 0) for p in self.historical]
        periods = list(range(1, len(revenues) + 1))
        slope, intercept, r_squared = simple_linear_regression(
            [float(x) for x in periods],
            [float(y) for y in revenues],
        )

        growth_rates = []
        for i in range(1, len(revenues)):
            if revenues[i - 1] > 0:
                growth = (revenues[i] - revenues[i - 1]) / revenues[i - 1]
                growth_rates.append(growth)

        avg_growth = mean(growth_rates) if growth_rates else 0.0
        seasonality_index: list[float] = []
        if len(revenues) >= 4:
            overall_avg = mean(revenues)
            if overall_avg > 0:
                seasonality_index = [r / overall_avg for r in revenues[-4:]]

        return {
            "trend": {
                "slope": round(slope, 2),
                "intercept": round(intercept, 2),
                "r_squared": round(r_squared, 4),
                "direction": "upward" if slope > 0 else "downward" if slope < 0 else "flat",
            },
            "growth_rates": [round(g, 4) for g in growth_rates],
            "average_growth_rate": round(avg_growth, 4),
            "seasonality_index": [round(s, 4) for s in seasonality_index],
            "historical_revenues": revenues,
        }

    def build_driver_based_forecast(self, scenario: str = "base") -> dict[str, Any]:
        """Build a driver-based revenue forecast."""
        scenario_adjustments = self.scenarios_config.get(scenario, {})
        growth_adjustment = scenario_adjustments.get("growth_adjustment", 0.0)
        margin_adjustment = scenario_adjustments.get("margin_adjustment", 0.0)

        base_revenue = 0.0
        if self.historical:
            base_revenue = self.historical[-1].get("revenue", 0)

        unit_drivers = self.drivers.get("units", {})
        price_drivers = self.drivers.get("pricing", {})
        base_growth = self.assumptions.get("revenue_growth_rate", 0.05)
        adjusted_growth = base_growth + growth_adjustment
        base_margin = self.assumptions.get("gross_margin", 0.40)
        adjusted_margin = base_margin + margin_adjustment
        cogs_pct = 1.0 - adjusted_margin
        opex_pct = self.assumptions.get("opex_pct_revenue", 0.25)

        forecast_periods: list[dict[str, Any]] = []
        current_revenue = base_revenue
        has_unit_drivers = bool(unit_drivers) and bool(price_drivers)

        if has_unit_drivers:
            base_units = unit_drivers.get("base_units", 1000)
            unit_growth = unit_drivers.get("growth_rate", 0.03) + growth_adjustment
            base_price = price_drivers.get("base_price", 100)
            price_growth = price_drivers.get("annual_increase", 0.02)
            current_units = base_units
            current_price = base_price

            for period in range(1, self.forecast_periods + 1):
                current_units = current_units * (1 + unit_growth / 12)
                if period % 12 == 0:
                    current_price = current_price * (1 + price_growth)
                period_revenue = current_units * current_price
                cogs = period_revenue * cogs_pct
                gross_profit = period_revenue - cogs
                opex = period_revenue * opex_pct
                operating_income = gross_profit - opex
                forecast_periods.append(
                    {
                        "period": period,
                        "revenue": round(period_revenue, 2),
                        "units": round(current_units, 0),
                        "price": round(current_price, 2),
                        "cogs": round(cogs, 2),
                        "gross_profit": round(gross_profit, 2),
                        "gross_margin": round(adjusted_margin, 4),
                        "opex": round(opex, 2),
                        "operating_income": round(operating_income, 2),
                    }
                )
        else:
            monthly_growth = (1 + adjusted_growth) ** (1 / 12) - 1
            for period in range(1, self.forecast_periods + 1):
                current_revenue = current_revenue * (1 + monthly_growth)
                cogs = current_revenue * cogs_pct
                gross_profit = current_revenue - cogs
                opex = current_revenue * opex_pct
                operating_income = gross_profit - opex
                forecast_periods.append(
                    {
                        "period": period,
                        "revenue": round(current_revenue, 2),
                        "cogs": round(cogs, 2),
                        "gross_profit": round(gross_profit, 2),
                        "gross_margin": round(adjusted_margin, 4),
                        "opex": round(opex, 2),
                        "operating_income": round(operating_income, 2),
                    }
                )

        total_revenue = sum(p["revenue"] for p in forecast_periods)
        total_operating_income = sum(p["operating_income"] for p in forecast_periods)
        return {
            "scenario": scenario,
            "growth_rate": round(adjusted_growth, 4),
            "gross_margin": round(adjusted_margin, 4),
            "forecast_periods": forecast_periods,
            "total_revenue": round(total_revenue, 2),
            "total_operating_income": round(total_operating_income, 2),
            "average_monthly_revenue": round(safe_divide(total_revenue, len(forecast_periods)), 2),
        }

    def build_rolling_cash_flow(self, weeks: int = 13) -> dict[str, Any]:
        """Build a 13-week rolling cash flow projection."""
        cfi = self.cash_flow_inputs
        opening_balance = cfi.get("opening_cash_balance", 0)
        weekly_revenue = cfi.get("weekly_revenue", 0)
        collection_rate = cfi.get("collection_rate", 0.85)
        collection_lag_weeks = cfi.get("collection_lag_weeks", 2)
        weekly_payroll = cfi.get("weekly_payroll", 0)
        weekly_rent = cfi.get("weekly_rent", 0)
        weekly_operating = cfi.get("weekly_operating", 0)
        weekly_other = cfi.get("weekly_other", 0)
        total_weekly_expenses = weekly_payroll + weekly_rent + weekly_operating + weekly_other
        one_time_items: list[dict[str, Any]] = cfi.get("one_time_items", [])
        weekly_projections: list[dict[str, Any]] = []
        running_balance = opening_balance
        revenue_pipeline: list[float] = [0.0] * collection_lag_weeks

        for week in range(1, weeks + 1):
            revenue_pipeline.append(weekly_revenue)
            collections = revenue_pipeline.pop(0) * collection_rate
            one_time_inflows = 0.0
            one_time_outflows = 0.0
            one_time_labels: list[str] = []
            for item in one_time_items:
                if item.get("week") == week:
                    amount = item.get("amount", 0)
                    if amount > 0:
                        one_time_inflows += amount
                    else:
                        one_time_outflows += abs(amount)
                    one_time_labels.append(item.get("description", ""))
            total_inflows = collections + one_time_inflows
            total_outflows = total_weekly_expenses + one_time_outflows
            net_cash_flow = total_inflows - total_outflows
            running_balance += net_cash_flow
            weekly_projections.append(
                {
                    "week": week,
                    "collections": round(collections, 2),
                    "one_time_inflows": round(one_time_inflows, 2),
                    "total_inflows": round(total_inflows, 2),
                    "payroll": round(weekly_payroll, 2),
                    "rent": round(weekly_rent, 2),
                    "operating": round(weekly_operating, 2),
                    "other_expenses": round(weekly_other, 2),
                    "one_time_outflows": round(one_time_outflows, 2),
                    "total_outflows": round(total_outflows, 2),
                    "net_cash_flow": round(net_cash_flow, 2),
                    "closing_balance": round(running_balance, 2),
                    "notes": ", ".join(one_time_labels) if one_time_labels else "",
                }
            )

        total_inflows_sum = sum(w["total_inflows"] for w in weekly_projections)
        total_outflows_sum = sum(w["total_outflows"] for w in weekly_projections)
        min_balance = min(w["closing_balance"] for w in weekly_projections)
        min_balance_week = next(
            w["week"] for w in weekly_projections if w["closing_balance"] == min_balance
        )
        return {
            "weeks": weeks,
            "opening_balance": opening_balance,
            "closing_balance": round(running_balance, 2),
            "total_inflows": round(total_inflows_sum, 2),
            "total_outflows": round(total_outflows_sum, 2),
            "net_change": round(total_inflows_sum - total_outflows_sum, 2),
            "minimum_balance": round(min_balance, 2),
            "minimum_balance_week": min_balance_week,
            "cash_runway_weeks": (
                round(safe_divide(running_balance, total_weekly_expenses))
                if total_weekly_expenses > 0
                else None
            ),
            "weekly_projections": weekly_projections,
        }

    def build_scenario_comparison(
        self,
        scenarios: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build and compare multiple scenarios."""
        if scenarios is None:
            scenarios = ["base", "bull", "bear"]
        scenario_results: dict[str, Any] = {}
        for scenario in scenarios:
            scenario_results[scenario] = self.build_driver_based_forecast(scenario)
        comparison: list[dict[str, Any]] = []
        for scenario in scenarios:
            result = scenario_results[scenario]
            comparison.append(
                {
                    "scenario": scenario,
                    "total_revenue": result["total_revenue"],
                    "total_operating_income": result["total_operating_income"],
                    "growth_rate": result["growth_rate"],
                    "gross_margin": result["gross_margin"],
                    "avg_monthly_revenue": result["average_monthly_revenue"],
                }
            )
        return {"scenarios": scenario_results, "comparison": comparison}

    def run_full_forecast(
        self,
        scenarios: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the complete forecast analysis."""
        trends = self.analyze_trends()
        scenario_comparison = self.build_scenario_comparison(scenarios)
        cash_flow = self.build_rolling_cash_flow()
        return {
            "trend_analysis": trends,
            "scenario_comparison": scenario_comparison,
            "rolling_cash_flow": cash_flow,
        }


def execute(**params: Any) -> dict[str, Any]:
    """Run driver-based revenue forecast.

    Params:
        historical_periods: list of dicts with 'revenue' key (required)
        assumptions: dict with revenue_growth_rate, gross_margin, opex_pct_revenue
        drivers: dict with 'units' and 'pricing' sub-dicts for unit economics
        scenarios: dict mapping scenario name to growth/margin adjustments
        cash_flow_inputs: dict for 13-week rolling cash flow projection
        forecast_periods: number of periods to project (default 12)
        scenarios_list: list of scenario names to compare (default base/bull/bear)
    """
    data = {
        "historical_periods": params.get("historical_periods", []),
        "drivers": params.get("drivers", {}),
        "assumptions": params.get("assumptions", {}),
        "cash_flow_inputs": params.get("cash_flow_inputs", {}),
        "scenarios": params.get("scenarios", {}),
        "forecast_periods": params.get("forecast_periods", 12),
    }
    builder = ForecastBuilder(data)
    return builder.run_full_forecast(params.get("scenarios_list"))


SCHEMA = HelperSchema(
    name="forecast_builder",
    description=(
        "Driver-based revenue forecasting with 13-week rolling cash flow projection, "
        "scenario modeling (base/bull/bear), and trend analysis via linear regression."
    ),
    params={
        "historical_periods": HelperParam(
            type="list[dict]",
            description="Historical revenue periods. Each dict has at least 'revenue' key.",
            required=True,
        ),
        "assumptions": HelperParam(
            type="dict",
            default=None,
            description="Assumptions: revenue_growth_rate, gross_margin, opex_pct_revenue.",
            required=False,
        ),
        "drivers": HelperParam(
            type="dict",
            default=None,
            description=(
                "Unit/price drivers: "
                "{'units': {base_units, growth_rate}, 'pricing': {base_price, annual_increase}}."
            ),
            required=False,
        ),
        "scenarios": HelperParam(
            type="dict",
            default=None,
            description=(
                "Scenario overrides: "
                "{'bull': {growth_adjustment, margin_adjustment}, 'bear': {...}}."
            ),
            required=False,
        ),
        "cash_flow_inputs": HelperParam(
            type="dict",
            default=None,
            description=(
                "Cash flow inputs for 13-week projection: "
                "opening_cash_balance, weekly_revenue, etc."
            ),
            required=False,
        ),
        "forecast_periods": HelperParam(
            type="int",
            default=12,
            description="Number of periods to project.",
            required=False,
        ),
    },
)

register_library_helper("forecast_builder", execute, SCHEMA)
