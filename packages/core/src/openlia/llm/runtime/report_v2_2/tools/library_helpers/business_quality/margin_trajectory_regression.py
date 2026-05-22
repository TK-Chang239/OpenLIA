"""margin_trajectory_regression — Linear regression on margin vs time; trend test.

Registered name: "margin_trajectory_regression"
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


def _linear_regression(x: list[float], y: list[float]) -> dict[str, float]:
    """Ordinary least-squares linear regression: y = slope * x + intercept."""
    n = len(x)
    if n < 2:
        raise ValueError("Need at least 2 data points for regression")

    x_mean = sum(x) / n
    y_mean = sum(y) / n

    ss_xy = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    ss_xx = sum((x[i] - x_mean) ** 2 for i in range(n))

    if ss_xx == 0:
        return {"slope": 0.0, "intercept": y_mean, "r_squared": 0.0}

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    # R-squared
    y_pred = [slope * x[i] + intercept for i in range(n)]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot != 0 else 0.0

    return {
        "slope": round(slope, 6),
        "intercept": round(intercept, 6),
        "r_squared": round(r_squared, 4),
    }


def _classify_trend(slope: float, threshold_bps_per_year: float = 20.0) -> str:
    """Classify trend direction based on slope (in pct units per period)."""
    slope_bps = slope * 100.0 * 100.0  # convert decimal pct to basis points
    if slope_bps > threshold_bps_per_year:
        return "expanding"
    elif slope_bps < -threshold_bps_per_year:
        return "contracting"
    else:
        return "stable"


def execute(
    gross_margins: list[float] | None = None,
    operating_margins: list[float] | None = None,
    net_margins: list[float] | None = None,
    period_labels: list[str] | None = None,
    trend_threshold_bps: float = 20.0,
) -> dict[str, Any]:
    """Run linear regression on margin series vs time.

    Margin inputs are decimal (e.g. 0.30 for 30%). Provide at least one margin series.

    Args:
        gross_margins: Gross margin per period (decimal, oldest first).
        operating_margins: Operating margin per period (decimal, oldest first).
        net_margins: Net margin per period (decimal, oldest first).
        period_labels: Optional period labels.
        trend_threshold_bps: Slope threshold in bps/year for expanding/contracting (default 20).

    Returns:
        Dict with regression results per margin type and trend classification.
    """
    series_map: dict[str, list[float] | None] = {
        "gross_margin": gross_margins,
        "operating_margin": operating_margins,
        "net_margin": net_margins,
    }

    # Find the first non-None series to determine n
    n = 0
    for vals in series_map.values():
        if vals is not None:
            n = len(vals)
            break

    if n < 2:
        raise ValueError("At least one margin series with >= 2 data points is required")

    x = list(range(n))  # 0, 1, 2, ... as time index
    labels = period_labels if period_labels is not None else [f"Period {i + 1}" for i in range(n)]

    results: dict[str, Any] = {}
    for margin_name, vals in series_map.items():
        if vals is None:
            results[margin_name] = None
            continue
        if len(vals) != n:
            raise ValueError(f"{margin_name} length must match other series lengths")

        reg = _linear_regression(x, vals)
        slope_bps_per_year = reg["slope"] * 10000.0  # decimal pct/year -> bps/year
        trend = _classify_trend(reg["slope"], trend_threshold_bps / 10000.0)

        results[margin_name] = {
            "values": [round(v, 4) for v in vals],
            "labels": labels,
            "slope_decimal_per_period": reg["slope"],
            "slope_bps_per_period": round(slope_bps_per_year, 1),
            "intercept": reg["intercept"],
            "r_squared": reg["r_squared"],
            "trend": trend,
        }

    return results


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="margin_trajectory_regression",
        category=Category.BUSINESS_QUALITY,
        one_liner="OLS regression on gross/operating/net margin vs time; trend classification.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fit a linear trend to gross, operating, and net margin time series. "
            "Produces slope (bps/year), R-squared, and expanding/stable/contracting verdict."
        ),
        when_to_use=[
            "Assessing structural margin expansion or compression over multiple years.",
            "Quantifying rate of margin change for quality-of-business analysis.",
        ],
        when_not_to_use=[
            "Single-period margin comparison — use common_size_statements.",
            "Peer margin comparison — use comparables.run.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "gross_margins": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Gross margin per period as decimal (e.g. 0.60).",
            ),
            "operating_margins": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Operating margin per period as decimal.",
            ),
            "net_margins": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Net margin per period as decimal.",
            ),
            "period_labels": HelperParam(
                type="list[str] | None",
                required=False,
                default=None,
                description="Optional period labels.",
            ),
            "trend_threshold_bps": HelperParam(
                type="float",
                required=False,
                default=20.0,
                description="Slope threshold in bps/year for expanding/contracting classification.",
            ),
        },
        outputs=[
            HelperOutput(
                name="margin_trajectory",
                type="dict",
                description=(
                    "Per-margin regression: slope (bps/year), R2, "
                    "trend (expanding/stable/contracting)."
                ),
            ),
        ],
        produces_artifacts=["margin_trajectory_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
