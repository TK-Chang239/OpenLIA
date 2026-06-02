# Morning Briefing Save-to-Repo Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Morning Briefing (MB) save-to-repo button and make saved MB briefings open/delete/remove correctly on the Repository page, mirroring the existing Earnings Update (`eu`) engine path.

**Architecture:** Frontend-only. The backend (`/api/repo/mb-runs` save/unsave/list, the repo fan-out emitting `engine="mb_v2"`, and `DELETE /runs/{id}`) is already complete. We add an `mb` saved-id bucket to `SavedReportsContext`, an `"mb"` engine discriminant to `SaveToRepoButton`, repo API helpers, the viewer plumbing so the MB viewer shows the button, and `engine === "mb_v2"` branches on the Repository page. Download and delete already work in the MB viewer — out of scope beyond regression.

**Tech Stack:** React + TypeScript + Vite, Vitest + Testing Library. Spec: `docs/superpowers/specs/2026-06-02-morning-briefing-save-download-delete-wiring-design.md`.

**Conventions:**
- Run a single frontend test file: `cd frontend && npx vitest run src/<path>`
- Typecheck: `cd frontend && npx tsc --noEmit`
- Repo-delete decision (approved): Repository-page **Delete** hard-deletes via `deleteMbRun`; **Remove** unsaves only.

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `frontend/src/api/repo.ts` | Repo HTTP client + `RepoEngine` type | Add `"mb_v2"` to `RepoEngine`; add `saveMbRunToRepo` / `unsaveMbRunFromRepo` / `listSavedMbRuns` |
| `frontend/src/components/repo/SavedReportsContext.tsx` | Global saved-id buckets per engine | Add `mb` bucket + hydration |
| `frontend/src/components/chat/SaveToRepoButton.tsx` | The save/unsave toggle button | Add `"mb"` to `SaveToRepoEngine` + the mb save/unsave branch |
| `frontend/src/components/viewer/ViewerHeader.tsx` | Viewer header affordances | Pass `engine={saveEngine}` (drop the `mb`→`v1` collapse) |
| `frontend/src/components/viewer/FileViewer.tsx` | Derives header props from the open target | Pass `reportId` + `saveEngine="mb"` for `mb_report` |
| `frontend/src/pages/departments/MorningBriefing.tsx` | MB feed page | Drop `hideSaveToRepoButton: true` in `openReport` |
| `frontend/src/pages/Repository.tsx` | Repository grid | Add `engine === "mb_v2"` open/delete/remove/undo branches |

Each task is independently committable and leaves tests green.

---

### Task 1: Repo API — `mb_v2` engine + MB save/unsave/list helpers

**Files:**
- Modify: `frontend/src/api/repo.ts`
- Test: `frontend/src/api/__tests__/repo.test.ts` (create if absent)

- [ ] **Step 1: Add the `mb_v2` engine + MB helpers**

In `frontend/src/api/repo.ts`, change the `RepoEngine` type. Current:

```ts
export type RepoEngine = "v1" | "v3" | "eu_v2";
```

New:

```ts
export type RepoEngine = "v1" | "v3" | "eu_v2" | "mb_v2";
```

Then, immediately after the `listSavedEuRuns` export (the EU block ending
with the `/api/repo/eu-runs` GET), append the MB mirror:

```ts
// Morning Briefing repo mirrors of the EU helpers. Polymorphic pointer
// column ``mb_v2_report_id`` lives in ``repo_items`` alongside the
// v1/v2/v3/eu pointers; the routes keep each engine's surface explicit.

export const saveMbRunToRepo = (reportId: string) =>
  fetchJson<RepoItem>("/api/repo/mb-runs", {
    method: "POST",
    json: { mb_v2_report_id: reportId },
  });

export const unsaveMbRunFromRepo = (reportId: string) =>
  fetchJson<void>(
    `/api/repo/mb-runs?mb_v2_report_id=${encodeURIComponent(reportId)}`,
    { method: "DELETE" },
  );

/** Returns the MB report ids the current user has saved. */
export const listSavedMbRuns = () =>
  fetchJson<{ saved_report_ids: string[] }>("/api/repo/mb-runs");
```

