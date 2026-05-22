"""v2.2 wrapper for the saas_metrics helper.

Imports the implementation from report_v2 (no duplication) and declares a
HelperSchema per the v2.2 four-tier contract.

DEPRECATED as of v0.2.0. Superseded by saas_kpi_panel (PR 2.9).
This wrapper remains registered for backward compatibility; do not use for new
analysis. Migrate to: saas_kpi_panel (Category.SAAS_KPIS).
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.library_helpers.saas_metrics import (
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
        name="saas_metrics",
        category=Category.SAAS_KPIS,
        one_liner="SaaS KPIs: MRR/ARR, churn, CAC, LTV, NRR, Rule of 40, and unit-econ sim.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute SaaS unit economics (MRR, ARR, churn, CAC, LTV, LTV:CAC, payback, NRR, "
            "Rule of 40), SaaS quick ratio, or simulate unit economics forward N months."
        ),
        when_to_use=[
            "Analyzing SaaS business health: mode='metrics' for core KPIs.",
            "Measuring revenue growth efficiency: mode='quick_ratio'.",
            "Projecting MRR growth and profitability forward: mode='simulate'.",
        ],
        when_not_to_use=[
            "DEPRECATED — prefer saas_kpi_panel for all new quarterly KPI analysis.",
            "Non-SaaS businesses — use ratio_calculator for general financial ratios.",
            "Full DCF valuation — use dcf_valuation instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "mode": HelperParam(
                type="str",
                default="metrics",
                description="Computation mode: 'metrics' (default), 'quick_ratio', or 'simulate'.",
                required=False,
            ),
            "mrr": HelperParam(
                type="float",
                default=None,
                description="Current Monthly Recurring Revenue (metrics and simulate modes).",
                required=False,
            ),
            "mrr_last": HelperParam(
                type="float",
                default=None,
                description="MRR from last month (for MoM growth and NRR in metrics mode).",
                required=False,
            ),
            "customers": HelperParam(
                type="float",
                default=None,
                description="Total active customer count (metrics mode).",
                required=False,
            ),
            "churned": HelperParam(
                type="float",
                default=None,
                description="Customers churned this month (metrics mode).",
                required=False,
            ),
            "new_customers": HelperParam(
                type="float",
                default=None,
                description="New customers acquired this month (metrics mode).",
                required=False,
            ),
            "sm_spend": HelperParam(
                type="float",
                default=None,
                description="Sales and marketing spend this month (metrics mode).",
                required=False,
            ),
            "gross_margin": HelperParam(
                type="float",
                default=0.70,
                description="Gross margin as a decimal (default 0.70).",
                required=False,
            ),
            "expansion_mrr": HelperParam(
                type="float",
                default=0,
                description="Expansion MRR from upsells (metrics and quick_ratio modes).",
                required=False,
            ),
            "churned_mrr": HelperParam(
                type="float",
                default=0,
                description="MRR lost from churned customers (metrics and quick_ratio modes).",
                required=False,
            ),
            "contraction_mrr": HelperParam(
                type="float",
                default=0,
                description="MRR lost from downgrades (metrics and quick_ratio modes).",
                required=False,
            ),
            "new_mrr": HelperParam(
                type="float",
                default=None,
                description="New MRR from new customers (quick_ratio mode).",
                required=False,
            ),
            "monthly_growth_pct": HelperParam(
                type="float",
                default=None,
                description="Expected monthly growth rate as percentage (simulate mode).",
                required=False,
            ),
            "monthly_churn_pct": HelperParam(
                type="float",
                default=None,
                description="Expected monthly churn rate as percentage (simulate mode).",
                required=False,
            ),
            "cac": HelperParam(
                type="float",
                default=None,
                description="Customer acquisition cost (simulate mode).",
                required=False,
            ),
            "months": HelperParam(
                type="int",
                default=12,
                description="Number of months to project (simulate mode, default 12).",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="saas_metrics_output",
                type="saas_metrics_output",
                description=(
                    "Core SaaS KPIs, quick ratio breakdown, or unit economics simulation "
                    "depending on mode."
                ),
            ),
        ],
        produces_artifacts=["saas_metrics_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[],
)

register_helper(_SCHEMA, _impl)
