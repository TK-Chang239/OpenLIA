"""
Vendored from alirezarezvani/claude-skills (MIT License).
Original: finance/skills/saas-metrics-coach/scripts/metrics_calculator.py
         finance/skills/saas-metrics-coach/scripts/quick_ratio_calculator.py
         finance/skills/saas-metrics-coach/scripts/unit_economics_simulator.py
Vendored on 2026-05-21 for OpenLIA report_v2 library helpers.

Adapted to expose a HelperSchema via SCHEMA module-level constant and an
execute(**params) entry point. All three SaaS scripts are consolidated here;
execute() dispatches based on the 'mode' parameter.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperParam,
    HelperSchema,
    register_library_helper,
)

# ---------------------------------------------------------------------------
# Core metrics calculator (from metrics_calculator.py)
# ---------------------------------------------------------------------------


def calculate_saas_metrics(
    mrr: float | None = None,
    mrr_last: float | None = None,
    customers: float | None = None,
    churned: float | None = None,
    new_customers: float | None = None,
    sm_spend: float | None = None,
    gross_margin: float = 0.70,
    expansion_mrr: float = 0,
    churned_mrr: float = 0,
    contraction_mrr: float = 0,
    profit_margin: float | None = None,
) -> dict[str, Any]:
    """Calculate SaaS unit economics metrics."""
    r: dict[str, Any] = {}
    missing: list[str] = []

    if mrr is not None:
        r["MRR"] = round(mrr, 2)
        r["ARR"] = round(mrr * 12, 2)
    else:
        missing.append("ARR/MRR - need current MRR")

    if mrr and customers:
        r["ARPA"] = round(mrr / customers, 2)
    else:
        missing.append("ARPA - need MRR + customer count")

    if mrr and mrr_last and mrr_last > 0:
        r["MoM_Growth_Pct"] = round(((mrr - mrr_last) / mrr_last) * 100, 2)
    else:
        missing.append("MoM Growth - need last month MRR")

    if churned is not None and customers:
        r["Churn_Pct"] = round((churned / customers) * 100, 2)
    else:
        missing.append("Churn Rate - need churned + total customers")

    if sm_spend and new_customers and new_customers > 0:
        r["CAC"] = round(sm_spend / new_customers, 2)
    else:
        missing.append("CAC - need S&M spend + new customers")

    arpa = r.get("ARPA")
    churn_dec = r.get("Churn_Pct", 0) / 100
    if arpa and churn_dec > 0:
        r["LTV"] = round((arpa / churn_dec) * gross_margin, 2)
    else:
        missing.append("LTV - need ARPA and churn rate")

    if r.get("LTV") and r.get("CAC") and r["CAC"] > 0:
        r["LTV_CAC"] = round(r["LTV"] / r["CAC"], 2)
    else:
        missing.append("LTV:CAC - need both LTV and CAC")

    if r.get("CAC") and arpa and arpa > 0:
        r["Payback_Months"] = round(r["CAC"] / (arpa * gross_margin), 1)
    else:
        missing.append("Payback Period - need CAC and ARPA")

    if mrr_last and mrr_last > 0 and (expansion_mrr or churned_mrr or contraction_mrr):
        nrr = ((mrr_last + expansion_mrr - churned_mrr - contraction_mrr) / mrr_last) * 100
        r["NRR_Pct"] = round(nrr, 2)
    elif r.get("Churn_Pct"):
        r["NRR_Est_Pct"] = round((1 - r["Churn_Pct"] / 100) * 100, 2)
        missing.append(
            "NRR (accurate) - using churn-only estimate; provide expansion MRR for full NRR"
        )

    if r.get("MoM_Growth_Pct") and profit_margin is not None:
        r["Rule_of_40"] = round(r["MoM_Growth_Pct"] * 12 + profit_margin, 1)

    r["_missing"] = missing
    r["_gross_margin"] = gross_margin
    return r


# ---------------------------------------------------------------------------
# Quick ratio calculator (from quick_ratio_calculator.py)
# ---------------------------------------------------------------------------


def calculate_quick_ratio(
    new_mrr: float,
    expansion_mrr: float,
    churned_mrr: float,
    contraction_mrr: float,
) -> dict[str, Any]:
    """Calculate SaaS Quick Ratio = (New MRR + Expansion MRR) / (Churned MRR + Contraction MRR)."""
    growth_mrr = new_mrr + expansion_mrr
    lost_mrr = churned_mrr + contraction_mrr

    if lost_mrr == 0:
        quick_ratio: float | None = None
        quick_ratio_display = "inf" if growth_mrr > 0 else "0"
        status = "EXCELLENT" if growth_mrr > 0 else "N/A"
        interpretation = (
            "No revenue loss - perfect retention with growth"
            if growth_mrr > 0
            else "No growth or loss"
        )
    else:
        qr = growth_mrr / lost_mrr
        quick_ratio = qr
        quick_ratio_display = f"{qr:.2f}"
        if qr >= 4:
            status = "EXCELLENT"
            interpretation = "Strong, efficient growth"
        elif qr >= 2:
            status = "HEALTHY"
            interpretation = "Good growth efficiency"
        elif qr >= 1:
            status = "WATCH"
            interpretation = "Marginal growth"
        else:
            status = "CRITICAL"
            interpretation = "Losing revenue faster than gaining"

    new_pct = (new_mrr / growth_mrr * 100) if growth_mrr > 0 else 0.0
    expansion_pct = (expansion_mrr / growth_mrr * 100) if growth_mrr > 0 else 0.0
    churned_pct = (churned_mrr / lost_mrr * 100) if lost_mrr > 0 else 0.0
    contraction_pct = (contraction_mrr / lost_mrr * 100) if lost_mrr > 0 else 0.0

    return {
        "quick_ratio": quick_ratio,
        "quick_ratio_display": quick_ratio_display,
        "status": status,
        "interpretation": interpretation,
        "components": {
            "growth_mrr": round(growth_mrr, 2),
            "lost_mrr": round(lost_mrr, 2),
            "new_mrr": round(new_mrr, 2),
            "expansion_mrr": round(expansion_mrr, 2),
            "churned_mrr": round(churned_mrr, 2),
            "contraction_mrr": round(contraction_mrr, 2),
        },
        "breakdown": {
            "new_mrr_pct": round(new_pct, 1),
            "expansion_mrr_pct": round(expansion_pct, 1),
            "churned_mrr_pct": round(churned_pct, 1),
            "contraction_mrr_pct": round(contraction_pct, 1),
        },
    }


# ---------------------------------------------------------------------------
# Unit economics simulator (from unit_economics_simulator.py)
# ---------------------------------------------------------------------------


def simulate_unit_economics(
    mrr: float,
    monthly_growth_pct: float,
    monthly_churn_pct: float,
    cac: float,
    gross_margin: float = 0.70,
    sm_spend_pct: float = 0.30,
    months: int = 12,
) -> dict[str, Any]:
    """Simulate SaaS unit economics forward N months."""
    projections: list[dict[str, Any]] = []
    current_mrr = mrr
    cumulative_sm_spend = 0.0
    cumulative_gross_profit = 0.0

    for month in range(1, months + 1):
        growth_rate = monthly_growth_pct / 100
        churn_rate = monthly_churn_pct / 100
        net_growth_rate = growth_rate - churn_rate
        new_mrr = current_mrr * (1 + net_growth_rate)
        monthly_revenue = current_mrr
        gross_profit = monthly_revenue * gross_margin
        sm_spend = monthly_revenue * sm_spend_pct
        net_profit = gross_profit - sm_spend
        cumulative_sm_spend += sm_spend
        cumulative_gross_profit += gross_profit
        arr = current_mrr * 12
        projections.append(
            {
                "month": month,
                "mrr": round(current_mrr, 2),
                "arr": round(arr, 2),
                "monthly_revenue": round(monthly_revenue, 2),
                "gross_profit": round(gross_profit, 2),
                "sm_spend": round(sm_spend, 2),
                "net_profit": round(net_profit, 2),
                "growth_rate_pct": round(net_growth_rate * 100, 2),
            }
        )
        current_mrr = new_mrr

    final_mrr = projections[-1]["mrr"]
    final_arr = projections[-1]["arr"]
    total_revenue = sum(p["monthly_revenue"] for p in projections)
    total_net_profit = sum(p["net_profit"] for p in projections)

    return {
        "inputs": {
            "starting_mrr": mrr,
            "monthly_growth_pct": monthly_growth_pct,
            "monthly_churn_pct": monthly_churn_pct,
            "cac": cac,
            "gross_margin": gross_margin,
            "sm_spend_pct": sm_spend_pct,
        },
        "projections": projections,
        "summary": {
            "starting_mrr": mrr,
            "ending_mrr": round(final_mrr, 2),
            "ending_arr": round(final_arr, 2),
            "mrr_growth_pct": round(((final_mrr - mrr) / mrr) * 100, 2),
            "total_revenue_12m": round(total_revenue, 2),
            "total_gross_profit_12m": round(cumulative_gross_profit, 2),
            "total_sm_spend_12m": round(cumulative_sm_spend, 2),
            "total_net_profit_12m": round(total_net_profit, 2),
            "avg_monthly_growth_pct": round((monthly_growth_pct - monthly_churn_pct), 2),
        },
    }


# ---------------------------------------------------------------------------
# Unified execute entry point
# ---------------------------------------------------------------------------


def execute(**params: Any) -> dict[str, Any]:
    """Compute SaaS metrics, quick ratio, or unit economics simulation.

    Params:
        mode: 'metrics' | 'quick_ratio' | 'simulate' (default 'metrics')

        For mode='metrics':
            mrr, mrr_last, customers, churned, new_customers, sm_spend,
            gross_margin, expansion_mrr, churned_mrr, contraction_mrr, profit_margin

        For mode='quick_ratio':
            new_mrr, expansion_mrr, churned_mrr, contraction_mrr

        For mode='simulate':
            mrr, monthly_growth_pct, monthly_churn_pct, cac,
            gross_margin, sm_spend_pct, months
    """
    mode = params.get("mode", "metrics")

    if mode == "quick_ratio":
        return calculate_quick_ratio(
            new_mrr=params["new_mrr"],
            expansion_mrr=params.get("expansion_mrr", 0),
            churned_mrr=params["churned_mrr"],
            contraction_mrr=params.get("contraction_mrr", 0),
        )
    elif mode == "simulate":
        return simulate_unit_economics(
            mrr=params["mrr"],
            monthly_growth_pct=params["monthly_growth_pct"],
            monthly_churn_pct=params["monthly_churn_pct"],
            cac=params["cac"],
            gross_margin=params.get("gross_margin", 0.70),
            sm_spend_pct=params.get("sm_spend_pct", 0.30),
            months=params.get("months", 12),
        )
    else:
        return calculate_saas_metrics(
            mrr=params.get("mrr"),
            mrr_last=params.get("mrr_last"),
            customers=params.get("customers"),
            churned=params.get("churned"),
            new_customers=params.get("new_customers"),
            sm_spend=params.get("sm_spend"),
            gross_margin=params.get("gross_margin", 0.70),
            expansion_mrr=params.get("expansion_mrr", 0),
            churned_mrr=params.get("churned_mrr", 0),
            contraction_mrr=params.get("contraction_mrr", 0),
            profit_margin=params.get("profit_margin"),
        )


SCHEMA = HelperSchema(
    name="saas_metrics",
    description=(
        "SaaS metrics calculator: MRR/ARR, ARPA, churn, CAC, LTV, LTV:CAC, payback, NRR, "
        "Rule of 40, quick ratio, and 12-month unit economics simulation. "
        "Dispatch via mode='metrics' | 'quick_ratio' | 'simulate'."
    ),
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
)

register_library_helper("saas_metrics", execute, SCHEMA)
