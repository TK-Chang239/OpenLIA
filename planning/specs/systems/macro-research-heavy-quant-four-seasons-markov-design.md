# Macro Research — Heavy Quant: Four Seasons Markov Transition (design spec)

- **Date:** 2026-06-03
- **Status:** Approved design, pending implementation plan
- **Scope:** Four Seasons (T2) dashboard only. Second of three deferred "heavy
  quant" engines (after All-Weather Monte-Carlo, shipped in #247). Five Forces
  VAR is the remaining sibling (separate spec).
- **Builds on:** `planning/specs/systems/macro-research-llm-dashboard-redesign.md`
  (the `report_dash_mr` engine) and
  `planning/specs/systems/macro-research-heavy-quant-all-weather-monte-carlo-design.md`
  (the baked-params + dedicated-typed-output + multi-tool-per-slug pattern this
  reuses).

## 1. Problem

The Four Seasons dashboard classifies the *current* economic season
deterministically (`macro_research/quant/seasons.py`: PMI/GDP/CPI → one of
Spring/Summer/Autumn/Winter/Transitioning + a quadrant marker). But its
**transition-risk read is LLM prose** — `T2TransitionRisk` (`intro`, `bull`,
`bear`, `keyIndicator`) is authored narrative with no quantified probability of
the regime actually shifting.

This spec adds a deterministic **Markov transition engine**: given the current
season, it reads a baked quarterly transition matrix and reports the next-season
probability distribution plus derived stats, surfaced inside the existing
`transitionRisk` section so the bull/bear narrative is grounded by real numbers.

## 2. Goals / non-goals

**Goals**
- Quantify regime-transition risk deterministically and reproducibly.
- Surface it *inside* the existing `transitionRisk` section (numbers beside the
  narrative they justify), not as a separate parallel section.
- Report a rich, useful read: next-quarter distribution, persistence,
  most-likely-next, adverse-transition probability, expected dwell time, and a
  4-quarters-ahead outlook.

**Non-goals**
- No new data fetching. The transition matrix is a **baked reference parameter**
  (consistent with the All-Weather approach). Estimating it from live history is
  out of scope.
- No Five Forces VAR (sibling spec).
- No change to the current-season classification (`classify_four_seasons` is
  unchanged); this layer consumes its output.

## 3. State space & baked data

A new reference module (`macro_research/quant/markov.py`) holds:

- **`SEASON_ORDER`** — the canonical 4 quadrant seasons in fixed order:
  `("Spring", "Summer", "Autumn", "Winter")`. `"Transitioning"` is **not** a
  Markov state (it is a confidence label in the classifier); it is resolved to
  the nearest quadrant — see `resolve_quadrant` below.
- **`TRANSITION_MATRIX`** — a row-stochastic 4×4 matrix at **quarterly** cadence,
  documented as adjustable reference assumptions. It is diagonal-dominant
  (seasons persist for several quarters) with the dominant off-diagonal mass
  following the canonical clockwise business cycle
  `Spring → Summer → Autumn → Winter → Spring`. Each row sums to 1.0 (validated
  at import/in tests). Initial values (rows = from, columns = to):

  | from \ to | Spring | Summer | Autumn | Winter |
  | --- | --- | --- | --- | --- |
  | Spring | 0.60 | 0.25 | 0.05 | 0.10 |
  | Summer | 0.08 | 0.60 | 0.27 | 0.05 |
  | Autumn | 0.05 | 0.08 | 0.57 | 0.30 |
  | Winter | 0.30 | 0.07 | 0.03 | 0.60 |

  (Diagonal ≈ 0.57–0.60 → expected dwell ≈ 2.3–2.5 quarters; dominant
  off-diagonal is the next season in the cycle.)

- **`resolve_quadrant(classification) -> str`** — maps a `SeasonsClassification`
  to one of the 4 states. If `season` is canonical, return it. If
  `"Transitioning"`, derive the quadrant from the marker coordinates the
  classifier already computes: growth rising ⟺ `marker_x_pct >= 50`, inflation
  rising ⟺ `marker_y_pct >= 50`, then:
  - rising growth + falling inflation → **Spring**
  - rising growth + rising inflation → **Summer**
  - falling growth + rising inflation → **Autumn**
  - falling growth + falling inflation → **Winter**

  (These are the same axis thresholds `classify_four_seasons` uses, so the
  resolution is consistent with the quadrant marker the dashboard renders.)

## 4. Markov core

Pure, **deterministic** — matrix arithmetic, no RNG (so identical inputs always
reproduce identical output; the payload is cached).

```python
def markov_outlook(current_season: str, *, steps: int = 4) -> MarkovOutlook: ...
```

- Validates `current_season` is one of `SEASON_ORDER` (else `ValueError`).
- `distribution` — next-quarter probabilities over the 4 seasons (the matrix row
  for `current_season`).
- `persistence` — P(stay) = the diagonal entry (= `distribution[current_season]`).
- `most_likely_next` — the season with the max next-quarter probability (may be
  the current season when persistence dominates).
- `adverse_season` / `adverse_prob` — fixed `"Autumn"` (stagflation, the red
  season) and its next-quarter probability — the headline transition risk.
- `expected_dwell_quarters` — `1 / (1 - persistence)`.
- `horizon_quarters` / `horizon_distribution` — the `steps`-ahead distribution
  via the matrix power `Mⁿ` (default `steps=4`, i.e. one year out).

Returns a frozen `MarkovOutlook` dataclass carrying these fields (distributions
as `dict[str, float]` keyed by season).

