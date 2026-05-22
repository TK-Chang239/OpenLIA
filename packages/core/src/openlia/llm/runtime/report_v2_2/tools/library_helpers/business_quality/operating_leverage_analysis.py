"""operating_leverage_analysis — DOL, fixed/variable cost decomposition.

Registered name: "operating_leverage_analysis"

Audit fix §9.5 applied: DOL = % change in EBIT / % change in Revenue.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper


def execute(
    revenue: float,
    revenue_prior: float,
    ebit: float,
    ebit_prior: float,
    fixed_costs: float | None = None,
    variable_costs: float | None = None,
) -> dict[str, Any]:
    """Compute Degree of Operating Leverage and cost structure.

    DOL = (% change in EBIT) / (% change in Revenue)  [audit fix §9.5]
    DOL > 1 indicates earnings amplify revenue changes.

    Fixed vs variable cost decomposition is optional; if provided, also computes
    contribution margin and break-even revenue.

    Args:
        revenue: Current period revenue.
        revenue_prior: Prior period revenue.
        ebit: Current period EBIT.
        ebit_prior: Prior period EBIT.
        fixed_costs: Optional total fixed costs (for contribution margin analysis).
        variable_costs: Optional total variable costs.

    Returns:
        Dict with DOL, pct change metrics, and optional cost structure.
    """
    if revenue_prior == 0:
        raise ValueError("revenue_prior must be non-zero for DOL computation")
    if ebit_prior == 0:
        raise ValueError("ebit_prior must be non-zero for DOL computation")

    pct_change_revenue = (revenue - revenue_prior) / abs(revenue_prior) * 100.0
    pct_change_ebit = (ebit - ebit_prior) / abs(ebit_prior) * 100.0

    # DOL = % change EBIT / % change Revenue (audit fix §9.5)
    if pct_change_revenue == 0:
        dol = None
        dol_warning = "Revenue growth is 0; DOL is undefined"
    else:
        dol = pct_change_ebit / pct_change_revenue
        dol_warning = None

    # Cost structure (if provided)
    cost_structure: dict[str, Any] | None = None
    if fixed_costs is not None and variable_costs is not None:
        total_costs = fixed_costs + variable_costs
        fixed_cost_ratio = fixed_costs / total_costs if total_costs != 0 else None
        variable_cost_ratio = variable_costs / total_costs if total_costs != 0 else None

        # Contribution margin = Revenue - Variable Costs
        contribution_margin = revenue - variable_costs
        contribution_margin_ratio = contribution_margin / revenue if revenue != 0 else None

        # Break-even revenue = Fixed Costs / Contribution Margin Ratio
        break_even = fixed_costs / contribution_margin_ratio if contribution_margin_ratio else None

        cost_structure = {
            "fixed_costs": fixed_costs,
            "variable_costs": variable_costs,
            "total_costs": round(total_costs, 2),
            "fixed_cost_ratio": round(fixed_cost_ratio, 4)
            if fixed_cost_ratio is not None
            else None,
            "variable_cost_ratio": round(variable_cost_ratio, 4)
            if variable_cost_ratio is not None
            else None,
            "contribution_margin": round(contribution_margin, 2),
            "contribution_margin_ratio": round(contribution_margin_ratio, 4)
            if contribution_margin_ratio is not None
            else None,
            "break_even_revenue": round(break_even, 2) if break_even is not None else None,
        }

    result: dict[str, Any] = {
        "revenue": revenue,
        "revenue_prior": revenue_prior,
        "ebit": ebit,
        "ebit_prior": ebit_prior,
        "pct_change_revenue": round(pct_change_revenue, 2),
        "pct_change_ebit": round(pct_change_ebit, 2),
        "dol": round(dol, 4) if dol is not None else None,
        "dol_warning": dol_warning,
        "cost_structure": cost_structure,
    }

    return result


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="operating_leverage_analysis",
        category=Category.BUSINESS_QUALITY,
        one_liner="DOL = %EBIT / %Revenue; optional fixed/variable cost decomposition.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute Degree of Operating Leverage (DOL = % change EBIT / % change Revenue) "
            "and optionally decompose into fixed vs variable costs with break-even analysis. "
            "Applies audit fix §9.5: uses period-over-period % changes."
        ),
        when_to_use=[
            "Assessing earnings sensitivity to revenue changes in equity research.",
            "Evaluating cost structure risk in cyclical businesses.",
        ],
        when_not_to_use=[
            "Financial leverage (D/E) — use ft_solvency_ratios.",
            "Revenue regression over many periods — use margin_trajectory_regression.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "revenue": HelperParam(
                type="float", required=True, description="Current period revenue."
            ),
            "revenue_prior": HelperParam(
                type="float", required=True, description="Prior period revenue."
            ),
            "ebit": HelperParam(type="float", required=True, description="Current period EBIT."),
            "ebit_prior": HelperParam(
                type="float", required=True, description="Prior period EBIT."
            ),
            "fixed_costs": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Optional total fixed costs for break-even analysis.",
            ),
            "variable_costs": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Optional total variable costs.",
            ),
        },
        outputs=[
            HelperOutput(
                name="operating_leverage",
                type="dict",
                description=(
                    "pct_change_revenue, pct_change_ebit, dol, dol_warning, "
                    "optional cost_structure with break-even."
                ),
            ),
        ],
        produces_artifacts=["operating_leverage_output"],
        consumes_artifacts=[],
    ),
    verifier_hooks=[VerifierIssueType.NUMERIC_INCONSISTENCY],
)

register_helper(_SCHEMA, execute)
