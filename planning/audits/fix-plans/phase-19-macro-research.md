# Phase 19 — Macro Research fix plan (-> 100%)

**Current:** ~85% shipped. **Root cause:** IMPLEMENTER (assessment-run route never
dispatches a real job; AllWeatherView surfaces a no-LLM "Run assessment" button;
threshold-overrides + auto-refresh + drilldowns never built; matrix rows missing).

**Verified-against-code summary (paths cited inline):**

- `routes/departments/macro_research.py:86-95` — `POST /dashboards/{slug}/assessment/run`
  generates a random UUID and returns `{"job_run_id": ..., "status": "queued"}`
  with **no** `JobRun` insert and **no** scheduler dispatch. Tracker P1-05.
- `core/openlia/macro_research/dashboards/all_weather.py:24` declares
  `T4_PROMPT_KEY: str | None = None` (correct: T3 dashboard, no LLM), yet
  `frontend/.../macro_research/AllWeatherView.tsx:86-94` still renders the
  "Run assessment now" button and calls `runAssessment("all_weather")`.
  Tracker P1-06 second half.
- `core/openlia/macro_research/dashboards/four_seasons.py:28` declares
  `T4_PROMPT_KEY: str | None = "four_seasons"` — design says Four Seasons is T2
  formula-only. The dashboard *does* have a T4 narrative path; spec
  (`macro-research-dalio-dashboards-design.md`) treats Four Seasons as a
  **T1+T2+T3** dashboard. **Verify with product** before stripping (the existing
  fix-plan asserted P1-06 wanted it stripped; we now classify this as a
  spec-vs-impl reconciliation, not a clear bug).
- `routes/departments/macro_research.py:48-55` — `GET /dashboards/{slug}` calls
  `mr_runner.run(... smart_mode=False)` ignoring any client-supplied query;
  Smart-Mode toggle in views (`AllWeatherView.tsx:85`, etc.) is local-only and
  never reaches the backend. Tracker observation 949.
- `routes/departments/macro_research.py:67-84` exposes `PUT /dashboards/{slug}/config`
  taking `{view_config, threshold_overrides}` together — spec
  (`MacroResearchPageSpec.md`) calls for a dedicated
  `PUT /dashboards/{slug}/threshold-overrides`; matrix rows missing either way.
- `services/mr_schedules.py:17-103` — `MRScheduleService` is **singleton per user**
  via the canonical `world_order` row, but spec calls for **per-dashboard**
  schedules. App.py constructs **two** `MRScheduleService` instances
  (`app.py:280`, `app.py:388`) — one with `scheduler=adapter`, one with
  `scheduler=None`; route writes through the `scheduler=None` instance never
  reach APScheduler. Tracker P0-05.
- `app.py:266` calls `build_scheduler_service(... batch_runner=None ...)`;
  `MRAssessmentExecutor._do_work` will fail with `AttributeError` on the first
  fired schedule. Tracker P0-04.
- `services/mr_runner.py:50-53` — `dashboard_service.get_or_create` is called
  inside `try/except: pass`, swallowing every error including programming
  bugs. Violates "fail fast and loudly" rule.
- `frontend/src/pages/departments/macro_research/SummaryView.tsx` — only links
  to dashboards; no aggregated severity/last-assessment surfaced (spec calls
  for a composite top-line view). Tracker §10 Phase 19 deferred bullet.
- Missing UI: per-dashboard threshold overrides panel; auto-refresh dropdown;
  drilldown for Debt Cycle stage / World Order metrics; "Last assessment at"
  badge per dashboard tab.
- Tests largely shipped (test_macro_research/ has 17 modules). Verify the
  matrix below against acceptance.

---

**Tasks (in execution order):**

1. **P1-05 — Wire `POST /dashboards/{slug}/assessment/run` to real scheduler dispatch.**
   - Files: `routes/departments/macro_research.py:86-95` — replace stub with a
     dispatcher: insert a `JobRun` row (`db/models/scheduler.JobRun`) keyed
     to `JobType.MR_ASSESSMENT` + `schedule_id=slug` + `user_id`, then call
     `app.state.scheduler.run_now(job_run_id=...)` (mirroring
     `scheduler/service.py:139` `re-run` pattern); return the **real** ID.
   - Pre-req: P0-04 (BatchRunner wired) and P0-05 (unify schedule services) —
     otherwise the dispatched job will crash inside `MRAssessmentExecutor`.
   - Acceptance: button persists `job_runs` row progressing
     `queued -> running -> success|failed`; `GET /jobs/{id}` returns live state;
     `MRAssessmentExecutor` writes a `mr_assessment_cache` row;
     `mr_dashboard_state.last_assessment_at` advances; `assessment_ready`
     notification fires.

