"""reverse_dcf — solve for the market-implied growth rate or WACC.

Registered name: "reverse_dcf"

Given the current market price, solves for:
  - mode "solve_growth": implied long-term growth rate (fixed WACC)
  - mode "solve_wacc": implied WACC (fixed terminal growth)

Uses Newton-Raphson iteration with a bisection fallback.

Design ref: planning/2026-05-21-equity-research-helpers-design.md §3.5
"""

from __future__ import annotations

import datetime
import math
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

_MAX_ITER = 100
_TOLERANCE = 1e-8
_BISECTION_FALLBACK = True

_GROWTH_LOWER = -0.20  # floor: -20%
_GROWTH_UPPER = 0.40  # ceil: +40%
_WACC_LOWER = 0.01  # floor: 1%
_WACC_UPPER = 0.60  # ceil: 60%


# ---------------------------------------------------------------------------
# DCF equity value as a function of one free parameter
# ---------------------------------------------------------------------------


def _dcf_equity_value(
    fcff_schedule: list[float],
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares: float,
    non_operating_assets: float = 0.0,
    mid_year: bool = True,
) -> float:
    """Compute equity value per share given fcff_schedule, wacc, terminal_growth."""
    if terminal_growth >= wacc:
        return float("inf")  # diverges

    n = len(fcff_schedule)
    pv_fcff = sum(
        fcff / (1.0 + wacc) ** ((t + 1 - 0.5) if mid_year else (t + 1))
        for t, fcff in enumerate(fcff_schedule)
    )
    fcff_n = fcff_schedule[-1] if fcff_schedule else 0.0
    tv = fcff_n * (1.0 + terminal_growth) / (wacc - terminal_growth)
    pv_tv = tv / (1.0 + wacc) ** n
    ev = pv_fcff + pv_tv
    equity = ev - net_debt + non_operating_assets
    return (equity / shares) if shares > 0 else equity


