# ER v3 Generation UI Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ER v3's raw streaming panel with a single report card that is present from the first stream frame, evolves in place (`GENERATING` → `READY`), shows live counts + an elapsed timer, folds the event log into a styled in-card activity feed, and ports the mockup's full entrance choreography.

**Architecture:** Frontend-only. One phase-aware `V3ReportCard` (no swap), a new `V3ActivityFeed` sub-component, two extra fields on `useV3RunStream` (elapsed timer + live citation count), a generating affordance on the composer mode pill, a generating pill in the shared TopBar via the existing chat-header registry, and a global `motion-shell.css` choreography keyed off opt-in shell data attributes. No core/engine/SSE-contract changes.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind + CSS custom-property design tokens, framer-motion, lucide-react, Vitest + @testing-library/react. Package manager for the frontend is `npm` (run from `frontend/`).

**Spec:** `docs/superpowers/specs/2026-05-31-er-v3-generation-ui-polish-design.md`

**Conventions:**
- All commands run from `frontend/` unless noted.
- Single-file test run: `npx vitest run <path>`.
- Typecheck/build gate: `npm run build` (Vite runs `tsc`).
- Tests live in `src/components/equity-research-v3/__tests__/`.
- Tokens already match the mockup (`#D4FF00` accent, Geist / IBM Plex Mono) — never hardcode hex where a `--color-*` / `--yellow-*` token exists.

---

## File Structure

| File | Responsibility | Action |
| --- | --- | --- |
| `src/components/equity-research-v3/useV3RunStream.ts` | SSE lifecycle + live counters. Add `elapsedSeconds` and `citationsSeen`. | Modify |
| `src/components/equity-research-v3/V3ActivityFeed.tsx` | Styled in-card activity timeline + "Show all activity" disclosure. Owns `summarizePayload`. | Create |
| `src/components/equity-research-v3/V3ReportCard.tsx` | Phase-aware card (`generating` \| `ready`). Header/pill/meta/body/actions switch on phase. | Modify |
| `src/components/equity-research-v3/V3ChatThread.tsx` | Render the phase-aware card from the first stream frame; retire `StreamPanel`/`StatusBadge`/`Chip`; widen the `stream` prop. | Modify |
| `src/components/equity-research/ErComposer.tsx` | Generating affordance on the mode pill while `isStreaming`. | Modify |
| `src/layouts/ChatHeaderContext.tsx` | Add optional `generating?: boolean` to the registry value. | Modify |
| `src/components/shell/TopBar.tsx` | Render a `GENERATING` `LivePill` when `chatHeader.generating`. | Modify |
| `src/pages/departments/EquityResearchV3.tsx` | Pass `elapsedSeconds`/`citationsSeen` through; publish `generating`; toggle `om-anim` on mount. | Modify |
| `src/styles/motion-shell.css` | `om-anim` entrance choreography + reduced-motion block. | Create |
| `src/styles/global.css` | `@import "./motion-shell.css";` | Modify |
| `src/layouts/AppLayout.tsx` | `data-om-shell="topbar"` on `<header>`, `data-om-shell="content"` on `<main>`. | Modify |
| `src/components/sidebar/Sidebar.tsx` | `data-om-shell="sidebar"` on the root `<nav>`. | Modify |
| `__tests__/V3ReportCard.test.tsx` | New phase tests; existing ready-phase tests stay green. | Modify |
| `__tests__/V3ChatThread.test.tsx` | Update assertions from `er-v3-stream-panel` to the phase-aware card. | Modify |
| `__tests__/useV3RunStream.test.ts` | Add elapsed + citation tests. | Modify |
| `__tests__/V3ActivityFeed.test.tsx` | New. | Create |

**WelcomeStage:** no code change. It already uses shared tokens and the `templateLabel` override; the entrance motion it gains comes from `motion-shell.css`. Verify visually in the final manual pass.

---

## Task 1: `useV3RunStream` — elapsed timer + live citation count

Adds two fields so the generating card can show "Elapsed Xs" and a live "N sources" count. `elapsedSeconds` is `null` until a real `run.started` frame (so reloaded/snapshot runs, which emit `run.snapshot`, never show a bogus near-zero duration).

**Files:**
- Modify: `src/components/equity-research-v3/useV3RunStream.ts`
- Test: `src/components/equity-research-v3/__tests__/useV3RunStream.test.ts`

- [ ] **Step 1: Write the failing tests**

Append these two tests inside the `describe("useV3RunStream", ...)` block in `__tests__/useV3RunStream.test.ts`:

```ts
it("counts citations from tool.completed frames that carry a source_id", async () => {
  const { result } = renderHook(() => useV3RunStream("run-1"));
  await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));
  const source = FakeEventSource.instances[0];

  act(() => {
    source.dispatch("run.started", { subject: "RKLB.US", model: "x" });
    source.dispatch("tool.completed", { turn: 0, tool_name: "web_search", ok: true, source_id: "web_1" });
    source.dispatch("tool.completed", { turn: 1, tool_name: "calc", ok: true });
    source.dispatch("tool.completed", { turn: 2, tool_name: "web_search", ok: true, source_id: "web_2" });
  });

  expect(result.current.citationsSeen).toBe(2);
});

it("tracks elapsedSeconds only after run.started and freezes it on a terminal frame", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-05-31T00:00:00Z"));
  try {
    const { result } = renderHook(() => useV3RunStream("run-1"));
    const source = FakeEventSource.instances[0];

    // Before run.started: no measured duration.
    expect(result.current.elapsedSeconds).toBeNull();

    act(() => {
      source.dispatch("run.started", { subject: "RKLB.US", model: "x" });
    });
    act(() => {
      vi.setSystemTime(new Date("2026-05-31T00:00:03Z"));
      vi.advanceTimersByTime(3000);
    });
    expect(result.current.elapsedSeconds).toBeGreaterThanOrEqual(3);

    act(() => {
      vi.setSystemTime(new Date("2026-05-31T00:00:05Z"));
      source.dispatch("run.completed", { section_count: 6, chart_count: 1, citation_count: 5 });
    });
    const frozen = result.current.elapsedSeconds;
    expect(frozen).toBeGreaterThanOrEqual(5);

    // Timer no longer advances once terminal.
    act(() => {
      vi.setSystemTime(new Date("2026-05-31T00:00:09Z"));
      vi.advanceTimersByTime(4000);
    });
    expect(result.current.elapsedSeconds).toBe(frozen);
  } finally {
    vi.useRealTimers();
  }
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run src/components/equity-research-v3/__tests__/useV3RunStream.test.ts`
Expected: FAIL — `citationsSeen` and `elapsedSeconds` are `undefined` on `result.current`.

- [ ] **Step 3: Implement the two fields**

In `useV3RunStream.ts`:

1. Extend the state interface (add two fields after `chartsEmitted`):

