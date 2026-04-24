# Phase 20 — Retail Sentiment fix plan (→ 100%)

**Current:** v1 ~60% / v2-bundle 100% (just shipped on `feat/rs-refreshing-classifier`) / v2-full deferred. **Root cause:** mixed (DEFERRED + SPEC_DRIFT on v1 UI + STALE_TRACKER on classifier-log).

**Status snapshot (verified against code 2026-04-24):**

- `rs_classification_log` table: model + migration + service + EXPECTED_TABLES entry all present. `packages/server/src/openlia_server/db/models/dashboard.py:199` (`RsClassificationLog`), `packages/server/src/openlia_server/db/migrations/versions/2026-04-24-0100_rs_classification_log.py`, `packages/server/tests/test_db/test_migrations.py:48`. **Tracker note "migration unconfirmed" is stale — close as VERIFIED.**
- `RefreshingSyncLlmClassifier` wired through `app.py:415-426` into `app.state.rs_runner` (resolves Quick-tier model per call; falls back to neutral when `TierNotConfiguredError`). `SyncLlmClassifier` retained for tests.
- `LlmClassifier` (core, async) ships with batch-30, retry-once, neutral fallback, audit emission per chunk.
- `RsRunner.run_ticker` persists every emitted `ClassificationAudit` via `RsClassificationLogService.insert`. Audit tests cover default-no-rows, success row, and error row.
- Batch prompt `prompts/retail_sentiment.yaml` `batch.classify_batch.system|user` rendered correctly by classifier.
- Routes shipped: `GET /dashboard`, `GET /dashboard/history`, `GET|PUT /config`, `POST /run`, `GET /stocks/{ticker}/sentiment`, `GET /spikes`. **Missing:** `GET|PUT /schedule`.
- Frontend `RetailSentiment.tsx` is a 323-line monolith with three tabs (Overview / Per Stock / Spikes), inline styles, no SWR/react-query, no Evidence/Insights tabs, no Settings drawer, no Metrics Deep Dive panel, no Schedule editor, no `components/retail-sentiment/` directory.
- Scheduler: no `JobType.RS_SNAPSHOT` in `scheduler/registry.py`, no `_DEPARTMENT_BY_JOB` entry, no `scheduler/executors/rs.py`, no `scheduler/wiring.py` registration. Plan Tasks 9 + 13 + 17 fully deferred.
- Metrics 8, 9, 11, 12 still null placeholders in `openlia.retail_sentiment.metrics`. Metric 10 (narrative concentration) ships but only when classifier provides `key_phrases` (NeutralClassifier emits none → always `None` for that path). Metric 5 (divergence) requires a `prior_buzz` from history but the runner passes `MetricSnapshot` history without raw buzz/sentiment z-score history (works because `MetricSnapshot.buzz_volume` and `.sentiment_score` are present). Metric 2 ships as raw post count, **not** the spec's `count_today / 30d_moving_avg` ratio (SPEC_DRIFT).
- Insights narrative synthesis prompt + LLM call: not present. No `retail_sentiment_insights.yaml`. `MetricSnapshot` has no narrative field.
- `core/openlia/retail_sentiment/reliability.py`: not present (plan Task 5). Cross-source weights are inlined as a constant in `metrics.py`.

**Gap summary:** v2-full surface remains. (1) RS scheduler integration; (2) Evidence/Insights/Settings/Deep-Dive UI + spec-aligned Overview (headline + compact tier + heat map for "All"); (3) metrics 8-12 + spec-correct Buzz Volume normalization; (4) narrative-synthesis LLM call; (5) typed API client SWR hooks; (6) component decomposition under `components/retail-sentiment/`; (7) `reliability.py` extraction; (8) frontend test coverage (zero `RetailSentiment.test.tsx` exists).

---

## Tasks (in execution order)

### Foundation cleanup

1. **NEW-20-01 — Close stale tracker entry for `rs_classification_log` (no-code task).**
   - Files: `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md` line 71 ("`rs_classification_log` migration unconfirmed") and the §10 P1-25 row.
   - Action: flip P1-25 to VERIFIED with pointer to migration file + EXPECTED_TABLES line. Leave Phase 20 row at "v1: 60% / v2-bundle: 100%" but rewrite the note to "v2-full deferred (scheduler + Evidence/Insights UI + metrics 8-12 + insights synthesis)".
   - Acceptance: tracker no longer references `rs_classification_log` as a gap.

