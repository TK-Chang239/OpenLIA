# Macro Research — Curated Reference Datasets for the Quant Engines (design spec)

- **Date:** 2026-06-03
- **Status:** Approved design, pending implementation plan
- **Scope:** The three baked-parameter quant engines —
  All-Weather Monte-Carlo (`macro_research/risk_math.py`), Four Seasons Markov
  (`macro_research/quant/markov.py`), and Five Forces influence network
  (`macro_research/quant/forces_network.py`). Replace hand-picked baked
  parameters with documented-provenance values. **Contract-preserving:** no
  changes to payloads, types, tools, prompts, or frontend.
- **Builds on:** the three heavy-quant specs
  (`macro-research-heavy-quant-all-weather-monte-carlo-design.md` #247,
  `...-four-seasons-markov-design.md` #248,
  `...-five-forces-network-design.md` #249) and
  `macro-research-llm-dashboard-redesign.md` (the `report_dash_mr` engine).

## 1. Problem

The three quant engines run on baked reference parameters that are hand-picked
round numbers with no documented provenance. Their modules describe them as
"Reference assumptions (adjustable)":

- **All-Weather** (`risk_math.py`): `DEFAULT_VOLS`, `EXPECTED_RETURNS`,
  `CORRELATIONS` — feed the covariance matrix and the Monte-Carlo drift.
- **Four Seasons** (`markov.py`): `TRANSITION_MATRIX` — a hand-set
  diagonal-dominant quarterly regime matrix.
- **Five Forces** (`forces_network.py`): `INFLUENCE` (directed coupling) +
  `PERSISTENCE` — a hand-set structural matrix.

This deferred item replaces those hand-picked numbers with
**documented-provenance values**: second moments *computed* from real history
where statistically defensible, regime/structure parameters *curated* from cited
sources, each with an audit trail. It does **not** change any engine's behaviour
contract — only the values, plus docstrings, a derivation script, a provenance
doc, and the test expectations that pin specific old numbers.

## 2. Goals / non-goals

**Goals**
- Give every baked parameter a documented basis (computed-from-data or
  cited-from-literature), captured in one provenance doc.
- **Compute** the parameters that are statistically defensible to estimate from
  real history (asset second moments).
- **Curate with citations** the parameters whose inputs are not clean time
  series (regime transitions; structural force couplings).
- Preserve the engines' two load-bearing invariants: **determinism** and
  **no live runtime fetch** (the parameters remain baked module constants; the
  payloads stay cached).
- Be **contract-preserving** — identical payloads/types/tools/prompts/frontend.

**Non-goals**
- **No live runtime data fetch.** Any computation happens *offline once*, via a
  committed derivation script; the results are pasted in as constants. The
  engines never fetch at request time (the cache contract depends on this).
- **No data-fitting of structural parameters.** The Five Forces `INFLUENCE`
  matrix's inputs are soft 0-10 scores, not time series; it stays structural and
  explicitly NOT fitted (the #249 non-goal is unchanged) — this track only
  documents its basis.
- **No naive realized-return drift.** Realized ~20yr proxy returns are a poor
  proxy for *forward* expected returns; `EXPECTED_RETURNS` is curated forward
  capital-market assumptions, not the realized sample mean (see §3).
- No new dashboards, no payload/type/tool/prompt/frontend changes, no behaviour
  changes beyond the numeric values.

## 3. Track 1 — All-Weather: computed second moments + curated forward returns

The textbook capital-market-assumptions split: estimate the **second moments**
(volatilities, correlations) from history — they are comparatively stationary and
defensible to estimate — and set the **first moments** (expected returns) as
forward assumptions rather than realized sample means.

### 3.1 Data source & window
- **Proxies** (EODHD `adjusted_close`, i.e. total return incl. distributions):
  | asset class | proxy ticker |
  | --- | --- |
  | `equities` | `SPY.US` |
  | `long_bonds` | `TLT.US` |
  | `intermediate_bonds` | `IEF.US` |
  | `gold` | `GLD.US` |
  | `commodities` | `DBC.US` |
- **Window:** the **maximal common overlapping** daily window across all five
  proxies. The binding inception is `DBC.US` (~Feb 2006); the window runs from
  the first common trading day through the most recent **complete year-end**.
  The exact start/end dates are recorded in the provenance doc at derivation
  time.

### 3.2 Computed parameters
- **`DEFAULT_VOLS` ← computed.** Annualized standard deviation of **daily log
  returns**: `vol_a = std(daily_log_returns_a) * sqrt(252)`.
- **`CORRELATIONS` ← computed.** Pairwise **Pearson correlation of daily log
  returns**. Because this is an empirical correlation matrix, it is
  positive-semi-definite by construction, so the existing
  `test_risk_math` eigenvalue (PSD) assertion stays green. Stored in the same
  upper-triangle `dict[tuple[str, str], float]` shape, rounded to a documented
  precision (e.g. 2 decimals).

### 3.3 Curated parameter
- **`EXPECTED_RETURNS` ← curated forward CMAs (decision on record).** Long-run
  nominal expected returns set as forward capital-market assumptions
  (long-run real return + a long-run inflation assumption), **not** the realized
  window CAGR. The realized window CAGR per asset **is** computed and recorded in
  the provenance doc **as a sanity reference**, but is not adopted as the drift.
  The current values are already roughly CMA-shaped; this track documents their
  basis and refines them against a cited CMA framework.

### 3.4 Reproducibility (offline, not runtime)
- A committed, re-runnable **derivation script** (dev tooling; **not** imported
  by any runtime module — keeps `openlia-core` import-clean and fetch-free). It
  reads the EODHD key from the environment, fetches the five proxy series over
  the common window, prints the computed `DEFAULT_VOLS` / `CORRELATIONS` and the
  realized-CAGR reference table, and is run **once** during implementation.
- The printed numbers are pasted into `risk_math.py` as the new constants. The
  module docstrings change from "Reference assumptions (adjustable)" to
  "Estimated from {proxies} daily adjusted closes over {window}; see provenance
  doc," and `EXPECTED_RETURNS` to "Curated forward CMAs; see provenance doc."

## 4. Track 2 — Four Seasons: literature-curated transition matrix

`TRANSITION_MATRIX` (quarterly, row-stochastic, over Spring/Summer/Autumn/Winter)
is curated and anchored to two cited quantities, so the numbers stop being
arbitrary:

- **Quadrant ↔ cycle phase mapping** (the four seasons are growth × inflation
  quadrants, which map onto the Merrill Lynch *Investment Clock* phases):
  - Spring = rising growth, falling inflation → **Recovery**
  - Summer = rising growth, rising inflation → **Overheat**
  - Autumn = falling growth, rising inflation → **Stagflation**
  - Winter = falling growth, falling inflation → **Reflation**
- **Off-diagonal rotation ← Investment Clock** (Trevor Greetham / Merrill Lynch):
  the cycle rotates clockwise Recovery → Overheat → Stagflation → Reflation →
  Recovery, i.e. **Spring → Summer → Autumn → Winter → Spring** — matching the
  existing dominant off-diagonal direction. The bulk of each row's off-diagonal
  mass goes to the **next** clockwise phase; small mass to reversion (previous
  phase) and a minimal "skip" to the opposite quadrant.
- **Diagonal/persistence ← documented phase dwell.** Anchored to documented
  average business-cycle phase durations (NBER cycle dating for expansion/
  contraction lengths; Investment Clock phase persistence). Target persistence
  `p` such that expected dwell `1/(1-p)` matches the cited ~3-quarter average,
  with the stagflation (Autumn) phase set slightly less persistent (it
  historically resolves faster toward Winter).

**Proposed matrix** (rows = from, cols = to; final values pinned in the plan +
provenance doc):

| from \ to | Spring | Summer | Autumn | Winter |
| --- | --- | --- | --- | --- |
| Spring | 0.65 | 0.25 | 0.03 | 0.07 |
| Summer | 0.07 | 0.65 | 0.25 | 0.03 |
| Autumn | 0.03 | 0.07 | 0.60 | 0.30 |
| Winter | 0.25 | 0.03 | 0.07 | 0.65 |

(Each row sums to 1.0; diagonal ≈ 0.60–0.65 → expected dwell ≈ 2.5–2.9 quarters;
dominant off-diagonal is the next clockwise phase.) Row-stochasticity is already
asserted in `test_markov` and remains.

## 5. Track 3 — Five Forces: documented structural basis

`INFLUENCE` is structural by design and explicitly **not** fitted (the #249
non-goal stands — its inputs are soft 0-10 scores, not time series). This track is
therefore **documentation-grade**:

- Each non-zero coupling `A[driver][driven]` is mapped to its **Dalio
  linkage rationale** (*Principles for Dealing with the Changing World Order* —
  the Big Cycle's description of how the forces drive one another) in the
  provenance doc: e.g. debt_money → political (debt/money stress drives internal
  political conflict), political → geopolitical (internal conflict spills into
  external conflict), etc.
- The module docstring gains a pointer to the provenance doc.
- **Default: values unchanged.** Any value change cascades to
  `test_forces_network` (hard-coded couplings/contagion), the TS `FALLBACK`, and
  the snapshot fixtures, so a change is made **only** if a documented linkage
  clearly contradicts a current entry, and is then propagated through all three.

## 6. Provenance document

One new doc: `planning/specs/systems/macro-research-reference-datasets-provenance.md`.
The audit trail that makes these values "curated," not arbitrary. Per engine:
- **source** (proxy tickers + EODHD, or the cited literature),
- **method** (computation formula, or the anchoring rationale),
- **window / citations**,
- **derivation run date**,
- **the resulting values** (and, for All-Weather, the realized-CAGR sanity table
  beside the curated forward returns),
- **re-derivation command** (for the All-Weather script).

(`planning/` is excluded from package builds and Docker images; this is
reference/operator documentation, consistent with the other MR specs.)

## 7. Contract preservation

**Changes:** constant values in `risk_math.py`, `markov.py`, `forces_network.py`
(Five Forces values unchanged by default); their docstrings; a new derivation
script; the provenance doc; and the test expectations that pin specific old
numbers.

**Unchanged:** every Pydantic payload model, `dalio_copy/types.ts`, the
`report_dash_mr` tools (`PAYLOAD_MODEL_BY_SLUG`, `CLASSIFY_TOOL_BY_SLUG`),
the prompts (`DASHBOARD_PROMPT_SPECS`), all frontend views, the run services, and
every engine's function signatures and return types. No migration, no API change.

## 8. Testing / blast radius (verified against the test files)

- **`test_risk_math.py`** — structural assertions (shape, symmetry, unit
  diagonal, PSD eigenvalues, `cov[i,i] == DEFAULT_VOLS[a]**2`) that read the
  constants rather than hard-code numbers → **survives** the new computed values.
- **`test_monte_carlo.py`** — relational assertions (scenario names/count,
  determinism, percentile ordering `p5<p25<p50<p75<p95`, crash worse than base,
  crash tone red, weight-normalization determinism) → **survives**; the plan adds
  a verification step that these relationships still hold under the new params.
- **`test_markov.py`** — **hard-codes matrix-derived values** (the Summer-row
  distribution, `persistence == 0.57`, `adverse_prob == 0.27`,
  `expected_dwell == 2.5`) → **must be updated** to the curated matrix's values.
- **`test_forces_network.py`** — hard-codes couplings, edge ordering, amplifier/
  absorber, and contagion → **untouched if Five Forces values are unchanged**
  (the default); if a value is changed, this file + the TS `FALLBACK` +
  `test_snapshot` fixtures are updated in lockstep.
- **`tests/runtime/report_dash_mr/test_runner_all_weather.py`** — engine-run test;
  re-verified for structural validity under the new params.
- New tests: none required beyond updates — the work changes values, not
  behaviour. The derivation script is dev tooling (not unit-tested); its output
  is validated by the existing `risk_math` structural tests once pasted in.

## 9. Build order

1. **All-Weather:** write the derivation script → run it (EODHD) → capture the
   computed vols/correlations + realized-CAGR reference → paste constants + set
   curated forward `EXPECTED_RETURNS` + update docstrings → verify `test_risk_math`
   and `test_monte_carlo` (update only if a relational assert breaks).
2. **Four Seasons:** finalize the curated `TRANSITION_MATRIX` (pin values to the
   cited dwell/rotation) → update `markov.py` + docstring → update `test_markov`
   expectations.
3. **Five Forces:** write the per-coupling provenance mapping → add the docstring
   pointer (values unchanged by default).
4. **Provenance doc:** consolidate all three (sources, methods, windows/citations,
   run date, resulting values, re-derivation command).
5. **Verify:** `uv run ruff check . && uv run ruff format --check .`; targeted
   `uv run pytest packages/core/tests/macro_research packages/core/tests/runtime/report_dash_mr`.

## 10. Decisions on record

- **Hybrid provenance:** compute the statistically defensible second moments from
  real EODHD history; curate the rest (regime transitions, force couplings) from
  cited literature. (User-selected.)
- **Curated forward `EXPECTED_RETURNS`**, not realized CAGR — realized ~20yr
  returns are not forward expectations; realized CAGR recorded only as a sanity
  reference. (User-selected.)
- **One spec, one PR, per-track commits** — the tracks are independent work but a
  cohesive, contract-preserving theme. (User-selected.)
- **Offline derivation only** — params stay baked constants; no runtime fetch;
  determinism + cache contract preserved.
- **Five Forces stays structural / documentation-grade** — not fitted (the #249
  non-goal is unchanged); values changed only on a clear documented contradiction.
- **Contract-preserving** — values + docstrings + script + provenance doc + pinned
  test expectations only; no payload/type/tool/prompt/frontend change.