- [ ] **Step 2: Add a focused test**

Create/extend `frontend/src/api/__tests__/repo.test.ts`. If the file does
not exist, create it with this content; if it exists, add the `describe`
block. Mock `fetchJson` is not used here — instead assert the URL/method
shape via a `global.fetch` stub the codebase already uses for `fetchJson`.
Check how a sibling test (e.g. an existing `repo` or `reports` api test)
stubs the network and follow that exact pattern. If no api-level network
stub pattern exists in the repo, SKIP this file-level test (the helpers are
exercised end-to-end by Tasks 3 and 6) and note the skip in the commit
message.

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { saveMbRunToRepo, unsaveMbRunFromRepo, listSavedMbRuns } from "../repo";

describe("MB repo helpers", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("saveMbRunToRepo POSTs the mb_v2_report_id", async () => {
    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ id: "x", created_at: "" }), {
          status: 201,
          headers: { "content-type": "application/json" },
        }),
      );
    await saveMbRunToRepo("mb-1");
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/api/repo/mb-runs");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ mb_v2_report_id: "mb-1" });
  });

  it("unsaveMbRunFromRepo DELETEs with the query param", async () => {
    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));
    await unsaveMbRunFromRepo("mb-1");
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/api/repo/mb-runs?mb_v2_report_id=mb-1");
    expect(init?.method).toBe("DELETE");
  });

  it("listSavedMbRuns GETs the mb-runs surface", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ saved_report_ids: ["mb-1"] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const res = await listSavedMbRuns();
    expect(res.saved_report_ids).toEqual(["mb-1"]);
    expect(String(fetchSpy.mock.calls[0][0])).toContain("/api/repo/mb-runs");
  });
});
```

- [ ] **Step 3: Run the test + typecheck**

Run: `cd frontend && npx vitest run src/api/__tests__/repo.test.ts && npx tsc --noEmit`
Expected: PASS (or, if the api-level test was skipped per Step 2, just `tsc` clean).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/repo.ts frontend/src/api/__tests__/repo.test.ts
git commit -m "feat(report-mb): repo API helpers + mb_v2 engine type"
```

---

### Task 2: SavedReportsContext — MB saved-id bucket

**Files:**
- Modify: `frontend/src/components/repo/SavedReportsContext.tsx`
- Test: `frontend/src/components/repo/__tests__/SavedReportsContext.test.tsx` (create if absent)

- [ ] **Step 1: Add the `mb` bucket**

In `SavedReportsContext.tsx`:

(a) Import `listSavedMbRuns` alongside the existing list imports:

```ts
import {
  listRepoItems,
  listSavedEuRuns,
  listSavedMbRuns,
  listSavedV2Runs,
  listSavedV3Runs,
} from "../../api/repo";
```

(b) Extend `ContextShape` — after the `isEuSaved`/`markEuSaved`/`markEuUnsaved` trio, add:

```ts
  // Morning Briefing report_mb — keyed by report_mb.id. Same isolation
  // rationale as eu/v3.
  isMbSaved: (reportId: string) => boolean;
  markMbSaved: (reportId: string) => void;
  markMbUnsaved: (reportId: string) => void;
```

(c) Add state next to `savedEuIds`:

```ts
  const [savedMbIds, setSavedMbIds] = useState<Set<string>>(() => new Set());
```

(d) In the hydration `useEffect`, after the `listSavedEuRuns()` block, add:

```ts
    void listSavedMbRuns()
      .then((res) => {
        if (cancelled) return;
        setSavedMbIds(new Set(res.saved_report_ids));
      })
      .catch(() => {
        // Endpoint is new — older deployments will 404; that's fine.
      });
```

(e) After the `markEuUnsaved` callback, add the MB callbacks:

