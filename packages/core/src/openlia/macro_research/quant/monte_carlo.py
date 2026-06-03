"""All-Weather (T3) Monte-Carlo stress simulator. Pure function; no I/O, no LLM.

Simulates the 1-year joint return distribution of the user's portfolio and the
Dalio reference allocation under a baseline and three baked adverse regimes,
using the reference expected returns / vols / correlation matrix in
``risk_math``. Stress is carried by explicit scenario overlays (drift shifts,
vol multipliers, correlation compression), not a fat-tail distribution. The
engine calls this so the model never invents the simulated numbers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

from openlia.macro_research.risk_math import (
    ASSET_ORDER,
    CORRELATIONS,
    DEFAULT_VOLS,
    EXPECTED_RETURNS,
    REFERENCE_ALLOCATION,
    correlation_matrix,
)

_KNOWN = set(ASSET_ORDER)
_PERCENTILES = (5, 25, 50, 75, 95)

# Crisis correlation target: in a deleveraging, cross-asset correlations
# compress toward a common high positive value (diversification fails).
_CRISIS_RHO = 0.85


@dataclass(frozen=True)
class ScenarioOverlay:
    """A named stress regime expressed as deltas over the baked parameters."""

    name: str
    drift_shift: dict[str, float] = field(default_factory=dict)  # added to annual mu
    vol_mult: dict[str, float] = field(default_factory=dict)  # multiplies annual vol
    corr_stress: float = 0.0  # 0..1 blend of correlations toward the crisis matrix


SCENARIOS: tuple[ScenarioOverlay, ...] = (
    ScenarioOverlay(name="Base case"),
    ScenarioOverlay(
        name="Stagflation",
        drift_shift={
            "equities": -0.10,
            "long_bonds": -0.06,
            "intermediate_bonds": -0.03,
            "gold": 0.08,
            "commodities": 0.10,
        },
        vol_mult={"equities": 1.3, "long_bonds": 1.3, "commodities": 1.2},
    ),
    ScenarioOverlay(
        name="Rate shock",
        drift_shift={"long_bonds": -0.18, "intermediate_bonds": -0.08, "equities": -0.08},
        vol_mult={"long_bonds": 1.5, "intermediate_bonds": 1.3},
    ),
    ScenarioOverlay(
        name="Equity crash / deleveraging",
        drift_shift={
            "equities": -0.30,
            "commodities": -0.15,
            "gold": 0.05,
            "long_bonds": 0.04,
            "intermediate_bonds": 0.03,
        },
        vol_mult={"equities": 1.8, "commodities": 1.5, "gold": 1.2},
        corr_stress=0.6,
    ),
)


@dataclass(frozen=True)
class PortfolioStat:
    median: float
    p5: float


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    user: PortfolioStat
    reference: PortfolioStat
    tone: str  # red / amber / green, from the user's p5


@dataclass(frozen=True)
class DistributionStat:
    percentiles: dict[str, float]  # user, Base case: {"p5":..,"p25":..,...}
    reference_percentiles: dict[str, float]


@dataclass(frozen=True)
class AllWeatherStress:
    distribution: DistributionStat
    scenarios: tuple[ScenarioResult, ...]


def _seed_from_weights(normalized: np.ndarray) -> int:
    # Seed off the NORMALIZED vector so {60, 40} and {0.6, 0.4} reproduce
    # identical output (test_weights_renormalize).
    items = [round(float(x), 6) for x in normalized]
    digest = hashlib.sha256(repr(items).encode()).hexdigest()
    return int(digest[:8], 16)


def _normalize(weights: dict[str, float]) -> np.ndarray:
    unknown = set(weights) - _KNOWN
    if unknown:
        raise ValueError(f"unknown asset classes: {sorted(unknown)}")
    total = float(sum(weights.values()))
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return np.array([weights.get(a, 0.0) / total for a in ASSET_ORDER], dtype=float)


def _tone(p5: float) -> str:
    if p5 <= -0.20:
        return "red"
    if p5 <= -0.10:
        return "amber"
    return "green"


def _crisis_matrix() -> np.ndarray:
    n = len(ASSET_ORDER)
    crisis = np.full((n, n), _CRISIS_RHO)
    np.fill_diagonal(crisis, 1.0)
    return crisis


def simulate_all_weather_stress(
    weights: dict[str, float],
    *,
    n_paths: int = 10_000,
    horizon_years: float = 1.0,
    seed: int | None = None,
) -> AllWeatherStress:
    """Simulate the user portfolio vs the Dalio reference under each scenario.

    Deterministic: when ``seed`` is None it is derived from the sorted, rounded
    weights so identical inputs reproduce identical output (the payload is
    cached). Raises ``ValueError`` on unknown asset classes or non-positive
    total weight.
    """
    w_user = _normalize(weights)
    w_ref = np.array([REFERENCE_ALLOCATION.get(a, 0.0) for a in ASSET_ORDER], dtype=float)
    if seed is None:
        seed = _seed_from_weights(w_user)
    rng = np.random.default_rng(seed)

    base_mu = np.array([EXPECTED_RETURNS[a] for a in ASSET_ORDER], dtype=float)
    base_corr = correlation_matrix(CORRELATIONS)
    crisis = _crisis_matrix()

    scenarios: list[ScenarioResult] = []
    base_user_pcts: dict[str, float] = {}
    base_ref_pcts: dict[str, float] = {}

    for sc in SCENARIOS:
        mu = base_mu + np.array([sc.drift_shift.get(a, 0.0) for a in ASSET_ORDER], dtype=float)
        vols = np.array(
            [DEFAULT_VOLS[a] * sc.vol_mult.get(a, 1.0) for a in ASSET_ORDER], dtype=float
        )
        corr = (1.0 - sc.corr_stress) * base_corr + sc.corr_stress * crisis
        cov = corr * np.outer(vols, vols)
        draws = rng.multivariate_normal(mu * horizon_years, cov * horizon_years, size=n_paths)
        user_ret = draws @ w_user
        ref_ret = draws @ w_ref
        user_stat = PortfolioStat(
            median=float(np.median(user_ret)), p5=float(np.percentile(user_ret, 5))
        )
        ref_stat = PortfolioStat(
            median=float(np.median(ref_ret)), p5=float(np.percentile(ref_ret, 5))
        )
        scenarios.append(
            ScenarioResult(
                name=sc.name, user=user_stat, reference=ref_stat, tone=_tone(user_stat.p5)
            )
        )
        if sc.name == "Base case":
            base_user_pcts = {f"p{q}": float(np.percentile(user_ret, q)) for q in _PERCENTILES}
            base_ref_pcts = {f"p{q}": float(np.percentile(ref_ret, q)) for q in _PERCENTILES}

    return AllWeatherStress(
        distribution=DistributionStat(
            percentiles=base_user_pcts, reference_percentiles=base_ref_pcts
        ),
        scenarios=tuple(scenarios),
    )
