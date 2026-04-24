# Phase 19 — Macro Research fix plan (→ 100%)


**Current:** ~72% shipped. **Root cause:** IMPLEMENTER (assessment-run stub, dashboard-LLM wiring contradicts design, Settings panel never built).

**Gap summary:** `POST /assessment/run` returns fake `job_run_id` with no dispatch (P1-05); `FourSeasonsDashboard.T4_PROMPT_KEY` blocks on a cached T4 result for a formula-only dashboard and `AllWeatherView` exposes "Run assessment" button for a dashboard with no LLM (P1-06); Settings panel absent; auto-refresh dropdown + composite Summary tab deferred; 14 of 18 backend + all 6 frontend tests missing.

**Tasks (in execution order):**

1. **P1-05 — Wire `POST /dashboards/{slug}/assessment/run` to real scheduler dispatch.**
   - Files: `routes/departments/macro_research.py:86-95` — replace stub with `MRScheduleService.run_now(user_id, slug)` (or dispatch via shipped `BatchRunner`), create `JobRun` row, return real `job_run_id`.
   - Spec ref: MacroResearchPageSpec "Run assessment now".
   - Acceptance: button persists `job_runs` row progressing `queued` → `running` → `success|failed`; `GET /job_runs/{id}` returns live state.

2. **P1-06 — Strip T4 dependency from Four Seasons + remove "Run assessment" button from All-Weather.**
   - Files: `packages/core/src/openlia/macro_research/dashboards/four_seasons.py` (remove `T4_PROMPT_KEY = "four_seasons"`); `FourSeasonsView.tsx` (remove button); `AllWeatherView.tsx:92` (remove button — T3 dashboard, no LLM).
   - Spec ref: `macro-research-dalio-dashboards-design.md` dashboard-tier assignments.
   - Acceptance: Four Seasons renders without blocking on `mr_assessment_cache`; All-Weather UI shows no run-assessment button; Debt Cycle / World Order / Five Forces (real T4 dashboards) still expose the button.

3. **NEW-19-01 — Build MR Settings panel / `ScheduleEditor` wiring.**
   - Files: verify `ScheduleEditor.tsx` round-trips to `PUT /schedules/{slug}`; add `MRSettingsPanel.tsx` hosting `ScheduleEditor` + per-dashboard threshold overrides; wire into `MacroResearch.tsx` as slide-over.
   - Why new: deferred in tracker P2-01 Phase 19 bullet, no ticket ID.
   - Acceptance: Settings shows per-dashboard cron + "Run now" + threshold overrides; saving persists to `mr_dashboard_state.assessment_schedule` + `threshold_overrides`.

4. **NEW-19-02 — Ship composite Summary tab + auto-refresh dropdown.**
   - Files: `SummaryView.tsx` (aggregate five dashboards' top-line status); `MacroResearch.tsx` (refresh-interval select; poll via `useMrDashboard`).
   - Why new: deferred.
   - Acceptance: Summary tab lists five dashboards; selecting 1m triggers repeated `GET /dashboards/*` at 60s.

5. **NEW-19-03 — Add missing backend tests (14 of 18).**
   - Files: create under `packages/server/tests/test_macro_research/`: `test_mr_assessment_builder.py`, `test_mr_cache_store.py`, `test_mr_dashboard_service.py`, `test_mr_runner.py`, `test_mr_schedules_service.py`, `test_routes_macro_research.py`, `test_routes_mr_schedules.py`, `test_scheduler_add_mr_schedule.py`, `test_lifespan_mr_rehydration.py`, `test_department_snapshot.py`, `test_dashboards_debt_cycle.py`, `test_dashboards_four_seasons.py`, `test_dashboards_all_weather.py`, `test_dashboards_world_order.py`.
   - Why new: pins P2-TESTS umbrella.
   - Acceptance: all green; each dashboard module has T1 + T2 + T3/T4 smoke case.

6. **NEW-19-04 — Add missing frontend tests (6 of 6).**
   - Files: `MacroResearch.test.tsx`, `DebtCycleView.test.tsx`, `FourSeasonsView.test.tsx`, `AllWeatherView.test.tsx`, `WorldOrderView.test.tsx`, `FiveForcesView.test.tsx`.
   - Acceptance: `cd frontend && npm run test -- macro_research` green.

7. **NEW-19-05 — Endpoint-contract + route-authorization matrix rows for MR.**
   - Files: `endpoint-contract-matrix.md` + `route-authorization-matrix.md` — rows for `GET /dashboards/{slug}`, `PUT /dashboards/{slug}/threshold-overrides`, `POST /dashboards/{slug}/assessment/run`, `GET/PUT /schedules/{slug}`.
   - Why new: Phase-19 slice of P2-21.
   - Acceptance: matrix files contain rows.

**Verification:** `uv run pytest packages/server/tests/test_macro_research && cd frontend && npm run test -- macro_research`; manual: "Run assessment now" on Debt Cycle progresses real `JobRun`; Four Seasons + All-Weather render without the button; Settings panel round-trips schedule changes.
