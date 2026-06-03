"""Five Forces (T5) influence-network engine. Pure function; no I/O, no LLM, no RNG.

A baked directed structural influence matrix (Dalio's documented force
linkages) is applied to the current five force scores as a VAR(1)-style
one-step linear map. The matrix is a reference assumption, NOT fitted from
data (the inputs are soft 0-10 scores, not time series); "VAR-style" refers
only to the one-step map form. The engine calls this so the model never
invents the force-network numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from openlia.macro_research.quant.forces import ForceScores

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


@dataclass(frozen=True)
class NetworkEdge:
    from_label: str
    to_label: str
    strength: float  # decimal 0-1


@dataclass(frozen=True)
class ForceProjection:
    force: str  # display label
    current: float  # 0-10
    projected: float  # 0-10
    delta: float


@dataclass(frozen=True)
class ForceNetwork:
    edges: tuple[NetworkEdge, ...]
    projections: tuple[ForceProjection, ...]
    amplifier: str  # display label
    absorber: str  # display label
    contagion: float  # 0-1
    contagion_label: str


def _contagion_label(value: float) -> str:
    if value < 0.25:
        return "Contained"
    if value < 0.5:
        return "Spreading"
    return "Self-reinforcing"


def analyze_force_network(scores: ForceScores) -> ForceNetwork:
    """VAR(1)-style one-step influence read from the five current force scores.

    Deterministic: pure arithmetic over the baked INFLUENCE matrix. See the
    module docstring on why this is NOT a fitted VAR.
    """
    x = {f: float(getattr(scores, f)) for f in FORCE_ORDER}

    # Projected next-period intensity per driven force: persistence blended with
    # the coupling-weighted average of its drivers' current intensities.
    projections: list[ForceProjection] = []
    for j in FORCE_ORDER:
        in_weight = sum(coupling(i, j) for i in FORCE_ORDER)
        if in_weight > 0.0:
            cross = sum(coupling(i, j) * x[i] for i in FORCE_ORDER) / in_weight
        else:
            cross = x[j]
        nxt = PERSISTENCE * x[j] + (1.0 - PERSISTENCE) * cross
        nxt = max(0.0, min(10.0, nxt))
        projections.append(
            ForceProjection(force=FORCE_LABELS[j], current=x[j], projected=nxt, delta=nxt - x[j])
        )

    # Active directed edges: an intense driver (>= ACTIVE_THRESHOLD) transmitting
    # along a non-zero coupling. Strength is coupling scaled by driver intensity.
    edges: list[NetworkEdge] = []
    for i in FORCE_ORDER:
        if x[i] < ACTIVE_THRESHOLD:
            continue
        for j in FORCE_ORDER:
            a = coupling(i, j)
            if a > 0.0:
                edges.append(
                    NetworkEdge(
                        from_label=FORCE_LABELS[i],
                        to_label=FORCE_LABELS[j],
                        strength=a * (x[i] / 10.0),
                    )
                )
    edges.sort(key=lambda e: e.strength, reverse=True)  # stable: ties keep FORCE_ORDER

    # Roles: amplifier drives the most; absorber receives the most.
    out_strength = {i: sum(coupling(i, j) * x[i] / 10.0 for j in FORCE_ORDER) for i in FORCE_ORDER}
    in_strength = {j: sum(coupling(i, j) * x[i] / 10.0 for i in FORCE_ORDER) for j in FORCE_ORDER}
    amplifier = FORCE_LABELS[max(FORCE_ORDER, key=lambda f: out_strength[f])]
    absorber = FORCE_LABELS[max(FORCE_ORDER, key=lambda f: in_strength[f])]

    contagion = sum(e.strength for e in edges) / len(edges) if edges else 0.0
    contagion = max(0.0, min(1.0, contagion))

    return ForceNetwork(
        edges=tuple(edges),
        projections=tuple(projections),
        amplifier=amplifier,
        absorber=absorber,
        contagion=contagion,
        contagion_label=_contagion_label(contagion),
    )
