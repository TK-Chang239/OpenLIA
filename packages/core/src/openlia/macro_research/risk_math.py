"""Closed-form risk math for T3 All-Weather audit."""

from __future__ import annotations

import numpy as np

# Annualized volatilities, computed as the stdev of daily log returns of the
# proxy ETFs (x sqrt(252)) over the common window 2006-02-03..2025-12-31. See
# planning/specs/systems/macro-research-reference-datasets-provenance.md.
DEFAULT_VOLS: dict[str, float] = {
    "equities": 0.194,
    "long_bonds": 0.149,
    "intermediate_bonds": 0.069,
    "gold": 0.179,
    "commodities": 0.192,
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

# Long-run nominal expected returns -- CURATED forward capital-market
# assumptions (long-run real return + a ~2.5% inflation assumption), used as the
# Monte-Carlo drift. NOT the realized window CAGR (a poor proxy for forward
# returns, recorded only as a sanity reference in the provenance doc). See
# planning/specs/systems/macro-research-reference-datasets-provenance.md.
EXPECTED_RETURNS: dict[str, float] = {
    "equities": 0.07,
    "long_bonds": 0.04,
    "intermediate_bonds": 0.035,
    "gold": 0.03,
    "commodities": 0.04,
}

# Cross-asset correlations (upper-triangle; symmetric, unit diagonal), computed
# as Pearson correlation of daily log returns over the common window
# 2006-02-03..2025-12-31. Empirical => positive-semi-definite. See the
# provenance doc above.
CORRELATIONS: dict[tuple[str, str], float] = {
    ("equities", "long_bonds"): -0.31,
    ("equities", "intermediate_bonds"): -0.30,
    ("equities", "gold"): 0.06,
    ("equities", "commodities"): 0.41,
    ("long_bonds", "intermediate_bonds"): 0.91,
    ("long_bonds", "gold"): 0.16,
    ("long_bonds", "commodities"): -0.22,
    ("intermediate_bonds", "gold"): 0.21,
    ("intermediate_bonds", "commodities"): -0.19,
    ("gold", "commodities"): 0.37,
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
