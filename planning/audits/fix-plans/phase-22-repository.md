# Phase 22 — Repository fix plan (-> 100%)

**Audit date:** 2026-04-24. **Plan:** `planning/implementation-plans/2026-04-23-phase-22-repository.md` (Tasks 0–18). **Spec:** `planning/specs/pages/RepositoryPageSpec.md`. **Master tracker:** Phase 22 row marked Done at ~65%, root cause `DEFERRED + IMPLEMENTER`, headline gap "FileViewer click-to-open missing (not in deferred list)". **Memory observation 1152** confirms filter routes shipped, UI polish + decomposition deferred.

**Current state (verified against code):**
- Backend `/repo` router shipped with the contracted `q / department / generated_from / generated_to / saved_from / saved_to / sort / page / page_size` filters, dual-shape response (legacy flat for unfiltered, paginated `RepoFilteredListOut` otherwise), `RepoRowOut` joining `repo_items`+`reports`, plus `GET /repo/facets`. Source: `packages/server/src/openlia_server/routes/repo.py` (176 LOC) and `packages/server/src/openlia_server/services/repo.py` (156 LOC, all six sort keys + pagination cap 200).
- `repo_items` schema unchanged from Plan 12 baseline — `id / user_id / report_id / created_at`, all UUID-36 — matches Plan 22 design rule 1 (no new columns).
- Server tests: `test_repo_filtered.py` (177 LOC) + `test_repo_filter_routes.py` (128 LOC) cover service + HTTP. `test_repo_routes.py` keeps Plan 12 save/unsave coverage.
- Frontend `Repository.tsx` is a 342-line single-file IMPLEMENTER monolith with inline-styled controls, NO Tailwind/design tokens beyond CSS variables, NO `lucide-react` icons, NO Framer Motion fade, NO Radix Dialog, NO infinite-scroll IntersectionObserver (manual "Load more" button instead), NO `useRepoList` hook.
- Frontend page test `Repository.test.tsx` covers only three flows: render row + facet, empty state, remove + confirm. No tests for sort, pagination/load-more, undo, error path, search, or department filter selection.
- `FileViewerContext` + `FileViewer` are functional in viewer tests but **NOT mounted in any layout** — `grep FileViewerProvider` in `frontend/src/layouts/` and `frontend/src/router/` returns zero hits. The Repository page does not import `useFileViewer`. Clicking a row goes nowhere; only Download (anchor `target="_blank"`) and Remove are wired. This is the headline gap.
- Spec-required components do NOT exist: `frontend/src/components/repo/` directory absent. No `RepoFilterBar`, `RepoFilterChips`, `RepoListItem`, `RepoListSkeleton`, `RepoEmptyState`, `RemoveConfirmDialog`, `UndoToast`, `useRepoList`. Department-tinted badge color map (5 distinct tints per spec) absent — page renders raw slug `equity_research` text in a generic chip.
- Spec controls missing: search debounce, "Filters" dropdown button (spec §Controls Bar) with department checklist + date range pickers, dismissible filter chips with `× Clear all`, sort `<DropdownMenu>` with `Check` icon on active, three-dot loading footer, "All reports loaded" footer present but un-styled, skeleton (8 rows) absent, empty-state icons + sub-text wrong copy, remove modal lacks Radix focus-trap + destructive button styling, toast lacks Framer Motion enter/exit and is centered (spec is `bottom-4 right-4`), undo "restored" success toast missing, error toast missing.
- URL state missing: spec design rule 6 + plan §Design Rules 6 require `?q=&department=&sort=&page=` via `useSearchParams`. Current page keeps state in `useState` only — bookmarks/back-button broken.
- Date range filters are wired in the API client (`generated_from / generated_to / saved_from / saved_to`) but the page provides NO UI to set them — the controls bar has only search + sort + per-facet department toggle.
- `loadPage` reset effect runs on every `q` keystroke without debounce — fires N requests per typed character.
- Removal flow does NOT call `unsaveFromRepo` until confirm, but on failure the row is restored to position 0 instead of original index (state bug).
- Open-from-Repo behavior: spec §FileViewer Panel from Repo says "no SaveToRepo button (the report is already saved)". `ViewerHeader` always renders `SaveToRepoButton` when `reportId` is present — there is no `hideSaveToRepo` / source-context flag. Even once click-to-open is wired, the Save button will appear erroneously.

