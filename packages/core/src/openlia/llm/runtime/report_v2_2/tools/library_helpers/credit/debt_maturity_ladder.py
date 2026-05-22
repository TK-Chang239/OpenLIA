"""debt_maturity_ladder — annual debt maturity profile with refinancing risk scoring.

Registered name: "debt_maturity_ladder"

Per supplement §12:
  - Annual debt maturity profile (year, principal_due, avg_coupon, instruments)
  - Weighted average maturity (WAM) and weighted average coupon (WAC)
  - Refinancing wall detection: >25% of total debt in a single year
  - Refinancing risk score
  - Optional refi stress test vs EBIT
"""

from __future__ import annotations

from datetime import date
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

_REFI_WALL_THRESHOLD_PCT = 0.25  # 25% of total debt


def _years_to_maturity(maturity_str: str, as_of: date) -> float:
    """Compute fractional years between as_of and maturity date string (YYYY-MM-DD)."""
    mat = date.fromisoformat(maturity_str[:10])
    delta_days = (mat - as_of).days
    return delta_days / 365.25


def _bucket_year(year_val: int, as_of_year: int) -> str:
    """Map a year to its ladder bucket label."""
    offset = year_val - as_of_year
    if offset <= 5:
        return str(year_val)
    if offset <= 10:
        return "6-10"
    return "11+"


