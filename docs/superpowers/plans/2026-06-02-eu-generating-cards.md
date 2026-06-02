# Earnings Update — Generating Card + Card Highlights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the bare "Generating" pill with a rich generating card, and populate the Earnings Update feed cards with the cover highlights (thesis subtitle, metric chips, rating) the engine already produces.

**Architecture:** Backend adds a compact `highlights` field to the feed's `RunSummaryOut`, derived from the already-loaded `ReportEu.cover_json` (no migration, no new query). Frontend adds a pure `deriveEuPhase` helper + a dedicated `EuGeneratingCard` driven by the existing SSE stream, and renders shared `MetricChip`/`RatingPill` bits on `EuBigCard` and `EuReportRow`. All highlights degrade gracefully when a report has no cover.

**Tech Stack:** Python / FastAPI / Pydantic / SQLAlchemy (server); React / TypeScript / Tailwind / Vitest / react-i18next (frontend).

**Spec:** `docs/superpowers/specs/2026-06-02-eu-generating-cards-design.md`

**Conventions verified:**
- Backend tests: `uv run pytest <path>` from repo root. Frontend tests: `npx vitest run <path>` from `frontend/`. Frontend type-check: `cd frontend && npm run lint` (alias for `tsc --noEmit`).
- Frontend tests initialize the real English i18n bundle (`src/setupTests.ts`), so `t()` returns real English text — assert against the English strings added in Task 3.
- `useEuRunStream` returns `EuStreamState` (exported from `frontend/src/hooks/useEuRunStream.ts`); `CoverMetric` is already exported from `frontend/src/api/earnings-update.ts`.
- CSS tokens in use already include `--color-accent-primary`, `--color-accent-primary-rgb`, `--color-accent-subtle`, `--color-surface-active`, `--color-surface-hover`, `--color-border-subtle`, `--color-border-strong`, `--color-feedback-success`, `--color-feedback-error`, `--duration-normal`.

---

### Task 1: Backend — `highlights` on the feed payload

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py`
- Test: `packages/server/tests/test_routes/departments/test_earnings_update_v2_highlights.py` (create)

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_routes/departments/test_earnings_update_v2_highlights.py`:

```python
"""Unit tests for the feed summary's `highlights` derivation.

Calls the route module's `_summary` helper directly with an in-memory
`ReportEu` row (no DB session needed) to verify cover_json is projected
into a compact, capped highlights payload.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from openlia_server.db.models.report_eu import ReportEu
from openlia_server.routes.departments import earnings_update_v2 as eu


def _row(cover_json: str | None) -> ReportEu:
    return ReportEu(
        id="r1",
        user_id="local",
        subject="Apple - Q2 beat",
        ticker="AAPL",
        trigger_kind="on_demand",
        fiscal_date="2026-03-31",
        template_id="default",
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="claude",
        status="completed",
        created_at=datetime.now(UTC),
        completed_at=None,
        cover_json=cover_json,
        reasoning_effort=None,
    )


def test_summary_highlights_populated_and_capped() -> None:
    cover = json.dumps(
        {
            "subtitle": "Beat on Services",
            "rating": "Buy",
            "key_metrics": [
                {"label": "Revenue", "value": "$94.2B", "change": "+5.4%", "tone": "positive"},
                {"label": "EPS", "value": "$1.78", "change": "+3.5%", "tone": "positive"},
                {"label": "Services", "value": "$26.8B", "change": "+15.2%", "tone": "positive"},
                {"label": "GM", "value": "46.2%", "change": None, "tone": "neutral"},
                {"label": "Extra", "value": "x", "change": None, "tone": None},
            ],
        }
    )
    out = eu._summary(_row(cover))
    assert out.highlights is not None
    assert out.highlights.subtitle == "Beat on Services"
    assert out.highlights.rating == "Buy"
    assert len(out.highlights.metrics) == 4  # capped at 4
    assert out.highlights.metrics[0].value == "$94.2B"
    assert out.highlights.metrics[0].tone == "positive"


def test_summary_highlights_none_without_cover() -> None:
    assert eu._summary(_row(None)).highlights is None


def test_summary_highlights_none_when_cover_has_no_usable_content() -> None:
    assert eu._summary(_row(json.dumps({"tldr": ["x"]}))).highlights is None


def test_summary_highlights_none_on_invalid_json() -> None:
    assert eu._summary(_row("not json")).highlights is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_highlights.py -v`
Expected: FAIL — `AttributeError: 'RunSummaryOut' object has no attribute 'highlights'`.

- [ ] **Step 3: Add `CardHighlightsOut`, the `highlights` field, and the derivation helper**

In `earnings_update_v2.py`, add `CardHighlightsOut` directly after the existing `CoverOut` class (it reuses `CoverMetricOut`):