## 5. Payload (augment `T2TransitionRisk`)

New Pydantic models in `payloads.py`, mirrored in `dalio_copy/types.ts`
(+ FALLBACK). Probabilities are **decimals 0–1** (the view formats as %); season
labels are plain strings.

- `T2TransitionProb` — `{season: str, prob: float}`
- `T2TransitionProbabilities` —
  `{currentSeason: str, nextQuarter: list[T2TransitionProb], persistence: float,
  mostLikelyNext: str, adverseSeason: str, adverseProb: float,
  expectedDwellQuarters: float, horizonQuarters: int, horizon: list[T2TransitionProb]}`

`T2TransitionRisk` gains a required field `probabilities: T2TransitionProbabilities`.
The existing `intro`/`bull`/`bear`/`keyIndicator` prose fields are unchanged
(model-authored, now grounded by these numbers). The `probabilities` block is
entirely tool-filled (no prose inside it).

## 6. Engine wiring

- **Tool:** new `markov_four_seasons` in `tools/dashboard_tools.py`. It accepts
  the same four indicators as `classify_four_seasons`
  (`pmi`, `gdp_yoy`, `cpi_yoy`, `credit_spread`), calls `classify_four_seasons`
  internally, runs `resolve_quadrant`, then `markov_outlook`, and returns the
  outlook numbers as JSON. Taking the indicators (not a season string) means the
  model cannot pass a wrong/derived season. Registered as the **second** builder
  in `CLASSIFY_TOOL_BY_SLUG["four_seasons"]`
  (`[build_classify_four_seasons_tool, build_markov_four_seasons_tool]`) — the
  list-per-slug registry already exists from the All-Weather work.
- **Prompt:** `_FOUR_SEASONS_WORKFLOW` gains a step to call `markov_four_seasons`
  and fill `transitionRisk.probabilities` verbatim, with an **explicit**
  snake_case-tool-key → camelCase-payload-key mapping (the lesson from
  All-Weather: never say "verbatim" when the key casing differs). The
  `_FOUR_SEASONS_PAYLOAD_SHAPE` `transitionRisk` bullet documents the
  `probabilities` sub-object and the mapping.
- **Run service:** no change — Four Seasons gathers its own indicators; nothing
  user- or cross-dashboard-specific is injected.

## 7. Frontend

Augment the existing transition-risk card in `FourSeasonsView.tsx` (do not add a
new section). Beside the bull/bear prose, render from
`transitionRisk.probabilities`: a next-quarter distribution bar set (4 seasons),
the persistence / most-likely-next / adverse-probability / expected-dwell
readouts, and the 4-quarters-ahead distribution. Reuse the existing T2 bar/stat
visual idiom; tone the adverse read by severity. A stable `data-testid`
(`t2-transition-probabilities`) anchors the view test.

## 8. Error handling

- `markov_outlook` raises `ValueError` if `current_season` is not in
  `SEASON_ORDER`. `resolve_quadrant` always returns a canonical season (it never
  emits `"Transitioning"`), so the tool path cannot produce an invalid state.
- The tool surfaces classifier/markov errors to the engine as a tool error (the
  model cannot fabricate the probabilities).
- The baked matrix's row-stochasticity is asserted in tests (rows sum to 1.0
  within tolerance; entries non-negative).

## 9. Testing

- **`quant/markov` unit tests:** every row of `TRANSITION_MATRIX` sums to 1.0 and
  is non-negative; `persistence` equals the diagonal entry; `distribution` sums
  to 1.0; `resolve_quadrant` returns the correct season for each canonical input
  and for a `"Transitioning"` classification in each of the four marker quadrants;
  `most_likely_next` / `adverse_prob` are correct for a known row;
  `horizon_distribution` equals the hand-computed `M⁴` row (sums to 1.0);
  `expected_dwell_quarters` matches `1/(1-persistence)`; unknown season raises.
- **Payload-fixture validation:** the `T2TransitionProbabilities` instance in the
  TS FALLBACK round-trips into the Pydantic `FourSeasonsData` model.
- **Tool presence:** `CLASSIFY_TOOL_BY_SLUG["four_seasons"]` builds exactly
  `{classify_four_seasons, markov_four_seasons}`.
- **Engine-run test:** a full `four_seasons` `report_dash_mr` run scripts
  classify → markov → emit and validates a populated `transitionRisk.probabilities`.
- **Frontend:** a view test asserting the transition-probabilities sub-card
  renders (next-quarter bars + the stat readouts).

## 10. Build order

1. Baked `TRANSITION_MATRIX` + `SEASON_ORDER` + `resolve_quadrant` + tests.
2. `markov.py` core (`MarkovOutlook`, `markov_outlook`) + unit tests.
3. Payload models + `types.ts` + FALLBACK + fixture-validation test.
4. Tool (`markov_four_seasons`) + registry + prompt update.
5. `FourSeasonsView.tsx` transition-probabilities sub-card + view test.
6. Engine-run test; full lint + targeted suites.

## 11. Decisions on record

- **Baked quarterly transition matrix** (adjustable reference assumptions), vs
  live estimation — baked, consistent with All-Weather.
- **Augment `transitionRisk`** with a typed `probabilities` sub-block, vs a new
  parallel section — augment (numbers beside the narrative; avoids a second
  "transition" section).
- **Richer stat set** (distribution + persistence + most-likely-next + adverse +
  expected dwell + 4-quarter horizon).
- **4-state chain**; `"Transitioning"` resolved to the nearest quadrant via the
  marker coordinates.
