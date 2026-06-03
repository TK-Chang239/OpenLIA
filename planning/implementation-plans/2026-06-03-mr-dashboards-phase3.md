# MR Dashboards Phase 3 — All-Weather + Five Forces + Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Bring the last three Macro Research dashboards live — All-Weather (T3, per-user portfolio audit), Five Forces (T5, depends on T1/T4), and Summary (aggregates all five) — completing the dashboard set.

**Architecture:** Same `report_dash_mr` per-slug engine + cached-payload pattern proven in Phases 1-2. The NEW piece this round is **server-side data injection**: unlike T1/T2/T4 (whose inputs the LLM gathers from the web), these three need inputs the LLM cannot fetch — the user's portfolio holdings (All-Weather), and other dashboards' cached classifications (Five Forces, Summary). The run service loads that data and injects it into the run via a new `RunRequest.data_context` free-text block; the LLM reads it and calls the per-slug classify tool / synthesizes. Heavy quant (Monte-Carlo stress, VAR causality) stays deferred → LLM narrative with honest provenance.

**Tech Stack:** Python (Pydantic v2, numpy via existing `risk_math`), `report_v2_3.research` tool API, React/TS/Vite, vitest, pytest.

**Reference pattern (read first):** the World Order slice from Phase 2 is the closest template —
- payloads: `packages/core/src/openlia/macro_research/payloads.py` (DebtCycleData / WorldOrderData / FourSeasonsData + sub-models)
- classifiers: `packages/core/src/openlia/macro_research/quant/{classification,world_order,seasons}.py`
- tools + registries: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py` (PAYLOAD_MODEL_BY_SLUG, CLASSIFY_TOOL_BY_SLUG)
- prompts: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py` (DASHBOARD_PROMPT_SPECS)
- engine tests: `packages/core/tests/runtime/report_dash_mr/test_runner_world_order.py`
- run service: `packages/server/src/openlia_server/services/mr_dash_run_service.py` (build_run_request, run_to_cache)
- frontend live views: `frontend/src/pages/departments/macro_research/{WorldOrderView,DebtCycleView}.tsx`

**Authoritative payload shapes** = `frontend/src/lib/macro_research/dalio_copy/types.ts`:
- AllWeatherData: lines 303-341 (keys: header, cardSummary, comparison, coverage, riskParity, gold, caveats, verdict, sources)
- FiveForcesData: lines 549-582 (keys: header, cardSummary, scorecard, loops, signals, goldAllocation, scenarios, verdict, sources)
- SummaryData: lines 584-704 (keys: hero, liaTake, regimeBar, frameworkStatus, depMap, cascade, watchlist, sources)
The fallback files `dalio_copy/{all_weather,five_forces,summary}.ts` are valid instances of these (the static views typecheck against them) — use them as test fixtures.

**Data available (recon-confirmed):**
- Portfolio holdings: `openlia_server.services.portfolio.list_holdings(session, user_id=...) -> list[HoldingDTO]` (HoldingDTO: ticker, name, shares: Decimal|None, cost_basis: Decimal|None, currency, groups, ...).
- Cross-dashboard cache: `session.query(MrDashboardCache).filter_by(user_id=..., dashboard=<slug>).one_or_none()` → `json.loads(row.payload_json)`.
- All-Weather quant already exists: `openlia.macro_research.risk_math` (DEFAULT_VOLS, REFERENCE_ALLOCATION, SEASON_ASSETS, risk_contributions, coverage_for_season, gold_gap).

**Scope decisions (carry over from Phase 2):** defer heavy statistical quant; replicate the proven slice pattern. **Deferred to a later follow-up (NOT this round):** the `get_current_snapshot` rewire in `departments/macro_research.py` to read `MrDashboardCache` instead of the legacy `mr_assessment_cache` (a cross-department Morning Briefing contract change). This round only ADDS the `active_force_count_from_payload` snapshot helper (parallel to the existing debt_cycle/economic_season helpers).

---

