"""quality_of_earnings_panel — Earnings quality: accruals, Sloan, CFO/NI, R&D cap.

Registered name: "quality_of_earnings_panel"

Audit fixes applied:
  - accruals_pct_of_ni (audit fix §9.7): (NI - CFO) / NI as %; warn if > 20%
  - Sloan ratio (audit fix §9.1): Sloan = (NI - CFO - CFI) / Avg Total Assets
    (discriminates true accruals from financing activities)
  - Capitalized R&D (audit fix §9.6): adjust NOPAT to capitalize R&D; show with/without
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

_ACCRUALS_WARN_THRESHOLD = 0.20  # 20% of NI


def execute(
    net_income: float,
    cfo: float,
    cfi: float,
    total_assets: float,
    total_assets_prior: float,
    rd_expense: float = 0.0,
    rd_amortization_years: int = 5,
    one_time_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute quality of earnings panel.

    Metrics:
      - accruals_pct_of_ni = (NI - CFO) / NI * 100
      - Sloan ratio = (NI - CFO - CFI) / avg_total_assets  [audit fix §9.1]
      - cfo_to_ni = CFO / NI
      - capitalized_rd_nopat_delta: adjusting NI upward for capitalized R&D

    Args:
        net_income: Net income for the period.
        cfo: Cash flow from operations.
        cfi: Cash flow from investing.
        total_assets: Total assets, current period.
        total_assets_prior: Total assets, prior period (for Sloan avg denominator).
        rd_expense: R&D expense reported in income statement.
        rd_amortization_years: Assumed useful life for R&D cap (default 5 years).
        one_time_items: Optional list of {"name": str, "amount": float, "type": str}.

    Returns:
        Dict with all QoE metrics, warnings, and capitalized R&D delta.
    """
    if total_assets == 0:
        raise ValueError("total_assets must be non-zero")

    # accruals_pct_of_ni (audit fix §9.7)
    accruals = net_income - cfo
    accruals_pct_of_ni: float | None = None
    accruals_warning = False
    if net_income != 0:
        accruals_pct_of_ni = (accruals / net_income) * 100.0
        accruals_warning = abs(accruals_pct_of_ni) > _ACCRUALS_WARN_THRESHOLD * 100

    # Sloan ratio (audit fix §9.1): (NI - CFO - CFI) / avg_total_assets
    avg_total_assets = (
        (total_assets + total_assets_prior) / 2.0 if total_assets_prior != 0 else total_assets
    )
    sloan_ratio = (net_income - cfo - cfi) / avg_total_assets

    # CFO / NI ratio
    cfo_to_ni: float | None = None
    if net_income != 0:
        cfo_to_ni = cfo / net_income

    # Capitalized R&D adjustment (audit fix §9.6)
    # Simple straight-line: capitalize this year's R&D, amortize 1/N per year
    # Net NI impact = R&D expense - (R&D / amortization_years)
    rd_cap_nopat_delta: float | None = None
    ni_adjusted_for_rd_cap: float | None = None
    if rd_expense != 0 and rd_amortization_years > 0:
        amortization = rd_expense / rd_amortization_years
        rd_cap_nopat_delta = rd_expense - amortization  # net add-back
        ni_adjusted_for_rd_cap = net_income + rd_cap_nopat_delta

    # One-time items summary
    one_time_total = 0.0
    if one_time_items:
        one_time_total = sum(item.get("amount", 0.0) for item in one_time_items)

    warnings: list[str] = []
    if accruals_warning:
        warnings.append(
            f"accruals_pct_of_ni {accruals_pct_of_ni:.1f}% exceeds 20% threshold — "
            "low earnings quality signal"
        )
    if sloan_ratio > 0.10:
        warnings.append(
            f"Sloan ratio {sloan_ratio:.3f} > 0.10 — accrual-heavy earnings, mean reversion risk"
        )

    return {
        "accruals": round(accruals, 2),
        "accruals_pct_of_ni": round(accruals_pct_of_ni, 2)
        if accruals_pct_of_ni is not None
        else None,
        "accruals_warning": accruals_warning,
        "sloan_ratio": round(sloan_ratio, 4),
        "cfo_to_ni": round(cfo_to_ni, 4) if cfo_to_ni is not None else None,
        "rd_expense": rd_expense,
        "rd_amortization_years": rd_amortization_years,
        "rd_cap_nopat_delta": round(rd_cap_nopat_delta, 2)
        if rd_cap_nopat_delta is not None
        else None,
        "ni_without_rd_cap": round(net_income, 2),
        "ni_with_rd_cap": round(ni_adjusted_for_rd_cap, 2)
        if ni_adjusted_for_rd_cap is not None
        else None,
        "one_time_items": one_time_items or [],
        "one_time_total": round(one_time_total, 2),
        "warnings": warnings,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="quality_of_earnings_panel",
        category=Category.BUSINESS_QUALITY,
        one_liner="Accruals pct, Sloan ratio, CFO/NI, capitalized R&D, one-time items.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Evaluate earnings quality using accruals (% of NI), Sloan ratio "
            "(using CFO and CFI per audit-fix §9.1), CFO/NI, and capitalized R&D "
            "adjustment. Flags high-accrual or low-quality earnings."
        ),
        when_to_use=[
            "Red-flag screening for earnings quality in equity research.",
            "When capitalizing R&D to show adjusted NOPAT.",
            "Supplementing forensic_panel with detailed QoE metrics.",
        ],
        when_not_to_use=[
            "Standalone Piotroski scoring — use piotroski_f_score.",
            "Full forensic aggregation — use forensic_panel.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "net_income": HelperParam(type="float", required=True, description="Net income."),
            "cfo": HelperParam(
                type="float", required=True, description="Cash flow from operations."
            ),
            "cfi": HelperParam(
                type="float", required=True, description="Cash flow from investing."
            ),
            "total_assets": HelperParam(
                type="float", required=True, description="Total assets, current period."
            ),
            "total_assets_prior": HelperParam(
                type="float",
                required=True,
                description="Total assets, prior period. Required for Sloan avg denominator.",
            ),
            "rd_expense": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="R&D expense in income statement. Used for capitalized R&D adjustment.",
            ),
            "rd_amortization_years": HelperParam(
                type="int",
                required=False,
                default=5,
                description="Assumed useful life for R&D capitalization (default 5 years).",
            ),
            "one_time_items": HelperParam(
                type="list[dict] | None",
                required=False,
                default=None,
                description='Optional list of one-time items: [{"name", "amount", "type"}].',
            ),
        },
        outputs=[
            HelperOutput(
                name="quality_of_earnings",
                type="dict",
                description=(
                    "accruals, accruals_pct_of_ni, sloan_ratio, cfo_to_ni, "
                    "rd_cap_nopat_delta, ni_with/without_rd_cap, one_time_total, warnings."
                ),
            ),
        ],
        produces_artifacts=["quality_of_earnings_output"],
        consumes_artifacts=[],
    ),
    verifier_hooks=[VerifierIssueType.NUMERIC_INCONSISTENCY],
)

register_helper(_SCHEMA, execute)
