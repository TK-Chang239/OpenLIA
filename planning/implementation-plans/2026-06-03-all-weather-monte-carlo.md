# All-Weather Monte-Carlo Stress — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic Monte-Carlo stress engine to the All-Weather (T3) dashboard that simulates the 1-year joint return distribution of the user's portfolio vs the Dalio reference allocation, under a baseline and three baked adverse regimes, and renders it as a new typed `stressTest` section.

**Architecture:** A pure-function core simulator (`macro_research/quant/monte_carlo.py`) draws multivariate-normal asset returns from baked reference parameters (expected returns + correlation matrix added to `risk_math.py`, combined with the existing `DEFAULT_VOLS`), with stress carried by named scenario overlays. A new `report_dash_mr` tool (`simulate_all_weather_stress`) exposes it to the engine; the prompt instructs the model to use the numbers verbatim to fill a new `stressTest` payload section, rendered by a new card in `AllWeatherView.tsx`.

**Tech Stack:** Python 3.13, numpy, Pydantic v2, pytest; React/TypeScript/Vite, vitest. `uv` for Python, `npm` for frontend.

**Spec:** `planning/specs/systems/macro-research-heavy-quant-all-weather-monte-carlo-design.md`

**Conventions:**
- Run Python via `uv run pytest ...` / `uv run ruff ...`. The uv cache (`~/.cache/uv`) is blocked under the default command sandbox; if a command fails with "Failed to initialize cache ... Operation not permitted", re-run it with the sandbox disabled.
- Percentages in the payload are **decimals** (e.g. `-0.12` for −12%); the view formats them.
- Asset classes (canonical order): `equities, long_bonds, intermediate_bonds, gold, commodities`.

---

### Task 1: Baked reference parameters + matrix helpers in `risk_math.py`

**Files:**
- Modify: `packages/core/src/openlia/macro_research/risk_math.py`
- Test: `packages/core/tests/macro_research/test_risk_math.py` (create)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/macro_research/test_risk_math.py`:

```python
"""Baked reference parameters + covariance/correlation helpers."""

import numpy as np

from openlia.macro_research.risk_math import (
    ASSET_ORDER,
    CORRELATIONS,
    DEFAULT_VOLS,
    EXPECTED_RETURNS,
    correlation_matrix,
    covariance_matrix,
)


def test_asset_order_is_the_five_classes() -> None:
    assert ASSET_ORDER == (
        "equities",
        "long_bonds",
        "intermediate_bonds",
        "gold",
        "commodities",
    )


def test_baked_params_cover_every_asset() -> None:
    for asset in ASSET_ORDER:
        assert asset in EXPECTED_RETURNS
        assert asset in DEFAULT_VOLS


def test_correlation_matrix_is_symmetric_unit_diagonal() -> None:
    corr = correlation_matrix(CORRELATIONS)
    assert corr.shape == (5, 5)
    assert np.allclose(np.diag(corr), 1.0)
    assert np.allclose(corr, corr.T)


def test_correlation_matrix_is_positive_semidefinite() -> None:
    # Hand-tuned reference correlations must form a valid (PSD) matrix so the
    # Gaussian simulator can draw from it.
    corr = correlation_matrix(CORRELATIONS)
    eigenvalues = np.linalg.eigvalsh(corr)
    assert eigenvalues.min() >= -1e-8