2. **NEW-20-02 — Smoke-test the just-shipped `RefreshingSyncLlmClassifier` end-to-end with a real provider stub.**
   - Files: `packages/server/tests/test_services/test_rs_sync_classifier.py` already covers neutral-fallback. Add a test that stubs `resolve` + `build_adapter` to return a fake provider whose `.generate` returns a valid JSON batch, then asserts `RefreshingSyncLlmClassifier.classify_batch` returns labelled items and exactly one audit per chunk.
   - Reason: current file (129 lines) verifies the no-model fallback only; the success path through `resolve → build_adapter → LlmClassifier.classify_batch → asyncio.run` is unexercised.
   - Acceptance: `uv run pytest packages/server/tests/test_services/test_rs_sync_classifier.py -v` covers labelled-success, neutral-fallback, and provider-exception-fallback.

### Scheduler integration (Plan Tasks 9, 13, 17)

3. **NEW-20-03 — Add `JobType.RS_SNAPSHOT` enum + registry mapping.**
   - Files: `packages/server/src/openlia_server/scheduler/registry.py` — extend `JobType` (line 14) with `RS_SNAPSHOT = "rs_snapshot"`; extend `_DEPARTMENT_BY_JOB` (line 37) with `JobType.RS_SNAPSHOT: "retail_sentiment"`.
   - Plan ref: Task 9.
   - Acceptance: `parse_job_key("rs_snapshot:<uuid>")` round-trips; `department_for_job_type(JobType.RS_SNAPSHOT) == "retail_sentiment"`; existing `test_scheduler/test_registry*.py` extended with two assertions.

4. **NEW-20-04 — Implement `RetailSentimentExecutor` + wiring.**
   - Files: NEW `packages/server/src/openlia_server/scheduler/executors/rs.py` (subclass `BaseExecutor` like `eu.py`/`mr.py`); MODIFY `packages/server/src/openlia_server/scheduler/wiring.py` (line 54-73 mapping) to register `JobType.RS_SNAPSHOT: RetailSentimentExecutor(...)`. Inject `RsRunner` via `app.state.rs_runner` lookup or via a runner factory like `MBBriefingExecutor`.
   - Behavior per Design Rule 10: executor runs `RsRunner.run_many(tickers)` for the user's watchlist, writes `JobRun`, and fans out one `UserNotification` per spike detected.
   - Plan ref: Task 13. Spec ref: "Integration → Server Layer".
   - Acceptance: NEW `packages/server/tests/test_scheduler/test_rs_executor.py` asserts (a) executor invocation writes a `JobRun`, (b) one `UserNotification` per spike, (c) classifier audit row written when classifier emits audit, (d) idempotent under repeat fire.

5. **NEW-20-05 — Add `GET /schedule` + `PUT /schedule` routes + frontend client.**
   - Files: MODIFY `packages/server/src/openlia_server/routes/departments/retail_sentiment.py` (extend after `/spikes` handler at line 195); MODIFY `frontend/src/api/retail-sentiment.ts` (add `getSchedule`/`putSchedule` + `RsSchedule` interface).
   - Constraint: one schedule per `(JobType.RS_SNAPSHOT, user_id)` per Plan Design Rule 12. PUT is upsert; DELETE not exposed (PUT-with-disabled is the off switch).
   - Plan ref: Task 17. Master tracker observation 1166 noted these were deferred — this lifts them.
   - Acceptance: tests in NEW `packages/server/tests/test_routes/departments/test_retail_sentiment_schedule.py` cover GET-empty, PUT-create, PUT-replace, PUT-disable, 401-when-unauth.

### Core engine completion (Plan Tasks 5, 6 partial)

6. **NEW-20-06 — Extract `retail_sentiment/reliability.py`.**
   - Files: NEW `packages/core/src/openlia/retail_sentiment/reliability.py` housing `DEFAULT_SOURCE_WEIGHTS`, `_normalize_weights`, and a `weight_for_source` helper. MODIFY `metrics.py` to import.
   - Plan ref: Task 5.
   - Acceptance: NEW `packages/core/tests/retail_sentiment/test_reliability.py` covers defaults, renormalization, override path, missing-source fallback.

