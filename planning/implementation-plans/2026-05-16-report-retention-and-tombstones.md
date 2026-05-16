# Report Retention & Tombstones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make unsaved reports ephemeral — they auto-expire 7 days after `created_at` unless the user has saved them to the Repository. Saved reports persist indefinitely until the user manually deletes them via a destructive, confirmed action (only available after the 7-day grace window). Expired and manually-deleted reports both leave a "no longer available" tombstone in the Equity Research chat artifact card so conversation history is preserved verbatim, while other surfaces (Repository, Earnings Update list, Morning Briefing archive) filter dead reports out.

**Architecture:**
- **DB**: one new nullable column `Report.expired_at`. Alembic migration only — no new tables, no FK changes.
- **Service**: extract a single `tombstone_report(db, report_id)` operation in a new `services/reports.py` that is invoked by both the API delete route and the nightly sweep, guaranteeing one write shape for the tombstone end state.
- **API**:
  - `GET /reports` adds an opt-in `include_expired=true` query param (default false). List rows expose `expired_at`.
  - `GET /reports/{id}` always returns the row regardless of `expired_at`; payload exposes `expired_at`. Body fields are empty strings on tombstoned rows.
  - Export routes (`/render`, `/export/pdf`, `/export/docx`) return **410 Gone** when `expired_at IS NOT NULL`.
  - `DELETE /reports/{id}` switches from `session.delete(row)` to `tombstone_report(...)`.
  - `DELETE /repo/items?report_id=...` is unchanged (soft `RepoItem` removal).
- **Sweep**: `MaintenanceExecutor.run_maintenance_once` gains two new steps — tombstone owned-but-orphaned-of-repo reports older than `OPENLIA_UNSAVED_REPORT_RETENTION_DAYS` (default 7), and hard-delete orphan reports (`user_id IS NULL`) older than the same cutoff.
- **Frontend**:
  - `api/reports.ts` adds `include_expired` param plumbing, `deleteReport(reportId)`, exposes `expired_at` on list/detail types.
  - `api/repo.ts` keeps `unsaveFromRepo()` (soft).
  - All four report-card surfaces become **age-aware**: <7d shows the save/unsave toggle; ≥7d + saved shows a "Delete" button that opens a single shared `<DeleteReportDialog>`. The EquityResearch chat artifact card additionally renders a "Report no longer available" state when `expired_at` is set.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2.
- Frontend: React 18 + TypeScript strict, Radix UI `AlertDialog`, Vitest + React Testing Library.

**Dependencies:**
- Plan 1a (`reports`, `report_versions`, `repo_items` tables; `MaintenanceExecutor`).
- Plan 13 (`/reports/{id}` route surface).
- Plan 22 (Repository page row component, soft-unsave toggle).
- Slice 9–12 (`GraphArtifactSummary`, `recall_artifacts`).

**Unblocks:** removes the unbounded growth of throwaway reports without forcing users to manage cleanup themselves.

---

## Design Rules

1. **One clock: `Report.created_at`.** No "last viewed" tracking. No clock reset on unsave.
2. **One end state, two triggers.** `tombstone_report(db, report_id)` is the only write that produces a tombstone. Both the route and the sweep call it. The function is idempotent (re-tombstoning is a no-op if `expired_at IS NOT NULL`).
3. **Tombstone shape (single transaction):**
   1. `UPDATE reports SET content_markdown='', content_structured='{}', expired_at=:now WHERE id=:id AND expired_at IS NULL`.
   2. `DELETE FROM report_versions WHERE report_id=:id`.
   3. `DELETE FROM repo_items WHERE report_id=:id`.
   4. `DELETE FROM graph_artifact_summaries WHERE artifact_kind='report' AND artifact_id=:id`.