def test_covariance_matrix_diagonal_is_variance() -> None:
    cov = covariance_matrix(vols=DEFAULT_VOLS, correlations=CORRELATIONS)
    for i, asset in enumerate(ASSET_ORDER):
        assert np.isclose(cov[i, i], DEFAULT_VOLS[asset] ** 2)
    assert np.allclose(cov, cov.T)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_risk_math.py -q`
Expected: FAIL with `ImportError` (`ASSET_ORDER`, `EXPECTED_RETURNS`, `CORRELATIONS`, `correlation_matrix`, `covariance_matrix` do not exist).

- [ ] **Step 3: Implement**

Append to `packages/core/src/openlia/macro_research/risk_math.py` (after `REFERENCE_ALLOCATION`/`SEASON_ASSETS`, before `risk_contributions`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_risk_math.py -q`
Expected: PASS (5 passed). If `test_correlation_matrix_is_positive_semidefinite` fails, the baked `CORRELATIONS` are inconsistent — reduce the largest off-diagonals until the min eigenvalue is `>= 0`.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/risk_math.py packages/core/tests/macro_research/test_risk_math.py
uv run ruff format packages/core/src/openlia/macro_research/risk_math.py packages/core/tests/macro_research/test_risk_math.py
git add packages/core/src/openlia/macro_research/risk_math.py packages/core/tests/macro_research/test_risk_math.py
git commit -m "feat(macro-research): baked expected-returns + correlation matrix for MC"
```

---

### Task 2: Monte-Carlo simulator (`quant/monte_carlo.py`)

**Files:**
- Create: `packages/core/src/openlia/macro_research/quant/monte_carlo.py`
- Test: `packages/core/tests/macro_research/test_monte_carlo.py` (create)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/macro_research/test_monte_carlo.py`:

```python
"""Deterministic All-Weather Monte-Carlo stress simulator. Pure; no I/O, no LLM."""

import pytest

from openlia.macro_research.quant.monte_carlo import (
    SCENARIOS,
    simulate_all_weather_stress,
)

_BALANCED = {
    "equities": 0.30,
    "long_bonds": 0.40,
    "intermediate_bonds": 0.15,
    "gold": 0.075,
    "commodities": 0.075,
}


def test_returns_base_plus_three_scenarios() -> None:
    out = simulate_all_weather_stress(_BALANCED)
    names = [s.name for s in out.scenarios]
    assert names[0] == "Base case"
    assert {"Stagflation", "Rate shock", "Equity crash / deleveraging"} <= set(names)
    assert len(out.scenarios) == len(SCENARIOS)


def test_is_deterministic_for_same_weights() -> None:
    a = simulate_all_weather_stress(_BALANCED)
    b = simulate_all_weather_stress(_BALANCED)
    assert a == b


def test_base_distribution_percentiles_are_ordered() -> None:
    out = simulate_all_weather_stress(_BALANCED)
    p = out.distribution.percentiles
    assert p["p5"] < p["p25"] < p["p50"] < p["p75"] < p["p95"]


def test_equity_crash_is_worse_than_base_for_the_user() -> None:
    out = simulate_all_weather_stress(_BALANCED)
    by_name = {s.name: s for s in out.scenarios}
    assert by_name["Equity crash / deleveraging"].user.p5 < by_name["Base case"].user.p5


def test_concentrated_equities_crash_worse_than_reference() -> None:
    out = simulate_all_weather_stress({"equities": 1.0})
    crash = next(s for s in out.scenarios if s.name == "Equity crash / deleveraging")
    # An all-equity book has a deeper crash tail than the diversified reference.
    assert crash.user.p5 < crash.reference.p5


def test_tone_is_derived_from_user_p5() -> None:
    out = simulate_all_weather_stress({"equities": 1.0})
    crash = next(s for s in out.scenarios if s.name == "Equity crash / deleveraging")
    assert crash.tone == "red"


def test_weights_renormalize() -> None:
    a = simulate_all_weather_stress({"equities": 60.0, "long_bonds": 40.0})
    b = simulate_all_weather_stress({"equities": 0.6, "long_bonds": 0.4})
    assert a == b


def test_unknown_asset_raises() -> None:
    with pytest.raises(ValueError, match="unknown asset"):
        simulate_all_weather_stress({"crypto": 1.0})


def test_empty_weights_raises() -> None:
    with pytest.raises(ValueError):
        simulate_all_weather_stress({})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_monte_carlo.py -q`
Expected: FAIL with `ModuleNotFoundError: openlia.macro_research.quant.monte_carlo`.