## Task 1: `data_context` injection plumbing (foundational)

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/schemas.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`
- Test: `packages/core/tests/runtime/report_dash_mr/test_prompts_data_context.py`

- [ ] **Step 1:** Add an optional field to `RunRequest` (schemas.py): `data_context: str | None = None`.
- [ ] **Step 2:** Render it in `prompts.py`. Add a helper mirroring `_render_instructions_block`:
```python
def _render_data_context_block(data_context: str | None) -> str:
    """Server-provided inputs for this run (portfolio holdings, other
    dashboards' cached states). Distinct from user analyst instructions:
    this is factual data the model must use, not methodology."""
    if not data_context or not data_context.strip():
        return ""
    return (
        "# Provided inputs for this run\n\n"
        "The following data was gathered for you by the system. Treat it as "
        "authoritative ground truth for this run; do not contradict it.\n\n"
        f"{data_context.strip()}\n\n"
    )
```
Thread it into `build_system_prompt` (add `data_context_block=_render_data_context_block(request.data_context)` to the `.format(...)` call) and add `{data_context_block}` to `_PROMPT_TEMPLATE` immediately before `{instructions_block}` (so provided data precedes user methodology). Both blocks already end with two newlines, so they collapse cleanly when empty.
- [ ] **Step 3:** TDD test: `build_system_prompt` with `data_context="FOO_BAR_TOKEN"` includes "Provided inputs for this run" and the token; with `data_context=None` the block is absent. (Build a minimal RunRequest with dashboard_slug="debt_cycle".) Run `uv run pytest packages/core/tests/runtime/report_dash_mr/ -q` → PASS (existing tests unaffected since data_context defaults None).
- [ ] **Step 4: Commit** `feat(mr): RunRequest.data_context injection block`.

---

## Task 2: All-Weather payload model

**Files:** Modify `payloads.py`; Test `packages/core/tests/macro_research/test_payloads_all_weather.py`; shape `types.ts:248-341`; fixture `dalio_copy/all_weather.ts`.
- [ ] TDD: validate `AllWeatherData` against a fixture transcribed from `ALL_WEATHER_FALLBACK` + `generated_at`. RED → implement → GREEN.
- [ ] Add `AllWeatherData` + `T3*` sub-models mirroring `types.ts:248-341` verbatim (camelCase exact). Reuse shared `Tone` (T3Tone is red/amber/green/blue — same as `Tone`). Sub-models: T3Pill, T3DonutSlice (`tone: Literal["accent","olive","neutral","amber","rust"]` — its OWN scale, define `T3SliceTone` locally), T3DonutCard, T3CoverageCell, T3RiskBar, T3GoldNeedle, T3GoldStat, T3CaveatCard, plus nested groups: comparison{label, benchmark: T3DonutCard, reference: T3DonutCard}, coverage{label, cells}, riskParity{label, intro, benchmarkTitle, benchmarkBars, referenceTitle, referenceBars, mechanism:{title,body}}, gold{label, title, needles, stats, rationale:{title,body}}, caveats{label, cards}, verdict{title, body} (NOTE: T3 verdict has NO tone — use a plain `Prose`-like model, not `TonedProse`). Header: T3 header.pills is T3Pill[] with `tone: Tone` → `DashHeader` works (Pill={tone: Tone, label}). Append `provenance` + `generated_at`. Commit `feat(mr): AllWeatherData payload model`.

---

## Task 3: All-Weather classifier (wrap existing risk_math)

**Files:** Create `packages/core/src/openlia/macro_research/quant/all_weather.py`; Test `packages/core/tests/macro_research/test_all_weather_classify.py`.
- [ ] TDD: a concentrated portfolio ({"equities":0.9,"long_bonds":0.1}) → severity "red"/label "Concentrated"; a balanced ref-like allocation → "green"/"Balanced". Assert risk_contributions sum≈1, season_coverage keys = the four seasons, gold_gap dict shape.
- [ ] Implement `classify_all_weather(weights: dict[str, float]) -> AllWeatherClassification` PORTING the legacy `dashboards/all_weather.py` `T3_compute` (reuse `risk_math.risk_contributions`/`coverage_for_season`/`gold_gap` + DEFAULT_VOLS/REFERENCE_ALLOCATION/SEASON_ASSETS). Logic verbatim: rc_user, rc_ref, season_coverage per season, gold_gap on weights.get("gold",0), severity by max_rc (>0.6 red/"Concentrated", >0.4 amber/"Moderately concentrated", else green/"Balanced"). Dataclass:
```python
@dataclass(frozen=True)
class AllWeatherClassification:
    severity: Literal["red", "amber", "green"]
    overall_coverage_label: str
    risk_contributions: dict[str, float]
    reference_risk_contributions: dict[str, float]
    season_coverage: dict[str, str]
    gold_gap: dict[str, float]
