# Retail Sentiment LLM-Dashboard Redesign (`report_dash_rs`)

> **Amendment 2026-06-20:** "web search as the backbone" now means the model's
> **native** web search, not a `WEB_SEARCH` connector. RS requires **no**
> connector category (`required_categories = ()`); `WEB_SEARCH` (a scraping
> connector such as Firecrawl), `FINANCIAL`, and `NEWS` are all optional
> enrichment. The engine already drives `enabled_connectors.web_search` from the
> model's native capability, so the department is active without any connector.

Rebuild the Retail Sentiment (RS) department as the exact sibling of Macro Research's
`report_dash_mr`: a single-model LLM tool-use loop (`gather -> classify -> narrate -> emit`)
with **web search as the backbone**, producing one typed dashboard payload per ticker,
cached and served to a polled frontend, scheduled through the existing job system.

> **Supersedes** `retail-sentiment-dashboard-design.md`. That document describes the
> per-post-classification pipeline (12-metric Pandas engine, batch LLM classifier,
> `RsRunner`). That pipeline is **deleted** by this redesign (see §10). The old spec is
> retained only as a historical record of the shipped-then-retired v1.

> **Sibling spec.** This mirrors `macro-research-llm-dashboard-redesign.md` and reuses
> the connector-requirement relaxation pattern shipped for MR in PR #251. Read that doc
> first; this spec only describes where RS diverges from the MR template.


## 1. Why this exists — the data-source dead-end

The entire existing RS stack (core `retail_sentiment/` package, `RsRunner`, the
Overview/Evidence/Insights frontend, `rs_classification_log`) is built on one data
contract: **a feed of per-post social text to classify**. No connector provides that.

- EODHD's sentiment endpoint returns **daily aggregates** (`date`, `count`, `normalized`)
  — not post text. The `social_posts` need's `field_map` documents this gap explicitly;
  `text`/`source`/per-post `ticker` source paths are absent.
- FMP has no social-sentiment endpoint at all (`fmp.py`: "social_posts is EODHD-only").
- In production `rs_data_provider` is never set on `app.state`, so `RsRunner` always runs
  with `data_provider=None` and classifies **zero posts** every fire. The dashboard is inert.

This is the identical problem MR faced (no API serves COFER/TIC/interest-coverage). MR
resolved it by making **web search the backbone** and the financial connector optional.
`report_dash_rs` resolves RS's data question the same way: the LLM reads the actual retail
discussion via web search and synthesizes a sentiment read, with connectors as optional
cross-checks. No per-post feed is ever required.


## 2. Decision log

| ID | Decision | Rationale |
|----|----------|-----------|
| R1 | Rebuild RS as the `report_dash_mr` sibling engine `report_dash_rs`, not patch `RsRunner`. | The per-post pipeline has no data source; patching it cannot work. The MR engine is the proven pattern for "honest dashboard from web search + optional connector". |
| R2 | **Web search required; FINANCIAL + NEWS optional.** | Mirrors MR's #251 relaxation. The qualitative sentiment read comes from reading discussion; connectors only add optional cross-check tiles. |
| R3 | `requires_runner = False`; **retain** `retail_sentiment.needs.yaml` as connector-resolution metadata. | Same as the MR pivot: deleting the needs file would orphan the EODHD `social_posts` runner_spec (`eodhd.py:117`) and break the `test_registry.py` drift invariant. The dashboard engine dispatches by connector, not by runner need. |
| R4 | **Delete the per-post pipeline now** (not deferred). | User decision: clean end state. The code is dead (zero-post), so deletion is low production risk; the risk is import/test blast radius, managed by the plan. |
| R5 | Ship the **engine + one view** (single-ticker sentiment overview) end-to-end in this PR; defer the rest to a roadmap. | Mirrors how MR shipped `debt_cycle` first. Proves the engine before fanning out; keeps the plan reviewable. |
| R6 | One payload model parameterized by ticker (subject = ticker), **not** one slug per analytical view. | RS's "dashboard" is sentiment-for-a-ticker; the same payload shape applies to every ticker. This is simpler than MR's per-slug registry. |
| R7 | A deterministic `classify_retail_sentiment` tool produces the normalized score + signal flags from gathered evidence. | Mirrors MR's classify tools so the headline number is computed, not free-form prose. |
| R8 | Tiles are reshaped to what web search + optional connector can honestly produce; per-tile degradation. | The old 12 metrics assumed per-post data and specialized endpoints (put/call, short interest, options). Only honestly-sourceable tiles ship. |


