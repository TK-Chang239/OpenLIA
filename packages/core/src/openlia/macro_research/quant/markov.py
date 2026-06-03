"""Four Seasons (T2) Markov transition engine. Pure function; no I/O, no LLM.

Reads a baked quarterly row-stochastic transition matrix over the four
canonical Dalio quadrant seasons and reports, from the current season, the
next-quarter transition-probability distribution plus derived stats. The
engine calls this so the model never invents the transition probabilities.
Deterministic (matrix arithmetic, no RNG).
"""

from __future__ import annotations

import numpy as np

from openlia.macro_research.quant.seasons import SeasonsClassification

# Canonical quadrant seasons, in fixed order for matrix math. "Transitioning"
# is a classifier confidence label, not a Markov state.
SEASON_ORDER: tuple[str, ...] = ("Spring", "Summer", "Autumn", "Winter")
_SEASON_SET = frozenset(SEASON_ORDER)

# The adverse (stagflation) season — the headline transition-risk target.
ADVERSE_SEASON = "Autumn"

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
