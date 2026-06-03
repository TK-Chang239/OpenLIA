"""Five Forces (T5) influence-network engine. Pure function; no I/O, no LLM, no RNG.

A baked directed structural influence matrix (Dalio's documented force
linkages) is applied to the current five force scores as a VAR(1)-style
one-step linear map. The matrix is a reference assumption, NOT fitted from
data (the inputs are soft 0-10 scores, not time series); "VAR-style" refers
only to the one-step map form. The engine calls this so the model never
invents the force-network numbers.
"""

from __future__ import annotations

# Canonical force order for the matrix.
FORCE_ORDER: tuple[str, ...] = (
    "debt_money",
    "political",
    "geopolitical",
    "technology",
    "natural",
)

# Display labels for the payload/UI.
FORCE_LABELS: dict[str, str] = {
    "debt_money": "Debt / money",
    "political": "Internal politics",
    "geopolitical": "Geopolitical",
    "technology": "Technology",
    "natural": "Nature",
}

# A force is "active" (able to transmit) at score >= this — same threshold as
# quant/forces.py.
ACTIVE_THRESHOLD: float = 7.0

# Each force partly persists period-over-period.
PERSISTENCE: float = 0.7

# Directed structural coupling A[driver][driven] in [0, 1], zero diagonal.
# Reference assumptions (adjustable); Dalio's documented force linkages. Only
# non-zero entries are listed; missing pairs are 0.0.
INFLUENCE: dict[str, dict[str, float]] = {
    "debt_money": {"political": 0.6, "geopolitical": 0.4},
    "political": {"geopolitical": 0.5, "debt_money": 0.4},
    "geopolitical": {"debt_money": 0.5, "political": 0.4},
    "technology": {"political": 0.4, "debt_money": 0.2},
    "natural": {"debt_money": 0.4, "political": 0.3, "geopolitical": 0.2},
}


def coupling(driver: str, driven: str) -> float:
    """Directed coupling strength from `driver` to `driven` (0.0 if unspecified)."""
    return INFLUENCE.get(driver, {}).get(driven, 0.0)
