"""Four Seasons (T2) Markov transition engine. Pure function; no I/O, no LLM.

Reads a baked quarterly row-stochastic transition matrix over the four
canonical Dalio quadrant seasons and reports, from the current season, the
next-quarter transition-probability distribution plus derived stats. The
engine calls this so the model never invents the transition probabilities.
Deterministic (matrix arithmetic, no RNG).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from openlia.macro_research.quant.seasons import SeasonsClassification

# Canonical quadrant seasons, in fixed order for matrix math. "Transitioning"
# is a classifier confidence label, not a Markov state.
SEASON_ORDER: tuple[str, ...] = ("Spring", "Summer", "Autumn", "Winter")
_SEASON_SET = frozenset(SEASON_ORDER)

# The adverse (stagflation) season — the headline transition-risk target.
ADVERSE_SEASON: str = "Autumn"

# Baked quarterly transition probabilities (rows = from, cols = to). Reference
# assumptions (adjustable): diagonal-dominant (seasons persist) with the
# dominant off-diagonal following the clockwise cycle
# Spring -> Summer -> Autumn -> Winter -> Spring. Each row sums to 1.0.
TRANSITION_MATRIX: dict[str, dict[str, float]] = {
    "Spring": {"Spring": 0.60, "Summer": 0.25, "Autumn": 0.05, "Winter": 0.10},
    "Summer": {"Spring": 0.08, "Summer": 0.60, "Autumn": 0.27, "Winter": 0.05},
    "Autumn": {"Spring": 0.05, "Summer": 0.08, "Autumn": 0.57, "Winter": 0.30},
    "Winter": {"Spring": 0.30, "Summer": 0.07, "Autumn": 0.03, "Winter": 0.60},
}


def _matrix_array() -> np.ndarray:
    """TRANSITION_MATRIX as a 4x4 float array in SEASON_ORDER."""
    return np.array(
        [[TRANSITION_MATRIX[r][c] for c in SEASON_ORDER] for r in SEASON_ORDER],
        dtype=float,
    )


def resolve_quadrant(classification: SeasonsClassification) -> str:
    """Map a SeasonsClassification to one of the four canonical seasons.

    A canonical season passes through. A "Transitioning" read is resolved to
    the nearest quadrant from the marker coordinates: growth rising when
    marker_x_pct >= 50, inflation rising when marker_y_pct >= 50 (the same axis
    thresholds classify_four_seasons uses).
    """
    if classification.season in _SEASON_SET:
        return classification.season
    growth_rising = classification.marker_x_pct >= 50
    inflation_rising = classification.marker_y_pct >= 50
    if growth_rising and not inflation_rising:
        return "Spring"
    if growth_rising and inflation_rising:
        return "Summer"
    if not growth_rising and inflation_rising:
        return "Autumn"
    return "Winter"


@dataclass(frozen=True)
class MarkovOutlook:
    current_season: str
    distribution: dict[str, float]  # next-quarter, keyed by season
    persistence: float
    most_likely_next: str
    adverse_season: str
    adverse_prob: float
    expected_dwell_quarters: float
    horizon_quarters: int
    horizon_distribution: dict[str, float]


def markov_outlook(current_season: str, *, steps: int = 4) -> MarkovOutlook:
    """Transition outlook from `current_season` over the baked quarterly matrix.

    Deterministic. Raises ValueError if `current_season` is not one of
    SEASON_ORDER.
    """
    if current_season not in _SEASON_SET:
        raise ValueError(f"unknown season {current_season!r}; expected one of {SEASON_ORDER}")
    matrix = _matrix_array()
    idx = SEASON_ORDER.index(current_season)
    row = matrix[idx]
    distribution = {s: float(row[j]) for j, s in enumerate(SEASON_ORDER)}
    persistence = distribution[current_season]
    most_likely_next = max(SEASON_ORDER, key=lambda s: distribution[s])
    adverse_prob = distribution[ADVERSE_SEASON]
    expected_dwell = 1.0 / (1.0 - persistence) if persistence < 1.0 else float("inf")
    horizon_row = np.linalg.matrix_power(matrix, steps)[idx]
    horizon_distribution = {s: float(horizon_row[j]) for j, s in enumerate(SEASON_ORDER)}
    return MarkovOutlook(
        current_season=current_season,
        distribution=distribution,
        persistence=persistence,
        most_likely_next=most_likely_next,
        adverse_season=ADVERSE_SEASON,
        adverse_prob=adverse_prob,
        expected_dwell_quarters=expected_dwell,
        horizon_quarters=steps,
        horizon_distribution=horizon_distribution,
    )