```python
class CardHighlightsOut(BaseModel):
    subtitle: str | None = None
    rating: str | None = None
    metrics: list[CoverMetricOut] = Field(default_factory=list)
```

Add the `highlights` field to `RunSummaryOut` (after `reasoning_effort`):

```python
    reasoning_effort: str | None = None
    highlights: "CardHighlightsOut | None" = None
```

Add `_card_highlights` directly after the existing `_cover_out` helper (reuses its tolerant parse):

```python
def _card_highlights(raw: str | None) -> CardHighlightsOut | None:
    cover = _cover_out(raw)
    if cover is None:
        return None
    metrics = cover.key_metrics[:4]
    if not (cover.subtitle or cover.rating or metrics):
        return None
    return CardHighlightsOut(
        subtitle=cover.subtitle,
        rating=cover.rating,
        metrics=metrics,
    )
```

Wire it into `_summary` (add the final field):

```python
def _summary(row: ReportEu) -> RunSummaryOut:
    return RunSummaryOut(
        report_id=row.id,
        subject=row.subject,
        ticker=row.ticker,
        trigger_kind=row.trigger_kind,
        fiscal_date=row.fiscal_date,
        template_id=row.template_id,
        language=row.language,
        length=row.length,
        status=row.status,
        created_at=row.created_at,
        completed_at=row.completed_at,
        reasoning_effort=row.reasoning_effort,
        highlights=_card_highlights(row.cover_json),
    )
```

Note: `CardHighlightsOut` is defined after `CoverOut` but referenced as a string annotation in `RunSummaryOut` (which is defined earlier in the file). Pydantic v2 resolves the forward ref at class build; if the run order in the file places `RunSummaryOut` before `CardHighlightsOut`, the string annotation + `model_rebuild()` is unnecessary because both are module-level by import time. If a `PydanticUndefinedAnnotation` error appears, add `RunSummaryOut.model_rebuild()` immediately after `CardHighlightsOut` is defined.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_highlights.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the existing EU route tests to confirm no regression**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py -q`
Expected: PASS (all existing tests green).

- [ ] **Step 6: Lint**

Run: `uv run ruff check packages/server/src/openlia_server/routes/departments/earnings_update_v2.py packages/server/tests/test_routes/departments/test_earnings_update_v2_highlights.py`
Expected: no errors. (If import-order errors appear, run `uv run ruff check --fix <paths>`.)

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/earnings_update_v2.py packages/server/tests/test_routes/departments/test_earnings_update_v2_highlights.py
git commit -m "feat(eu): surface cover highlights on the feed summary payload"
```

---

### Task 2: Frontend — `CardHighlights` type on `RunSummary`

**Files:**
- Modify: `frontend/src/api/earnings-update.ts`

- [ ] **Step 1: Add the type and field**

In `frontend/src/api/earnings-update.ts`, add `CardHighlights` immediately after the existing `CoverMetric` interface (around line 143):

```ts
export interface CardHighlights {
  subtitle: string | null;
  rating: string | null;
  metrics: CoverMetric[];
}
```

Add the field to `RunSummary` (after `reasoning_effort`):

```ts
  reasoning_effort: ReasoningEffort;
  highlights?: CardHighlights | null;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run lint`
