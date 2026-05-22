"""commodity_exposure_tracker — commodity-price correlation, regression, and sensitivity.

Registered name: "commodity_exposure_tracker"

Per design §5.3:
  - Pearson and Spearman correlation between company metric and commodity series
  - Lagged correlation for lags 0-4 quarters; argmax lag
  - OLS regression slope (subject_metric change per unit commodity price change)
  - Sensitivity coefficient: EBITDA impact per unit commodity move
  - Plain-English interpretation
  - Category.RISK_MACRO

Note: §5.3 "commodity_exposure_tracker" was claimed as "existing — schema migration only"
in PR 0.2 but no v1 file existed. Built fresh in PR 2.11.
"""

from __future__ import annotations

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

# Minimum series length for correlation/regression.
_MIN_PAIRS = 4


# ---------------------------------------------------------------------------
# Statistics helpers (stdlib-only, no numpy/scipy dependency)
# ---------------------------------------------------------------------------


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _pearson(x: list[float], y: list[float]) -> float | None:
    """Pearson r between two equal-length sequences."""
    n = len(x)
    if n < 2:
        return None
    mx, my = _mean(x), _mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y, strict=True))
    dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if dx < 1e-12 or dy < 1e-12:
        return None
    return round(num / (dx * dy), 6)


def _rank(xs: list[float]) -> list[float]:
    """Return rank series (1-based, average rank for ties)."""
    sorted_pairs = sorted(enumerate(xs), key=lambda p: p[1])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(sorted_pairs):
        j = i
        while j < len(sorted_pairs) - 1 and sorted_pairs[j + 1][1] == sorted_pairs[j][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[sorted_pairs[k][0]] = avg_rank
        i = j + 1
    return ranks


def _spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman rank correlation."""
    if len(x) < 2:
        return None
    rx = _rank(x)
    ry = _rank(y)
    return _pearson(rx, ry)


def _ols_slope_intercept(x: list[float], y: list[float]) -> tuple[float, float] | None:
    """OLS regression of y on x. Returns (slope, intercept) or None."""
    n = len(x)
    if n < 2:
        return None
    mx = _mean(x)
    my = _mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y, strict=True))
    denom = sum((xi - mx) ** 2 for xi in x)
    if abs(denom) < 1e-12:
        return None
    slope = num / denom
    intercept = my - slope * mx
    return round(slope, 6), round(intercept, 6)


def _lagged_pairs(
    x: list[float],
    y: list[float],
    lag: int,
) -> tuple[list[float], list[float]]:
    """Shift x backward by `lag` positions to align with y.

    lag=0: contemporaneous. lag=1: x[t-1] paired with y[t].
    Returns (x_lagged, y_aligned) with shared length.
    """
    if lag == 0:
        return x, y
    if lag >= len(x):
        return [], []
    return x[:-lag], y[lag:]


def _lag_correlation_table(
    commodity: list[float],
    metric: list[float],
    max_lag: int = 4,
) -> list[dict[str, Any]]:
    """Compute Pearson correlation for lags 0..max_lag quarters.

    At each lag, commodity[t-lag] is paired with metric[t].
    """
    results: list[dict[str, Any]] = []
    for lag in range(max_lag + 1):
        cx, my = _lagged_pairs(commodity, metric, lag)
        if len(cx) < _MIN_PAIRS:
            results.append({"lag_quarters": lag, "correlation": None, "n": len(cx)})
            continue
        r = _pearson(cx, my)
        results.append({"lag_quarters": lag, "correlation": r, "n": len(cx)})
    return results


def _argmax_lag(table: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the lag entry with highest absolute correlation."""
    valid = [row for row in table if row["correlation"] is not None]
    if not valid:
        return {"lag_quarters": 0, "correlation": None}
    return max(valid, key=lambda r: abs(r["correlation"]))  # type: ignore[arg-type]


def _build_interpretation(
    commodity_name: str,
    pearson: float | None,
    spearman: float | None,
    argmax: dict[str, Any],
    slope: float | None,
    unit: str,
) -> str:
    """Build a plain-English interpretation string."""
    if pearson is None:
        return f"Insufficient data to assess {commodity_name} exposure."

    abs_r = abs(pearson)
    direction = "positive" if pearson > 0 else "negative"

    if abs_r >= 0.7:
        strength = "Strong"
    elif abs_r >= 0.4:
        strength = "Moderate"
    elif abs_r >= 0.2:
        strength = "Weak"
    else:
        strength = "Negligible"

    lag_q = argmax.get("lag_quarters", 0)
    lag_r = argmax.get("correlation")

    lag_clause = ""
    if lag_q and lag_r is not None and abs(lag_r) > abs_r + 0.02:
        lag_clause = f" The relationship strengthens at a {lag_q}-quarter lag (r={lag_r:.2f})."

    slope_clause = ""
    if slope is not None:
        slope_clause = (
            f" Each 1-{unit} move in {commodity_name} corresponds to "
            f"~{slope:+.4f} change in the subject metric."
        )

    spearman_str = f"{spearman:.2f}" if spearman is not None else "N/A"
    return (
        f"{strength} {direction} correlation with {commodity_name} "
        f"(Pearson r={pearson:.2f}, Spearman r={spearman_str})."
        f"{lag_clause}{slope_clause}"
    )


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------


def execute(
    subject_metric_series: list[float],
    commodity_series: list[float],
    commodity_name: str,
    commodity_unit: str = "unit",
    max_lag_quarters: int = 4,
) -> dict[str, Any]:
    """Compute commodity exposure metrics for a company.

    Args:
        subject_metric_series: Company revenue or EBITDA per quarter, oldest first.
            Must align 1:1 with commodity_series. Min 4 values.
        commodity_series: Commodity price per quarter (or month averaged), oldest first.
        commodity_name: Human-readable name, e.g. "WTI Oil", "Henry Hub Gas", "Copper LME".
        commodity_unit: Unit of the commodity price for interpretation text,
            e.g. "bbl", "MMBtu", "tonne". Default "unit".
        max_lag_quarters: Maximum lag to test in lagged correlation analysis (default 4).

    Returns:
        Dict with:
            commodity, n_periods,
            correlation_pearson, correlation_spearman,
            lag_correlation_table (list of {lag_quarters, correlation, n}),
            lag_correlation_max ({lag_quarters, correlation}),
            regression_slope, regression_intercept,
            interpretation (str),
            status ("OK" or "DEGRADED"), missing_inputs.

    Raises:
        ValueError: If series are empty or mismatched in length.
    """
    if not subject_metric_series:
        raise ValueError("subject_metric_series is empty")
    if not commodity_series:
        raise ValueError("commodity_series is empty")
    if len(subject_metric_series) != len(commodity_series):
        raise ValueError(
            f"subject_metric_series length {len(subject_metric_series)} != "
            f"commodity_series length {len(commodity_series)}"
        )

    n = len(subject_metric_series)
    missing: list[str] = []

    if n < _MIN_PAIRS:
        missing.append(f"series_too_short_min_{_MIN_PAIRS}")
        return {
            "commodity": commodity_name,
            "n_periods": n,
            "correlation_pearson": None,
            "correlation_spearman": None,
            "lag_correlation_table": [],
            "lag_correlation_max": {"lag_quarters": 0, "correlation": None},
            "regression_slope": None,
            "regression_intercept": None,
            "interpretation": (
                f"Insufficient data to assess {commodity_name} exposure "
                f"(need {_MIN_PAIRS}+ periods)."
            ),
            "status": "DEGRADED",
            "missing_inputs": missing,
        }

    pearson = _pearson(commodity_series, subject_metric_series)
    spearman = _spearman(commodity_series, subject_metric_series)

    lag_table = _lag_correlation_table(commodity_series, subject_metric_series, max_lag_quarters)
    argmax = _argmax_lag(lag_table)

    ols = _ols_slope_intercept(commodity_series, subject_metric_series)
    slope: float | None = None
    intercept: float | None = None
    if ols is not None:
        slope, intercept = ols

    interpretation = _build_interpretation(
        commodity_name, pearson, spearman, argmax, slope, commodity_unit
    )

    return {
        "commodity": commodity_name,
        "n_periods": n,
        "correlation_pearson": pearson,
        "correlation_spearman": spearman,
        "lag_correlation_table": lag_table,
        "lag_correlation_max": argmax,
        "regression_slope": slope,
        "regression_intercept": intercept,
        "interpretation": interpretation,
        "status": "OK",
        "missing_inputs": [],
    }


# ---------------------------------------------------------------------------
# Schema registration
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="commodity_exposure_tracker",
        category=Category.RISK_MACRO,
        one_liner=(
            "Commodity-price exposure: Pearson/Spearman correlation, "
            "lagged correlation, OLS regression slope, and interpretation."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Quantify a company's revenue or EBITDA sensitivity to commodity price movements. "
            "Computes Pearson and Spearman correlation, lagged correlation (lags 0-4 quarters), "
            "OLS regression slope, and a plain-English interpretation. "
            "Designed for energy, materials, agricultural, and industrial companies."
        ),
        when_to_use=[
            "Commodity-linked revenue analysis for energy, mining, agriculture, or chemicals.",
            "Identifying revenue lag structure relative to spot commodity prices.",
            "Hedging effectiveness framing: baseline exposure before hedges applied.",
        ],
        when_not_to_use=[
            "Pure technology or services companies with no commodity input exposure.",
            "When fewer than 4 quarterly data points are available.",
            "Macro commodity price forecasting — this is a historical exposure metric only.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "subject_metric_series": HelperParam(
                type="list[float]",
                required=True,
                description=(
                    "Company revenue or EBITDA per quarter, oldest first. "
                    "Must align 1:1 with commodity_series. Min 4 values."
                ),
            ),
            "commodity_series": HelperParam(
                type="list[float]",
                required=True,
                description=(
                    "Commodity price per quarter (or monthly average), oldest first. "
                    "Must align 1:1 with subject_metric_series."
                ),
            ),
            "commodity_name": HelperParam(
                type="str",
                required=True,
                description=(
                    "Human-readable commodity name, e.g. 'WTI Oil', "
                    "'Henry Hub Gas', 'Copper LME', 'Wheat CBOT'."
                ),
            ),
            "commodity_unit": HelperParam(
                type="str",
                required=False,
                default="unit",
                description=(
                    "Unit label for interpretation text. "
                    "E.g. 'bbl', 'MMBtu', 'tonne', 'bushel'. Default 'unit'."
                ),
            ),
            "max_lag_quarters": HelperParam(
                type="int",
                required=False,
                default=4,
                description=(
                    "Maximum number of quarters to test in lagged correlation. "
                    "Default 4. Higher values require more data."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="commodity_exposure_output",
                type="commodity_exposure_output",
                description=(
                    "commodity name, n_periods, Pearson/Spearman correlation, "
                    "lag_correlation_table, lag_correlation_max (argmax lag), "
                    "regression_slope/intercept, interpretation string."
                ),
            ),
        ],
        produces_artifacts=["commodity_exposure_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
