# Macro Research — Heavy Quant: All-Weather Monte-Carlo Stress (design spec)

- **Date:** 2026-06-03
- **Status:** Approved design, pending implementation plan
- **Scope:** All-Weather (T3) dashboard only. This is the first of three deferred
  "heavy quant" engines; Four Seasons Markov and Five Forces VAR are sibling
  follow-ons (separate specs). Each is independent.
- **Builds on:** `planning/specs/systems/macro-research-llm-dashboard-redesign.md`
  (the `report_dash_mr` engine, per-slug classifier + tool + prompt pattern).

## 1. Problem

The redesigned All-Weather dashboard computes its risk numbers deterministically
(`macro_research/quant/all_weather.py` on top of `risk_math.py`: linear risk
contributions, per-season coverage, gold gap). But its **stress narrative is
LLM prose** — the prompt explicitly instructs the model to *"describe stress
scenarios qualitatively as reasoning, NOT as a simulated distribution."* There
is no actual simulation of how the portfolio behaves under adverse regimes, and
no quantified tail risk.

This spec adds a deterministic **Monte-Carlo stress engine**: it simulates the
1-year joint return distribution of the user's portfolio (and the Dalio
reference allocation) under a baseline and several baked adverse regimes, and
surfaces the result as a new typed dashboard section.

## 2. Goals / non-goals

**Goals**
- Replace the qualitative stress narrative with quantified, deterministic,
  reproducible simulation output.
