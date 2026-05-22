"""v2.2 wrapper for the dcf_valuation helper.

Imports the implementation from report_v2 (no duplication) and declares a
HelperSchema per the v2.2 four-tier contract.

Skeleton impl — full DCF engine with skill doc lands in PR 2.2.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.library_helpers.dcf_valuation import (
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
        name="dcf_valuation",
        category=Category.DCF,
        one_liner="DCF enterprise and equity valuation with WACC, terminal value, and sensitivity.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Run a discounted cash flow valuation: project FCFs, calculate WACC, "
            "derive terminal value via perpetuity growth and exit multiple, "
            "and produce a 2-D sensitivity grid over WACC and terminal growth rate."
        ),
        when_to_use=[
            "Intrinsic equity valuation requiring explicit FCF projections.",
            "When the analyst needs both perpetuity-growth and exit-multiple TV methods.",
            "When sensitivity analysis over WACC and terminal growth is required.",
        ],
        when_not_to_use=[
            "Quick comparables-based valuation — use ratio_calculator instead.",
            "Capex go/no-go decisions — use business_investment instead.",
        ],
    ),
    contract=MechanicalContract(
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
        outputs=[
            HelperOutput(
                name="dcf_valuation_output",
                type="dcf_valuation_output",
                description=(
                    "WACC, FCF schedule, terminal value (both methods), enterprise value, "
                    "equity value, per-share value, and 2-D sensitivity table."
                ),
            ),
        ],
        produces_artifacts=["dcf_valuation_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,  # TODO(PR 2.2): add skill_doc with step-by-step DCF build guide
    verifier_hooks=[],
)

register_helper(_SCHEMA, _impl)
