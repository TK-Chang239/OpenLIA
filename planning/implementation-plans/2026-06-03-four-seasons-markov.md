# Four Seasons Markov Transition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic Markov transition engine to the Four Seasons (T2) dashboard that, from the current economic season, reports the next-quarter transition-probability distribution plus derived stats, surfaced inside the existing `transitionRisk` section.

**Architecture:** A pure-function core (`macro_research/quant/markov.py`) reads a baked quarterly row-stochastic transition matrix over the 4 quadrant seasons. A new `report_dash_mr` tool (`markov_four_seasons`) classifies the current season from the same indicators, resolves a `"Transitioning"` read to its nearest quadrant, and computes the outlook; the prompt fills a new typed `transitionRisk.probabilities` block verbatim; the Four Seasons view renders it beside the existing bull/bear prose.

**Tech Stack:** Python 3.13, numpy, Pydantic v2, pytest; React/TypeScript/Vite, vitest. `uv` for Python, `npm` for frontend.

**Spec:** `planning/specs/systems/macro-research-heavy-quant-four-seasons-markov-design.md`

**Conventions:**
- Run Python via `uv run pytest ...` / `uv run ruff ...`. The uv cache (`~/.cache/uv`) is blocked under the default command sandbox; on "Failed to initialize cache ... Operation not permitted", re-run that exact command with the sandbox disabled.
- Markov is pure matrix arithmetic — **no RNG**, so output is byte-identical for identical inputs (the payload is cached).
- Probabilities in the payload are **decimals 0–1** (the view formats as %).
- Seasons (canonical order): `Spring, Summer, Autumn, Winter`. `"Transitioning"` is a classifier confidence label, not a Markov state.
- Run `npx tsc`/`npx vitest` from the `frontend/` directory (not the repo root).

---

### Task 1: Baked transition matrix + `resolve_quadrant`

**Files:**
- Create: `packages/core/src/openlia/macro_research/quant/markov.py`
- Test: `packages/core/tests/macro_research/test_markov.py` (create)

This task lands the baked data + the quadrant resolver. Task 2 adds `markov_outlook` to the same module.

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/macro_research/test_markov.py`:

```python
"""Baked Four Seasons transition matrix + quadrant resolver. Pure; no I/O, no LLM."""

from openlia.macro_research.quant.markov import (
    SEASON_ORDER,
    TRANSITION_MATRIX,
    resolve_quadrant,
)
from openlia.macro_research.quant.seasons import SeasonsInputs, classify_four_seasons


def test_season_order_is_the_four_quadrants() -> None:
    assert SEASON_ORDER == ("Spring", "Summer", "Autumn", "Winter")


def test_matrix_rows_are_stochastic() -> None:
    for season in SEASON_ORDER:
        row = TRANSITION_MATRIX[season]
        assert set(row) == set(SEASON_ORDER)
        assert all(p >= 0.0 for p in row.values())
        assert abs(sum(row.values()) - 1.0) < 1e-9


def test_resolve_quadrant_passes_through_canonical_seasons() -> None:
    spring = classify_four_seasons(
        SeasonsInputs(pmi=54.0, gdp_yoy=2.5, cpi_yoy=1.8, credit_spread=0.03)
    )
    assert spring.season == "Spring"
    assert resolve_quadrant(spring) == "Spring"

    autumn = classify_four_seasons(
        SeasonsInputs(pmi=47.0, gdp_yoy=0.2, cpi_yoy=4.0, credit_spread=0.06)
    )
    assert autumn.season == "Autumn"
    assert resolve_quadrant(autumn) == "Autumn"


def test_resolve_quadrant_maps_transitioning_via_marker() -> None:
    # Mixed signals -> classifier returns "Transitioning"; resolver picks the
    # nearest quadrant from the marker coordinates (growth x>=50, inflation y>=50).
    c = classify_four_seasons(
        SeasonsInputs(pmi=48.0, gdp_yoy=1.5, cpi_yoy=2.5, credit_spread=0.04)
    )
    assert c.season == "Transitioning"
    # pmi 48 -> x = (48-45)*10 = 30 (<50, growth falling); cpi 2.5 -> y = (2.5-1)*25 = 37.5 (<50, inflation falling) -> Winter
    assert resolve_quadrant(c) == "Winter"