```ts
export interface V3StreamState {
  status: V3StreamStatus;
  events: V3Event[];
  sectionsWritten: number;
  chartsEmitted: number;
  citationsSeen: number;
  elapsedSeconds: number | null;
  toolCallsInflight: number;
  terminalMessage: string | null;
  errorMessage: string | null;
  cancel: () => Promise<void>;
}
```

2. Add state + a start-time ref alongside the existing `useState` calls (after `chartsEmitted`):

```ts
const [citationsSeen, setCitationsSeen] = useState(0);
const [elapsedSeconds, setElapsedSeconds] = useState<number | null>(null);
const startedAtRef = useRef<number | null>(null);
```

3. Inside the `useEffect`, in the reset block (where `setEvents([])` etc. run), reset the new state:

```ts
setSectionsWritten(0);
setChartsEmitted(0);
setCitationsSeen(0);
setElapsedSeconds(null);
startedAtRef.current = null;
setToolCallsInflight(0);
```

4. In the frame `handler`, extend the counter branch. Replace the existing `if (type === "tool.called") { ... } else if (type === "tool.completed") { ... }` chain with:

```ts
if (type === "run.started") {
  startedAtRef.current = Date.now();
  setElapsedSeconds(0);
} else if (type === "tool.called") {
  setToolCallsInflight((n) => n + 1);
} else if (type === "tool.completed") {
  setToolCallsInflight((n) => Math.max(0, n - 1));
  if (payload.source_id) setCitationsSeen((n) => n + 1);
} else if (type === "section.written") {
  setSectionsWritten((n) => n + 1);
} else if (type === "chart.emitted") {
  setChartsEmitted((n) => n + 1);
}
```

5. In the terminal branch (inside `if (V3_TERMINAL_EVENT_TYPES.has(type)) { ... }`), freeze the elapsed reading right before `source.close()`:

```ts
if (startedAtRef.current != null) {
  setElapsedSeconds((Date.now() - startedAtRef.current) / 1000);
}
```

6. Add a live-tick effect after the main SSE `useEffect`:

```ts
// Tick the elapsed clock once per second while streaming. The
// terminal handler writes the final value; this only drives the
// live count-up so the generating card's timer moves.
useEffect(() => {
  if (status !== "streaming") return;
  const id = window.setInterval(() => {
    if (startedAtRef.current != null) {
      setElapsedSeconds((Date.now() - startedAtRef.current) / 1000);
    }
  }, 1000);
  return () => window.clearInterval(id);
}, [status]);
```

7. Add both fields to the returned `useMemo` object and its dependency array:

```ts
return useMemo(
  () => ({
    status,
    events,
    sectionsWritten,
    chartsEmitted,
    citationsSeen,
    elapsedSeconds,
    toolCallsInflight,
    terminalMessage,
    errorMessage,
    cancel,
  }),
  [
    cancel,
    chartsEmitted,
    citationsSeen,
    elapsedSeconds,
    errorMessage,
    events,
    sectionsWritten,
    status,
    terminalMessage,
    toolCallsInflight,
  ],
);
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npx vitest run src/components/equity-research-v3/__tests__/useV3RunStream.test.ts`
Expected: PASS (all existing tests + the two new ones).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/equity-research-v3/useV3RunStream.ts frontend/src/components/equity-research-v3/__tests__/useV3RunStream.test.ts
git commit -m "feat(er-v3): add elapsed timer + live citation count to useV3RunStream"
```

---

## Task 2: `V3ActivityFeed` — styled in-card activity timeline

A self-contained presentational component. Renders the most recent ~6 events as a fading timeline, with a "Show all activity" disclosure that expands the full reversed history. Empty state shows "Starting run…". Owns `summarizePayload` (moved out of `V3ChatThread` in Task 4).

**Files:**
- Create: `src/components/equity-research-v3/V3ActivityFeed.tsx`
- Test: `src/components/equity-research-v3/__tests__/V3ActivityFeed.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `__tests__/V3ActivityFeed.test.tsx`:

```tsx
import { describe, expect, test } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type { V3Event } from "../../../api/equity-research-v3";
import { V3ActivityFeed } from "../V3ActivityFeed";

function ev(type: V3Event["type"], payload: Record<string, unknown>): V3Event {
  return { type, payload } as V3Event;
}

describe("V3ActivityFeed", () => {
  test("shows a starting row when there are no events", () => {
    render(<V3ActivityFeed events={[]} />);
    expect(screen.getByTestId("er-v3-activity-feed")).toHaveTextContent("Starting run");
  });

  test("renders the most recent events (newest last) and caps the collapsed view", () => {
    const events: V3Event[] = Array.from({ length: 9 }, (_, i) =>
      ev("section.written", { section_id: `s${i}`, char_count: 100 + i }),
    );
    render(<V3ActivityFeed events={events} />);
    const rows = screen.getAllByTestId("er-v3-activity-row");
    expect(rows.length).toBe(6); // collapsed cap
    // Newest (s8) is present; the oldest (s0) is trimmed from the collapsed view.
    expect(screen.getByText(/s8/)).toBeInTheDocument();
    expect(screen.queryByText(/\bs0\b/)).toBeNull();
  });

  test("'Show all activity' expands to the full history", () => {
    const events: V3Event[] = Array.from({ length: 9 }, (_, i) =>
      ev("section.written", { section_id: `s${i}`, char_count: 100 + i }),
    );
    render(<V3ActivityFeed events={events} />);
    fireEvent.click(screen.getByTestId("er-v3-activity-toggle"));
    expect(screen.getAllByTestId("er-v3-activity-row").length).toBe(9);
    expect(screen.getByText(/\bs0\b/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/components/equity-research-v3/__tests__/V3ActivityFeed.test.tsx`
Expected: FAIL with "Cannot find module '../V3ActivityFeed'".

- [ ] **Step 3: Implement the component**

Create `src/components/equity-research-v3/V3ActivityFeed.tsx`:

```tsx
/**
 * V3ActivityFeed — the in-card activity timeline shown while a v3 run
 * streams. Replaces the old raw StreamPanel event log: it leads with
 * the most recent few events as a quiet mono timeline and offers a
 * "Show all activity" disclosure for the full history.
 */
import { ChevronDown } from "lucide-react";
import { type JSX, useState } from "react";

import type { V3Event } from "../../api/equity-research-v3";

const COLLAPSED_CAP = 6;

export function V3ActivityFeed({ events }: { events: V3Event[] }): JSX.Element {
  const [expanded, setExpanded] = useState(false);

  // Chronological order (oldest -> newest) so the newest row sits at
  // the bottom, nearest the composer, like a chat transcript.
  const ordered = events;
  const visible = expanded ? ordered : ordered.slice(-COLLAPSED_CAP);
  const hiddenCount = ordered.length - visible.length;

  return (
    <div
      data-testid="er-v3-activity-feed"
      className="px-[18px] pb-[14px]"
    >
      {ordered.length === 0 ? (
        <p className="m-0 font-mono text-[11px] text-[--color-text-tertiary]">
          Starting run…
        </p>
      ) : (
        <ol className="m-0 flex list-none flex-col gap-[5px] p-0">
          {visible.map((e, idx) => (
            <li
              key={`${e.type}-${ordered.length - visible.length + idx}`}
              data-testid="er-v3-activity-row"
              className="flex items-baseline gap-[8px] font-mono text-[11px] leading-[1.5] text-[--color-text-secondary] motion-safe:animate-[cardIn_240ms_var(--ease-out)]"
            >
              <span className="text-[--color-feedback-success]">
                {humanizeType(e.type)}
              </span>
              <span className="truncate text-[--color-text-tertiary]">
                {summarizePayload(e)}
              </span>
            </li>
          ))}
        </ol>
      )}

      {ordered.length > COLLAPSED_CAP ? (
        <button
          type="button"
          data-testid="er-v3-activity-toggle"
          onClick={() => setExpanded((v) => !v)}
          className="mt-[8px] inline-flex items-center gap-[4px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary] hover:text-[--color-text-secondary]"
        >
          <ChevronDown
            size={11}
            strokeWidth={2}
            className={expanded ? "rotate-180 transition-transform" : "transition-transform"}
            aria-hidden="true"
          />
          {expanded ? "Show less" : `Show all activity (${hiddenCount} more)`}
        </button>
      ) : null}
    </div>
  );
}

function humanizeType(type: V3Event["type"]): string {
  return type.replace(/\./g, " · ");
}

export function summarizePayload(event: V3Event): string {
  switch (event.type) {
    case "run.started":
      return `${event.payload.subject} — ${event.payload.model}`;
    case "tool.called":
      return `turn ${event.payload.turn} → ${event.payload.tool_name}`;
    case "tool.completed": {
      const ok = event.payload.ok ? "ok" : "error";
      const sid = event.payload.source_id ? ` ${event.payload.source_id}` : "";
      return `turn ${event.payload.turn} ← ${event.payload.tool_name} (${ok})${sid}`;
    }
    case "section.written":
      return `${event.payload.section_id} (${event.payload.char_count ?? "?"} chars)`;
    case "chart.emitted":
      return `${event.payload.chart_id} (${event.payload.chart_type})`;
    case "run.completed":
    case "run.failed":
    case "run.cancelled":
      return `${event.payload.section_count ?? 0} sections · ${event.payload.chart_count ?? 0} charts · ${event.payload.citation_count ?? 0} citations`;
    case "run.snapshot":
      return `prior run status: ${event.payload.status}`;
    default:
      return "";
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/components/equity-research-v3/__tests__/V3ActivityFeed.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/equity-research-v3/V3ActivityFeed.tsx frontend/src/components/equity-research-v3/__tests__/V3ActivityFeed.test.tsx
git commit -m "feat(er-v3): add V3ActivityFeed in-card activity timeline"
```

---

## Task 3: `V3ReportCard` — phase-aware (generating / ready)

Make the card render from the first stream frame and evolve in place. `phase` defaults to `"ready"` and `detail` stays the data source for the ready phase, so the existing tests keep passing. The generating phase pulls header text from new optional props and live data from a `live` object.

**Files:**
- Modify: `src/components/equity-research-v3/V3ReportCard.tsx`
- Test: `src/components/equity-research-v3/__tests__/V3ReportCard.test.tsx`

- [ ] **Step 1: Write the failing tests**

Append to `__tests__/V3ReportCard.test.tsx` (inside the `describe` block). Add this import at the top of the file alongside the existing imports:

```tsx
import type { V3Event } from "../../../api/equity-research-v3";
```

Then the tests:

```tsx
const LIVE = {
  status: "streaming" as const,
  sectionsWritten: 3,
  chartsEmitted: 1,
  citationsSeen: 4,
  elapsedSeconds: 22.4,
  events: [
    { type: "section.written", payload: { section_id: "overview", char_count: 1500 } },
  ] as V3Event[],
  terminalMessage: null,
  errorMessage: null,
};

describe("V3ReportCard — generating phase", () => {
  test("shows a GENERATING pill, the subject, and live counts", () => {
    render(
      <V3ReportCard
        phase="generating"
        subject="AAPL"
        templateLabel="Stock Initiation"
        createdAtIso={null}
        live={LIVE}
      />,
    );
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("er-v3-report-card-generating")).toBeInTheDocument();
    const meta = screen.getByTestId("er-v3-report-card-meta");
    expect(meta).toHaveTextContent("3 sections");
    expect(meta).toHaveTextContent("4 sources");
    expect(meta).toHaveTextContent("Elapsed 22.4s");
  });

  test("renders the activity feed and hides the action row while generating", () => {
    render(
      <V3ReportCard
        phase="generating"
        subject="AAPL"
        templateLabel="Stock Initiation"
        createdAtIso={null}
        live={LIVE}
      />,
    );
    expect(screen.getByTestId("er-v3-activity-feed")).toBeInTheDocument();
    expect(screen.queryByTestId("er-v3-report-card-open")).toBeNull();
  });

  test("shows a FAILED pill and the error message when the stream fails before detail", () => {
    render(
      <V3ReportCard
        phase="generating"
        subject="AAPL"
        templateLabel="Stock Initiation"
        createdAtIso={null}
        live={{ ...LIVE, status: "failed", errorMessage: "stream dropped" }}
      />,
    );
    expect(screen.getByTestId("er-v3-report-card-failed")).toBeInTheDocument();
    expect(screen.getByText("stream dropped")).toBeInTheDocument();
  });

  test("ready phase shows Generated-in time from generatedSeconds", () => {
    render(<V3ReportCard detail={BASE_DETAIL} generatedSeconds={22.4} />);
    expect(screen.getByTestId("er-v3-report-card-meta")).toHaveTextContent(
      "Generated in 22.4s",
    );
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run src/components/equity-research-v3/__tests__/V3ReportCard.test.tsx`
Expected: FAIL — `phase`/`subject`/`live` props not accepted; `er-v3-report-card-generating` not found.

- [ ] **Step 3: Implement the phase-aware card**

Edit `V3ReportCard.tsx`:

1. Extend imports (add `Loader2`, `AlertTriangle` to the lucide import; add the feed + types):

```tsx
import {
  AlertTriangle,
  Clock,
  ExternalLink,
  FileText,
  Globe,
  Image as ImageIcon,
  Layers,
  Loader2,
} from "lucide-react";
import { type JSX } from "react";

import type { V3Event, V3ReportDetail } from "../../api/equity-research-v3";
import { v3HtmlUrl } from "../../api/equity-research-v3";
import { V3ActivityFeed } from "./V3ActivityFeed";
import { ReportDownloadButton } from "../report/ReportDownloadButton";
import { SaveToRepoButton } from "../chat/SaveToRepoButton";
import { useFileViewerOptional } from "../viewer/FileViewerContext";
```

2. Replace the `Props` interface with the phase-aware shape:

```tsx
export type V3CardPhase = "generating" | "ready";

export interface V3CardLive {
  /** Stream status: streaming while running, or a terminal state if
   *  the run failed/cancelled before ``detail`` loaded. */
  status: "streaming" | "completed" | "failed" | "cancelled";
  sectionsWritten: number;
  chartsEmitted: number;
  citationsSeen: number;
  elapsedSeconds: number | null;
  events: V3Event[];
  terminalMessage: string | null;
  errorMessage: string | null;
}

interface Props {
  /** Defaults to "ready" so existing detail-only callers are unchanged. */
  phase?: V3CardPhase;
  /** Header subject. Ready phase falls back to ``detail.report.subject``. */
  subject?: string;
  /** Friendly template label for the meta line. Ready phase falls back
   *  to ``detail.report.template_id``. */
  templateLabel?: string;
  /** ISO date for the meta line. Ready phase falls back to
   *  ``detail.report.created_at``. */
  createdAtIso?: string | null;
  /** Persisted detail — present in the ready phase. */
  detail?: V3ReportDetail | null;
  /** Optional preview text (ready phase). Falls back to first section. */
  preview?: string;
  /** Generation duration in seconds (ready phase meta row). */
  generatedSeconds?: number | null;
  /** Ready-phase: flips the pill to "Revising…" while a revision runs. */
  revising?: boolean;
  /** Pre-populate the Save-to-Repo "Saved" state on first paint. */
  initialSaved?: boolean;
  /** Live stream data — required in the generating phase. */
  live?: V3CardLive;
}
```

3. Replace the component body. The header, meta-row, and action-row become phase-driven. Use this full replacement for the `export function V3ReportCard(...)` body (keep `formatDate` and `deriveFallbackPreview` as-is above it):

```tsx
export function V3ReportCard({
  phase = "ready",
  subject,
  templateLabel,
  createdAtIso,
  detail,
  preview,
  generatedSeconds,
  revising = false,
  initialSaved = false,
  live,
}: Props): JSX.Element {
  const reduce = useReducedMotion();
  const fileViewer = useFileViewerOptional();

  const generating = phase === "generating";
  const headerSubject = detail?.report.subject ?? subject ?? "";
  const headerTemplate = templateLabel ?? detail?.report.template_id ?? "";
  const headerDateIso = detail?.report.created_at ?? createdAtIso ?? null;
  const previewText = detail ? (preview ?? deriveFallbackPreview(detail)) : "";
  const htmlHref = detail ? v3HtmlUrl(detail.report.report_id) : "#";

  const openInViewer = (trigger?: HTMLElement | null) => {
    if (!detail) return;
    if (!fileViewer) {
      window.open(htmlHref, "_blank", "noopener,noreferrer");
      return;
    }
    fileViewer.open({
      filename: detail.report.subject || "Equity Research Report",
      kind: "report",
      metadata: `v3 engine · ${detail.report.template_id}`,
      source: { kind: "v3_report", reportId: detail.report.report_id },
      trigger: trigger ?? null,
    });
  };

  return (
    <motion.article
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      data-testid="er-v3-report-card"
      className="max-w-[640px] overflow-hidden rounded-[12px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-sm"
    >
      <header className="flex items-start gap-3 px-[18px] pt-4 pb-3">
        <div
          aria-hidden="true"
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-[rgba(168,204,0,0.3)] bg-[rgba(212,255,0,0.16)] text-[--color-feedback-success]"
        >
          <FileText size={16} strokeWidth={1.6} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span className="truncate text-[15px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
            {headerSubject}
          </span>
          <span className="flex flex-wrap items-center gap-[5px] truncate font-mono text-[11px] tracking-[0.02em] text-[--color-text-secondary]">
            <span className="truncate">{headerTemplate}</span>
            {headerDateIso ? (
              <>
                <span aria-hidden="true" className="text-[--color-text-tertiary]">·</span>
                <span>{formatDate(headerDateIso)}</span>
              </>
            ) : null}
          </span>
        </div>
        <StatusPill phase={phase} status={live?.status} revising={revising} />
      </header>

      {generating ? (
        <>
          {live?.errorMessage ? (
            <p className="m-0 px-[18px] pb-[10px] text-[12px] text-[--color-feedback-danger]">
              {live.errorMessage}
            </p>
          ) : live?.terminalMessage ? (
            <p className="m-0 px-[18px] pb-[10px] text-[12px] text-[--color-feedback-warning]">
              {live.terminalMessage}
            </p>
          ) : null}
          <V3ActivityFeed events={live?.events ?? []} />
        </>
      ) : previewText ? (
        <p className="m-0 line-clamp-3 px-[18px] pb-[14px] text-[13px] leading-[1.6] text-[--color-text-secondary]">
          {previewText}{" "}
          <button
            type="button"
            onClick={(e) => openInViewer(e.currentTarget)}
            className="font-medium text-[--color-text-primary] hover:text-[--color-feedback-success]"
          >
            Read more
          </button>
        </p>
      ) : null}

      <div
        className="flex flex-wrap gap-[14px] px-[18px] pb-[14px] font-mono text-[10px] tracking-[0.06em] text-[--color-text-tertiary]"
        data-testid="er-v3-report-card-meta"
      >
        <MetaCounts
          generating={generating}
          live={live}
          detail={detail}
          generatedSeconds={generatedSeconds}
        />
      </div>

      {generating ? null : detail ? (
        <div className="flex items-center gap-2 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[18px] py-3">
          <button
            type="button"
            onClick={(e) => openInViewer(e.currentTarget)}
            data-testid="er-v3-report-card-open"
            className="inline-flex h-[30px] items-center gap-[6px] rounded-md bg-[--color-accent-primary] px-3 text-[13px] font-medium text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover]"
          >
            <FileText size={13} strokeWidth={1.7} />
            Open report
          </button>
          <span data-testid="er-v3-report-card-download">
            <ReportDownloadButton
              reportId={detail.report.report_id}
              engine="v3"
              variant="primary"
            />
          </span>
          <span data-testid="er-v3-report-card-save">
            <SaveToRepoButton
              reportId={detail.report.report_id}
              engine="v3"
              initialSaved={initialSaved}
              variant="viewer-header"
            />
          </span>
          <a
            href={htmlHref}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="er-v3-report-card-standalone"
            title="Open the printable HTML in a new tab (use the browser's Save As to grab a Word or PDF copy)"
            className="ml-auto inline-flex h-[30px] items-center gap-[6px] rounded-md px-2 text-[12px] text-[--color-text-tertiary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-secondary]"
          >
            <ExternalLink size={12} strokeWidth={1.7} />
            Standalone
          </a>
        </div>
      ) : null}
    </motion.article>
  );
}

function MetaCounts({
  generating,
  live,
  detail,
  generatedSeconds,
}: {
  generating: boolean;
  live?: V3CardLive;
  detail?: V3ReportDetail | null;
  generatedSeconds?: number | null;
}): JSX.Element {
  const sections = generating ? (live?.sectionsWritten ?? 0) : (detail?.sections.length ?? 0);
  const charts = generating ? (live?.chartsEmitted ?? 0) : (detail?.charts.length ?? 0);
  const sources = generating ? (live?.citationsSeen ?? 0) : (detail?.citations.length ?? 0);
  const elapsed = generating ? (live?.elapsedSeconds ?? null) : (generatedSeconds ?? null);

  return (
    <>
      {sections > 0 ? (
        <span className="inline-flex items-center gap-[5px]">
          <Layers size={11} strokeWidth={1.6} />
          {sections} section{sections === 1 ? "" : "s"}
        </span>
      ) : null}
      {charts > 0 ? (
        <span className="inline-flex items-center gap-[5px]">
          <ImageIcon size={11} strokeWidth={1.6} />
          {charts} chart{charts === 1 ? "" : "s"}
        </span>
      ) : null}
      {sources > 0 ? (
        <span className="inline-flex items-center gap-[5px]">
          <Globe size={11} strokeWidth={1.6} />
          {sources} source{sources === 1 ? "" : "s"}
        </span>
      ) : null}
      {elapsed != null ? (
        <span className="inline-flex items-center gap-[5px]">
          <Clock size={11} strokeWidth={1.6} />
          {generating ? `Elapsed ${elapsed.toFixed(1)}s` : `Generated in ${elapsed.toFixed(1)}s`}
        </span>
      ) : null}
    </>
  );
}
```