```ts
  const isMbSaved = useCallback(
    (reportId: string) => savedMbIds.has(reportId),
    [savedMbIds],
  );

  const markMbSaved = useCallback((reportId: string) => {
    setSavedMbIds((prev) => {
      if (prev.has(reportId)) return prev;
      const next = new Set(prev);
      next.add(reportId);
      return next;
    });
  }, []);

  const markMbUnsaved = useCallback((reportId: string) => {
    setSavedMbIds((prev) => {
      if (!prev.has(reportId)) return prev;
      const next = new Set(prev);
      next.delete(reportId);
      return next;
    });
  }, []);
```

(f) Add `isMbSaved`, `markMbSaved`, `markMbUnsaved` to BOTH the `value`
object and the `useMemo` dependency array (after the `eu` trio in each).

- [ ] **Step 2: Add a hydration test**

Create `frontend/src/components/repo/__tests__/SavedReportsContext.test.tsx`
(if a context test already exists, add the `it` block to it instead):

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import {
  SavedReportsProvider,
  useSavedReportsOptional,
} from "../SavedReportsContext";
import * as repoApi from "../../../api/repo";

vi.mock("../../../api/repo");

function Probe({ id }: { id: string }) {
  const ctx = useSavedReportsOptional();
  return <div data-testid="probe">{ctx?.isMbSaved(id) ? "saved" : "no"}</div>;
}

describe("SavedReportsContext MB bucket", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (repoApi.listRepoItems as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [] });
    (repoApi.listSavedV2Runs as ReturnType<typeof vi.fn>).mockResolvedValue({ saved_run_ids: [] });
    (repoApi.listSavedV3Runs as ReturnType<typeof vi.fn>).mockResolvedValue({ saved_report_ids: [] });
    (repoApi.listSavedEuRuns as ReturnType<typeof vi.fn>).mockResolvedValue({ saved_report_ids: [] });
  });

  it("hydrates isMbSaved from listSavedMbRuns", async () => {
    (repoApi.listSavedMbRuns as ReturnType<typeof vi.fn>).mockResolvedValue({
      saved_report_ids: ["mb-1"],
    });
    render(
      <SavedReportsProvider>
        <Probe id="mb-1" />
      </SavedReportsProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("saved"));
  });
});
```

- [ ] **Step 3: Run the test + typecheck**

Run: `cd frontend && npx vitest run src/components/repo/__tests__/SavedReportsContext.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/repo/SavedReportsContext.tsx frontend/src/components/repo/__tests__/SavedReportsContext.test.tsx
git commit -m "feat(report-mb): saved-reports context mb bucket + hydration"
```

---

### Task 3: SaveToRepoButton — `mb` engine branch

**Files:**
- Modify: `frontend/src/components/chat/SaveToRepoButton.tsx`
- Test: `frontend/src/components/chat/__tests__/SaveToRepoButton.test.tsx`

- [ ] **Step 1: Write the failing test** (add to the existing describe block)

```tsx
  it("routes to the mb save endpoint when engine=mb", async () => {
    (repoApi.saveMbRunToRepo as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "x",
      mb_v2_report_id: "mb-1",
      created_at: "",
    });
    render(
      <SavedReportsProvider>
        <SaveToRepoButton
          reportId="mb-1"
          initialSaved={false}
          variant="viewer-header"
          engine="mb"
        />
      </SavedReportsProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /save to repository/i }));
    await waitFor(() => expect(repoApi.saveMbRunToRepo).toHaveBeenCalledWith("mb-1"));
    expect(repoApi.saveToRepo).not.toHaveBeenCalled();
  });

  it("routes to the mb unsave endpoint when engine=mb and already saved", async () => {
    (repoApi.unsaveMbRunFromRepo as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    render(
      <SavedReportsProvider>
        <SaveToRepoButton
          reportId="mb-1"
          initialSaved={true}
          variant="viewer-header"
          engine="mb"
        />
      </SavedReportsProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /remove from repository/i }));
    await waitFor(() => expect(repoApi.unsaveMbRunFromRepo).toHaveBeenCalledWith("mb-1"));
    expect(repoApi.unsaveFromRepo).not.toHaveBeenCalled();
  });
