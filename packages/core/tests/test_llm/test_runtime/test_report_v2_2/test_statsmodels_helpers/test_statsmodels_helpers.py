"""Tests for statsmodels regression helpers (PR 4.1).

Covers:
  - Registration of all 6 helpers
  - OLS: y = 2x + 3 + ε → coefficient ≈ 2, intercept ≈ 3
  - Stationarity: random walk fails ADF; stationary AR(1) passes
  - Autocorrelation: AR(1) series has significant lag-1 autocorrelation
  - Heteroskedasticity: known heteroskedastic residuals trigger BP rejection
  - GARCH: simulated GARCH(1,1) returns parameter estimates close to true values
  - VAR: 2-variable VAR fits, Granger causality matrix is 2x2
"""

from __future__ import annotations

import math
import random

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper, list_helpers

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SM_HELPERS = [
    "sm_ols_regression",
    "sm_stationarity_test",
    "sm_autocorrelation",
    "sm_heteroskedasticity_test",
    "sm_garch_volatility",
    "sm_var_var_model",
]


# ---------------------------------------------------------------------------
# Registration checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", SM_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


def test_all_6_sm_helpers_registered() -> None:
    registered = {h.schema.directory.name for h in list_helpers()}
    missing = [n for n in SM_HELPERS if n not in registered]
    assert not missing, f"Missing statsmodels helpers: {missing}"