def execute(
    debt_instruments: list[dict[str, Any]],
    as_of_date: str,
    refi_rate_shock: float = 0.02,
    current_pretax_cost_of_debt: float | None = None,
    current_ebit: float | None = None,
) -> dict[str, Any]:
    """Build a debt maturity ladder from a list of debt instruments.

    Args:
        debt_instruments: List of dicts, each with:
            - name (str): Human-readable description.
            - principal (float): Face value / principal amount.
            - coupon (float): Annual coupon rate (0.05 = 5%).
            - maturity (str): ISO date string "YYYY-MM-DD".
            - kind (str, optional): "bond" | "loan" | "lease". Defaults to "bond".
            - currency (str, optional): Reporting currency. Defaults to "USD".
        as_of_date: ISO date string for the analysis date.
        refi_rate_shock: Interest rate shock for stress test (0.02 = +200 bps).
        current_pretax_cost_of_debt: Current pre-tax cost of debt for stress test.
        current_ebit: Current EBIT for stress test as % of EBIT calculation.

    Returns:
        Dict with ladder, weighted_avg_coupon, weighted_avg_maturity_years,
        refi_wall, refi_stress_test, refinancing_risk_score, warnings.

    Raises:
        ValueError: If debt_instruments is empty or as_of_date is invalid.
    """
    if not debt_instruments:
        raise ValueError("debt_instruments must be non-empty")

    as_of = date.fromisoformat(as_of_date[:10])
    as_of_year = as_of.year

    # --- Aggregate by bucket ---
    # Keys: year string (e.g., "2026", "6-10", "11+")
    buckets: dict[str, dict[str, Any]] = {}

    total_debt = 0.0
    wam_numerator = 0.0  # sum(principal * years_to_maturity)
    wac_numerator = 0.0  # sum(principal * coupon)
    wac_denominator = 0.0

    for inst in debt_instruments:
        name = inst.get("name", "unnamed")
        principal = float(inst["principal"])
        coupon = float(inst.get("coupon", 0.0))
        maturity_str = inst["maturity"]

        ytm = _years_to_maturity(maturity_str, as_of)
        mat_year = date.fromisoformat(maturity_str[:10]).year
        bucket_key = _bucket_year(mat_year, as_of_year)

        if bucket_key not in buckets:
            buckets[bucket_key] = {
                "year": bucket_key,
                "principal_due": 0.0,
                "coupon_numerator": 0.0,
                "instruments": [],
            }

        buckets[bucket_key]["principal_due"] += principal
        buckets[bucket_key]["coupon_numerator"] += principal * coupon
        buckets[bucket_key]["instruments"].append(name)

        total_debt += principal
        if ytm > 0:
            wam_numerator += principal * ytm
        wac_numerator += principal * coupon
        wac_denominator += principal

    if total_debt == 0:
        raise ValueError("Total principal across debt_instruments is zero")

    # Build sorted ladder rows
    def _sort_key(k: str) -> tuple[int, int]:
        if k.isdigit():
            return (0, int(k))
        if k == "6-10":
            return (1, 0)
        return (2, 0)

    ladder: list[dict[str, Any]] = []
    for key in sorted(buckets.keys(), key=_sort_key):
        b = buckets[key]
        pd = b["principal_due"]
        cn = b["coupon_numerator"]
        avg_coupon = round(cn / pd, 6) if pd > 0 else None
        ladder.append(
            {
                "year": key,
                "principal_due": round(pd, 2),
                "avg_coupon": avg_coupon,
                "instruments": sorted(b["instruments"]),
            }
        )

    # --- WAM and WAC ---
    wam = round(wam_numerator / total_debt, 4) if total_debt > 0 else None
    wac = round(wac_numerator / wac_denominator, 6) if wac_denominator > 0 else None

    # --- Refinancing wall detection ---
    refi_wall: dict[str, Any] = {
        "detected": False,
        "year": None,
        "principal_at_wall": None,
        "pct_of_total_debt": None,
    }
    for row in ladder:
        if not isinstance(row["year"], str) or row["year"].isdigit():
            pct = row["principal_due"] / total_debt
            if pct >= _REFI_WALL_THRESHOLD_PCT:
                refi_wall = {
                    "detected": True,
                    "year": row["year"],
                    "principal_at_wall": row["principal_due"],
                    "pct_of_total_debt": round(pct, 4),
                    "threshold_pct": _REFI_WALL_THRESHOLD_PCT,
                }
                break  # flag first wall only

    # --- Refinancing risk score (0-100; higher = more risk) ---
    # Heuristic: based on wall concentration + WAM (shorter WAM = higher risk)
    wall_pct = refi_wall.get("pct_of_total_debt") or 0.0
    wam_score = max(0.0, 1.0 - (wam or 5.0) / 10.0) * 40  # short WAM = high risk
    wall_score = min(wall_pct * 200, 60)  # cap at 60
    refinancing_risk_score = round(min(100, wam_score + wall_score), 1)

    # --- Stress test ---
    refi_stress: dict[str, Any] = {}
    if refi_wall["detected"] and refi_wall["principal_at_wall"] is not None:
        shock_bps = round(refi_rate_shock * 10000)
        incremental_interest = round(refi_wall["principal_at_wall"] * refi_rate_shock, 2)
        refi_stress = {
            "shock_bps": shock_bps,
            "incremental_annual_interest": incremental_interest,
        }
        if current_pretax_cost_of_debt is not None:
            refi_stress["implied_new_cost_of_debt"] = round(
                current_pretax_cost_of_debt + refi_rate_shock, 6
            )
        if current_ebit is not None and current_ebit != 0:
            refi_stress["incremental_interest_pct_of_ebit"] = round(
                incremental_interest / abs(current_ebit), 6
            )

    # --- Warnings ---
    warnings: list[str] = []
    if refi_wall["detected"]:
        pct_str = f"{refi_wall['pct_of_total_debt'] * 100:.1f}%"
        amt_str = f"{refi_wall['principal_at_wall']:,.0f}"
        warnings.append(
            f"Refinancing wall in {refi_wall['year']}: {pct_str} of total debt ({amt_str})."
        )
    if wam is not None and wam < 2.0:
        warnings.append(f"Short WAM {wam:.1f} years - near-term refinancing pressure.")

    # --- Narrative ---
    if refi_wall["detected"]:
        wall_txt = (
            f"Refi wall in {refi_wall['year']} "
            f"({refi_wall['pct_of_total_debt'] * 100:.0f}% of total debt). "
        )
    else:
        wall_txt = "No single-year refinancing wall detected. "
    wam_str = f"WAM {wam:.1f} years" if wam is not None else "WAM N/A"
    wac_str = f"WAC {wac * 100:.2f}%" if wac is not None else "WAC N/A"
    narrative = (
        f"Debt ladder: total debt {total_debt:,.0f}; {wam_str}; {wac_str}. "
        f"{wall_txt}"
        f"Refinancing risk score {refinancing_risk_score}/100."
    )

    return {
        "as_of": as_of_date,
        "ladder": ladder,
        "total_debt": round(total_debt, 2),
        "weighted_avg_coupon": wac,
        "weighted_avg_maturity_years": wam,
        "refi_wall": refi_wall,
        "refi_stress_test": refi_stress,
        "refinancing_risk_score": refinancing_risk_score,
        "warnings": warnings,
        "narrative": narrative,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="debt_maturity_ladder",
        category=Category.FORENSIC,
        one_liner="Debt maturity schedule, WAM, WAC, refinancing wall detection, and stress test.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Build a year-by-year debt maturity ladder from individual instruments. "
            "Computes weighted average maturity (WAM), weighted average coupon (WAC), "
            "detects refinancing walls (>25% of total debt in a single year), scores "
            "refinancing risk 0-100, and stress-tests the incremental interest cost "
            "of rolling maturities at an elevated rate."
        ),
        when_to_use=[
            "Credit deep dives for any leveraged company with disclosed debt schedules.",
            "Post-refinancing update reports to show how the maturity profile shifted.",
            "Sector reports for cyclicals entering a downturn with near-term maturities.",
        ],
        when_not_to_use=[
            "Companies with no disclosed maturity schedule; use pdf_ingest on 10-K debt note.",
            "Floating-rate revolvers only (WAM misleading; duration governed by credit agreement).",
            "Purely equity-financed companies with immaterial debt.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "debt_instruments": HelperParam(
                type="list[dict]",
                required=True,
                description=(
                    "List of debt instruments. Each dict: "
                    "name (str), principal (float), coupon (float), "
                    "maturity (ISO date str), kind (bond/loan/lease, optional), "
                    "currency (optional)."
                ),
            ),
            "as_of_date": HelperParam(
                type="str",
                required=True,
                description="Analysis date as ISO string (YYYY-MM-DD).",
            ),
            "refi_rate_shock": HelperParam(
                type="float",
                required=False,
                default=0.02,
                description="Interest rate shock for stress test. 0.02 = +200 bps.",
            ),
            "current_pretax_cost_of_debt": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Current pre-tax cost of debt; enables implied new cost in stress.",
            ),
            "current_ebit": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Current EBIT; enables incremental interest as % of EBIT in stress.",
            ),
        },
        outputs=[
            HelperOutput(
                name="debt_maturity_ladder_output",
                type="debt_maturity_ladder_output",
                description=(
                    "ladder list (year, principal_due, avg_coupon, instruments), "
                    "total_debt, weighted_avg_coupon, weighted_avg_maturity_years, "
                    "refi_wall (detected, year, pct_of_total_debt), "
                    "refi_stress_test, refinancing_risk_score (0-100), warnings, narrative."
                ),
            ),
        ],
        produces_artifacts=["debt_maturity_ladder_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
