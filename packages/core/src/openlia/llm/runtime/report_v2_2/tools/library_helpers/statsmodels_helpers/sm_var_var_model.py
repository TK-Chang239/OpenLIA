"""sm_var_var_model — Vector Autoregression (VAR) model via statsmodels.

Registered name: "sm_var_var_model"

Fits a VAR(p) model to a multivariate time series, selects lag order via
information criteria, returns coefficient matrices, Granger causality matrix,
and impulse response functions.

Not on the 18-complex list — no skill doc.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR


def execute(
    series: dict[str, list[float]],
    max_lags: int = 4,
    ic: str = "aic",
    irf_periods: int = 10,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Fit VAR(p) model and compute Granger causality + IRFs.

    Args:
        series: Dict mapping variable name → list of observations.
            All series must be the same length (N) and stationary.
        max_lags: Maximum lag order to search. Default 4.
        ic: Information criterion for lag selection: 'aic', 'bic', 'hqic', 'fpe'.
            Default 'aic'.
        irf_periods: Number of periods for impulse response functions. Default 10.
        alpha: Significance level for Granger causality tests. Default 0.05.

    Returns:
        Dict with lag_order, variable_names, coefficients (per lag, per equation),
        granger_causality_matrix (variable x variable p-values),
        impulse_responses (per variable pair), aic, bic, log_likelihood, n_obs.
    """
    if len(series) < 2:
        raise ValueError("VAR requires at least 2 variables")

    var_names = list(series.keys())
    lengths = [len(v) for v in series.values()]
    if len(set(lengths)) != 1:
        raise ValueError("All series must have the same length")

    n = lengths[0]
    if n < 20:
        raise ValueError("Each series must have at least 20 observations")

    # Build DataFrame
    df = pd.DataFrame({name: np.array(vals, dtype=float) for name, vals in series.items()})

    # Fit VAR
    model = VAR(df)
    # Select lag order
    results_select = model.select_order(maxlags=min(max_lags, max(1, n // 5)))
    lag_order: int = getattr(results_select, ic, None)
    if lag_order is None or lag_order == 0:
        lag_order = 1

    res = model.fit(lag_order)

    # Extract coefficients: one dict per lag, each mapping equation → {variable: coef}
    # res.params is a DataFrame: rows = ['const', 'L1.y1', 'L1.y2', ...], cols = var_names
    coef_matrices: list[dict[str, dict[str, float]]] = []
    for lag_idx in range(lag_order):
        lag_num = lag_idx + 1
        lag_coefs: dict[str, dict[str, float]] = {}
        for eq_name in var_names:
            eq_coefs: dict[str, float] = {}
            for var_name in var_names:
                row_label = f"L{lag_num}.{var_name}"
                try:
                    eq_coefs[var_name] = float(res.params.loc[row_label, eq_name])
                except KeyError:
                    eq_coefs[var_name] = float("nan")
            lag_coefs[eq_name] = eq_coefs
        coef_matrices.append(lag_coefs)

    # Granger causality matrix: granger_matrix[caused][causing] = p_value
    # "Does X Granger-cause Y?" — test H0: X does not Granger-cause Y
    granger_matrix: dict[str, dict[str, Any]] = {name: {} for name in var_names}
    for caused in var_names:
        for causing in var_names:
            if caused == causing:
                granger_matrix[caused][causing] = {
                    "p_value": None,
                    "verdict": "self",
                }
                continue
            try:
                gc_res = res.test_causality(caused=caused, causing=causing, kind="f")
                pval = float(gc_res.pvalue)
                granger_matrix[caused][causing] = {
                    "p_value": pval,
                    "verdict": "causes" if pval < alpha else "does_not_cause",
                }
            except Exception as exc:
                granger_matrix[caused][causing] = {
                    "p_value": None,
                    "verdict": "error",
                    "error": str(exc),
                }

    # Impulse response functions
    irf = res.irf(periods=irf_periods)
    irf_dict: dict[str, dict[str, list[float]]] = {}
    for shock_i, shock_name in enumerate(var_names):
        irf_dict[shock_name] = {}
        for resp_i, resp_name in enumerate(var_names):
            # irf.irfs shape: (periods+1, k_var, k_var) — [period, response, shock]
            irf_dict[shock_name][resp_name] = [
                float(irf.irfs[t, resp_i, shock_i]) for t in range(irf.irfs.shape[0])
            ]

    return {
        "lag_order": int(lag_order),
        "ic_used": ic,
        "variable_names": var_names,
        "n_obs": int(res.nobs),
        "coefficients": coef_matrices,
        "granger_causality_matrix": granger_matrix,
        "impulse_responses": irf_dict,
        "aic": float(res.aic),
        "bic": float(res.bic),
        "log_likelihood": float(res.llf),
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
        name="sm_var_var_model",
        category=Category.RISK_MACRO,
        one_liner="VAR(p) model: coefficients, Granger causality matrix, impulse responses.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Model dynamic relationships between multiple stationary time series. "
            "Granger causality tests whether one series helps predict another. "
            "Impulse response functions show how a shock to one variable propagates "
            "through the system over time."
        ),
        when_to_use=[
            "Macro driver analysis: GDP ↔ earnings, rates ↔ margins.",
            "Lead-lag relationships between macro variables and sector returns.",
            "Dynamic spillover analysis between correlated asset classes.",
        ],
        when_not_to_use=[
            "Non-stationary series — difference or cointegrate first.",
            "More than 6-8 variables — curse of dimensionality inflates parameter count.",
            "Fewer than 20 observations per series.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "series": HelperParam(
                type="dict[str, list[float]]",
                required=True,
                description=(
                    "Dict mapping variable name to list of N stationary observations. "
                    "At least 2 variables, at least 20 observations each."
                ),
            ),
            "max_lags": HelperParam(
                type="int",
                required=False,
                default=4,
                description="Maximum lag order for IC-based selection. Default 4.",
            ),
            "ic": HelperParam(
                type="str",
                required=False,
                default="aic",
                description="Information criterion: 'aic', 'bic', 'hqic', 'fpe'. Default 'aic'.",
            ),
            "irf_periods": HelperParam(
                type="int",
                required=False,
                default=10,
                description="Impulse response periods. Default 10.",
            ),
            "alpha": HelperParam(
                type="float",
                required=False,
                default=0.05,
                description="Significance level for Granger causality tests. Default 0.05.",
            ),
        },
        outputs=[
            HelperOutput(
                name="var_model_output",
                type="dict",
                description=(
                    "lag_order, variable_names, n_obs, coefficients (per-lag matrices), "
                    "granger_causality_matrix (p-values + verdicts), impulse_responses, "
                    "aic, bic, log_likelihood."
                ),
            ),
        ],
        produces_artifacts=["var_model_output"],
        consumes_artifacts=[],
    ),
    skill_doc=SkillDocRef(path="", estimated_tokens=0),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
