# Macro Research — LLM-Dashboard Redesign (design spec)

- **Date:** 2026-06-03
- **Status:** Approved design, pending implementation plan
- **Scope:** Macro Research (`macro_research`) only. Retail Sentiment is a sibling follow-on (separate spec).
- **Supersedes (data architecture):** `planning/specs/systems/macro-research-dalio-dashboards-design.md`,
  `planning/implementation-plans/2026-04-23-phase-19-macro-research.md`,
  `planning/audits/fix-plans/phase-19-macro-research.md`. The page *layout/visual* design
  in the old systems spec still holds; this spec replaces how the data behind it is produced.

## 1. Problem

Macro Research ships as a polished but inert page. Concretely, today:

- **Frontend is a static mockup.** Every view (`frontend/src/pages/departments/macro_research/*View.tsx`)
  renders a hardcoded April-2026 constant from `frontend/src/lib/macro_research/dalio_copy/*.ts`.
  Views fire `getDashboard(slug)` on mount and **discard the result** (`void setLive`). The header
  reads `LIVE · 42 streaming series` — both fake static strings.
- **Backend produces an unrelated shape.** `DashboardAssembler` (`packages/core/src/openlia/macro_research/assembler.py`)
  runs a tiered T1–T5 pipeline returning `DashboardResult{tiers:[...]}`. The frontend contract
  (`DebtCycleData`, etc.) is a flat presentation object that is ~90% narrative prose. Nobody built
  the adapter between the two; the page ignores the backend entirely.
- **Backend math is partly stubbed.** T2 formulas include placeholders such as
  `tips_yield = "TIP_price * 0 + 1.5"` (constant) and `dxy = "UUP_price * 3.3"` (crude proxy).
- **The data layer is the rigid part.** Macro inputs resolve through a need-id abstraction
  (`packages/core/src/openlia/departments/macro_research.needs.yaml` + a wizard-time adapter LLM
  that authors `CallableSpec`/`field_map`, validated by canary calls, dispatched at runtime via
  `dispatcher.fetch_need(need_id)`). This layer is complex, mis-resolves, and is declared a frozen
  public API ("rigid").

### Why the abstraction is safe to remove for MR

`fetch_need` (the need-id resolver) is **not** used by the report engines. Verified non-test call sites:

- `packages/core/src/openlia/llm/runtime/deterministic.py` — MR T1 + Retail Sentiment `social_posts`.
- `packages/server/src/openlia_server/services/connector_financial_adapter.py` — portfolio quotes,
  `stock_quote` only.

Equity Research (`report_v3`), Earnings Update (`report_eu`), and Morning Briefing (`report_mb`) never
call `fetch_need`. EU/MB use `in_department(dept)` purely to **scope which connector tools the LLM
sees**, then run a tool-use turn loop where the model calls the tools directly. ER builds its own
`ToolCatalog` (`packages/core/src/openlia/llm/runtime/report_v3/tools/registry.py`) plus a native
`web_search` tool. These engines are the proof that the target pattern works.

`in_department` (tool scoping) and the connector layer **stay**. Only the need-id resolution layer
(`needs.yaml`, adapter-LLM resolution, `CallableSpec`/`field_map`, `fetch_need`) is removed — for MR.

## 2. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Remove the need-id/adapter-resolver data layer for MR (and RS, later). | Complex, error-prone, rigid; not used by the report engines. |
| D2 | Replace it with an LLM tool-use agent: `in_department`-scoped connector tools + native `web_search` + deterministic quant tools. | The EU/MB pattern; provider-agnostic (the LLM adapts to whatever tools exist). |
| D3 | Scheduled execution + DB cache. Page reads cache; "Refresh now" re-triggers. | An LLM+web pass per dashboard is ~30-90s and costs tokens; macro moves slowly. Mirrors EU/MB. |
| D4 | Keep every existing tile; build real quant. | Highest fidelity to the current design; no fabricated numbers. |
| D5 | Live-compute where inputs are sourceable; curated versioned reference data where series are historical/slow-moving. | Some tiles (1900–2026 composites) cannot be live-sourced; curated published data is honest, static is not fake. |
| D6 | Two independent engines: `report_dash_mr` now, `report_dash_rs` later. | User chose decoupled engines; RS also has an unresolved data-source question. |
| D7 | Web search is the macro backbone; financial connector is "quotes + whatever indicators it has". | No retail financial API serves COFER/TIC/interest-coverage; MR's hard data was always a web-extraction product. |

