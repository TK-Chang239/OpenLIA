"""yield_curve_shape — UST yield-curve shape signals and regime classification.

Registered name: "yield_curve_shape"

Per design §5.2:
  - 10Y-2Y spread (bps) — most-cited recession indicator
  - 10Y-3M spread (bps) — NY Fed recession signal
  - 5Y-2Y spread, 30Y-10Y spread
  - Inversion flag: 10Y-2Y < 0
  - Days since last inversion (from historical series if provided)
  - OLS slope: linear regression of yields vs maturity in years
  - Curvature score: (yield_2y + yield_30y)/2 - yield_10y
  - Regime classification: steep / modestly upward / flat / inverted
  - Category.RISK_MACRO
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

# Maturity mapping: field name -> years
_MATURITY_YEARS: dict[str, float] = {
    "1m": 1 / 12,
    "3m": 3 / 12,
    "6m": 6 / 12,
    "1y": 1.0,
    "2y": 2.0,
    "3y": 3.0,
    "5y": 5.0,
    "7y": 7.0,
    "10y": 10.0,
    "20y": 20.0,
    "30y": 30.0,
}

# Classification thresholds in bps
_STEEP_THRESHOLD_BPS = 100
_MODESTLY_UPWARD_THRESHOLD_BPS = 30
# _FLAT: 0 <= spread < 30 bps
# _INVERTED: spread < 0


def _bps(rate_long: float | None, rate_short: float | None) -> int | None:
    """Convert yield spread to basis points (integer). Returns None if either is None."""
    if rate_long is None or rate_short is None:
        return None
    return round((rate_long - rate_short) * 100)


def _classify_regime(spread_10y_2y_bps: int | None) -> str:
    """Classify yield curve regime from 10Y-2Y spread."""
    if spread_10y_2y_bps is None:
        return "unknown"
    if spread_10y_2y_bps >= _STEEP_THRESHOLD_BPS:
        return "steep"
    if spread_10y_2y_bps >= _MODESTLY_UPWARD_THRESHOLD_BPS:
        return "modestly_upward"
    if spread_10y_2y_bps >= 0:
        return "flat"
    return "inverted"


def _ols_slope(
    yields: dict[str, float | None],
) -> float | None:
    """OLS slope (yield vs maturity years) — a positive slope = normal/steep curve.

    Returns slope in bps per year.
    """
    points: list[tuple[float, float]] = []
    for tenor, maturity in _MATURITY_YEARS.items():
        y = yields.get(tenor)
        if y is not None:
            points.append((maturity, y * 100))  # convert to bps

    n = len(points)
    if n < 2:
        return None

    x_mean = sum(p[0] for p in points) / n
    y_mean = sum(p[1] for p in points) / n
    num = sum((p[0] - x_mean) * (p[1] - y_mean) for p in points)
    denom = sum((p[0] - x_mean) ** 2 for p in points)
    if abs(denom) < 1e-12:
        return None
    return round(num / denom, 4)


def _curvature(
    yield_2y: float | None,
    yield_10y: float | None,
    yield_30y: float | None,
) -> float | None:
    """Curvature = (yield_2y + yield_30y) / 2 - yield_10y, in bps.

    Positive = humped (belly cheap), Negative = inverted belly.
    """
    if yield_2y is None or yield_10y is None or yield_30y is None:
        return None
    return round(((yield_2y + yield_30y) / 2.0 - yield_10y) * 100, 2)


def _days_since_inversion(
    historical_snapshots: list[dict[str, Any]],
    as_of_str: str,
) -> int | None:
    """Count calendar days since the last date where 10Y-2Y spread was negative.

    historical_snapshots: list of {date: str, 2y: float|None, 10y: float|None, ...}.
    Returns None if no historical data or no prior inversion found.
    """
    if not historical_snapshots:
        return None

    last_inversion: date | None = None
    for snap in historical_snapshots:
        snap_date_str = snap.get("date")
        y2 = snap.get("2y")
        y10 = snap.get("10y")
        if snap_date_str is None or y2 is None or y10 is None:
            continue
        if (y10 - y2) < 0:
            try:
                snap_date = date.fromisoformat(snap_date_str)
            except ValueError:
                continue
            if last_inversion is None or snap_date > last_inversion:
                last_inversion = snap_date

    if last_inversion is None:
        return None

    try:
        as_of = date.fromisoformat(as_of_str)
    except ValueError:
        return None

    diff = (as_of - last_inversion).days
    return diff if diff >= 0 else None


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------


def execute(
    yields: dict[str, float | None],
    as_of: str | None = None,
    historical_snapshots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute yield-curve shape signals from a single UST yield snapshot.

    Args:
        yields: Dict mapping tenor names to yield values (as percentages, e.g. 4.5 for 4.5%).
            Expected keys (all optional): "1m", "3m", "6m", "1y", "2y", "3y", "5y",
            "7y", "10y", "20y", "30y".
            Minimum useful set: "2y" and "10y" for the headline spread.
        as_of: ISO-8601 date for this snapshot (used for days-since-inversion calc).
        historical_snapshots: List of prior yield dicts, each with a "date" key.
            If provided, used to compute days_since_last_inversion.

    Returns:
        Dict with key spreads in bps, inversion flag, days since last inversion,
        OLS slope (bps/yr), curvature score, classification, missing_inputs.

    Raises:
        ValueError: If yields is empty.
    """
    if not yields:
        raise ValueError("yields dict is empty")

    y = yields  # shorthand

    y2 = y.get("2y")
    y3m = y.get("3m")
    y5 = y.get("5y")
    y10 = y.get("10y")
    y30 = y.get("30y")

    missing: list[str] = []
    if y10 is None:
        missing.append("10y")
    if y2 is None:
        missing.append("2y")

    spread_10y_2y = _bps(y10, y2)
    spread_10y_3m = _bps(y10, y3m)
    spread_5y_2y = _bps(y5, y2)
    spread_30y_10y = _bps(y30, y10)

    inverted = spread_10y_2y is not None and spread_10y_2y < 0
    regime = _classify_regime(spread_10y_2y)
    slope = _ols_slope(yields)
    curvature_score = _curvature(y2, y10, y30)

    as_of_str = as_of or ""
    days_inv: int | None = None
    if historical_snapshots and as_of_str:
        days_inv = _days_since_inversion(historical_snapshots, as_of_str)

    # Human-readable classification string
    _regime_label: dict[str, str] = {
        "steep": "upward sloping, steep",
        "modestly_upward": "upward sloping, modestly steep",
        "flat": "flat",
        "inverted": "inverted",
        "unknown": "unknown",
    }
    classification = _regime_label.get(regime, regime)

    return {
        "as_of": as_of_str or None,
        "10y_2y_spread_bps": spread_10y_2y,
        "10y_3m_spread_bps": spread_10y_3m,
        "5y_2y_spread_bps": spread_5y_2y,
        "30y_10y_spread_bps": spread_30y_10y,
        "inverted": inverted,
        "days_since_last_inversion": days_inv,
        "curve_slope_bps_per_year": slope,
        "curvature_score": curvature_score,
        "regime": regime,
        "classification": classification,
        "status": "DEGRADED" if missing else "OK",
        "missing_inputs": missing,
    }