- [ ] **Step 3: Implement**

Create `packages/core/src/openlia/macro_research/quant/monte_carlo.py`:

```python
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

    base_mu = np.array([EXPECTED_RETURNS[a] for a in ASSET_ORDER], dtype=float)
    base_corr = correlation_matrix(CORRELATIONS)
    crisis = _crisis_matrix()

    scenarios: list[ScenarioResult] = []
    base_user_pcts: dict[str, float] = {}
    base_ref_pcts: dict[str, float] = {}

    # Per-scenario RNG derived from the master seed so a scenario's draws are
    # independent of iteration order — reordering/extending SCENARIOS never
    # silently changes another scenario's (cached) output.
    for i, sc in enumerate(SCENARIOS):
        sc_rng = np.random.default_rng([seed, i])
        mu = base_mu + np.array([sc.drift_shift.get(a, 0.0) for a in ASSET_ORDER], dtype=float)
        vols = np.array(
            [DEFAULT_VOLS[a] * sc.vol_mult.get(a, 1.0) for a in ASSET_ORDER], dtype=float
        )
        corr = (1.0 - sc.corr_stress) * base_corr + sc.corr_stress * crisis
        cov = corr * np.outer(vols, vols)
        draws = sc_rng.multivariate_normal(mu * horizon_years, cov * horizon_years, size=n_paths)
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

    if not base_user_pcts:
        raise RuntimeError("SCENARIOS must contain a 'Base case' entry")

    return AllWeatherStress(
        distribution=DistributionStat(
            percentiles=base_user_pcts, reference_percentiles=base_ref_pcts
        ),
        scenarios=tuple(scenarios),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_monte_carlo.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/quant/monte_carlo.py packages/core/tests/macro_research/test_monte_carlo.py
uv run ruff format packages/core/src/openlia/macro_research/quant/monte_carlo.py packages/core/tests/macro_research/test_monte_carlo.py
git add packages/core/src/openlia/macro_research/quant/monte_carlo.py packages/core/tests/macro_research/test_monte_carlo.py
git commit -m "feat(macro-research): All-Weather Monte-Carlo stress simulator"
```

---

### Task 3: `stressTest` payload models (`payloads.py`)

**Files:**
- Modify: `packages/core/src/openlia/macro_research/payloads.py` (insert before `class AllWeatherData`, ~line 486; add field to `AllWeatherData`)
- Test: `packages/core/tests/macro_research/test_payloads_all_weather.py:13-159`

- [ ] **Step 1: Write the failing test**

In `packages/core/tests/macro_research/test_payloads_all_weather.py`, add a `stressTest` block to the dict returned by `_all_weather_fixture()` (insert immediately before the `"verdict": {...}` key):

```python
        "stressTest": {
            "label": "Section E — Monte-Carlo stress test",
            "intro": "10,000-path 1-year simulation under baked reference parameters.",
            "distribution": {
                "title": "Base-case 1-year return distribution (user vs reference)",
                "bars": [
                    {"label": "5th pct", "userPct": -0.18, "refPct": -0.09},
                    {"label": "Median", "userPct": 0.06, "refPct": 0.05},
                    {"label": "95th pct", "userPct": 0.31, "refPct": 0.20},
                ],
            },
            "scenarios": [
                {
                    "name": "Equity crash / deleveraging",
                    "userMedianPct": -0.22,
                    "userP5Pct": -0.41,
                    "refMedianPct": -0.08,
                    "refP5Pct": -0.19,
                    "tone": "red",
                }
            ],
            "note": "Stress carried by scenario overlays; Gaussian draws.",
        },
```

Then add a test function at the end of the file:

```python
def test_all_weather_stress_test_validates() -> None:
    data = AllWeatherData.model_validate(_all_weather_fixture())
    assert data.stressTest.distribution.bars[0].userPct == -0.18
    row = data.stressTest.scenarios[0]
    assert row.name == "Equity crash / deleveraging"
    assert row.tone == "red"
    assert row.userP5Pct == -0.41
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_payloads_all_weather.py -q`
Expected: FAIL — existing tests now error because `AllWeatherData` has no `stressTest` field (extra key) → actually Pydantic ignores unknown keys by default, so `test_all_weather_stress_test_validates` fails with `AttributeError: 'AllWeatherData' object has no attribute 'stressTest'`.

- [ ] **Step 3: Implement**

In `packages/core/src/openlia/macro_research/payloads.py`, insert these models immediately before `class AllWeatherData(BaseModel):`:

```python
class T3StressBar(BaseModel):
    label: str
    userPct: float
    refPct: float


class T3StressScenarioRow(BaseModel):
    name: str
    userMedianPct: float
    userP5Pct: float
    refMedianPct: float
    refP5Pct: float
    tone: Tone


class T3StressDistribution(BaseModel):
    title: str
    bars: list[T3StressBar]


class T3StressTest(BaseModel):
    label: str
    intro: str
    distribution: T3StressDistribution
    scenarios: list[T3StressScenarioRow]
    note: str
```

Then add the field to `AllWeatherData` (immediately after `caveats: T3Caveats`):

```python
    stressTest: T3StressTest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_payloads_all_weather.py -q`
