# Earnings Update v2 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewire the existing Earnings Update frontend to the v2 backend — keeping the current visual design — by repointing the API client to `/v2`, rewriting the Settings modal (model + template + connectors), turning the cron schedule UI into a read-only upcoming-earnings calendar, reusing the v3 client-side report renderer, and adapting the feed/watchlist/on-demand flows.

**Architecture:** Frontend-only (React/TypeScript/Vite). The v2 backend (`/api/departments/earnings-update/v2`) already returns report detail in the same shape as Equity Research v3, so the v3 client-side renderer pipeline is reused. Model/template/connectors are per-user settings (no per-run override). No backend changes.

**Tech Stack:** React, TypeScript, Vite, Radix UI, lucide-react, Vitest + Testing Library. Run from `frontend/`.

**Spec:** `planning/2026-05-29-earnings-update-v2-frontend-design.md`

**Conventions:**
- All commands run from `frontend/`: `npm run test -- <path>` (Vitest), `npm run lint`, `npx tsc --noEmit` for type checks.
- Branch: `feat/earnings-update-v2-frontend` (already checked out).
- Commit after each green step. Every commit message ends with:
  ```

  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  ```
- The API client uses `fetchJson` from `frontend/src/api/client.ts` (signature: `fetchJson<T>(path, { method?, json? })`). SSE uses the browser `EventSource`.
- No emojis. Match existing file style (design-token CSS vars, `data-testid` conventions).

---

## File Structure

Create:
- `frontend/src/components/earnings-update/EuModelPicker.tsx` — model picker pill (clone of `V3ModelPicker`)
- `frontend/src/components/earnings-update/EuTemplateUploadModal.tsx` — template upload (clone of `V3TemplateUploadModal`)
- `frontend/src/components/viewer/renderers/EUV2ReportRenderer.tsx` — report renderer (clone of `V3ReportRenderer`)
- `frontend/src/components/report/adapters/euV2DetailAdapter.ts` — detail→schema adapter (clone of `v3DetailAdapter`)
- `frontend/src/hooks/useEuSettings.ts`, `useEuSchedule.ts`, `useEuTemplates.ts`, `useEuRunStream.ts`, `useEuRuns.ts`

Rewrite / modify:
- `frontend/src/api/earnings-update.ts` (full rewrite to v2)
- `frontend/src/components/viewer/FileViewerContext.tsx` (add `eu_v2_report` FileSource kind)
- `frontend/src/components/viewer/renderers/StructuredReportRenderer.tsx` (dispatch the new kind)
- `frontend/src/components/earnings-update/ReportSettingsModal.tsx` (model/template/connectors/reasoning; drop sections/custom)
- `frontend/src/components/earnings-update/OnDemandReportModal.tsx` (free ticker + v2 start/stream)
- `frontend/src/hooks/useEuWatchlist.ts` (v2 shape)
- `frontend/src/pages/departments/EarningsUpdate.tsx` (feed→runs, Up Next→schedule, watchlist join, live card, 503 banner)
- `frontend/src/components/earnings-update/feed/*` + `feedHelpers.ts` (new run shape, hero stats), `WatchlistCard.tsx` (schedule join)

Delete:
- `frontend/src/components/earnings-update/ScheduleManager.tsx`, `AddScheduleModal.tsx`, `CustomSectionRow.tsx`
- `frontend/src/lib/earnings-update/section-catalog.ts`
- `frontend/src/hooks/useEuConfig.ts`, `useEuReports.ts` (replaced by useEuSettings/useEuRuns)

---

## Phase A — API client (foundation)

### Task 1: Rewrite `earnings-update.ts` for v2

**Files:**
- Rewrite: `frontend/src/api/earnings-update.ts`
- Test: `frontend/src/api/__tests__/earnings-update.test.ts` (rewrite)

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/api/__tests__/earnings-update.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../client";
import {
  fetchWatchlist, addWatchlistEntry, syncWatchlist,
  fetchSettings, updateSettings,
  fetchTemplates, fetchSchedule,
  startRun, fetchRuns, getRun, deleteRun, cancelRun,
  runEventsUrl, EU_TERMINAL_EVENT_TYPES,
} from "../earnings-update";

afterEach(() => vi.restoreAllMocks());

function mockJson(value: unknown) {
  return vi.spyOn(client, "fetchJson").mockResolvedValue(value as never);
}