# ---------------------------------------------------------------------------
# Schema registration
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="yield_curve_shape",
        category=Category.RISK_MACRO,
        one_liner=(
            "UST yield-curve shape: 10Y-2Y / 10Y-3M spreads, inversion flag, "
            "OLS slope, curvature, and regime classification."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Derive the key yield-curve shape signals from a UST rate snapshot: "
            "10Y-2Y spread (most-cited recession indicator), 10Y-3M spread (NY Fed model), "
            "5Y-2Y and 30Y-10Y spreads, OLS slope across the curve, curvature score, "
            "and a regime label (steep/modestly upward/flat/inverted). "
            "Optionally computes days since last inversion from a historical series."
        ),
        when_to_use=[
            "Macro context section of any equity research report.",
            "Rate-sensitive sector analysis (financials, utilities, REITs).",
            "Regime characterisation for asset-allocation framing.",
        ],
        when_not_to_use=[
            "Non-US issuers where UST curve is not the relevant benchmark.",
            "Individual bond valuation — use dcf_engine for discounted cash flows.",
            "Credit spread analysis — use fred_credit_spreads for IG/HY OAS data.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "yields": HelperParam(
                type="dict[str, float | None]",
                required=True,
                description=(
                    "Map of tenor -> yield (%). "
                    "Keys: '1m','3m','6m','1y','2y','3y','5y','7y','10y','20y','30y'. "
                    "At minimum supply '2y' and '10y' for the headline spread."
                ),
            ),
            "as_of": HelperParam(
                type="str | None",
                required=False,
                default=None,
                description="ISO-8601 date of the snapshot (used for days-since-inversion).",
            ),
            "historical_snapshots": HelperParam(
                type="list[dict] | None",
                required=False,
                default=None,
                description=(
                    "List of prior curve snapshots, each with at minimum "
                    "{'date': str, '2y': float|None, '10y': float|None}. "
                    "Used to compute days_since_last_inversion."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="yield_curve_shape_output",
                type="yield_curve_shape_output",
                description=(
                    "Key spreads in bps (10Y-2Y, 10Y-3M, 5Y-2Y, 30Y-10Y), "
                    "inversion flag, days since last inversion, OLS slope (bps/yr), "
                    "curvature score, regime, classification string."
                ),
            ),
        ],
        produces_artifacts=["yield_curve_shape_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
