"""sm_heteroskedasticity_test — Breusch-Pagan and White's tests via statsmodels.

Registered name: "sm_heteroskedasticity_test"

Tests OLS residuals for heteroskedasticity (non-constant variance).
Breusch-Pagan: linear relationship between squared residuals and regressors.
White's test: general auxiliary regression including cross-products and squares.

Not on the 18-complex list — no skill doc.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan, het_white


def execute(
    residuals: list[float],
    regressors: list[list[float]],
    regressor_names: list[str] | None = None,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Run Breusch-Pagan and White heteroskedasticity tests.

    Args:
        residuals: OLS residuals from a prior regression (N observations).
        regressors: The original X matrix used in that regression (without the constant).
            Row-major: N rows, M columns. Each inner list is one observation.
        regressor_names: Column names. Defaults to x0, x1, ...
        alpha: Significance level. Default 0.05.

    Returns:
        Dict with breusch_pagan (lm_stat, lm_p_value, f_stat, f_p_value, verdict),
        white (lm_stat, lm_p_value, f_stat, f_p_value, verdict),
        overall_verdict, alpha.
    """
    n = len(residuals)
    if n < 10:
        raise ValueError("residuals must have at least 10 observations")
    if not regressors:
        raise ValueError("regressors must not be empty")

    resid_arr = np.array(residuals, dtype=float)

    # Build regressor array (row-major)
    x_arr = np.array(regressors, dtype=float)
    if x_arr.ndim == 1:
        x_arr = x_arr.reshape(-1, 1)

    if x_arr.shape[0] != n:
        raise ValueError(
            f"regressors row count {x_arr.shape[0]} does not match residuals length {n}"
        )

    if regressor_names is None:
        regressor_names = [f"x{i}" for i in range(x_arr.shape[1])]

    # Add constant for the aux regressions
    x_with_const = sm.add_constant(x_arr, has_constant="add")

    # Breusch-Pagan
    bp_lm, bp_lm_p, bp_f, bp_f_p = het_breuschpagan(resid_arr, x_with_const)
    bp_verdict = "heteroskedastic" if float(bp_lm_p) < alpha else "homoskedastic"

    # White's test
    try:
        w_lm, w_lm_p, w_f, w_f_p = het_white(resid_arr, x_with_const)
        white_verdict = "heteroskedastic" if float(w_lm_p) < alpha else "homoskedastic"
        white_result: dict[str, Any] = {
            "lm_stat": float(w_lm),
            "lm_p_value": float(w_lm_p),
            "f_stat": float(w_f),
            "f_p_value": float(w_f_p),
            "verdict": white_verdict,
        }
    except Exception as exc:
        # White's test can fail when n is too small for the expanded regressor matrix
        white_verdict = "unavailable"
        white_result = {
            "lm_stat": None,
            "lm_p_value": None,
            "f_stat": None,
            "f_p_value": None,
            "verdict": "unavailable",
            "error": str(exc),
        }

    # Overall: flag heteroskedastic if either test rejects H0
    if bp_verdict == "heteroskedastic" or white_verdict == "heteroskedastic":
        overall = "heteroskedastic"
    elif white_verdict == "unavailable":
        overall = bp_verdict
    else:
        overall = "homoskedastic"

    return {
        "breusch_pagan": {
            "lm_stat": float(bp_lm),
            "lm_p_value": float(bp_lm_p),
            "f_stat": float(bp_f),
            "f_p_value": float(bp_f_p),
            "verdict": bp_verdict,
        },
        "white": white_result,
        "overall_verdict": overall,
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
        name="sm_heteroskedasticity_test",
        category=Category.RISK_MACRO,
        one_liner="Breusch-Pagan and White's tests for non-constant residual variance.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Validate the homoskedasticity assumption after OLS regression. "
            "Heteroskedastic residuals invalidate standard errors — use robust "
            "(HAC) SEs if rejected. Run after sm_ols_regression when the series "
            "spans different market regimes or the dependent variable has exponential scale."
        ),
        when_to_use=[
            "Post-regression diagnostic after sm_ols_regression.",
            "Financial returns data (variance commonly clusters over time).",
            "Cross-sectional data spanning companies of very different sizes.",
        ],
        when_not_to_use=[
            "Before running OLS — run OLS first, pass residuals here.",
            "Series shorter than 20 observations — White's test will fail.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "residuals": HelperParam(
                type="list[float]",
                required=True,
                description="OLS residuals from a prior regression.",
            ),
            "regressors": HelperParam(
                type="list[list[float]]",
                required=True,
                description="Original X matrix (without constant), N rows x M cols.",
            ),
            "regressor_names": HelperParam(
                type="list[str] | None",
                required=False,
                default=None,
                description="Column names. Defaults to x0, x1, ...",
            ),
            "alpha": HelperParam(
                type="float",
                required=False,
                default=0.05,
                description="Significance level. Default 0.05.",
            ),
        },
        outputs=[
            HelperOutput(
                name="heteroskedasticity_test_output",
                type="dict",
                description=(
                    "breusch_pagan (lm_stat, lm_p_value, f_stat, f_p_value, verdict), "
                    "white (same), overall_verdict, alpha."
                ),
            ),
        ],
        produces_artifacts=["heteroskedasticity_test_output"],
        consumes_artifacts=["ols_regression_output"],
    ),
    skill_doc=SkillDocRef(path="", estimated_tokens=0),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