## 3. Goals / Non-goals

**Goals**
- Every visible RS number is either computed from cited gathered evidence, computed from
  cached snapshot history, or labelled as an optional connector cross-check.
- The page works with only a WEB_SEARCH connector configured; FINANCIAL/NEWS add tiles,
  their absence degrades per-tile and honestly.
- The engine, run service, executor, routes, cache, and frontend polling mirror the MR
  dashboard so the two stay structurally parallel.

**Non-goals (this PR)**
- All-tickers heat map, Insights/signals tab, alerting (roadmap, §11).
- Per-post classification, batch-classify audit trail, the 12-metric Pandas engine (deleted).
- Chat interface, report/PDF export, real-time SSE (out of scope forever, per old spec).
- Non-English sentiment (forever out of scope).


## 4. Architecture

Three layers, same boundaries as MR:

```
core   openlia.llm.runtime.report_dash_rs   -- engine: LLM tool loop -> typed payload
  ^
server services/rs_dash_run_service          -- run engine, upsert cache row
       scheduler/executors/rs.py             -- repointed to the run service
       routes/departments/retail_sentiment   -- MR-shaped dashboard endpoints
  ^
front  pages/departments/RetailSentiment     -- polled single-ticker view
```

The engine reuses `report_dash_mr`'s department-agnostic submodules by import where they
are identical (`session`, `ledger`, `events`, `workspace`, `transports`, `tools/web_search`,
`tools/dispatcher_tools`). RS-specific code is the payload model, the classify tool, the
prompt spec, and the tool registry assembly. Connector dispatch enters
`dispatcher.in_department("retail_sentiment")`.


## 5. The single view — payload contract

One Pydantic model `RetailSentimentData` in `report_dash_rs/schemas.py`. `subject` on the
`RunRequest` is the ticker. Registered via:

- `PAYLOAD_MODEL_BY_SLUG = {"retail_sentiment": RetailSentimentData}`
- `CLASSIFY_TOOL_BY_SLUG = {"retail_sentiment": [build_classify_retail_sentiment_tool]}`
- `implemented_dashboard_slugs()` returns `{"retail_sentiment"}`.

### 5.1 Tiles (reshaped, per-tile degradation)

| Tile | Field(s) | Source | Degrades to |
|------|----------|--------|-------------|
| Sentiment score | `sentiment_score: float` (-1..+1), `direction: "bullish"\|"bearish"\|"neutral"` | LLM read of gathered discussion, finalized by the deterministic classify tool | always available (web search) |
| Momentum / trend | `momentum: float`, `trend_label` | computed from cached snapshot history | "building history (N days)" until >= 2 snapshots |
| Attention / buzz | `buzz_level: "low"\|"elevated"\|"high"`, `buzz_note` | LLM estimate from volume/recency of discussion found | always (qualitative, not a precise count) |
| Bull/bear breakdown | `bull_pct: float`, `bear_pct: float` | LLM characterization of the split | always |
| Key narratives | `narratives: list[str]` | LLM theme extraction | always |
| Notable signals | `signals: list[Signal]` (name, severity, one-liner) | deterministic flags on the above (FOMO/panic/stealth-recovery thresholds) | always |
| Evidence | `evidence: list[EvidenceItem]` (title, url, source, classification, published_at) | citation ledger — the actual cited threads/articles | always |
| Aggregated cross-check | `aggregated_sentiment: float \| None` | EODHD `get_sentiment` via dispatcher | `null` -> tile hidden if no FINANCIAL connector |
| Institutional-retail gap | `analyst_gap: float \| None` | analyst consensus via FINANCIAL connector | `null` -> tile hidden if unavailable |

Plus payload metadata mirroring MR: `subject` (ticker), `narrative` (synthesis paragraph),
`captured_at`, and `citations` carried on `RunResult`.