2. **P1-06a — Remove "Run assessment now" from AllWeatherView (T3, no LLM).**
   - Files: `frontend/src/pages/departments/macro_research/AllWeatherView.tsx:42,57-67,86-94`
     drop the `running` state, `onRun`, and the button.
   - Spec ref: `macro-research-dalio-dashboards-design.md` (All-Weather is T1+T3
     risk-parity audit, no LLM tier).
   - Acceptance: no run-assessment button on All-Weather; existing test
     `__tests__/AllWeatherView.test.tsx` updated.

3. **P1-06b — Reconcile Four Seasons T4 with spec (PRODUCT decision).**
   - Files: choose one of:
     - (a) drop `T4_PROMPT_KEY` in
       `core/openlia/macro_research/dashboards/four_seasons.py:28` and remove
       the matching button in `FourSeasonsView.tsx`, or
     - (b) update `macro-research-dalio-dashboards-design.md` to acknowledge
       Four Seasons has a narrative T4.
   - Why new: implementation diverges from spec; CLAUDE.md rule 9 says update
     plan if implementation diverges. Block on PM clarification first; default
     to (a) to match design doc.
   - Acceptance: spec + dashboard module + frontend agree.

4. **NEW-19-06 — Plumb `smart_mode` through the dashboard fetch.**
   - Files: `routes/departments/macro_research.py:48-55` accept
     `smart_mode: bool = Query(False)`; pass into `mr_runner.run`. Update
     `frontend/src/api/macro_research.ts` `getDashboard(slug, smartMode?)` to
     send the param; views (`AllWeatherView.tsx:53`, `FourSeasonsView`,
     `DebtCycleView`, `WorldOrderView`, `FiveForcesView`) re-fetch when toggle
     flips.
   - Why new: observation 949 noted the smart-mode param was removed without
     server-side replacement; T5 overlay is therefore dead code.
   - Acceptance: toggling Smart Mode produces a request with
     `?smart_mode=true`; `T5_smart_mode_adjustments` exercised by an
     integration test.

5. **NEW-19-07 — Replace `try/except: pass` in `mr_runner.run`.**
   - Files: `services/mr_runner.py:50-53` — let `get_or_create` raise; only
     swallow `IntegrityError` for racy unique-constraint hits.
   - Why new: violates CLAUDE.md fail-fast rule.
   - Acceptance: a deliberately broken `dashboard_service` raises through the
     route as 500.

6. **NEW-19-08 — Split threshold-overrides endpoint per spec.**
   - Files: `routes/departments/macro_research.py` — keep
     `PUT /dashboards/{slug}/config` for view_config; add
     `PUT /dashboards/{slug}/threshold-overrides` returning the merged row.
     Update `frontend/src/api/macro_research.ts` and add a panel UI in
     Settings (NEW-19-01).
   - Spec ref: `MacroResearchPageSpec.md` -> "Threshold overrides" sub-section.
   - Acceptance: matrix row exists; spec endpoint resolves; existing combined
     endpoint stays for backward compat or is removed once frontend migrates.

7. **NEW-19-01 — Build MR Settings slide-over with ScheduleEditor + threshold panel.**
   - Files: existing `ScheduleEditor.tsx` already round-trips via
     `getSchedule/putSchedule/deleteSchedule`; wrap it inside a new
     `MRSettingsPanel.tsx` that adds a per-dashboard threshold-overrides
     section (driven by NEW-19-08). Wire from `MacroResearch.tsx:91-93`
     (currently opens ScheduleEditor directly).
   - Acceptance: Settings shows cron + per-dashboard threshold overrides;
     saving persists to `mr_dashboard_state.assessment_schedule` (canonical
     `world_order` row) and `mr_dashboard_state.threshold_overrides`
     (per-dashboard row).

8. **NEW-19-02 — Composite Summary tab + auto-refresh dropdown.**
   - Files: rewrite `SummaryView.tsx` to fetch all five dashboards
     concurrently and surface `severity` + `last_assessment_at` + top T3
     line. Add a refresh-interval `<select>` to `MacroResearch.tsx` that
     drives a polling `useEffect` (60s/5m/15m/off) hitting `getDashboard`
     for the active tab.
   - Acceptance: Summary tab lists five dashboards with severity pills and
     last-run timestamps; selecting "1m" triggers periodic
     `GET /dashboards/<slug>` calls.

9. **NEW-19-09 — Per-dashboard "last assessment at" + freshness badge.**
   - Files: `DashboardFrame.tsx` — extend the header with
     `<FreshnessBadge generatedAt={data.generated_at} ttlMinutes={...} />`.
     Source TTL from `mr_assessment_cache.expires_at` via the runner result
     (already populated for T4-bearing dashboards).
   - Acceptance: badge renders "Fresh" / "Stale" based on age.