7. **NEW-20-07 — Fix Metric 2 (Buzz Volume) to spec formula.**
   - Files: `packages/core/src/openlia/retail_sentiment/metrics.py` lines 84-86 currently set `buzz_volume = float(len(posts))`. Spec §"2. Buzz Volume" requires `buzz_ratio = count_today / avg(mentions_over_30d)`. Either (a) rename the field to `buzz_count` and add a new `buzz_ratio` to `MetricSnapshot`, or (b) compute the ratio using `prior_snapshots`' buzz counts (note: prior snapshots persist `buzz_volume` only — so this needs a stored `buzz_count` too).
   - Spec ref: "Metric Definitions" §2 + "Visualization: dashed horizontal line at 30-day average".
   - Acceptance: `MetricSnapshot.buzz_volume` returns the ratio (or rename), and the original count is exposed as `buzz_count`. Snapshot row payload (`rs_snapshot._snapshot_to_row_payload`) extended; `_row_to_metric_snapshot` extended; route `_snapshot_out` extended; frontend interface extended. Unit test asserts ratio calc matches spec for synthetic 30-day series.

8. **NEW-20-08 — Implement metrics 8, 9, 11, 12 and tighten metric 10.**
   - Files: REPLACE null placeholders in `packages/core/src/openlia/retail_sentiment/metrics.py` lines 145-148. Add per-metric helpers:
     - **§8 Put/Call Sentiment Ratio** — needs `optional_inputs["options_data"]` provider payload; ratio = `puts / calls`, scaled by sentiment.
     - **§9 Short Interest Pressure** — needs `optional_inputs["short_interest"]`; pressure index from `short_pct_float` * `days_to_cover`.
     - **§10 Narrative Concentration** — already shipped but only when `key_phrases` populated. Extend `_classify_chunk` audit / `RsRunner._fetch_posts` to ensure the LLM-backed path always emits phrases, and in `NeutralClassifier` document the limitation.
     - **§11 Institutional-Retail Gap** — needs `optional_inputs["institutional_holdings"]`; gap = institutional change % minus retail sentiment.
     - **§12 Event Sensitivity Score** — needs `historical_prices` + cold-start logic ("Insufficient data (N/30 days)" per spec page state).
   - NEW: extend `RsRunner._fetch_posts` (or new method `_fetch_optional`) to pull these provider requirements once and pass through `compute_snapshot(optional_inputs=...)`.
   - Plan ref: Task 6 (the 12-metric body).
   - Acceptance: NEW `packages/core/tests/retail_sentiment/test_metrics_advanced.py` has one passing test per metric; each metric returns `None` when its optional input is missing (graceful degrade per Design Rule 9).

9. **NEW-20-09 — Insights narrative synthesis LLM call.**
   - Files: NEW `packages/core/src/openlia/prompts/retail_sentiment_insights.yaml` (system + user templates per spec §"Insights Generation"); NEW `packages/core/src/openlia/retail_sentiment/insights.py` exposing `synthesize_narrative(snapshot, signals, *, provider, prompts) -> str` async; MODIFY `services/rs_runner.py` to invoke synthesis after `compute_snapshot` (gated on Quick-tier resolution like `RefreshingSyncLlmClassifier`); MODIFY `MetricSnapshot` to add `narrative: str | None`; MODIFY snapshot service payload + route serializer + frontend interface accordingly.
   - Spec ref: "Insights Generation" + spec §"Narrative Synthesis" (Insights tab).
   - Acceptance: integration test in NEW `packages/server/tests/test_services/test_rs_runner_insights.py` shows `RsRunResult.snapshot.narrative` populated when a stub provider returns prose; `None` when Tier-not-configured; persisted into `rs_snapshots.snapshot_data["narrative"]` and read back via `GET /stocks/{ticker}/sentiment`.

### Frontend rebuild (Plan Tasks 20-27)

