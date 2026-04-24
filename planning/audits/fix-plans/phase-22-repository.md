# Phase 22 — Repository fix plan (→ 100%)


**Current:** ~65% shipped. **Root cause:** mixed (IMPLEMENTER monolith + missing FileViewer integration).

**Gap summary:** `Repository.tsx` is ~340-line single file; spec's primary "Open Report in FileViewer" interaction missing; no `useRepoList` hook; toasts/skeleton/dept badge colors inline or absent.

**Tasks (in execution order):**

1. **P1-09 — Wire FileViewer click-to-open from Repository rows** (also required in Phase 12 entry — coordinate PRs).
   - Files: `Repository.tsx` (import `useFileViewer`; row `onClick={() => openViewer({...})}`); `FileViewer.tsx` (suppress SaveToRepo when opened from Repo).
   - Spec ref: Functionality §5 "Open Report in FileViewer".
   - Acceptance: vitest — click row → FileViewer panel opens with header showing filename + department + both timestamps; no SaveToRepo button visible.

2. **NEW-22-01 — Extract `useRepoList` hook with infinite scroll + facets query.**
   - Files: `frontend/src/hooks/useRepoList.ts` (new); consume in `Repository.tsx`.
   - Spec ref: "Infinite Scroll" (50/page).
   - Acceptance: hook test verifies page-size 50, `loadMore` appends.

3. **NEW-22-02 — Decompose `Repository.tsx` into spec components.**
   - Files: create under `frontend/src/components/repo/`: `RepoFilterBar.tsx`, `RepoFilterChips.tsx`, `RepoListItem.tsx`, `RepoListSkeleton.tsx`, `RepoEmptyState.tsx`, `RemoveConfirmDialog.tsx`, `UndoToast.tsx`. Reduce `Repository.tsx` to composition.
   - Plan ref: Tasks 10–15.
   - Spec ref: UI Design sections.
   - Acceptance: vitest per component; `Repository.tsx` < 100 LOC.

4. **NEW-22-03 — Department-tinted badges per spec color mapping.**
   - Files: `RepoListItem.tsx` (badge class map); `frontend/src/lib/department-colors.ts` (new shared).
   - Spec ref: "Report Entry Row → Department badge" (5 distinct tints).
   - Acceptance: snapshot test asserts each department slug resolves to its spec color pair.

5. **NEW-22-04 — Undo toast on remove (restore via idempotent save).**
   - Files: `UndoToast.tsx`; `frontend/src/api/repo.ts` restore call.
   - Spec ref: "Toast Notifications" (4s + Undo link).
   - Acceptance: remove then Undo within 4s restores row + shows "Report restored."

**Verification:** `cd frontend && npm run test -- repo && npm run test -- viewer` plus manual click-through in `/repo`.