**Root cause classification:** mixed — DEFERRED for the spec UI polish (decomposition, badge colors, Radix dialog, undo toast, skeleton, infinite-scroll observer, URL state, date range UI) and IMPLEMENTER for the headline missing FileViewer integration which is explicitly in the plan (Task 16 step 16.5 says "row `onClick` opens FileViewer"). FileViewer integration is **not** in the deferred list.

---

## Tasks (execution order)

### NEW-22-01 — Mount `FileViewerProvider` + `<FileViewer>` in the authenticated app layout

- Files: `frontend/src/layouts/AppLayout.tsx` (or whichever wraps authenticated routes — verify by tracing `router/routes.tsx` line 50). Wrap children with `FileViewerProvider`; render `<FileViewer />` panel adjacent to the main content column so it can slide in from the right.
- Plan ref: Task 16 + Task 0 step 0.3 (gate verifies the context exists; gate did not verify it is mounted).
- Spec ref: §5 "Open Report in FileViewer" — chat area shifts left to accommodate the panel.
- Acceptance: vitest renders any authenticated route, asserts `useFileViewer()` is consumable; visual check `<aside data-testid="file-viewer">` in DOM tree.

### NEW-22-02 — Wire row click-to-open in Repository.tsx (P1-09 in master tracker)

- Files: `frontend/src/pages/Repository.tsx` — import `useFileViewer` and `kindFromFilename` from `components/viewer/FileViewerContext`. Add `onClick` on the `<li>` that calls `open({ filename: row.filename, kind: "pdf", metadata: \`${departmentLabel(row.department)} · Generated ${formatDate(row.generated_at)} · Saved ${formatDate(row.saved_at)}\`, source: { kind: "report", reportId: row.report_id }, initialSaved: true })`. Stop propagation on Download anchor + Remove button so clicks on actions don't open the viewer.
- Spec ref: §5 + §FileViewer Panel from Repo (header shows filename, department, both timestamps).
- Acceptance: vitest — render Repository inside `FileViewerProvider`, click row, assert FileViewer panel renders with the three header fields; clicking Remove or Download does NOT open the viewer.

### NEW-22-03 — Add `hideSaveToRepoButton` flag to `FileViewerTarget` and respect in `ViewerHeader`

- Files: `frontend/src/components/viewer/FileViewerContext.tsx` (extend `FileViewerTarget` with optional `hideSaveToRepoButton?: boolean`); `frontend/src/components/viewer/FileViewer.tsx` (forward to header); `frontend/src/components/viewer/ViewerHeader.tsx` (skip rendering `<SaveToRepoButton>` when flag true).
- Spec ref: §FileViewer Panel from Repo — "Download + Close buttons only — no Save to Repo button".
- Acceptance: vitest — open via Repository sets flag; header shows Download + Close, no Save button. Existing usages from chat / department pages remain unchanged (default false).

### NEW-22-04 — Extract `useRepoList` hook with URL-state + IntersectionObserver infinite scroll

- Files: `frontend/src/hooks/useRepoList.ts` (new); consume in `Repository.tsx` to replace inline `useState`/`useEffect`/`loadPage`. Persist `q`, `department[]`, `generated_from`, `generated_to`, `saved_from`, `saved_to`, `sort`, `page` via `useSearchParams` from `react-router-dom`. Debounce `q` changes 250 ms before refetch. Expose `{ rows, hasMore, loading, error, loadMore, sentinelRef, params, setParams, removeRow, restoreRow }`. Use IntersectionObserver attached to `sentinelRef` to trigger `loadMore` (50/page).
- Plan ref: Tasks 9 (hook), Design Rule 5 (50/page), Design Rule 6 (URL state).
- Spec ref: §Infinite Scroll, §Controls Bar (search live-as-you-type — debounce required).
- Acceptance: hook test verifies (a) page-size 50 default, (b) `loadMore` appends not replaces, (c) URL params round-trip, (d) `q` debounce coalesces rapid changes into one fetch, (e) IntersectionObserver fires `loadMore` when sentinel intersects.

### NEW-22-05 — Build the Filters dropdown (department checklist + date range pickers)

- Files: `frontend/src/components/repo/RepoFilterBar.tsx` (new) — search input + Filters button + sort trigger; `frontend/src/components/repo/FiltersDropdown.tsx` (new) using Radix `Popover`, contains department checklist (sourced from `fetchRepoFacets`) + two `<input type="date">` pairs ("Generated From/To", "Saved From/To") + "Apply" accent button + active state on Filters button when filters non-empty.
- Spec ref: §Controls Bar, §Filters Dropdown (300px panel, section labels, checkbox + date input styling).
- Acceptance: vitest — opens dropdown, ticks two departments, picks a date range, clicks Apply → `useRepoList` params updated and one network call fired with the chosen query string.