Expected: exit 0 (no type errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/earnings-update.ts
git commit -m "feat(eu): add CardHighlights type to RunSummary"
```

---

### Task 3: i18n — generating-card strings (both locales)

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Add the `gen` block to English**

In `frontend/src/i18n/locales/en.json`, inside the `earnings.feed` object, add a `gen` sub-object (place it after the existing `generating` key):

```json
    "gen": {
      "badge": "Generating Update",
      "title_fallback": "{{ticker}} — Earnings Update",
      "cancel": "Cancel",
      "elapsed_aria": "Time elapsed",
      "phase_connect": "Connecting to data sources",
      "phase_research": "Reading the release",
      "phase_write": "Writing the update",
      "phase_finalize": "Finalizing"
    },
```

- [ ] **Step 2: Add the matching `gen` block to Traditional Chinese**

In `frontend/src/i18n/locales/zh-TW.json`, inside `earnings.feed`, add:

```json
    "gen": {
      "badge": "正在生成更新",
      "title_fallback": "{{ticker}} — 財報更新",
      "cancel": "取消",
      "elapsed_aria": "已用時間",
      "phase_connect": "正在連接資料來源",
      "phase_research": "正在閱讀財報",
      "phase_write": "正在撰寫更新",
      "phase_finalize": "正在完成"
    },
```

- [ ] **Step 3: Validate both JSON files parse**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json','utf8')); JSON.parse(require('fs').readFileSync('src/i18n/locales/zh-TW.json','utf8')); console.log('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(eu): add generating-card i18n strings (en + zh-TW)"
```

---

### Task 4: Tailwind keyframes for the generating card

**Files:**
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Add keyframes**

In `frontend/tailwind.config.ts`, inside `theme.extend.keyframes` (after `feedFadeIn`), add:

```ts
        lcgScan: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        lcgSweep: {
          "0%": { left: "-32%" },
          "100%": { left: "100%" },
        },
        lcgPipFill: {
          "0%": { transform: "scaleX(0)" },
          "100%": { transform: "scaleX(1)" },
        },
```

- [ ] **Step 2: Add the animation utilities**

In the same file, inside `theme.extend.animation` (after `feed-fade-in`), add:

```ts
        "lcg-scan": "lcgScan 2.4s linear infinite",
        "lcg-sweep": "lcgSweep 1.9s var(--ease-in-out) infinite",
        "lcg-pip-fill": "lcgPipFill 1200ms var(--ease-out) forwards",
```

- [ ] **Step 3: Type-check the config compiles**

Run: `cd frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/tailwind.config.ts
git commit -m "feat(eu): add generating-card keyframes (scan/sweep/pip-fill)"
```

---

### Task 5: `deriveEuPhase` — pure phase helper

**Files:**
- Create: `frontend/src/components/earnings-update/feed/euPhase.ts`
- Test: `frontend/src/components/earnings-update/__tests__/euPhase.test.ts` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/earnings-update/__tests__/euPhase.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { EuEvent } from "../../../api/earnings-update";
import { deriveEuPhase } from "../feed/euPhase";

const ev = (type: EuEvent["type"], payload: Record<string, unknown> = {}): EuEvent => ({
  type,
  payload,
});

describe("deriveEuPhase", () => {
  it("starts in connect with RUN_STARTED and only connect active", () => {
    const p = deriveEuPhase([ev("run.started", { subject: "AAPL" })]);
    expect(p.phaseKey).toBe("connect");
    expect(p.monoCode).toBe("RUN_STARTED");
    expect(p.pips).toEqual({
      connect: "active",
      research: "pending",
      write: "pending",
      finalize: "pending",
    });
  });

  it("moves to research on a data tool call and uses args_summary as mono", () => {
    const p = deriveEuPhase([
      ev("run.started"),
      ev("tool.called", { tool_name: "get_earnings_calendar", args_summary: "AAPL Q2" }),
    ]);
    expect(p.phaseKey).toBe("research");
    expect(p.monoCode).toBe("AAPL Q2");
    expect(p.pips.connect).toBe("done");
    expect(p.pips.research).toBe("active");
  });

  it("falls back to the tool name when no args_summary", () => {
    const p = deriveEuPhase([ev("tool.called", { tool_name: "fetch_fundamentals" })]);
    expect(p.phaseKey).toBe("research");
    expect(p.monoCode).toBe("fetch_fundamentals");
  });

  it("moves to write on section.written and shows the section title", () => {
    const p = deriveEuPhase([
      ev("tool.called", { tool_name: "get_earnings_calendar" }),
      ev("section.written", { title: "Guidance" }),
    ]);
    expect(p.phaseKey).toBe("write");
    expect(p.monoCode).toBe("Guidance");
    expect(p.pips.research).toBe("done");
    expect(p.pips.write).toBe("active");
  });

  it("moves to finalize on set_cover and marks all prior phases done", () => {
    const p = deriveEuPhase([
      ev("section.written", { title: "Guidance" }),
      ev("tool.called", { tool_name: "set_cover" }),
    ]);
    expect(p.phaseKey).toBe("finalize");
    expect(p.monoCode).toBe("FINALIZING");
    expect(p.pips).toEqual({
      connect: "done",
      research: "done",
      write: "done",
      finalize: "active",
    });
  });

  it("never moves backwards once a later phase is reached", () => {
    const p = deriveEuPhase([
      ev("tool.called", { tool_name: "set_cover" }),
      ev("tool.called", { tool_name: "get_earnings_calendar" }),
    ]);
    expect(p.phaseKey).toBe("finalize");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/euPhase.test.ts`
Expected: FAIL — cannot resolve `../feed/euPhase`.

- [ ] **Step 3: Implement `euPhase.ts`**

Create `frontend/src/components/earnings-update/feed/euPhase.ts`:

```ts
import type { EuEvent } from "../../../api/earnings-update";

export type EuPhaseKey = "connect" | "research" | "write" | "finalize";
export type PipState = "pending" | "active" | "done";

export interface EuPhase {
  phaseKey: EuPhaseKey;
  labelKey: string;
  monoCode: string;
  pips: Record<EuPhaseKey, PipState>;
}

export const PHASE_ORDER: EuPhaseKey[] = ["connect", "research", "write", "finalize"];

const LABEL_KEYS: Record<EuPhaseKey, string> = {
  connect: "earnings.feed.gen.phase_connect",
  research: "earnings.feed.gen.phase_research",
  write: "earnings.feed.gen.phase_write",
  finalize: "earnings.feed.gen.phase_finalize",
};

/**
 * Derive the current generating phase from the rolling SSE event list.
 *
 * Phase index is monotonic (max reached), but `monoCode` reflects the
 * latest meaningful event. Output tools (write_section/emit_chart) map
 * to the write phase; set_cover/finalize map to finalize; every other
 * tool call is treated as a research/data fetch.
 */
export function deriveEuPhase(events: EuEvent[]): EuPhase {
  let phaseIdx = 0;
  let monoCode = "RUN_STARTED";

  for (const event of events) {
    if (event.type === "tool.called") {
      const tool = String(event.payload.tool_name ?? "");
      if (tool === "set_cover" || tool === "finalize") {
        phaseIdx = Math.max(phaseIdx, 3);
        monoCode = "FINALIZING";
      } else if (tool === "write_section") {
        phaseIdx = Math.max(phaseIdx, 2);
      } else if (tool === "emit_chart") {
        phaseIdx = Math.max(phaseIdx, 2);
        monoCode = "EMIT_CHART";
      } else {
        phaseIdx = Math.max(phaseIdx, 1);
        const summary = (event.payload.args_summary as string | undefined)?.trim();
        monoCode = summary || tool || monoCode;
      }
    } else if (event.type === "section.written") {
      phaseIdx = Math.max(phaseIdx, 2);
      monoCode = String(event.payload.title ?? "section");
    }
  }

  const phaseKey = PHASE_ORDER[phaseIdx];
  const pips = {} as Record<EuPhaseKey, PipState>;
  PHASE_ORDER.forEach((key, i) => {
    pips[key] = i < phaseIdx ? "done" : i === phaseIdx ? "active" : "pending";
  });

  return { phaseKey, labelKey: LABEL_KEYS[phaseKey], monoCode, pips };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/euPhase.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/feed/euPhase.ts frontend/src/components/earnings-update/__tests__/euPhase.test.ts
git commit -m "feat(eu): add deriveEuPhase SSE-to-phase helper"
```

---

### Task 6: `EuGeneratingCard` component

**Files:**
- Create: `frontend/src/components/earnings-update/feed/EuGeneratingCard.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/EuGeneratingCard.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/earnings-update/__tests__/EuGeneratingCard.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EuEvent } from "../../../api/earnings-update";
import type { EuStreamState } from "../../../hooks/useEuRunStream";
import { EuGeneratingCard } from "../feed/EuGeneratingCard";

function makeStream(overrides: Partial<EuStreamState> = {}): EuStreamState {
  return {
    status: "streaming",
    events: [],
    sectionsWritten: 0,
    chartsEmitted: 0,
    toolCallsInflight: 0,
    terminalMessage: null,
    errorMessage: null,
    cancel: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

const ev = (type: EuEvent["type"], payload: Record<string, unknown> = {}): EuEvent => ({
  type,
  payload,
});

describe("EuGeneratingCard", () => {
  it("renders the badge, fallback title, elapsed, and four pips", () => {
    render(<EuGeneratingCard ticker="AAPL" stream={makeStream()} />);
    expect(screen.getByText("Generating Update")).toBeTruthy();
    expect(screen.getByText("AAPL — Earnings Update")).toBeTruthy();
    expect(screen.getByText("0:00")).toBeTruthy();
    expect(screen.getByTestId("eu-gen-pips").querySelectorAll("[data-pip]")).toHaveLength(4);
  });

  it("uses the run.started subject as the title when present", () => {
    const stream = makeStream({ events: [ev("run.started", { subject: "Apple Inc. — Q2 FY26" })] });
    render(<EuGeneratingCard ticker="AAPL" stream={stream} />);
    expect(screen.getByText("Apple Inc. — Q2 FY26")).toBeTruthy();
  });

  it("shows the research phase label and mono code from a data tool call", () => {
    const stream = makeStream({
      events: [ev("tool.called", { tool_name: "get_earnings_calendar", args_summary: "AAPL Q2" })],
    });
    render(<EuGeneratingCard ticker="AAPL" stream={stream} />);
    expect(screen.getByText("Reading the release")).toBeTruthy();
    expect(screen.getByText("AAPL Q2")).toBeTruthy();
    expect(screen.getByTestId("eu-gen-pips").querySelector('[data-pip="research"]')?.getAttribute("data-state")).toBe("active");
  });

  it("calls stream.cancel when Cancel is clicked", () => {
    const stream = makeStream();
    render(<EuGeneratingCard ticker="AAPL" stream={stream} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(stream.cancel).toHaveBeenCalledTimes(1);
  });

  it("disables Cancel once the run is no longer streaming", () => {
    const stream = makeStream({ status: "completed" });
    render(<EuGeneratingCard ticker="AAPL" stream={stream} />);
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuGeneratingCard.test.tsx`
Expected: FAIL — cannot resolve `../feed/EuGeneratingCard`.

- [ ] **Step 3: Implement `EuGeneratingCard.tsx`**

Create `frontend/src/components/earnings-update/feed/EuGeneratingCard.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { EuStreamState } from "../../../hooks/useEuRunStream";

import { deriveEuPhase, PHASE_ORDER } from "./euPhase";

interface Props {
  ticker: string;
  stream: EuStreamState;
}

function useElapsedSeconds(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  const startRef = useRef<number | null>(null);
  useEffect(() => {
    if (!active) return;
    startRef.current = Date.now();
    setSeconds(0);
    const id = setInterval(() => {
      if (startRef.current != null) {
        setSeconds(Math.floor((Date.now() - startRef.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(id);
  }, [active]);
  return seconds;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function subjectFromEvents(stream: EuStreamState): string | null {
  for (const event of stream.events) {
    if (event.type === "run.started") {
      const subject = event.payload.subject;
      if (typeof subject === "string" && subject.trim()) return subject;
    }
  }
  return null;
}

const PIP_CLASS: Record<string, string> = {
  done: "bg-[--color-accent-primary]",
  active: "bg-[rgba(var(--color-accent-primary-rgb),0.4)]",
  pending: "bg-[--color-surface-active]",
};

export function EuGeneratingCard({ ticker, stream }: Props) {
  const { t } = useTranslation();
  const phase = deriveEuPhase(stream.events);
  const elapsed = useElapsedSeconds(stream.status === "streaming");
  const title = subjectFromEvents(stream) ?? t("earnings.feed.gen.title_fallback", { ticker });
  const terminal = stream.status !== "streaming";

  return (
    <article
      data-testid="eu-generating-card"
      className="relative overflow-hidden rounded-[12px] bg-[--color-bg-elevated] border border-[rgba(var(--color-accent-primary-rgb),0.55)] px-[26px] py-5 flex flex-col gap-3.5"
    >
      <span
        aria-hidden
        className="absolute top-0 left-0 right-0 h-px animate-lcg-scan"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(var(--color-accent-primary-rgb),0.85), transparent)",
        }}
      />

      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="inline-flex items-center gap-1.5 h-[22px] px-2.5 rounded bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-feedback-success] font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
          {t("earnings.feed.gen.badge")}
        </span>
        <span className="font-mono text-[10.5px] tracking-[0.06em] text-[--color-text-tertiary] uppercase">
          {ticker}
        </span>
        <span
          aria-label={t("earnings.feed.gen.elapsed_aria")}
          className="ml-auto font-mono text-[11px] text-[--color-text-tertiary] tabular-nums tracking-[0.04em]"
        >
          {formatElapsed(elapsed)}
        </span>
      </div>

      <h2 className="text-[24px] font-semibold tracking-[-0.01em] m-0 text-[--color-text-primary] leading-[1.2]">
        {title}
      </h2>

      <div className="flex items-center gap-3 min-h-[22px]">
        <span className="w-[15px] h-[15px] rounded-full border-[1.6px] border-[--color-border-strong] border-t-[--color-accent-primary] animate-spin flex-shrink-0" />
        <span className="text-[15px] font-medium text-[--color-text-primary]">
          {t(phase.labelKey)}
        </span>
        <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-feedback-success] pl-3 border-l border-[--color-border-subtle] truncate max-w-[280px]">
          {phase.monoCode}
        </span>
      </div>

      <div
        aria-hidden
        className="relative h-[3px] bg-[--color-surface-active] rounded-full overflow-hidden"
      >
        <span
          className="absolute top-0 bottom-0 w-[32%] animate-lcg-sweep"
          style={{
            background:
              "linear-gradient(90deg, rgba(var(--color-accent-primary-rgb),0), rgba(var(--color-accent-primary-rgb),0.9), rgba(var(--color-accent-primary-rgb),0))",
          }}
        />
      </div>

      <div className="flex items-center gap-1.5" data-testid="eu-gen-pips">
        {PHASE_ORDER.map((key) => (
          <span
            key={key}
            data-pip={key}
            data-state={phase.pips[key]}
            className={`flex-1 h-[3px] rounded-full ${PIP_CLASS[phase.pips[key]]}`}
          />
        ))}
      </div>

      <div className="flex mt-0.5">
        <button
          type="button"
          onClick={() => void stream.cancel()}
          disabled={terminal}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] text-[13px] hover:text-[--color-text-primary] hover:border-[--color-border-strong] disabled:opacity-50 transition-colors duration-[--duration-normal]"
        >
          <X size={13} /> {t("earnings.feed.gen.cancel")}
        </button>
      </div>
    </article>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuGeneratingCard.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/feed/EuGeneratingCard.tsx frontend/src/components/earnings-update/__tests__/EuGeneratingCard.test.tsx
git commit -m "feat(eu): add EuGeneratingCard with live phase/elapsed/pips/cancel"
```

---

### Task 7: Wire `EuGeneratingCard` into the page

**Files:**
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx`

- [ ] **Step 1: Import the component**

Add the import next to the existing `EuBigCard` import (keep alphabetical grouping):

```ts
import { EuBigCard } from "../../components/earnings-update/feed/EuBigCard";
import { EuGeneratingCard } from "../../components/earnings-update/feed/EuGeneratingCard";
```

- [ ] **Step 2: Swap the live block to render the generating card while streaming**

Replace the existing `{live ? ( ... ) : null}` block (the one rendering `EuBigCard` with `liveTitle`) with:

```tsx
                      {live ? (
                        <div className="mb-2">
                          {stream.status === "completed" ? (
                            <EuBigCard
                              ticker={live.ticker}
                              title={liveTitle}
                              status="complete"
                              reportId={live.reportId}
                              onOpen={openReport}
                            />
                          ) : (
                            <EuGeneratingCard ticker={live.ticker} stream={stream} />
                          )}
                        </div>
                      ) : null}
```

(`highlights` wiring for the completed-live card and the hero card is added in Task 8, after `EuBigCard` gains the prop — this task deliberately leaves it off so it type-checks standalone.)

- [ ] **Step 3: Type-check**

Run: `cd frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 4: Run the page's existing test**

Run: `cd frontend && npx vitest run src/pages/departments/EarningsUpdate.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/departments/EarningsUpdate.tsx
git commit -m "feat(eu): render EuGeneratingCard during live runs"
```

---

### Task 8: Shared highlight bits + `EuBigCard` enrichment (+ page wiring)

**Files:**
- Create: `frontend/src/components/earnings-update/feed/highlightBits.tsx`
- Modify: `frontend/src/components/earnings-update/feed/EuBigCard.tsx`
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx` (pass `highlights` to the hero + completed-live cards)
- Test: `frontend/src/components/earnings-update/__tests__/EuBigCard.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/earnings-update/__tests__/EuBigCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CardHighlights } from "../../../api/earnings-update";
import { EuBigCard } from "../feed/EuBigCard";

const highlights: CardHighlights = {
  subtitle: "Beat on Services, in-line on iPhone",
  rating: "Buy",
  metrics: [
    { label: "Revenue", value: "$94.2B", change: "+5.4%", tone: "positive" },
    { label: "EPS", value: "$1.78", change: "+3.5%", tone: "positive" },
    { label: "Services", value: "$26.8B", change: "+15.2%", tone: "positive" },
    { label: "GM", value: "46.2%", change: null, tone: "neutral" },
  ],
};

describe("EuBigCard", () => {
  it("renders rating pill, subtitle from highlights, and metric chips (capped at 4)", () => {
    render(
      <EuBigCard
        ticker="AAPL"
        title="Apple Inc. — Earnings Update"
        status="complete"
        reportId="r1"
        highlights={{
          ...highlights,
          metrics: [...highlights.metrics, { label: "X", value: "1", change: null, tone: null }],
        }}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByTestId("eu-rating-pill").textContent).toContain("Buy");
    expect(screen.getByText("Beat on Services, in-line on iPhone")).toBeTruthy();
    expect(screen.getAllByTestId("eu-metric-chip")).toHaveLength(4);
    expect(screen.getByText("$94.2B")).toBeTruthy();
  });

  it("renders without highlights (degrades to title only)", () => {
    render(
      <EuBigCard
        ticker="AAPL"
        title="Apple Inc. — Earnings Update"
        status="complete"
        reportId="r1"
        onOpen={() => {}}
      />,
    );
    expect(screen.getByText("Apple Inc. — Earnings Update")).toBeTruthy();
    expect(screen.queryByTestId("eu-metric-chip")).toBeNull();
    expect(screen.queryByTestId("eu-rating-pill")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuBigCard.test.tsx`
Expected: FAIL — `highlights` prop is unknown / `eu-rating-pill` not found.

- [ ] **Step 3: Create the shared highlight bits**

Create `frontend/src/components/earnings-update/feed/highlightBits.tsx`:

```tsx
import type { CoverMetric } from "../../../api/earnings-update";

export function toneClass(tone: string | null | undefined): string {
  if (tone === "positive") return "text-[--color-feedback-success]";
  if (tone === "negative") return "text-[--color-feedback-error]";
  return "text-[--color-text-secondary]";
}

export function MetricChip({ metric }: { metric: CoverMetric }) {
  return (
    <span
      data-testid="eu-metric-chip"
      className="inline-flex items-baseline gap-1.5 px-2 py-1 rounded-md bg-[--color-surface-hover] border border-[--color-border-subtle]"
    >
      <span className="font-mono text-[9.5px] tracking-[0.06em] uppercase text-[--color-text-tertiary]">
        {metric.label}
      </span>
      <span className="text-[12.5px] font-semibold text-[--color-text-primary] tabular-nums">
        {metric.value}
      </span>
      {metric.change ? (
        <span className={`font-mono text-[10.5px] tabular-nums ${toneClass(metric.tone)}`}>
          {metric.change}
        </span>
      ) : null}
    </span>
  );
}

export function RatingPill({ rating }: { rating: string }) {
  return (
    <span
      data-testid="eu-rating-pill"
      className="inline-flex items-center h-[22px] px-2.5 rounded bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.08em] uppercase text-[--color-feedback-success] font-semibold"
    >
      {rating}
    </span>
  );
}
```

- [ ] **Step 4: Enrich `EuBigCard`**

In `frontend/src/components/earnings-update/feed/EuBigCard.tsx`:

Add imports at the top:

```ts
import type { CardHighlights } from "../../../api/earnings-update";

import { MetricChip, RatingPill } from "./highlightBits";
```

Add `highlights` to `Props`:

```ts
interface Props {
  ticker: string;
  title: string;
  subtitle?: string;
  stamp?: string;
  status: "streaming" | "complete";
  reportId?: string | null;
  highlights?: CardHighlights | null;
  onOpen?: (id: string) => void;
}
```

Update the destructure and add a resolved subtitle:

```ts
export function EuBigCard({
  ticker,
  title,
  subtitle,
  stamp,
  status,
  reportId,
  highlights,
  onOpen,
}: Props) {
  const { t } = useTranslation();
  const live = status === "streaming";
  const resolvedSubtitle = subtitle ?? highlights?.subtitle ?? undefined;
  const metrics = highlights?.metrics?.slice(0, 4) ?? [];
```

In the tag row (the `div` containing the live/today badge and the ticker), add the rating pill at the end of that flex container, right after the ticker `<span>`:

```tsx
          </span>
          {highlights?.rating ? <RatingPill rating={highlights.rating} /> : null}
        </div>
```

Replace the subtitle render to use `resolvedSubtitle`:

```tsx
        {resolvedSubtitle ? (
          <p className="text-[14.5px] text-[--color-text-secondary] leading-[1.5] m-0">
            {resolvedSubtitle}
          </p>
        ) : null}
```

Add the metric chips row directly after the subtitle paragraph and before the `<div className="flex gap-2 mt-1">` actions block:

```tsx
        {metrics.length > 0 ? (
          <div className="flex flex-wrap gap-2 mt-0.5">
            {metrics.map((metric, i) => (
              <MetricChip key={`${metric.label}-${i}`} metric={metric} />
            ))}
          </div>
        ) : null}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuBigCard.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Wire `highlights` into the page (hero + completed-live cards)**

In `frontend/src/pages/departments/EarningsUpdate.tsx`, pass `highlights` to the two `EuBigCard` call sites.

For the completed-live card (inside the `live` block added in Task 8/Step-equivalent — the `stream.status === "completed"` branch), add the `highlights` prop:

```tsx
                            <EuBigCard
                              ticker={live.ticker}
                              title={liveTitle}
                              status="complete"
                              reportId={live.reportId}
                              highlights={findRun(runs, live.reportId)?.highlights ?? null}
                              onOpen={openReport}
                            />
```

For the `heroToday` card, add the `highlights` prop:

```tsx
                        <div className="mb-2">
                          <EuBigCard
                            ticker={heroToday.ticker}
                            title={heroToday.subject}
                            stamp={formatHeroStamp(heroToday.created_at)}
                            status="complete"
                            reportId={heroToday.report_id}
                            highlights={heroToday.highlights ?? null}
                            onOpen={openReport}
                          />
                        </div>
```

- [ ] **Step 7: Type-check**

Run: `cd frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 8: Run the page test to confirm no regression**

Run: `cd frontend && npx vitest run src/pages/departments/EarningsUpdate.test.tsx`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/earnings-update/feed/highlightBits.tsx frontend/src/components/earnings-update/feed/EuBigCard.tsx frontend/src/components/earnings-update/__tests__/EuBigCard.test.tsx frontend/src/pages/departments/EarningsUpdate.tsx
git commit -m "feat(eu): show rating + metric chips on EuBigCard and wire highlights into the feed"
```

---

### Task 9: `EuReportRow` enrichment

**Files:**
- Modify: `frontend/src/components/earnings-update/feed/EuReportRow.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/EuReportRow.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/earnings-update/__tests__/EuReportRow.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RunSummary } from "../../../api/earnings-update";
import { EuReportRow } from "../feed/EuReportRow";

function makeReport(highlights: RunSummary["highlights"]): RunSummary {
  return {
    report_id: "r1",
    ticker: "META",
    subject: "Q1 FY26 — Reality Labs narrows loss",
    template_id: "default",
    trigger_kind: "scheduled",
    fiscal_date: "2026-03-31",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-06-02T14:32:00Z",
    completed_at: "2026-06-02T14:36:00Z",
    reasoning_effort: null,
    highlights,
  };
}

describe("EuReportRow", () => {
  it("renders subtitle, up to 2 metric chips, and rating", () => {
    render(
      <EuReportRow
        report={makeReport({
          subtitle: "Reels CPMs up; capex guide raised",
          rating: "Buy",
          metrics: [
            { label: "Rev", value: "$36.5B", change: "+1.4%", tone: "positive" },
            { label: "EPS", value: "$5.16", change: "+5.2%", tone: "positive" },
            { label: "DAP", value: "3.31B", change: null, tone: "neutral" },
          ],
        })}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByTestId("eu-row-subtitle").textContent).toContain("Reels CPMs");
    expect(screen.getAllByTestId("eu-metric-chip")).toHaveLength(2);
    expect(screen.getByTestId("eu-rating-pill").textContent).toContain("Buy");
  });

  it("degrades to subject only when there are no highlights", () => {
    render(<EuReportRow report={makeReport(null)} onOpen={() => {}} />);
    expect(screen.getByText(/Reality Labs/)).toBeTruthy();
    expect(screen.queryByTestId("eu-row-subtitle")).toBeNull();
    expect(screen.queryByTestId("eu-metric-chip")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuReportRow.test.tsx`
Expected: FAIL — `eu-row-subtitle` not found.

- [ ] **Step 3: Enrich `EuReportRow`**

In `frontend/src/components/earnings-update/feed/EuReportRow.tsx`:

Add the import (after the existing imports):

```ts
import { MetricChip, RatingPill } from "./highlightBits";
```

Change the grid template on the root `<button>` from `grid-cols-[64px_1fr_30px]` to `grid-cols-[64px_1fr_auto_30px]`.

Replace the middle `<div className="min-w-0">…</div>` (the subject block) with:

```tsx
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
```

Insert a metrics/rating cluster between the subject block and the `<ChevronRight … />` (this fills the new `auto` grid column):

```tsx
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/EuReportRow.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Type-check**

Run: `cd frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/earnings-update/feed/EuReportRow.tsx frontend/src/components/earnings-update/__tests__/EuReportRow.test.tsx
git commit -m "feat(eu): show subtitle + metric chips + rating on EuReportRow"
```

---

### Task 10: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full Earnings Update frontend test set**

Run: `cd frontend && npx vitest run src/components/earnings-update src/pages/departments/EarningsUpdate.test.tsx`
Expected: PASS (all EU component + page tests, including the new euPhase / EuGeneratingCard / EuBigCard / EuReportRow suites).

- [ ] **Step 2: Frontend type-check**

Run: `cd frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 3: Backend EU route tests**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py packages/server/tests/test_routes/departments/test_earnings_update_v2_highlights.py -q`
Expected: PASS.

- [ ] **Step 4: Backend lint/format**

Run: `uv run ruff check packages/server/src/openlia_server/routes/departments/earnings_update_v2.py packages/server/tests/test_routes/departments/test_earnings_update_v2_highlights.py`
Expected: no errors.

- [ ] **Step 5: Manual smoke (optional but recommended)**

Start backend (`uv run openlia serve`, :8080) and Vite (`cd frontend && npm run dev`, :5173). On `/earnings-update`: start an on-demand report and confirm the generating card shows the badge, advancing phase label/mono code, sweeping bar, filling pips, and ticking elapsed timer; confirm Cancel stops the run. After completion, confirm feed rows and the hero/big card show the thesis subtitle, metric chips, and rating where the report produced a cover, and degrade cleanly where it did not.

---

## Notes for the implementer

- **Graceful degradation is a hard requirement.** Every highlight render path must no-op when `highlights` is null/empty. The tests in Tasks 8 and 9 cover the degraded path — keep them green.
- **Do not re-format metric values.** `value`/`change` are model-authored strings; render verbatim.
- **Out of scope (do not add):** Beat/Miss verdict pill, surprise %, after-hours move, signal score, sparkline, scramble/odometer text effects, cabinet-view restyle.