### 5.2 Deterministic classify layer

`build_classify_retail_sentiment_tool(workspace)` accepts the LLM's gathered evidence
(classified items + counts) and computes deterministically:
- `sentiment_score` = (bullish - bearish) / total, clamped to [-1, 1]
- `direction` from score thresholds
- `bull_pct`/`bear_pct`
- `signals` from threshold rules (e.g. high buzz + negative tone -> "panic")

`momentum` and `trend_label` are computed in the run service from cached history (not the
LLM), reusing clean reimplementations of the small momentum/divergence math from the old
`metrics.py` (the old file is deleted; the math is reimplemented in the new quant module,
not imported).


## 6. Engine internals (mirror `report_dash_mr`)

`packages/core/src/openlia/llm/runtime/report_dash_rs/`:

| File | Responsibility |
|------|----------------|
| `__init__.py` | Public API: `Runner`, `RunRequest`, `RunResult`, `RunStatus`, `EnabledConnectors`, `LLMSession`, `CancelToken`, `NullEmitter`, `MbDataTransports` (re-exported from MR where shared), `implemented_dashboard_slugs()`. |
| `runner.py` | `Runner(request, transports, dispatcher=None).run(...)` driving the tool loop; enters `dispatcher.in_department("retail_sentiment")`. Same loop shape as MR (turns, wall-time cap, emit-dashboard finalization, web-citation rewrite notice). |
| `schemas.py` | `RetailSentimentData` + nested `Signal`/`EvidenceItem`; `RunRequest`/`RunResult` (reused/extended from MR). |
| `prompts.py` | `DASHBOARD_PROMPT_SPECS = {"retail_sentiment": DashboardPromptSpec(workflow, payload_shape, indicator_hint)}` + `build_system_prompt`. |
| `tools/registry.py` | `build_catalog(...)` assembling emit_dashboard + classify tool + dispatcher tools (optional FINANCIAL/NEWS) + web search. |
| `tools/dashboard_tools.py` | `PAYLOAD_MODEL_BY_SLUG`, `CLASSIFY_TOOL_BY_SLUG`, `implemented_dashboard_slugs()`, `build_emit_dashboard_tool`, `build_classify_retail_sentiment_tool`. |
| `tools/web_search.py`, `tools/dispatcher_tools.py`, `session.py`, `ledger.py`, `events.py`, `workspace.py`, `transports.py` | Imported from / thin wrappers over `report_dash_mr` where identical. No fork unless RS genuinely diverges. |

Where a submodule is byte-identical to MR's, import it rather than copy it (DRY). A new
file is created only when RS content differs (payload, classify tool, prompt spec, registry).


## 7. Server integration

### 7.1 Run service — `services/rs_dash_run_service.py`
Mirrors `mr_dash_run_service.run_to_cache`. Signature:
`run_to_cache(session, user_id, ticker, cancel_token=None) -> str` (returns ticker).
- Resolves `EnabledConnectors`: web_search on (when model supports it), validated providers,
  EODHD when a key resolves — reusing `build_mb_dispatcher` / `build_mb_transports` /
  `resolve_eodhd_api_key` (department-agnostic; no fork).
- Builds `RunRequest(dashboard_slug="retail_sentiment", subject=ticker, ...)`.
- Computes `momentum`/`trend_label` from cached history for `ticker`, merges into payload.
- Upserts `RsDashboardCache` row keyed `(user_id, ticker)`.

### 7.2 Executor — `scheduler/executors/rs.py`
Keep `RSSnapshotExecutor` and `JobType.RS_SNAPSHOT`. Rewrite `_do_work` to, per ticker in
the user's watchlist, call `rs_dash_run_service.run_to_cache(user_id, ticker)` and emit one
`assessment_ready` notification per fire. (Old behaviour called `RsRunner.run_many`.)

### 7.3 Routes — `routes/departments/retail_sentiment.py` (full rewrite)
MR-shaped, prefix `/departments/retail_sentiment`:

| Method | Path | Behaviour |
|--------|------|-----------|
| GET | `/dashboard/{ticker}` | read cached payload + `generated_at` + `is_stale` + `provenance` (`{payload: null, ...}` when no cache) |
| GET | `/dashboard/{ticker}/history?days=N` | historical snapshots for the ticker |
| GET | `/config` | per-user dashboard state (watchlist, threshold overrides, refresh interval) |
| PUT | `/config` | update state |
| POST | `/dashboard/{ticker}/refresh` | `202`; `gate_dept_or_409(request, "retail_sentiment")`; 409 if `active_run_for_schedule` running; enqueue RS_SNAPSHOT for that ticker |
| GET | `/schedule`, PUT `/schedule` | unchanged (reuse `rs_schedules`) |

Stale TTL per the MR pattern (`_DEFAULT_TTL_SECONDS = 24h`). The old endpoints
(`/spikes`, `/stocks/{ticker}` per-post, `/classifier/audit`) are removed.

### 7.4 Database
- **New** `rs_dashboard_cache` (mirror `mr_dashboard_cache`): `id`, `user_id` (FK),
  `ticker` (str), `payload_json` (TEXT), `provenance` (str), `model_ref` (str),
  `generated_at` (TIMESTAMP); unique `(user_id, ticker)`; index `(user_id, ticker)`.
  New Alembic migration.
- **Repurpose** `rs_user_config` -> dashboard state (watchlist, threshold overrides, refresh
  interval). Keep the table/migration; adjust columns via migration if needed.
- **Keep** `rs_schedules` verbatim.
- **Drop** `rs_snapshots` (old per-post snapshot shape) and `rs_classification_log` (no batch
  classifier) — with a down-safe migration. Note: `rs_snapshots` history feeds momentum;
  the new `rs_dashboard_cache` history (generated_at series) replaces it.

### 7.5 app.py
Remove the `RefreshingSyncLlmClassifier` / `RsRunner` / `rs_data_provider` wiring. The
executor constructs what it needs per fire (MR pattern); no app-state runner.


## 8. Department shape + coverage hint

`packages/core/src/openlia/departments/retail_sentiment.py`:
```python
required_categories: ClassVar[tuple[Category, ...]] = (Category.WEB_SEARCH,)
optional_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL, Category.NEWS)
required_any_of: ClassVar[tuple[tuple[Category, ...], ...]] = ()
requires_runner: ClassVar[bool] = False
is_dashboard: bool = True
```
Retain `retail_sentiment.needs.yaml` (header updated to note `requires_runner=False`,
declarations are connector-resolution metadata, mirroring the MR needs file) and
`routing_context.md` (updated to describe the web-search-backbone dashboard, drop per-post
language).

