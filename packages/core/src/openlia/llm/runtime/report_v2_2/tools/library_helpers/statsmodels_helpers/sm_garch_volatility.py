"""sm_garch_volatility — GARCH(1,1) conditional volatility via the arch package.

Registered name: "sm_garch_volatility"

Fits a GARCH(1,1) model to a returns series and returns estimated parameters
(omega, alpha, beta), the full conditional volatility series, and a
1-step-ahead volatility forecast.

Not on the 18-complex list — no skill doc.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def execute(
    returns: list[float],
    scale: float = 1.0,
    dist: str = "normal",
    forecast_horizon: int = 1,
    mean_model: str = "Constant",
) -> dict[str, Any]:
    """Fit GARCH(1,1) and compute conditional volatility.

    Args:
        returns: Return series (percentage or decimal; use scale to adjust).
            Recommend percent returns (e.g. 1.5 for +1.5%) for numerical stability.
        scale: Multiply returns by this before fitting. Default 1.0 (no scaling).
            Use 100.0 if passing decimal returns (e.g. 0.015 → 1.5).
        dist: Error distribution: 'normal' (default), 't' (Student-t), or 'skewt'.
        forecast_horizon: Steps ahead for the volatility forecast. Default 1.
        mean_model: Mean model: 'Constant' (default) or 'Zero'.

    Returns:
        Dict with parameters (omega, alpha, beta, persistence), conditional_volatility
        (list of floats, same length as input), forecasted_volatility (1+ steps),
        log_likelihood, aic, bic, model_summary.
    """
    from arch import arch_model  # type: ignore[import-untyped]

    if len(returns) < 30:
        raise ValueError("returns must have at least 30 observations for GARCH fitting")

    r = np.array(returns, dtype=float) * scale

    # Fit GARCH(1,1)
    am = arch_model(r, vol="Garch", p=1, q=1, dist=dist, mean=mean_model)
    res = am.fit(disp="off", show_warning=False)

    params = res.params
    omega = float(params.get("omega", float("nan")))
    alpha = float(params.get("alpha[1]", float("nan")))
    beta = float(params.get("beta[1]", float("nan")))
    persistence = alpha + beta

    cond_vol = [float(v) for v in res.conditional_volatility]

    # Forecast
    fc = res.forecast(horizon=forecast_horizon, reindex=False)
    forecast_variance = fc.variance.iloc[-1].tolist()
    forecast_vol = [float(v**0.5) for v in forecast_variance]

    return {
        "parameters": {
            "omega": omega,
            "alpha": alpha,
            "beta": beta,
            "persistence": float(persistence),
        },
        "conditional_volatility": cond_vol,
        "forecasted_volatility": forecast_vol,
        "log_likelihood": float(res.loglikelihood),
        "aic": float(res.aic),
        "bic": float(res.bic),
        "model_summary": {
            "n_obs": len(returns),
            "dist": dist,
            "mean_model": mean_model,
            "vol_model": "GARCH(1,1)",
            "scale_applied": float(scale),
        },
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
        name="sm_garch_volatility",
        category=Category.RISK_MACRO,
        one_liner="GARCH(1,1) conditional volatility model and 1-step forecast.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Model time-varying volatility (heteroskedastic variance) in financial "
            "return series. GARCH(1,1) captures volatility clustering — large shocks "
            "are followed by large shocks. Used for risk estimation, option pricing "
            "inputs, and Value-at-Risk calculations."
        ),
        when_to_use=[
            "Estimating current conditional volatility for a stock or index.",
            "Input to VaR or CVaR calculations when volatility clustering is present.",
            "Comparing current implied volatility to GARCH realized vol.",
        ],
        when_not_to_use=[
            "Series shorter than 30 observations — parameter estimates are unreliable.",
            "Non-return series (prices, ratios) — always pass returns.",
            "When volatility is constant — use simple standard deviation.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "returns": HelperParam(
                type="list[float]",
                required=True,
                description=(
                    "Return series. Percent (e.g. 1.5 = +1.5%) preferred for "
                    "numerical stability. At least 30 observations."
                ),
            ),
            "scale": HelperParam(
                type="float",
                required=False,
                default=1.0,
                description=(
                    "Multiply returns by this before fitting. Use 100.0 "
                    "for decimal returns (e.g. 0.015 → 1.5)."
                ),
            ),
            "dist": HelperParam(
                type="str",
                required=False,
                default="normal",
                description="Error distribution: 'normal', 't', or 'skewt'.",
            ),
            "forecast_horizon": HelperParam(
                type="int",
                required=False,
                default=1,
                description="Forecast steps ahead. Default 1.",
            ),
            "mean_model": HelperParam(
                type="str",
                required=False,
                default="Constant",
                description="Mean model: 'Constant' or 'Zero'.",
            ),
        },
        outputs=[
            HelperOutput(
                name="garch_volatility_output",
                type="dict",
                description=(
                    "parameters (omega, alpha, beta, persistence), "
                    "conditional_volatility (list), forecasted_volatility (list), "
                    "log_likelihood, aic, bic, model_summary."
                ),
            ),
        ],
        produces_artifacts=["garch_volatility_output"],
        consumes_artifacts=[],
    ),
    skill_doc=SkillDocRef(path="", estimated_tokens=0),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
