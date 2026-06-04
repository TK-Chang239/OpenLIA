# Macro Research — Heavy Quant: Five Forces Influence Network (VAR-style) (design spec)

- **Date:** 2026-06-03
- **Status:** Approved design, pending implementation plan
- **Scope:** Five Forces (T5) dashboard only. Third and final of the three
  deferred "heavy quant" engines (after All-Weather Monte-Carlo #247 and Four
  Seasons Markov #248).
- **Builds on:** `planning/specs/systems/macro-research-llm-dashboard-redesign.md`
  (the `report_dash_mr` engine) and the All-Weather / Four Seasons heavy-quant
  specs (the baked-params + dedicated-typed-output + multi-tool-per-slug pattern
  this reuses).

## 1. Problem

The Five Forces dashboard scores five forces (debt/money, internal politics,
geopolitical, technology, nature) on a 0–10 intensity scale and classifies an
active-force count + bucket deterministically (`macro_research/quant/forces.py`).
But its **interlocking-loop read is LLM prose** — `T5Loops` (the feedback-loop
`blocks` with force→force `arrows`, plus the active-count block) is hand-authored
narrative with no quantified force-to-force coupling or propagation.

The deferred "VAR causality" work asked for cross-force causality. The inputs are
**soft 0–10 scores, not time series** (F1 is seeded from the Debt Cycle, F3 from
World Order, and F2/F4/F5 are LLM-researched), so a *data-fitted* VAR/Granger
model is not available under the baked-params approach. This spec adds the honest
deterministic analog: a **baked structural influence matrix** (Dalio's documented
force linkages) applied to the current 5-score vector as a **VAR(1)-style one-step
linear map** — yielding the active causal edges, a projected next-period intensity
per force, per-force amplifier/absorber roles, and an aggregate contagion read,
surfaced inside the existing `loops` section.

## 2. Goals / non-goals

**Goals**
- Quantify cross-force coupling deterministically and reproducibly.
- Surface it *inside* the existing `loops` section (computed network beside the
  narrative loops), not as a separate parallel section.
- Report: ranked active causal edges, a one-step projected next-period intensity
  per force, per-force amplifier/absorber roles, and an aggregate contagion read.

**Non-goals**
- **No data-fitted VAR/Granger.** The influence matrix is a **baked structural
  reference parameter** (Dalio's documented force linkages), explicitly NOT
  estimated from time series. The spec and code state this plainly; "VAR-style"
  refers only to the one-step linear-map *form* (`x_next = f(A·x)`), not to
  coefficient estimation.
- No new data fetching (consistent with the prior two engines).
- No change to the current-force classification (`classify_five_forces` is
  unchanged); this layer consumes the same 5 scores.

## 3. Inputs & baked data

A new pure-function module `macro_research/quant/forces_network.py`. Inputs are the
five 0–10 force scores (reusing `ForceScores` from `quant/forces.py`:
`debt_money`, `political`, `geopolitical`, `technology`, `natural`). New baked
reference data (documented as adjustable structural assumptions, NOT fitted):

- **`FORCE_ORDER`** — fixed order:
  `("debt_money", "political", "geopolitical", "technology", "natural")`, with a
  display-label map (e.g. `debt_money` → "Debt / money", etc.).
- **`INFLUENCE`** — a directed 5×5 coupling matrix `A[driver][driven] ∈ [0,1]`,
  **zero diagonal** (self-persistence is handled separately), encoding Dalio's
  documented linkages. Initial structure (driver → driven, strength):
  - debt_money → political (0.6), debt_money → geopolitical (0.4)
  - political → geopolitical (0.5), political → debt_money (0.4)
  - geopolitical → debt_money (0.5), geopolitical → political (0.4)
  - technology → political (0.4), technology → debt_money (0.2)
  - natural → debt_money (0.4), natural → political (0.3), natural → geopolitical (0.2)
  - (all other pairs 0.0)
- **`PERSISTENCE`** — scalar ≈ `0.7`: each force partly persists period-over-period.

The exact numeric values are reference assumptions, adjustable, and pinned in the
implementation plan.

## 4. The VAR(1)-style engine

Pure, **deterministic** — matrix/vector arithmetic, no RNG (identical inputs always
reproduce identical output; the payload is cached).

```python
def analyze_force_network(scores: ForceScores) -> ForceNetwork: ...
```

- **Projected next-period intensity** per driven force `j`:
  `cross[j] = (Σᵢ A[i][j]·x[i]) / (Σᵢ A[i][j])` when `j` has incoming edges, else
  `x[j]`; then `x_next[j] = clamp(PERSISTENCE·x[j] + (1−PERSISTENCE)·cross[j], 0, 10)`.
  `delta[j] = x_next[j] − x[j]`. This is the bounded VAR(1)-style one-step map
  with the baked coefficient matrix `A`.
- **Active causal edges**: edge `i→j` is active when the driver is intense
  (`x[i] ≥ 7.0`, the existing active threshold from `forces.py`) and `A[i][j] > 0`.
  `strength = A[i][j]·(x[i]/10)` (decimal 0–1). Returned ranked by strength,
  descending (ties broken by `FORCE_ORDER`).
- **Per-force roles**: `amplifier` = force with the max out-strength
  (`Σⱼ A[i][j]·x[i]/10`); `absorber` = force with the max in-strength
  (`Σᵢ A[i][j]·x[i]/10`). Reported as display labels.
- **Contagion**: `contagion = clamp(mean active-edge strength, 0, 1)` (0.0 when no
  active edges); `contagion_label` is a fixed bucket — `Contained` (< 0.25),
  `Spreading` (< 0.5), `Self-reinforcing` (≥ 0.5).

Returns a frozen `ForceNetwork` dataclass: `edges` (list of `(from_label,
to_label, strength)`), `projections` (list of `(force_label, current, projected,
delta)` over `FORCE_ORDER`), `amplifier`, `absorber`, `contagion`,
`contagion_label`.

## 5. Payload (augment `T5Loops`)

New Pydantic models in `payloads.py`, mirrored in `dalio_copy/types.ts`
(+ FALLBACK). Edge strengths and contagion are **decimals 0–1**; force
intensities are **0–10** (matching the scorecard scale).

- `T5NetworkEdge` — `{fromLabel: str, toLabel: str, strength: float}`
- `T5ForceProjection` — `{force: str, current: float, projected: float, delta: float}`
- `T5ForceNetwork` —
  `{label: str, edges: list[T5NetworkEdge], projections: list[T5ForceProjection],
  amplifier: str, absorber: str, contagion: float, contagionLabel: str}`

`T5Loops` gains a required field `network: T5ForceNetwork`. The existing
`blocks`/`active` prose fields are unchanged (model-authored). The `network` block
is entirely tool-filled except `label` (a short model-authored header).

## 6. Engine wiring

- **Tool:** new `analyze_five_forces_network` in `tools/dashboard_tools.py`. It
  accepts the same five 0–10 scores as `classify_five_forces`
  (`debt_money`, `political`, `geopolitical`, `technology`, `natural`), builds a
  `ForceScores`, runs `analyze_force_network`, and returns the network numbers as
  JSON. Registered as the **second** builder in
  `CLASSIFY_TOOL_BY_SLUG["five_forces"]`
  (`[build_classify_five_forces_tool, build_analyze_five_forces_network_tool]`) —
  the list-per-slug registry already exists.
- **Prompt:** `_FIVE_FORCES_WORKFLOW` gains a step to call
  `analyze_five_forces_network` (with the same five scores) and fill
  `loops.network` verbatim, with an **explicit** snake_case-tool-key →
  camelCase-payload-key mapping AND an explicit instruction that the returned
  `edges`/`projections` lists become `[{...}]` arrays (the lesson from the prior
  two engines). The `_FIVE_FORCES_PAYLOAD_SHAPE` `loops` bullet documents the
  `network` sub-object.
- **Run service:** no change — F1/F3 seeding already happens in
  `mr_dash_run_service._five_forces_data_context`; F2/F4/F5 are LLM-scored.

## 7. Frontend

Augment the `loops` section (`t5-loops`) in `FiveForcesView.tsx` with a
force-network sub-card (`data-testid="t5-force-network"`), rendered beside the
existing loop blocks / active-count: the ranked active edges (from→to chips with
strength bars), the per-force current→projected intensities with delta, and the
amplifier / absorber / contagion readouts. Reuse the existing T5 chip/bar idiom;
tone the contagion read by its bucket.

## 8. Error handling

- `analyze_force_network` takes a typed `ForceScores`; the tool coerces the five
  numeric args and raises `ToolExecutionError` with context on a missing/invalid
  score (mirroring `build_classify_five_forces_tool`).
- With no active edges (all scores < 7), `edges` is empty and `contagion` is 0.0
  / `Contained` — a valid, fully-populated network (not an error).
- The baked matrix's properties (entries in [0,1], zero diagonal) are asserted in
  tests.

## 9. Testing

- **`quant/forces_network` unit tests:** `INFLUENCE` entries ∈ [0,1] with a zero
  diagonal; an all-low-score input yields no active edges, contagion 0.0,
  `Contained`; a high debt_money score activates its outgoing edges with the
  expected `strength = A·(x/10)`; `projections` are clamped to [0,10] and `delta`
  has the expected sign for a force with intense drivers; `amplifier`/`absorber`
  are the expected argmax labels for a known score vector; `contagion` ∈ [0,1] and
  its bucket label matches the thresholds; edges are ranked descending by strength.
- **Payload-fixture validation:** the `T5ForceNetwork` instance in the TS FALLBACK
  round-trips into the Pydantic `FiveForcesData` model.
- **Tool presence:** `CLASSIFY_TOOL_BY_SLUG["five_forces"]` builds exactly
  `{classify_five_forces, analyze_five_forces_network}`.
- **Engine-run test:** a full `five_forces` `report_dash_mr` run scripts
  classify → network → emit and validates a populated `loops.network`.
- **Frontend:** a view test asserting the force-network sub-card
  (`t5-force-network`) renders (edges + projections + the readouts).

## 10. Build order

1. Baked `INFLUENCE` + `FORCE_ORDER` + labels + `PERSISTENCE` + tests.
2. `forces_network.py` core (`ForceNetwork`, `analyze_force_network`) + unit tests.
3. Payload models + `types.ts` + FALLBACK + fixture-validation test.
4. Tool (`analyze_five_forces_network`) + registry + prompt update.
5. `FiveForcesView.tsx` force-network sub-card + view test.
6. Engine-run test; full lint + targeted suites.

## 11. Decisions on record

- **Baked structural influence matrix, VAR(1)-style one-step map**, explicitly NOT
  fitted from data (the honest reading of "VAR" given soft-score inputs).
- **Augment `loops`** with a typed `network` sub-block, vs a new parallel section.
- **Outputs:** active edges + per-force projected next-period intensity +
  amplifier/absorber + aggregate contagion.
- **Reuse `ForceScores`** (from `quant/forces.py`) as the engine input type.