## 3. Goals / Non-goals

**Goals**
- Every visible MR number is either live-computed from cited inputs or labeled curated reference data.
- The page works regardless of which financial connector the user configured (EODHD / FMP / custom),
  degrading per-tile and honestly when a source is unavailable.
- Preserve the existing UI design and the cross-department `MRSnapshot` contract consumed by Morning Briefing.

**Non-goals**
- No visual/layout redesign.
- No changes to ER / EU / MB / chat.
- No system-wide removal of the need-id layer.
- Retail Sentiment implementation (separate spec).

## 4. Architecture

### 4.1 Engine: `report_dash_mr` (core)

New engine under `packages/core/src/openlia/llm/runtime/report_dash_mr/`, forked in the EU/MB lineage
(single-model tool-use loop, ledger-backed citations, event emitter, typed final emit). Per dashboard
slug it runs one loop and emits one typed payload.

Tool surface assembled per run (`build_catalog`-style):

- **Connector tools** — the user's configured connectors, scoped by `in_department("macro_research")`.
  These are whatever tools the connectors expose (quotes, fundamentals, macro endpoints). No need-ids.
- **Native `web_search`** — the macro backbone and universal fallback for any input no connector covers.
- **Quant tools** — thin tool wrappers over the deterministic quant modules (§4.3). The agent passes
  gathered series in; the tool returns computed numbers. This keeps the math out of the model.

The agent gathers raw inputs (each citation recorded in the ledger), calls quant tools for the hard
numbers, writes the narrative tiles, and emits the dashboard's typed payload (§5).

### 4.2 Execution and caching (D3)

```
cron (per-dashboard cadence) ──► report_dash_mr run(slug)
                                    └─► typed payload + provenance ──► DB cache (mr_dashboard_cache)
page open ───────────────────────► read cache (instant, with as-of + staleness)
auto-refresh ────────────────────► re-read cache (no agent run)
"Refresh now" (per dashboard) ───► enqueue agent run(slug) ──► update cache
```

- Scheduler reuses the existing job/scheduler infrastructure (the same path EU/MB use; MR already has
  `JobType.MR_ASSESSMENT` and an assessment scheduler — repurpose it to drive `report_dash_mr` runs).
- Default cadences (configurable per dashboard): debt_cycle / four_seasons daily; world_order /
  five_forces weekly; summary daily. Curated-reference-only fields refresh on dataset version bumps, not on schedule.
- Cache row carries: payload JSON, `generated_at`, `sources_count`, per-input provenance, model ref,
  token usage, and a computed `is_stale` (TTL per dashboard).

### 4.3 Three isolated layers

1. **Deterministic quant** (`packages/core/src/openlia/macro_research/quant/`, pure Python, unit-tested):
   - `classification.py` — RAG buckets, phase/season/stage classification. Port the sound logic from
     today's `dashboards/*.py` `T3_compute`; drop the stubbed T2 formulas.
   - `risk_parity.py` — keep existing `risk_math.py` logic.
   - `markov.py` — quarterly growth/inflation regime transition matrix over a sourced ~12y window.
   - `montecarlo.py` — scenario simulation from current vols/correlations.
   - `var_causality.py` — VAR(2) causality over a sourced post-1970 window.
   - Each is a pure function: `(input series) -> typed result`. No I/O, no LLM, no network.