4. Replace the `StatusPill` function with the phase/status-aware version:

```tsx
function StatusPill({
  phase,
  status,
  revising,
}: {
  phase: V3CardPhase;
  status?: V3CardLive["status"];
  revising: boolean;
}): JSX.Element {
  const base =
    "inline-flex flex-shrink-0 items-center gap-[5px] self-start rounded-full border px-2 py-[3px] font-mono text-[9px] uppercase tracking-[0.1em]";

  if (phase === "generating") {
    if (status === "failed") {
      return (
        <span
          data-testid="er-v3-report-card-failed"
          className={`${base} border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] text-[--color-feedback-danger]`}
        >
          <AlertTriangle size={10} strokeWidth={2} aria-hidden="true" />
          Failed
        </span>
      );
    }
    if (status === "cancelled") {
      return (
        <span
          data-testid="er-v3-report-card-cancelled"
          className={`${base} border-[--color-feedback-warning] bg-[rgba(255,180,0,0.08)] text-[--color-feedback-warning]`}
        >
          Cancelled
        </span>
      );
    }
    return (
      <span
        data-testid="er-v3-report-card-generating"
        className={`${base} border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] text-[--color-feedback-success]`}
      >
        <Loader2 size={10} strokeWidth={2.2} className="motion-safe:animate-spin" aria-hidden="true" />
        Generating
      </span>
    );
  }

  if (revising) {
    return (
      <span
        data-testid="er-v3-report-card-revising"
        className={`${base} border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-secondary]`}
      >
        <span aria-hidden="true" className="h-[5px] w-[5px] animate-pulse rounded-full bg-[--color-text-secondary]" />
        Revising
      </span>
    );
  }

  return (
    <span
      data-testid="er-v3-report-card-ready"
      className={`${base} border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] text-[--color-feedback-success]`}
    >
      <span
        aria-hidden="true"
        className="h-[5px] w-[5px] rounded-full bg-[--color-feedback-success] shadow-[0_0_4px_rgba(168,204,0,0.7)]"
      />
      Ready
    </span>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npx vitest run src/components/equity-research-v3/__tests__/V3ReportCard.test.tsx`
Expected: PASS — both the original ready-phase tests and the new generating-phase tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/equity-research-v3/V3ReportCard.tsx frontend/src/components/equity-research-v3/__tests__/V3ReportCard.test.tsx
git commit -m "feat(er-v3): make V3ReportCard phase-aware (generating + ready)"
```

---

## Task 4: `V3ChatThread` — render the phase-aware card from the first frame

Replace the StreamPanel↔card swap with one card that morphs. Widen the `stream` prop to carry `citationsSeen` + `elapsedSeconds`, delete `StreamPanel`/`StatusBadge`/`Chip`/`summarizePayload` (now in the feed).

**Files:**
- Modify: `src/components/equity-research-v3/V3ChatThread.tsx`
- Test: `src/components/equity-research-v3/__tests__/V3ChatThread.test.tsx`

- [ ] **Step 1: Read the existing thread test**

Run: `sed -n '1,80p' src/components/equity-research-v3/__tests__/V3ChatThread.test.tsx`
Note any assertions that reference `er-v3-stream-panel`, "Live activity", "Sections written", or the counter `Chip`s — these move to the card in Step 5.

- [ ] **Step 2: Write/adjust the failing test**

In `__tests__/V3ChatThread.test.tsx`, ensure a test asserts the generating card renders while streaming (no detail). Add this test (and, if present, delete or rewrite any test asserting `er-v3-stream-panel`):

```tsx
test("renders the generating report card while the run streams", () => {
  render(
    <V3ChatThread
      initialPrompt="Initiate coverage on AAPL"
      initialSettings={{
        templateName: "Stock Initiation",
        length: "normal",
        language: "en",
        reasoningEffort: "medium",
        modelLabel: "Claude Sonnet",
      }}
      reportId="run-1"
      stream={{
        status: "streaming",
        events: [],
        sectionsWritten: 2,
        chartsEmitted: 0,
        citationsSeen: 1,
        elapsedSeconds: 4.2,
        toolCallsInflight: 1,
        terminalMessage: null,
        errorMessage: null,
      }}
      detail={null}
      onRefreshDetail={() => undefined}
    />,
  );
  expect(screen.getByTestId("er-v3-report-card-generating")).toBeInTheDocument();
  expect(screen.getByText("Initiate coverage on AAPL")).toBeInTheDocument();
});
```

If the existing test file mocks `listV3Revisions`, keep that mock; the thread still polls revisions. Match the file's existing mock setup (see Step 1).

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run src/components/equity-research-v3/__tests__/V3ChatThread.test.tsx`
Expected: FAIL — `citationsSeen`/`elapsedSeconds` not allowed on `stream`, and no `er-v3-report-card-generating` (StreamPanel renders instead).

- [ ] **Step 4: Widen the `stream` prop type**

In `V3ChatThread.tsx`, update the `Props.stream` shape:

```ts
stream: {
  status: string;
  events: V3Event[];
  sectionsWritten: number;
  chartsEmitted: number;
  citationsSeen: number;
  elapsedSeconds: number | null;
  toolCallsInflight: number;
  terminalMessage: string | null;
  errorMessage: string | null;
};
```

- [ ] **Step 5: Replace the system turn + delete the dead sub-components**

Replace the `<SystemTurn>...</SystemTurn>` block (the `{detail ? <V3ReportCard ... /> : <StreamPanel ... />}`) with a single phase-aware card:

```tsx
{/* --- Initial system turn ----------------------------------- */}
<SystemTurn>
  <V3ReportCard
    phase={detail ? "ready" : "generating"}
    subject={promptText}
    templateLabel={settings?.templateName ?? ""}
    createdAtIso={detail?.report.created_at ?? null}
    detail={detail}
    generatedSeconds={detail ? stream.elapsedSeconds : undefined}
    revising={revisions?.some((r) => !isTerminal(r.status)) ?? false}
    live={{
      status: stream.status as "streaming" | "completed" | "failed" | "cancelled",
      sectionsWritten: stream.sectionsWritten,
      chartsEmitted: stream.chartsEmitted,
      citationsSeen: stream.citationsSeen,
      elapsedSeconds: stream.elapsedSeconds,
      events: stream.events,
      terminalMessage: stream.terminalMessage,
      errorMessage: stream.errorMessage,
    }}
  />
</SystemTurn>
```

Then delete these now-unused functions from the file: `StreamPanel`, `StatusBadge`, `Chip`, and `summarizePayload`. Remove the now-unused lucide import (none of `StreamPanel`'s icons were imported there — verify after deletion). Keep `AlertTriangle`, `Check`, `Loader2`, `User as UserIcon` if still referenced by `RevisionStatusBadge`/`UserMessage` (they are).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npx vitest run src/components/equity-research-v3/__tests__/V3ChatThread.test.tsx`
Expected: PASS.

- [ ] **Step 7: Typecheck the touched module set**

Run: `npx tsc --noEmit`
Expected: no errors. (If `V3Event` is now unused in `V3ChatThread.tsx`, keep it only if referenced by the `stream` type — it is.)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/equity-research-v3/V3ChatThread.tsx frontend/src/components/equity-research-v3/__tests__/V3ChatThread.test.tsx
git commit -m "feat(er-v3): render phase-aware card from first stream frame; retire StreamPanel"
```

---

## Task 5: `ErComposer` — generating affordance on the mode pill

While `isStreaming`, the mode pill's dot pulses and the label reads as generating. Stop button and submit-gating are unchanged (the page already keeps Stop and never hard-locks the textarea).

**Files:**
- Modify: `src/components/equity-research/ErComposer.tsx`
- Test: `src/components/equity-research/__tests__/ErComposer.generating.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `src/components/equity-research/__tests__/ErComposer.generating.test.tsx`:

```tsx
import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { ErComposer } from "../ErComposer";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, d?: unknown) => (typeof d === "string" ? d : k) }),
}));

const BASE = {
  value: "",
  onChange: () => undefined,
  onSubmit: () => undefined,
  onStop: vi.fn(),
  placeholder: "Run in progress…",
  mode: "stock_initiation" as const,
  length: "normal" as const,
  onModeClick: () => undefined,
  templateLabel: "Stock Initiation",
};

describe("ErComposer generating affordance", () => {
  test("shows the Stop button and the generating mode-pill marker while streaming", () => {
    render(<ErComposer {...BASE} isStreaming />);
    expect(screen.getByLabelText("chat.aria_stop_generating")).toBeInTheDocument();
    expect(screen.getByTestId("er-composer-mode-pill")).toHaveAttribute(
      "data-generating",
      "true",
    );
  });

  test("mode pill is not marked generating when idle", () => {
    render(<ErComposer {...BASE} isStreaming={false} />);
    expect(screen.getByTestId("er-composer-mode-pill")).toHaveAttribute(
      "data-generating",
      "false",
    );
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/components/equity-research/__tests__/ErComposer.generating.test.tsx`
Expected: FAIL — `er-composer-mode-pill` testid not found.

- [ ] **Step 3: Add the marker + generating styling to the mode pill**

In `ErComposer.tsx`, edit the mode-pill `<button>` (the one with `onClick={onModeClick}`). Add a `data-testid`, a `data-generating` attribute, and a conditional pulse on the dot:

```tsx
<button
  type="button"
  onClick={onModeClick}
  data-testid="er-composer-mode-pill"
  data-generating={isStreaming ? "true" : "false"}
  aria-label={t("equity_research.change_mode_aria")}
  className="inline-flex items-center gap-2 rounded-full border border-[--color-border-subtle] bg-[--color-bg-base] py-[5px] pl-2 pr-[10px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
>
  <span
    aria-hidden="true"
    className={
      isStreaming
        ? "h-1.5 w-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_5px_rgba(212,255,0,0.6)] motion-safe:animate-pulse"
        : "h-1.5 w-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_5px_rgba(212,255,0,0.6)]"
    }
  />
  <strong className="font-medium tracking-[0.06em] text-[--color-text-primary]">
    {isStreaming ? "Generating" : (templateLabel ?? t(MODE_KEY[mode]))}
  </strong>
  <span className="text-[--color-text-tertiary]">·</span>
  <span>{t(LENGTH_KEY[length])}</span>
  <ChevronDown size={10} strokeWidth={2} className="opacity-70" aria-hidden="true" />
</button>
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/components/equity-research/__tests__/ErComposer.generating.test.tsx`
Expected: PASS.

- [ ] **Step 5: Guard against regressions in the existing composer test**

Run: `npx vitest run src/components/equity-research/__tests__/ErComposer.attachments.test.tsx`
Expected: PASS (no behavior change to attachments/submit).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/equity-research/ErComposer.tsx frontend/src/components/equity-research/__tests__/ErComposer.generating.test.tsx
git commit -m "feat(er-v3): generating affordance on the composer mode pill"
```

---

## Task 6: TopBar generating pill via the chat-header registry

Surface a `GENERATING` pill in the shared TopBar while a run streams, reusing the existing `LivePill`. Additive registry field; other departments unaffected.

**Files:**
- Modify: `src/layouts/ChatHeaderContext.tsx`
- Modify: `src/components/shell/TopBar.tsx`
- Test: `src/components/shell/__tests__/TopBar.generating.test.tsx` (create; if a `__tests__` dir doesn't exist under `shell/`, create it)

- [ ] **Step 1: Add the registry field**

In `ChatHeaderContext.tsx`, add to the `ChatHeaderValue` interface (after `renderPopover`):

```ts
  /** When true, the TopBar renders a GENERATING pill. ER v3 sets this
   *  while a run streams so the page-level generating state is visible
   *  in the shell chrome. */
  generating?: boolean;
```

- [ ] **Step 2: Write the failing test**

Create `src/components/shell/__tests__/TopBar.generating.test.tsx`:

```tsx
import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { TopBar } from "../TopBar";
import { ChatHeaderRegistryTestHarness } from "./_chatHeaderHarness";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, o?: { defaultValue?: string }) => o?.defaultValue ?? k }),
}));