```

Note: the existing test file imports `SavedReportsProvider` and
`* as repoApi` and calls `vi.mock("../../../api/repo")` — the mocked module
auto-stubs the new `saveMbRunToRepo`/`unsaveMbRunFromRepo`. If other
hydration calls (`listRepoItems`, etc.) are not already defaulted in
`beforeEach`, the provider's best-effort `.catch` swallows the rejection,
so no extra setup is needed.

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/SaveToRepoButton.test.tsx`
Expected: FAIL — `engine="mb"` is not assignable / `saveMbRunToRepo` never called (falls through to v1).

- [ ] **Step 3: Implement the mb branch**

In `SaveToRepoButton.tsx`:

(a) Extend the imports from `../../api/repo` to include
`saveMbRunToRepo` and `unsaveMbRunFromRepo`.

(b) Extend the engine union:

```ts
export type SaveToRepoEngine = "v1" | "v2" | "v3" | "eu" | "mb";
```

(c) Extend `ctxIsSaved` to handle `mb` (insert before the final `eu`
fallthrough chain so the ternary reads cleanly):

```ts
  const ctxIsSaved =
    engine === "v2"
      ? ctx?.isV2Saved(reportId)
      : engine === "v3"
        ? ctx?.isV3Saved(reportId)
        : engine === "eu"
          ? ctx?.isEuSaved(reportId)
          : engine === "mb"
            ? ctx?.isMbSaved(reportId)
            : ctx?.isSaved(reportId);
```

(d) In the `onClick` unsave branch, add `mb` before the final `else`:

```ts
        } else if (engine === "eu") {
          await unsaveEuRunFromRepo(reportId);
          ctx?.markEuUnsaved(reportId);
        } else if (engine === "mb") {
          await unsaveMbRunFromRepo(reportId);
          ctx?.markMbUnsaved(reportId);
        } else {
          await unsaveFromRepo(reportId);
          ctx?.markUnsaved(reportId);
        }
```

(e) In the `onClick` save branch, add `mb` before the final `else`:

```ts
        } else if (engine === "eu") {
          await saveEuRunToRepo(reportId);
          ctx?.markEuSaved(reportId);
        } else if (engine === "mb") {
          await saveMbRunToRepo(reportId);
          ctx?.markMbSaved(reportId);
        } else {
          await saveToRepo(reportId);
          ctx?.markSaved(reportId);
        }
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/SaveToRepoButton.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/SaveToRepoButton.tsx frontend/src/components/chat/__tests__/SaveToRepoButton.test.tsx
git commit -m "feat(report-mb): SaveToRepoButton mb engine branch"
```

---

### Task 4: Viewer plumbing — show the save button for `mb_report`

**Files:**
- Modify: `frontend/src/components/viewer/ViewerHeader.tsx`
- Modify: `frontend/src/components/viewer/FileViewer.tsx`
- Test: `frontend/src/components/viewer/__tests__/ViewerHeader.test.tsx`

- [ ] **Step 1: Write the failing test** (add to the existing describe block)

The existing test mocks `SaveToRepoButton` as `<div data-testid="save" />`,
so a save render is asserted by the presence of `save`. Add:

```tsx
  test("mb_report with reportId + saveEngine=mb renders the Save-to-Repo button", () => {
    render(
      <ViewerHeader
        filename="briefing.pdf"
        metadata="m"
        source={{ kind: "mb_report", reportId: "r1" }}
        reportId="r1"
        saveEngine="mb"
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId("save")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/components/viewer/__tests__/ViewerHeader.test.tsx`
Expected: PASS already? No — `reportId` is set and `hideSaveToRepoButton`
is false, so the button renders even today (it collapses engine to v1).
This test passes immediately. That is acceptable: it locks in that the
button renders for mb. The behavioral change (engine no longer collapses)
is covered by Task 3's endpoint test. Proceed to Step 3 to remove the
collapse.

- [ ] **Step 3: Drop the `mb`→`v1` collapse in ViewerHeader**

In `ViewerHeader.tsx`, the `SaveToRepoButton` currently reads:

```tsx
            engine={saveEngine === "mb" ? "v1" : saveEngine}
```

Replace with:

```tsx
            engine={saveEngine}
```

Also replace the stale multi-line comment above it (the block starting
"The backend exposes /api/repo/mb-runs, but the MB viewer save…") with:

```tsx
            // Selects the repo endpoint + SavedReportsContext bucket
            // (v1/v2/v3/eu/mb). The MB page no longer hides this button.
```

- [ ] **Step 4: Pass reportId + saveEngine for `mb_report` in FileViewer**

In `FileViewer.tsx`, extend the `reportId` ternary (currently ends with
`: undefined`) to add `mb_report` before the `undefined`:

```tsx
            reportId={
              current.source.kind === "report"
                ? current.source.reportId
                : current.source.kind === "v3_report"
                  ? current.source.reportId
                  : current.source.kind === "eu_v2_report"
                    ? current.source.reportId
                    : current.source.kind === "mb_report"
                      ? current.source.reportId
                      : undefined
            }
```

Extend the `saveEngine` ternary to add `mb_report`:

```tsx
            saveEngine={
              current.source.kind === "v3_report"
                ? "v3"
                : current.source.kind === "eu_v2_report"
                  ? "eu"
                  : current.source.kind === "mb_report"
                    ? "mb"
                    : "v1"
            }
```

Update the adjacent comment to mention `mb` (POST /api/repo/mb-runs).

- [ ] **Step 5: Run the tests + typecheck**

Run: `cd frontend && npx vitest run src/components/viewer/__tests__/ViewerHeader.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/viewer/ViewerHeader.tsx frontend/src/components/viewer/FileViewer.tsx frontend/src/components/viewer/__tests__/ViewerHeader.test.tsx
git commit -m "feat(report-mb): viewer shows the save-to-repo button for mb_report"
```

---

### Task 5: MorningBriefing page — stop hiding the save button

**Files:**
- Modify: `frontend/src/pages/departments/MorningBriefing.tsx`
- Test: `frontend/src/pages/departments/MorningBriefing.test.tsx`

- [ ] **Step 1: Write the failing test**

Open `MorningBriefing.test.tsx` and find how it opens a report (it asserts
on `fv.open` / the file viewer). The viewer in these tests is typically a
mock that records the `open()` target. Add an assertion that the opened
target does NOT set `hideSaveToRepoButton` to `true`. Mirror the existing
"openReport" test's setup. Concretely, if the test mocks `useFileViewer`
to capture the target into a spy `openSpy`, add:

```tsx
  it("opens a briefing without hiding the save-to-repo button", async () => {
    // ...trigger opening a completed briefing the same way the existing
    // "opens the viewer" test does...
    const target = openSpy.mock.calls.at(-1)?.[0];
    expect(target?.source).toEqual({ kind: "mb_report", reportId: expect.any(String) });
    expect(target?.hideSaveToRepoButton).not.toBe(true);
  });
```

If the existing suite has no viewer-open capture, extend the existing
open-related test to also assert `hideSaveToRepoButton` is not `true`
rather than adding a new test.

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/pages/departments/MorningBriefing.test.tsx`
Expected: FAIL — current `openReport` sets `hideSaveToRepoButton: true`.

- [ ] **Step 3: Remove the flag**

In `MorningBriefing.tsx`, the `openReport` callback's `fv.open({ ... })`
currently includes:

```tsx
        hideSaveToRepoButton: true,
```

Delete that single line. Leave `onDelete`, `kind`, `metadata`, `source`,
and `filename` unchanged. The save button is now ctx-driven via
`isMbSaved` (the page is already inside `SavedReportsProvider` via
`AppLayout`), matching how EU's page opens its viewer.

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run src/pages/departments/MorningBriefing.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/departments/MorningBriefing.tsx frontend/src/pages/departments/MorningBriefing.test.tsx
git commit -m "feat(report-mb): show save-to-repo button in the MB viewer"
```

---

### Task 6: Repository page — `mb_v2` open / delete / remove / undo

