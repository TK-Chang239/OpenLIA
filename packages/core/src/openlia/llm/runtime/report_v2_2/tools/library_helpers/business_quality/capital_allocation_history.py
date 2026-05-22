"""capital_allocation_history — Capex, buybacks, dividends, M&A, debt paydown as % of CFO.

Registered name: "capital_allocation_history"
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
    cfo_series: list[float],
    capex_series: list[float],
    buybacks_series: list[float],
    dividends_series: list[float],
    ma_series: list[float] | None = None,
    debt_paydown_series: list[float] | None = None,
    period_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Compute capital allocation history: each use as % of CFO over time.

    Args:
        cfo_series: Operating cash flow per period (oldest first).
        capex_series: Capital expenditure per period (positive = outflow).
        buybacks_series: Share repurchases per period (positive = outflow).
        dividends_series: Dividends paid per period (positive = outflow).
        ma_series: M&A spend per period. Defaults to 0 if None.
        debt_paydown_series: Net debt repayment per period. Defaults to 0 if None.
        period_labels: Optional period labels.

    Returns:
        Dict with per-period allocation as % of CFO, totals, and averages.
    """
    n = len(cfo_series)
    if n < 1:
        raise ValueError("cfo_series must have at least one period")
    for series_name, series in [
        ("capex_series", capex_series),
        ("buybacks_series", buybacks_series),
        ("dividends_series", dividends_series),
    ]:
        if len(series) != n:
            raise ValueError(f"{series_name} length must match cfo_series length")

    ma = ma_series if ma_series is not None else [0.0] * n
    debt_pd = debt_paydown_series if debt_paydown_series is not None else [0.0] * n

    if len(ma) != n or len(debt_pd) != n:
        raise ValueError(
            "ma_series and debt_paydown_series must match cfo_series length if provided"
        )

    labels = period_labels if period_labels is not None else [f"Period {i + 1}" for i in range(n)]

    def _pct(val: float, base: float) -> float | None:
        return round(val / base * 100.0, 1) if base != 0 else None

    periods: list[dict[str, Any]] = []
    for i in range(n):
        cfo = cfo_series[i]
        total_uses = capex_series[i] + buybacks_series[i] + dividends_series[i] + ma[i] + debt_pd[i]
        periods.append(
            {
                "label": labels[i],
                "cfo": cfo,
                "capex": capex_series[i],
                "buybacks": buybacks_series[i],
                "dividends": dividends_series[i],
                "ma": ma[i],
                "debt_paydown": debt_pd[i],
                "total_uses": round(total_uses, 2),
                "capex_pct_cfo": _pct(capex_series[i], cfo),
                "buybacks_pct_cfo": _pct(buybacks_series[i], cfo),
                "dividends_pct_cfo": _pct(dividends_series[i], cfo),
                "ma_pct_cfo": _pct(ma[i], cfo),
                "debt_paydown_pct_cfo": _pct(debt_pd[i], cfo),
                "total_uses_pct_cfo": _pct(total_uses, cfo),
            }
        )

    def _avg_pct(key: str) -> float | None:
        vals = [p[key] for p in periods if p[key] is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    return {
        "periods": periods,
        "avg_capex_pct_cfo": _avg_pct("capex_pct_cfo"),
        "avg_buybacks_pct_cfo": _avg_pct("buybacks_pct_cfo"),
        "avg_dividends_pct_cfo": _avg_pct("dividends_pct_cfo"),
        "avg_ma_pct_cfo": _avg_pct("ma_pct_cfo"),
        "avg_debt_paydown_pct_cfo": _avg_pct("debt_paydown_pct_cfo"),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="capital_allocation_history",
        category=Category.BUSINESS_QUALITY,
        one_liner="Capex, buybacks, dividends, M&A, debt paydown as % of CFO over time.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Analyze how management has deployed operating cash flow across capex, "
            "buybacks, dividends, M&A, and debt repayment over multiple periods."
        ),
        when_to_use=[
            "Evaluating management capital allocation discipline in equity research.",
            "Comparing reinvestment (capex) vs. return to shareholders over time.",
        ],
        when_not_to_use=[
            "Total shareholder yield calculation — use total_shareholder_yield.",
            "Forward capital allocation modeling — use forecast_builder.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "cfo_series": HelperParam(
                type="list[float]",
                required=True,
                description="Operating cash flow per period (oldest first).",
            ),
            "capex_series": HelperParam(
                type="list[float]",
                required=True,
                description="Capital expenditure per period (positive = outflow).",
            ),
            "buybacks_series": HelperParam(
                type="list[float]",
                required=True,
                description="Share repurchases per period (positive = outflow).",
            ),
            "dividends_series": HelperParam(
                type="list[float]",
                required=True,
                description="Dividends paid per period (positive = outflow).",
            ),
            "ma_series": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="M&A spend per period. Defaults to 0.",
            ),
            "debt_paydown_series": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Net debt repayment per period. Defaults to 0.",
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
                name="capital_allocation_history",
                type="dict",
                description=(
                    "periods list with absolute and pct-of-CFO values; "
                    "avg pct per category across periods."
                ),
            ),
        ],
        produces_artifacts=["capital_allocation_history_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