def _bisection(
    fn: Any,  # Callable[[float], float]
    lo: float,
    hi: float,
    tolerance: float,
    max_iter: int,
) -> tuple[float, int, bool]:
    """Bisection solver. Returns (root, iters, converged)."""
    f_lo = fn(lo)
    f_hi = fn(hi)
    if f_lo * f_hi > 0:
        # Same sign — no root bracketed; return midpoint
        return (lo + hi) / 2.0, 0, False
    converged = False
    mid = (lo + hi) / 2.0
    for _it in range(max_iter):
        mid = (lo + hi) / 2.0
        f_mid = fn(mid)
        if abs(f_mid) < tolerance or (hi - lo) / 2.0 < tolerance:
            converged = True
            break
        if f_lo * f_mid <= 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return mid, max_iter, converged


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    current_price: float,
    fcff_schedule: list[float],
    net_debt: float,
    shares_outstanding: float,
    mode: str = "solve_growth",
    fixed_wacc: float | None = None,
    fixed_terminal_growth: float | None = None,
    non_operating_assets: float = 0.0,
    mid_year_convention: bool = True,
    growth_search_lo: float = _GROWTH_LOWER,
    growth_search_hi: float = _GROWTH_UPPER,
    wacc_search_lo: float = _WACC_LOWER,
    wacc_search_hi: float = _WACC_UPPER,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Solve for the market-implied growth rate or WACC.

    Args:
        current_price: Current market price per share.
        fcff_schedule: Explicit-period FCFF projections (list of floats).
        net_debt: Total debt minus cash.
        shares_outstanding: Diluted shares.
        mode: "solve_growth" (fixed WACC, solve for g) | "solve_wacc" (fixed g, solve for WACC).
        fixed_wacc: Required for mode="solve_growth".
        fixed_terminal_growth: Required for mode="solve_wacc".
        non_operating_assets: Excess cash / investments.
        mid_year_convention: Mid-year discounting flag.
        growth_search_lo: Lower bound for growth search.
        growth_search_hi: Upper bound for growth search.
        wacc_search_lo: Lower bound for WACC search.
        wacc_search_hi: Upper bound for WACC search.
    """
    if mode not in ("solve_growth", "solve_wacc"):
        raise ValueError(f"mode must be solve_growth|solve_wacc, got {mode!r}")
    if not fcff_schedule:
        raise ValueError("fcff_schedule must be non-empty")
    if current_price <= 0:
        raise ValueError(f"current_price must be > 0, got {current_price}")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be > 0")

    warnings: list[str] = []

    if mode == "solve_growth":
        if fixed_wacc is None:
            raise ValueError("fixed_wacc is required for mode='solve_growth'")

        def objective(g: float) -> float:
            return (
                _dcf_equity_value(
                    fcff_schedule,
                    fixed_wacc,
                    g,
                    net_debt,
                    shares_outstanding,
                    non_operating_assets,
                    mid_year_convention,
                )
                - current_price
            )

        implied_val, iters, converged = _bisection(
            objective,
            growth_search_lo,
            growth_search_hi,
            _TOLERANCE,
            _MAX_ITER,
        )

        if not converged:
            warnings.append(
                f"Bisection did not fully converge in {_MAX_ITER} iterations; "
                f"result {implied_val:.6f} is approximate."
            )
        if implied_val >= fixed_wacc:
            warnings.append(
                f"Implied growth rate {implied_val:.4f} >= WACC {fixed_wacc:.4f}. "
                "The market may be pricing in an unsustainable perpetuity growth rate."
            )
        if implied_val > 0.15:
            warnings.append(
                f"Implied growth rate {implied_val:.4f} > 15%. "
                "This is well above nominal GDP growth; "
                "market may be pricing speculative optionality."
            )

        solved_for = "implied_growth_rate"
        solved_value = implied_val
        fixed_param = "wacc"
        fixed_param_value = fixed_wacc

    else:  # solve_wacc
        if fixed_terminal_growth is None:
            raise ValueError("fixed_terminal_growth is required for mode='solve_wacc'")

        def objective(wacc: float) -> float:  # type: ignore[misc]
            return (
                _dcf_equity_value(
                    fcff_schedule,
                    wacc,
                    fixed_terminal_growth,
                    net_debt,
                    shares_outstanding,
                    non_operating_assets,
                    mid_year_convention,
                )
                - current_price
            )

        implied_val, iters, converged = _bisection(
            objective,
            max(wacc_search_lo, fixed_terminal_growth + 0.001),  # WACC must > g
            wacc_search_hi,
            _TOLERANCE,
            _MAX_ITER,
        )

        if not converged:
            warnings.append(
                f"Bisection did not fully converge in {_MAX_ITER} iterations; "
                f"result {implied_val:.6f} is approximate."
            )

        solved_for = "implied_wacc"
        solved_value = implied_val
        fixed_param = "terminal_growth"
        fixed_param_value = fixed_terminal_growth

    # Verify solution
    if mode == "solve_growth":
        check_price = _dcf_equity_value(
            fcff_schedule,
            fixed_wacc,  # type: ignore[arg-type]
            implied_val,
            net_debt,
            shares_outstanding,
            non_operating_assets,
            mid_year_convention,
        )
    else:
        check_price = _dcf_equity_value(
            fcff_schedule,
            implied_val,
            fixed_terminal_growth,  # type: ignore[arg-type]
            net_debt,
            shares_outstanding,
            non_operating_assets,
            mid_year_convention,
        )

    residual = abs(check_price - current_price)
    if residual > 0.01 and not math.isinf(check_price):
        warnings.append(
            f"Residual check: implied price ${check_price:.2f} vs target ${current_price:.2f} "
            f"(gap ${residual:.4f}). Solution may not have converged."
        )

    # Interpretation
    interpretation = (
        f"At the current price ${current_price:.2f}, the market implies "
        f"{solved_for.replace('_', ' ')} = {solved_value * 100:.2f}% "
        f"(holding {fixed_param.replace('_', ' ')} = {fixed_param_value * 100:.2f}% fixed)."
    )

    return {
        "mode": mode,
        "current_price": current_price,
        solved_for: solved_value,
        f"fixed_{fixed_param}": fixed_param_value,
        "convergence": {
            "converged": converged,
            "iterations": iters,
            "residual": residual,
            "check_price": check_price,
        },
        "interpretation": interpretation,
        "warnings": warnings,
        "data_as_of": data_as_of or datetime.date.today().isoformat(),
        "source_provenance": source_provenance or [],
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="reverse_dcf",
        category=Category.DCF,
        one_liner=(
            "Solve for market-implied growth rate or WACC given current price and FCF schedule."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Answer 'what growth rate does the current share price imply?' "
            "by inverting the DCF. Useful for testing whether the current valuation "
            "is realistic and for framing the bull/bear debate."
        ),
        when_to_use=[
            "Valuation section of an initiation or update report: 'market prices in Y% growth.'",
            "Stress-testing an implied WACC when terminal growth is debated.",
            "Pairing with scenario_weighting to bracket a distribution of outcomes.",
        ],
        when_not_to_use=[
            "Forward DCF valuation — use dcf_engine instead.",
            "Comparables-based valuation — use comparables.run.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "current_price": HelperParam(
                type="float",
                description="Current market price per share.",
                required=True,
            ),
            "fcff_schedule": HelperParam(
                type="list[float]",
                description="Explicit-period FCFF projections (same list as used in dcf_engine).",
                required=True,
            ),
            "net_debt": HelperParam(
                type="float",
                description="Net debt = total_debt - cash.",
                required=True,
            ),
            "shares_outstanding": HelperParam(
                type="float",
                description="Diluted shares outstanding.",
                required=True,
            ),
            "mode": HelperParam(
                type="str",
                default="solve_growth",
                description="solve_growth (fixed WACC) | solve_wacc (fixed terminal growth).",
                required=False,
            ),
            "fixed_wacc": HelperParam(
                type="float",
                default=None,
                description="Required for mode=solve_growth.",
                required=False,
            ),
            "fixed_terminal_growth": HelperParam(
                type="float",
                default=None,
                description="Required for mode=solve_wacc.",
                required=False,
            ),
            "non_operating_assets": HelperParam(
                type="float",
                default=0.0,
                description="Excess cash / investments to add to equity value.",
                required=False,
            ),
            "mid_year_convention": HelperParam(
                type="bool",
                default=True,
                description="Mid-year discounting (institutional default).",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="reverse_dcf_output",
                type="reverse_dcf_output",
                description=(
                    "Implied growth rate or WACC, convergence diagnostics, interpretation."
                ),
            ),
        ],
        produces_artifacts=["reverse_dcf_output"],
        consumes_artifacts=["cost_of_capital_output"],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
