"""Closed-form risk math for T3 All-Weather audit."""

from __future__ import annotations

import numpy as np

# Long-run annualized volatility defaults (see design spec).
DEFAULT_VOLS: dict[str, float] = {
    "equities": 0.165,
    "long_bonds": 0.115,
    "intermediate_bonds": 0.07,
    "gold": 0.16,
    "commodities": 0.18,
}

# Dalio reference All-Weather allocation.
REFERENCE_ALLOCATION: dict[str, float] = {
    "equities": 0.30,
    "long_bonds": 0.40,
    "intermediate_bonds": 0.15,
    "gold": 0.075,
    "commodities": 0.075,
}

# Season → aligned assets (for coverage scoring).
SEASON_ASSETS: dict[str, set[str]] = {
    "Spring": {"equities"},
    "Summer": {"commodities"},
    "Autumn": {"gold", "commodities"},
    "Winter": {"long_bonds", "intermediate_bonds"},
}


# Canonical asset-class order for matrix math.
ASSET_ORDER: tuple[str, ...] = (
    "equities",
    "long_bonds",
    "intermediate_bonds",
    "gold",
    "commodities",
)

# Long-run annualized nominal expected return per asset class. Reference
# assumptions (adjustable), used as the Monte-Carlo drift.
EXPECTED_RETURNS: dict[str, float] = {
    "equities": 0.07,
    "long_bonds": 0.03,
    "intermediate_bonds": 0.025,
    "gold": 0.03,
    "commodities": 0.04,
}

# Long-run cross-asset correlations (upper-triangle; symmetric, unit diagonal).
# Reference assumptions (adjustable).
CORRELATIONS: dict[tuple[str, str], float] = {
    ("equities", "long_bonds"): -0.15,
    ("equities", "intermediate_bonds"): -0.05,
    ("equities", "gold"): 0.05,
    ("equities", "commodities"): 0.35,
    ("long_bonds", "intermediate_bonds"): 0.85,
    ("long_bonds", "gold"): 0.20,
    ("long_bonds", "commodities"): -0.10,
    ("intermediate_bonds", "gold"): 0.15,
    ("intermediate_bonds", "commodities"): -0.05,
    ("gold", "commodities"): 0.30,
}


def correlation_matrix(
    correlations: dict[tuple[str, str], float],
    order: tuple[str, ...] = ASSET_ORDER,
) -> np.ndarray:
    """Build a symmetric correlation matrix (unit diagonal) in ``order``.

    ``correlations`` keys may be given in either direction; both off-diagonal
    cells are filled. Missing pairs default to 0.0.
    """
    n = len(order)
    idx = {asset: i for i, asset in enumerate(order)}
    corr = np.eye(n)
    for (a, b), rho in correlations.items():
        i, j = idx[a], idx[b]
        corr[i, j] = rho
        corr[j, i] = rho
    return corr


def covariance_matrix(
    *,
    vols: dict[str, float],
    correlations: dict[tuple[str, str], float],
    order: tuple[str, ...] = ASSET_ORDER,
) -> np.ndarray:
    """Covariance matrix Sigma_ij = rho_ij * sigma_i * sigma_j."""
    corr = correlation_matrix(correlations, order)
    sigma = np.array([vols[a] for a in order], dtype=float)
    return corr * np.outer(sigma, sigma)


def risk_contributions(
    *,
    weights: dict[str, float],
    vols: dict[str, float],
) -> dict[str, float]:
    """Simplified linear risk contribution (w_i * vol_i, normalized)."""
    keys = sorted(weights.keys())
    w = np.array([weights[k] for k in keys], dtype=float)
    v = np.array([vols.get(k, 0.1) for k in keys], dtype=float)
    raw = w * v
    total = raw.sum()
    if total <= 0:
        return {k: 0.0 for k in keys}
    normalized = raw / total
    return {k: float(normalized[i]) for i, k in enumerate(keys)}


def coverage_for_season(
    *,
    season: str,
    weights: dict[str, float],
    strong_threshold: float = 0.20,
    partial_threshold: float = 0.05,
) -> str:
    """One of: exposed | partial | strong."""
    aligned = SEASON_ASSETS.get(season, set())
    total = sum(w for k, w in weights.items() if k in aligned)
    if total >= strong_threshold:
        return "strong"
    if total >= partial_threshold:
        return "partial"
    return "exposed"


def gold_gap(
    *,
    user_weight: float,
    reference_weight: float = 0.075,
    stress_weight: float = 0.15,
    use_stress: bool = False,
) -> dict[str, float]:
    target = stress_weight if use_stress else reference_weight
    return {
        "current": user_weight,
        "target": target,
        "gap": user_weight - target,
    }
