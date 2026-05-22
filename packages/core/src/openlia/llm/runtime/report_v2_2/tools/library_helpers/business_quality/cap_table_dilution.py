"""cap_table_dilution — Share count evolution, gross/net dilution, buyback offset.

Registered name: "cap_table_dilution"
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
    shares_series: list[float],
    sbc_shares_issued_series: list[float] | None = None,
    buyback_shares_series: list[float] | None = None,
    period_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Compute cap table dilution analysis over time.

    Args:
        shares_series: Total shares outstanding per period (oldest first).
        sbc_shares_issued_series: Shares issued for SBC per period (gross dilution).
        buyback_shares_series: Shares retired via buybacks per period.
        period_labels: Optional period labels.

    Returns:
        Dict with per-period dilution metrics, averages, and net dilution trend.
    """
    n = len(shares_series)
    if n < 2:
        raise ValueError("shares_series must have at least 2 periods")

    sbc_shares = sbc_shares_issued_series if sbc_shares_issued_series is not None else [0.0] * n
    buyback_shares = buyback_shares_series if buyback_shares_series is not None else [0.0] * n

    if len(sbc_shares) != n or len(buyback_shares) != n:
        raise ValueError("All series must have equal length")

    labels = period_labels if period_labels is not None else [f"Period {i + 1}" for i in range(n)]

    periods: list[dict[str, Any]] = []
    for i in range(n):
        shares = shares_series[i]
        prior_shares = shares_series[i - 1] if i > 0 else None

        net_change = (shares - prior_shares) if prior_shares is not None else None
        net_dilution_bps: float | None = None
        if prior_shares is not None and prior_shares > 0 and net_change is not None:
            net_dilution_bps = round(net_change / prior_shares * 10000.0, 1)

        gross_dilution_bps: float | None = None
        if prior_shares is not None and prior_shares > 0:
            gross_dilution_bps = round(sbc_shares[i] / prior_shares * 10000.0, 1)

        buyback_offset_bps: float | None = None
        if prior_shares is not None and prior_shares > 0:
            buyback_offset_bps = round(buyback_shares[i] / prior_shares * 10000.0, 1)

        periods.append(
            {
                "label": labels[i],
                "shares_outstanding": shares,
                "sbc_shares_issued": sbc_shares[i],
                "buyback_shares_retired": buyback_shares[i],
                "net_dilution_bps": net_dilution_bps,
                "gross_dilution_bps": gross_dilution_bps,
                "buyback_offset_bps": buyback_offset_bps,
            }
        )

    # Averages (skip first period since no prior)
    net_dilutions = [
        p["net_dilution_bps"] for p in periods[1:] if p["net_dilution_bps"] is not None
    ]
    avg_net_dilution_bps = sum(net_dilutions) / len(net_dilutions) if net_dilutions else None

    # Trend
    total_change = shares_series[-1] - shares_series[0]
    trend = "dilutive" if total_change > 0 else ("accretive" if total_change < 0 else "flat")

    return {
        "periods": periods,
        "avg_net_dilution_bps_per_period": round(avg_net_dilution_bps, 1)
        if avg_net_dilution_bps is not None
        else None,
        "trend": trend,
        "total_share_change": round(total_change, 0),
        "total_share_change_pct": round(total_change / shares_series[0] * 100.0, 2)
        if shares_series[0] != 0
        else None,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="cap_table_dilution",
        category=Category.BUSINESS_QUALITY,
        one_liner="Share count evolution, gross SBC dilution, buyback offset, net dilution bps.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Track share count evolution over time, decomposing into gross SBC dilution "
            "and buyback offset to compute net dilution in basis points per period."
        ),
        when_to_use=[
            "Evaluating long-run dilution burden relative to buyback program.",
            "When SBC intensity requires context of buyback offset.",
        ],
        when_not_to_use=[
            "Single-period SBC intensity metrics — use sbc_intensity.",
            "Per-share EPS computation — use ft_per_share_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "shares_series": HelperParam(
                type="list[float]",
                required=True,
                description="Shares outstanding per period (oldest first, min 2 periods).",
            ),
            "sbc_shares_issued_series": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Shares issued for SBC per period (gross dilution).",
            ),
            "buyback_shares_series": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Shares retired via buybacks per period.",
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
                name="cap_table_dilution",
                type="dict",
                description=(
                    "periods (net/gross dilution bps, buyback offset bps), "
                    "avg_net_dilution_bps_per_period, trend, total_share_change."
                ),
            ),
        ],
        produces_artifacts=["cap_table_dilution_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
