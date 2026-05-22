"""sm_autocorrelation — ACF/PACF computation and Ljung-Box test via statsmodels.

Registered name: "sm_autocorrelation"

Computes the Autocorrelation Function (ACF), Partial Autocorrelation Function (PACF),
and the Ljung-Box portmanteau test for white noise. Returns an autocorrelation
classification based on the LB test result and the ACF decay pattern.

Not on the 18-complex list — no skill doc.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.stattools import acf, pacf


def _classify_autocorrelation(
    lb_p_value: float,
    acf_values: list[float],
    alpha: float,
    lags: int,
) -> str:
    """Classify autocorrelation pattern.

    Returns one of: none, mild, moderate, strong, decaying (AR-like), oscillating (MA-like).
    """
    if lb_p_value >= alpha:
        return "none"

    # Check decay pattern of significant ACF values
    significant = [
        abs(acf_values[i])
        for i in range(1, min(lags + 1, len(acf_values)))
        if abs(acf_values[i]) > 2 / (len(acf_values) ** 0.5)
    ]

    if not significant:
        return "mild"

    max_sig = max(significant)
    if max_sig > 0.5:
        return "strong"

    # Check oscillation (alternating sign)
    signs = [1 if v > 0 else -1 for v in acf_values[1 : min(6, len(acf_values))]]
    alternating = all(signs[i] != signs[i + 1] for i in range(len(signs) - 1))
    if alternating and len(signs) >= 3:
        return "oscillating"

    # Check geometric decay (AR-like)
    if len(significant) >= 3 and significant[0] > significant[-1]:
        return "decaying"

    return "moderate"


def execute(
    series: list[float],
    lags: int = 20,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Compute ACF, PACF, and Ljung-Box test.

    Args:
        series: Univariate time series. Should be stationary; difference if needed.
        lags: Number of lags to compute. Default 20. Must be < len(series)/2.
        alpha: Significance level for Ljung-Box test. Default 0.05.

    Returns:
        Dict with acf_values (list), pacf_values (list), ljung_box (stat, p_value,
        lags_tested), durbin_watson_stat, autocorrelation_classification.
    """
    n = len(series)
    if n < 10:
        raise ValueError("series must have at least 10 observations")

    # Cap lags to avoid statsmodels error
    max_lags = max(1, n // 2 - 1)
    effective_lags = min(lags, max_lags)

    arr = np.array(series, dtype=float)

    # ACF with confidence interval
    acf_vals, _confint = acf(arr, nlags=effective_lags, alpha=alpha, fft=True)

    # PACF
    try:
        pacf_vals = pacf(arr, nlags=effective_lags, method="ywm")
    except Exception:
        # Fallback for pathological series
        pacf_vals = np.zeros(effective_lags + 1)

    # Ljung-Box at lags [1..effective_lags], use the last row for overall test
    lb_result = acorr_ljungbox(arr, lags=list(range(1, effective_lags + 1)), return_df=True)
    lb_stat = float(lb_result["lb_stat"].iloc[-1])
    lb_pval = float(lb_result["lb_pvalue"].iloc[-1])

    # Durbin-Watson (lag-1 autocorrelation check for regression residuals)
    dw_stat = float(durbin_watson(arr))

    acf_list = [float(v) for v in acf_vals]
    pacf_list = [float(v) for v in pacf_vals]

    classification = _classify_autocorrelation(lb_pval, acf_list, alpha, effective_lags)

    return {
        "acf_values": acf_list,
        "pacf_values": pacf_list,
        "ljung_box": {
            "statistic": lb_stat,
            "p_value": lb_pval,
            "lags_tested": effective_lags,
            "verdict": "autocorrelated" if lb_pval < alpha else "white_noise",
        },
        "durbin_watson_stat": dw_stat,
        "autocorrelation_classification": classification,
        "lags": effective_lags,
        "alpha": float(alpha),
    }


# ---------------------------------------------------------------------------
# Schema + registration
# ---------------------------------------------------------------------------

from openlia.llm.runtime.report_v2_2 import (  # noqa: E402
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper  # noqa: E402

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="sm_autocorrelation",
        category=Category.RISK_MACRO,
        one_liner="ACF/PACF computation and Ljung-Box white-noise test.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Characterize autocorrelation structure in a time series. ACF/PACF "
            "plots guide ARIMA order selection; Ljung-Box tests whether residuals "
            "from a model are white noise."
        ),
        when_to_use=[
            "Diagnosing OLS residuals for autocorrelation before HAC correction.",
            "Selecting ARIMA(p,d,q) order from ACF/PACF shape.",
            "Confirming GARCH model residuals are white noise.",
        ],
        when_not_to_use=[
            "Non-stationary series — difference first using sm_stationarity_test.",
            "Very short series (< 20 obs) — ACF/PACF confidence bands are unreliable.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "series": HelperParam(
                type="list[float]",
                required=True,
                description="Stationary univariate time series.",
            ),
            "lags": HelperParam(
                type="int",
                required=False,
                default=20,
                description="Number of lags. Default 20. Capped at len(series)//2 - 1.",
            ),
            "alpha": HelperParam(
                type="float",
                required=False,
                default=0.05,
                description="Significance level for Ljung-Box. Default 0.05.",
            ),
        },
        outputs=[
            HelperOutput(
                name="autocorrelation_output",
                type="dict",
                description=(
                    "acf_values, pacf_values, ljung_box (stat, p_value, lags_tested, verdict), "
                    "durbin_watson_stat, autocorrelation_classification."
                ),
            ),
        ],
        produces_artifacts=["autocorrelation_output"],
        consumes_artifacts=[],
    ),
    skill_doc=SkillDocRef(path="", estimated_tokens=0),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
