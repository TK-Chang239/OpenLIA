"""earnings_surprise_tracker — Beats/misses vs consensus, magnitude, trend.

Registered name: "earnings_surprise_tracker"
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
    actuals: list[float],
    estimates: list[float],
    period_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Compute earnings surprise tracker.

    Args:
        actuals: Actual EPS per quarter (oldest first).
        estimates: Consensus EPS estimate per quarter (oldest first).
        period_labels: Optional period labels.

    Returns:
        Dict with per-quarter beat/miss, magnitude, beat rate, and trend.
    """
    n = len(actuals)
    if n < 1:
        raise ValueError("actuals must have at least one period")
    if len(estimates) != n:
        raise ValueError("actuals and estimates must have equal length")

    labels = period_labels if period_labels is not None else [f"Q{i + 1}" for i in range(n)]

    quarters: list[dict[str, Any]] = []
    beat_count = 0
    for i in range(n):
        actual = actuals[i]
        estimate = estimates[i]
        surprise = actual - estimate
        if estimate != 0:
            surprise_pct = (surprise / abs(estimate)) * 100.0
        else:
            surprise_pct = None
        beat = actual >= estimate
        if beat:
            beat_count += 1
        quarters.append(
            {
                "label": labels[i],
                "actual": actual,
                "estimate": estimate,
                "surprise": round(surprise, 4),
                "surprise_pct": round(surprise_pct, 2) if surprise_pct is not None else None,
                "beat": beat,
            }
        )

    beat_rate = beat_count / n * 100.0

    surprise_pcts = [q["surprise_pct"] for q in quarters if q["surprise_pct"] is not None]
    avg_surprise_pct = sum(surprise_pcts) / len(surprise_pcts) if surprise_pcts else None

    # Simple trend: compare avg of latter half vs former half
    if n >= 4:
        mid = n // 2
        recent = [q["surprise"] for q in quarters[mid:]]
        earlier = [q["surprise"] for q in quarters[:mid]]
        avg_recent = sum(recent) / len(recent)
        avg_earlier = sum(earlier) / len(earlier)
        if avg_recent > avg_earlier + 0.001:
            trend = "improving"
        elif avg_recent < avg_earlier - 0.001:
            trend = "deteriorating"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    return {
        "quarters": quarters,
        "beat_count": beat_count,
        "miss_count": n - beat_count,
        "beat_rate_pct": round(beat_rate, 1),
        "avg_surprise_pct": round(avg_surprise_pct, 2) if avg_surprise_pct is not None else None,
        "trend": trend,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="earnings_surprise_tracker",
        category=Category.BUSINESS_QUALITY,
        one_liner="EPS beats/misses vs consensus, surprise magnitude, and trend direction.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Track earnings beats and misses relative to consensus estimates, compute "
            "beat rate, average surprise magnitude, and trend over trailing quarters."
        ),
        when_to_use=[
            "Assessing management guidance credibility in equity research.",
            "Identifying systematic estimate revision patterns.",
        ],
        when_not_to_use=[
            "Analyst revision count/direction — use analyst_revision_momentum.",
            "Forward earnings forecasting — use forecast_builder.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "actuals": HelperParam(
                type="list[float]",
                required=True,
                description="Actual EPS per quarter (oldest first).",
            ),
            "estimates": HelperParam(
                type="list[float]",
                required=True,
                description="Consensus EPS estimate per quarter (oldest first).",
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
                name="earnings_surprise_tracker",
                type="dict",
                description=(
                    "quarters list (label, actual, estimate, surprise, surprise_pct, beat), "
                    "beat_count, miss_count, beat_rate_pct, avg_surprise_pct, trend."
                ),
            ),
        ],
        produces_artifacts=["earnings_surprise_tracker_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
