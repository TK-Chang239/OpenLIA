# Five Forces Influence Network (VAR-style) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic influence-network engine to the Five Forces (T5) dashboard that, from the five current force scores, computes the active causal edges + a VAR(1)-style projected next-period intensity per force + amplifier/absorber roles + an aggregate contagion read, surfaced inside the existing `loops` section.

**Architecture:** A pure-function core (`macro_research/quant/forces_network.py`) holds a baked directed 5x5 structural influence matrix (Dalio's documented force linkages, explicitly NOT fitted from data) and applies it to the current score vector as a bounded one-step linear map. A new `report_dash_mr` tool (`analyze_five_forces_network`) computes it; the prompt fills a new typed `loops.network` block verbatim; the Five Forces view renders it beside the existing loop blocks.

**Tech Stack:** Python 3.13, Pydantic v2, pytest (pure-Python engine — no numpy needed); React/TypeScript/Vite, vitest. `uv` for Python, `npm` for frontend.

**Spec:** `planning/specs/systems/macro-research-heavy-quant-five-forces-network-design.md`

**Conventions:**
- Run Python via `uv run pytest ...` / `uv run ruff ...`. The uv cache (`~/.cache/uv`) is blocked under the default command sandbox; on "Failed to initialize cache ... Operation not permitted", re-run that exact command with the sandbox disabled.
- The engine is pure deterministic arithmetic — **no RNG** — so output is byte-identical for identical inputs (the payload is cached).
- Edge strengths and contagion are **decimals 0–1**; force intensities are **0–10** (the scorecard scale).
- Forces (canonical order): `debt_money, political, geopolitical, technology, natural`.
- Run `npx tsc`/`npx vitest` from the `frontend/` directory (not the repo root).

---

### Task 1: Baked influence matrix + constants

**Files:**
- Create: `packages/core/src/openlia/macro_research/quant/forces_network.py`
- Test: `packages/core/tests/macro_research/test_forces_network.py` (create)

This task lands the baked data + accessors. Task 2 adds `analyze_force_network` to the same module.

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/macro_research/test_forces_network.py`:

```python
"""Baked Five Forces influence matrix + accessors. Pure; no I/O, no LLM, no RNG."""

from openlia.macro_research.quant.forces_network import (
    FORCE_LABELS,
    FORCE_ORDER,
    INFLUENCE,
    PERSISTENCE,
    coupling,
)


def test_force_order_is_the_five_forces() -> None:
    assert FORCE_ORDER == (
        "debt_money",
        "political",
        "geopolitical",
        "technology",
        "natural",
    )


def test_every_force_has_a_label() -> None:
    assert set(FORCE_LABELS) == set(FORCE_ORDER)


def test_influence_entries_in_range_and_zero_diagonal() -> None:
    for driver in FORCE_ORDER:
        for driven in FORCE_ORDER:
            c = coupling(driver, driven)
            assert 0.0 <= c <= 1.0
            if driver == driven:
                assert c == 0.0


def test_coupling_reads_the_matrix_and_defaults_zero() -> None:
    assert coupling("debt_money", "political") == 0.6
    # An unspecified pair defaults to 0.0.
    assert coupling("technology", "natural") == 0.0


def test_persistence_is_a_fraction() -> None:
    assert 0.0 < PERSISTENCE < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_forces_network.py -q`
Expected: FAIL with `ModuleNotFoundError: openlia.macro_research.quant.forces_network`.

- [ ] **Step 3: Implement**

Create `packages/core/src/openlia/macro_research/quant/forces_network.py`:

```python
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
ACTIVE_THRESHOLD = 7.0

# Each force partly persists period-over-period.
PERSISTENCE = 0.7

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_forces_network.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/quant/forces_network.py packages/core/tests/macro_research/test_forces_network.py
uv run ruff format packages/core/src/openlia/macro_research/quant/forces_network.py packages/core/tests/macro_research/test_forces_network.py
git add packages/core/src/openlia/macro_research/quant/forces_network.py packages/core/tests/macro_research/test_forces_network.py
git commit -m "feat(macro-research): baked Five Forces influence matrix + coupling accessor"
```

---

### Task 2: `analyze_force_network`

**Files:**
- Modify: `packages/core/src/openlia/macro_research/quant/forces_network.py`
- Test: `packages/core/tests/macro_research/test_forces_network.py`

- [ ] **Step 1: Write the failing test**

First, extend the **top-of-file imports** in `packages/core/tests/macro_research/test_forces_network.py` (do NOT add a mid-file import): add `analyze_force_network` to the existing `forces_network` import block (alphabetically), and add a `ForceScores` import. The import block becomes:

```python
from openlia.macro_research.quant.forces import ForceScores
from openlia.macro_research.quant.forces_network import (
    FORCE_LABELS,
    FORCE_ORDER,
    INFLUENCE,
    PERSISTENCE,
    analyze_force_network,
    coupling,
)
```

Then append the new test functions to the file:

```python
_LOW = ForceScores(debt_money=3, political=3, geopolitical=3, technology=3, natural=3)


def test_all_low_has_no_active_edges_and_is_contained() -> None:
    out = analyze_force_network(_LOW)
    assert out.edges == ()
    assert out.contagion == 0.0
    assert out.contagion_label == "Contained"
    # Projections are always present, one per force.
    assert len(out.projections) == 5


def test_intense_driver_activates_its_outgoing_edges_ranked() -> None:
    # Only debt_money is intense (>=7); its two outgoing edges activate.
    scores = ForceScores(debt_money=8, political=3, geopolitical=3, technology=3, natural=3)
    out = analyze_force_network(scores)
    pairs = [(e.from_label, e.to_label, round(e.strength, 3)) for e in out.edges]
    assert pairs == [
        ("Debt / money", "Internal politics", 0.48),   # 0.6 * 0.8
        ("Debt / money", "Geopolitical", 0.32),         # 0.4 * 0.8
    ]
    # Ranked descending by strength.
    assert out.edges[0].strength >= out.edges[1].strength


def test_projection_is_clamped_and_pulled_up_by_intense_driver() -> None:
    scores = ForceScores(debt_money=8, political=3, geopolitical=3, technology=3, natural=3)
    out = analyze_force_network(scores)
    by_force = {p.force: p for p in out.projections}
    pol = by_force["Internal politics"]
    assert 0.0 <= pol.projected <= 10.0
    # Intense debt_money drives politics up next period.
    assert pol.delta > 0.0
    assert pol.projected > pol.current


def test_amplifier_and_absorber_labels() -> None:
    # debt_money is the strongest driver (out-couplings 0.6+0.4); when it is the
    # only intense force it is the amplifier. Internal politics has the largest
    # incoming coupling, so it is the absorber.
    scores = ForceScores(debt_money=9, political=2, geopolitical=2, technology=2, natural=2)
    out = analyze_force_network(scores)
    assert out.amplifier == "Debt / money"
    assert out.absorber == "Internal politics"


def test_contagion_buckets() -> None:
    # Only debt_money maxed: two edges (0.6, 0.4), mean 0.5 -> Self-reinforcing.
    hot = ForceScores(debt_money=10, political=0, geopolitical=0, technology=0, natural=0)
    out_hot = analyze_force_network(hot)
    assert out_hot.contagion == 0.5
    assert out_hot.contagion_label == "Self-reinforcing"
    # Everything maxed: many edges dilute the mean into the Spreading band.
    allmax = ForceScores(debt_money=10, political=10, geopolitical=10, technology=10, natural=10)
    out_all = analyze_force_network(allmax)
    assert 0.25 <= out_all.contagion < 0.5
    assert out_all.contagion_label == "Spreading"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_forces_network.py -q`
Expected: FAIL with `ImportError: cannot import name 'analyze_force_network'`.

- [ ] **Step 3: Implement**

Append to `packages/core/src/openlia/macro_research/quant/forces_network.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_forces_network.py -q`
Expected: PASS (10 passed total).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/quant/forces_network.py packages/core/tests/macro_research/test_forces_network.py
uv run ruff format packages/core/src/openlia/macro_research/quant/forces_network.py packages/core/tests/macro_research/test_forces_network.py
git add packages/core/src/openlia/macro_research/quant/forces_network.py packages/core/tests/macro_research/test_forces_network.py
git commit -m "feat(macro-research): analyze_force_network (edges, projections, roles, contagion)"
```

---

### Task 3: `network` payload models (`payloads.py`) + snapshot-fixture fix

**Files:**
- Modify: `packages/core/src/openlia/macro_research/payloads.py` (insert before `class T5Loops`, ~line 625; add field to `T5Loops`)
- Test: `packages/core/tests/macro_research/test_payloads_five_forces.py`
- Test: `packages/core/tests/macro_research/test_snapshot.py` (its `_five_forces` builder constructs a `FiveForcesData` directly, so making `network` required breaks it — fix it here)

- [ ] **Step 1: Write the failing test**

In `packages/core/tests/macro_research/test_payloads_five_forces.py`, add a `network` block to the `"loops"` dict in `_five_forces_fixture()` (immediately after the `"active": {...}` block, inside `loops`):

```python
            "network": {
                "label": "Influence network (current)",
                "edges": [
                    {"fromLabel": "Debt / money", "toLabel": "Internal politics", "strength": 0.54},
                    {"fromLabel": "Geopolitical", "toLabel": "Debt / money", "strength": 0.45},
                ],
                "projections": [
                    {"force": "Debt / money", "current": 9.0, "projected": 8.6, "delta": -0.4},
                    {"force": "Internal politics", "current": 8.0, "projected": 8.3, "delta": 0.3},
                    {"force": "Geopolitical", "current": 9.0, "projected": 8.7, "delta": -0.3},
                    {"force": "Technology", "current": 6.0, "projected": 6.0, "delta": 0.0},
                    {"force": "Nature", "current": 5.0, "projected": 5.2, "delta": 0.2},
                ],
                "amplifier": "Debt / money",
                "absorber": "Internal politics",
                "contagion": 0.45,
                "contagionLabel": "Spreading",
            },
```

Then add a test function at the end of the file:

```python
def test_five_forces_network_validates() -> None:
    data = FiveForcesData.model_validate(_five_forces_fixture())
    net = data.loops.network
    assert net.amplifier == "Debt / money"
    assert net.absorber == "Internal politics"
    assert net.contagionLabel == "Spreading"
    assert net.edges[0].fromLabel == "Debt / money"
    assert net.edges[0].strength == 0.54
    assert len(net.projections) == 5
    assert net.projections[1].delta == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_payloads_five_forces.py -q`
Expected: FAIL — `test_five_forces_network_validates` fails with `AttributeError: 'T5Loops' object has no attribute 'network'` (Pydantic ignores the unknown fixture key until the field exists).

- [ ] **Step 3: Implement the models + field**

In `packages/core/src/openlia/macro_research/payloads.py`, insert these models immediately before `class T5Loops(BaseModel):`:

```python
class T5NetworkEdge(BaseModel):
    fromLabel: str
    toLabel: str
    strength: float


class T5ForceProjection(BaseModel):
    force: str
    current: float
    projected: float
    delta: float


class T5ForceNetwork(BaseModel):
    label: str
    edges: list[T5NetworkEdge]
    projections: list[T5ForceProjection]
    amplifier: str
    absorber: str
    contagion: float
    contagionLabel: str
```

Then add the field to `T5Loops` (immediately after `active: T5ActiveCount`):

```python
    network: T5ForceNetwork
```

- [ ] **Step 4: Fix the snapshot-deriver fixture**

In `packages/core/tests/macro_research/test_snapshot.py`, the `_five_forces(count_text)` helper builds a `FiveForcesData` with a `loops` dict that now needs a `network` key. Add it inside that `loops` dict, immediately after its `"active": {...}` block:

```python
            "network": {
                "label": "Influence network (current)",
                "edges": [],
                "projections": [],
                "amplifier": "Debt / money",
                "absorber": "Internal politics",
                "contagion": 0.0,
                "contagionLabel": "Contained",
            },
```

(Empty `edges`/`projections` lists are valid; this fixture only exercises the `active_force_count` deriver, which does not read `network`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/macro_research/test_payloads_five_forces.py packages/core/tests/macro_research/test_snapshot.py -q`
Expected: PASS (all, including the new `test_five_forces_network_validates` and the snapshot tests).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_five_forces.py packages/core/tests/macro_research/test_snapshot.py
uv run ruff format packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_five_forces.py packages/core/tests/macro_research/test_snapshot.py
git add packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads_five_forces.py packages/core/tests/macro_research/test_snapshot.py
git commit -m "feat(macro-research): force-network payload models on T5Loops"
```

---

### Task 4: Frontend types + FALLBACK (`types.ts`, `five_forces.ts`)

**Files:**
- Modify: `frontend/src/lib/macro_research/dalio_copy/types.ts` (add interfaces + `network` on `FiveForcesData.loops`)
- Modify: `frontend/src/lib/macro_research/dalio_copy/five_forces.ts` (add `network` instance)

- [ ] **Step 1: Add the interfaces**

In `frontend/src/lib/macro_research/dalio_copy/types.ts`, immediately before `export interface FiveForcesData {` (line 596), add:

```typescript
export interface T5NetworkEdge {
  fromLabel: string;
  toLabel: string;
  strength: number;
}

export interface T5ForceProjection {
  force: string;
  current: number;
  projected: number;
  delta: number;
}

export interface T5ForceNetwork {
  label: string;
  edges: T5NetworkEdge[];
  projections: T5ForceProjection[];
  amplifier: string;
  absorber: string;
  contagion: number;
  contagionLabel: string;
}
```

Then inside `FiveForcesData`, add the field to the inline `loops` object (immediately after `active: T5ActiveCount;`):

```typescript
    network: T5ForceNetwork;
```

- [ ] **Step 2: Add the FALLBACK instance**

In `frontend/src/lib/macro_research/dalio_copy/five_forces.ts`, add a `network` key to the `loops` object of `FIVE_FORCES_FALLBACK`, immediately after the `active: { ... }` block:

```typescript
    network: {
      label: "Influence network (current)",
      edges: [
        { fromLabel: "Debt / money", toLabel: "Internal politics", strength: 0.54 },
        { fromLabel: "Geopolitical", toLabel: "Debt / money", strength: 0.45 },
        { fromLabel: "Internal politics", toLabel: "Geopolitical", strength: 0.45 },
        { fromLabel: "Nature", toLabel: "Debt / money", strength: 0.36 },
      ],
      projections: [
        { force: "Debt / money", current: 9, projected: 8.6, delta: -0.4 },
        { force: "Internal politics", current: 8, projected: 8.3, delta: 0.3 },
        { force: "Geopolitical", current: 9, projected: 8.7, delta: -0.3 },
        { force: "Technology", current: 6, projected: 6, delta: 0 },
        { force: "Nature", current: 5, projected: 5.2, delta: 0.2 },
      ],
      amplifier: "Debt / money",
      absorber: "Internal politics",
      contagion: 0.45,
      contagionLabel: "Spreading",
    },
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/macro_research/dalio_copy/types.ts frontend/src/lib/macro_research/dalio_copy/five_forces.ts
git commit -m "feat(macro-research): force-network types + fallback for Five Forces"
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
def test_five_forces_exposes_both_classify_and_network_tools() -> None:
    from openlia.llm.runtime.report_dash_mr.tools.dashboard_tools import (
        CLASSIFY_TOOL_BY_SLUG,
    )

    builders = CLASSIFY_TOOL_BY_SLUG["five_forces"]
    names = {b().descriptor.name for b in builders}
    assert names == {"classify_five_forces", "analyze_five_forces_network"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py -q`
Expected: FAIL — `five_forces` currently maps to a single-element list, so the name set is `{"classify_five_forces"}`.

- [ ] **Step 3a: Add the tool + register it**

In `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`:

Add the import next to the other quant imports near the top:

```python
from openlia.macro_research.quant.forces_network import analyze_force_network
```

Add the builder immediately after `build_classify_five_forces_tool`:

```python
def build_analyze_five_forces_network_tool() -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            out = analyze_force_network(
                ForceScores(
                    debt_money=float(args["debt_money"]),
                    political=float(args["political"]),
                    geopolitical=float(args["geopolitical"]),
                    technology=float(args["technology"]),
                    natural=float(args["natural"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolExecutionError(
                "analyze_five_forces_network requires numeric debt_money, political, "
                f"geopolitical, technology, natural (each 0-10). {exc}"
            ) from exc
        return ToolResult(
            payload={
                "edges": [
                    {"from_label": e.from_label, "to_label": e.to_label, "strength": e.strength}
                    for e in out.edges
                ],
                "projections": [
                    {
                        "force": p.force,
                        "current": p.current,
                        "projected": p.projected,
                        "delta": p.delta,
                    }
                    for p in out.projections
                ],
                "amplifier": out.amplifier,
                "absorber": out.absorber,
                "contagion": out.contagion,
                "contagion_label": out.contagion_label,
            },
            provenance=ComputedSource(
                method="analyze_five_forces_network", derived_from=["(scores)"]
            ),
            summary=f"{out.contagion_label} contagion={out.contagion:.2f} edges={len(out.edges)}",
        )

    _score = {"type": "number", "minimum": 0, "maximum": 10}
    return ResearchTool(
        descriptor=ToolDescriptor(
            name="analyze_five_forces_network",
            description=(
                "Deterministic Dalio force-influence network from the five 0-10 force "
                "scores (same scores as classify_five_forces). Returns the active causal "
                "`edges` (each a {from_label, to_label, strength} object; render as a "
                "{fromLabel, toLabel, strength} array), the per-force `projections` (each a "
                "{force, current, projected, delta} object; render as an array), the "
                "`amplifier` and `absorber` force labels, and the aggregate `contagion` "
                "(0-1) plus `contagion_label`. Use the returned numbers verbatim to fill "
                "loops.network."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "debt_money": {**_score, "description": "F1 debt/money cycle intensity, 0-10"},
                    "political": {**_score, "description": "F2 internal order/political, 0-10"},
                    "geopolitical": {**_score, "description": "F3 geopolitical cycle, 0-10"},
                    "technology": {**_score, "description": "F4 technology wave, 0-10"},
                    "natural": {**_score, "description": "F5 acts of nature, 0-10"},
                },
                "required": ["debt_money", "political", "geopolitical", "technology", "natural"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )
```

Update the `five_forces` entry in `CLASSIFY_TOOL_BY_SLUG` to list both builders:

```python
    "five_forces": [build_classify_five_forces_tool, build_analyze_five_forces_network_tool],
```

(`ForceScores` is already imported in this file by `build_classify_five_forces_tool`; the registry is already `dict[str, list[Callable[[], ResearchTool]]]`.)

- [ ] **Step 3b: Update the prompt**

In `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`, replace step 4 of `_FIVE_FORCES_WORKFLOW` (the "Write the force scorecard rows ..." step) and renumber so the block reads:

```python
_FIVE_FORCES_WORKFLOW = """\
Work in this order:
  1. Read the seeded force scores in the "# Provided inputs for this run"
     block. F1 (debt/money) is seeded from the cached Debt Cycle state and
     F3 (geopolitical) from the cached World Order state — treat both as
     authoritative ground truth; do not invent or override them.
  2. Research and score the remaining three forces on a 0-10 intensity
     scale, each with citations: F2 (internal order / political), F4
     (technology), and F5 (acts of nature). Prefer the enabled connector
     tools first; fall back to `web_search` of official and reputable
     sources.
  3. Call `classify_five_forces` with all five scores. Use the returned
     `active_force_count`, `bucket`, and `severity` verbatim — do not invent
     or override them.
  4. Call `analyze_five_forces_network` with the same five scores. Fill
     `loops.network` from its output, mapping the numbers exactly — do not
     invent or override them: `amplifier`->`amplifier`, `absorber`->`absorber`,
     `contagion`->`contagion`, `contagion_label`->`contagionLabel`,
     `edges`->`edges`, `projections`->`projections`. The returned `edges` is a
     list of {from_label, to_label, strength}; render each as
     {fromLabel, toLabel, strength}. The returned `projections` is a list of
     {force, current, projected, delta}; render each verbatim. You author only
     the short `label` header.
  5. Write the force scorecard rows, the interlocking-loop blocks plus the
     active-count block, the signal cards, the gold-allocation block, the
     bull/bear scenarios, and the synthesis verdict from the cited data you
     gathered.
  6. Call `emit_dashboard` exactly once with the full FiveForcesData object
     in `payload`. This finalizes the run."""
```

In `_FIVE_FORCES_PAYLOAD_SHAPE`, replace the `loops` bullet with:

```python
  - `loops`: {label, blocks: [{title, arrows: [{fromLabel, toLabel}], body}],
    active: {countText, countTone, title, body}, network: {label, edges:
    [{fromLabel, toLabel, strength}], projections: [{force, current, projected,
    delta}], amplifier, absorber, contagion, contagionLabel}} — anchor
    `active.countText` on the classifier's active_force_count (e.g. "3 / 5") and
    `active.title` on its bucket. Fill `network` entirely from
    `analyze_five_forces_network` (strength/contagion are decimals 0-1;
    current/projected/delta are 0-10); you author only `network.label`.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py -q`
Expected: PASS (including the new tool-presence test and the existing `set(CLASSIFY_TOOL_BY_SLUG) <= set(PAYLOAD_MODEL_BY_SLUG)` test — keys unchanged).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py
uv run ruff format packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py
git add packages/core/src/openlia/llm/runtime/report_dash_mr/ packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py
git commit -m "feat(macro-research): analyze_five_forces_network tool + prompt wiring"
```

---

### Task 6: Engine-run test (verbatim numbers end-to-end)

**Files:**
- Test: `packages/core/tests/runtime/report_dash_mr/test_runner_five_forces.py`

Task 3 made `loops.network` required and Task 5 registered the `analyze_five_forces_network` tool — so this runner test is RED until updated here (its payload lacks `network` and its script lacks the network turn). This task makes it green.

- [ ] **Step 1: Extend the run test**

In `packages/core/tests/runtime/report_dash_mr/test_runner_five_forces.py`:

In `_complete_five_forces_payload()`, add a `network` key to the `"loops"` dict, immediately after its `"active": {...}` block:

```python
            "network": {
                "label": "Influence network (current)",
                "edges": [
                    {"fromLabel": "Debt / money", "toLabel": "Internal politics", "strength": 0.48},
                ],
                "projections": [
                    {"force": "Debt / money", "current": 8.0, "projected": 7.8, "delta": -0.2},
                    {"force": "Internal politics", "current": 7.0, "projected": 7.4, "delta": 0.4},
                    {"force": "Geopolitical", "current": 5.0, "projected": 5.3, "delta": 0.3},
                    {"force": "Technology", "current": 7.0, "projected": 6.9, "delta": -0.1},
                    {"force": "Nature", "current": 4.0, "projected": 4.2, "delta": 0.2},
                ],
                "amplifier": "Debt / money",
                "absorber": "Internal politics",
                "contagion": 0.42,
                "contagionLabel": "Spreading",
            },
```

Update the scripted turns in `test_runner_classify_then_emit_five_forces` to add the network tool call between classify and emit:

```python
    script = [
        script_tool_calls(
            (
                "classify_five_forces",
                {
                    "debt_money": 8,
                    "political": 7,
                    "geopolitical": 5,
                    "technology": 7,
                    "natural": 4,
                },
            )
        ),
        script_tool_calls(
            (
                "analyze_five_forces_network",
                {
                    "debt_money": 8,
                    "political": 7,
                    "geopolitical": 5,
                    "technology": 7,
                    "natural": 4,
                },
            )
        ),
        script_tool_calls(("emit_dashboard", {"payload": payload})),
    ]
```

After the existing assertions in that test, add:

```python
    assert validated.loops.network.amplifier == "Debt / money"
    assert validated.loops.network.contagionLabel == "Spreading"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest packages/core/tests/runtime/report_dash_mr/test_runner_five_forces.py -q`
Expected: PASS (1 passed). The runner executes the real loop classify → network → emit; the typed payload (now with `loops.network`) round-trips and validates.

- [ ] **Step 3: Commit**

```bash
git add packages/core/tests/runtime/report_dash_mr/test_runner_five_forces.py
git commit -m "test(macro-research): five_forces run exercises network tool + loops.network payload"
```

---

### Task 7: Frontend force-network sub-card (`FiveForcesView.tsx`)

**Files:**
- Modify: `frontend/src/pages/departments/macro_research/FiveForcesView.tsx`
- Test: `frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx` (FiveForcesView block)

- [ ] **Step 1: Write the failing test**

In `Views.test.tsx`, in the FiveForcesView "renders live cache content" test (the block asserting `t5-loops` / `t5-active-count` etc.), add:

```typescript
    expect(screen.getByTestId("t5-force-network")).toBeInTheDocument();
```

(The shared `FIVE_FORCES_FALLBACK` already carries `loops.network` from Task 4, so no mock change is needed.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/departments/macro_research/__tests__/Views.test.tsx -t "FiveForcesView"`
Expected: FAIL — `Unable to find an element by: [data-testid="t5-force-network"]`.

- [ ] **Step 3: Implement the sub-card**

In `frontend/src/pages/departments/macro_research/FiveForcesView.tsx`:

Add `T5NetworkEdge` and `T5ForceProjection` to the type import block (alongside the other `T5*` type imports near the top):

```typescript
  T5ForceProjection,
  T5NetworkEdge,
```

Add a percentage formatter at module scope (near the existing helpers):

```typescript
function fmtPct(d: number): string {
  return `${Math.round(d * 100)}%`;
}
```

Insert the force-network sub-card immediately after the `<ActiveCount active={data.loops.active} />` element (line ~187) and before the `<SectionLabel count={data.signals.label}>` (Section C):

```tsx
      <div
        className="mr-card"
        data-testid="t5-force-network"
        style={{ padding: "16px 18px", marginBottom: 14 }}
      >
        <div className="mr-card-title">{data.loops.network.label}</div>
        <div className="mr-bar-section" style={{ marginTop: 8 }}>
          <div className="mr-bar-section-title">Active causal edges</div>
          {data.loops.network.edges.length === 0 ? (
            <p className="mr-card-body-text">No forces are intense enough to transmit.</p>
          ) : (
            data.loops.network.edges.map((e: T5NetworkEdge) => (
              <div key={`${e.fromLabel}->${e.toLabel}`} className="mr-bar-row">
                <div className="mr-bar-label">
                  {e.fromLabel} &rarr; {e.toLabel}
                </div>
                <div className="mr-bar-track">
                  <div className="mr-bar-fill mr-fill-bad" style={{ width: `${e.strength * 100}%` }} />
                </div>
                <div className="mr-bar-val">{fmtPct(e.strength)}</div>
              </div>
            ))
          )}
        </div>
        <div className="mr-bar-section" style={{ marginTop: 12 }}>
          <div className="mr-bar-section-title">Projected next-period intensity</div>
          {data.loops.network.projections.map((p: T5ForceProjection) => (
            <div key={p.force} className="mr-bar-row">
              <div className="mr-bar-label">{p.force}</div>
              <div className="mr-bar-val" style={{ minWidth: 150 }}>
                {p.current.toFixed(1)} &rarr; {p.projected.toFixed(1)} (
                {p.delta >= 0 ? "+" : ""}
                {p.delta.toFixed(1)})
              </div>
            </div>
          ))}
        </div>
        <div className="mr-grid3" style={{ marginTop: 12 }}>
          <div>
            <div className="mr-card-title">Amplifier</div>
            <div className="mr-card-body-text">{data.loops.network.amplifier}</div>
          </div>
          <div>
            <div className="mr-card-title">Absorber</div>
            <div className="mr-card-body-text">{data.loops.network.absorber}</div>
          </div>
          <div>
            <div className="mr-card-title">Contagion</div>
            <div className="mr-card-body-text">
              {data.loops.network.contagionLabel} ({fmtPct(data.loops.network.contagion)})
            </div>
          </div>
        </div>
      </div>
```

- [ ] **Step 4: Run the test + tsc**

Run: `cd frontend && npx vitest run src/pages/departments/macro_research/__tests__/Views.test.tsx -t "FiveForcesView" && npx tsc --noEmit`
Expected: PASS; tsc no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/departments/macro_research/FiveForcesView.tsx frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx
git commit -m "feat(macro-research): Five Forces influence-network sub-card"
```

---

### Task 8: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Lint + format (whole packages)**

Run: `uv run ruff check packages/core packages/server && uv run ruff format --check packages/core packages/server`
Expected: `All checks passed!` and no files would reformat. Fix any findings and amend the relevant commit.

- [ ] **Step 2: Core test suite**

Run: `uv run pytest packages/core/tests/macro_research/ packages/core/tests/runtime/report_dash_mr/ -q`
Expected: all pass (the new `test_forces_network.py`, the extended payload/snapshot/runner/implemented-dashboards tests, and every pre-existing macro_research/report_dash_mr test).

- [ ] **Step 3: Frontend tests + build**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/pages/departments/macro_research/`
Expected: tsc clean; all macro_research view tests pass.

- [ ] **Step 4: Final commit (if any fixups)**

```bash
git add -A
git commit -m "chore(macro-research): lint/format fixups for Five Forces network" || echo "nothing to commit"
```

---

## Notes for the implementer

- **Determinism:** the engine is pure arithmetic — no RNG, no wall-clock. Identical inputs always yield identical output; the payload is cached in `mr_dashboard_cache`.
- **Honesty:** the `INFLUENCE` matrix is baked structural coupling, NOT fitted from data. The module docstring states this; do not add any data-fitting.
- **The model never invents the network numbers.** The tool returns them; the prompt maps the snake_case tool keys to the camelCase payload keys explicitly (`from_label`->`fromLabel`, `contagion_label`->`contagionLabel`, etc.) and turns the `edges`/`projections` lists into `{...}` arrays. The model authors only the short `network.label`.
- **No server `mr_dash_run_service` change** — Five Forces already seeds F1/F3 via `data_context`; F2/F4/F5 are LLM-scored.
- If `npx vitest`/`tsc` is run from the repo root it will fail; run from `frontend/`.

## Post-implementation amendments (review-driven)

Changes made during code review / verification, reflected in the final code:

1. **Task 4 — FALLBACK consistency.** The static `five_forces.ts` FALLBACK `network`
   instance was rewritten to be internally consistent with the engine contract:
   all five forces active (intensity 7-9, matching `active: "5 / 5"`), all 11
   active edges with `strength = coupling × (driver_intensity/10)`, correctly
   derived projections, and `contagion` = the mean of those edge strengths
   (0.32 → "Spreading"). The initial draft had edges whose strengths/drivers
   didn't reconcile with the projections table.
2. **Task 5 — explicit per-edge key rename.** `_FIVE_FORCES_WORKFLOW` step 4's
   inline mapping spells out `edges`->`edges` (each `{from_label, to_label,
   strength}` becomes `{fromLabel, toLabel, strength}`), and the tool descriptor
   notes `contagion_label` renders as `contagionLabel` — the snake_case/camelCase
   + dict→array clarity the sibling engines needed.
3. **Task 6 — runner fixture.** Docstring updated to "three turns" (classify →
   network → emit); the scripted `contagion` set to 0.48 to equal its single
   edge's strength.
4. **Task 7 — projections layout.** The per-force projection rows use a bespoke
   2-column flex row instead of `mr-bar-row` (a 3-column label|track|val grid),
   which had misplaced the value into the track column.
5. Trivial lint hygiene: `ACTIVE_THRESHOLD: float` / `PERSISTENCE: float`
   annotations (Task 1); Task 1 scoped strictly to the baked data + accessor
   (an early pull-forward of Task 2's dataclasses was reverted).