**Files:**
- Modify: `frontend/src/pages/Repository.tsx`
- Test: `frontend/src/pages/__tests__/Repository.test.tsx`

- [ ] **Step 1: Write the failing tests**

In `Repository.test.tsx`:

(a) Add a `deleteMbRun` mock and MB repo mocks. Near the other
`vi.mock` blocks, add:

```tsx
const deleteMbRun = vi.fn();
vi.mock("../../api/morning-briefing", () => ({
  deleteMbRun: (...a: unknown[]) => deleteMbRun(...a),
}));
```

And inside the existing `vi.mock("../../api/repo", ...)` factory, add
`saveMbRunToRepo` and `unsaveMbRunFromRepo` stubs alongside the EU ones:

```tsx
const unsaveMbRunFromRepo = vi.fn();
const saveMbRunToRepo = vi.fn();
// ...inside the factory's returned object:
  unsaveMbRunFromRepo: (...a: unknown[]) => unsaveMbRunFromRepo(...a),
  saveMbRunToRepo: (...a: unknown[]) => saveMbRunToRepo(...a),
```

(b) Add a sample MB row near `SAMPLE_EU_ROW`:

```tsx
const SAMPLE_MB_ROW = {
  ...SAMPLE_EU_ROW,
  id: "repo-mb-1",
  engine: "mb_v2" as const,
  // For mb_v2 rows, report_id holds the report_mb.id.
  report_id: "mb-report-1",
  filename: "briefing.pdf",
};
```

(c) Add three tests mirroring the EU equivalents:

```tsx
  it("opens an mb_v2 row via the mb_report file source", async () => {
    // render with list rows = [SAMPLE_MB_ROW] following the same harness
    // the eu_v2 open test uses; click the row; assert openViewer target:
    expect(openViewer).toHaveBeenCalledWith(
      expect.objectContaining({
        source: { kind: "mb_report", reportId: SAMPLE_MB_ROW.report_id },
        initialSaved: true,
        hideSaveToRepoButton: true,
      }),
    );
  });

  it("removes an mb_v2 row via unsaveMbRunFromRepo, not the v1 unsave", async () => {
    unsaveMbRunFromRepo.mockResolvedValueOnce(undefined);
    // render [SAMPLE_MB_ROW]; trigger Remove + confirm exactly as the
    // eu_v2 remove test does:
    await waitFor(() =>
      expect(unsaveMbRunFromRepo).toHaveBeenCalledWith(SAMPLE_MB_ROW.report_id),
    );
    expect(unsaveFromRepo).not.toHaveBeenCalled();
  });

  it("hard-deletes an mb_v2 row via deleteMbRun", async () => {
    deleteMbRun.mockResolvedValueOnce(undefined);
    // render [SAMPLE_MB_ROW] with a generated_at >= 7 days old so the
    // Delete affordance shows (mirror the "deleteReport for rows >= 7
    // days old" test); trigger Delete + confirm:
    await waitFor(() =>
      expect(deleteMbRun).toHaveBeenCalledWith(SAMPLE_MB_ROW.report_id),
    );
    expect(deleteReport).not.toHaveBeenCalled();
  });
```

Match the exact render/click harness the existing `eu_v2` and
`deleteReport`-age tests use in this file (row injection, confirm-dialog
button names). Do not invent new helpers.

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run src/pages/__tests__/Repository.test.tsx`
Expected: FAIL — `mb_v2` rows fall through to the v1 path (`openViewer`
gets `{kind: "report"}`, Remove calls `unsaveFromRepo`, Delete calls
`deleteReport`).

- [ ] **Step 3: Add the imports**

In `Repository.tsx`, extend the `../api/repo` import to add
`saveMbRunToRepo` and `unsaveMbRunFromRepo`, and add a new import:

```tsx
import { deleteMbRun } from "../api/morning-briefing";
```

- [ ] **Step 4: Add the `mb_v2` open branch**

In `handleOpen`, after the `if (row.engine === "eu_v2") { ... return; }`
block and before the final v1 fallthrough, insert:

```tsx
    if (row.engine === "mb_v2") {
      openViewer({
        filename: row.filename,
        kind: "report",
        metadata,
        source: { kind: "mb_report", reportId: row.report_id },
        initialSaved: true,
        hideSaveToRepoButton: true,
      });
      return;
    }
