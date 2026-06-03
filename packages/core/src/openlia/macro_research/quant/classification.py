"""Debt Cycle deterministic classification. Pure function; no I/O, no LLM.

Ported from the old dashboards/debt_cycle.py T3_compute. Thresholds are
Dalio defaults. Inputs are already-fetched scalars (the engine gathers
them via tools/web_search), so the stubbed T2 formulas are gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Tone = Literal["red", "amber", "green"]

_DEBT_GDP_WARN = 100.0
_DEBT_GDP_CRITICAL = 120.0
_INTEREST_REVENUE_WARN = 15.0
_INTEREST_REVENUE_CRITICAL = 20.0
_TIPS_YIELD_WARN = 0.5
_DXY_WARN = 100.0


@dataclass(frozen=True)
class DebtCycleInputs:
    debt_gdp: float
    interest_revenue: float
    tips_real_yield: float
    dxy: float


@dataclass(frozen=True)
class DebtCycleClassification:
    phase: str
    severity: Tone
    indicator_statuses: dict[str, Tone]
    red_count: int
    amber_count: int
    monetary_space: dict[str, object] = field(default_factory=dict)


def _bucket(value: float, warn: float, crit: float) -> Tone:
    if value >= crit:
        return "red"
    if value >= warn:
        return "amber"
    return "green"


def classify_debt_cycle(inputs: DebtCycleInputs) -> DebtCycleClassification:
    statuses: dict[str, Tone] = {
        "debt_gdp": _bucket(inputs.debt_gdp, _DEBT_GDP_WARN, _DEBT_GDP_CRITICAL),
        "interest_revenue": _bucket(
            inputs.interest_revenue, _INTEREST_REVENUE_WARN, _INTEREST_REVENUE_CRITICAL
        ),
        "tips_yield": "amber" if inputs.tips_real_yield < _TIPS_YIELD_WARN else "green",
        "dxy": "amber" if inputs.dxy < _DXY_WARN else "green",
    }
    red = sum(1 for s in statuses.values() if s == "red")
    amber = sum(1 for s in statuses.values() if s == "amber")

    if red >= 2:
        phase, severity = "Deleveraging", "red"
    elif red == 1 and amber >= 1:
        phase, severity = "Late Plateau", "red"
    elif amber >= 2:
        phase, severity = "Plateau", "amber"
    else:
        phase, severity = "Expansion", "green"

    return DebtCycleClassification(
        phase=phase,
        severity=severity,
        indicator_statuses=statuses,
        red_count=red,
        amber_count=amber,
        monetary_space={
            "rate_cut_headroom": max(0.0, 5.0 - inputs.tips_real_yield),
            "qe_credibility": "amber" if inputs.interest_revenue >= 12 else "green",
            "currency_debasement_risk": (
                "red" if inputs.dxy < 98 else "amber" if inputs.dxy < 102 else "green"
            ),
        },
    )