Expected: PASS (all, including `test_all_weather_stress_test_validates`).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_all_weather.py
uv run ruff format packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_all_weather.py
git add packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_all_weather.py
git commit -m "feat(macro-research): stressTest payload models on AllWeatherData"
```

---

### Task 4: Frontend types + FALLBACK (`types.ts`, `all_weather.ts`)

**Files:**
- Modify: `frontend/src/lib/macro_research/dalio_copy/types.ts` (add interfaces + `stressTest` on `AllWeatherData`, ~line 338)
- Modify: `frontend/src/lib/macro_research/dalio_copy/all_weather.ts` (add `stressTest` instance)

- [ ] **Step 1: Add the interfaces**

In `frontend/src/lib/macro_research/dalio_copy/types.ts`, immediately before `export interface AllWeatherData {` (line 303), add:

```typescript
export interface T3StressBar {
  label: string;
  userPct: number;
  refPct: number;
}

export interface T3StressScenarioRow {
  name: string;
  userMedianPct: number;
  userP5Pct: number;
  refMedianPct: number;
  refP5Pct: number;
  tone: T3Tone;
}

export interface T3StressDistribution {
  title: string;
  bars: T3StressBar[];
}

export interface T3StressTest {
  label: string;
  intro: string;
  distribution: T3StressDistribution;
  scenarios: T3StressScenarioRow[];
  note: string;
}
```

Then inside `AllWeatherData`, add the field immediately after the `caveats: { ... }` block (before `verdict`):

```typescript
  stressTest: T3StressTest;
```

- [ ] **Step 2: Add the FALLBACK instance**

In `frontend/src/lib/macro_research/dalio_copy/all_weather.ts`, add a `stressTest` key to `ALL_WEATHER_FALLBACK` immediately before the `verdict:` key:

```typescript
  stressTest: {
    label: "Section E — Monte-Carlo stress test",
    intro:
      "10,000-path 1-year Monte-Carlo simulation under baked reference parameters (long-run expected returns, volatilities, and cross-asset correlations). Stress regimes are parameter overlays, not a fat-tail model.",
    distribution: {
      title: "Base-case 1-year return distribution — 60/40 vs All-Weather reference",
      bars: [
        { label: "5th pct (VaR-95)", userPct: -0.18, refPct: -0.09 },
        { label: "25th pct", userPct: -0.04, refPct: -0.01 },
        { label: "Median", userPct: 0.06, refPct: 0.05 },
        { label: "75th pct", userPct: 0.17, refPct: 0.12 },
        { label: "95th pct", userPct: 0.31, refPct: 0.2 },
      ],
    },
    scenarios: [
      {
        name: "Base case",
        userMedianPct: 0.06,
        userP5Pct: -0.18,
        refMedianPct: 0.05,
        refP5Pct: -0.09,
        tone: "amber",
      },
      {
        name: "Stagflation",
        userMedianPct: -0.05,
        userP5Pct: -0.27,
        refMedianPct: -0.01,
        refP5Pct: -0.14,
        tone: "red",
      },
      {
        name: "Rate shock",
        userMedianPct: -0.03,
        userP5Pct: -0.24,
        refMedianPct: -0.04,
        refP5Pct: -0.17,
        tone: "red",
      },
      {
        name: "Equity crash / deleveraging",
        userMedianPct: -0.22,
        userP5Pct: -0.41,
        refMedianPct: -0.08,
        refP5Pct: -0.19,
        tone: "red",
      },
    ],
    note: "Reference assumptions; not investment advice. Gaussian draws — tails are conservative relative to historical crashes.",
  },
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (the FALLBACK now satisfies the extended `AllWeatherData`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/macro_research/dalio_copy/types.ts frontend/src/lib/macro_research/dalio_copy/all_weather.ts
git commit -m "feat(macro-research): stressTest types + fallback for All-Weather"
```

---

### Task 5: Engine tool + registry (multi-tool per slug) + prompt

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py` (import, new builder, registry shape)
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/registry.py:107-109` (consume list)
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py` (`_ALL_WEATHER_WORKFLOW`, `_ALL_WEATHER_PAYLOAD_SHAPE`)
- Test: `packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py` (add a tool-presence assertion)

- [ ] **Step 1: Write the failing test**

In `packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py`, add:

```python
def test_all_weather_exposes_both_classify_and_stress_tools() -> None:
    from openlia.llm.runtime.report_dash_mr.tools.dashboard_tools import (
        CLASSIFY_TOOL_BY_SLUG,
    )

    builders = CLASSIFY_TOOL_BY_SLUG["all_weather"]
    names = {b().descriptor.name for b in builders}
    assert names == {"classify_all_weather", "simulate_all_weather_stress"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py -q`
Expected: FAIL — `CLASSIFY_TOOL_BY_SLUG["all_weather"]` is currently a single callable, not an iterable of builders (`TypeError`/`AttributeError`).

- [ ] **Step 3a: Add the tool + change the registry shape**

In `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`:

Add the import (next to the other quant imports near the top):

```python
from openlia.macro_research.quant.monte_carlo import simulate_all_weather_stress
```

Add the builder immediately after `build_classify_all_weather_tool` (before `build_classify_five_forces_tool`):

```python
def build_simulate_all_weather_stress_tool() -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            raw = args["weights"]
            weights = {str(k): float(v) for k, v in raw.items()}
            out = simulate_all_weather_stress(weights)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ToolExecutionError(
                "simulate_all_weather_stress requires a `weights` object mapping "
                f"asset-class names to numeric portfolio weights. {exc}"
            ) from exc
        return ToolResult(
            payload={
                "distribution": {
                    "user": out.distribution.percentiles,
                    "reference": out.distribution.reference_percentiles,
                },
                "scenarios": [
                    {
                        "name": s.name,
                        "user_median": s.user.median,
                        "user_p5": s.user.p5,
                        "reference_median": s.reference.median,
                        "reference_p5": s.reference.p5,
                        "tone": s.tone,
                    }
                    for s in out.scenarios
                ],
            },
            provenance=ComputedSource(
                method="simulate_all_weather_stress", derived_from=["(weights)"]
            ),
            summary=f"{len(out.scenarios)} scenarios simulated",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="simulate_all_weather_stress",
            description=(
                "Deterministic Monte-Carlo stress simulation of the portfolio vs the "
                "Dalio reference allocation, from the portfolio's asset-class weights. "
                "Returns the Base-case 1-year return distribution (user/reference "
                "percentiles, as decimals) and per-scenario user/reference median and "
                "5th-percentile (VaR-95) returns plus a tone. Use the returned numbers "
                "verbatim to fill the stressTest section; do not invent them."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "weights": {
                        "type": "object",
                        "description": (
                            "Asset-class name to portfolio weight (e.g. "
                            '{"equities": 0.6, "long_bonds": 0.4}).'
                        ),
                        "additionalProperties": {"type": "number"},
                    },
                },
                "required": ["weights"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )
```

Change the registry (bottom of the file) to map each slug to a **list** of builders:

```python
# Per-slug deterministic tool builders. A slug present here gets each of its
# tools added to the catalog alongside emit_dashboard. New dashboards register
# their builder(s) here.
CLASSIFY_TOOL_BY_SLUG: dict[str, list[Callable[[], ResearchTool]]] = {
    "debt_cycle": [build_classify_debt_cycle_tool],
    "world_order": [build_classify_world_order_tool],
    "four_seasons": [build_classify_four_seasons_tool],
    "all_weather": [build_classify_all_weather_tool, build_simulate_all_weather_stress_tool],
    "five_forces": [build_classify_five_forces_tool],
}
```

- [ ] **Step 3b: Update the registry consumer**

In `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/registry.py`, replace lines 107-109:

```python
    classify_builder = CLASSIFY_TOOL_BY_SLUG.get(dashboard_slug)
    if classify_builder is not None:
        core.append(classify_builder())
```

with:

```python
    for classify_builder in CLASSIFY_TOOL_BY_SLUG.get(dashboard_slug, []):
        core.append(classify_builder())
```

- [ ] **Step 3c: Update the prompt**

In `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`, replace step 3 of `_ALL_WEATHER_WORKFLOW` (the "Gather current cross-asset volatilities ... NOT as a simulated distribution." paragraph) and renumber, so the block reads:

```python
_ALL_WEATHER_WORKFLOW = """\
Work in this order:
  1. Read the user's portfolio weights from the "# Provided inputs for this
     run" block. Those weights are authoritative ground truth — the system
     gathered them; do not invent or override them.
  2. Call `classify_all_weather` with those weights. Use the returned
     `risk_contributions`, `reference_risk_contributions`, `season_coverage`,
     `gold_gap`, and `severity` verbatim — do not invent or override the
     computed numbers.
  3. Call `simulate_all_weather_stress` with the same weights. Use the
     returned Base-case `distribution` percentiles and per-scenario
     `user_median`/`user_p5`/`reference_median`/`reference_p5`/`tone` verbatim
     to fill the `stressTest` section — do not invent or override the
     simulated numbers. You author only the prose `intro` and `note`.
  4. Gather current cross-asset volatilities and historical stress-episode
     context, then write the comparison donuts, the season-coverage cells,
     the risk-parity bars, the gold needle/stats, the caveats, and the
     verdict.
  5. Call `emit_dashboard` exactly once with the full AllWeatherData object
     in `payload`. This finalizes the run."""
```

In `_ALL_WEATHER_PAYLOAD_SHAPE`, add a bullet for `stressTest` immediately before the `caveats` bullet:

```python
  - `stressTest`: {label, intro, distribution: {title, bars: [{label, userPct,
    refPct}]}, scenarios: [{name, userMedianPct, userP5Pct, refMedianPct,
    refP5Pct, tone}], note} — `userPct`/`*Pct` are decimal returns (e.g. -0.12
    for -12%); fill every number from `simulate_all_weather_stress`'s output
    (the distribution `bars` from its `distribution`, the `scenarios` rows from
    its `scenarios`). You write only `label`, `intro`, and `note`.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py -q`
Expected: PASS (including the new tool-presence test and the existing `set(CLASSIFY_TOOL_BY_SLUG) <= set(PAYLOAD_MODEL_BY_SLUG)` test — keys are unchanged).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py packages/core/src/openlia/llm/runtime/report_dash_mr/tools/registry.py packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py
uv run ruff format packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py packages/core/src/openlia/llm/runtime/report_dash_mr/tools/registry.py packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py
git add packages/core/src/openlia/llm/runtime/report_dash_mr/ packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py
git commit -m "feat(macro-research): simulate_all_weather_stress tool + prompt wiring"
```

---

### Task 6: Engine-run test (verbatim numbers end-to-end)

**Files:**
- Test: `packages/core/tests/runtime/report_dash_mr/test_runner_all_weather.py`

- [ ] **Step 1: Extend the run test**

In `packages/core/tests/runtime/report_dash_mr/test_runner_all_weather.py`:

In `_complete_all_weather_payload()`, add a `stressTest` key immediately before `"verdict":`:

```python
        "stressTest": {
            "label": "Section E - Monte-Carlo stress test",
            "intro": "10,000-path 1-year simulation.",
            "distribution": {
                "title": "Base-case distribution",
                "bars": [
                    {"label": "5th pct", "userPct": -0.18, "refPct": -0.09},
                    {"label": "Median", "userPct": 0.06, "refPct": 0.05},
                ],
            },
            "scenarios": [
                {
                    "name": "Equity crash / deleveraging",
                    "userMedianPct": -0.22,
                    "userP5Pct": -0.41,
                    "refMedianPct": -0.08,
                    "refP5Pct": -0.19,
                    "tone": "red",
                }
            ],
            "note": "Gaussian draws.",
        },
```

Update the scripted turns in `test_runner_classify_then_emit_all_weather` to add the stress-tool call between classify and emit:

```python
    script = [
        script_tool_calls(
            (
                "classify_all_weather",
                {"weights": {"equities": 0.6, "long_bonds": 0.4}},
            )
        ),
        script_tool_calls(
            (
                "simulate_all_weather_stress",
                {"weights": {"equities": 0.6, "long_bonds": 0.4}},
            )
        ),
        script_tool_calls(("emit_dashboard", {"payload": payload})),
    ]
```

Add an assertion after the existing ones:

```python
    assert validated.stressTest.scenarios[0].tone == "red"
    assert validated.stressTest.distribution.bars[0].userPct == -0.18
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_runner_all_weather.py -q`
Expected: PASS (1 passed). The runner executes the real loop: classify → simulate → emit; the typed payload (now with `stressTest`) round-trips and validates.

- [ ] **Step 3: Commit**

```bash
git add packages/core/tests/runtime/report_dash_mr/test_runner_all_weather.py
git commit -m "test(macro-research): all_weather run exercises stress tool + stressTest payload"
```

---

### Task 7: Frontend Stress Test card (`AllWeatherView.tsx`)

**Files:**
- Modify: `frontend/src/pages/departments/macro_research/AllWeatherView.tsx`
- Test: `frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx` (AllWeatherView block, ~line 273-296)

- [ ] **Step 1: Write the failing test**

In `frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx`, in the `AllWeatherView` "renders live cache content" test (the `expect(screen.getByTestId(...))` block ~line 285-294), add:

```typescript
    expect(screen.getByTestId("t3-stress-test")).toBeInTheDocument();
```

(The shared `ALL_WEATHER_FALLBACK` mock already carries `stressTest` from Task 4, so no mock change is needed.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/departments/macro_research/__tests__/Views.test.tsx -t "AllWeatherView"`
Expected: FAIL — `Unable to find an element by: [data-testid="t3-stress-test"]`.

- [ ] **Step 3: Implement the card**

In `frontend/src/pages/departments/macro_research/AllWeatherView.tsx`:

Add `T3StressScenarioRow` and `T3StressBar` to the type import block (lines 4-15):

```typescript
  T3StressBar,
  T3StressScenarioRow,
```

Add a percentage formatter near `toneToStatus` (after line 45):

```typescript
function fmtPct(d: number): string {
  return `${d >= 0 ? "+" : ""}${(d * 100).toFixed(1)}%`;
}
```

Insert the Stress Test section in the returned JSX immediately after the `riskParity` card's closing `</div>` (after line 166, before the `gold` `<SectionLabel>` on line 168):

```tsx
      <SectionLabel>{data.stressTest.label}</SectionLabel>
      <div
        className="mr-card"
        data-testid="t3-stress-test"
        style={{ padding: "16px 18px", marginBottom: 14 }}
      >
        <p className="mr-card-body-text">{data.stressTest.intro}</p>
        <div className="mr-bar-section" style={{ marginTop: 8 }}>
          <div className="mr-bar-section-title">{data.stressTest.distribution.title}</div>
          {data.stressTest.distribution.bars.map((b: T3StressBar) => (
            <div key={b.label} className="mr-bar-row">
              <div className="mr-bar-label">{b.label}</div>
              <div className="mr-bar-val" style={{ minWidth: 120 }}>
                {fmtPct(b.userPct)} <span style={{ color: "var(--color-text-tertiary)" }}>vs</span>{" "}
                {fmtPct(b.refPct)}
              </div>
            </div>
          ))}
        </div>
        <table className="mr-stress-table" style={{ width: "100%", marginTop: 14 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Scenario</th>
              <th>Your median</th>
              <th>Your VaR-95</th>
              <th>Ref median</th>
              <th>Ref VaR-95</th>
            </tr>
          </thead>
          <tbody>
            {data.stressTest.scenarios.map((s: T3StressScenarioRow) => (
              <tr key={s.name} className={toneToStatus(s.tone)}>
                <td style={{ textAlign: "left" }}>{s.name}</td>
                <td>{fmtPct(s.userMedianPct)}</td>
                <td>{fmtPct(s.userP5Pct)}</td>
                <td>{fmtPct(s.refMedianPct)}</td>
                <td>{fmtPct(s.refP5Pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mr-card-body-text" style={{ marginTop: 10 }}>
          {data.stressTest.note}
        </p>
      </div>
```

- [ ] **Step 4: Run the test + tsc**

Run: `cd frontend && npx vitest run src/pages/departments/macro_research/__tests__/Views.test.tsx -t "AllWeatherView" && npx tsc --noEmit`
Expected: PASS; tsc no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/departments/macro_research/AllWeatherView.tsx frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx
git commit -m "feat(macro-research): All-Weather Stress Test card"
```

---

### Task 8: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Lint + format (whole packages)**

Run: `uv run ruff check packages/core packages/server && uv run ruff format --check packages/core packages/server`
Expected: `All checks passed!` and no files would reformat. Fix any findings (`ruff check --fix`, `ruff format`) and amend the relevant commit.

- [ ] **Step 2: Core test suite**

Run: `uv run pytest packages/core/tests/macro_research/ packages/core/tests/runtime/report_dash_mr/ -q`
Expected: all pass (the new `test_risk_math.py`, `test_monte_carlo.py`, the extended payload/runner/implemented-dashboards tests, and every pre-existing macro_research/report_dash_mr test).

- [ ] **Step 3: Frontend tests + build**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/pages/departments/macro_research/`
Expected: tsc clean; all macro_research view tests pass.

- [ ] **Step 4: Final commit (if any fixups)**

```bash
git add -A
git commit -m "chore(macro-research): lint/format fixups for All-Weather MC" || echo "nothing to commit"
```

---

## Notes for the implementer

- **Determinism is load-bearing.** The payload is cached in `mr_dashboard_cache`; the simulator must give byte-identical output for identical weights. The default seed is derived from the sorted, rounded weights. Never introduce wall-clock or unseeded randomness.
- **The model never invents the simulated numbers.** The tool returns them; the prompt says "verbatim." The model authors only the `label`/`intro`/`note` prose.
- **Percentages are decimals** in both the Python payload and `types.ts`; only the view multiplies by 100.
- **No server `mr_dash_run_service` change** — `_build_data_context` already supplies the user's portfolio weights for `all_weather`.
- If `npx vitest`/`tsc` is run from the repo root it will fail; run from `frontend/`.