def test_resolve_quadrant_each_marker_corner() -> None:
    from openlia.macro_research.quant.seasons import SeasonsClassification

    def _stub(x: int, y: int) -> SeasonsClassification:
        return SeasonsClassification(
            season="Transitioning",
            severity="amber",
            confidence="transitioning",
            growth_axis="flat",
            inflation_axis="steady",
            marker_x_pct=x,
            marker_y_pct=y,
        )

    assert resolve_quadrant(_stub(80, 20)) == "Spring"   # growth rising, inflation falling
    assert resolve_quadrant(_stub(80, 80)) == "Summer"   # growth rising, inflation rising
    assert resolve_quadrant(_stub(20, 80)) == "Autumn"   # growth falling, inflation rising
    assert resolve_quadrant(_stub(20, 20)) == "Winter"   # growth falling, inflation falling
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_markov.py -q`
Expected: FAIL with `ModuleNotFoundError: openlia.macro_research.quant.markov`.

- [ ] **Step 3: Implement**

Create `packages/core/src/openlia/macro_research/quant/markov.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_markov.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
uv run ruff format packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
git add packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
git commit -m "feat(macro-research): baked Four Seasons transition matrix + quadrant resolver"
```

---

### Task 2: `markov_outlook`

**Files:**
- Modify: `packages/core/src/openlia/macro_research/quant/markov.py`
- Test: `packages/core/tests/macro_research/test_markov.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/core/tests/macro_research/test_markov.py`:

```python
from openlia.macro_research.quant.markov import markov_outlook  # noqa: E402


def test_outlook_distribution_is_the_matrix_row() -> None:
    out = markov_outlook("Summer")
    assert out.current_season == "Summer"
    assert out.distribution == {
        "Spring": 0.08,
        "Summer": 0.60,
        "Autumn": 0.27,
        "Winter": 0.05,
    }
    assert abs(sum(out.distribution.values()) - 1.0) < 1e-9


def test_outlook_persistence_is_diagonal() -> None:
    out = markov_outlook("Autumn")
    assert out.persistence == 0.57


def test_outlook_most_likely_next_and_adverse() -> None:
    out = markov_outlook("Summer")
    assert out.most_likely_next == "Summer"  # persistence dominates
    assert out.adverse_season == "Autumn"
    assert out.adverse_prob == 0.27


def test_outlook_expected_dwell() -> None:
    out = markov_outlook("Spring")  # persistence 0.60
    assert abs(out.expected_dwell_quarters - 2.5) < 1e-9


def test_outlook_horizon_is_matrix_power_and_stochastic() -> None:
    out = markov_outlook("Spring", steps=4)
    assert out.horizon_quarters == 4
    assert abs(sum(out.horizon_distribution.values()) - 1.0) < 1e-9
    # 1-step distribution is more concentrated on the current season than the
    # 4-step distribution (the chain mixes toward its stationary spread).
    assert out.horizon_distribution["Spring"] < out.distribution["Spring"]


def test_outlook_unknown_season_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="unknown season"):
        markov_outlook("Monsoon")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_markov.py -q`
Expected: FAIL with `ImportError: cannot import name 'markov_outlook'`.

- [ ] **Step 3: Implement**

Append to `packages/core/src/openlia/macro_research/quant/markov.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_markov.py -q`
Expected: PASS (11 passed total).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
uv run ruff format packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
git add packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
git commit -m "feat(macro-research): markov_outlook (distribution, persistence, dwell, horizon)"
```

---

### Task 3: `probabilities` payload models (`payloads.py`)

**Files:**
- Modify: `packages/core/src/openlia/macro_research/payloads.py` (insert before `class T2TransitionRisk`, ~line 369; add field to `T2TransitionRisk`)
- Test: `packages/core/tests/macro_research/test_payloads_four_seasons.py`

- [ ] **Step 1: Write the failing test**

In `packages/core/tests/macro_research/test_payloads_four_seasons.py`, add a `probabilities` block to the `"transitionRisk"` dict in `_four_seasons_fixture()` (insert immediately after the `"keyIndicator": {...}` block, inside `transitionRisk`):