10. **NEW-20-10 — Decompose `RetailSentiment.tsx` into spec-required components.**
    - Files: CREATE under `frontend/src/components/retail-sentiment/`:
      - `OverviewTab.tsx` — single-ticker headline tier (Sentiment, Momentum, Divergence, Cross-Source) + compact tier (8 smaller cards) + charts; "All"-selected heat map (tickers × key metrics) per spec §"Overview Tab".
      - `EvidenceTab.tsx` — metric filter bar, score-impact decomposition chart, reverse-chronological evidence feed with source badges, per spec §"Evidence Tab".
      - `InsightsTab.tsx` — active signal alert cards, narrative synthesis paragraph, reliability matrix bubble scatter, per spec §"Insights Tab".
      - `TickerSelector.tsx` — pills + "All" + "Import from Portfolio" + "+ Add" + remove-on-hover + 21+ amber warning, per spec §"Ticker Selector".
      - `MetricCard.tsx`, `SentimentGauge.tsx`, `TrendChart.tsx` (Recharts), `ReliabilityBadge.tsx`, `SignalAlert.tsx` — leaf components.
      - `ScheduleEditor.tsx` — cron schedule modal hitting `PUT /schedule` (NEW-20-05).
      - `SettingsDrawer.tsx` — thresholds + cross-source weights drawer per spec §"Settings Panel".
      - `MetricsDeepDive.tsx` — fixed `?` button + 480px drawer per spec §"Metrics Deep Dive Panel".
    - MODIFY: rewrite `frontend/src/pages/departments/RetailSentiment.tsx` (323 lines) to compose these components; remove all inline `style={{...}}` blocks in favour of token classes; replace bespoke fetch with SWR hooks (NEW-20-11).
    - Spec ref: `RetailSentimentPageSpec.md` §"User Interface Design" + design spec §"Page-Level Structure" / §"Overview Tab" / §"Evidence Tab" / §"Insights Tab" / §"Metrics Deep Dive Panel".
    - Acceptance: each component has a vitest smoke test under `frontend/src/components/retail-sentiment/__tests__/`. NEW `frontend/src/pages/departments/__tests__/RetailSentiment.test.tsx` asserts: (a) renders 3 spec tabs, (b) `?` opens drawer, (c) Settings drawer mounts, (d) "Import from Portfolio" wired, (e) tab switching persists via `PUT /config`.

11. **NEW-20-11 — Typed API client + SWR hooks.**
    - Files: EXTEND `frontend/src/api/retail-sentiment.ts` — add `getSchedule`, `putSchedule`, `getInsights` (if synthesis exposed standalone), and rename loose ad-hoc `fetchJson` calls into typed wrappers. CREATE `frontend/src/hooks/useRsDashboard.ts`, `useRsHistory.ts`, `useRsConfig.ts`, `useRsSpikes.ts`, `useRsSchedule.ts` (matches plan Task 21).
    - Acceptance: hook tests under `frontend/src/hooks/__tests__/` assert SWR revalidation cadence (driven by `RsConfig.refresh_interval_minutes`), optimistic mutation for `useRsConfig.setActiveTab`, and error surface when fetch rejects.

12. **NEW-20-12 — Frontend metric catalogue.**
    - Files: NEW `frontend/src/lib/retail-sentiment/metric-catalog.ts` mapping each of the 12 metrics to label, units, formula reference, reliability tier, default chart type. Used by `MetricsDeepDive.tsx` and `MetricCard.tsx`.
    - Plan ref: file structure §`lib/retail-sentiment/metric-catalog.ts`.
    - Acceptance: catalogue has 12 entries; deep-dive drawer renders all 12 sections from a single source-of-truth.

### Test backfill

13. **NEW-20-13 — RS Runner full-pipeline integration tests.**
    - Files: NEW `packages/server/tests/test_services/test_rs_runner.py`. Currently the runner has only audit-write coverage in `test_routes/departments/test_retail_sentiment_classifier_audit.py`; there is no unit test of `_fetch_posts` adapter coercion, `run_many` ordering, or spike emission paths.
    - Acceptance: tests cover (a) `_coerce_posts` handles `text|title|summary|created_at|published_at`; (b) `run_ticker` returns `RsRunResult.spike` when buzz exceeds 7-day baseline by 2σ; (c) snapshot history fed to `compute_snapshot`; (d) data-provider `Exception` swallowed with empty post list.