2. **LLM agent** (`report_dash_mr`) — gather, compute (via quant tools), narrate, assemble payload.
3. **Curated reference data** (`packages/core/src/openlia/macro_research/reference/`, versioned static):
   1900–2026 empire composites (US + China), regime Sharpe tables, century-scale causality. Each
   dataset has a `version` and `as_of`; surfaced in the payload with a "reference · as-of YYYY" label,
   never a LIVE pill.

## 5. Payload contract

The engine's output schema **is** the existing frontend contract. The typed shapes in
`frontend/src/lib/macro_research/dalio_copy/types.ts` (`DebtCycleData`, `FourSeasonsData`,
`AllWeatherData`, `WorldOrderData`, `FiveForcesData`, `SummaryData`) become the authoritative payload
definitions. Mirror them as Pydantic models in core (`macro_research/payloads.py`) so the engine emits
validated objects and the server returns them verbatim.

Each field-group in a payload is tagged with a provenance enum: `live` (cited), `computed`
(deterministic quant), or `reference` (curated, with `as_of`). The frontend uses this to render the
correct freshness affordance per tile.

`MRSnapshot` (cross-department, consumed by Morning Briefing via `MacroResearchDepartment.get_current_snapshot`)
is derived from the cached payloads: `debt_cycle_phase` from debt_cycle, `economic_season` from
four_seasons, `active_force_count` from five_forces, plus `generated_at` / `is_stale`. This contract is
preserved unchanged.

## 6. Per-dashboard data and quant plan

Field groups map to one of: live (connector/web, cited), computed (deterministic), reference (curated).

### T1 Debt Cycle
- live: debt/GDP, interest/revenue, TIPS real yield, DXY, Fed funds, deficit (replaces stubbed formulas)
- computed: RAG buckets, phase classification, monetary-space scoring
- live + narrative: historical analog, time-to-constraint, gold/long-bond theses, watchlist, verdict

### T2 Four Seasons
- live: PMI, GDP YoY, CPI/core CPI, credit spreads
- computed: quadrant z-scores + marker placement, **Markov transition matrix** (12y window), transition risk
- reference: regime Sharpe playbook table
- narrative: transition triggers, synthesis

### T3 All-Weather
- live: portfolio holdings (from portfolio layer), current vols/correlations
- computed: coverage radar, risk-parity allocation, **Monte-Carlo** stress scenarios
- reference: historical stress-episode returns (Stagflation '70, GFC '08, COVID, Twin Shock)
- narrative: rebalance suggestions, synthesis

### T4 World Order
- live: USD FX reserve share (web/COFER), CB gold purchases, foreign Treasury holdings (TIC), DXY, gold
- computed: composite index, empire-stage classification, internal markers
- reference: 1900–2026 US + China composite series; 1999/2014 reserve snapshots
- narrative: conflict ladder, historical analogs, synthesis

### T5 Five Forces
- computed: F1 from T1, F3 from T4, F2/F4/F5 dedicated modules; composite; **VAR causality** (post-1970)
- reference: century-scale causality reference graph (labeled)
- narrative + Monte-Carlo: scenario probabilities; watchlist; synthesis

### Summary
- live: growth nowcast, core PCE, FCI, 10Y, cross-asset quotes, central-bank rates, yield curve, calendar
- computed: regime quadrant composite, per-dashboard mini-states
- narrative: today's-read headline (Morning Briefing tie-in), flashpoints

## 7. Removed / migrated (MR only)

**Deleted:**
- `packages/core/src/openlia/departments/macro_research.needs.yaml`
- MR entries in the adapter-LLM resolution and any MR `CallableSpec`s
- `packages/core/src/openlia/macro_research/assembler.py` (tiered T1–T5) and the stubbed T2 formulas
- The `fetch_mr_t1_data` path in `deterministic.py` (MR portion)
- `dalio_copy/*.ts` fallback data files (after each view is migrated)