describe("earnings-update v2 client", () => {
  it("fetchWatchlist hits v2 watchlist", async () => {
    const spy = mockJson({ entries: [] });
    await fetchWatchlist();
    expect(spy).toHaveBeenCalledWith("/api/departments/earnings-update/v2/watchlist");
  });

  it("addWatchlistEntry POSTs ticker", async () => {
    const spy = mockJson({ id: "1", ticker: "MSFT.US", company_name: null, created_at: "" });
    await addWatchlistEntry("MSFT.US");
    expect(spy).toHaveBeenCalledWith("/api/departments/earnings-update/v2/watchlist", {
      method: "POST", json: { ticker: "MSFT.US" },
    });
  });

  it("syncWatchlist POSTs to /watchlist/sync", async () => {
    const spy = mockJson({ synced: 2 });
    const r = await syncWatchlist();
    expect(spy).toHaveBeenCalledWith("/api/departments/earnings-update/v2/watchlist/sync", { method: "POST" });
    expect(r.synced).toBe(2);
  });

  it("updateSettings PUTs settings", async () => {
    const settings = {
      provider_kind: "anthropic", model: "claude-sonnet-4-6", template_id: "eu_default",
      language: "en", length: "normal", reasoning_effort: null,
      financial_enabled: true, calendar_enabled: true, web_search_enabled: false,
    };
    const spy = mockJson(settings);
    await updateSettings(settings);
    expect(spy).toHaveBeenCalledWith("/api/departments/earnings-update/v2/settings", {
      method: "PUT", json: settings,
    });
  });

  it("startRun returns report_id", async () => {
    mockJson({ report_id: "r1" });
    const r = await startRun({ ticker: "AAPL.US" });
    expect(r.report_id).toBe("r1");
  });

  it("fetchRuns passes status filter", async () => {
    const spy = mockJson([]);
    await fetchRuns("completed");
    expect(spy).toHaveBeenCalledWith("/api/departments/earnings-update/v2/runs?status=completed");
  });

  it("runEventsUrl builds the SSE path", () => {
    expect(runEventsUrl("r1")).toBe("/api/departments/earnings-update/v2/runs/r1/events");
  });

  it("cancelRun POSTs cancel", async () => {
    const spy = mockJson({ cancelled: true });
    await cancelRun("r1");
    expect(spy).toHaveBeenCalledWith("/api/departments/earnings-update/v2/runs/r1/cancel", { method: "POST" });
  });

  it("terminal event set covers run.completed/failed/cancelled/snapshot", () => {
    expect(EU_TERMINAL_EVENT_TYPES.has("run.completed")).toBe(true);
    expect(EU_TERMINAL_EVENT_TYPES.has("run.snapshot")).toBe(true);
    expect(EU_TERMINAL_EVENT_TYPES.has("section.written")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/api/__tests__/earnings-update.test.ts`
Expected: FAIL (functions/exports not found, old v1 client present).

- [ ] **Step 3: Rewrite the client (full file)**

```typescript
// frontend/src/api/earnings-update.ts
import { fetchJson } from "./client";

const BASE = "/api/departments/earnings-update/v2";

// ----- Types -----
export type ReportLength = "concise" | "normal" | "elaborative";
export type ReleaseTiming = "pre_market" | "post_market" | null;
export type ReasoningEffort = "medium" | "high" | null;
export type RunStatus = "running" | "completed" | "failed";
export type ScheduleStatus = "pending" | "reported" | "skipped";

export interface WatchlistEntry {
  id: string;
  ticker: string;
  company_name: string | null;
  created_at: string;
}
export interface WatchlistListResponse { entries: WatchlistEntry[]; }

export interface EuSettings {
  provider_kind: string;
  model: string;
  template_id: string;
  language: string;
  length: ReportLength;
  reasoning_effort: ReasoningEffort;
  financial_enabled: boolean;
  calendar_enabled: boolean;
  web_search_enabled: boolean;
}

export interface EuTemplate {
  id: string;
  name: string;
  is_builtin: boolean;
  created_at: string;
}
export interface TemplateListResponse { templates: EuTemplate[]; }

export interface EuScheduleEntry {
  id: string;
  ticker: string;
  fiscal_date: string;
  release_timing: ReleaseTiming;
  scheduled_run_at: string;
  status: ScheduleStatus;
  report_id: string | null;
}
export interface ScheduleListResponse { schedule: EuScheduleEntry[]; }

export interface RunSummary {
  id: string;
  ticker: string;
  subject: string;
  template_id: string;
  status: RunStatus;
  trigger_kind: "scheduled" | "on_demand";
  created_at: string;
}

export interface SectionRow { section_id: string; section_index: number; title: string; markdown: string; version: number; }
export interface ChartRow { chart_id: string; chart_type: string; title: string; spec: Record<string, unknown>; rendered_url: string | null; version: number; }
export interface CitationRow { source_id: string; tool_name: string; display_index: number | null; provenance: Record<string, unknown>; }
export interface CoverSpec { subtitle?: string | null; tagline?: string | null; tldr?: string[]; key_metrics?: Array<Record<string, unknown>>; rating?: string | null; upside_pct?: number | null; }
export interface RunDetail {
  report: RunSummary;
  error_message: string | null;
  sections: SectionRow[];
  charts: ChartRow[];
  citations: CitationRow[];
  cover: CoverSpec | null;
}

// ----- SSE event types -----
export type EuEventType =
  | "run.started" | "tool.called" | "tool.completed"
  | "section.written" | "chart.emitted"
  | "run.completed" | "run.failed" | "run.cancelled" | "run.snapshot";
export interface EuEvent { type: EuEventType; payload: Record<string, unknown>; }
export const EU_TERMINAL_EVENT_TYPES: ReadonlySet<EuEventType> = new Set([
  "run.completed", "run.failed", "run.cancelled", "run.snapshot",
]);

// ----- Watchlist -----
export async function fetchWatchlist(): Promise<WatchlistListResponse> {
  return fetchJson<WatchlistListResponse>(`${BASE}/watchlist`);
}
export async function addWatchlistEntry(ticker: string): Promise<WatchlistEntry> {
  return fetchJson<WatchlistEntry>(`${BASE}/watchlist`, { method: "POST", json: { ticker } });
}
export async function removeWatchlistEntry(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/watchlist/${id}`, { method: "DELETE" });
}
export async function syncWatchlist(): Promise<{ synced: number }> {
  return fetchJson<{ synced: number }>(`${BASE}/watchlist/sync`, { method: "POST" });
}

// ----- Settings -----
export async function fetchSettings(): Promise<EuSettings> {
  return fetchJson<EuSettings>(`${BASE}/settings`);
}
export async function updateSettings(next: EuSettings): Promise<EuSettings> {
  return fetchJson<EuSettings>(`${BASE}/settings`, { method: "PUT", json: next });
}

// ----- Templates -----
export async function fetchTemplates(): Promise<TemplateListResponse> {
  return fetchJson<TemplateListResponse>(`${BASE}/templates`);
}
export async function uploadTemplate(payload: { name: string; source_markdown: string }): Promise<EuTemplate> {
  return fetchJson<EuTemplate>(`${BASE}/templates`, { method: "POST", json: payload });
}
export async function deleteTemplate(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/templates/${id}`, { method: "DELETE" });
}

// ----- Schedule (read-only) -----
export async function fetchSchedule(): Promise<ScheduleListResponse> {
  return fetchJson<ScheduleListResponse>(`${BASE}/schedule`);
}

// ----- Runs -----
export async function startRun(payload: { ticker: string }): Promise<{ report_id: string }> {
  return fetchJson<{ report_id: string }>(`${BASE}/runs/start`, { method: "POST", json: payload });
}
export async function fetchRuns(status?: RunStatus): Promise<RunSummary[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return fetchJson<RunSummary[]>(`${BASE}/runs${qs}`);
}
export async function getRun(id: string): Promise<RunDetail> {
  return fetchJson<RunDetail>(`${BASE}/runs/${encodeURIComponent(id)}`);
}
export async function deleteRun(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/runs/${id}`, { method: "DELETE" });
}
export async function cancelRun(id: string): Promise<{ cancelled: boolean }> {
  return fetchJson<{ cancelled: boolean }>(`${BASE}/runs/${id}/cancel`, { method: "POST" });
}
export function runEventsUrl(id: string): string {
  return `${BASE}/runs/${encodeURIComponent(id)}/events`;
}
```

NOTE: confirm the exact `RunSummary` / `RunDetail` field names against the backend route `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py` (`RunSummaryOut`, `RunDetailOut`, `SectionOut`, `ChartOut`, `CitationOut`, `CoverOut`) and align casing/optionality before finishing. Adjust if the backend differs (e.g. chart spec field name `spec` vs `spec_json`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/api/__tests__/earnings-update.test.ts`
Expected: PASS. Then `npx tsc --noEmit` — expect type errors only in files that still import the deleted v1 exports (fixed in later tasks; note them).

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run lint -- src/api/earnings-update.ts src/api/__tests__/earnings-update.test.ts
git add src/api/earnings-update.ts src/api/__tests__/earnings-update.test.ts
git commit -m "feat(eu-v2-fe): rewrite earnings-update API client for v2"
```

---

## Phase B — Report rendering reuse

### Task 2: Add `eu_v2_report` FileSource kind + dispatch

**Files:**
- Modify: `frontend/src/components/viewer/FileViewerContext.tsx` (the `FileSource` union)
- Modify: `frontend/src/components/viewer/renderers/StructuredReportRenderer.tsx`
- Create: `frontend/src/components/viewer/renderers/EUV2ReportRenderer.tsx`
- Create: `frontend/src/components/report/adapters/euV2DetailAdapter.ts`
- Test: `frontend/src/components/report/adapters/__tests__/euV2DetailAdapter.test.ts`

- [ ] **Step 1: Inspect the FileSource union**

Read `FileViewerContext.tsx`, find the `FileSource` discriminated union (it has `{ kind: "v3_report"; reportId: string }`). You will add `{ kind: "eu_v2_report"; reportId: string }`.

- [ ] **Step 2: Write the failing adapter test**

```typescript
// frontend/src/components/report/adapters/__tests__/euV2DetailAdapter.test.ts
import { describe, expect, it } from "vitest";
import { adaptEuV2DetailToSchema } from "../euV2DetailAdapter";
import type { RunDetail } from "../../../../api/earnings-update";

const detail: RunDetail = {
  report: { id: "r1", ticker: "MSFT.US", subject: "MSFT.US Q3 FY26 earnings", template_id: "eu_default", status: "completed", trigger_kind: "on_demand", created_at: "2026-05-30T00:00:00Z" },
  error_message: null,
  sections: [
    { section_id: "quick_take", section_index: 0, title: "Quick Take", markdown: "Beat on EPS [^eodhd_1].", version: 1 },
  ],
  charts: [],
  citations: [{ source_id: "eodhd_1", tool_name: "get_fundamentals", display_index: 1, provenance: { url: "https://eodhd.com" } }],
  cover: { subtitle: "Q3 FY26", tldr: ["Strong quarter"], rating: "Buy" },
};

describe("adaptEuV2DetailToSchema", () => {
  it("produces a ReportSchema with the section and a resolved citation", () => {
    const schema = adaptEuV2DetailToSchema(detail);
    expect(schema.sections.length).toBe(1);
    expect(schema.citations.length).toBe(1);
    // citation marker [^eodhd_1] rewritten to a numeric index in the section text
    const text = JSON.stringify(schema.sections[0]);
    expect(text).not.toContain("[^eodhd_1]");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/report/adapters/__tests__/euV2DetailAdapter.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 4: Create the adapter by copying v3's**

```bash
cd frontend && cp src/components/report/adapters/v3DetailAdapter.ts src/components/report/adapters/euV2DetailAdapter.ts
```
Then edit `euV2DetailAdapter.ts`:
- Rename the exported function `adaptV3DetailToSchema` → `adaptEuV2DetailToSchema`.
- Replace the input type import: instead of `V3ReportDetail` from `equity-research-v3`, import `RunDetail` (and the row types) from `../../../api/earnings-update`. The field shapes are identical (sections/charts/citations/cover), so the body needs no logic change — only the type names and any `department`/label string (set `department: "earnings_update"` in the produced schema if the adapter sets one).
- Keep ALL marker-rewriting / chart-splitting / cover logic identical.

If the v3 adapter references `V3SectionRow.spec` vs your `ChartRow.spec`, align the chart field access to your `RunDetail` row type names.

- [ ] **Step 5: Create the renderer by copying v3's**

```bash
cd frontend && cp src/components/viewer/renderers/V3ReportRenderer.tsx src/components/viewer/renderers/EUV2ReportRenderer.tsx
```
Edit `EUV2ReportRenderer.tsx`:
- Rename component `V3ReportRenderer` → `EUV2ReportRenderer`.
- Import `getRun` (aliased) + `RunDetail` from `../../../api/earnings-update` instead of `getV3Run`/`V3ReportDetail`.
- Change `const reportId = source.kind === "v3_report" ? source.reportId : null;` → `source.kind === "eu_v2_report"`.
- Call `getRun(reportId)` and `adaptEuV2DetailToSchema(detail)` from `../../report/adapters/euV2DetailAdapter`.
- Keep the dev-mode + loading/error states identical.

- [ ] **Step 6: Wire the dispatch + union**

In `FileViewerContext.tsx`, add `| { kind: "eu_v2_report"; reportId: string }` to the `FileSource` union.
In `StructuredReportRenderer.tsx`, add before the fallback:
```tsx
  if (source.kind === "eu_v2_report") {
    return <EUV2ReportRenderer source={source} />;
  }
```
and import `EUV2ReportRenderer`.

- [ ] **Step 7: Run test + typecheck**

Run: `cd frontend && npm run test -- src/components/report/adapters/__tests__/euV2DetailAdapter.test.ts && npx tsc --noEmit`
Expected: adapter test PASS; tsc clean for these files.

- [ ] **Step 8: Commit**

```bash
cd frontend && npm run lint -- src/components/viewer/renderers/EUV2ReportRenderer.tsx src/components/report/adapters/euV2DetailAdapter.ts src/components/viewer/renderers/StructuredReportRenderer.tsx src/components/viewer/FileViewerContext.tsx
git add src/components/viewer src/components/report/adapters
git commit -m "feat(eu-v2-fe): reuse v3 client-side renderer for eu_v2 reports"
```

---

## Phase C — Hooks

### Task 3: `useEuSettings` + `useEuRuns` (replace useEuConfig/useEuReports)

**Files:**
- Create: `frontend/src/hooks/useEuSettings.ts`, `frontend/src/hooks/useEuRuns.ts`
- Delete: `frontend/src/hooks/useEuConfig.ts`, `frontend/src/hooks/useEuReports.ts`
- Test: `frontend/src/hooks/__tests__/useEuSettings.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/hooks/__tests__/useEuSettings.test.tsx
import { renderHook, waitFor, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/earnings-update";
import { useEuSettings } from "../useEuSettings";

const base: api.EuSettings = {
  provider_kind: "anthropic", model: "claude-sonnet-4-6", template_id: "eu_default",
  language: "en", length: "normal", reasoning_effort: null,
  financial_enabled: true, calendar_enabled: true, web_search_enabled: false,
};

afterEach(() => vi.restoreAllMocks());

describe("useEuSettings", () => {
  it("loads settings then saves", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(base);
    const saveSpy = vi.spyOn(api, "updateSettings").mockResolvedValue({ ...base, web_search_enabled: true });
    const { result } = renderHook(() => useEuSettings());
    await waitFor(() => expect(result.current.settings).not.toBeNull());
    await act(async () => { await result.current.save({ ...base, web_search_enabled: true }); });
    expect(saveSpy).toHaveBeenCalled();
    expect(result.current.settings?.web_search_enabled).toBe(true);
  });
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd frontend && npm run test -- src/hooks/__tests__/useEuSettings.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement both hooks**

```typescript
// frontend/src/hooks/useEuSettings.ts
import { useCallback, useEffect, useState } from "react";
import { fetchSettings, updateSettings, type EuSettings } from "../api/earnings-update";

export interface EuSettingsState {
  settings: EuSettings | null;
  loading: boolean;
  error: Error | null;
  disabled: boolean; // true when the engine returns 503
  save: (next: EuSettings) => Promise<EuSettings>;
}

export function useEuSettings(): EuSettingsState {
  const [settings, setSettings] = useState<EuSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [disabled, setDisabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then((s) => { if (!cancelled) { setSettings(s); setLoading(false); } })
      .catch((e: Error) => {
        if (cancelled) return;
        if (/\b503\b/.test(e.message)) setDisabled(true);
        else setError(e);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const save = useCallback(async (next: EuSettings) => {
    const saved = await updateSettings(next);
    setSettings(saved);
    return saved;
  }, []);

  return { settings, loading, error, disabled, save };
}
```

```typescript
// frontend/src/hooks/useEuRuns.ts
import { useCallback, useEffect, useState } from "react";
import { fetchRuns, type RunSummary, type RunStatus } from "../api/earnings-update";

export interface EuRunsState {
  runs: RunSummary[];
  loading: boolean;
  error: Error | null;
  disabled: boolean;
  refresh: () => Promise<void>;
}

export function useEuRuns(status?: RunStatus): EuRunsState {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [disabled, setDisabled] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = await fetchRuns(status);
      setRuns(next);
      setError(null);
    } catch (e) {
      const err = e as Error;
      if (/\b503\b/.test(err.message)) setDisabled(true);
      else setError(err);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { void refresh(); }, [refresh]);

  return { runs, loading, error, disabled, refresh };
}
```

Delete the old hooks:
```bash
cd frontend && git rm src/hooks/useEuConfig.ts src/hooks/useEuReports.ts
```

- [ ] **Step 4: Run test + typecheck**

Run: `cd frontend && npm run test -- src/hooks/__tests__/useEuSettings.test.tsx`
Expected: PASS. (`tsc --noEmit` will still flag the page/components importing the old hooks — fixed in Phase E.)

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run lint -- src/hooks/useEuSettings.ts src/hooks/useEuRuns.ts
git add src/hooks
git commit -m "feat(eu-v2-fe): useEuSettings + useEuRuns hooks (replace config/reports)"
```

### Task 4: `useEuSchedule` + `useEuTemplates`

**Files:**
- Create: `frontend/src/hooks/useEuSchedule.ts`, `frontend/src/hooks/useEuTemplates.ts`
- Test: `frontend/src/hooks/__tests__/useEuSchedule.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/hooks/__tests__/useEuSchedule.test.tsx
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/earnings-update";
import { useEuSchedule } from "../useEuSchedule";

afterEach(() => vi.restoreAllMocks());

describe("useEuSchedule", () => {
  it("loads schedule and exposes a byTicker map", async () => {
    vi.spyOn(api, "fetchSchedule").mockResolvedValue({
      schedule: [
        { id: "s1", ticker: "MSFT.US", fiscal_date: "2026-06-15", release_timing: "post_market", scheduled_run_at: "2026-06-15T23:00:00Z", status: "pending", report_id: null },
      ],
    });
    const { result } = renderHook(() => useEuSchedule());
    await waitFor(() => expect(result.current.schedule.length).toBe(1));
    expect(result.current.byTicker.get("MSFT.US")?.fiscal_date).toBe("2026-06-15");
  });
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd frontend && npm run test -- src/hooks/__tests__/useEuSchedule.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement both hooks**

```typescript
// frontend/src/hooks/useEuSchedule.ts
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchSchedule, type EuScheduleEntry } from "../api/earnings-update";

export function useEuSchedule() {
  const [schedule, setSchedule] = useState<EuScheduleEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { schedule: rows } = await fetchSchedule();
      setSchedule(rows);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // Soonest pending release per ticker, for the watchlist-card join.
  const byTicker = useMemo(() => {
    const m = new Map<string, EuScheduleEntry>();
    for (const row of schedule) {
      const cur = m.get(row.ticker);
      if (!cur || row.scheduled_run_at < cur.scheduled_run_at) m.set(row.ticker, row);
    }
    return m;
  }, [schedule]);

  return { schedule, byTicker, loading, error, refresh };
}
```

```typescript
// frontend/src/hooks/useEuTemplates.ts
import { useCallback, useEffect, useState } from "react";
import {
  fetchTemplates, uploadTemplate, deleteTemplate, type EuTemplate,
} from "../api/earnings-update";

export function useEuTemplates() {
  const [templates, setTemplates] = useState<EuTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { templates: rows } = await fetchTemplates();
      setTemplates(rows);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const upload = useCallback(async (name: string, source_markdown: string) => {
    const created = await uploadTemplate({ name, source_markdown });
    await refresh();
    return created;
  }, [refresh]);

  const remove = useCallback(async (id: string) => {
    await deleteTemplate(id);
    await refresh();
  }, [refresh]);

  return { templates, loading, error, refresh, upload, remove };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/hooks/__tests__/useEuSchedule.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run lint -- src/hooks/useEuSchedule.ts src/hooks/useEuTemplates.ts
git add src/hooks
git commit -m "feat(eu-v2-fe): useEuSchedule + useEuTemplates hooks"
```

### Task 5: `useEuRunStream` (clone of useV3RunStream)

**Files:**
- Create: `frontend/src/hooks/useEuRunStream.ts`
- Test: `frontend/src/hooks/__tests__/useEuRunStream.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/hooks/__tests__/useEuRunStream.test.tsx
import { renderHook, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEuRunStream } from "../useEuRunStream";

class FakeEventSource {
  static last: FakeEventSource | null = null;
  listeners = new Map<string, (e: MessageEvent) => void>();
  readyState = 0;
  url: string;
  onerror: ((e: unknown) => void) | null = null;
  constructor(url: string) { this.url = url; FakeEventSource.last = this; }
  addEventListener(t: string, cb: (e: MessageEvent) => void) { this.listeners.set(t, cb); }
  emit(t: string, data: unknown) { this.listeners.get(t)?.({ data: JSON.stringify(data) } as MessageEvent); }
  close() { this.readyState = 2; }
}

beforeEach(() => { (globalThis as unknown as { EventSource: unknown }).EventSource = FakeEventSource as unknown; });
afterEach(() => vi.restoreAllMocks());

describe("useEuRunStream", () => {
  it("counts sections and resolves to completed on run.completed", () => {
    const { result } = renderHook(() => useEuRunStream("r1"));
    act(() => { FakeEventSource.last!.emit("section.written", {}); });
    expect(result.current.sectionsWritten).toBe(1);
    act(() => { FakeEventSource.last!.emit("run.completed", { message: "done" }); });
    expect(result.current.status).toBe("completed");
  });
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd frontend && npm run test -- src/hooks/__tests__/useEuRunStream.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Create by copying useV3RunStream**

```bash
cd frontend && cp src/components/equity-research-v3/useV3RunStream.ts src/hooks/useEuRunStream.ts
```
Edit `useEuRunStream.ts`:
- Rename `useV3RunStream`→`useEuRunStream`, `V3StreamStatus`→`EuStreamStatus`, `V3StreamState`→`EuStreamState`.
- Replace imports from `../../api/equity-research-v3` with `../api/earnings-update`: `cancelV3Run`→`cancelRun`, `v3EventsUrl`→`runEventsUrl`, `V3_TERMINAL_EVENT_TYPES`→`EU_TERMINAL_EVENT_TYPES`, `V3Event`→`EuEvent`, `V3EventType`→`EuEventType`.
- The event-type list and terminal logic are identical (same event names). No other changes.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/hooks/__tests__/useEuRunStream.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run lint -- src/hooks/useEuRunStream.ts
git add src/hooks/useEuRunStream.ts
git commit -m "feat(eu-v2-fe): useEuRunStream SSE hook (clone of v3)"
```

### Task 6: Update `useEuWatchlist` to the v2 shape

**Files:**
- Modify: `frontend/src/hooks/useEuWatchlist.ts`
- Test: `frontend/src/hooks/__tests__/useEuWatchlist.test.tsx` (create if absent)

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/hooks/__tests__/useEuWatchlist.test.tsx
import { renderHook, waitFor, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/earnings-update";
import { useEuWatchlist } from "../useEuWatchlist";

afterEach(() => vi.restoreAllMocks());

describe("useEuWatchlist (v2)", () => {
  it("loads, adds, and removes entries", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "addWatchlistEntry").mockResolvedValue({ id: "1", ticker: "MSFT.US", company_name: null, created_at: "" });
    vi.spyOn(api, "removeWatchlistEntry").mockResolvedValue(undefined);
    const { result } = renderHook(() => useEuWatchlist());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.add("MSFT.US"); });
    expect(result.current.entries.some((e) => e.ticker === "MSFT.US")).toBe(true);
    await act(async () => { await result.current.remove("1"); });
    expect(result.current.entries.length).toBe(0);
  });
});
```

- [ ] **Step 2: Run to verify fail/regression**

Run: `cd frontend && npm run test -- src/hooks/__tests__/useEuWatchlist.test.tsx`
Expected: FAIL if the hook still references removed v1 fields (or passes if already compatible — then just ensure the v2 `WatchlistEntry` shape is used).

- [ ] **Step 3: Update the hook**

Read the current `useEuWatchlist.ts`; keep its `entries/add/remove/loading/error/refresh` surface; ensure it imports `WatchlistEntry` from the v2 client and uses `addWatchlistEntry`/`removeWatchlistEntry`/`fetchWatchlist`. Add an optional `syncNow` that calls `syncWatchlist()` then `refresh()`. Remove any reference to `next_earnings_date`/`release_timing` (those now come from the schedule join in the component).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/hooks/__tests__/useEuWatchlist.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run lint -- src/hooks/useEuWatchlist.ts
git add src/hooks/useEuWatchlist.ts src/hooks/__tests__/useEuWatchlist.test.tsx
git commit -m "feat(eu-v2-fe): useEuWatchlist on v2 watchlist shape"
```

---

## Phase D — Components

### Task 7: `EuModelPicker` (clone of V3ModelPicker)

**Files:**
- Create: `frontend/src/components/earnings-update/EuModelPicker.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/EuModelPicker.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/earnings-update/__tests__/EuModelPicker.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as settings from "../../../api/settings";
import { EuModelPicker } from "../EuModelPicker";

afterEach(() => vi.restoreAllMocks());

describe("EuModelPicker", () => {
  it("emits the first enabled model on load", async () => {
    vi.spyOn(settings, "getEnabledModels").mockResolvedValue([
      { id: "m1", provider_kind: "anthropic", model_ref: "claude-sonnet-4-6", display_name: "Claude Sonnet 4.6", is_enabled: true } as never,
    ]);
    const onChange = vi.fn();
    render(<EuModelPicker onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ provider_kind: "anthropic", model: "claude-sonnet-4-6" })));
  });
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd frontend && npm run test -- src/components/earnings-update/__tests__/EuModelPicker.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Create by copying V3ModelPicker**

```bash
cd frontend && cp src/components/equity-research-v3/V3ModelPicker.tsx src/components/earnings-update/EuModelPicker.tsx
```
Edit `EuModelPicker.tsx`:
- Rename component `V3ModelPicker`→`EuModelPicker`, interface `V3ModelSelection`→`EuModelSelection`.
- Change `const LS_KEY = "er.v3.model_id"` → `"eu.v2.model_id"`.
- Replace `data-testid` / `aria-label` strings `er-v3-*` → `eu-v2-*` and "v3 engine" → "Earnings Update v2".
- Everything else (RosterEntry source, grouping, dropdown) unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/components/earnings-update/__tests__/EuModelPicker.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run lint -- src/components/earnings-update/EuModelPicker.tsx
git add src/components/earnings-update/EuModelPicker.tsx src/components/earnings-update/__tests__/EuModelPicker.test.tsx
git commit -m "feat(eu-v2-fe): EuModelPicker (clone of V3ModelPicker)"
```

### Task 8: `EuTemplateUploadModal` (clone of V3TemplateUploadModal)

**Files:**
- Create: `frontend/src/components/earnings-update/EuTemplateUploadModal.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/EuTemplateUploadModal.test.tsx`

- [ ] **Step 1: Read `V3TemplateUploadModal.tsx`** to learn its props (open/onClose/onUploaded), the DOCX→markdown ingest call, and the POST it makes. Note the props signature.

- [ ] **Step 2: Write a focused failing test** asserting the modal renders a name field + file input and calls an injected `onUpload(name, markdown)` (refactor the clone to take `onUpload` as a prop so it routes to `useEuTemplates().upload` instead of v3's hardcoded endpoint):

```tsx
// frontend/src/components/earnings-update/__tests__/EuTemplateUploadModal.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EuTemplateUploadModal } from "../EuTemplateUploadModal";

describe("EuTemplateUploadModal", () => {
  it("renders when open", () => {
    render(<EuTemplateUploadModal open onClose={() => {}} onUpload={vi.fn()} />);
    expect(screen.getByText(/template/i)).toBeTruthy();
  });
});
```

- [ ] **Step 3: Run to verify fail.** `cd frontend && npm run test -- src/components/earnings-update/__tests__/EuTemplateUploadModal.test.tsx` → FAIL.

- [ ] **Step 4: Create by copying + adapting.**
```bash
cd frontend && cp src/components/equity-research-v3/V3TemplateUploadModal.tsx src/components/earnings-update/EuTemplateUploadModal.tsx
```
Edit: rename to `EuTemplateUploadModal`; change the props to `{ open: boolean; onClose: () => void; onUpload: (name: string, markdown: string) => Promise<void> }`; replace the hardcoded v3 `POST /equity-research-v3/templates` with a call to the injected `onUpload(name, markdown)`. Keep the file picker, DOCX→markdown ingest (`/api/report-templates/ingest`), name auto-fill, and heading-count preview unchanged.

- [ ] **Step 5: Run test → PASS.**

- [ ] **Step 6: Commit.**
```bash
cd frontend && npm run lint -- src/components/earnings-update/EuTemplateUploadModal.tsx
git add src/components/earnings-update/EuTemplateUploadModal.tsx src/components/earnings-update/__tests__/EuTemplateUploadModal.test.tsx
git commit -m "feat(eu-v2-fe): EuTemplateUploadModal (clone of V3 upload modal)"
```

### Task 9: Rewrite `ReportSettingsModal`

**Files:**
- Rewrite: `frontend/src/components/earnings-update/ReportSettingsModal.tsx`
- Delete: `frontend/src/components/earnings-update/CustomSectionRow.tsx`, `frontend/src/lib/earnings-update/section-catalog.ts`
- Test: `frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx` (rewrite)

- [ ] **Step 1: Read the current `ReportSettingsModal.tsx`** to keep its modal chrome, header, footer Save/Cancel buttons, and visual classes. The new body replaces the section toggles + custom-section editor.

- [ ] **Step 2: Write the failing test**

```tsx
// frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as settingsApi from "../../../api/settings";
import * as euApi from "../../../api/earnings-update";
import { ReportSettingsModal } from "../ReportSettingsModal";

const base: euApi.EuSettings = {
  provider_kind: "anthropic", model: "claude-sonnet-4-6", template_id: "eu_default",
  language: "en", length: "normal", reasoning_effort: null,
  financial_enabled: true, calendar_enabled: true, web_search_enabled: false,
};

afterEach(() => vi.restoreAllMocks());

describe("ReportSettingsModal (v2)", () => {
  it("renders connector toggles and saves changes", async () => {
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([
      { id: "m1", provider_kind: "anthropic", model_ref: "claude-sonnet-4-6", display_name: "Claude Sonnet 4.6", is_enabled: true } as never,
    ]);
    vi.spyOn(euApi, "fetchTemplates").mockResolvedValue({ templates: [{ id: "eu_default", name: "Earnings Update (Default)", is_builtin: true, created_at: "" }] });
    const onSave = vi.fn().mockResolvedValue(base);
    render(<ReportSettingsModal settings={base} onSave={onSave} onClose={() => {}} />);
    // toggle web search on
    const webSearch = await screen.findByTestId("eu-v2-connector-web_search");
    fireEvent.click(webSearch);
    fireEvent.click(screen.getByTestId("eu-v2-settings-save"));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ web_search_enabled: true })));
  });

  it("does not render section toggles or custom sections", () => {
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
    vi.spyOn(euApi, "fetchTemplates").mockResolvedValue({ templates: [] });
    render(<ReportSettingsModal settings={base} onSave={vi.fn()} onClose={() => {}} />);
    expect(screen.queryByText(/custom section/i)).toBeNull();
  });
});
```

- [ ] **Step 3: Run to verify fail.** FAIL (modal still v1 / new props absent).

- [ ] **Step 4: Rewrite the modal.** New props: `{ settings: EuSettings; onSave: (next: EuSettings) => Promise<unknown>; onClose: () => void }`. Local draft state seeded from `settings`. Body sections, each in the existing modal's visual style:
  - **Model**: `<EuModelPicker onChange={(sel) => sel && setDraft(d => ({ ...d, provider_kind: sel.provider_kind, model: sel.model }))} />`.
  - **Template**: a `<select>` populated from `useEuTemplates()` (builtin first), bound to `draft.template_id`; an "Upload template" button opening `EuTemplateUploadModal` (on upload, refresh list and select the new template); a delete affordance for non-builtin templates.
  - **Connectors**: three toggle switches with `data-testid="eu-v2-connector-financial|calendar|web_search"` bound to `financial_enabled`/`calendar_enabled`/`web_search_enabled`.
  - **Length**: radio/select concise/normal/elaborative → `draft.length`.
  - **Language**: select en / zh-Hant → `draft.language`.
  - **Reasoning effort**: select Default/Medium/High → `draft.reasoning_effort` (Default = null); render ONLY when `draft.provider_kind === "anthropic"`.
  - **Footer**: Save button `data-testid="eu-v2-settings-save"` calls `onSave(draft)` then `onClose()`; Cancel calls `onClose()`.
  Delete the section-catalog import and `CustomSectionRow`:
```bash
cd frontend && git rm src/components/earnings-update/CustomSectionRow.tsx src/lib/earnings-update/section-catalog.ts
```

- [ ] **Step 5: Run test → PASS.** Then `npx tsc --noEmit` for this file.

- [ ] **Step 6: Commit.**
```bash
cd frontend && npm run lint -- src/components/earnings-update/ReportSettingsModal.tsx
git add src/components/earnings-update/ReportSettingsModal.tsx src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx src/lib src/components/earnings-update/CustomSectionRow.tsx
git commit -m "feat(eu-v2-fe): rewrite settings modal (model/template/connectors/reasoning)"
```

### Task 10: Update `OnDemandReportModal`

**Files:**
- Modify: `frontend/src/components/earnings-update/OnDemandReportModal.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/OnDemandReportModal.test.tsx` (create/rewrite)

- [ ] **Step 1: Read the current modal** (126 lines) to keep its look.

- [ ] **Step 2: Write the failing test**

```tsx
// frontend/src/components/earnings-update/__tests__/OnDemandReportModal.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../../api/earnings-update";
import { OnDemandReportModal } from "../OnDemandReportModal";

afterEach(() => vi.restoreAllMocks());

describe("OnDemandReportModal (v2)", () => {
  it("accepts a free-text ticker and starts a run", async () => {
    const startSpy = vi.spyOn(api, "startRun").mockResolvedValue({ report_id: "r1" });
    const onStarted = vi.fn();
    render(<OnDemandReportModal open watchlist={[]} onClose={() => {}} onStarted={onStarted} />);
    fireEvent.change(screen.getByTestId("eu-v2-ondemand-ticker"), { target: { value: "NVDA.US" } });
    fireEvent.click(screen.getByTestId("eu-v2-ondemand-start"));
    await waitFor(() => expect(startSpy).toHaveBeenCalledWith({ ticker: "NVDA.US" }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith("r1", "NVDA.US"));
  });
});
```

- [ ] **Step 3: Run to verify fail.**

- [ ] **Step 4: Update the modal.** Props `{ open: boolean; watchlist: WatchlistEntry[]; onClose: () => void; onStarted: (reportId: string, ticker: string) => void }`. Free-text ticker input (`data-testid="eu-v2-ondemand-ticker"`) that accepts ANY ticker; offer watchlist tickers as datalist suggestions. Start button (`data-testid="eu-v2-ondemand-start"`) calls `startRun({ ticker })`, then `onStarted(report_id, ticker)` (the page drives the live card + stream). Add a small read-only line "Uses your saved model & template — change in Settings". Remove the old POST-and-consume-SSE logic.

- [ ] **Step 5: Run test → PASS.**

- [ ] **Step 6: Commit.**
```bash
cd frontend && npm run lint -- src/components/earnings-update/OnDemandReportModal.tsx
git add src/components/earnings-update/OnDemandReportModal.tsx src/components/earnings-update/__tests__/OnDemandReportModal.test.tsx
git commit -m "feat(eu-v2-fe): on-demand modal accepts any ticker, starts v2 run"
```

---

## Phase E — Page wiring + feed + schedule + cleanup

### Task 11: Delete cron schedule UI

**Files:**
- Delete: `frontend/src/components/earnings-update/ScheduleManager.tsx`, `AddScheduleModal.tsx` (+ their tests)

- [ ] **Step 1: Confirm no remaining imports**

Run: `cd frontend && grep -rn "ScheduleManager\|AddScheduleModal" src` — note every importer (should be only the page, fixed in Task 13).

- [ ] **Step 2: Delete the files**

```bash
cd frontend && git rm src/components/earnings-update/ScheduleManager.tsx src/components/earnings-update/AddScheduleModal.tsx
# also remove their test files if present:
cd frontend && git rm -f src/components/earnings-update/__tests__/ScheduleManager.test.tsx src/components/earnings-update/__tests__/AddScheduleModal.test.tsx 2>/dev/null || true
```

- [ ] **Step 3: Commit** (the page still references them — that's fixed in Task 13; this commit may not typecheck alone, which is fine on the branch):

```bash
git commit -m "chore(eu-v2-fe): remove cron schedule UI (no v2 equivalent)"
```

### Task 12: Schedule view + watchlist card schedule-join

**Files:**
- Modify: `frontend/src/components/earnings-update/feed/EuUpNextCard.tsx` (or the "Up Next" section component) to render `EuScheduleEntry`
- Modify: `frontend/src/components/earnings-update/WatchlistCard.tsx` (accept an optional next-release prop)
- Test: `frontend/src/components/earnings-update/__tests__/EuUpNextCard.test.tsx`

- [ ] **Step 1: Write the failing test** for the Up Next card rendering a schedule entry (ticker, fiscal date, pre/post badge, status). Then run → FAIL.

```tsx
// frontend/src/components/earnings-update/__tests__/EuUpNextCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EuUpNextCard } from "../feed/EuUpNextCard";

describe("EuUpNextCard", () => {
  it("shows ticker, fiscal date, and timing badge", () => {
    render(<EuUpNextCard entry={{ id: "s1", ticker: "MSFT.US", fiscal_date: "2026-06-15", release_timing: "post_market", scheduled_run_at: "2026-06-15T23:00:00Z", status: "pending", report_id: null }} />);
    expect(screen.getByText(/MSFT/)).toBeTruthy();
    expect(screen.getByText(/2026-06-15/)).toBeTruthy();
    expect(screen.getByText(/post/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Implement** the Up Next card to take an `entry: EuScheduleEntry` prop and render ticker, fiscal date, a pre/post-market badge, and (optionally) the scheduled run time. Update `WatchlistCard.tsx` to accept an optional `nextRelease?: EuScheduleEntry` prop and show its date + timing badge when present (else a neutral "no upcoming date").

- [ ] **Step 3: Run test → PASS. Commit.**
```bash
cd frontend && npm run lint -- src/components/earnings-update/feed/EuUpNextCard.tsx src/components/earnings-update/WatchlistCard.tsx
git add src/components/earnings-update/feed/EuUpNextCard.tsx src/components/earnings-update/WatchlistCard.tsx src/components/earnings-update/__tests__/EuUpNextCard.test.tsx
git commit -m "feat(eu-v2-fe): schedule-driven Up Next card + watchlist next-release join"
```

### Task 13: Wire the page (`EarningsUpdate.tsx`)

**Files:**
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx`
- Modify: `frontend/src/components/earnings-update/feed/feedHelpers.ts`, `EuHero.tsx`, `EuBigCard.tsx`, `EuReportRow.tsx` (new run shape)
- Test: `frontend/src/pages/departments/__tests__/EarningsUpdate.test.tsx` (update)

- [ ] **Step 1: Read the current page** to preserve layout/state structure. Identify where it used `useEuConfig`, `useEuReports`, the schedule manager, and the v1 on-demand flow.

- [ ] **Step 2: Update feed helpers + hero for the new shape.** `feedHelpers.ts` `groupReports`/`applyFilter` operate on `RunSummary` (fields: `ticker`, `subject`, `status`, `created_at`, `trigger_kind`). `EuHero` shows reports-this-week (count of `runs` with `created_at` in the last 7 days) + pending-scheduled (count of `schedule` rows with `status==="pending"`). `EuBigCard`/`EuReportRow` read `RunSummary` fields. Update their prop types and any field access. Add/adjust a focused test for `groupReports` on the new shape.

- [ ] **Step 3: Rewire the page.** Replace hooks: `useEuRuns()` (feed), `useEuSettings()` (settings modal), `useEuSchedule()` (Up Next + watchlist join), `useEuWatchlist()` (unchanged surface), `useEuTemplates()` (passed into settings modal). 
  - Settings button opens the rewritten `ReportSettingsModal` with `settings={settings}` and `onSave={save}`.
  - On-demand button opens `OnDemandReportModal`; its `onStarted(reportId, ticker)` sets a `liveCard` state and renders the streaming card driven by `useEuRunStream(liveReportId)`; on `status==="completed"` the card links to open the report.
  - "Open report" anywhere calls `fileViewer.open({ filename: run.subject, kind: "report", source: { kind: "eu_v2_report", reportId: run.id }, metadata: \`EU v2 · ${run.ticker}\` })`.
  - Delete report → `deleteRun(id)` then `runs.refresh()`.
  - "Up Next" section maps `schedule` (pending) to `EuUpNextCard`.
  - Watchlist cards receive `nextRelease={schedule.byTicker.get(entry.ticker)}`.
  - Remove all imports of `ScheduleManager`/`AddScheduleModal`/`useEuConfig`/`useEuReports`/section-catalog.

- [ ] **Step 4: Engine-disabled banner.** When `useEuSettings().disabled` (or `useEuRuns().disabled`) is true, render a non-blocking banner at the top: "Earnings Update v2 is disabled. Set EARNINGS_ENGINE_VERSION=v2 to enable." (testid `eu-v2-disabled-banner`).

- [ ] **Step 5: Update the page test** to mock the v2 hooks/api and assert: feed renders runs, the Up Next section renders schedule rows, opening a report calls `fileViewer.open` with `kind: "eu_v2_report"`, and the disabled banner shows on 503.

- [ ] **Step 6: Run tests + full typecheck.**

Run:
```bash
cd frontend && npm run test -- src/pages/departments/__tests__/EarningsUpdate.test.tsx && npx tsc --noEmit
```
Expected: page test PASS; `tsc --noEmit` now CLEAN across the whole frontend (all old-hook/old-client references resolved).

- [ ] **Step 7: Commit.**
```bash
cd frontend && npm run lint
git add src/pages/departments/EarningsUpdate.tsx src/components/earnings-update/feed src/pages/departments/__tests__/EarningsUpdate.test.tsx
git commit -m "feat(eu-v2-fe): wire Earnings Update page to v2 (runs, schedule, live stream)"
```

---

## Phase F — Verification

### Task 14: Full frontend check + visual smoke

- [ ] **Step 1: Type + lint + unit tests, whole frontend**

Run:
```bash
cd frontend && npx tsc --noEmit && npm run lint && npm run test -- src/api/__tests__/earnings-update.test.ts src/hooks/__tests__ src/components/earnings-update src/components/report/adapters
```
Expected: all green. Fix any straggler imports of deleted modules.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds (no unresolved imports / type errors).

- [ ] **Step 3: Manual smoke (documented, not automated)** — with the backend running and `EARNINGS_ENGINE_VERSION=v2`, load `/earnings-update`: confirm the feed loads from `/v2/runs`, Settings shows model/template/connectors, an on-demand run streams and opens a rendered report, the Up Next section shows schedule rows, and a watchlist add shows a next-release date. Note results in the PR description.

- [ ] **Step 4: Commit any fixes from Steps 1-2.**
```bash
git add -A && git commit -m "fix(eu-v2-fe): resolve type/lint stragglers after v2 rewire"
```

### Task 15: Planning doc + PR

- [ ] **Step 1: Append an "as-built" note** to `planning/2026-05-29-earnings-update-v2-frontend-design.md` recording any divergences (per coding standard #9).
- [ ] **Step 2: Push + open PR** (only when the user asks):
```bash
git push -u origin feat/earnings-update-v2-frontend
gh pr create --base main --title "feat(earnings-update): v2 frontend rewire" --body "Implements planning/2026-05-29-earnings-update-v2-frontend-design.md. Rewires the existing Earnings Update page to the v2 backend; keeps the visual design. No backend changes."
```

---

## Self-review (spec coverage)

- Spec §2 strategy (rewire in place, settings-only, reuse v3 renderer) → Tasks 1-13 (no backend work).
- Spec §3 API client → Task 1.
- Spec §4 settings modal (model/template/connectors/reasoning, drop sections/custom) → Tasks 7, 8, 9.
- Spec §5 on-demand any-ticker → Task 10.
- Spec §6 schedule read-only (cron removed, Up Next from /schedule) → Tasks 11, 12, 13.
- Spec §7 watchlist schedule-join → Tasks 6, 12, 13.
- Spec §8 reports feed + report display (reuse v3 renderer) → Tasks 2, 13.
- Spec §9 hooks → Tasks 3, 4, 5, 6.
- Spec §10 live run UX → Tasks 5, 10, 13.
- Spec §11 engine-disabled banner → Tasks 3 (disabled state), 13 (banner).
- Spec §12 files (create/modify/delete) → mapped across tasks; deletions in Tasks 3, 9, 11.
- Spec §13 testing → every task is TDD; Task 14 is the full-suite gate.

Open follow-ups (non-blocking): if the backend `RunSummaryOut`/`RunDetailOut` field names differ from the assumed shape (Task 1 NOTE), align the client types and the adapter before Task 13's typecheck gate.
