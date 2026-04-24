# Phase 20 — Retail Sentiment fix plan (→ 100%)


**Current:** v1 ~60% / v2-bundle 100% / v2-full deferred. **Root cause:** mixed (DEFERRED + SPEC_DRIFT on v1 UI).

**Gap summary:** v2-bundle (classifier + audit log + batch prompt) landed per PR #46. Remaining gap is the v2-full surface: scheduler integration, Evidence/Insights/Settings/Deep-Dive UI, metrics 8–12, narrative synthesis LLM call, typed API client/hooks.

**Tasks (in execution order):**

1. **P1-25 (verify) — Confirm `rs_classification_log` migration present & green.**
   - Files: `packages/server/src/openlia_server/db/migrations/versions/2026-04-24-0100_rs_classification_log.py` (verify); `test_migrations.py` (assert in EXPECTED_TABLES).
   - Acceptance: `uv run pytest packages/server/tests/test_migrations.py -v` passes.

2. **NEW-20-01 — Ship `JobType.RS_SNAPSHOT` + `RetailSentimentExecutor` + scheduler wiring.**
   - Files: `scheduler/registry.py` (add enum); `scheduler/executors/rs.py` (new); `scheduler/wiring.py` (register); `app.py` (construct executor).
   - Plan ref: Tasks 9 + 13.
   - Spec ref: "Integration → Server Layer" `[v2]` bullet.
   - Why new: tracker deferred list flags this but has no standing ID.
   - Acceptance: unit test asserts executor invocation writes `JobRun` and fans out `UserNotification` rows.

3. **NEW-20-02 — Add `GET /schedule` + `PUT /schedule` routes.**
   - Files: `routes/departments/retail_sentiment.py` (extend); `frontend/src/api/retail-sentiment.ts` (client methods).
   - Plan ref: Task 17.
   - Acceptance: tests cover GET empty, PUT create, PUT replace (one schedule per user constraint).

4. **NEW-20-03 — Implement metrics 8–12 in `openlia.retail_sentiment.metrics`.**
   - Files: `packages/core/src/openlia/retail_sentiment/metrics.py` (replace null placeholders); `tests/retail_sentiment/test_metrics_advanced.py` (new).
   - Spec ref: "Metric Definitions" §8–§12 (Put/Call, Short Interest, Narrative Concentration, Institutional-Retail Gap, Event Sensitivity).
   - Acceptance: one passing test per metric; graceful-degrade returns `None` when optional data missing.

5. **NEW-20-04 — Add `LlmClassifier` narrative synthesis call.**
   - Files: `packages/core/src/openlia/prompts/retail_sentiment_insights.yaml` (new); `services/rs_runner.py` (invoke synthesis after snapshot).
   - Spec ref: "Insights Generation".
   - Acceptance: integration test shows `snapshot_data["narrative"]` populated from mocked Quick-tier call.

6. **NEW-20-05 — Decompose `RetailSentiment.tsx` into spec-required components.**
   - Files: create under `frontend/src/components/retail-sentiment/`: `OverviewTab.tsx`, `PerStockTab.tsx`, `SpikesTab.tsx`, `EvidenceTab.tsx`, `InsightsTab.tsx`, `MetricCard.tsx`, `SentimentGauge.tsx`, `TrendChart.tsx`, `ReliabilityBadge.tsx`, `SignalAlert.tsx`, `ScheduleEditor.tsx`, `SettingsDrawer.tsx`, `MetricsDeepDive.tsx`. Rewrite `RetailSentiment.tsx` to compose.
   - Plan ref: Tasks 22–27.
   - Spec ref: `RetailSentimentPageSpec.md` "User Interface Design".
   - Acceptance: each component has vitest smoke; manual: `/departments/retail-sentiment` renders all 3 tabs, `?` opens deep-dive drawer, Settings drawer persists.

7. **NEW-20-06 — Add typed API client methods + SWR hooks.**
   - Files: `frontend/src/api/retail-sentiment.ts` (extend); `frontend/src/hooks/useRsSchedule.ts` (new), plus `useRsDashboard/useRsHistory/useRsConfig/useRsSpikes` if absent.
   - Acceptance: hook tests assert revalidation + optimistic mutation.

**Verification:** `uv run pytest packages/core/tests/retail_sentiment packages/server/tests -k "rs_" && cd frontend && npm run test -- retail-sentiment`.
