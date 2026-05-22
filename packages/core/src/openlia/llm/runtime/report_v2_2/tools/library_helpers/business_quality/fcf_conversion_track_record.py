"""fcf_conversion_track_record — FCF / NI ratio over time, stability, trend.

Registered name: "fcf_conversion_track_record"
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
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper


def execute(
    fcf_series: list[float],
    net_income_series: list[float],
    period_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Compute FCF conversion track record (FCF / NI over time).

    A ratio > 1 indicates earnings are more than fully backed by free cash flow.
    Stable, high ratios signal high-quality earnings.

    Args:
        fcf_series: Free cash flow per period (oldest first).
        net_income_series: Net income per period (oldest first).
        period_labels: Optional period labels.

    Returns:
        Dict with per-period FCF/NI, average, stability (stdev), and trend.
    """
    n = len(fcf_series)
    if n < 1:
        raise ValueError("fcf_series must have at least one period")
    if len(net_income_series) != n:
        raise ValueError("fcf_series and net_income_series must have equal length")

    labels = period_labels if period_labels is not None else [f"Period {i + 1}" for i in range(n)]

    periods: list[dict[str, Any]] = []
    for i in range(n):
        fcf = fcf_series[i]
        ni = net_income_series[i]
        ratio = fcf / ni if ni != 0 else None
        periods.append(
            {
                "label": labels[i],
                "fcf": fcf,
                "net_income": ni,
                "fcf_to_ni": round(ratio, 4) if ratio is not None else None,
            }
        )

    ratios = [p["fcf_to_ni"] for p in periods if p["fcf_to_ni"] is not None]
    avg_conversion = sum(ratios) / len(ratios) if ratios else None

    # Stability: standard deviation of conversion ratios
    stability: float | None = None
    if len(ratios) >= 2 and avg_conversion is not None:
        variance = sum((r - avg_conversion) ** 2 for r in ratios) / len(ratios)
        stability = round(variance**0.5, 4)

    # Trend: last vs first half
    trend = "insufficient_data"
    if n >= 4:
        mid = n // 2
        recent_ratios = [p["fcf_to_ni"] for p in periods[mid:] if p["fcf_to_ni"] is not None]
        earlier_ratios = [p["fcf_to_ni"] for p in periods[:mid] if p["fcf_to_ni"] is not None]
        if recent_ratios and earlier_ratios:
            recent_avg = sum(recent_ratios) / len(recent_ratios)
            earlier_avg = sum(earlier_ratios) / len(earlier_ratios)
            if recent_avg > earlier_avg + 0.05:
                trend = "improving"
            elif recent_avg < earlier_avg - 0.05:
                trend = "declining"
            else:
                trend = "stable"

    return {
        "periods": periods,
        "avg_fcf_to_ni": round(avg_conversion, 4) if avg_conversion is not None else None,
        "stability_stdev": stability,
        "trend": trend,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="fcf_conversion_track_record",
        category=Category.BUSINESS_QUALITY,
        one_liner="FCF / Net Income conversion ratio over time: stability and trend.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Track FCF / NI conversion over multiple periods to assess earnings quality. "
            "High, stable conversion signals cash-backed earnings."
        ),
        when_to_use=[
            "Supplementing QoE panel with FCF-to-NI time series.",
            "Identifying periods of divergence between earnings and cash generation.",
        ],
        when_not_to_use=[
            "Full earnings quality with accruals and Sloan — use quality_of_earnings_panel.",
            "FCF yield or shareholder return analysis — use total_shareholder_yield.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "fcf_series": HelperParam(
                type="list[float]",
                required=True,
                description="Free cash flow per period (oldest first).",
            ),
            "net_income_series": HelperParam(
                type="list[float]",
                required=True,
                description="Net income per period (oldest first).",
            ),
            "period_labels": HelperParam(
                type="list[str] | None",
                required=False,
                default=None,
                description="Optional period labels.",
            ),
        },
        outputs=[
            HelperOutput(
                name="fcf_conversion",
                type="dict",
                description=(
                    "periods (label, fcf, ni, fcf_to_ni), "
                    "avg_fcf_to_ni, stability_stdev, trend."
                ),
            ),
        ],
        produces_artifacts=["fcf_conversion_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