4. **Orphan reports are hard-deleted, not tombstoned.** No chat history to anchor; no user to view them. Sweep uses a separate branch.
5. **Age boundary is strict `>=`.** A report exactly 7 days old (to the microsecond) is eligible for the destructive flows.
6. **Retention is configurable.** `OPENLIA_UNSAVED_REPORT_RETENTION_DAYS` env var, default `7`. Read inside `run_maintenance_once` per call (consistent with `LIA_GUARDRAIL_LOG_RETENTION_DAYS`).
7. **The frontend determines which button to render based on `created_at` + saved state.** No new fields needed for the button matrix; just a `now()` reference and an `isSaved` boolean. The age check uses the user's local clock — acceptable drift since the destructive button only differs in label by ±a few seconds at the boundary, and the server re-checks nothing (the API does whatever the user requested).
8. **Tombstoned reports appear in `GET /reports` only when `include_expired=true`.** Today's callsites (EU `RecentReportsList`, MB `MBArchiveView`, the Repository page's repo-row queries) do **not** opt in, so dead reports vanish from those listings naturally. The EquityResearch session-restore call (`pages/departments/EquityResearch.tsx:206`) is the only caller that flips `include_expired=true`.
9. **Detail endpoint never 404s a tombstone.** Callers always get the row plus `expired_at`. Body fields are empty strings. This is what keeps the EquityResearch chat artifact tombstone renderable on hard reload.
10. **Export endpoints return 410 Gone on tombstones.** Consistent HTTP semantics ("the resource was here, it is intentionally gone"). The frontend `ReportDownloadButton` should treat 410 as "show a non-retriable error toast" (the download is moot if the body is dead).
11. **Confirmation dialog is single + reused.** Lives at `frontend/src/components/report/DeleteReportDialog.tsx`. Body copy explicitly mentions the chat-history tombstone so the user is not surprised later.
12. **No new job type.** The sweep step lives inside the existing `run_maintenance_once` so its schedule, recovery, and observability all come for free.
13. **No release-note grace period.** First post-deploy sweep tombstones the existing backlog. The CHANGELOG entry calls out the new behavior; that's the only special handling.

---

## Wire Shapes (Locked)

### `GET /reports`
**Query (new):** `include_expired: bool = false`.
**Per-row shape (new field):**
```json
{
  "id": "...",
  "department": "equity_research",
  "report_type": "...",
  "title": "...",
  "subject": "AAPL",
  "created_at": "2026-05-16T20:00:00Z",
  "expired_at": null
}
```
When `include_expired=false` (default), `expired_at IS NOT NULL` rows are filtered out server-side. When `true`, rows are returned including the tombstones.

### `GET /reports/{id}`
**Always returns 200** for any row owned by the requester, regardless of `expired_at`. Payload gains `expired_at: string | null`. On tombstones, `content_markdown == ""` and `content_structured == {}`; the schema fields are present but empty.

### `GET /reports/{id}/render`, `/export/pdf`, `/export/docx`
Return **410 Gone** when `expired_at IS NOT NULL`. Body: `{"detail": {"code": "report_expired", "message": "This report has expired and is no longer available."}}`.

### `DELETE /reports/{id}`
Authz unchanged (`Report.user_id == user.id`). 404 if not found. Otherwise runs `tombstone_report(db, report_id)` and returns **204 No Content**. The route does NOT enforce the "age >= 7d" rule server-side — the frontend gates which button to show; the backend trusts the caller. (We could add an age gate; see Q&A in §Open Questions.)

### `DELETE /repo/items?report_id=...`
Unchanged. Removes `RepoItem` only.

---

## Files Touched (Reference)

**New files:**
- `packages/server/src/openlia_server/services/reports.py` — `tombstone_report(db, report_id)`.
- `packages/server/src/openlia_server/db/migrations/versions/2026-05-16-XXXX_reports_expired_at.py`.
- `frontend/src/components/report/DeleteReportDialog.tsx`.
- `packages/server/tests/services/test_reports_tombstone.py`.

