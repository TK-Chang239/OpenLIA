"""roic_panel — ROIC, ROIIC, Economic Profit, and WACC spread panel.

Registered name: "roic_panel"

Audit fixes applied:
  - ROIIC (audit fix §9.3): DELTA_NOPAT / DELTA_IC; period over period
  - Economic profit (audit fix §9.4): EP = (ROIC - WACC) * IC
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
    nopat_series: list[float],
    invested_capital_series: list[float],
    wacc: float,
    period_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Compute ROIC panel, ROIIC, Economic Profit, and WACC spread.

    Args:
        nopat_series: NOPAT per period (len N, oldest first).
        invested_capital_series: Invested Capital per period (len N, oldest first).
            Invested Capital = Total Equity + Total Debt - Cash.
        wacc: Weighted average cost of capital (decimal, e.g. 0.10 for 10%).
        period_labels: Optional period labels (e.g. ["FY2021", "FY2022", ...]).
            Must match len of nopat_series if provided.

    Returns:
        Dict with periods, roic, roic_vs_wacc, roiic, economic_profit, and summary.
    """
    n = len(nopat_series)
    if n < 1:
        raise ValueError("nopat_series must have at least one period")
    if len(invested_capital_series) != n:
        raise ValueError("nopat_series and invested_capital_series must have equal length")
    if period_labels is not None and len(period_labels) != n:
        raise ValueError("period_labels length must match nopat_series length")

    labels = period_labels if period_labels is not None else [f"Period {i + 1}" for i in range(n)]

    periods: list[dict[str, Any]] = []
    for i in range(n):
        ic = invested_capital_series[i]
        nopat = nopat_series[i]
        if ic == 0:
            roic = None
        else:
            roic = nopat / ic

        roic_vs_wacc = (roic - wacc) if roic is not None else None
        ep = roic_vs_wacc * ic if roic_vs_wacc is not None else None

        # ROIIC: DELTA_NOPAT / DELTA_IC — requires prior period
        roiic: float | None = None
        if i > 0:
            delta_nopat = nopat_series[i] - nopat_series[i - 1]
            delta_ic = invested_capital_series[i] - invested_capital_series[i - 1]
            if delta_ic != 0:
                roiic = delta_nopat / delta_ic

        periods.append(
            {
                "label": labels[i],
                "nopat": nopat,
                "invested_capital": ic,
                "roic": round(roic, 4) if roic is not None else None,
                "roic_vs_wacc": round(roic_vs_wacc, 4) if roic_vs_wacc is not None else None,
                "economic_profit": round(ep, 2) if ep is not None else None,
                "roiic": round(roiic, 4) if roiic is not None else None,
            }
        )

    # Summary statistics
    roic_values = [p["roic"] for p in periods if p["roic"] is not None]
    latest = periods[-1]
    avg_roic = sum(roic_values) / len(roic_values) if roic_values else None
    value_creating = (latest["roic_vs_wacc"] or 0) > 0

    return {
        "periods": periods,
        "wacc": wacc,
        "latest_roic": latest["roic"],
        "latest_roic_vs_wacc": latest["roic_vs_wacc"],
        "latest_economic_profit": latest["economic_profit"],
        "latest_roiic": latest["roiic"],
        "avg_roic": round(avg_roic, 4) if avg_roic is not None else None,
        "value_creating": value_creating,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="roic_panel",
        category=Category.BUSINESS_QUALITY,
        one_liner="ROIC trend, WACC spread, ROIIC, and Economic Profit panel.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute ROIC = NOPAT / Invested Capital over time, the ROIC-WACC spread, "
            "ROIIC (Return on Incremental Invested Capital), and Economic Profit. "
            "Assesses whether management creates or destroys economic value."
        ),
        when_to_use=[
            "Evaluating management capital allocation quality in an equity report.",
            "Comparing ROIC to WACC to determine value creation.",
            "When ROIIC is needed to assess incremental returns on new investment.",
        ],
        when_not_to_use=[
            "WACC derivation — use cost_of_capital_builder first.",
            "Valuation-grade NOPAT from raw financials — build NOPAT externally.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "nopat_series": HelperParam(
                type="list[float]",
                required=True,
                description="NOPAT per period (oldest first). NOPAT = EBIT * (1 - tax_rate).",
            ),
            "invested_capital_series": HelperParam(
                type="list[float]",
                required=True,
                description=(
                    "Invested Capital per period, same length as nopat_series. "
                    "IC = Equity + Debt - Cash."
                ),
            ),
            "wacc": HelperParam(
                type="float",
                required=True,
                description="WACC as decimal (e.g. 0.10 for 10%). From cost_of_capital_builder.",
            ),
            "period_labels": HelperParam(
                type="list[str] | None",
                required=False,
                default=None,
                description="Optional period labels matching nopat_series length.",
            ),
        },
        outputs=[
            HelperOutput(
                name="roic_panel",
                type="dict",
                description=(
                    "periods list (label, nopat, IC, roic, roic_vs_wacc, EP, roiic), "
                    "latest and avg ROIC, value_creating flag."
                ),
            ),
        ],
        produces_artifacts=["roic_panel_output"],
        consumes_artifacts=[],
        data_dependencies=["cost_of_capital_builder"],
    ),
    verifier_hooks=[VerifierIssueType.NUMERIC_INCONSISTENCY],
)

register_helper(_SCHEMA, execute)