```python
            "probabilities": {
                "currentSeason": "Summer",
                "nextQuarter": [
                    {"season": "Spring", "prob": 0.08},
                    {"season": "Summer", "prob": 0.60},
                    {"season": "Autumn", "prob": 0.27},
                    {"season": "Winter", "prob": 0.05},
                ],
                "persistence": 0.60,
                "mostLikelyNext": "Summer",
                "adverseSeason": "Autumn",
                "adverseProb": 0.27,
                "expectedDwellQuarters": 2.5,
                "horizonQuarters": 4,
                "horizon": [
                    {"season": "Spring", "prob": 0.18},
                    {"season": "Summer", "prob": 0.30},
                    {"season": "Autumn", "prob": 0.27},
                    {"season": "Winter", "prob": 0.25},
                ],
            },
```

Then add a test function at the end of the file:

```python
def test_four_seasons_transition_probabilities_validates() -> None:
    data = FourSeasonsData.model_validate(_four_seasons_fixture())
    probs = data.transitionRisk.probabilities
    assert probs.currentSeason == "Summer"
    assert probs.persistence == 0.60
    assert probs.adverseSeason == "Autumn"
    assert probs.adverseProb == 0.27
    assert probs.nextQuarter[1].season == "Summer"
    assert probs.nextQuarter[1].prob == 0.60
    assert probs.horizonQuarters == 4
    assert len(probs.horizon) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_payloads_four_seasons.py -q`
Expected: FAIL — `test_four_seasons_transition_probabilities_validates` fails with `AttributeError: 'T2TransitionRisk' object has no attribute 'probabilities'` (Pydantic ignores the unknown fixture key until the field exists).

- [ ] **Step 3: Implement**

In `packages/core/src/openlia/macro_research/payloads.py`, insert these models immediately before `class T2TransitionRisk(BaseModel):`:

```python
class T2TransitionProb(BaseModel):
    season: str
    prob: float


class T2TransitionProbabilities(BaseModel):
    currentSeason: str
    nextQuarter: list[T2TransitionProb]
    persistence: float
    mostLikelyNext: str
    adverseSeason: str
    adverseProb: float
    expectedDwellQuarters: float
    horizonQuarters: int
    horizon: list[T2TransitionProb]
```

Then add the field to `T2TransitionRisk` (immediately after `keyIndicator: T2KeyIndicator`):

