"""v2.2 wrapper for the forecast_builder helper.

Imports the implementation from report_v2 (no duplication) and declares a
HelperSchema per the v2.2 four-tier contract.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.library_helpers.forecast_builder import (
    execute as _impl,
)
from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="forecast_builder",
        category=Category.BUSINESS_QUALITY,
        one_liner="Driver-based revenue forecast with scenario modeling and 13-week cash flow.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Build a driver-based revenue forecast with base/bull/bear scenario comparison, "
            "linear-regression trend analysis, and a 13-week rolling cash flow projection."
        ),
        when_to_use=[
            "Forward revenue forecasting over 1-12 periods with unit/price drivers.",
            "Short-term cash flow planning with a 13-week rolling view.",
            "When scenario-based (bull/base/bear) revenue ranges are needed.",
        ],
        when_not_to_use=[
            "Full DCF equity valuation — use dcf_valuation instead.",
            "Comparing actuals vs a fixed budget baseline — use budget_variance instead.",
        ],
    ),
    contract=MechanicalContract(
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
                    "{'units': {base_units, growth_rate}, "
                    "'pricing': {base_price, annual_increase}}."
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
        outputs=[
            HelperOutput(
                name="forecast_output",
                type="forecast_output",
                description=(
                    "Trend analysis, scenario comparison (all scenarios), "
                    "and 13-week rolling cash flow projection."
                ),
            ),
        ],
        produces_artifacts=["forecast_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[],
)

register_helper(_SCHEMA, _impl)