```

- [ ] **Step 5: Add the `mb_v2` delete + remove + undo branches**

In `confirmDelete`, add before the final `else`:

```tsx
      } else if (row.engine === "mb_v2") {
        await deleteMbRun(row.report_id);
        savedReports?.markMbUnsaved(row.report_id);
```

In `confirmRemove`, add before the final `else`:

```tsx
      } else if (row.engine === "mb_v2") {
        await unsaveMbRunFromRepo(row.report_id);
        savedReports?.markMbUnsaved(row.report_id);
```

In the same `confirmRemove`'s undo `onClick`, add before its final `else`:

```tsx
              } else if (row.engine === "mb_v2") {
                await saveMbRunToRepo(row.report_id);
                savedReports?.markMbSaved(row.report_id);
```

- [ ] **Step 6: Run to verify they pass**

Run: `cd frontend && npx vitest run src/pages/__tests__/Repository.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Repository.tsx frontend/src/pages/__tests__/Repository.test.tsx
git commit -m "feat(report-mb): Repository page open/delete/remove for mb_v2 rows"
```

---

### Task 7: Full regression sweep

**Files:** none (verification only)

- [ ] **Step 1: Frontend typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 2: Targeted frontend suites**

Run: `cd frontend && npx vitest run src/components/chat src/components/viewer src/components/repo src/pages/Repository.test.tsx src/pages/departments/MorningBriefing.test.tsx src/api`
Expected: all PASS.

- [ ] **Step 3: Backend repo regression (guard, no change expected)**

Run: `cd /Users/tkchang/Projects/OpenLIA && uv run pytest packages/server/tests/test_services/test_repo_mb_listing.py packages/server/tests/test_routes/test_repo.py -q`
(If `test_routes/test_repo.py` does not exist, run the directory
`packages/server/tests/test_routes/ -k repo`.)
Expected: PASS — confirms the already-shipped MB repo endpoints + fan-out
still behave.

- [ ] **Step 4: Lint**

Run: `cd /Users/tkchang/Projects/OpenLIA && cd frontend && npm run lint`
Expected: clean (or no new warnings on the touched files).

- [ ] **Step 5: Final commit (if lint auto-fixed anything)**

```bash
git add -A && git commit -m "chore(report-mb): lint + regression sweep" || echo "nothing to commit"
```

---

## Self-Review

**1. Spec coverage:**
- Save button wiring (api/context/button/viewer/MB page) → Tasks 1–5. ✓
- Repository page `mb_v2` open/delete/remove/undo → Task 6. ✓
- Repo-delete = hard-delete decision → Task 6 Step 5 (`deleteMbRun`). ✓
- Download + delete already-working (out of scope) → no task; regression in Task 7. ✓
- Tests for each surface → Tasks 1–6 + sweep in Task 7. ✓

**2. Placeholder scan:** No TBD/TODO. Test harness references ("mirror the
eu_v2 test") point at concrete existing tests in the same file rather than
inventing unknown helpers — acceptable because the exact row-injection
harness is file-local and must be matched, not reinvented.

**3. Type consistency:** `RepoEngine` gains `"mb_v2"` (Task 1) and is the
value matched in Repository branches (Task 6). `SaveToRepoEngine` gains
`"mb"` (Task 3), matched by `saveEngine="mb"` from FileViewer (Task 4) and
threaded through ViewerHeader (Task 4). Context methods `isMbSaved` /
`markMbSaved` / `markMbUnsaved` defined in Task 2 are consumed in Tasks 3
and 6. Helper names `saveMbRunToRepo` / `unsaveMbRunFromRepo` /
`listSavedMbRuns` defined in Task 1, consumed in Tasks 2, 3, 6. Consistent.