**Modified backend:**
- `packages/server/src/openlia_server/db/models/content.py` — add `expired_at` column to `Report`.
- `packages/server/src/openlia_server/routes/reports.py` — `include_expired` param on list; `expired_at` on list + detail responses; tombstone in DELETE; 410 in export routes.
- `packages/server/src/openlia_server/scheduler/executors/maintenance.py` — two new sweep branches (tombstone + orphan hard-delete); env-var config; new keys in summary dict.
- `packages/server/src/openlia_server/services/repo.py` — list queries gain an implicit `expired_at IS NULL` filter (saved-but-tombstoned shouldn't appear in Repository anyway because we delete `RepoItem` on tombstone, but the filter is belt-and-suspenders).
- `packages/server/tests/scheduler/test_maintenance.py` — new cases.
- `packages/server/tests/routes/test_reports.py` — new cases.
- `packages/server/tests/routes/test_repo.py` — sanity check soft path still works.

**Modified frontend:**
- `frontend/src/api/reports.ts` — types + `include_expired` plumbing + `deleteReport()`.
- `frontend/src/pages/Repository.tsx` — age-aware action per row (currently always soft unsave).
- `frontend/src/pages/departments/EquityResearch.tsx` — pass `include_expired=true` on session-restore listReports; render tombstone state in `<ReportCard>`.
- `frontend/src/components/equity-research/ReportCard.tsx` — accept `expiredAt` prop, render tombstone variant, render age-aware action button.
- `frontend/src/components/earnings-update/RecentReportsList.tsx` — render age-aware action button per row (default flow already filters expired since `include_expired` defaults false).
- `frontend/src/components/morning-briefing/MBReportCard.tsx` — render age-aware action button.
- `frontend/src/hooks/useMbReports.ts` — no behavior change; types may pick up `expired_at | null`.
- `frontend/src/components/report/ReportDownloadButton.tsx` — handle 410 with a one-line error toast/message.
- Test files for each modified component.

---

## Implementation Phases

### Phase 0 — Pre-work (no code)

- [ ] Re-read this plan top to bottom.
- [ ] Run `git status` and confirm a clean working tree before starting.
- [ ] Confirm current branch is appropriate (a new feature branch off `main`, e.g. `feat/report-retention`).
- [ ] Skim `packages/server/src/openlia_server/scheduler/executors/maintenance.py` to internalize the existing sweep shape; the new sweep step must match style.

### Phase 1 — DB column + migration

- [ ] Add `expired_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)` to `Report` in `packages/server/src/openlia_server/db/models/content.py`. Index it: `Index("ix_reports_expired_at", "expired_at")` (small selectivity but the sweep query and the list filter both use it).
- [ ] Generate Alembic migration: `uv run alembic -c packages/server/alembic.ini revision -m "reports_expired_at"`. Edit the autogen to be explicit:
  - `op.add_column("reports", sa.Column("expired_at", UTCDateTime(), nullable=True))`
  - `op.create_index("ix_reports_expired_at", "reports", ["expired_at"])`
  - Downgrade: drop index then drop column.
- [ ] `uv run alembic -c packages/server/alembic.ini upgrade head` against the dev DB to verify.
- [ ] Run `uv run pytest packages/server/tests/db/` and the existing maintenance/report tests to verify no regression from the schema change.

### Phase 2 — Shared `tombstone_report` service

- [ ] Create `packages/server/src/openlia_server/services/reports.py` with:
  ```python
  def tombstone_report(db: Session, *, report_id: str) -> bool:
      """Tombstone a report: blank body, drop versions + repo_items + graph
      artifact summary, set expired_at. Idempotent (no-op if already
      tombstoned). Returns True if any state changed, False if already
      tombstoned or not found.
      """
  ```
  Implementation in a single transaction. Use `select` to fetch the row first; if `row is None`, return False; if `row.expired_at is not None`, return False (idempotent).
- [ ] Add unit tests in `packages/server/tests/services/test_reports_tombstone.py`:
  - Tombstones an owned, saved, content-bearing report → body emptied, `expired_at` set, `report_versions` rows for that report deleted, `repo_items` for that report deleted, `GraphArtifactSummary` for `(artifact_kind='report', artifact_id=report.id)` deleted.
  - Tombstoning an unsaved report works (no `repo_items` row exists; no error).
  - Tombstoning a report with no `GraphArtifactSummary` row works (no error).
  - Re-tombstoning is a no-op (returns False; row unchanged).
  - Tombstoning a missing report returns False.
- [ ] Run `uv run pytest packages/server/tests/services/test_reports_tombstone.py`.

### Phase 3 — API route changes

- [ ] `GET /reports` (list): add `include_expired: bool = Query(False)`. When `False`, append `Report.expired_at.is_(None)` to the query. Add `expired_at` to the per-row response model.
- [ ] `GET /reports/{id}`: confirm the route does NOT short-circuit on `expired_at`; always returns the row. Add `expired_at` to the response model. Body fields stay as-is (empty strings on tombstones).
- [ ] `GET /reports/{id}/render`, `/export/pdf`, `/export/docx`: at the top of each handler, after the row is fetched, check `if row.expired_at is not None: raise HTTPException(status_code=410, detail={"code": "report_expired", "message": "..."})`.
- [ ] `DELETE /reports/{id}`: replace `session.delete(row); session.commit()` with `tombstone_report(session, report_id=report_id); session.commit()`. Keep the existing 404 check.
- [ ] Update `packages/server/tests/routes/test_reports.py`:
  - List: with `include_expired` unset/false, a tombstoned row is filtered out; with `true`, it appears.
  - Detail: a tombstoned row returns 200 with `expired_at` set, body fields empty.
  - Export (each format): tombstoned row returns 410.
  - DELETE: a saved-and-content-bearing report becomes a tombstone (re-fetch the row, assert `expired_at` set, body empty); the `RepoItem` is gone; subsequent DELETE on the same report returns 204 (idempotent — `tombstone_report` returns False but the route still 204s).
  - DELETE other-user's report returns 404 (existing test should still pass).
- [ ] `services/repo.py`: in `list_items_filtered`, add `Report.expired_at.is_(None)` to the WHERE so a saved-then-tombstoned row (edge case: shouldn't exist because tombstone deletes `RepoItem`, but defense in depth) doesn't leak in.
- [ ] Run `uv run pytest packages/server/tests/routes/test_reports.py packages/server/tests/routes/test_repo.py`.

### Phase 4 — Sweep step

- [ ] Edit `packages/server/src/openlia_server/scheduler/executors/maintenance.py`:
  - Add constant `UNSAVED_REPORT_RETENTION_DAYS_DEFAULT = 7`.
  - At the top of `run_maintenance_once`, after `now = datetime.now(UTC)`, compute:
    ```python
    report_retention_days = int(os.environ.get(
        "OPENLIA_UNSAVED_REPORT_RETENTION_DAYS",
        UNSAVED_REPORT_RETENTION_DAYS_DEFAULT,
    ))
    report_cutoff = now - timedelta(days=report_retention_days)
    ```
  - Add the **tombstone branch** (owned reports):
    ```python
    candidate_ids = session.execute(
        select(Report.id)
        .where(
            Report.user_id.is_not(None),
            Report.expired_at.is_(None),
            Report.created_at < report_cutoff,
            ~exists().where(RepoItem.report_id == Report.id),
        )
    ).scalars().all()
    reports_tombstoned = 0
    for rid in candidate_ids:
        if tombstone_report(session, report_id=rid):
            reports_tombstoned += 1
    ```
    (Using the shared service guarantees identical end state. Acceptable performance: sweeps run nightly with typical counts in the hundreds.)
  - Add the **orphan hard-delete branch** (`user_id IS NULL`):
    ```python
    orphan_ids = session.execute(
        select(Report.id)
        .where(
            Report.user_id.is_(None),
            Report.created_at < report_cutoff,
        )
    ).scalars().all()
    if orphan_ids:
        session.execute(delete(GraphArtifactSummary).where(
            GraphArtifactSummary.artifact_kind == "report",
            GraphArtifactSummary.artifact_id.in_(orphan_ids),
        ))
        session.execute(delete(Report).where(Report.id.in_(orphan_ids)))
        # report_versions and repo_items cascade via FK.
    reports_hard_deleted = len(orphan_ids)
    ```
  - Append both counters to the returned summary dict: `"reports_tombstoned": int(reports_tombstoned)`, `"reports_hard_deleted": int(reports_hard_deleted)`.
- [ ] Edit `packages/server/tests/scheduler/test_maintenance.py`:
  - **Tombstone candidates**: owned report, no `RepoItem`, `created_at > cutoff` → still alive after sweep. Owned, saved, `created_at < cutoff` → still alive. Owned, unsaved, `created_at < cutoff` → tombstoned (body empty, `expired_at` set, no `report_versions`, no `GraphArtifactSummary`).
  - **Idempotence**: running the sweep twice doesn't double-count or error on already-tombstoned rows.
  - **Env override**: setting `OPENLIA_UNSAVED_REPORT_RETENTION_DAYS=30` keeps a 10-day-old unsaved report alive.
  - **Orphans**: `user_id IS NULL`, `created_at < cutoff` → row + cascaded `report_versions` + `GraphArtifactSummary` all gone. `user_id IS NULL`, `created_at > cutoff` → still alive.
  - **Summary dict**: contains both new keys with correct counts.
- [ ] Run `uv run pytest packages/server/tests/scheduler/test_maintenance.py`.

### Phase 5 — Frontend API client + types

- [ ] Edit `frontend/src/api/reports.ts`:
  - Add `expired_at: string | null` to both the list-row type and the detail type.
  - `listReports()` accepts a new optional `include_expired?: boolean` param; append `&include_expired=true` when true.
  - Add `deleteReport(reportId: string): Promise<void>` that does `DELETE /api/reports/${reportId}` and throws on non-2xx (no special 410 handling — the report being already gone is not a real failure case; if it happens, surface the error).
  - Export a helper `isReportExpired(reportRow: { expired_at: string | null }): boolean` for symmetry.
- [ ] Edit `frontend/src/api/morning-briefing.ts` (`fetchReports`): type pickup only; no behavior change.
- [ ] Edit `frontend/src/api/repo.ts`: no change to `unsaveFromRepo`.

### Phase 6 — Shared `<DeleteReportDialog>` component

- [ ] Create `frontend/src/components/report/DeleteReportDialog.tsx`:
  - Radix `AlertDialog` (it's already a project dependency — used by similar destructive flows; verify with `grep "AlertDialog" frontend/src`).
  - Props: `{ open: boolean; onOpenChange: (open: boolean) => void; reportTitle: string; onConfirm: () => Promise<void> | void; }`.
  - Title: `"Delete this report?"`.
  - Body: `"The report body and version history will be permanently removed. The card will remain in your chat history showing 'no longer available'. This cannot be undone."`.
  - Buttons: Cancel (default) / Delete (destructive variant, red).
  - On confirm: await `onConfirm()`, then `onOpenChange(false)`.
- [ ] Unit test: open/close, confirm calls `onConfirm` exactly once, cancel does not.

### Phase 7 — Surface 1: EquityResearch chat artifact

- [ ] Edit `frontend/src/pages/departments/EquityResearch.tsx`:
  - Update the `listReports` call at line 206 to pass `include_expired: true`. (This is the only callsite that needs the expired rows.)
  - When the latest report row has a non-null `expired_at`, do NOT call `fetchReport(id)` — there's no schema to load. Set `restoredReportId` to the row's id and pass a tombstone marker to `<ReportCard>` instead of a schema. (Cleanest signal: pass `schema={null}` and a separate `expiredAt={row.expired_at}` prop; ReportCard branches.)
- [ ] Edit `frontend/src/components/equity-research/ReportCard.tsx`:
  - Accept `expiredAt?: string | null` prop.
  - When `expiredAt` is set, render a tombstone variant: card chrome retained (title from props, created date from props), body replaced with a centered muted message "Report no longer available — automatically expired after 7 days" (or similar). No action buttons. No download button.
  - When `expiredAt` is null AND `isSaved && ageInDays(createdAt) >= 7`: replace the soft "Save/Unsave" toggle with a "Delete" button that opens `<DeleteReportDialog>` and on confirm calls `deleteReport(id)` then refreshes the parent state.
  - When `expiredAt` is null AND `ageInDays < 7`: existing save/unsave toggle behavior.
- [ ] Tests in `frontend/src/components/equity-research/ReportCard.test.tsx`:
  - Tombstone variant renders correctly given `expiredAt`.
  - Saved + <7d shows "Remove from repository" toggle.
  - Saved + ≥7d shows "Delete" button; clicking opens dialog; confirming calls `deleteReport`.
  - Unsaved + <7d shows "Add to repository" toggle.

### Phase 8 — Surface 2: Repository page row

- [ ] Edit `frontend/src/pages/Repository.tsx` (or the row component if extracted):
  - For each row, compute `ageDays = (now - generated_at) / 86400000`.
  - If `ageDays < 7`: existing "Remove from repository" soft-toggle (existing behavior, no confirmation per Plan 22's spec — actually Plan 22's spec DOES include a confirm dialog + undo toast for the soft path; keep it).
  - If `ageDays >= 7`: replace with "Delete" button that opens `<DeleteReportDialog>` and on confirm calls `deleteReport(id)`. The row should disappear from the list on success (refetch or local filter).
- [ ] Update existing Repository tests to cover both branches.

### Phase 9 — Surface 3: Earnings Update RecentReportsList

- [ ] Edit `frontend/src/components/earnings-update/RecentReportsList.tsx`:
  - Per-row action: today rows have a star/save toggle (verify by reading the file). Apply the same age-aware matrix.
  - Default list fetch path already excludes tombstones (no `include_expired`), so no tombstone variant needed here.
- [ ] Update component tests.

### Phase 10 — Surface 4: Morning Briefing MBReportCard

- [ ] Edit `frontend/src/components/morning-briefing/MBReportCard.tsx`:
  - Same age-aware matrix as Phase 9.
- [ ] Update component tests.

### Phase 11 — Export error handling

- [ ] Edit `frontend/src/components/report/ReportDownloadButton.tsx`:
  - On a 410 response from any format export, show a one-line non-retriable error ("This report has expired and is no longer available.") and disable the dropdown until the report ID changes.
- [ ] Component test for the 410 path.

### Phase 12 — End-to-end smoke

- [ ] Start the server (`uv run openlia serve`) and the frontend dev server (`cd frontend && npm run dev`).
- [ ] Manual smoke matrix:
  1. Generate a new Equity Research report. Verify the card shows "Add to repository" (or whatever the existing label is) and the report body renders.
  2. Save it. Verify the toggle label flips to "Remove from repository".
  3. Open the dev DB and **hand-tune the `created_at` to 8 days ago**: `UPDATE reports SET created_at = datetime('now', '-8 days') WHERE id = '...'`. Reload the page.
  4. Verify the action button is now "Delete" (red, destructive).
  5. Click Delete → dialog opens → cancel works → confirm fires, card switches to "Report no longer available" tombstone state, body is gone.
  6. Reload the chat session. Verify the tombstone persists (this is the load-from-server path).
  7. Visit `/repository` — the deleted report should no longer appear (RepoItem was removed).
  8. Generate a second new report and **do not save it**. Hand-tune `created_at` to 8 days ago.
  9. Manually invoke the sweep (`uv run python -c "from openlia_server.scheduler.executors.maintenance import run_maintenance_once; from openlia_server.db.session import session_factory; with session_factory() as s: print(run_maintenance_once(s)); s.commit()"`).
  10. Verify the report is tombstoned (chat artifact card shows tombstone; EU/MB listings — if applicable — no longer show it; PDF/DOCX export returns 410).
- [ ] Capture screenshots of each tombstone surface for the PR description.

### Phase 13 — Docs + ship

- [ ] Add a CHANGELOG entry (or update `planning/dev-backlog`'s release notes file) describing the new behavior: "Unsaved reports are now automatically deleted 7 days after generation. Save reports to the Repository to keep them indefinitely. Configurable via `OPENLIA_UNSAVED_REPORT_RETENTION_DAYS`."
- [ ] Run the full test suite: `uv run pytest && cd frontend && npm test`.
- [ ] Run `uv run ruff check .` and `uv run ruff format --check .`.
- [ ] Open the PR. Title: `feat(reports): 7-day auto-expiry for unsaved reports, manual delete after`. Description: bullet the design rules + link this plan.

---

## Open Questions / Defer to PR Review

1. **Server-side age gate on `DELETE /reports/{id}`?** Currently the route trusts the frontend's age check. A user calling the API directly could "delete" (tombstone) a <7d-old saved report. Acceptable — they own it and the tombstone is idempotent. If we want defense in depth, add `if (now - row.created_at) < retention: raise 409`. Punted to PR review.
2. **Tombstone copy strings.** Final wording is bikeshed-able in the PR.
3. **Should the sweep also tombstone reports whose user was deleted but whose `RepoItem`s somehow survived?** Impossible given current FK cascades; not handled.

---

## Rollback

- The migration is forward-additive (one nullable column + one index). Downgrade drops both.
- The shared service is new code; removing it requires reverting the route + sweep edits.
- Frontend changes are additive (new dialog + age-aware buttons). Reverting the four card edits restores prior behavior.
- No data loss on rollback as long as the migration's downgrade runs before code revert — though tombstoned reports stay body-empty after downgrade (the `expired_at` column is gone but the blank `content_markdown` / `content_structured` persist). This is unrecoverable; tombstoning is destructive. Note in PR description.
