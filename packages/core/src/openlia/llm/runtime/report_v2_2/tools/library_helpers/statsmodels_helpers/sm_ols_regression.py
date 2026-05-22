"""sm_ols_regression — Ordinary Least Squares regression via statsmodels.

Registered name: "sm_ols_regression"

Fits OLS (optionally with Newey-West HAC standard errors) and returns
coefficients, standard errors, t-statistics, p-values, R², adjusted R²,
F-statistic, residuals, and fitted values.

Not on the 18-complex list — no skill doc.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import statsmodels.api as sm

from openlia.llm.runtime.report_v2_2 import (
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
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper


def execute(
    y: list[float],
    X: list[list[float]],
    X_names: list[str] | None = None,
    include_constant: bool = True,
    hac_lag: int | None = None,
) -> dict[str, Any]:
    """Fit OLS regression.

    Args:
        y: Dependent variable (N observations).
        X: Independent variables — list of column vectors, each length N.
            Pass a list of N lists where each inner list is one row, OR a list
            of M column-vectors each of length N. Detected by shape.
            Accepts both (N, M) row-major and (M, N) column-major; auto-detected
            via len(X[0]) — if inner list length == len(y), X is column-major.
        X_names: Variable names, one per column. Defaults to x0, x1, ...
        include_constant: Add a constant (intercept) column. Default True.
        hac_lag: If set, use Newey-West HAC standard errors with this lag length.

    Returns:
        Dict with coefficients, std_errors, t_statistics, p_values, r_squared,
        adj_r_squared, f_statistic, f_p_value, n_obs, residuals, fitted_values, method.
    """
    n = len(y)
    if n < 3:
        raise ValueError("y must have at least 3 observations")
    if not X:
        raise ValueError("X must not be empty")

    y_arr = np.array(y, dtype=float)

    # Auto-detect row-major vs column-major
    # Row-major: X is list of N rows, each row has M features → len(X)==N, len(X[0])==M
    # Column-major: X is list of M columns, each col has N values → len(X)==M, len(X[0])==N
    inner_len = len(X[0]) if X else 0
    if inner_len == n and len(X) != n:
        # Column-major: transpose to row-major
        x_arr = np.column_stack([np.array(col, dtype=float) for col in X])
    else:
        # Row-major (most common)
        x_arr = np.array(X, dtype=float)
        if x_arr.ndim == 1:
            x_arr = x_arr.reshape(-1, 1)

    if x_arr.shape[0] != n:
        raise ValueError(f"X row count {x_arr.shape[0]} does not match y length {n}")

    n_features = x_arr.shape[1] if x_arr.ndim == 2 else 1

    if X_names is None:
        X_names = [f"x{i}" for i in range(n_features)]
    elif len(X_names) != n_features:
        raise ValueError(
            f"X_names length {len(X_names)} does not match X column count {n_features}"
        )

    if include_constant:
        x_arr = sm.add_constant(x_arr, has_constant="add")
        param_names = ["const", *X_names]
    else:
        param_names = list(X_names)

    model = sm.OLS(y_arr, x_arr)
    if hac_lag is not None:
        result = model.fit(cov_type="HAC", cov_kwds={"maxlags": hac_lag})
        method = "OLS_HAC"
    else:
        result = model.fit()
        method = "OLS"

    return {
        "coefficients": {
            name: float(coef) for name, coef in zip(param_names, result.params, strict=True)
        },
        "std_errors": {name: float(se) for name, se in zip(param_names, result.bse, strict=True)},
        "t_statistics": {
            name: float(t) for name, t in zip(param_names, result.tvalues, strict=True)
        },
        "p_values": {name: float(p) for name, p in zip(param_names, result.pvalues, strict=True)},
        "r_squared": float(result.rsquared),
        "adj_r_squared": float(result.rsquared_adj),
        "f_statistic": float(result.fvalue) if result.fvalue is not None else None,
        "f_p_value": float(result.f_pvalue) if result.f_pvalue is not None else None,
        "n_obs": int(result.nobs),
        "residuals": [float(r) for r in result.resid],
        "fitted_values": [float(f) for f in result.fittedvalues],
        "method": method,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="sm_ols_regression",
        category=Category.RISK_MACRO,
        one_liner="OLS regression: coefficients, R², F-stat, residuals, fitted values.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fit a linear regression model to quantify the relationship between a "
            "dependent variable and one or more independent variables. Useful for "
            "margin trend over time, factor exposure analysis, or revenue sensitivity "
            "to macro drivers."
        ),
        when_to_use=[
            "Margin trend: y=margin, X=time index.",
            "Factor exposure: y=stock returns, X=factor returns.",
            "Revenue sensitivity: y=revenue growth, X=GDP/CPI.",
            "Any linear relationship requiring statistical significance testing.",
        ],
        when_not_to_use=[
            "Non-linear relationships — use a non-linear model instead.",
            "Time series with autocorrelated errors without hac_lag — set hac_lag.",
            "Classification tasks — use logistic regression.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "y": HelperParam(
                type="list[float]",
                required=True,
                description="Dependent variable, N observations.",
            ),
            "X": HelperParam(
                type="list[list[float]]",
                required=True,
                description=(
                    "Independent variables. Row-major (N rows, M cols) or "
                    "column-major (M cols, N rows); auto-detected."
                ),
            ),
            "X_names": HelperParam(
                type="list[str] | None",
                required=False,
                default=None,
                description="Column names for X. Defaults to x0, x1, ...",
            ),
            "include_constant": HelperParam(
                type="bool",
                required=False,
                default=True,
                description="Add intercept column. Default True.",
            ),
            "hac_lag": HelperParam(
                type="int | None",
                required=False,
                default=None,
                description=(
                    "Newey-West HAC lag length. Set when residuals are "
                    "autocorrelated (time series regression)."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="ols_regression_output",
                type="dict",
                description=(
                    "coefficients, std_errors, t_statistics, p_values, r_squared, "
                    "adj_r_squared, f_statistic, f_p_value, n_obs, residuals, "
                    "fitted_values, method."
                ),
            ),
        ],
        produces_artifacts=["ols_regression_output"],
        consumes_artifacts=[],
    ),
    skill_doc=SkillDocRef(path="", estimated_tokens=0),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
