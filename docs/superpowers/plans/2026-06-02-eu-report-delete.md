# Earnings Update — Delete Report Cards + Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users delete Earnings Update reports from the feed cards (`EuReportRow`, `EuBigCard`) and from the open-report file viewer, behind a confirm dialog (hard delete).

**Architecture:** Frontend-only. The backend `DELETE /runs/{id}` (`deleteRun`), the page's `removeReport()` (delete + refresh), and the `ConfirmDialog` primitive already exist. We add hover-revealed trash affordances on the cards (page owns a confirm dialog), and a generic optional `onDelete` on the viewer target so the file viewer shows a delete action only when the opener supplies one (EU does).

**Tech Stack:** React / TypeScript / Tailwind / Vitest / react-i18next.

**Spec:** `docs/superpowers/specs/2026-06-02-eu-report-delete-design.md`

**Conventions verified:**
- Frontend tests: `npx vitest run <path>` from `frontend/`. Type-check: `cd frontend && npm run lint` (alias for `tsc --noEmit`).
- Frontend tests initialize the real English i18n bundle (`src/setupTests.ts`), so `t()` returns English — EXCEPT `viewer/__tests__/ViewerHeader.test.tsx`, which mocks `react-i18next` so `t(k) => k` (assert on the raw key there).
- `ConfirmDialog` props: `{ open, title, description?, confirmLabel?, cancelLabel?, destructive?, onConfirm, onCancel }` (from `components/primitives/ConfirmDialog`).
- Existing reusable keys: `earnings.cabinet.remove_title` = "Remove report?", `earnings.cabinet.remove_description` = "This action cannot be undone.", `earnings.cabinet.remove_confirm` = "Remove".
- `deleteRun(id)` is exported from `api/earnings-update.ts`; `EarningsUpdate.tsx` already has `removeReport(id)` (= `deleteRun` + `refreshRuns`) and a `findRun(runs, id)` helper, and a `live` state with `setLive`.

> **Spec divergence note:** The spec said the card trash could reuse `earnings.report_row.remove_aria`. That value is the bare word "Remove", which collides with the confirm button label in tests and reads poorly. This plan instead adds a dedicated `earnings.feed.remove_aria` = "Remove report". The spec's i18n section is updated to match.

---

### Task 1: i18n keys (both locales)

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Add the feed card aria key (English)**

In `frontend/src/i18n/locales/en.json`, inside the `earnings.feed` object (anywhere among its scalar keys, e.g. after `"generating"`), add:

```json
      "remove_aria": "Remove report",
```

- [ ] **Step 2: Add the viewer delete keys (English)**

In the same file, inside the existing `chat` object, alongside the other `viewer_*` keys (e.g. after `"viewer_tab_raw"`), add:

```json
      "viewer_delete_title": "Delete report?",
      "viewer_delete_description": "This permanently deletes the report. This action cannot be undone.",
      "viewer_delete_confirm": "Delete",
      "viewer_delete_aria": "Delete report",
```

- [ ] **Step 3: Add the matching keys (Traditional Chinese)**

In `frontend/src/i18n/locales/zh-TW.json`, inside `earnings.feed` add:

```json
      "remove_aria": "移除報告",
```

And inside `chat` (alongside the `viewer_*` keys) add:

```json
      "viewer_delete_title": "刪除報告？",
      "viewer_delete_description": "此操作將永久刪除報告，且無法復原。",
      "viewer_delete_confirm": "刪除",
      "viewer_delete_aria": "刪除報告",
```

(Match the surrounding indentation in each file; mind JSON commas — every added line needs a trailing comma unless it is the last key in its object.)

- [ ] **Step 4: Validate both files parse and the keys resolve**