### NEW-22-06 — Build active filter chips with dismiss + "Clear all"

- Files: `frontend/src/components/repo/RepoFilterChips.tsx` (new) — render one chip per active filter (each department slug, each populated date range as `Generated: Apr 1 – Apr 30`, search `q="aapl"`). `×` icon dismisses individual filter; "Clear all" link dismisses everything; container hidden when no filters.
- Spec ref: §Active Filter Chips (chip styling, "Clear all" `ml-auto`).
- Acceptance: vitest — sets filters via hook setter, asserts correct chip labels render; click `×` removes one, click "Clear all" clears state and URL.

### NEW-22-07 — Build sort dropdown using Radix `DropdownMenu`

- Files: `frontend/src/components/repo/SortDropdown.tsx` (new) — trigger format "Sort: Date Saved (newest)", chevron-down icon (12 px); menu with all six options, active row gets `Check` icon + accent-primary text.
- Spec ref: §Sort Control. Six options spec-listed match `RepoSort` union in `api/repo.ts`.
- Acceptance: vitest — open menu, click each option, assert label updates and hook fires fetch with new `sort` param.

### NEW-22-08 — Build `RepoListItem`, `RepoListSkeleton`, `RepoEmptyState` with department badge color map

- Files: `frontend/src/components/repo/RepoListItem.tsx` (new) — `FileText` Lucide icon (20px), filename, department badge, metadata line, action buttons revealed on hover (`group-hover:opacity-100` pattern, always visible on touch via `@media (hover: none)`); `frontend/src/components/repo/RepoListSkeleton.tsx` (new) — 8 skeleton rows with varying widths 40/55/35/50%; `frontend/src/components/repo/RepoEmptyState.tsx` (new) — handles BOTH "no saved reports" (`BookOpen` icon, copy "Save a report from any department to see it here.") and "no match" (`SearchX` icon, copy "Try adjusting your filters or search terms.", "Clear filters" link); `frontend/src/lib/department-colors.ts` (new) — exports `departmentBadgeClass(slug)` returning the 5-tint class string from spec §Report Entry Row → Department badge (`equity_research`, `earnings_update`, `morning_briefing`, `retail_sentiment`, `secretary` — note the spec also names "Macro" mapped to warning tint; include macro-research per Plan 19 even though spec dropdown lists 5).
- Spec ref: §Report Entry Row, §Loading State, §Empty States.
- Acceptance: snapshot test asserts each department slug → spec class pair; skeleton renders 8 rows; empty state switches mode based on hook params.

### NEW-22-09 — Replace removal modal with Radix `Dialog` + Framer Motion fade

- Files: `frontend/src/components/repo/RemoveConfirmDialog.tsx` (new) — Radix `Dialog` with focus-trap, max-width 400, destructive Remove button styled `bg-feedback-error text-white`, Cancel outline button. On confirm, animate row fade `opacity 1->0, height -> 0, 200ms` before unmount.
- Spec ref: §Remove Report Confirmation Modal.
- Acceptance: vitest — Esc closes, focus returns to trigger; remove → row fades out.

### NEW-22-10 — Replace toast with spec'd undo toast (Framer Motion + bottom-right)

- Files: `frontend/src/components/repo/UndoToast.tsx` (new) — `fixed bottom-4 right-4`, enter `opacity 0->1 y 8->0 200ms`, exit `opacity 1->0 150ms`. Renders three variants: removed-with-undo, restored ("Report restored.", 2s), error ("Failed to remove. Try again.", 4s, error color).
- Spec ref: §Toast Notifications. Restore on Undo re-POSTs `/repo/items` (idempotent per Plan 22 Design Rule 4).
- Acceptance: vitest — remove fires unsave, undo within 4 s fires save and shows "Report restored."; failure shows error toast and re-inserts row at original index (fixes existing bug where it goes to index 0).

### NEW-22-11 — Compose `Repository.tsx` from new pieces (target <120 LOC)

- Files: `frontend/src/pages/Repository.tsx` (rewrite) — import `useRepoList`, render `<RepoFilterBar>`, `<RepoFilterChips>`, `<SortDropdown>`, conditional `<RepoListSkeleton>` / list / `<RepoEmptyState>`, sentinel `<div ref={sentinelRef}>`, footer ("All reports loaded" or three-dot loading), `<RemoveConfirmDialog>`, `<UndoToast>`. Apply spec layout shell (56 px header, divide-y bordered list `mx-6 my-2`).
- Spec ref: §Layout, §Page Header.
- Acceptance: file is <120 LOC; integration test exercises type-search → debounced fetch → row click → viewer open → close → remove → undo → load-more.

