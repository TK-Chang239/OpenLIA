"""sm_stationarity_test — ADF + KPSS stationarity tests via statsmodels.

Registered name: "sm_stationarity_test"

Runs both Augmented Dickey-Fuller (ADF) and KPSS tests on a univariate series,
combines their verdicts, and returns a consensus stationarity classification.

ADF null: series has a unit root (non-stationary).
KPSS null: series is stationary (trend or level).

Not on the 18-complex list — no skill doc.
"""

from __future__ import annotations

from typing import Any

from statsmodels.tsa.stattools import adfuller, kpss


def _adf_verdict(p_value: float, alpha: float) -> str:
    """Reject H0 (unit root) → stationary."""
    return "stationary" if p_value < alpha else "non_stationary"


def _kpss_verdict(p_value: float, alpha: float) -> str:
    """Reject H0 (level-stationary) → non-stationary."""
    return "non_stationary" if p_value < alpha else "stationary"


def _consensus(adf: str, kpss_v: str) -> str:
    """Combine ADF and KPSS verdicts into a consensus classification.

    Both stationary       → stationary
    Both non-stationary   → non_stationary
    Conflicting verdicts  → inconclusive (common for trend-stationary series)
    """
    if adf == "stationary" and kpss_v == "stationary":
        return "stationary"
    if adf == "non_stationary" and kpss_v == "non_stationary":
        return "non_stationary"
    return "inconclusive"


def execute(
    series: list[float],
    alpha: float = 0.05,
    adf_regression: str = "c",
    kpss_regression: str = "c",
    adf_maxlag: int | None = None,
) -> dict[str, Any]:
    """Run ADF and KPSS stationarity tests.

    Args:
        series: Univariate time series (at least 20 observations recommended).
        alpha: Significance level for both tests. Default 0.05.
        adf_regression: ADF deterministic component: 'c' (const), 'ct' (const+trend),
            'ctt' (const+linear+quadratic trend), 'n' (no const). Default 'c'.
        kpss_regression: KPSS regression type: 'c' (level) or 'ct' (trend). Default 'c'.
        adf_maxlag: Max lag for ADF. None → automatic Schwert criterion.

    Returns:
        Dict with adf (stat, p_value, lags_used, critical_values, verdict),
        kpss (stat, p_value, lags_used, critical_values, verdict),
        consensus (stationarity classification string), alpha.
    """
    if len(series) < 10:
        raise ValueError("series must have at least 10 observations")

    # ADF
    adf_kwargs: dict[str, Any] = {"regression": adf_regression, "autolag": "AIC"}
    if adf_maxlag is not None:
        adf_kwargs["maxlag"] = adf_maxlag
    adf_stat, adf_pval, adf_usedlag, _adf_nobs, adf_crit, *_ = adfuller(series, **adf_kwargs)
    adf_v = _adf_verdict(float(adf_pval), alpha)

    # KPSS — suppress spurious convergence warnings
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kpss_stat, kpss_pval, kpss_usedlag, kpss_crit = kpss(
            series, regression=kpss_regression, nlags="auto"
        )
    kpss_v = _kpss_verdict(float(kpss_pval), kpss_pval)

    # Re-evaluate kpss verdict with correct alpha
    kpss_v = _kpss_verdict(float(kpss_pval), alpha)

    return {
        "adf": {
            "statistic": float(adf_stat),
            "p_value": float(adf_pval),
            "lags_used": int(adf_usedlag),
            "critical_values": {k: float(v) for k, v in adf_crit.items()},
            "verdict": adf_v,
        },
        "kpss": {
            "statistic": float(kpss_stat),
            "p_value": float(kpss_pval),
            "lags_used": int(kpss_usedlag),
            "critical_values": {k: float(v) for k, v in kpss_crit.items()},
            "verdict": kpss_v,
        },
        "consensus": _consensus(adf_v, kpss_v),
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
        name="sm_stationarity_test",
        category=Category.RISK_MACRO,
        one_liner="ADF + KPSS stationarity tests with consensus classification.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Determine whether a time series is stationary (constant mean/variance) "
            "before applying time-series models. Non-stationary inputs violate OLS "
            "assumptions and produce spurious regressions."
        ),
        when_to_use=[
            "Before OLS regression on time-series data.",
            "Checking whether macro series (e.g. GDP growth, margins) need differencing.",
            "Validating stationarity assumption for VAR or GARCH inputs.",
        ],
        when_not_to_use=[
            "Cross-sectional data (stationarity is a time-series concept).",
            "Series with fewer than 20 observations — power is very low.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "series": HelperParam(
                type="list[float]",
                required=True,
                description="Univariate time series, at least 10 observations.",
            ),
            "alpha": HelperParam(
                type="float",
                required=False,
                default=0.05,
                description="Significance level. Default 0.05.",
            ),
            "adf_regression": HelperParam(
                type="str",
                required=False,
                default="c",
                description="ADF deterministic component: 'c', 'ct', 'ctt', or 'n'.",
            ),
            "kpss_regression": HelperParam(
                type="str",
                required=False,
                default="c",
                description="KPSS regression type: 'c' (level) or 'ct' (trend).",
            ),
            "adf_maxlag": HelperParam(
                type="int | None",
                required=False,
                default=None,
                description="Max lag for ADF. None → automatic.",
            ),
        },
        outputs=[
            HelperOutput(
                name="stationarity_test_output",
                type="dict",
                description=(
                    "adf (stat, p_value, lags_used, critical_values, verdict), "
                    "kpss (stat, p_value, lags_used, critical_values, verdict), "
                    "consensus stationarity classification, alpha."
                ),
            ),
        ],
        produces_artifacts=["stationarity_test_output"],
        consumes_artifacts=[],
    ),
    skill_doc=SkillDocRef(path="", estimated_tokens=0),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