Run:
```bash
cd frontend && node -e "const e=require('./src/i18n/locales/en.json'),z=require('./src/i18n/locales/zh-TW.json'); for(const o of [e,z]){ if(!o.earnings.feed.remove_aria) throw new Error('feed.remove_aria'); for(const k of ['viewer_delete_title','viewer_delete_description','viewer_delete_confirm','viewer_delete_aria']) if(!o.chat[k]) throw new Error(k);} console.log('keys ok');"
```
Expected: prints `keys ok`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(eu): i18n for report delete (feed aria + viewer delete dialog)"
```

---

### Task 2: `EuReportRow` delete affordance

**Files:**
- Modify: `frontend/src/components/earnings-update/feed/EuReportRow.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/EuReportRow.test.tsx`

- [ ] **Step 1: Add the failing tests**

In `frontend/src/components/earnings-update/__tests__/EuReportRow.test.tsx`, update the import line and append two tests inside the `describe("EuReportRow", ...)` block.

Change the first import line to add `fireEvent` and `vi`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
```

Append these tests (before the closing `});` of the describe block):

```tsx
  it("renders a delete control that calls onRemove without opening the report", () => {
    const onOpen = vi.fn();
    const onRemove = vi.fn();
    render(
      <EuReportRow report={makeReport(null)} onOpen={onOpen} onRemove={onRemove} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /remove report/i }));
    expect(onRemove).toHaveBeenCalledWith("r1");
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("renders no delete control when onRemove is absent", () => {
    render(<EuReportRow report={makeReport(null)} onOpen={() => {}} />);
    expect(
      screen.queryByRole("button", { name: /remove report/i }),
    ).toBeNull();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuReportRow.test.tsx`
Expected: the two new tests FAIL (no "Remove report" button found).

- [ ] **Step 3: Implement the affordance**

In `frontend/src/components/earnings-update/feed/EuReportRow.tsx`:

Update imports:
```tsx
import { ChevronRight, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { RunSummary } from "../../../api/earnings-update";

import { tickerOf } from "./feedHelpers";
import { MetricChip, RatingPill } from "./highlightBits";
```

Update `Props`:
```tsx
interface Props {
  report: RunSummary;
  onOpen: (id: string) => void;
  onRemove?: (id: string) => void;
}
```

Update the component signature and add the translation hook:
```tsx
export function EuReportRow({ report, onOpen, onRemove }: Props) {
  const { t } = useTranslation();
  const ticker = tickerOf(report) || "—";
```

Wrap the existing `<button>...</button>` (the whole row, unchanged) in a `relative group` div, and add the trash button as a SIBLING of the row button (NOT nested — nesting a button in a button is invalid HTML). The returned JSX becomes:

```tsx
  return (
    <div className="relative group">
      <button
        type="button"
        onClick={() => onOpen(report.report_id)}
        data-testid="eu-report-row"
        className="group text-left grid grid-cols-[64px_1fr_auto_30px] gap-4 items-center px-4 py-3.5 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px] hover:border-[--color-feedback-success] hover:-translate-y-0.5 transition-all duration-[--duration-normal] w-full"
      >
        <div className="font-mono text-[13px] font-semibold text-[--color-text-primary] tracking-wide">
          {ticker}
          <span className="block font-mono text-[9.5px] text-[--color-text-tertiary] mt-0.5 tracking-[0.06em] font-medium">
            {stamp}
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-[14.5px] font-medium text-[--color-text-primary] m-0 leading-tight line-clamp-2">
            {report.subject}
          </p>
          {report.highlights?.subtitle ? (
            <p
              data-testid="eu-row-subtitle"
              className="text-[12.5px] text-[--color-text-secondary] m-0 mt-0.5 leading-snug line-clamp-1"
            >
              {report.highlights.subtitle}
            </p>
          ) : null}
        </div>
        {report.highlights && (report.highlights.metrics.length > 0 || report.highlights.rating) ? (
          <div className="hidden sm:flex items-center gap-2 justify-end">
            {report.highlights.metrics.slice(0, 2).map((metric, i) => (
              <MetricChip key={`${metric.label}-${i}`} metric={metric} />
            ))}
            {report.highlights.rating ? <RatingPill rating={report.highlights.rating} /> : null}
          </div>
        ) : (
          <div />
        )}
        <ChevronRight
          size={16}
          className="text-[--color-text-tertiary] group-hover:text-[--color-feedback-success] group-hover:translate-x-[3px] transition-all duration-[--duration-normal]"
        />
      </button>
      {onRemove ? (
        <button
          type="button"
          onClick={() => onRemove(report.report_id)}
          aria-label={t("earnings.feed.remove_aria")}
          className="absolute top-2 right-2 z-10 inline-flex h-6 w-6 items-center justify-center rounded-md bg-[--color-bg-elevated] text-[--color-text-tertiary] opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover] transition-[opacity,color] duration-[--duration-normal]"
        >
          <Trash2 size={13} />
        </button>
      ) : null}
    </div>
  );
}
```

