# Phase 15 — Earnings Update fix plan (to 100%)

**Current:** ~92% shipped. **Root cause:** SPEC / IMPLEMENTER drift after the scheduler landed (P0-02 was written before `eu_schedules.py` was mounted, so the master tracker line is stale).

**Gap summary:** Backend watchlist / config / runner / scan-planner / schedules-service + EU executor + `EuSchedule` + `EuWatchlistEntry` + `EuUserConfig` tables are all shipped; `build_eu_schedules_router` is mounted at `app.py:484`, `build_earnings_update_router` at `app.py:348`, and `EUScanExecutor` is wired at `app.py:250,267` via `build_scheduler_service(eu_planner=...)`. Frontend `EarningsUpdate.tsx` exists (198 lines), `navData.ts:58` registers the nav item, and `router/routes.tsx:55` mounts it. Remaining gaps: duplicate schedules-router vs service (two implementations, service unused), spec-required UI behaviors (Overdue card state, New-badge on recent reports row, Cabinet search+filter wiring, remove-with-confirmation tooltip, loading skeletons, pre/post-market badge colors, inline "Generating..." indicator, On-Demand selected-company CheckCircle state), report `DELETE` endpoint for Cabinet remove (stub on frontend, `EarningsUpdate.tsx:181-183` comment "endpoint arrives with a later plan"), and the integration test for `/schedules` endpoints uses only 48 lines — coverage of PATCH/DELETE hot-reload not exercised end-to-end from the router layer.

---

**Tasks (in execution order):**

