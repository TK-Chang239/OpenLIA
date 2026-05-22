"""v2.2 wrapper for the business_investment helper.

Imports the implementation from report_v2 (no duplication) and declares a
HelperSchema per the v2.2 four-tier contract.

DEPRECATED as of v0.2.0. Slated for removal in a follow-up cleanup PR after 2.5.
This wrapper remains registered for backward compatibility.
For capital allocation analysis, migrate to capital_allocation_history.
For ROI / NPV / IRR computation, this helper remains available until removal.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.library_helpers.business_investment import (
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
    deprecated_at_version="0.2.0",
    directory=DirectoryEntry(
        name="business_investment",
        category=Category.DECISION,
        one_liner="ROI, payback, NPV, IRR, scoring rubric, and three-scenario capex analysis.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Evaluate a business investment decision using ROI, payback period, NPV, IRR, "
            "a weighted scoring rubric, and base/upside/downside scenario comparison."
        ),
        when_to_use=[
            "Assessing capex decisions: equipment, hiring, technology, or real estate.",
            "Comparing investment alternatives with a single scoring summary.",
            "When NPV and IRR are needed alongside a qualitative scoring rubric.",
        ],
        when_not_to_use=[
            "Full DCF equity valuation — use dcf_valuation instead.",
            "Revenue forecasting — use forecast_builder instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "total_investment": HelperParam(
                type="float",
                description="Total upfront investment cost.",
                required=True,
            ),
            "annual_net_cash_flow": HelperParam(
                type="float",
                description=(
                    "Expected annual net cash inflow "
                    "(revenue increase or cost savings minus ongoing costs)."
                ),
                required=True,
            ),
            "useful_life_years": HelperParam(
                type="int",
                description="Expected useful life of the investment in years.",
                required=True,
            ),
            "discount_rate": HelperParam(
                type="float",
                default=0.10,
                description="Cost of capital as a decimal (default 0.10 = 10%).",
                required=False,
            ),
            "strategic_fit": HelperParam(
                type="int",
                default=3,
                description="Strategic fit score 1-5 (5=core to mission).",
                required=False,
            ),
            "risk_level": HelperParam(
                type="int",
                default=3,
                description="Risk level score 1-5 (5=low/proven risk).",
                required=False,
            ),
            "reversibility": HelperParam(
                type="int",
                default=3,
                description="Reversibility score 1-5 (5=easy to exit).",
                required=False,
            ),
            "cash_flow_impact": HelperParam(
                type="int",
                default=3,
                description="Cash flow impact score 1-5 (5=self-funding quickly).",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="business_investment_output",
                type="business_investment_output",
                description=("Summary metrics, scoring rubric, three scenarios, and flags list."),
            ),
        ],
        produces_artifacts=["business_investment_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[],
)

register_helper(_SCHEMA, _impl)