(The `stamp`/`sameDay` computation above the `return` is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuReportRow.test.tsx`
Expected: PASS (all tests, including the existing subtitle/chips/degradation cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/feed/EuReportRow.tsx frontend/src/components/earnings-update/__tests__/EuReportRow.test.tsx
git commit -m "feat(eu): hover-revealed delete control on EuReportRow"
```

---

### Task 3: `EuBigCard` delete affordance

**Files:**
- Modify: `frontend/src/components/earnings-update/feed/EuBigCard.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/EuBigCard.test.tsx`

- [ ] **Step 1: Add the failing tests**

In `frontend/src/components/earnings-update/__tests__/EuBigCard.test.tsx`, ensure the import line includes `fireEvent` and `vi`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
```

Append these tests inside the `describe("EuBigCard", ...)` block (before its closing `});`):

```tsx
  it("renders a delete control that calls onRemove on a completed card", () => {
    const onRemove = vi.fn();
    render(
      <EuBigCard
        ticker="AAPL"
        title="Apple Inc. — Earnings Update"
        status="complete"
        reportId="r1"
        onRemove={onRemove}
        onOpen={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /remove report/i }));
    expect(onRemove).toHaveBeenCalledWith("r1");
  });

  it("renders no delete control when streaming or when onRemove is absent", () => {
    const { rerender } = render(
      <EuBigCard
        ticker="AAPL"
        title="t"
        status="streaming"
        reportId="r1"
        onRemove={() => {}}
        onOpen={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: /remove report/i })).toBeNull();
    rerender(
      <EuBigCard
        ticker="AAPL"
        title="t"
        status="complete"
        reportId="r1"
        onOpen={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: /remove report/i })).toBeNull();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuBigCard.test.tsx`
Expected: the two new tests FAIL.

- [ ] **Step 3: Implement the affordance**

In `frontend/src/components/earnings-update/feed/EuBigCard.tsx`:

Update the lucide import:
```tsx
import { FileText, Trash2 } from "lucide-react";
```

Add `onRemove` to `Props` (after `onOpen`):
```tsx
  onOpen?: (id: string) => void;
  onRemove?: (id: string) => void;
}
```

Add `onRemove` to the destructured params (after `onOpen`):
```tsx
  onOpen,
  onRemove,
}: Props) {
```

Inside the `<article>`, immediately after the accent rail span (`<span className="absolute left-0 top-0 bottom-0 w-[3px] bg-[--color-accent-primary]" />`), add the trash button (the `<article>` is already `relative`):

```tsx
      {!live && reportId && onRemove ? (
        <button
          type="button"
          onClick={() => onRemove(reportId)}
          aria-label={t("earnings.feed.remove_aria")}
          className="absolute top-3 right-3 z-10 inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover] transition-colors duration-[--duration-normal]"
        >
          <Trash2 size={14} />
        </button>
      ) : null}
```

(`live` is the existing `const live = status === "streaming";`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuBigCard.test.tsx`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/feed/EuBigCard.tsx frontend/src/components/earnings-update/__tests__/EuBigCard.test.tsx
git commit -m "feat(eu): delete control on completed EuBigCard"
```

---

### Task 4: Page confirm + wiring (`EarningsUpdate.tsx`)

**Files:**
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx`
- Test: `frontend/src/pages/departments/EarningsUpdate.test.tsx`

- [ ] **Step 1: Add the failing page test**

In `frontend/src/pages/departments/EarningsUpdate.test.tsx`, append this test inside the `describe("EarningsUpdatePage (v2)", ...)` block (before its closing `});`). The existing file already imports `fireEvent`, `waitFor`, `vi`, `api`, and has `makeRun`/`renderPage`:

```tsx
  it("deletes a feed report after confirming", async () => {
    vi.spyOn(api, "fetchRuns").mockResolvedValue([
      makeRun({ report_id: "rDel", subject: "Apple delete me" }),
    ]);
    const del = vi.spyOn(api, "deleteRun").mockResolvedValue(undefined);
    renderPage();
    // The single recent run renders as the hero EuBigCard; click its trash.
    fireEvent.click(
      await screen.findByRole("button", { name: /remove report/i }),
    );
    // Confirm dialog: the confirm button label is exactly "Remove".
    fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("rDel"));
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/departments/EarningsUpdate.test.tsx`
Expected: the new test FAILS (no "Remove report" button — cards have no delete wired yet).

- [ ] **Step 3: Wire the confirm dialog + onRemove**

In `frontend/src/pages/departments/EarningsUpdate.tsx`:

Add the `ConfirmDialog` import (next to other component imports):
```tsx
import { ConfirmDialog } from "../../components/primitives/ConfirmDialog";
```

Add the pending-removal state (next to the other `useState` calls, e.g. after `const [live, setLive] = useState<LiveCard | null>(null);`):
```tsx
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null);
```

Pass `onRemove` to all four card render sites:

- The completed-live `EuBigCard` (inside the `{live ? ...}` block, `stream.status === "completed"` branch): add `onRemove={(id) => setPendingRemoval(id)}`.
- The `heroToday` `EuBigCard`: add `onRemove={(id) => setPendingRemoval(id)}` (alongside the existing `highlights={heroToday.highlights ?? null}`).
- The `restToday.map((r) => <EuReportRow ... />)`: add `onRemove={(id) => setPendingRemoval(id)}`.
- The `groups.earlierThisWeek.map((r) => <EuReportRow ... />)`: add `onRemove={(id) => setPendingRemoval(id)}`.

(Each `EuReportRow` call becomes:)
```tsx
                            <EuReportRow
                              key={r.report_id}
                              report={r}
                              onOpen={openReport}
                              onRemove={(id) => setPendingRemoval(id)}
                            />
```

Render the confirm dialog just before the closing `</div>` of the page root — placing it alongside the other modals (`CoverageDrawer`, `OnDemandReportModal`, etc.) at the bottom of the returned JSX:
```tsx
      <ConfirmDialog
        open={pendingRemoval !== null}
        title={t("earnings.cabinet.remove_title")}
        description={t("earnings.cabinet.remove_description")}
        confirmLabel={t("earnings.cabinet.remove_confirm")}
        destructive
        onCancel={() => setPendingRemoval(null)}
        onConfirm={() => {
          const id = pendingRemoval;
          setPendingRemoval(null);
          if (!id) return;
          if (id === live?.reportId) setLive(null);
          void removeReport(id);
        }}
      />
```

- [ ] **Step 4: Run the page tests to verify pass + no regression**

Run: `cd frontend && npx vitest run src/pages/departments/EarningsUpdate.test.tsx src/pages/departments/EarningsUpdate.live.test.tsx`
Expected: PASS (new delete test + all existing page tests + live-lifecycle tests).

- [ ] **Step 5: Type-check**

Run: `cd frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/departments/EarningsUpdate.tsx frontend/src/pages/departments/EarningsUpdate.test.tsx
git commit -m "feat(eu): confirm-dialog delete wiring for feed cards"
```

---

### Task 5: Open-report viewer delete

**Files:**
- Modify: `frontend/src/components/viewer/FileViewerContext.tsx`
- Modify: `frontend/src/components/viewer/ViewerHeader.tsx`
- Modify: `frontend/src/components/viewer/FileViewer.tsx`
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx` (pass `onDelete` in `openReport`)
- Test: `frontend/src/components/viewer/__tests__/ViewerHeader.test.tsx`
- Test: `frontend/src/components/viewer/__tests__/FileViewer.test.tsx`

- [ ] **Step 1: Add the failing ViewerHeader tests**

In `frontend/src/components/viewer/__tests__/ViewerHeader.test.tsx`, add `fireEvent` to the testing-library import:
```tsx
import { fireEvent, render } from "@testing-library/react";
```
(NOTE: this file mocks `react-i18next` so `t(k) => k`; the delete button's accessible name is the raw key `chat.viewer_delete_aria`.)

Append inside the `describe(...)`:
```tsx
  test("renders a delete button that fires onRequestDelete when provided", () => {
    const onRequestDelete = vi.fn();
    const { getByLabelText } = render(
      <ViewerHeader
        filename="AAPL earnings"
        metadata="EU v2"
        source={{ kind: "eu_v2_report", reportId: "r1" }}
        onRequestDelete={onRequestDelete}
        onClose={() => undefined}
      />,
    );
    fireEvent.click(getByLabelText("chat.viewer_delete_aria"));
    expect(onRequestDelete).toHaveBeenCalledTimes(1);
  });

  test("renders no delete button when onRequestDelete is absent", () => {
    const { queryByLabelText } = render(
      <ViewerHeader
        filename="AAPL earnings"
        metadata="EU v2"
        source={{ kind: "eu_v2_report", reportId: "r1" }}
        onClose={() => undefined}
      />,
    );
    expect(queryByLabelText("chat.viewer_delete_aria")).toBeNull();
  });
```

- [ ] **Step 2: Add the failing FileViewer tests**

In `frontend/src/components/viewer/__tests__/FileViewer.test.tsx`, add a deletable trigger component and two tests. After the existing `Trigger` function, add:

```tsx
function DeletableTrigger({ onDelete }: { onDelete: () => void }) {
  const { open } = useFileViewer();
  return (
    <button
      onClick={() =>
        open({
          filename: "q.pdf",
          kind: "pdf",
          metadata: "PDF · 12 pages",
          source: { kind: "report", reportId: "5" },
          onDelete,
        })
      }
    >
      open-del
    </button>
  );
}
```

Append inside `describe("FileViewer", ...)`:
```tsx
  it("shows a delete action for a deletable target; confirming calls onDelete then closes", async () => {
    const onDelete = vi.fn();
    const { container } = render(
      <FileViewerProvider>
        <DeletableTrigger onDelete={onDelete} />
        <FileViewer />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByText("open-del"));
    fireEvent.click(screen.getByRole("button", { name: /delete report/i }));
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    await waitFor(() => expect(onDelete).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(container.querySelector('[role="complementary"]')).toBeNull(),
    );
  });

  it("shows no delete action when the target has no onDelete", () => {
    render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByText("open"));
    expect(
      screen.queryByRole("button", { name: /delete report/i }),
    ).toBeNull();
  });