describe("TopBar generating pill", () => {
  test("renders a GENERATING pill when the chat header reports generating", () => {
    render(
      <ChatHeaderRegistryTestHarness
        value={{
          departmentId: "equity_research_v3",
          activeSessionId: "run-1",
          chatTitle: "AAPL",
          onSelect: () => undefined,
          onCreate: () => undefined,
          generating: true,
        }}
      >
        <TopBar crumbs={["Equity Research"]} />
      </ChatHeaderRegistryTestHarness>,
    );
    expect(screen.getByText("GENERATING")).toBeInTheDocument();
  });
});
```

Create the harness `src/components/shell/__tests__/_chatHeaderHarness.tsx`:

```tsx
import type { JSX, ReactNode } from "react";

import { ChatHeaderProvider, useChatHeaderRegistry, type ChatHeaderValue } from "../../../layouts/ChatHeaderContext";

function Register({ value, children }: { value: ChatHeaderValue; children: ReactNode }): JSX.Element {
  const { register } = useChatHeaderRegistry();
  // Register synchronously on first render so TopBar (a sibling) sees it.
  register(value);
  return <>{children}</>;
}

export function ChatHeaderRegistryTestHarness({
  value,
  children,
}: {
  value: ChatHeaderValue;
  children: ReactNode;
}): JSX.Element {
  return (
    <ChatHeaderProvider>
      <Register value={value}>{children}</Register>
    </ChatHeaderProvider>
  );
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run src/components/shell/__tests__/TopBar.generating.test.tsx`
Expected: FAIL — no "GENERATING" text rendered.

- [ ] **Step 4: Render the pill in TopBar**

In `TopBar.tsx`, in the right-hand cluster (the `<div className="ml-auto ...">`), render the generating pill before the existing `{live && <LivePill />}`:

```tsx
<div className="ml-auto flex items-center gap-[14px]">
  {chatHeader?.generating ? <LivePill label="GENERATING" /> : null}
  {live && <LivePill />}
  {chatHeader ? (
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run src/components/shell/__tests__/TopBar.generating.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/layouts/ChatHeaderContext.tsx frontend/src/components/shell/TopBar.tsx frontend/src/components/shell/__tests__/
git commit -m "feat(er-v3): GENERATING pill in TopBar via chat-header registry"
```

---

## Task 7: Page wiring — pass live fields, publish `generating`

Wire the new stream fields into `V3ChatThread`, publish `generating` to the registry, so Tasks 4 + 6 light up end-to-end.

**Files:**
- Modify: `src/pages/departments/EquityResearchV3.tsx`

- [ ] **Step 1: Pass the new stream fields into the thread**

In the `<V3ChatThread ... stream={{ ... }} />` block, add the two fields:

```tsx
stream={{
  status: stream.status,
  events: stream.events,
  sectionsWritten: stream.sectionsWritten,
  chartsEmitted: stream.chartsEmitted,
  citationsSeen: stream.citationsSeen,
  elapsedSeconds: stream.elapsedSeconds,
  toolCallsInflight: stream.toolCallsInflight,
  terminalMessage: stream.terminalMessage,
  errorMessage: stream.errorMessage,
}}
```

- [ ] **Step 2: Publish `generating` to the chat-header registry**

In the `register({ ... })` call, add `generating: isStreaming`, and add `isStreaming` to that effect's dependency array:

```tsx
register({
  departmentId: "equity_research_v3",
  activeSessionId: activeReportId,
  chatTitle: activeSubject ?? "New chat",
  onSelect: handleSelectRun,
  onCreate: handleNewRun,
  generating: isStreaming,
  renderPopover: (props) => (
    <V3RunsPopover
      activeSessionId={props.activeSessionId}
      onSelect={props.onSelect}
      onActiveDeleted={props.onActiveDeleted}
      onClose={props.onClose}
    />
  ),
});
```

And the dependency array:

```tsx
}, [
  activeReportId,
  activeSubject,
  clear,
  handleNewRun,
  handleSelectRun,
  isStreaming,
  register,
]);
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/departments/EquityResearchV3.tsx
git commit -m "feat(er-v3): wire live stream fields + generating pill into the page"
```

---

## Task 8: Motion choreography — `motion-shell.css` + shell hooks + page opt-in

Port the mockup's `om-anim` entrance system as a global stylesheet keyed off opt-in data attributes, add the hooks to the shared shell, and toggle the opt-in from the ER v3 page.

**Files:**
- Create: `src/styles/motion-shell.css`
- Modify: `src/styles/global.css`
- Modify: `src/layouts/AppLayout.tsx`
- Modify: `src/components/sidebar/Sidebar.tsx`
- Modify: `src/pages/departments/EquityResearchV3.tsx`
- Test: `src/pages/departments/__tests__/EquityResearchV3.motion.test.tsx` (create; if no `__tests__` dir under `pages/departments/`, create it)

- [ ] **Step 1: Create the choreography stylesheet**

Create `src/styles/motion-shell.css`:

```css
/* ============================================================
   motion-shell.css — opt-in entrance choreography for the
   standard app shell (sidebar / topbar / content). A page opts
   in by adding ``om-anim`` to <html> and ``data-om-auto`` to
   <body>; shell elements are tagged with ``data-om-shell``.
   Ported from the Equity Research generating mockup.
   ============================================================ */
@keyframes om-side-in    { from { opacity: 0; transform: translate3d(-22px,0,0); } to { opacity: 1; transform: none; } }
@keyframes om-bar-rise   { from { opacity: 0; transform: translate3d(0,-8px,0); }  to { opacity: 1; transform: none; } }
@keyframes om-content-in { from { opacity: 0; transform: translate3d(8px,0,0); }   to { opacity: 1; transform: none; } }
@keyframes om-fade-up    { from { opacity: 0; transform: translate3d(0,12px,0); }  to { opacity: 1; transform: none; } }
/* Used by V3ActivityFeed rows (Task 2) and any in-card reveal. Defined
   here, globally, because Tailwind's animate-[cardIn_...] arbitrary
   value emits ``animation: cardIn ...`` that needs a global keyframe. */
@keyframes cardIn        { from { opacity: 0; transform: translateY(8px); }         to { opacity: 1; transform: translateY(0); } }

html.om-anim body[data-om-auto] [data-om-shell="sidebar"] {
  animation: om-side-in 420ms var(--ease-out) both;
  will-change: transform, opacity;
}

html.om-anim body[data-om-auto] [data-om-shell="topbar"] {
  animation: om-bar-rise 340ms var(--ease-out) both;
  animation-delay: 120ms;
}

html.om-anim body[data-om-auto] [data-om-shell="content"] {
  animation: om-content-in 360ms var(--ease-out) both;
  animation-delay: 160ms;
}

/* Direct children of the content region cascade in. */
html.om-anim body[data-om-auto] [data-om-shell="content"] > * {
  animation: om-fade-up 440ms var(--ease-out) both;
}
html.om-anim body[data-om-auto] [data-om-shell="content"] > *:nth-child(1) { animation-delay: 260ms; }
html.om-anim body[data-om-auto] [data-om-shell="content"] > *:nth-child(2) { animation-delay: 340ms; }
html.om-anim body[data-om-auto] [data-om-shell="content"] > *:nth-child(3) { animation-delay: 420ms; }
html.om-anim body[data-om-auto] [data-om-shell="content"] > *:nth-child(n+4) { animation-delay: 500ms; }

@media (prefers-reduced-motion: reduce) {
  html.om-anim body[data-om-auto] [data-om-shell="sidebar"],
  html.om-anim body[data-om-auto] [data-om-shell="topbar"],
  html.om-anim body[data-om-auto] [data-om-shell="content"],
  html.om-anim body[data-om-auto] [data-om-shell="content"] > * {
    animation: none !important;
  }
}
```

(If `--ease-out` is not defined in `tokens.css`, substitute `cubic-bezier(0.22, 1, 0.36, 1)`. Verify with `grep -n "\-\-ease-out" src/styles/tokens.css` and adjust before committing.)

- [ ] **Step 2: Import it from global.css**

In `src/styles/global.css`, add after the existing `@import "./report/layout.css";` line:

```css
@import "./motion-shell.css";
```

- [ ] **Step 3: Tag the shell elements**

In `src/layouts/AppLayout.tsx`, add `data-om-shell="topbar"` to the `<header>` (line ~73) and `data-om-shell="content"` to the `<main>` (line ~80):

```tsx
        <header data-om-shell="topbar">
          <TopBar
            crumbs={crumbs}
            stamps={stampsForNow()}
            live={pathname.startsWith("/morning-briefing")}
          />
        </header>
        <main
          id="main"
          data-om-shell="content"
          tabIndex={-1}
          className="flex overflow-y-auto pb-14 md:pb-0"
          style={{ scrollbarGutter: "stable" }}
        >
```

In `src/components/sidebar/Sidebar.tsx`, add `data-om-shell="sidebar"` to the root `<nav>` (line ~51):

```tsx
    <nav
      aria-label={t("nav.main_navigation")}
      data-om-shell="sidebar"
      className={[
```

- [ ] **Step 4: Write the failing page test**

Create `src/pages/departments/__tests__/EquityResearchV3.motion.test.tsx`:

```tsx
import { describe, expect, test } from "vitest";
import { renderHook } from "@testing-library/react";

import { useOmEntranceChoreography } from "../EquityResearchV3";

describe("om-anim entrance opt-in", () => {
  test("adds om-anim/data-om-auto on mount and removes them on unmount", () => {
    const { unmount } = renderHook(() => useOmEntranceChoreography());
    expect(document.documentElement.classList.contains("om-anim")).toBe(true);
    expect(document.body.hasAttribute("data-om-auto")).toBe(true);
    unmount();
    expect(document.documentElement.classList.contains("om-anim")).toBe(false);
    expect(document.body.hasAttribute("data-om-auto")).toBe(false);
  });
});
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `npx vitest run src/pages/departments/__tests__/EquityResearchV3.motion.test.tsx`
Expected: FAIL — `useOmEntranceChoreography` is not exported.

- [ ] **Step 6: Implement + call the opt-in hook**

In `EquityResearchV3.tsx`, add an exported hook above the default export component:

```tsx
/** Opts the page into the shell entrance choreography (see
 *  motion-shell.css). Exported for testing. */
export function useOmEntranceChoreography(): void {
  useEffect(() => {
    const root = document.documentElement;
    root.classList.add("om-anim");
    document.body.setAttribute("data-om-auto", "");
    return () => {
      root.classList.remove("om-anim");
      document.body.removeAttribute("data-om-auto");
    };
  }, []);
}
```

Then call it once at the top of the `EquityResearchV3` component body (after the `useAuth()`/`useSearchParams()` lines):

```tsx
  useOmEntranceChoreography();
```

Ensure `useEffect` is imported (it already is via the existing `import { type JSX, useCallback, useEffect, useState }`).

- [ ] **Step 7: Run the test to verify it passes**

Run: `npx vitest run src/pages/departments/__tests__/EquityResearchV3.motion.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/styles/motion-shell.css frontend/src/styles/global.css frontend/src/layouts/AppLayout.tsx frontend/src/components/sidebar/Sidebar.tsx frontend/src/pages/departments/EquityResearchV3.tsx frontend/src/pages/departments/__tests__/EquityResearchV3.motion.test.tsx
git commit -m "feat(er-v3): port om-anim entrance choreography (opt-in shell hooks)"
```

---

## Task 9: Integration verification

**Files:** none (verification only)

- [ ] **Step 1: Full frontend test suite**

Run: `npx vitest run`
Expected: PASS, no new failures. (Pre-existing `SettingsShellBlocker` unhandled-rejection noise is unrelated — confirm the count of failures is not higher than on `main`.)

- [ ] **Step 2: Typecheck + production build**

Run: `npm run build`
Expected: build succeeds, 0 TypeScript errors.

- [ ] **Step 3: Manual browser pass**

Start the app (backend on :8080, Vite on :5173) and open `/equity-research`. Confirm:
- Entrance choreography plays once (sidebar slides, topbar rises, content cascades).
- Submitting a report shows the card immediately with a pulsing `GENERATING` pill.
- Meta-row counts (sections / sources) tick up; `Elapsed Xs` increments.
- The activity feed shows recent events; "Show all activity" expands the full log.
- TopBar shows the `GENERATING` pill; composer mode pill pulses and reads "Generating"; Stop is present and cancels.
- On completion the same card flips to `READY`, shows `Generated in Xs`, the exec-summary preview + "Read more", and the Open / Download / Save action row — with no card remount/flash.
- Toggle OS "Reduce motion" and reload: no entrance animation, no pulsing/spinning; content appears in final state immediately.

- [ ] **Step 4: Final commit (if any manual-pass fixes were needed)**

```bash
git add -A
git commit -m "fix(er-v3): generation UI polish — manual-pass adjustments"
```

---

## Self-Review Notes

- **Spec coverage:** §1 one-evolving-card → Tasks 3–4; §2 status pill / live meta / activity feed → Tasks 2–3; §3 composer → Task 5; §4 topbar → Task 6; §5 motion → Task 8; §6 welcome/finished card → finished card covered by Task 3, WelcomeStage confirmed no-change (verified in Task 9 manual pass). Activity-log "integrate, don't drop" → Task 2 feed + disclosure.
- **Backward compatibility:** `V3ReportCard.phase` defaults to `"ready"` and `detail` remains the ready-phase data source, so the original `V3ReportCard` tests pass unchanged.
- **Type consistency:** `V3CardLive`/`V3CardPhase` (Task 3) match the `live` object built in `V3ChatThread` (Task 4) and the `stream` fields added in `useV3RunStream` (Task 1: `citationsSeen`, `elapsedSeconds`). `summarizePayload` is defined once (Task 2) and removed from `V3ChatThread` (Task 4).
- **No engine changes:** all live data comes from existing SSE event types; `citationsSeen` derives from `tool.completed.source_id` already present in the stream.