1. **P0-02 — Resolve duplicate `/schedules` implementations and consolidate on the service layer.**
   Why: `routes/eu_schedules.py:65-148` (the mounted router) talks directly to `EuSchedule` ORM and calls `svc.add_schedule(row)` / `svc.modify_schedule(row)` (passing ORM objects — the current SchedulerService API), while `services/eu_schedules.py:85-179` uses a *different* protocol (`add_schedule(*, job_type, user_id, schedule_id, time, timezone, days_of_week)`) that nothing now calls. Two schemas exist for the same concept: the route encodes `days_of_week` as `list[int]` (0=Sun…6=Sat) while the service uses `list[str]` (`"mon"`, `"tue"`, …). The service also validates timezone via `zoneinfo.ZoneInfo` and time via regex, which the router does not.
   - Files: `packages/server/src/openlia_server/routes/eu_schedules.py`, `packages/server/src/openlia_server/services/eu_schedules.py`, `packages/server/src/openlia_server/scheduler/service.py:120-137` (confirm `add_schedule(row)` / `modify_schedule(row)` signatures), `packages/server/src/openlia_server/app.py:482-484`.
   - Action:
     - Decide: keep the ORM-object scheduler API (matches what MR + MB use) and delete/retire the unused `services/eu_schedules.py`, OR switch the service to the ORM-object API and have the router delegate to it. The first is shorter and consistent.
     - After removal, move the `zoneinfo.ZoneInfo` + `^\d{2}:\d{2}$` + non-empty `days_of_week` validators into `routes/eu_schedules.py` so bad input returns 422 instead of committing and then failing in APScheduler.
     - Fold the router under `routes/departments/earnings_update.py:build_earnings_update_router` so a single factory owns every EU HTTP surface (the tracker's "schedules route absent" reflects the old split).
     - Mark `tests/services/test_eu_schedules_service.py` (216 lines) for deletion or refactor: it tests the unused service module.
   - Spec ref: EarningsUpdatePageSpec §"Scan Schedules" (`planning/specs/pages/departments/EarningsUpdatePageSpec.md:231-253`).
   - Acceptance: (a) only one schedules implementation exists; (b) `GET/POST/PATCH/DELETE /api/departments/earnings-update/schedules[/{id}]` all reachable; (c) invalid `time=25:99` → 422; invalid timezone → 422; empty `days_of_week` → 422; (d) APScheduler hot-reload verified by integration test that adds a schedule and asserts `scheduler.list_jobs()` contains it.

2. **NEW-15-01 — Implement Cabinet `DELETE /reports/{id}` and wire Cabinet remove.**
   Why: `EarningsUpdate.tsx:181-183` leaves `onRemove` as a TODO. The spec (`EarningsUpdatePageSpec.md:144`) requires a confirmation tooltip + fade-out; route does not exist in `routes/departments/earnings_update.py`.
   - Files: `routes/departments/earnings_update.py` add `DELETE /reports/{report_id}` filtering by `user_id` and `department="earnings_update"`; `frontend/src/api/earnings-update.ts` add `deleteReport(id)`; `components/earnings-update/EUCabinetView.tsx` add Radix Popover confirm on `×`; `pages/departments/EarningsUpdate.tsx:181-183` call `deleteReport` then `refreshReports()`.
   - Acceptance: `curl -X DELETE /api/departments/earnings-update/reports/{id}` → 204 for own report, 404 for foreign; vitest renders confirm tooltip and only calls mock on Confirm.

3. **NEW-15-02 — Watchlist "Overdue" visual state.**
   Why: spec (`EarningsUpdatePageSpec.md:83`) requires `next_earnings_date < today` cards get border `--color-feedback-error` and badge replaced with "Date passed". `WatchlistCard.tsx` (81 lines) currently renders timing pill unconditionally.
   - Files: `components/earnings-update/WatchlistCard.tsx`, add vitest case to `WatchlistCard.test.tsx` with fixture `next_earnings_date: '2026-04-22'` (before "today" in test).
   - Acceptance: overdue fixture renders border error + "Date passed" text; non-overdue unchanged.

4. **NEW-15-03 — Recent Reports "New badge" dot.**
   Why: spec (`EarningsUpdatePageSpec.md:112`) requires a 1.5px filled dot prepended to rows whose `created_at > now-24h` and not yet opened. `ReportRowItem.tsx` has no such logic.
   - Files: `components/earnings-update/ReportRowItem.tsx` accept `isNew: boolean`; `components/earnings-update/RecentReportsList.tsx` compute `isNew` from `created_at` and opened-report state; persist opened ids via `localStorage` (`eu-opened-reports`).
   - Acceptance: vitest fixture `created_at=now-1h` → dot present; `created_at=now-30h` → absent; after `openReport(id)` the dot is cleared.

5. **NEW-15-04 — Pre/post-market badge colors.**
   Why: spec (`EarningsUpdatePageSpec.md:81`) requires Pre-Market → `bg-[--color-info]/10 text-[--color-info]`, Post-Market → `bg-[--color-warning]/10 text-[--color-warning]`. Verify `WatchlistCard.tsx` matches; adjust if not.
   - Files: `components/earnings-update/WatchlistCard.tsx`.
   - Acceptance: vitest asserts className membership for both release timings.

6. **NEW-15-05 — Cabinet search + filters wired to backend.**
   Why: spec (`EarningsUpdatePageSpec.md:140-142`) requires search box + "Filters ▾" (ticker, date range). Current `EUCabinetView.tsx` (92 lines) renders a list only; `list_recent_reports` (`routes/departments/earnings_update.py:233-258`) only supports `limit`.
   - Files: `routes/departments/earnings_update.py` accept `q`, `ticker`, `from`, `to` query params on `/reports`; `api/earnings-update.ts:fetchRecentReports` forward them; `components/earnings-update/EUCabinetView.tsx` add debounced search input (300ms) + filter popover; group rows by month with `text-sm font-medium text-[--color-text-secondary] px-6 py-2`.
   - Acceptance: GET `/reports?q=AAPL` narrows; vitest exercises ticker filter.

7. **NEW-15-06 — On-Demand modal selected-state CheckCircle + generation progress.**
   Why: spec (`EarningsUpdatePageSpec.md:170-173`) shows a `CheckCircle` icon next to the selected company with "Last earnings: Jan 30, 2026", plus an inline "Generating report for AAPL..." status in the Recent Reports section during SSE.
   - Files: `components/earnings-update/OnDemandReportModal.tsx` show selected state + last-earnings date; `pages/departments/EarningsUpdate.tsx` render animated bar / spinner block above `RecentReportsList` while SSE stream is active; `eu_runner.run_on_demand` already emits events from the runtime (ok).
   - Acceptance: vitest mounts modal, selects a ticker, asserts CheckCircle + date visible; starts stream, asserts progress block renders; completes, asserts block hides.

8. **NEW-15-07 — Loading skeletons.**
   Why: spec (`EarningsUpdatePageSpec.md:189`) "Watchlist cards and report rows replaced by animated skeleton elements: `bg-[--color-surface-hover] rounded-[--radius-md] animate-pulse`".
   - Files: `pages/departments/EarningsUpdate.tsx` render skeletons while `useEuWatchlist` / `useEuReports` are `loading`; hooks already expose loading state (verify by Reading `frontend/src/hooks/useEuWatchlist.ts`).
   - Acceptance: initial render with pending fetch shows pulse skeletons; replaced by real content on resolve.

9. **NEW-15-08 — Empty-state strings match spec.**
   Why: spec (`EarningsUpdatePageSpec.md:84,113`) mandates dashed-border placeholder card "Add companies to your watchlist to track upcoming earnings" with inner `+ Add Ticker`, and Recent Reports empty text "On-Demand reports and automated reports will appear here".
   - Files: `components/earnings-update/WatchlistRow.tsx`, `components/earnings-update/RecentReportsList.tsx`.
   - Acceptance: vitest renders both empty states with exact strings.

10. **NEW-15-09 — Error banner with retry.**
    Why: spec (`EarningsUpdatePageSpec.md:192`) "Failed to load earnings data. Try again." with retry button. Current page has no error boundary for fetch failures.
    - Files: `pages/departments/EarningsUpdate.tsx` consume `error` + `refresh` from each hook; render inline banner at top of the scroll area.
    - Acceptance: mock-fail `fetchWatchlist` → banner visible; click "Retry" → re-invokes fetch.

11. **NEW-15-10 — Responsive mobile treatment.**
    Why: spec (`EarningsUpdatePageSpec.md:202`) mobile <768px hides date column on rows, Cabinet full-screen.
    - Files: `components/earnings-update/ReportRowItem.tsx` (`hidden sm:block` on date); `components/earnings-update/EUCabinetView.tsx` full-screen overlay breakpoint.
    - Acceptance: vitest with 375px viewport — date column absent.

12. **NEW-15-11 — EU executor backfill on-demand trigger.**
    Why: `EUScanExecutor._do_work` reads `schedule.last_run_at` but `eu_runner.run_on_demand` does not record anything into `job_runs` / `last_run_at`; on-demand reports are therefore invisible to the scheduler backfill logic. Spec is silent, but `scheduler/service.py:97-98` calls `_maybe_backfill` — on-demand should not interfere. Confirm (or document) on-demand does NOT bump `last_run_at`.
    - Files: `services/eu_runner.py`, `scheduler/service.py:86-98`, add a test that on-demand leaves `eu_schedules.last_run_at` unchanged.
    - Acceptance: test `test_eu_runner_does_not_touch_schedule_last_run_at` passes.

13. **NEW-15-12 — Integration test for `/schedules` CRUD covering hot-reload.**
    Why: `tests/test_routes/departments/test_earnings_update_schedules.py` is only 48 lines — single happy path. Missing: 422 on bad time/tz/days, 404 on foreign user, PATCH toggling `is_enabled` triggers `remove_schedule` branch, DELETE removes APScheduler job.
    - Files: same.
    - Acceptance: ≥5 new cases; coverage of `routes/eu_schedules.py:73-138` branches.

14. **NEW-15-13 — Backend `list_recent_reports` — confirm `subject` / `title` / `report_type` fields match spec.**
    Why: spec (`EarningsUpdatePageSpec.md:108-109`) requires row label formatted as "Apple Inc. — Q1 FY2026 Earnings"; backend returns `title` + `subject` separately. Verify `Report.title` is populated with company-name + quarter + "Earnings" by `report_store.create_report`, and that `eu_runner` passes a useful `subject` (currently it doesn't — `create_report` receives `schema=schema` only).
    - Files: `services/report_store.py` (confirm title derivation), `services/eu_runner.py:67-72` pass `subject=t` (ticker) if missing.
    - Acceptance: integration test: generate on-demand report for AAPL, then GET `/reports` returns row with `subject="AAPL"` and `title` containing "Earnings".

15. **NEW-15-14 — Sidebar notification-dot end-to-end verification.**
    Why: `Sidebar.tsx:13,25,121` consumes `useNotificationPoll` and renders dot when `unreadByDepartment[departmentId] > 0`; `navData.ts:58` sets `departmentId: "earnings_update"`; `EUScanExecutor` emits `NotificationSpec(type=REPORT_READY, department="earnings_update")`. Confirm server `user_notifications` row is produced by the executor, then that the poll route maps it to `departmentId`.
    - Files: `scheduler/services/notifications.py`, `routes/notifications.py` (find via grep), frontend `useNotificationPoll`.
    - Acceptance: e2e simulated: insert `user_notifications` row for `department="earnings_update"` → sidebar dot appears; visit page → `markRead` hook fires, dot disappears.

16. **NEW-15-15 — Prompt + core-department parity checks.**
    Why: `packages/core/src/openlia/prompts/earnings_update.yaml` and `packages/core/src/openlia/departments/earnings_update.py` must expose the 8 sections named in spec (`EarningsUpdatePageSpec.md:17`): Quick Take, Market Reaction, Key Financials, Operational Highlights, Forward Guidance, Earnings Call, Risk Assessment, Thesis Check. `eu_config.DEFAULT_SECTION_IDS` matches (`eu_config.py:12-21`). Verify report framework JSON (`core/reports/frameworks/earnings_update.json`) section IDs match `DEFAULT_SECTION_IDS` exactly.
    - Files: `packages/core/src/openlia/reports/frameworks/earnings_update.json` vs `eu_config.py:12-21`.
    - Acceptance: unit test `test_eu_section_ids_match_framework` asserts equal sets.

17. **NEW-15-16 — Add `test_eu_config.py` → section-catalog frontend parity test.**
    Why: `frontend/src/lib/earnings-update/section-catalog.ts` holds the default sections rendered in `ReportSettingsModal`. If backend `DEFAULT_SECTION_IDS` drifts, users see ghost sections. Add a CI guard.
    - Files: `frontend/src/lib/earnings-update/__tests__/section-catalog.test.ts`, mirror fixture.
    - Acceptance: vitest fails if IDs diverge from the backend canonical list (manually synced from `eu_config.py:12-21`).

18. **P2-TESTS-15 — Close remaining backend test gaps.**
    Why: `test_eu_migration.py` (70 lines) and `test_eu_models.py` (128 lines) exist, but no test covers `EuWatchlistEntry` cascade delete when a user is deleted.
    - Files: `tests/db/test_eu_models.py` add cascade test.
    - Acceptance: delete a `User`, assert watchlist + config + schedules rows are gone.

19. **NEW-15-17 — Spec drift: Settings button on page header vs spec header having only "On-Demand Report".**
    Why: `EarningsUpdate.tsx:117-131` renders both a `SettingsIcon` and an On-Demand button, but the spec (`EarningsUpdatePageSpec.md:58-64`) header row only lists the On-Demand action. Spec (`…:239`) says schedule config is "accessible from the EU page via a Settings button (same pattern as MB Settings view)". Resolution: update spec to include the settings icon and document the MB-parity. Alternatively move schedules into a dedicated `/earnings-update/settings` sub-route.
    - Files: `planning/specs/pages/departments/EarningsUpdatePageSpec.md` — amend header row; OR move `ScheduleManager` behind a Settings route.
    - Acceptance: spec + implementation agree.

20. **NEW-15-18 — Spec drift: `Settings` section #1 says "In the settings page for SR" (wrong department).**
    Why: `EarningsUpdatePageSpec.md:205` reads "In the settings page for SR" — copy-paste from SR spec. Must say EU.
    - Files: `planning/specs/pages/departments/EarningsUpdatePageSpec.md:205`.
    - Acceptance: one-line fix.

21. **NEW-15-19 — Document that `on-demand` SSE endpoint does not use the `Depends(_earnings_adapter_dep)`.**
    Why: The `/report` endpoint (`routes/departments/earnings_update.py:201-231`) uses `report_runner` but not the earnings adapter — the runner tool-calls the data provider itself. Confirm this is intentional and add a docstring explaining; otherwise, an adapter dependency hole ("on-demand" generates a report for a ticker the user might have never fetched earnings for).
    - Files: `routes/departments/earnings_update.py:201`.
    - Acceptance: inline comment present.

---

**Verification:**
```bash
uv run pytest packages/server/tests -k "eu_ or earnings_update" -q
uv run pytest packages/core/tests -k "earnings_update" -q
npm --prefix frontend test -- --run earnings-update
npm --prefix frontend test -- --run EarningsUpdate
curl -s http://localhost:8000/api/departments/earnings-update/schedules -H "Cookie: session=…" | jq .
curl -s -X POST http://localhost:8000/api/departments/earnings-update/schedules \
     -H "Content-Type: application/json" -H "Cookie: session=…" \
     -d '{"time":"06:00","timezone":"America/New_York","days_of_week":[1,2,3,4,5],"label":"Pre-Market Scan","is_enabled":true}'
```

Expected: all test suites green; `/schedules` returns 200 with shape `{schedules:[…]}` (list wrapper — note `api/earnings-update.ts:105-106` wraps the raw list, backend returns the raw list at `routes/eu_schedules.py:140`); POST returns 201 with APScheduler job registered.