- Compare the **user portfolio vs the Dalio reference allocation** (the
  dashboard's existing theme) under stress.
- Ship a **baseline distribution** (percentiles) and **named stress scenarios**.
- Render the result as a dedicated, deterministic UI card (not LLM prose).

**Non-goals**
- No new data fetching. All statistical parameters are **baked reference
  values** (consistent with how `risk_math.DEFAULT_VOLS` already works). Live
  historical fetch is explicitly out of scope (a separate, larger effort).
- No Four Seasons Markov or Five Forces VAR work (sibling specs).
- No Student-t / fat-tail model in v1 (noted as a future refinement; stress is
  carried by scenario overlays instead).

## 3. Data: baked reference parameters

Added to `packages/core/src/openlia/macro_research/risk_math.py` (beside the
existing `DEFAULT_VOLS` / `REFERENCE_ALLOCATION`), documented as adjustable
reference assumptions over the existing five asset classes (`equities`,
`long_bonds`, `intermediate_bonds`, `gold`, `commodities`):

- **`EXPECTED_RETURNS`** — long-run annualized nominal expected return per asset.
  Initial values: `equities 0.07`, `long_bonds 0.03`, `intermediate_bonds 0.025`,
  `gold 0.03`, `commodities 0.04`.
- **`CORRELATIONS`** — a symmetric 5×5 correlation matrix (unit diagonal),
  expressed as a `dict[tuple[str, str], float]` or a nested dict keyed by asset.
  Combined with `DEFAULT_VOLS` to build the covariance matrix
  `Σ_ij = ρ_ij · σ_i · σ_j`. Initial values reflect long-run cross-asset
  relationships (e.g. equities/commodities mildly positive, long_bonds/equities
  mildly negative, gold weakly correlated with everything).

The covariance builder lives in `risk_math.py` as a small helper
(`covariance_matrix(vols, correlations, order) -> np.ndarray`), so both the
simulator and any future engine reuse it.

## 4. Computation model

New pure-function core module
`packages/core/src/openlia/macro_research/quant/monte_carlo.py`. No I/O, no LLM.

Entry point:

```python
def simulate_all_weather_stress(
    weights: dict[str, float],
    *,
    n_paths: int = 10_000,
    horizon_years: float = 1.0,
    seed: int | None = None,
) -> AllWeatherStress: ...
```

- **Asset universe:** the five `risk_math` classes, in a fixed canonical order.
- **Determinism:** when `seed is None`, derive it from a stable hash of the
  sorted, rounded `weights` (so identical inputs → identical output). This is
  required because the dashboard payload is cached (`mr_dashboard_cache`);
  non-deterministic output would break reproducibility and create diff noise.
  Use `numpy.random.default_rng(seed)`.
- **Per scenario:** build `(μ', Σ')` from the baked params plus the scenario
  overlay, draw `n_paths` 1-year asset-return vectors `~ N(μ', Σ')`, then compute
  the portfolio return `wᵀr` for **both** the user `weights` and
  `REFERENCE_ALLOCATION`. Reduce each to summary metrics.
- **Metrics:** per scenario, per portfolio (user / reference): `median` and
  `p5` (the 5th-percentile 1-yr return, i.e. VaR-95). For the **Base** scenario
  additionally compute `p25 / p50 / p75 / p95` for the distribution card.
- A scenario row's `tone` is derived deterministically from the user's `p5`
  (e.g. `p5 <= -0.20` → red, `<= -0.10` → amber, else green) — a fixed mapping
  in the module, not LLM-decided.

Return dataclass `AllWeatherStress` (frozen): the Base distribution percentiles
(user + reference) plus a list of scenario results.

## 5. Scenarios

Baked as data in `monte_carlo.py` (a list of named overlays). Each overlay can
shift drift per asset (annualized), scale vols (per asset or global), and stress
correlations toward a crisis matrix. v1 ships four:

1. **Base** — baked `μ`, `Σ`, no overlay.
2. **Stagflation** — equities/long_bonds drift down, commodities/gold up; vols up.
3. **Rate Shock** — long_bonds and intermediate_bonds drift hit hard; bond vols up.
4. **Equity Crash / Deleveraging** — large negative equity drift shock,
   correlations stressed toward 1 across risk assets (gold a partial safe haven),
   vols up.

Exact overlay numbers are defined in the implementation plan; they are reference
assumptions and adjustable.

## 6. Payload additions

Mirrored in **both** `packages/core/src/openlia/macro_research/payloads.py` and
`frontend/src/lib/macro_research/dalio_copy/types.ts` (plus the `*_FALLBACK`
instance), added as a new `stressTest` field on `AllWeatherData` (T3). New models:

- **`T3StressBar`** — `{ label: str, userPct: float, refPct: float }` (one row per
  percentile for the distribution card; reuses a simple bar shape).
- **`T3StressScenarioRow`** — `{ name, userMedianPct, userP5Pct, refMedianPct, refP5Pct, tone }`.
- **`T3StressDistribution`** — `{ title, bars: list[T3StressBar] }` (Base p5/p25/p50/p75/p95).
- **`T3StressTest`** — `{ label, intro, distribution: T3StressDistribution, scenarios: list[T3StressScenarioRow], note }`.

`tone` reuses the shared T3 `Tone`. Percentages are stored as decimals (e.g.
`-0.12` for −12%); the view formats them.

## 7. Engine wiring

- **Tool:** new classify-style tool `simulate_all_weather_stress` (separate from
  `classify_all_weather`) in
  `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`,
  registered in `CLASSIFY_TOOL_BY_SLUG` alongside the existing All-Weather tool
  (a slug may expose more than one deterministic tool). It accepts the weights
  and returns the `AllWeatherStress` numbers as JSON.
- **Prompt:** update `_ALL_WEATHER_WORKFLOW` in `prompts.py` — remove the
  *"describe stress scenarios qualitatively … NOT as a simulated distribution"*
  instruction; add a step to call `simulate_all_weather_stress` with the
  authoritative weights and fill `stressTest` from the returned numbers
  **verbatim** (the model writes only the prose `intro` / `note`, never the
  numbers).
- **Run service:** no change. `mr_dash_run_service._build_data_context` already
  supplies the user's portfolio weights for `all_weather`.

## 8. Frontend

A new **Stress Test** card in
`frontend/src/pages/departments/macro_research/AllWeatherView.tsx`, slotted after
the existing `riskParity` section. It renders:
- the Base **distribution** as user-vs-reference percentile bars (reusing the
  existing risk-bar visual idiom), and
- the **scenario table**: one row per scenario with user median / user VaR-95 /
  reference median / reference VaR-95, tinted by `tone`.

No new live-data plumbing — the view already consumes the typed payload from
`getDashboard`.

## 9. Error handling

- The simulator validates that `weights` keys are a subset of the known asset
  classes and renormalizes to sum 1.0; unknown keys raise `ValueError` (fail
  loud, per repo standards).
- Empty weights (user has no holdings) is handled upstream by the existing
  `data_context` proxy-instruction path; the tool is only called when weights
  exist. If called with empty weights it raises `ValueError`.
- The tool surfaces simulator errors to the engine as a tool error (the model
  cannot fabricate the numbers).

## 10. Testing

- **`quant/monte_carlo` unit tests:** seed reproducibility (same inputs → byte-identical
  output); invariants — `Equity Crash` user p5 < `Base` user p5; a 100%-equities
  portfolio has a worse crash p5 than the diversified reference; percentiles are
  monotonically ordered; weight validation/renormalization.
- **Payload-fixture validation:** the `T3StressTest` instance in the TS
  `*_FALLBACK` round-trips into the Pydantic `AllWeatherData` model.
- **Engine-run test:** a full `all_weather` `report_dash_mr` run emits a populated
  `stressTest`.
- **Frontend:** a view test asserting the Stress Test card renders the distribution
  bars and scenario rows.

## 11. Build order

1. Baked params (`EXPECTED_RETURNS`, `CORRELATIONS`, `covariance_matrix`) + tests.
2. `quant/monte_carlo.py` (`AllWeatherStress`, `simulate_all_weather_stress`) + unit tests.
3. Payload models (`payloads.py`) + `types.ts` + `*_FALLBACK` + fixture-validation test.
4. Tool (`simulate_all_weather_stress`) + registry + prompt update.
5. `AllWeatherView.tsx` Stress Test card + view test.
6. Engine-run test; full lint + targeted suites.

## 12. Open questions / decisions

- **Baked μ / correlations are assumptions**, shipped as adjustable reference
  constants. Reviewed and accepted as the chosen approach (vs live fetch).
- **Gaussian draws (no fat tails) in v1.** Stress is carried by explicit scenario
  overlays. Student-t is a documented future refinement.
- **`n_paths = 10_000`, `horizon = 1yr`** — fixed defaults; cheap enough to run
  inline, fine enough for stable percentiles.