10. **NEW-19-10 — Plumb dashboard data series through real DataProvider.**
    - Files: `app.py:361-380` — `_NoopPtDispatcher` is the default and the
      `_MRDataFetchAdapter` swallows every fetch error to `None`. Replace
      with the shipped `DataProviderRegistry` (`services/data_providers.py`)
      so Debt Cycle / Four Seasons get real EODHD/macro readings.
      Audit each `T1_REQUIREMENTS` string in
      `core/openlia/macro_research/dashboards/*.py` and ensure
      `data/<provider>` adapters resolve them.
    - Why new: dashboards currently render zeroes / fallbacks because no
      real data ever flows.
    - Acceptance: integration test stubs the data registry and asserts
      Debt Cycle T2 metrics populate from the stub.

11. **NEW-19-11 — Drop or fix duplicate `MRScheduleService` in app.py (depends on P0-05).**
    - Files: `app.py:280` (lifespan, `scheduler=adapter`) vs. `app.py:388`
      (factory, `scheduler=None`). Hand the lifespan instance to
      `app.state.mr_schedule_service` and remove the second construction.
      Currently `build_mr_schedule_router` receives the `scheduler=None`
      instance, so route-driven `PUT /schedules/{slug}` writes never call
      `scheduler.modify_schedule`.
    - Acceptance: route writes round-trip through APScheduler; rehydration
      still fires at startup; no duplicate construction.

12. **NEW-19-12 — Schedule key alignment (per-dashboard vs canonical row).**
    - Files: `services/mr_schedules.py:20` hard-codes
      `CANONICAL_DASHBOARD = "world_order"`; spec calls for per-dashboard
      schedules. Either (a) change route + service to take `slug` end-to-end
      and store the cron on each dashboard row, or (b) document that MR has
      one global schedule and update the spec.
    - Why new: spec/impl divergence; current code makes `world_order`
      magical.
    - Acceptance: spec + service agree; tests cover the chosen model.

13. **NEW-19-13 — Tighten existing test coverage.**
    - Files (already exist; verify each acceptance):
      `test_routes_macro_research.py` (add a non-stub run_assessment case
      after P1-05); `test_dashboards_*.py` (assert T1+T2+T3 outputs match
      design tables); `test_mr_runner.py` (assert exception escapes after
      NEW-19-07); `test_mr_schedules_service.py` (cover
      duplicate-instance bug regression). `test_scheduler/test_mr_executor.py`
      already exists — verify it constructs a real `BatchRunner` after P0-04.
    - Acceptance: `uv run pytest packages/server/tests/test_macro_research`
      green with the new assertions.

14. **NEW-19-14 — Tighten frontend tests.**
    - Files (already exist):
      `__tests__/MacroResearch.test.tsx` (add tab navigation + Settings
      open assertion); `AllWeatherView.test.tsx` (assert no run-assessment
      button after P1-06a); `FourSeasonsView.test.tsx` (mirror P1-06b
      decision); `DebtCycleView.test.tsx`, `WorldOrderView.test.tsx`,
      `FiveForcesView.test.tsx` (assert SmartMode toggle posts to backend
      after NEW-19-06); `ScheduleEditor.test.tsx` already covers
      get/put/delete.
    - Acceptance: `cd frontend && npm run test -- macro_research` green.

15. **NEW-19-05 — Endpoint-contract + route-authorization matrix rows.**
    - Files: `planning/audits/endpoint-contract-matrix.md` +
      `route-authorization-matrix.md` — rows for
      `GET /departments/macro_research/dashboards`,
      `GET /departments/macro_research/dashboards/{slug}`,
      `GET/PUT /departments/macro_research/dashboards/{slug}/config`,
      `PUT /departments/macro_research/dashboards/{slug}/threshold-overrides`,
      `POST /departments/macro_research/dashboards/{slug}/assessment/run`,
      `GET/PUT/DELETE /departments/macro_research/schedules/{slug}`.
    - Why new: Phase-19 slice of P2-21.
    - Acceptance: matrix files contain the rows with auth + body schemas.

---

**Dependencies / sequencing notes:**

- P1-05 cannot land before Phase 6 P0-04 + P0-05 (BatchRunner wiring + unified
  schedule service). Order across phases: Phase 6 -> Phase 19.
- NEW-19-12 may invalidate parts of NEW-19-01/NEW-19-08 — resolve the spec
  question first.

**Verification:**

```
uv run pytest packages/server/tests/test_macro_research \
              packages/server/tests/test_scheduler/test_mr_executor.py
cd frontend && npm run test -- macro_research
```

Manual: open MR -> "Run assessment now" on Debt Cycle persists a real
`JobRun` progressing through `success`; All-Weather UI has no run-assessment
button; Settings panel round-trips schedule + threshold changes; Summary tab
shows severity + last-assessment for all five dashboards; Smart-Mode toggle
flips fetched payload.