### NEW-22-12 — Backfill frontend tests for hook + components + integration

- Files: `frontend/src/hooks/__tests__/useRepoList.test.ts`; `frontend/src/components/repo/__tests__/{RepoFilterBar,RepoFilterChips,SortDropdown,RepoListItem,RepoListSkeleton,RepoEmptyState,RemoveConfirmDialog,UndoToast,FiltersDropdown}.test.tsx`; expand `frontend/src/pages/__tests__/Repository.test.tsx` to cover (a) sort change, (b) load-more pagination, (c) URL param round-trip, (d) error path, (e) filter chip dismiss, (f) date range filter, (g) FileViewer open + Save button suppressed.
- Plan ref: Task 16 lists the integration assertions (steps 16.6 – 16.10).
- Acceptance: `cd frontend && npm run test -- repo` — at least 30 new assertions; existing 3 tests still pass.

### NEW-22-13 — Backfill server route tests for negative + pagination edge cases

- Files: `packages/server/tests/test_routes/test_repo_filter_routes.py` — verify the file contains tests already shipped per Plan 22 Task 3 and add any gaps: `page=0` -> 422, `page_size=201` -> 422, `q=""` (empty string) treated as no filter, mixed CSV + repeatable `?department=a&department=b,c` union-deduped, `saved_from > saved_to` returns empty (not 422), authenticated cross-user isolation, `has_more` flag exact at boundary `len(items)==page_size` AND `total>page*page_size`. Re-verify against shipped test file (128 LOC) — add only the missing cases.
- Plan ref: Task 3 acceptance assertions. The shipped file omits the page/page_size cap negative tests and the cross-user isolation test.
- Acceptance: `uv run pytest packages/server/tests/test_routes/test_repo_filter_routes.py -q` green; coverage delta ≥+5 lines.

### NEW-22-14 — Sidebar link + route registration verification

- Files: `frontend/src/router/routes.tsx` (line 50 has the route), `frontend/src/components/sidebar/navData.ts` (line 35 has the label). Add a smoke test in `frontend/src/App.test.tsx` (or new) that navigates to `/repository` and asserts the page renders.
- Plan ref: Task 17.
- Acceptance: vitest passes navigation smoke; manual `npm run dev` -> click sidebar -> page loads.

### NEW-22-15 — Contract matrix + auth matrix doc updates

- Files: `planning/specs/systems/endpoint-contract-matrix.md` and `planning/specs/systems/route-authorization-matrix.md` — add rows for `GET /repo/items` (filtered + paginated shape) and `GET /repo/facets` if not already present. Verify against current docs before editing.
- Plan ref: Task 7.
- Acceptance: matrix rows present, `q / department / generated_from / generated_to / saved_from / saved_to / sort / page / page_size` enumerated; auth matrix says `require_auth`, owner-scoped, no admin escalation.

---

## Verification

```
uv run ruff check packages/server/src/openlia_server/routes/repo.py packages/server/src/openlia_server/services/repo.py
uv run pytest packages/server/tests/test_services/test_repo_filtered.py packages/server/tests/test_routes/test_repo_filter_routes.py packages/server/tests/test_routes/test_repo_routes.py packages/server/tests/test_services/test_repo.py -q
cd frontend && npm run test -- repo viewer
cd frontend && npm run build
```

Manual: `uv run openlia serve` + `cd frontend && npm run dev` → log in → save 60+ reports across departments → `/repository` → exercise search debounce, sort, department checklist, date range, infinite scroll past page 1, click row to open FileViewer (no Save button visible), download, remove + undo, remove + let toast expire, refresh page (URL params restore filters).

---

## Counts

- Plan tasks 0–18 → shipped: backend (Tasks 0–7) and route registration + sidebar (parts of 17). Deferred or partial: Tasks 8 (api client done; tests thin), 9 (`useRepoList` missing), 10–15 (all seven components missing), 16 (page is monolith without spec UI, no FileViewer wiring, no URL state), 17 (no smoke nav test), 18 (aggregate suite incomplete).
- New IDs added: NEW-22-01 through NEW-22-15 (15 total). Existing NEW-22-01..04 from prior fix-plan reabsorbed into the broader list.