**Migrated / preserved:**
- Sound classification + risk math from `dashboards/*.py` → `quant/`
- `in_department` tool scoping and the connector layer — unchanged
- Portfolio's `fetch_need("stock_quote")` → a small direct-quote helper so the portfolio price layer
  is unaffected by MR's need-id removal
- `MRSnapshot` contract — unchanged, re-derived from the new cache

## 8. Server layer

- **Routes** (`routes/departments/macro_research.py`): `GET /dashboards/{slug}` returns the cached typed
  payload (+ as-of/staleness); `POST /dashboards/{slug}/refresh` enqueues an agent run; keep schedule
  config endpoints. Drop the threshold-override and smart-mode plumbing tied to the old tiered model
  (re-evaluate later if needed).
- **Services:** replace `MRRunner`/`MRAssessmentBuilder`/`DashboardAssembler` wiring with a
  `report_dash_mr` run service + cache store. Reuse the EU/MB render/scheduler service shape.
- **DB:** `mr_dashboard_cache` (per user-or-global, per slug: payload JSON, provenance, generated_at,
  is_stale, model ref, tokens). Migration adds it; deprecate `mr_assessment_cache` tiered schema.
- **Wiring (`app.py`):** instantiate the `report_dash_mr` runner + cache store on `app.state`; wire the
  scheduler job to it. Remove the old `DashboardAssembler` instantiation.

## 9. Provider-agnostic resolution (D2, D7)

- The agent is handed whatever connector tools the user configured (scoped by `in_department`) plus
  native `web_search`. It is prompted to prefer a structured connector tool for a value and fall back
  to `web_search` against official sources (FRED, IMF, Treasury, CBO, BEA) when no tool covers it.
- **Per-tile honest degradation:** if neither a tool nor web search can substantiate a value, the tile
  renders an explicit "source unavailable" state with the missing input named — never a fabricated
  number. (This kills the current frozen-fallback behavior.)
- **Coverage preflight:** the connector config/wizard already canary-tests connectors. Surface a
  coverage indicator so the user knows up front what their sources can fill.
- The `macro_research` department connector requirements relax: `WEB_SEARCH` required (backbone),
  `FINANCIAL` optional (quotes + whatever indicators it has), `NEWS` optional.

## 10. Testing

- **Quant modules:** fixture-based unit tests (known series → known matrix/scenario/classification).
- **Engine:** a fake tool surface (deterministic stub connector + stub web_search) + golden typed-payload
  assertions; assert provenance tags and that no field is emitted without a citation or `reference`/`computed` tag.
- **Cache/scheduler:** mirror EU/MB tests (run → cache write → read; refresh enqueue).
- **Server routes:** payload read + refresh enqueue.
- **Frontend:** replace fallback-render tests with mocked-cache-fetch tests; add skeleton + degraded-tile tests.
- Note: full `packages/server` pytest hangs on SSE/stream tests; run targeted dirs.

## 11. Risks and open questions

- **Historical series sourcing** is the long pole. Markov needs ~12y quarterly GDP/CPI (sourceable);
  VAR's century inputs do not exist as series — scoped to post-1970 live + curated century graph.
- **Curated dataset stewardship:** who updates the 1900–2026 composites and on what cadence; versioning format.
- **Cost/latency per run** across 5 dashboards + summary; cadence tuning to control token spend.
- **Open:** exact per-dashboard TTLs; whether cache is per-user or global (global is cheaper; per-user
  only if portfolio-dependent tiles like All-Weather demand it — likely All-Weather is per-user, the
  rest global).

## 12. Out of scope / follow-ons

- **Retail Sentiment** (`report_dash_rs`): same pattern, separate spec, after MR proves it and after the
  RS data-source question (no per-post social text) is resolved.
- ER / EU / MB / chat: untouched.
- System-wide need-id removal: not pursued.