**Coverage hint** (mirror `mr-coverage`): the RS settings panel renders a
`data-testid="rs-coverage"` section reading `dept-health` (`satisfied_categories` /
`optional_categories` from #251's serializer) — web_search active/required; financial,
news active/"not configured" with a one-line note on what each adds. No emojis.


## 9. Frontend reshape

- `pages/departments/RetailSentiment.tsx`: reshape to the polled single-ticker overview
  against `RetailSentimentData`, reusing the `MacroResearch`/`DebtCycleView` pattern
  (poll `GET /dashboard/{ticker}`, "Generate now" -> `POST .../refresh`, polling skeleton,
  refresh spinner, stale badge). Ticker selector retained.
- `api/retail-sentiment.ts`: replace interfaces with the new payload + dashboard
  fetch/refresh/config calls (MR client shape).
- Reuse gauges/cards/chrome that fit (`SentimentGauge`, `MomentumGauge`, `SignalAlert`,
  `TrendChart`, `MetricCard`, `charts.tsx`, `TickerSelector`, `SettingsDrawer`,
  `ScheduleEditor`). **Remove** components tied to deleted data: `EvidenceTab`,
  `MetricsDeepDiveTab`, `OverviewAllView` (heat map -> roadmap), `InsightsTab`,
  `ReliabilityBadge`, `lib/retail-sentiment/metric-catalog.ts` (12-metric catalog), and the
  evidence/insights/metrics tab wiring in the page.
- `frontend/src/api/departments.ts`: remove `"retail_sentiment"` from
  `RUNNER_BEARING_DEPARTMENTS` (left `["retail_sentiment"]` after #251) -> it becomes `[]`;
  RS is now a non-runner dashboard dept, parallel to macro_research.
- i18n: prune deleted tab/metric keys; add coverage-hint strings (en + zh-TW).


## 10. Deletion inventory (the inert per-post pipeline)

**Core** — delete: `retail_sentiment/{classifier,metrics,reliability,spike_detector,quotes,insights,schemas}.py`,
`prompts/retail_sentiment.yaml`, `prompts/retail_sentiment_insights.yaml`, and the package
`__init__.py` re-exports. (The `retail_sentiment/` package directory is removed entirely.)

**Server** — delete: `services/rs_runner.py`, `services/rs_sync_classifier.py`,
`services/rs_classification_log.py`; the `rs_classification_log` table + its migration +
the `/classifier/audit` route; the `RsRunner`/classifier wiring in `app.py`.

**Tests** — delete: all `packages/core/tests/retail_sentiment/test_*.py`;
`test_services/test_rs_runner.py`, `test_rs_runner_insights.py`, `test_rs_sync_classifier.py`;
`test_db/test_rs_classification_log.py`; `test_routes/departments/test_retail_sentiment_classifier_audit.py`.
Rewrite (not delete): `test_routes/departments/test_retail_sentiment.py`,
`test_retail_sentiment_schedule.py`, `test_scheduler/test_rs_executor.py`,
`departments/test_retail_sentiment.py`, the frontend `RetailSentiment.test.tsx`.

**Deletion hazards** (resolve by deleting the importer in the same change):
- `routes/departments/retail_sentiment.py` imports `spike_detector.detect_spike`,
  `quotes.fetch_quotes`, and `schemas` -> the route rewrite removes those imports.
- `rs_sync_classifier.py` imports `classifier.LlmClassifier` -> both deleted together.
- `retail_sentiment.needs.yaml` is **NOT** deleted (R3).


## 11. Roadmap (deferred, out of scope for this PR)

1. **All-tickers heat map** (the "All" view) — matrix of tickers x key tiles, sparklines.
2. **Insights / active-signals tab** — signal cards with historical framing + narrative.
3. **Richer optional-connector tiles** — options-derived put/call, short interest, narrative
   concentration — only when a connector that actually serves them is configured.
4. **Alerting** — notify on signal thresholds.
5. **Old-table cleanup** verification — confirm no orphaned `rs_snapshots`/`rs_classification_log`
   references after a release cycle.


## 12. Testing strategy

Mirror MR's coverage:
- **Engine**: a `report_dash_rs` run test (fake LLM session drives gather->classify->emit,
  asserts a valid `RetailSentimentData`); payload-validation tests; classify-tool unit tests
  (score/signal determinism).
- **Server**: route tests (`refresh` 202, 409-on-running, 409/disabled when no WEB_SEARCH
  connector, cache read shape, history); run-service test (cache upsert + momentum merge);
  executor test (per-ticker run + notification).
- **Department artifacts**: extend `test_department_artifacts.py` with an RS branch allowing
  the retained `needs.yaml` under `requires_runner=False` (exactly the MR branch); update
  `test_health.py` RS category tests (web_search required, financial/news optional,
  disabled without web_search).
- **Frontend**: RetailSentiment view tests (polling, generate-now, payload render, coverage
  hint); mock `dept-health`.
- Full `core` + targeted `server` dirs + frontend vitest green; ruff + tsc clean.


## 13. Open questions / risks

1. **Web-search sentiment quality.** The qualitative read depends on the model finding and
   correctly weighing discussion. Mitigation: the deterministic classify tool constrains the
   score to gathered evidence; the prompt instructs citing concrete threads/articles.
2. **History bootstrap.** Momentum needs >= 2 snapshots; first run shows
   "building history". Acceptable, matches MR's cold-start tiles.
3. **Blast radius of deletion.** Large import/test surface. Mitigation: the plan deletes each
   module together with its importer and rewrites the affected tests in the same task.
4. **`rs_snapshots` drop vs history.** Dropping the old table loses any old snapshot rows
   (all zero-post, worthless) — acceptable. New history accrues in `rs_dashboard_cache`.