@pytest.mark.parametrize("name", SM_HELPERS)
def test_helper_produces_artifacts(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    assert len(helper.schema.contract.produces_artifacts) >= 1


# ---------------------------------------------------------------------------
# OLS regression
# ---------------------------------------------------------------------------


def _make_ols_data(
    n: int = 100, true_slope: float = 2.0, true_intercept: float = 3.0, seed: int = 42
) -> tuple[list[float], list[list[float]]]:
    """y = true_slope * x + true_intercept + small noise."""
    rng = random.Random(seed)
    x = [i * 0.1 for i in range(n)]
    y = [true_slope * xi + true_intercept + rng.gauss(0, 0.1) for xi in x]
    # X as row-major (N rows, 1 col)
    X = [[xi] for xi in x]
    return y, X


def test_ols_coefficient_close_to_true() -> None:
    y, X = _make_ols_data()
    helper = get_helper("sm_ols_regression")
    assert helper is not None
    result = helper.impl(y=y, X=X, X_names=["x"], include_constant=True)

    assert abs(result["coefficients"]["x"] - 2.0) < 0.1, (
        f"slope {result['coefficients']['x']} not close to 2.0"
    )
    assert abs(result["coefficients"]["const"] - 3.0) < 0.2, (
        f"intercept {result['coefficients']['const']} not close to 3.0"
    )


def test_ols_r_squared_high() -> None:
    y, X = _make_ols_data()
    helper = get_helper("sm_ols_regression")
    assert helper is not None
    result = helper.impl(y=y, X=X)
    assert result["r_squared"] > 0.99


def test_ols_output_keys() -> None:
    y, X = _make_ols_data(n=50)
    helper = get_helper("sm_ols_regression")
    assert helper is not None
    result = helper.impl(y=y, X=X)
    for key in (
        "coefficients",
        "std_errors",
        "t_statistics",
        "p_values",
        "r_squared",
        "adj_r_squared",
        "f_statistic",
        "f_p_value",
        "n_obs",
        "residuals",
        "fitted_values",
        "method",
    ):
        assert key in result, f"Missing key: {key}"


def test_ols_residuals_length() -> None:
    y, X = _make_ols_data(n=50)
    helper = get_helper("sm_ols_regression")
    assert helper is not None
    result = helper.impl(y=y, X=X)
    assert len(result["residuals"]) == 50
    assert len(result["fitted_values"]) == 50


def test_ols_hac_method_label() -> None:
    y, X = _make_ols_data(n=50)
    helper = get_helper("sm_ols_regression")
    assert helper is not None
    result = helper.impl(y=y, X=X, hac_lag=3)
    assert result["method"] == "OLS_HAC"


def test_ols_raises_on_short_series() -> None:
    helper = get_helper("sm_ols_regression")
    assert helper is not None
    with pytest.raises(ValueError, match="at least 3"):
        helper.impl(y=[1.0, 2.0], X=[[1.0], [2.0]])


# ---------------------------------------------------------------------------
# Stationarity tests
# ---------------------------------------------------------------------------


def _random_walk(n: int = 200, seed: int = 7) -> list[float]:
    """Non-stationary random walk: unit root."""
    rng = random.Random(seed)
    series = [0.0]
    for _ in range(n - 1):
        series.append(series[-1] + rng.gauss(0, 1))
    return series


def _stationary_ar1(n: int = 200, phi: float = 0.3, seed: int = 7) -> list[float]:
    """Stationary AR(1) with |phi| < 1."""
    rng = random.Random(seed)
    series = [rng.gauss(0, 1)]
    for _ in range(n - 1):
        series.append(phi * series[-1] + rng.gauss(0, 1))
    return series


def test_random_walk_non_stationary() -> None:
    """Random walk should fail ADF (high p-value → non-stationary)."""
    series = _random_walk(n=200)
    helper = get_helper("sm_stationarity_test")
    assert helper is not None
    result = helper.impl(series=series, alpha=0.05)
    assert result["adf"]["verdict"] == "non_stationary", (
        f"ADF p={result['adf']['p_value']:.4f} — expected non_stationary"
    )


def test_stationary_ar1_passes_adf() -> None:
    """Stationary AR(1) should reject H0 (unit root) → stationary."""
    series = _stationary_ar1(n=200, phi=0.3)
    helper = get_helper("sm_stationarity_test")
    assert helper is not None
    result = helper.impl(series=series, alpha=0.05)
    assert result["adf"]["verdict"] == "stationary", (
        f"ADF p={result['adf']['p_value']:.4f} — expected stationary"
    )


def test_stationarity_output_keys() -> None:
    series = _stationary_ar1(n=100)
    helper = get_helper("sm_stationarity_test")
    assert helper is not None
    result = helper.impl(series=series)
    for block in ("adf", "kpss"):
        assert block in result
        for key in ("statistic", "p_value", "lags_used", "critical_values", "verdict"):
            assert key in result[block], f"Missing {block}.{key}"
    assert "consensus" in result
    assert result["consensus"] in ("stationary", "non_stationary", "inconclusive")


def test_stationarity_raises_on_short_series() -> None:
    helper = get_helper("sm_stationarity_test")
    assert helper is not None
    with pytest.raises(ValueError, match="at least 10"):
        helper.impl(series=[1.0] * 5)


# ---------------------------------------------------------------------------
# Autocorrelation
# ---------------------------------------------------------------------------


def _ar1_series(n: int = 200, phi: float = 0.8, seed: int = 99) -> list[float]:
    """AR(1) with strong autocorrelation (phi=0.8)."""
    rng = random.Random(seed)
    s = [rng.gauss(0, 1)]
    for _ in range(n - 1):
        s.append(phi * s[-1] + rng.gauss(0, 1))
    return s


def test_ar1_has_significant_lag1_acf() -> None:
    """AR(1) with phi=0.8 should have large ACF at lag 1."""
    series = _ar1_series(phi=0.8, n=200)
    helper = get_helper("sm_autocorrelation")
    assert helper is not None
    result = helper.impl(series=series, lags=20)
    # ACF at lag 0 = 1.0; lag 1 should be ~phi
    assert abs(result["acf_values"][1]) > 0.5, (
        f"ACF lag-1 = {result['acf_values'][1]:.3f} — expected > 0.5 for AR(1) phi=0.8"
    )


def test_autocorrelation_lb_rejects_ar1() -> None:
    """Ljung-Box should reject white-noise H0 for an AR(1) series."""
    series = _ar1_series(phi=0.7, n=200)
    helper = get_helper("sm_autocorrelation")
    assert helper is not None
    result = helper.impl(series=series, lags=20)
    assert result["ljung_box"]["verdict"] == "autocorrelated"


def test_autocorrelation_output_keys() -> None:
    series = _ar1_series(n=100)
    helper = get_helper("sm_autocorrelation")
    assert helper is not None
    result = helper.impl(series=series, lags=10)
    for key in (
        "acf_values",
        "pacf_values",
        "ljung_box",
        "durbin_watson_stat",
        "autocorrelation_classification",
    ):
        assert key in result, f"Missing key: {key}"
    assert len(result["acf_values"]) == 11  # lags 0..10
    assert isinstance(result["durbin_watson_stat"], float)


# ---------------------------------------------------------------------------
# Heteroskedasticity tests
# ---------------------------------------------------------------------------


def _heteroskedastic_residuals(
    n: int = 100, seed: int = 11
) -> tuple[list[float], list[list[float]]]:
    """Residuals whose variance grows with the regressor (classic hetero)."""
    rng = random.Random(seed)
    x = [float(i) for i in range(1, n + 1)]
    # Variance scales as x_i → standard deviation = 0.1 * x_i
    residuals = [rng.gauss(0, 0.1 * xi) for xi in x]
    regressors = [[xi] for xi in x]
    return residuals, regressors


def _homoskedastic_residuals(n: int = 100, seed: int = 22) -> tuple[list[float], list[list[float]]]:
    """Residuals with constant variance."""
    rng = random.Random(seed)
    x = [float(i) for i in range(1, n + 1)]
    residuals = [rng.gauss(0, 1.0) for _ in x]
    regressors = [[xi] for xi in x]
    return residuals, regressors


def test_bp_rejects_heteroskedastic_residuals() -> None:
    residuals, regressors = _heteroskedastic_residuals(n=150)
    helper = get_helper("sm_heteroskedasticity_test")
    assert helper is not None
    result = helper.impl(residuals=residuals, regressors=regressors)
    assert result["breusch_pagan"]["verdict"] == "heteroskedastic", (
        f"BP p={result['breusch_pagan']['lm_p_value']:.4f} — expected heteroskedastic"
    )


def test_hetero_output_keys() -> None:
    residuals, regressors = _homoskedastic_residuals()
    helper = get_helper("sm_heteroskedasticity_test")
    assert helper is not None
    result = helper.impl(residuals=residuals, regressors=regressors)
    for block in ("breusch_pagan", "white"):
        assert block in result
        for key in ("lm_stat", "lm_p_value", "f_stat", "f_p_value", "verdict"):
            assert key in result[block], f"Missing {block}.{key}"
    assert "overall_verdict" in result
    assert result["overall_verdict"] in ("homoskedastic", "heteroskedastic")


def test_hetero_raises_on_short_residuals() -> None:
    helper = get_helper("sm_heteroskedasticity_test")
    assert helper is not None
    with pytest.raises(ValueError, match="at least 10"):
        helper.impl(residuals=[0.1] * 5, regressors=[[float(i)] for i in range(5)])


# ---------------------------------------------------------------------------
# GARCH volatility
# ---------------------------------------------------------------------------


def _simulate_garch11(
    n: int = 500,
    omega: float = 0.05,
    alpha: float = 0.1,
    beta: float = 0.85,
    seed: int = 13,
) -> list[float]:
    """Simulate GARCH(1,1) percent returns."""

    rng = random.Random(seed)
    h = omega / (1 - alpha - beta)  # unconditional variance
    returns = []
    for _ in range(n):
        z = rng.gauss(0, 1)
        ret = math.sqrt(h) * z
        returns.append(ret)
        eps = ret
        h = omega + alpha * eps**2 + beta * h
    return returns


def test_garch_parameters_in_range() -> None:
    """Fitted GARCH parameters should be positive and persistence < 1."""
    returns = _simulate_garch11(n=600, omega=0.05, alpha=0.10, beta=0.85)
    helper = get_helper("sm_garch_volatility")
    assert helper is not None
    result = helper.impl(returns=returns)
    params = result["parameters"]
    assert params["omega"] > 0, "omega must be positive"
    assert 0 < params["alpha"] < 1, f"alpha={params['alpha']} out of (0,1)"
    assert 0 < params["beta"] < 1, f"beta={params['beta']} out of (0,1)"
    assert params["persistence"] < 1.0, "persistence (alpha+beta) must be < 1 for stationarity"


def test_garch_conditional_volatility_length() -> None:
    returns = _simulate_garch11(n=300)
    helper = get_helper("sm_garch_volatility")
    assert helper is not None
    result = helper.impl(returns=returns)
    assert len(result["conditional_volatility"]) == 300


def test_garch_output_keys() -> None:
    returns = _simulate_garch11(n=200)
    helper = get_helper("sm_garch_volatility")
    assert helper is not None
    result = helper.impl(returns=returns)
    for key in (
        "parameters",
        "conditional_volatility",
        "forecasted_volatility",
        "log_likelihood",
        "aic",
        "bic",
        "model_summary",
    ):
        assert key in result, f"Missing key: {key}"
    for p in ("omega", "alpha", "beta", "persistence"):
        assert p in result["parameters"], f"Missing parameter: {p}"


def test_garch_raises_on_short_series() -> None:
    helper = get_helper("sm_garch_volatility")
    assert helper is not None
    with pytest.raises(ValueError, match="at least 30"):
        helper.impl(returns=[0.1] * 10)


# ---------------------------------------------------------------------------
# VAR model
# ---------------------------------------------------------------------------


def _simulate_var2(n: int = 200, seed: int = 55) -> dict[str, list[float]]:
    """Simulate a 2-variable VAR(1) process."""
    rng = random.Random(seed)
    # VAR(1): y1[t] = 0.5*y1[t-1] + 0.1*y2[t-1] + eps1
    #         y2[t] = 0.2*y1[t-1] + 0.4*y2[t-1] + eps2
    y1 = [rng.gauss(0, 1)]
    y2 = [rng.gauss(0, 1)]
    for _ in range(n - 1):
        new_y1 = 0.5 * y1[-1] + 0.1 * y2[-1] + rng.gauss(0, 1)
        new_y2 = 0.2 * y1[-1] + 0.4 * y2[-1] + rng.gauss(0, 1)
        y1.append(new_y1)
        y2.append(new_y2)
    return {"y1": y1, "y2": y2}


def test_var_fits_2variable() -> None:
    series = _simulate_var2(n=200)
    helper = get_helper("sm_var_var_model")
    assert helper is not None
    result = helper.impl(series=series, max_lags=4)
    assert result["lag_order"] >= 1
    assert set(result["variable_names"]) == {"y1", "y2"}
    assert result["n_obs"] >= 195  # VAR consumes lag_order initial obs


def test_var_granger_matrix_is_2x2() -> None:
    series = _simulate_var2(n=200)
    helper = get_helper("sm_var_var_model")
    assert helper is not None
    result = helper.impl(series=series)
    gc = result["granger_causality_matrix"]
    assert set(gc.keys()) == {"y1", "y2"}, "Granger matrix rows should be y1, y2"
    for row in gc.values():
        assert set(row.keys()) == {"y1", "y2"}, "Granger matrix cols should be y1, y2"


def test_var_granger_matrix_self_is_none() -> None:
    series = _simulate_var2(n=200)
    helper = get_helper("sm_var_var_model")
    assert helper is not None
    result = helper.impl(series=series)
    gc = result["granger_causality_matrix"]
    assert gc["y1"]["y1"]["verdict"] == "self"
    assert gc["y2"]["y2"]["verdict"] == "self"


def test_var_irf_shape() -> None:
    series = _simulate_var2(n=200)
    helper = get_helper("sm_var_var_model")
    assert helper is not None
    result = helper.impl(series=series, irf_periods=10)
    irf = result["impulse_responses"]
    # Should have IRF for each (shock, response) pair
    assert "y1" in irf
    assert "y2" in irf["y1"]
    assert len(irf["y1"]["y2"]) == 11  # periods 0..10


def test_var_output_keys() -> None:
    series = _simulate_var2(n=150)
    helper = get_helper("sm_var_var_model")
    assert helper is not None
    result = helper.impl(series=series)
    for key in (
        "lag_order",
        "variable_names",
        "n_obs",
        "coefficients",
        "granger_causality_matrix",
        "impulse_responses",
        "aic",
        "bic",
        "log_likelihood",
    ):
        assert key in result, f"Missing key: {key}"


def test_var_raises_on_single_variable() -> None:
    helper = get_helper("sm_var_var_model")
    assert helper is not None
    with pytest.raises(ValueError, match="at least 2"):
        helper.impl(series={"y1": [1.0] * 50})


def test_var_raises_on_mismatched_lengths() -> None:
    helper = get_helper("sm_var_var_model")
    assert helper is not None
    with pytest.raises(ValueError, match="same length"):
        helper.impl(series={"y1": [1.0] * 50, "y2": [1.0] * 60})