```python
    probabilities: T2TransitionProbabilities
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_payloads_four_seasons.py -q`
Expected: PASS (all, including the new test).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_four_seasons.py
uv run ruff format packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_four_seasons.py
git add packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_four_seasons.py
git commit -m "feat(macro-research): transition-probabilities payload models on T2TransitionRisk"
```

---

### Task 4: Frontend types + FALLBACK (`types.ts`, `four_seasons.ts`)

**Files:**
- Modify: `frontend/src/lib/macro_research/dalio_copy/types.ts`
- Modify: `frontend/src/lib/macro_research/dalio_copy/four_seasons.ts`

- [ ] **Step 1: Add the interfaces**

In `frontend/src/lib/macro_research/dalio_copy/types.ts`, immediately before `export interface FourSeasonsData {` (line 213), add:

```typescript
export interface T2TransitionProb {
  season: string;
  prob: number;
}

export interface T2TransitionProbabilities {
  currentSeason: string;
  nextQuarter: T2TransitionProb[];
  persistence: number;
  mostLikelyNext: string;
  adverseSeason: string;
  adverseProb: number;
  expectedDwellQuarters: number;
  horizonQuarters: number;
  horizon: T2TransitionProb[];
}
```

Then inside `FourSeasonsData`, add the field to the inline `transitionRisk` object (immediately after the `keyIndicator: { title: string; body: string };` line):

```typescript
    probabilities: T2TransitionProbabilities;
```

- [ ] **Step 2: Add the FALLBACK instance**

In `frontend/src/lib/macro_research/dalio_copy/four_seasons.ts`, add a `probabilities` key to the `transitionRisk` object in `FOUR_SEASONS_FALLBACK`, immediately after the `keyIndicator: { ... }` block:

```typescript
    probabilities: {
      currentSeason: "Summer",
      nextQuarter: [
        { season: "Spring", prob: 0.08 },
        { season: "Summer", prob: 0.6 },
        { season: "Autumn", prob: 0.27 },
        { season: "Winter", prob: 0.05 },
      ],
      persistence: 0.6,
      mostLikelyNext: "Summer",
      adverseSeason: "Autumn",
      adverseProb: 0.27,
      expectedDwellQuarters: 2.5,
      horizonQuarters: 4,
      horizon: [
        { season: "Spring", prob: 0.18 },
        { season: "Summer", prob: 0.3 },
        { season: "Autumn", prob: 0.27 },
        { season: "Winter", prob: 0.25 },
      ],
    },
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/macro_research/dalio_copy/types.ts frontend/src/lib/macro_research/dalio_copy/four_seasons.ts
git commit -m "feat(macro-research): transition-probabilities types + fallback for Four Seasons"
```

---

### Task 5: Engine tool + registry + prompt

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`
- Test: `packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py`

- [ ] **Step 1: Write the failing test**

In `packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py`, add:

```python
def test_four_seasons_exposes_both_classify_and_markov_tools() -> None:
    from openlia.llm.runtime.report_dash_mr.tools.dashboard_tools import (
        CLASSIFY_TOOL_BY_SLUG,
    )

    builders = CLASSIFY_TOOL_BY_SLUG["four_seasons"]
    names = {b().descriptor.name for b in builders}
    assert names == {"classify_four_seasons", "markov_four_seasons"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py -q`
Expected: FAIL — `four_seasons` currently maps to a single-element list, so the name set is `{"classify_four_seasons"}`.

- [ ] **Step 3a: Add the tool + register it**

In `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`:

Add the import next to the other quant imports near the top:

```python
from openlia.macro_research.quant.markov import markov_outlook, resolve_quadrant
```

Add the builder immediately after `build_classify_four_seasons_tool` (before `build_classify_all_weather_tool`):

```python
def build_markov_four_seasons_tool() -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            classification = classify_four_seasons(
                SeasonsInputs(
                    pmi=float(args["pmi"]),
                    gdp_yoy=float(args["gdp_yoy"]),
                    cpi_yoy=float(args["cpi_yoy"]),
                    credit_spread=float(args["credit_spread"]),
                )
            )
            out = markov_outlook(resolve_quadrant(classification))
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolExecutionError(
                "markov_four_seasons requires numeric pmi, gdp_yoy, cpi_yoy, "
                f"credit_spread. {exc}"
            ) from exc
        return ToolResult(
            payload={
                "current_season": out.current_season,
                "next_quarter": out.distribution,
                "persistence": out.persistence,
                "most_likely_next": out.most_likely_next,
                "adverse_season": out.adverse_season,
                "adverse_prob": out.adverse_prob,
                "expected_dwell_quarters": out.expected_dwell_quarters,
                "horizon_quarters": out.horizon_quarters,
                "horizon": out.horizon_distribution,
            },
            provenance=ComputedSource(method="markov_four_seasons", derived_from=["(inputs)"]),
            summary=(
                f"current={out.current_season} P(stay)={out.persistence:.2f} "
                f"P(Autumn)={out.adverse_prob:.2f}"
            ),
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="markov_four_seasons",
            description=(
                "Deterministic Markov transition outlook for the four-seasons regime, from "
                "the same four indicators as classify_four_seasons. Returns the current "
                "season, the next-quarter transition-probability distribution "
                "(`next_quarter`, season->decimal probability), `persistence` (P stay), "
                "`most_likely_next`, `adverse_season`/`adverse_prob` (P of moving to Autumn), "
                "`expected_dwell_quarters`, and the `horizon_quarters`-ahead distribution "
                "(`horizon`). Use the returned numbers verbatim to fill "
                "transitionRisk.probabilities."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pmi": {
                        "type": "number",
                        "description": "Manufacturing PMI (ISM / S&P Global) level",
                    },
                    "gdp_yoy": {
                        "type": "number",
                        "description": "Real GDP growth, percent year-over-year",
                    },
                    "cpi_yoy": {
                        "type": "number",
                        "description": "Headline CPI, percent year-over-year",
                    },
                    "credit_spread": {
                        "type": "number",
                        "description": "IG vs HY credit-spread proxy (decimal, e.g. 0.04)",
                    },
                },
                "required": ["pmi", "gdp_yoy", "cpi_yoy", "credit_spread"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )
```

Update the `four_seasons` entry in `CLASSIFY_TOOL_BY_SLUG` to list both builders:

```python
    "four_seasons": [build_classify_four_seasons_tool, build_markov_four_seasons_tool],
```

(The registry is already `dict[str, list[Callable[[], ResearchTool]]]` from the All-Weather work; only the `four_seasons` value changes from a single-element list to two.)

- [ ] **Step 3b: Update the prompt**

In `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`, replace step 3 of `_FOUR_SEASONS_WORKFLOW` (the "Write the scorecard trend reads ..." step) and renumber so the block reads:

```python
_FOUR_SEASONS_WORKFLOW = """\
Work in this order:
  1. Gather the four-seasons indicators, each with a value and an as-of
     date:
       - Manufacturing PMI (ISM / S&P Global)
       - Real GDP growth, percent year-over-year
       - Headline and core CPI, percent year-over-year
       - An investment-grade vs high-yield credit-spread proxy
     Prefer the enabled connector tools first; fall back to `web_search`
     of official sources (ISM, S&P Global, BEA, BLS, FRED).
  2. Call `classify_four_seasons` with those values. Use the returned
     `season`, `severity`, `confidence`, `growth_axis`, `inflation_axis`,
     `marker_x_pct`, `marker_y_pct`, `best_assets`, and `worst_assets`
     verbatim — do not invent or override the computed season. Place the
     quadrant `now` marker at `marker_x_pct`/`marker_y_pct`.
  3. Call `markov_four_seasons` with the same four indicators. Fill
     `transitionRisk.probabilities` from its output, mapping the (decimal)
     numbers exactly — do not invent or override them: `current_season`->
     `currentSeason`, `persistence`->`persistence`, `most_likely_next`->
     `mostLikelyNext`, `adverse_season`->`adverseSeason`, `adverse_prob`->
     `adverseProb`, `expected_dwell_quarters`->`expectedDwellQuarters`,
     `horizon_quarters`->`horizonQuarters`. Turn the returned `next_quarter`
     and `horizon` dicts (season->probability) into the `nextQuarter` and
     `horizon` arrays, one `{season, prob}` object per season.
  4. Write the scorecard trend reads, the parallels, the transition-risk
     bull/bear/keyIndicator prose (now grounded by those probabilities), the
     asset playbook, and the synthesis verdict from the cited data you
     gathered.
  5. Call `emit_dashboard` exactly once with the full FourSeasonsData
     object in `payload`. This finalizes the run."""
```

In `_FOUR_SEASONS_PAYLOAD_SHAPE`, replace the `transitionRisk` bullet with:

```python
  - `transitionRisk`: {intro, bull: {title, body}, bear: {title, body},
    keyIndicator: {title, body}, probabilities: {currentSeason, nextQuarter:
    [{season, prob}], persistence, mostLikelyNext, adverseSeason, adverseProb,
    expectedDwellQuarters, horizonQuarters, horizon: [{season, prob}]}} — every
    `prob`/`persistence`/`adverseProb` is a decimal 0-1. Fill `probabilities`
    entirely from `markov_four_seasons` (you write only the intro/bull/bear/
    keyIndicator prose).
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py -q`
Expected: PASS (including the new tool-presence test and the existing `set(CLASSIFY_TOOL_BY_SLUG) <= set(PAYLOAD_MODEL_BY_SLUG)` test — keys unchanged).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py
uv run ruff format packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py
git add packages/core/src/openlia/llm/runtime/report_dash_mr/ packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py
git commit -m "feat(macro-research): markov_four_seasons tool + prompt wiring"
```

---

### Task 6: Engine-run test (verbatim numbers end-to-end)

**Files:**
- Test: `packages/core/tests/runtime/report_dash_mr/test_runner_four_seasons.py`

Task 3 made `probabilities` required on `T2TransitionRisk`, and Task 5 registered the `markov_four_seasons` tool — so this runner test is RED until updated here (the payload lacks `probabilities` and the script lacks the markov turn). This task makes it green.

- [ ] **Step 1: Extend the run test**

In `packages/core/tests/runtime/report_dash_mr/test_runner_four_seasons.py`:

In `_complete_four_seasons_payload()`, add a `probabilities` key to the `"transitionRisk"` dict, immediately after its `"keyIndicator": {...}` block:

```python
            "probabilities": {
                "currentSeason": "Autumn",
                "nextQuarter": [
                    {"season": "Spring", "prob": 0.05},
                    {"season": "Summer", "prob": 0.08},
                    {"season": "Autumn", "prob": 0.57},
                    {"season": "Winter", "prob": 0.30},
                ],
                "persistence": 0.57,
                "mostLikelyNext": "Autumn",
                "adverseSeason": "Autumn",
                "adverseProb": 0.57,
                "expectedDwellQuarters": 2.33,
                "horizonQuarters": 4,
                "horizon": [
                    {"season": "Spring", "prob": 0.20},
                    {"season": "Summer", "prob": 0.18},
                    {"season": "Autumn", "prob": 0.32},
                    {"season": "Winter", "prob": 0.30},
                ],
            },
```

Update the scripted turns in `test_runner_classify_then_emit_four_seasons` to add the markov tool call between classify and emit:

```python
    script = [
        script_tool_calls(
            (
                "classify_four_seasons",
                {
                    "pmi": 47.0,
                    "gdp_yoy": 0.2,
                    "cpi_yoy": 4.0,
                    "credit_spread": 0.04,
                },
            )
        ),
        script_tool_calls(
            (
                "markov_four_seasons",
                {
                    "pmi": 47.0,
                    "gdp_yoy": 0.2,
                    "cpi_yoy": 4.0,
                    "credit_spread": 0.04,
                },
            )
        ),
        script_tool_calls(("emit_dashboard", {"payload": payload})),
    ]
```

After the existing assertions in that test (the ones validating the emitted `FourSeasonsData`), add:

```python
    assert validated.transitionRisk.probabilities.currentSeason == "Autumn"
    assert validated.transitionRisk.probabilities.adverseProb == 0.57
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_runner_four_seasons.py -q`
Expected: PASS (1 passed). The runner executes the real loop classify → markov → emit; the typed payload (now with `transitionRisk.probabilities`) round-trips and validates.

- [ ] **Step 3: Commit**

```bash
git add packages/core/tests/runtime/report_dash_mr/test_runner_four_seasons.py
git commit -m "test(macro-research): four_seasons run exercises markov tool + probabilities payload"
```

---

### Task 7: Frontend transition-probabilities sub-card (`FourSeasonsView.tsx`)

**Files:**
- Modify: `frontend/src/pages/departments/macro_research/FourSeasonsView.tsx`
- Test: `frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx` (FourSeasonsView block)

- [ ] **Step 1: Write the failing test**

In `Views.test.tsx`, in the FourSeasonsView "renders live cache content" test (the block asserting `t2-transition-risk` etc.), add:

```typescript
    expect(screen.getByTestId("t2-transition-probabilities")).toBeInTheDocument();
```

(The shared `FOUR_SEASONS_FALLBACK` already carries `transitionRisk.probabilities` from Task 4, so no mock change is needed.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/departments/macro_research/__tests__/Views.test.tsx -t "FourSeasonsView"`
Expected: FAIL — `Unable to find an element by: [data-testid="t2-transition-probabilities"]`.

- [ ] **Step 3: Implement the sub-card**

In `frontend/src/pages/departments/macro_research/FourSeasonsView.tsx`:

Add `T2TransitionProb` to the type import block (alongside the other `T2*` type imports near the top of the file):

```typescript
  T2TransitionProb,
```

Add a percentage formatter near the top of the component module (after the existing imports, at module scope):

```typescript
function fmtProb(p: number): string {
  return `${(p * 100).toFixed(0)}%`;
}
```

Insert the probabilities sub-card inside the existing `t2-transition-risk` card, immediately after the `<ScenarioDuo .../>` element (line ~210) and before the `keyIndicator` `<div className="mr-card-sm" ...>`:

```tsx
        <div
          className="mr-card-sm"
          data-testid="t2-transition-probabilities"
          style={{ marginTop: 14 }}
        >
          <div className="mr-card-title">
            Regime transition probabilities (from {data.transitionRisk.probabilities.currentSeason})
          </div>
          <div className="mr-bar-section" style={{ marginTop: 8 }}>
            <div className="mr-bar-section-title">Next quarter</div>
            {data.transitionRisk.probabilities.nextQuarter.map((p: T2TransitionProb) => (
              <div key={p.season} className="mr-bar-row">
                <div className="mr-bar-label">{p.season}</div>
                <div className="mr-bar-track">
                  <div className="mr-bar-fill mr-fill-ok" style={{ width: `${p.prob * 100}%` }} />
                </div>
                <div className="mr-bar-val">{fmtProb(p.prob)}</div>
              </div>
            ))}
          </div>
          <div className="mr-grid3" style={{ marginTop: 12 }}>
            <div>
              <div className="mr-card-title">Persistence</div>
              <div className="mr-card-body-text">
                {fmtProb(data.transitionRisk.probabilities.persistence)} stay in{" "}
                {data.transitionRisk.probabilities.currentSeason} · ~
                {data.transitionRisk.probabilities.expectedDwellQuarters.toFixed(1)}q dwell
              </div>
            </div>
            <div>
              <div className="mr-card-title">Most likely next</div>
              <div className="mr-card-body-text">
                {data.transitionRisk.probabilities.mostLikelyNext}
              </div>
            </div>
            <div>
              <div className="mr-card-title">
                P(&rarr; {data.transitionRisk.probabilities.adverseSeason})
              </div>
              <div className="mr-card-body-text">
                {fmtProb(data.transitionRisk.probabilities.adverseProb)} next quarter
              </div>
            </div>
          </div>
          <div className="mr-bar-section" style={{ marginTop: 12 }}>
            <div className="mr-bar-section-title">
              {data.transitionRisk.probabilities.horizonQuarters} quarters ahead
            </div>
            {data.transitionRisk.probabilities.horizon.map((p: T2TransitionProb) => (
              <div key={p.season} className="mr-bar-row">
                <div className="mr-bar-label">{p.season}</div>
                <div className="mr-bar-track">
                  <div className="mr-bar-fill mr-fill-ok" style={{ width: `${p.prob * 100}%` }} />
                </div>
                <div className="mr-bar-val">{fmtProb(p.prob)}</div>
              </div>
            ))}
          </div>
        </div>
```

- [ ] **Step 4: Run the test + tsc**

Run: `cd frontend && npx vitest run src/pages/departments/macro_research/__tests__/Views.test.tsx -t "FourSeasonsView" && npx tsc --noEmit`
Expected: PASS; tsc no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/departments/macro_research/FourSeasonsView.tsx frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx
git commit -m "feat(macro-research): Four Seasons transition-probabilities sub-card"
```

---

### Task 8: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Lint + format (whole packages)**

Run: `uv run ruff check packages/core packages/server && uv run ruff format --check packages/core packages/server`
Expected: `All checks passed!` and no files would reformat. Fix any findings and amend the relevant commit.

- [ ] **Step 2: Core test suite**

Run: `uv run pytest packages/core/tests/macro_research/ packages/core/tests/runtime/report_dash_mr/ -q`
Expected: all pass (the new `test_markov.py`, the extended payload/runner/implemented-dashboards tests, and every pre-existing macro_research/report_dash_mr test).

- [ ] **Step 3: Frontend tests + build**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/pages/departments/macro_research/`
Expected: tsc clean; all macro_research view tests pass.

- [ ] **Step 4: Final commit (if any fixups)**

```bash
git add -A
git commit -m "chore(macro-research): lint/format fixups for Four Seasons Markov" || echo "nothing to commit"
```

---

## Notes for the implementer

- **Determinism:** the engine is pure matrix arithmetic — no RNG, no wall-clock. Identical inputs always yield identical output; the payload is cached in `mr_dashboard_cache`.
- **The model never invents the probabilities.** The tool returns them; the prompt maps the snake_case tool keys to the camelCase payload keys explicitly (`current_season`->`currentSeason`, etc.) and turns the `next_quarter`/`horizon` season->prob dicts into `{season, prob}` arrays. The model authors only the intro/bull/bear/keyIndicator prose.
- **`"Transitioning"` is not a Markov state** — `resolve_quadrant` maps it to the nearest quadrant from the marker coordinates, so the tool always feeds `markov_outlook` a canonical season.
- **No server `mr_dash_run_service` change** — Four Seasons gathers its own indicators; nothing is injected.
- If `npx vitest`/`tsc` is run from the repo root it will fail; run from `frontend/`.
