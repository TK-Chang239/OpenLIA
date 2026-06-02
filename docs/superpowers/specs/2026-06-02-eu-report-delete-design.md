# Earnings Update — Delete Report Cards + Reports

Date: 2026-06-02
Status: Approved (design)
Scope: Earnings Update v2 frontend only. Branch `feat/eu-report-delete` (stacked on
`feat/eu-generating-cards` / PR #237, which it extends).

## Goal

Let the user delete Earnings Update reports directly from:
1. **Feed cards** — the `EuReportRow` list rows and the `EuBigCard` hero/today card.
2. **The open-report viewer** — a delete action while reading a report in the file viewer.

The cabinet ("View all reports") already supports delete; this fills the two surfaces
that don't. Deletion is a **hard delete** behind a **confirm dialog** (matching the
cabinet's existing UX).

## Background (verified)

This is **frontend-only** — every backend piece already exists:
- `DELETE /api/departments/earnings-update/v2/runs/{report_id}` (`delete_run`, hard
  delete via `db.delete(row)`) and its client `deleteRun(id)`.
- `EarningsUpdate.tsx` already has `removeReport(id)` = `await deleteRun(id); await
  refreshRuns();`, currently passed only to `EUCabinetView`.
- The reusable `ConfirmDialog` primitive (`components/primitives/ConfirmDialog`) with
  `destructive` styling, used by `EUCabinetView`.
- i18n keys `earnings.cabinet.remove_title` ("Remove report?"),
  `remove_description` ("This action cannot be undone."), `remove_confirm` ("Remove"),
  and `earnings.report_row.remove_aria` already exist in en + zh-TW.

No migration, no new endpoint, no backend change.

## A. Feed card delete

Both feed-card components gain an optional `onRemove?: (reportId: string) => void`.
When absent, nothing renders (graceful, and keeps existing call sites valid).

### `EuReportRow`
Its root element is a `<button>` (the whole row opens the report), so a nested
`<button>` is invalid HTML. Wrap the row in a `<div className="relative group">`
and render the trash control as an **absolutely-positioned sibling** of the row
button (not a child), top-right, revealed on hover/focus:
`opacity-0 group-hover:opacity-100 focus-within:opacity-100` (and always visible on
touch is acceptable — keep it simple with hover/focus).

The trash button:
- `lucide-react` `Trash2`, ~14px, `text-[--color-text-tertiary] hover:text-[--color-feedback-error]`.
- `aria-label={t("earnings.report_row.remove_aria")}`.
- `onClick`: `e.stopPropagation(); e.preventDefault(); onRemove(report.report_id);`
  so it never triggers the row's open handler.
- Rendered only when `onRemove` is provided.

### `EuBigCard`
An `<article>` root — add a hover-revealed trash button positioned top-right
(`absolute top-3 right-3`, same icon/colors), shown only when
`status === "complete" && reportId && onRemove`. The generating state is handled by
`EuGeneratingCard` (Cancel), so no delete there. `onClick` calls `onRemove(reportId)`.

## B. Page confirm + wiring (`EarningsUpdate.tsx`)

- Add state `const [pendingRemoval, setPendingRemoval] = useState<string | null>(null)`.
- Pass `onRemove={(id) => setPendingRemoval(id)}` to **every** `EuReportRow`
  (restToday, earlierThisWeek) and **every** `EuBigCard` (the completed-live card and
  the `heroToday` card).
- Render a `ConfirmDialog` at the page level, reusing the cabinet keys:
  `open={pendingRemoval !== null}`, `title=earnings.cabinet.remove_title`,
  `description=earnings.cabinet.remove_description`,
  `confirmLabel=earnings.cabinet.remove_confirm`, `destructive`.
- `onConfirm`: capture `const id = pendingRemoval; setPendingRemoval(null);` then
  `if (id) { if (id === live?.reportId) setLive(null); void removeReport(id); }`.
  Clearing `live` ensures a just-finished live card doesn't linger pointing at a
  deleted report.

## C. Open-report viewer delete (generic, decoupled)

Keep the shared viewer generic: it shows a delete affordance **only when the opener
supplies a delete handler**.

### `FileViewerContext`
Add an optional field to `FileViewerTarget`:
```ts
/** When provided, the viewer shows a delete action that calls this then closes. */
onDelete?: () => void | Promise<void>;
```

### `ViewerHeader`
Add an optional prop `onRequestDelete?: () => void`. When provided, render a Trash
button (`lucide-react` `Trash2`) in the existing action-button row (before the close
button), styled like the other header buttons,
`aria-label={t("chat.viewer_delete_aria")}`, `onClick={onRequestDelete}`.

### `FileViewer`
- When `current?.onDelete` is set, manage local state
  `const [confirmDelete, setConfirmDelete] = useState(false)` and pass
  `onRequestDelete={() => setConfirmDelete(true)}` to `ViewerHeader`.
- Render a `ConfirmDialog` (new generic keys `chat.viewer_delete_title` /
  `chat.viewer_delete_description` / `chat.viewer_delete_confirm`, `destructive`). On confirm:
  `setConfirmDelete(false); await current.onDelete?.(); close();`. On cancel:
  `setConfirmDelete(false)`.
- Reset `confirmDelete` to false when the open target changes (alongside the existing
  `setTab("preview")` effect keyed on `current?.filename`).

### EU page `openReport`
Pass the handler when opening an EU report:
```ts
fv.open({
  filename: ..., kind: "report", metadata: ...,
  source: { kind: "eu_v2_report", reportId },
  onDelete: () => removeReport(reportId),
});
```
`removeReport` refreshes the feed; the viewer closes itself after `onDelete` resolves.
Other departments don't pass `onDelete`, so no delete button and no behavior change.

## i18n

- **Reuse** (no new keys): `earnings.cabinet.remove_title/description/confirm` (feed
  page confirm), `earnings.report_row.remove_aria` (card trash aria).
- **New** in en + zh-TW, added to the existing `chat` namespace alongside the other
  `chat.viewer_*` keys (there is no top-level `viewer` namespace; viewer strings live
  under `chat`):
  - `chat.viewer_delete_title` — en "Delete report?" / zh-TW "刪除報告？"
  - `chat.viewer_delete_description` — en "This permanently deletes the report. This action cannot be undone." / zh-TW "此操作將永久刪除報告，且無法復原。"
  - `chat.viewer_delete_confirm` — en "Delete" / zh-TW "刪除"
  - `chat.viewer_delete_aria` — en "Delete report" / zh-TW "刪除報告"

## Testing

- **`EuReportRow`**: trash calls `onRemove` with `report_id`; clicking trash does NOT
  call `onOpen` (stopPropagation); no trash rendered when `onRemove` absent.
- **`EuBigCard`**: trash renders + calls `onRemove(reportId)` when
  `status="complete"` + `reportId` + `onRemove`; not rendered when `onRemove` absent;
  not rendered for `status="streaming"`.
- **`EarningsUpdate` (page)**: clicking a feed row's trash opens the confirm; confirming
  calls `deleteRun` and refreshes; deleting the live-completed card clears it. (Use the
  existing page test harness / the mutable-stream pattern from `EarningsUpdate.live.test.tsx`
  where a live card is needed.)
- **`ViewerHeader`**: renders the delete button and fires `onRequestDelete` when the prop
  is set; no button when it's absent.
- **`FileViewer`**: a target with `onDelete` shows the delete button; confirming calls
  `onDelete` then `close`; canceling calls neither.
- Existing viewer/EU tests stay green (notably: targets WITHOUT `onDelete` show no delete
  button — chat/attachment/other-department opens are unchanged).

## Files

**Edit**
- `frontend/src/components/earnings-update/feed/EuReportRow.tsx`
- `frontend/src/components/earnings-update/feed/EuBigCard.tsx`
- `frontend/src/pages/departments/EarningsUpdate.tsx`
- `frontend/src/components/viewer/FileViewerContext.tsx`
- `frontend/src/components/viewer/FileViewer.tsx`
- `frontend/src/components/viewer/ViewerHeader.tsx`
- `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/zh-TW.json`

**Tests**
- Extend `__tests__/EuReportRow.test.tsx`, `__tests__/EuBigCard.test.tsx`,
  `viewer/__tests__/ViewerHeader.test.tsx`, `viewer/__tests__/FileViewer.test.tsx`.
- Add a page-level delete test (extend `EarningsUpdate.test.tsx` or a focused file).

## Out of scope

- Equity Research v3 / other departments' cards (this pass is Earnings Update only;
  the generic `onDelete` hook makes wiring them later trivial, but we don't do it now).
- Soft delete / undo (hard delete + confirm, matching the cabinet).
- Bulk/multi-select delete.
- Cabinet view (`EUCabinetView`) — already has delete, unchanged.
