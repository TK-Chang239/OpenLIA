# Phase 15 — Earnings Update fix plan (→ 100%)


**Current:** ~78% shipped. **Root cause:** IMPLEMENTER.

**Gap summary:** Watchlist, config, runner, schedules service/router, `EarningsUpdate.tsx` page composition, and all child components exist. Remaining gaps: tracker's P0-02 "schedules route absent" is partially stale (route mounted at `app.py:484`) but not inline-composed per plan; Cabinet/OnDemand test coverage missing; New-badge, Overdue state, Recent-Reports click-to-FileViewer likely incomplete; sidebar notification dot integration.

**Tasks (in execution order):**

1. **P0-02 (reduced) — Consolidate `/schedules` under EU department router OR document the split; verify no route duplication.**
   - Files: `routes/departments/earnings_update.py:95–260` — either nest `build_eu_schedules_router` inside the same `prefix` or confirm the standalone mount at `app.py:482–484` uses identical prefix + update Plan Task 10; add `test_earnings_update_schedules.py` integration test.
   - Spec ref: EarningsUpdatePageSpec "Scan Schedules".
   - Acceptance: `curl /api/departments/earnings-update/schedules` returns 200 with shape frontend expects.

2. **NEW-15-01 — Verify `EarningsUpdate.tsx` composition; wire FileViewer + sidebar dot.** Why new: tracker said page absent; actually exists at 198 lines — real gap is FileViewer click-through + notification dot.
   - Files: `EarningsUpdate.tsx` (confirm `RecentReportsList` row `onClick` calls `useFileViewer().open(...)`); `SidebarItem.tsx` (add notification-dot rendering).
   - Spec ref: EarningsUpdatePageSpec "Notification Dot (Sidebar)" + "Recent Reports Section".
   - Acceptance: generating on-demand report shows dot; visiting page clears it; clicking recent-report row opens FileViewer.

3. **NEW-15-02 — Implement Watchlist "Overdue" state, New-badge on reports, pre/post-market badge colors.** Why new: spec states table entries; verification needed.
   - Files: `WatchlistCard.tsx` (overdue border `--color-feedback-error`); `ReportRowItem.tsx` (new-badge dot when `created_at > now - 24h && !opened`).
   - Acceptance: vitest fixtures render expected classNames.

4. **NEW-15-03 — Implement Cabinet search + filter dropdown.** Why new: spec requires ticker/date-range filter.
   - Files: `EUCabinetView.tsx` (debounced search + filter popover); `frontend/src/api/earnings-update.ts` pass `q=`/`ticker=`/`from=`/`to=` query params; `routes/departments/earnings_update.py:233–259` `/reports` honor them.
   - Acceptance: searching "AAPL" narrows results.

5. **P2-TESTS-15 — Add missing backend service tests.**
   - Files: `test_eu_watchlist.py`, `test_eu_config.py`, `test_eu_runner.py`, `test_eu_scan_planner.py`.
   - Acceptance: ≥4 new files passing.

6. **NEW-15-04 — Loading-skeleton state for Watchlist + Recent Reports.** Why new: spec "Loading" state requires `animate-pulse` skeletons.
   - Files: `EarningsUpdate.tsx` — render skeletons while hooks loading.
   - Acceptance: initial render with pending fetch shows pulse skeletons.

7. **NEW-15-05 — Cabinet remove-with-confirmation tooltip.** Why new: spec requires tooltip confirm before deleting.
   - Files: `EUCabinetView.tsx` — Radix Popover on × with Confirm/Cancel.
   - Acceptance: click × shows "Remove this report?"; only Confirm triggers DELETE.

**Verification:** `uv run pytest packages/server/tests -k "eu_ or earnings_update" && npm --prefix frontend test -- earnings-update && curl /api/departments/earnings-update/schedules -H "Cookie: session=..."` returns 200.
