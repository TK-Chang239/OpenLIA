"""v2.2 wrapper for the budget_variance helper.

Imports the implementation from report_v2 (no duplication) and declares a
HelperSchema per the v2.2 four-tier contract.

DEPRECATED as of v0.2.0. Slated for removal in a follow-up cleanup PR after 2.5.
This wrapper remains registered for backward compatibility.
There is no direct PR 2.5 replacement; budget variance is not part of the equity
research business quality bundle. Callers using this for cost-structure analysis
should migrate to common_size_statements or capital_allocation_history.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.library_helpers.budget_variance import (
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
        name="budget_variance",
        category=Category.STATEMENT_INTEGRITY,
        one_liner="Actual vs budget variance with materiality filtering and dept/category split.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Analyze budget variances across revenue and expense line items, classifying each as "
            "favorable or unfavorable and filtering by materiality thresholds."
        ),
        when_to_use=[
            "Comparing actual vs budgeted financial performance for a period.",
            "Identifying material variances for management commentary.",
            "Summarizing variance performance by department or category.",
        ],
        when_not_to_use=[
            "When you need forecast projections forward — use forecast_builder instead.",
            "When comparing periods without a budget baseline — use ratio_calculator instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "line_items": HelperParam(
                type="list[dict]",
                description=(
                    "Budget line items. Each dict: name, type (revenue|expense), "
                    "department, category, actual, budget, optional prior_year."
                ),
                required=True,
            ),
            "period": HelperParam(
                type="str",
                default="Current Period",
                description="Label for the analysis period.",
                required=False,
            ),
            "company": HelperParam(
                type="str",
                default="Company",
                description="Company name for the report header.",
                required=False,
            ),
            "threshold_pct": HelperParam(
                type="float",
                default=10.0,
                description="Materiality threshold as percentage variance (default 10%).",
                required=False,
            ),
            "threshold_amt": HelperParam(
                type="float",
                default=50000.0,
                description="Materiality threshold as dollar amount (default $50K).",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="budget_variance_output",
                type="budget_variance_output",
                description=(
                    "Executive summary, all line-item variances, material variances, "
                    "department summary, and category summary."
                ),
            ),
        ],
        produces_artifacts=["budget_variance_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[],
)

register_helper(_SCHEMA, _impl)
