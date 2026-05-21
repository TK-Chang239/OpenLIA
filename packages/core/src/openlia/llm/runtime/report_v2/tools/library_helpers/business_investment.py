"""
Vendored from alirezarezvani/claude-skills (MIT License).
Original: finance/business-investment-advisor/skills/business-investment-advisor/SKILL.md
Vendored on 2026-05-21 for OpenLIA report_v2 library helpers.

Adapted to expose a HelperSchema via SCHEMA module-level constant and an
execute(**params) entry point.

Ports the prose math from the SKILL.md into Python: ROI, payback period,
NPV, IRR (binary-search approximation), investment scoring, and scenario
comparison for business capital allocation decisions.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperParam,
    HelperSchema,
    register_library_helper,
)


def calculate_roi(
    net_gain: float,
    cost: float,
) -> float:
    """ROI = (Net Gain / Cost) * 100."""
    if cost == 0:
        return 0.0
    return (net_gain / cost) * 100


def calculate_payback_period(
    total_investment: float,
    annual_net_cash_flow: float,
) -> float:
    """Payback = Total Investment / Annual Net Cash Flow (returns years)."""
    if annual_net_cash_flow <= 0:
        return float("inf")
    return total_investment / annual_net_cash_flow


def calculate_npv(
    initial_investment: float,
    cash_flows: list[float],
    discount_rate: float,
) -> float:
    """NPV = Sum[CF_t / (1+r)^t] - Initial Investment."""
    pv = sum(cf / ((1 + discount_rate) ** (t + 1)) for t, cf in enumerate(cash_flows))
    return pv - initial_investment


def _npv_at_rate(
    initial_investment: float,
    cash_flows: list[float],
    rate: float,
) -> float:
    pv = sum(cf / ((1 + rate) ** (t + 1)) for t, cf in enumerate(cash_flows))
    return pv - initial_investment


def calculate_irr(
    initial_investment: float,
    cash_flows: list[float],
    tolerance: float = 1e-6,
    max_iterations: int = 1000,
) -> float:
    """Approximate IRR via binary search. Returns the rate at which NPV=0."""
    lo, hi = -0.999, 10.0
    for _ in range(max_iterations):
        mid = (lo + hi) / 2
        npv = _npv_at_rate(initial_investment, cash_flows, mid)
        if abs(npv) < tolerance:
            return mid
        if npv > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def score_investment(
    roi_pct: float,
    payback_years: float,
    strategic_fit: int,
    risk_level: int,
    reversibility: int,
    cash_flow_impact: int,
) -> dict[str, Any]:
    """Score investment 1-5 on 6 dimensions; total 6-30.

    ROI score:      <10%->1, <25%->2, <35%->3, <50%->4, >=50%->5
    Payback score:  >5yr->1, >3yr->2, >2yr->3, >1yr->4, <=1yr->5
    strategic_fit, risk_level, reversibility, cash_flow_impact: pass in 1-5 directly.
    """
    roi_score = (
        1
        if roi_pct < 10
        else 2
        if roi_pct < 25
        else 3
        if roi_pct < 35
        else 4
        if roi_pct < 50
        else 5
    )
    payback_score = (
        1
        if payback_years > 5
        else 2
        if payback_years > 3
        else 3
        if payback_years > 2
        else 4
        if payback_years > 1
        else 5
    )
    total = (
        roi_score + payback_score + strategic_fit + risk_level + reversibility + cash_flow_impact
    )
    if total <= 12:
        verdict = "Do not proceed"
    elif total <= 20:
        verdict = "Needs more analysis"
    else:
        verdict = "Strong investment"

    return {
        "roi_score": roi_score,
        "payback_score": payback_score,
        "strategic_fit": strategic_fit,
        "risk_level": risk_level,
        "reversibility": reversibility,
        "cash_flow_impact": cash_flow_impact,
        "total": total,
        "verdict": verdict,
    }


def run_scenarios(
    initial_investment: float,
    base_annual_cash_flow: float,
    useful_life_years: int,
    discount_rate: float,
) -> dict[str, Any]:
    """Run base, upside (+20%), and downside (-40%) scenarios."""
    scenarios: dict[str, Any] = {}
    for label, multiplier in (("base", 1.0), ("upside", 1.20), ("downside", 0.60)):
        annual_cf = base_annual_cash_flow * multiplier
        cash_flows = [annual_cf] * useful_life_years
        total_returns = annual_cf * useful_life_years
        net_gain = total_returns - initial_investment
        roi = calculate_roi(net_gain, initial_investment)
        payback = calculate_payback_period(initial_investment, annual_cf)
        npv = calculate_npv(initial_investment, cash_flows, discount_rate)
        irr = calculate_irr(initial_investment, cash_flows)
        scenarios[label] = {
            "annual_cash_flow": round(annual_cf, 2),
            "total_returns": round(total_returns, 2),
            "net_gain": round(net_gain, 2),
            "roi_pct": round(roi, 2),
            "payback_years": round(payback, 2),
            "npv": round(npv, 2),
            "irr_pct": round(irr * 100, 2),
        }
    return scenarios


def execute(**params: Any) -> dict[str, Any]:
    """Evaluate a business investment decision.

    Params:
        total_investment: total upfront cost (required)
        annual_net_cash_flow: expected annual net cash inflow (required)
        useful_life_years: expected useful life in years (required)
        discount_rate: cost of capital as decimal (default 0.10)
        strategic_fit: 1-5 strategic fit score
        risk_level: 1-5 risk level score (5=low risk)
        reversibility: 1-5 reversibility score (5=easy to exit)
        cash_flow_impact: 1-5 cash flow impact score (5=self-funding quickly)
    """
    total_investment = params["total_investment"]
    annual_net_cash_flow = params["annual_net_cash_flow"]
    useful_life_years = int(params["useful_life_years"])
    discount_rate = params.get("discount_rate", 0.10)
    strategic_fit = int(params.get("strategic_fit", 3))
    risk_level = int(params.get("risk_level", 3))
    reversibility = int(params.get("reversibility", 3))
    cash_flow_impact = int(params.get("cash_flow_impact", 3))

    cash_flows = [annual_net_cash_flow] * useful_life_years
    total_returns = annual_net_cash_flow * useful_life_years
    net_gain = total_returns - total_investment
    roi = calculate_roi(net_gain, total_investment)
    payback = calculate_payback_period(total_investment, annual_net_cash_flow)
    npv = calculate_npv(total_investment, cash_flows, discount_rate)
    irr = calculate_irr(total_investment, cash_flows)
    scoring = score_investment(
        roi, payback, strategic_fit, risk_level, reversibility, cash_flow_impact
    )
    scenarios = run_scenarios(
        total_investment, annual_net_cash_flow, useful_life_years, discount_rate
    )

    flags: list[str] = []
    if payback >= useful_life_years:
        flags.append("Payback period exceeds useful life — investment never pays back.")
    if npv < 0:
        flags.append("NPV is negative — investment destroys value at this discount rate.")
    if irr * 100 < discount_rate * 100:
        flags.append("IRR is below hurdle rate.")

    return {
        "summary": {
            "total_investment": total_investment,
            "annual_net_cash_flow": annual_net_cash_flow,
            "useful_life_years": useful_life_years,
            "roi_pct": round(roi, 2),
            "payback_years": round(payback, 2),
            "npv": round(npv, 2),
            "irr_pct": round(irr * 100, 2),
            "discount_rate_pct": round(discount_rate * 100, 2),
        },
        "scoring": scoring,
        "scenarios": scenarios,
        "flags": flags,
    }


SCHEMA = HelperSchema(
    name="business_investment",
    description=(
        "Business investment analysis: ROI, payback period, NPV, IRR, investment scoring "
        "rubric, and base/upside/downside scenario comparison. "
        "For capital expenditure decisions — equipment, hiring, technology, real estate."
    ),
    params={
        "total_investment": HelperParam(
            type="float",
            description="Total upfront investment cost.",
            required=True,
        ),
        "annual_net_cash_flow": HelperParam(
            type="float",
            description=(
                "Expected annual net cash inflow "
                "(revenue increase or cost savings minus ongoing costs)."
            ),
            required=True,
        ),
        "useful_life_years": HelperParam(
            type="int",
            description="Expected useful life of the investment in years.",
            required=True,
        ),
        "discount_rate": HelperParam(
            type="float",
            default=0.10,
            description="Cost of capital as a decimal (default 0.10 = 10%).",
            required=False,
        ),
        "strategic_fit": HelperParam(
            type="int",
            default=3,
            description="Strategic fit score 1-5 (5=core to mission).",
            required=False,
        ),
        "risk_level": HelperParam(
            type="int",
            default=3,
            description="Risk level score 1-5 (5=low/proven risk).",
            required=False,
        ),
        "reversibility": HelperParam(
            type="int",
            default=3,
            description="Reversibility score 1-5 (5=easy to exit).",
            required=False,
        ),
        "cash_flow_impact": HelperParam(
            type="int",
            default=3,
            description="Cash flow impact score 1-5 (5=self-funding quickly).",
            required=False,
        ),
    },
)

register_library_helper("business_investment", execute, SCHEMA)