```
(The asset-class taxonomy is the risk_math keys: equities, long_bonds, intermediate_bonds, gold, commodities.) Commit `feat(mr): all_weather classifier wrapping risk_math`.

---

## Task 4: All-Weather classify tool + prompt + register + portfolio injection

**Files:** Modify `dashboard_tools.py`, `prompts.py`, and `services/mr_dash_run_service.py`.
- [ ] `build_classify_all_weather_tool()` in dashboard_tools.py: one param `weights` (object mapping asset-class → fraction, additionalProperties number) — execute coerces to dict[str,float], calls classify_all_weather, returns ToolResult payload={severity, overall_coverage_label, risk_contributions, reference_risk_contributions, season_coverage, gold_gap}, ComputedSource(method="classify_all_weather"). Register `all_weather` in PAYLOAD_MODEL_BY_SLUG + CLASSIFY_TOOL_BY_SLUG.
- [ ] Add `all_weather` DASHBOARD_PROMPT_SPECS entry. indicator_hint = "current cross-asset volatilities and any benchmark allocation context." workflow: 1) Read the user's portfolio weights from the "Provided inputs" block; 2) call classify_all_weather with those weights and use the returned risk_contributions/season_coverage/gold_gap/severity verbatim; 3) gather current vols/correlations and historical stress-episode context (web), write the comparison donuts, coverage cells, risk-parity bars, gold needle/stats, caveats (the Monte-Carlo stress is described qualitatively — label it as scenario reasoning, not a simulated distribution), and the verdict; 4) emit_dashboard once with full AllWeatherData. payload_shape: transcribe AllWeatherData keys from types.ts:303-341 as a single-brace block (tones red/amber/green/blue; donut slice tones accent/olive/neutral/amber/rust; pct integers).
- [ ] In `mr_dash_run_service.py`: add `_portfolio_weights(db, user_id) -> dict[str, float]` that calls `portfolio.list_holdings(db, user_id=user_id)`, maps each holding to an asset class (simple heuristic: a small TICKER_ASSET_CLASS map for common ETFs — e.g. SPY/VTI/QQQ→equities, TLT/EDV→long_bonds, IEF/BND→intermediate_bonds, GLD/IAU→gold, DBC/GSG→commodities; default unknown tickers to "equities"), weights by `shares * cost_basis` (fallback equal-weight when cost_basis missing), normalized to sum 1.0; returns {} if no holdings. Add `_build_data_context(db, user_id, dashboard_slug) -> str | None` that, for `all_weather`, formats the weights dict (and a note when holdings are empty → "No portfolio holdings on file; audit a Dalio reference 60/40 as the user proxy."). Wire `build_run_request` to set `data_context=_build_data_context(...)`. Run `uv run pytest packages/core/tests/runtime/report_dash_mr/ -q` + `packages/server/tests/test_macro_research/ -q` → PASS. Commit `feat(mr): wire all_weather classify tool, prompt, portfolio injection`.

---

## Task 5: All-Weather engine run test
**Files:** `packages/core/tests/runtime/report_dash_mr/test_runner_all_weather.py`
- [ ] Mirror test_runner_world_order: dashboard_slug="all_weather", RunRequest with a `data_context` containing sample weights; fake session scripts classify_all_weather then emit_dashboard with valid AllWeatherData; assert completed + payload validates. Commit `test(mr): all_weather engine run`.

## Task 6: All-Weather live view
**Files:** `frontend/.../AllWeatherView.tsx`; extend `__tests__/Views.test.tsx`.
- [ ] Convert AllWeatherView to the DebtCycleView/WorldOrderView live pattern (copy machinery; `getDashboard<AllWeatherData>("all_weather")` / `runAssessment("all_weather")`; DashLoading/DashEmpty guards; keep JSX body + helpers unchanged; remove ALL_WEATHER_FALLBACK import; capture-but-unused generatedAt). Add WorldOrder-style live + generate→poll tests. `npx vitest run .../Views.test.tsx` + `npm run lint` → green. Commit `feat(mr): all_weather live view`.

---

## Task 7: Five Forces payload model
**Files:** `payloads.py`; Test `test_payloads_five_forces.py`; shape `types.ts:484-582`; fixture `five_forces.ts`.
- [ ] TDD against FIVE_FORCES_FALLBACK fixture. Add FiveForcesData + T5* sub-models mirroring types.ts:484-582 verbatim. Reuse `Tone` (T5Tone is red/amber/green/blue). Sub-models: T5HeaderBadge, T5ForceRow, T5LoopArrow, T5LoopBlock, T5ActiveCount, T5SignalCard, T5AllocStat, T5GoldAllocation, T5Scenario (`variant: Literal["bull","bear"]`); groups: header{title,subtitle,badges: list[T5HeaderBadge]} (dedicated T5Header — header has `badges` not `pills`), scorecard{label, rows}, loops{label, blocks, active: T5ActiveCount}, signals{label, cards}, goldAllocation{label, block: T5GoldAllocation}, scenarios{label, cards}, verdict{title, body} (no tone). Append provenance + generated_at. Commit `feat(mr): FiveForcesData payload model`.

## Task 8: Five Forces classifier (port)
**Files:** Create `quant/forces.py`; Test `test_forces_classify.py`.
- [ ] TDD: all-low forces → "Normal"/green/active 0; three ≥7 → "Elevated"/amber/active 3; four ≥7 → "Historical turning point zone"/red/active 4.
- [ ] Implement `classify_five_forces(scores: ForceScores) -> ForcesClassification` porting legacy `dashboards/five_forces.py` T3_compute. `ForceScores` dataclass: debt_money, political, geopolitical, technology, natural (floats 0-10). active = count(score>=7); bucket Normal(≤1)/Elevated(≤3)/"Historical turning point zone"(>3); severity green/amber/red. Output: force_scores dict, active_force_count, bucket, severity. Commit `feat(mr): five_forces classifier`.

## Task 9: Five Forces classify tool + prompt + register + cross-dashboard injection + snapshot helper
**Files:** `dashboard_tools.py`, `prompts.py`, `mr_dash_run_service.py`, `snapshot.py` (+ its test).
- [ ] `build_classify_five_forces_tool()`: five numeric params (debt_money, political, geopolitical, technology, natural); returns payload {force_scores, active_force_count, bucket, severity}, ComputedSource(method="classify_five_forces"). Register `five_forces` in both maps.
- [ ] `five_forces` DASHBOARD_PROMPT_SPECS entry. indicator_hint = "any current readings that bear on geopolitical, technological, and natural-disaster stress." workflow: 1) Read the seeded force scores in "Provided inputs" — F1 (debt/money) derived from the cached Debt Cycle state and F3 (geopolitical) from the cached World Order state; 2) research and score the remaining forces F2 (internal political/social order), F4 (technology), F5 (acts of nature) on a 0-10 intensity scale; 3) call classify_five_forces with all five scores and use the returned active_force_count/bucket/severity verbatim; 4) write the force scorecard rows, interlocking loops + active-count block, signal cards, gold-allocation block, bull/bear scenarios, and verdict; 5) emit_dashboard once. payload_shape from types.ts:549-582 (single-brace; tones red/amber/green/blue; pcts integers).
- [ ] In `mr_dash_run_service.py`: extend `_build_data_context` for `five_forces` — load cached `debt_cycle` + `world_order` payloads (helper `_cached_payload(db, user_id, slug) -> dict | None`); derive F1 from debt_cycle (map phaseBox.tone red→8/amber→5/green→3, include the phase title) and F3 from world_order (map verdict.tone similarly, include the stage); format a context block stating the two seeded scores + their source states, and note honestly when a source dashboard has not been generated yet ("Debt Cycle not yet generated; research the debt/money force from official sources.").
- [ ] In `snapshot.py`: add `active_force_count_from_payload(payload: FiveForcesData) -> int` returning `payload.loops.active.countText` parsed to int — BUT countText is a display string; instead derive from the count of scorecard rows whose pill indicates active, OR (cleaner) return the integer by counting `scorecard.rows` with `scoreTone == "red"`... DECISION: the robust source is the active-count block — add the integer to the payload is not allowed (must match types.ts). Implement by parsing the leading integer out of `loops.active.countText` (e.g. "3 / 5" → 3); fail loud (ValueError) if no leading int. Add a unit test with a sample FiveForcesData. (This mirrors how economic_season is derived from rendered fields.)
- [ ] Run `uv run pytest packages/core/tests/ -q -k "report_dash_mr or macro_research"` + `packages/server/tests/test_macro_research/ -q` → PASS. Commit `feat(mr): wire five_forces tool, prompt, cross-dashboard injection, snapshot helper`.

## Task 10: Five Forces engine run test
**Files:** `test_runner_five_forces.py` — mirror world_order with dashboard_slug="five_forces", data_context seeding F1/F3, session scripts classify_five_forces then emit_dashboard with valid FiveForcesData. Commit `test(mr): five_forces engine run`.

## Task 11: Five Forces live view
**Files:** `FiveForcesView.tsx` + Views.test.tsx — DebtCycleView live pattern, `getDashboard<FiveForcesData>("five_forces")`/`runAssessment`, keep JSX/helpers, add tests, vitest + lint green. Commit `feat(mr): five_forces live view`.

---

## Task 12: Summary payload model
**Files:** `payloads.py`; Test `test_payloads_summary.py`; shape `types.ts:584-704`; fixture `summary.ts`.
- [ ] TDD against SUMMARY_FALLBACK fixture. Add SummaryData + sub-models mirroring types.ts:584-704 verbatim. Note tricky shapes: `Status = Literal["ok","warn","bad","flat","info","acid"]` (the shared Status used across summary sub-models — define it locally in payloads.py); FrameworkStatusCard (tcode Literal["T1".."T5"], miniVisual Literal["bars","quadrant","ring","stage","forces"], `miniData: list[float] | MiniActive` where `MiniActive` is {active: bool, index: int | None} — use a Union; spotlight/spotlightChart optional), LiaTake.pulls is a fixed 4-tuple → `tuple[LiaPull, LiaPull, LiaPull, LiaPull]`, DepMapNode (position Literal), DepMapEdge (variant Literal), CascadeStep, ConsolidatedTrigger, RegimeBarSegment. Groups: hero, liaTake, regimeBar, frameworkStatus{label, subLabel, cards}, depMap{label, subLabel, sub, nodes, edges}, cascade{label, subLabel, sub, row1, row2}, watchlist{label, subLabel, triggers}, sources. Append provenance + generated_at. Commit `feat(mr): SummaryData payload model`.

## Task 13: Summary prompt + register + all-dashboard injection (no classifier)
**Files:** `dashboard_tools.py` (register payload only), `prompts.py`, `mr_dash_run_service.py`.
- [ ] Register `summary` in PAYLOAD_MODEL_BY_SLUG only (NO classify tool — Summary is pure synthesis; CLASSIFY_TOOL_BY_SLUG.get returns None and build_catalog already handles that).
- [ ] `summary` DASHBOARD_PROMPT_SPECS entry. indicator_hint = "a growth nowcast, core PCE, a financial-conditions index, the 10-year yield, key cross-asset quotes, central-bank policy rates, the yield-curve slope, and the economic calendar." workflow: 1) Read the cached per-dashboard states in "Provided inputs" (Debt Cycle phase, Four Seasons season, World Order stage, All-Weather coverage, Five Forces active count + severities); 2) gather the live macro signals above (web/tools); 3) synthesize the SummaryData — the hero read, the LIA take (4 pulls), the regime bar, ONE frameworkStatus card per dashboard reflecting its cached state (tcode/title/stamp/summary/miniVisual/stats), the dependency map + cascade narrative, and the consolidated watchlist drawn from the individual dashboards' watchlists; 4) emit_dashboard once with full SummaryData. payload_shape: transcribe SummaryData keys from types.ts:584-704 (single-brace; Status values ok/warn/bad/flat/info/acid; miniVisual one of bars/quadrant/ring/stage/forces).
- [ ] In `mr_dash_run_service.py`: extend `_build_data_context` for `summary` — load all five cached payloads (`_cached_payload` for each), extract each one's headline state (debt_cycle phaseBox.title+tone, four_seasons verdict + derived season, world_order verdict.title+stage, all_weather verdict + coverage label, five_forces verdict + active count), format into the context with honest notes for any not-yet-generated dashboard.
- [ ] Run core + server MR tests → PASS. Commit `feat(mr): wire summary prompt + all-dashboard injection`.

## Task 14: Summary engine run test
**Files:** `test_runner_summary.py` — dashboard_slug="summary", data_context seeding the five states, session scripts a single emit_dashboard with valid SummaryData (no classify call). Assert completed + payload validates. Commit `test(mr): summary engine run`.

## Task 15: Summary live view
**Files:** `SummaryView.tsx` + Views.test.tsx — convert from `SUMMARY_FALLBACK` to live `getDashboard<SummaryData>("summary")`/`runAssessment("summary")` with the DebtCycleView machinery (note SummaryView is short, ~48 lines, with `const data = SUMMARY_FALLBACK`); keep render body + sub-components; add tests; vitest + lint green. Commit `feat(mr): summary live view`.

---

## Task 16: Enable Run Now + full verification
- [ ] `MRSettingsPanel.tsx`: `IMPLEMENTED_DASHBOARDS = ["debt_cycle","world_order","four_seasons","all_weather","five_forces","summary"]`. Update `MacroResearch.test.tsx`'s settings-drawer test to expect all six runnable and none excluded (delete the now-empty unimplemented assertions, or assert the two formerly-excluded slugs are now present).
- [ ] `uv run pytest packages/core/tests/macro_research/ packages/core/tests/runtime/report_dash_mr/ packages/server/tests/test_macro_research/ -q` → all green.
- [ ] `uv run ruff check . && uv run ruff format --check .` → clean (format touched files).
- [ ] `cd frontend && npx vitest run && npm run lint` → green (modulo pre-existing SettingsShellBlocker error), tsc clean.
- [ ] Update this plan + spec if diverged (CLAUDE.md rule 9). Commit `feat(mr): enable all six dashboards + Phase 3 verification`.

---

## Notes / deferred (NOT this round)
- `get_current_snapshot` rewire (read MrDashboardCache + use snapshot.py helpers, replacing legacy mr_assessment_cache) — cross-department Morning Briefing contract; its own follow-up. This round only adds the `active_force_count_from_payload` helper.
- Heavy quant (Monte-Carlo stress, VAR causality, Markov) — LLM narrative for now.
- Curated reference datasets (century composites, stress-episode return tables) — LLM-sourced with `reference` provenance.
- Deleting `dalio_copy/*.ts` fallback files — defer until confident no test/import depends on them.