14. **NEW-20-14 — Route smoke tests for shipped surface.**
    - Files: existing `test_retail_sentiment.py` exists but content unverified for full route coverage. Add tests for `GET /dashboard` (multiple tickers), `GET /dashboard/history` (days clamp), `GET /config` (auto-create), `PUT /config` (refresh<5 raises 400), `POST /run` (empty tickers → 400), `GET /stocks/{ticker}/sentiment` (404 path), `GET /spikes` (excludes-latest-from-baseline behavior already encoded in route line 184).
    - Acceptance: each route has a positive + negative test.

15. **NEW-20-15 — Frontend page-level test.**
    - Files: NEW `frontend/src/pages/departments/__tests__/RetailSentiment.test.tsx`. There is currently zero frontend test coverage for RS — every other shipped department (`EarningsUpdate`, `EquityResearch`, `MorningBriefing`) has `*.test.tsx`.
    - Acceptance: covers tab switching, manual run trigger calls `runSnapshot`, error banner shows on fetch failure, empty-watchlist state matches spec.

---

## Spec drift summary (catalogued for closure)

| # | Drift | Source-of-truth | Where in code | Closing task |
|---|---|---|---|---|
| D1 | Buzz Volume = post count, spec demands `count/30d-MA` ratio | spec §2 | `metrics.py:85` | NEW-20-07 |
| D2 | Tab labels are "Overview / Per Stock / Spikes" | spec §"Tab Bar" demands "Overview / Evidence / Insights" | `RetailSentiment.tsx:14-20` | NEW-20-10 |
| D3 | `Spikes` tab exists; spec has no Spikes tab (spikes surface inside Insights "Active signals") | spec §"Insights Tab" §"Active Signals Section" | `RetailSentiment.tsx:295` | NEW-20-10 |
| D4 | No `?` Metrics Deep Dive button | spec §"Help Button (Metrics Deep Dive)" | absent in `RetailSentiment.tsx` | NEW-20-10 |
| D5 | No Settings drawer in header | spec §"Settings Panel" | absent | NEW-20-10 |
| D6 | No Auto-refresh dropdown in header | spec §"Page Header" | absent | NEW-20-10 |
| D7 | No "Import from Portfolio" / "+ Add" / 21+ amber warning | spec §"Ticker Selector" | absent | NEW-20-10 |
| D8 | No multi-ticker heat map for "All" | spec §"All Tickers View" | absent | NEW-20-10 |
| D9 | Inline `style={{...}}` everywhere | spec uses Tailwind CSS-var tokens | `RetailSentiment.tsx` | NEW-20-10 |
| D10 | Missing narrative-synthesis prompt + LLM call | spec §"Insights Generation" / §"Narrative Synthesis" | no `retail_sentiment_insights.yaml` | NEW-20-09 |
| D11 | Metrics 8, 9, 11, 12 are null placeholders | spec §§8, 9, 11, 12 | `metrics.py:145-148` | NEW-20-08 |
| D12 | No `reliability.py`; weights inlined | plan Task 5 + spec §"Cross-Source Reliability" | `metrics.py:22-33` | NEW-20-06 |
| D13 | `NeutralClassifier` cannot emit `key_phrases`, so Metric 10 always `None` on neutral path | spec §10 | `rs_runner.py:54-64` | NEW-20-08 (documentation) |
| D14 | Schedule endpoints absent | plan Task 17 | route file ends at line 195 | NEW-20-05 |
| D15 | Master tracker line 71 says `rs_classification_log` migration unconfirmed; it ships | tracker | migration verified | NEW-20-01 |

---

## Verification

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest packages/core/tests/retail_sentiment packages/server/tests -k "rs_ or retail_sentiment" -v
uv run pytest packages/server/tests/test_db/test_migrations.py -v
cd frontend && npm run test -- retail-sentiment
```

Manual: navigate to `/departments/retail-sentiment`, confirm 3 spec tabs (Overview / Evidence / Insights), `?` opens deep-dive drawer, Settings drawer persists thresholds, schedule editor round-trips, "All" view shows heat map, Insights tab renders narrative synthesis paragraph for at least one ticker.