```

- [ ] **Step 3: Run both viewer test files to verify the new tests fail**

Run: `cd frontend && npx vitest run src/components/viewer/__tests__/ViewerHeader.test.tsx src/components/viewer/__tests__/FileViewer.test.tsx`
Expected: the new tests FAIL (no delete button / `onDelete`/`onRequestDelete` not supported).

- [ ] **Step 4: Add `onDelete` to the viewer target type**

In `frontend/src/components/viewer/FileViewerContext.tsx`, add a field to the `FileViewerTarget` interface (after the existing fields, e.g. after the `source` / `initialSaved` fields — place it before the closing brace of the interface):

```ts
  /** When provided, the viewer shows a delete action that calls this then closes. */
  onDelete?: () => void | Promise<void>;
```

- [ ] **Step 5: Add the delete button to `ViewerHeader`**

In `frontend/src/components/viewer/ViewerHeader.tsx`:

Add `Trash2` to the lucide import:
```tsx
import { ExternalLink, Trash2, X } from "lucide-react";
```

Add `onRequestDelete` to `Props` (after `onClose`):
```tsx
  onClose: () => void;
  onRequestDelete?: () => void;
  closeButtonRef?: Ref<HTMLButtonElement>;
```

Add it to the destructured params (after `onClose`):
```tsx
  onClose,
  onRequestDelete,
  closeButtonRef,
}: Props): JSX.Element {
```

In the action-button row, immediately BEFORE the close `<button ref={closeButtonRef} ...>`, add:
```tsx
        {onRequestDelete ? (
          <button
            type="button"
            aria-label={t("chat.viewer_delete_aria")}
            onClick={onRequestDelete}
            className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors duration-normal ease-out hover:bg-surface-hover hover:text-feedback-error"
          >
            <Trash2 size={14} strokeWidth={1.5} />
          </button>
        ) : null}
```

- [ ] **Step 6: Wire the confirm + delete in `FileViewer`**

In `frontend/src/components/viewer/FileViewer.tsx`:

Add the `ConfirmDialog` import:
```tsx
import { ConfirmDialog } from "../primitives/ConfirmDialog";
```

Add confirm state (next to the other `useState` calls):
```tsx
  const [confirmDelete, setConfirmDelete] = useState(false);
```

Reset it when the open target changes — extend the existing effect that resets the tab:
```tsx
  useEffect(() => {
    setTab("preview");
    setConfirmDelete(false);
  }, [current?.filename]);
```

Pass `onRequestDelete` to `ViewerHeader` (add the prop to the existing `<ViewerHeader ... />`):
```tsx
            onRequestDelete={
              current.onDelete ? () => setConfirmDelete(true) : undefined
            }
            onClose={close}
            closeButtonRef={closeButtonRef}
```

Render the confirm dialog inside the `motion.aside`, immediately before its closing `</motion.aside>` tag (after the scroll-container `</div>`):
```tsx
          <ConfirmDialog
            open={confirmDelete}
            title={t("chat.viewer_delete_title")}
            description={t("chat.viewer_delete_description")}
            confirmLabel={t("chat.viewer_delete_confirm")}
            destructive
            onCancel={() => setConfirmDelete(false)}
            onConfirm={() => {
              setConfirmDelete(false);
              void Promise.resolve(current?.onDelete?.()).then(() => close());
            }}
          />
```

- [ ] **Step 7: Pass `onDelete` from the EU page's `openReport`**

In `frontend/src/pages/departments/EarningsUpdate.tsx`, in the `openReport` callback, add `onDelete` to the `fv.open({...})` target object:
```tsx
      fv.open({
        filename: match?.subject ?? "Earnings Update",
        kind: "report",
        metadata: match ? `EU v2 · ${match.ticker}` : "Earnings Update",
        source: { kind: "eu_v2_report", reportId },
        onDelete: () => removeReport(reportId),
      });
```
(`removeReport` is already defined in this component and is stable via `useCallback`; if `openReport`'s `useCallback` dependency array exists, add `removeReport` to it.)

- [ ] **Step 8: Run the viewer tests + type-check**

Run: `cd frontend && npx vitest run src/components/viewer/__tests__/ViewerHeader.test.tsx src/components/viewer/__tests__/FileViewer.test.tsx`
Expected: PASS (new + existing viewer tests).

Run: `cd frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/viewer/FileViewerContext.tsx frontend/src/components/viewer/ViewerHeader.tsx frontend/src/components/viewer/FileViewer.tsx frontend/src/pages/departments/EarningsUpdate.tsx frontend/src/components/viewer/__tests__/ViewerHeader.test.tsx frontend/src/components/viewer/__tests__/FileViewer.test.tsx
git commit -m "feat(eu): delete report from the open-report viewer via optional onDelete"
```

---

### Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Full EU + viewer frontend test set**

Run: `cd frontend && npx vitest run src/components/earnings-update src/components/viewer src/pages/departments/EarningsUpdate.test.tsx src/pages/departments/EarningsUpdate.live.test.tsx`
Expected: PASS (all suites).

- [ ] **Step 2: Frontend type-check**

Run: `cd frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 3: Manual smoke (recommended)**

Backend (`uv run openlia serve`, :8080) + Vite (`npm run dev`, :5173). On `/earnings-update`: hover a feed row and the hero card → trash appears → click → confirm → report disappears from the feed. Open a report in the viewer → click the trash in the header → confirm → viewer closes and the report is gone from the feed. Confirm a non-EU file open (e.g. a chat attachment) shows NO delete button.

---

## Notes for the implementer

- **Graceful, additive:** `onRemove` / `onDelete` are optional everywhere. Existing call sites that don't pass them must keep working unchanged (no delete affordance, no behavior change) — the "absent" tests guard this.
- **No nested buttons:** the `EuReportRow` trash MUST be a sibling of the row `<button>`, never a child.
- **Hard delete:** confirm-then-`deleteRun`, matching the cabinet. No undo, no soft delete.
- **Out of scope:** Equity Research / other departments, bulk delete, cabinet view (already has delete).
