# Morning Briefing — Save-to-Repo / Download / Delete Wiring

**Date:** 2026-06-02
**Status:** Approved (design)
**Depends on:** Morning Briefing rework (PR #240, merged as `7c379f8d`)

## Goal

Make the three report-level affordances work for Morning Briefing (MB)
briefings, matching how Earnings Update v2 (EU) and Equity Research v3
(v3) already behave: **save-to-repo**, **download**, **delete**.

## Finding: backend complete; download + delete already wired

A full trace shows the backend is entirely in place and two of the three
affordances already work in the live UI. The only real gap is the
**save-to-repo** frontend wiring (and the Repository page's handling of
saved MB rows).

| Affordance | Backend | Frontend status |
| --- | --- | --- |
| Download (html/pdf/docx) | `GET /api/.../morning-briefing/runs/{id}/{html,pdf,docx}` | Already renders in the MB viewer header: `ReportDownloadButton engine="mb"` + Standalone HTML link (`mbHtmlUrl`). `downloadReportBlob` already has the `mb` branch. No work. |
| Delete | `DELETE /api/.../morning-briefing/runs/{id}` | Already wired: MB feed cards (`onRemove` → `ConfirmDialog` → `deleteMbRun`) and the viewer (`onDelete` → `ConfirmDialog` → `deleteMbRun`). No work. |
| Save-to-repo | `POST/DELETE/GET /api/repo/mb-runs`; `repo.list_items_filtered` already fans out MB rows with `engine="mb_v2"` | **Unwired.** Button is hidden in the MB viewer; `SaveToRepoButton`/`SaveToRepoEngine`/`SavedReportsContext` have no `mb` bucket; the Repository page has no `mb_v2` branch, so a saved MB row would fall through to the v1 path and break on open/delete/remove. |

This spec therefore covers **only** the save-to-repo wiring. Download and
delete are documented above as verified-working; they are out of scope
beyond a regression check.

## Architecture

Mirror the existing **`eu` engine** path end-to-end. The MB save flow is
structurally identical to EU's: a per-engine saved-id bucket in
`SavedReportsContext`, an engine discriminant on `SaveToRepoButton`, repo
API helpers hitting the MB-specific endpoints, and `engine === "mb_v2"`
branches on the Repository page.

### Data flow (save)

```
MB viewer header
  -> SaveToRepoButton (engine="mb")
     -> api/repo.saveMbRunToRepo(reportId)  POST /api/repo/mb-runs {mb_v2_report_id}
     -> SavedReportsContext.markMbSaved(reportId)
SavedReportsContext hydrates on mount via listSavedMbRuns()  GET /api/repo/mb-runs
```

### Repository page (saved MB row)

```
RepoRow {engine: "mb_v2", report_id: report_mb.id}
  open   -> FileViewer source {kind: "mb_report"}, initialSaved: true, hideSaveToRepoButton: true
  remove -> unsaveMbRunFromRepo + markMbUnsaved (briefing survives in the MB feed); undo re-saves
  delete -> deleteMbRun  (hard-delete: gone from repo AND the MB feed — parity with v1/v3)
```

**Decision (approved):** Repository-page **Delete** hard-deletes the
briefing via `deleteMbRun` (MB has a real delete endpoint, unlike EU).
**Remove** only unsaves.

## Components to change

All changes are frontend-only. No backend, migration, or i18n changes
(the save button labels are hardcoded strings already, matching EU).

### 1. `frontend/src/api/repo.ts`
- `RepoEngine`: add `"mb_v2"`.
- Add `saveMbRunToRepo(reportId)` → `POST /api/repo/mb-runs` body
  `{ mb_v2_report_id: reportId }`.
- Add `unsaveMbRunFromRepo(reportId)` → `DELETE /api/repo/mb-runs?mb_v2_report_id=...`.
- Add `listSavedMbRuns()` → `GET /api/repo/mb-runs` returning
  `{ saved_report_ids: string[] }`.

### 2. `frontend/src/components/repo/SavedReportsContext.tsx`
- Add a `savedMbIds` set + `isMbSaved` / `markMbSaved` / `markMbUnsaved`,
  mirroring the `eu` bucket exactly.
- Hydrate on mount via `listSavedMbRuns()` (best-effort `.catch`).
- Extend `ContextShape`, the `value` object, and its memo deps.

### 3. `frontend/src/components/chat/SaveToRepoButton.tsx`
- `SaveToRepoEngine`: add `"mb"`.
- Add the `mb` branch to `ctxIsSaved`, save, and unsave (calls
  `saveMbRunToRepo`/`unsaveMbRunFromRepo` + `markMbSaved`/`markMbUnsaved`).

### 4. `frontend/src/components/viewer/ViewerHeader.tsx`
- Remove the `engine={saveEngine === "mb" ? "v1" : saveEngine}` collapse;
  pass `engine={saveEngine}` through (the `SaveToRepoEngine` union now
  includes `"mb"`). Update the stale comment.

### 5. `frontend/src/components/viewer/FileViewer.tsx`
- Extend the `reportId` ternary to pass `source.reportId` for
  `mb_report`.
- Extend the `saveEngine` ternary to return `"mb"` for `mb_report`.

### 6. `frontend/src/pages/departments/MorningBriefing.tsx`
- In `openReport`, drop `hideSaveToRepoButton: true` so the save button
  renders (EU sets neither flag — the button is ctx-driven via
  `isMbSaved`). Keep `onDelete`.

### 7. `frontend/src/pages/Repository.tsx`
- Import `saveMbRunToRepo` / `unsaveMbRunFromRepo` and `deleteMbRun`
  (from `api/morning-briefing`).
- `handleOpen`: add `row.engine === "mb_v2"` → open with
  `source: { kind: "mb_report", reportId: row.report_id }`,
  `initialSaved: true`, `hideSaveToRepoButton: true`.
- `confirmDelete`: add `mb_v2` → `deleteMbRun(row.report_id)` +
  `markMbUnsaved`.
- `confirmRemove`: add `mb_v2` → `unsaveMbRunFromRepo` + `markMbUnsaved`;
  undo → `saveMbRunToRepo` + `markMbSaved`.

## Testing

Mirror the existing EU-engine tests:
- `SaveToRepoButton.test.tsx` — an `engine="mb"` case hits the MB
  save/unsave endpoints and toggles state.
- `SavedReportsContext` — hydration from `listSavedMbRuns` populates
  `isMbSaved` (extend existing context test if present, else add).
- `ViewerHeader.test.tsx` — `mb_report` source with `saveEngine="mb"`
  renders the save button with `engine="mb"` (no longer collapsed).
- `Repository.test.tsx` — an `mb_v2` row opens the `mb_report` viewer;
  Delete calls `deleteMbRun`; Remove calls `unsaveMbRunFromRepo`.
- `MorningBriefing.test.tsx` — opening a briefing shows the save button
  (no `hideSaveToRepoButton`).
- Regression: existing MB viewer download + delete tests stay green.

Run: `npm run test -- morning-briefing repo SaveToRepo ViewerHeader Repository`,
`npx tsc --noEmit`, and the server repo suite
(`uv run pytest packages/server/tests/test_services/test_repo_mb_listing.py packages/server/tests/test_routes/` for the repo route) as a backend regression guard.

## Out of scope
- Download and delete affordances (already working — verified above).
- Any backend change (all MB repo endpoints + the repo fan-out exist).
- Card-level download buttons in the MB feed (EU also only downloads from
  the viewer; no parity gap).
