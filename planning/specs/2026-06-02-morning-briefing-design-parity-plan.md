# Morning Briefing Visual Parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every Morning Briefing (MB) surface up to the Earnings Update (EU) / Equity Research v3 (ER) finish level so the three department pages read as one design system.

**Architecture:** Frontend-only. Port proven EU/ER patterns into MB-local components (the repo's per-department duplication convention). Add a hero + polished empty state, restyle the two overlay views, and rebuild the shared config panel + both modal shells to ER's settings parity (mono-eyebrow headers, Segmented controls, card-list pickers). No backend/API/streaming changes; tokens only.

**Tech Stack:** React + TypeScript + Vite, Tailwind (arbitrary values + CSS-variable design tokens), Radix Dialog, lucide-react, react-i18next, Vitest + Testing Library.

**Branch:** `feat/mb-design-parity` (already created; the design spec is committed there).

**Spec:** `planning/specs/2026-06-02-morning-briefing-design-parity-design.md`

**Conventions (apply throughout):**
- All commands run from the repo root unless they start with `cd frontend`.
- Test a single file: `cd frontend && npx vitest run src/<path>.test.tsx`.
- Typecheck: `cd frontend && npm run lint` (this is `tsc --noEmit`).
- Build: `cd frontend && npm run build`.
- Tests live in `frontend/src/components/morning-briefing/__tests__/`.
- i18n: add every new string to BOTH `frontend/src/i18n/locales/en.json` and
  `frontend/src/i18n/locales/zh-TW.json`, nested under `morning_briefing`.
- Use the design token `--color-feedback-error` for danger/delete states.
  `--color-feedback-danger` is NOT defined in `styles/tokens.css` — never use it.
- Commit after each task on branch `feat/mb-design-parity`.

---

## File Structure

**New files:**
- `frontend/src/components/morning-briefing/feed/MbHero.tsx` — presentational hero (eyebrow + headline + 3 stat cells).
- `frontend/src/components/morning-briefing/feed/MbEmptyPage.tsx` — dashed-card empty state with glowing icon + two CTAs.
- `frontend/src/components/morning-briefing/__tests__/MbHero.test.tsx`
- `frontend/src/components/morning-briefing/__tests__/MbEmptyPage.test.tsx`

**Modified files:**
- `frontend/src/pages/departments/MorningBriefing.tsx` — render hero + empty page; tidy search row; compute stats.
- `frontend/src/components/morning-briefing/MbConfigFields.tsx` — full rewrite: `MbSectionHeader` + `MbSegmented` primitives, bordered section rhythm, card-list template/instructions pickers, Segmented Length/Language/Reasoning.
- `frontend/src/components/morning-briefing/MbRunNowModal.tsx` — ER modal shell chrome.
- `frontend/src/components/morning-briefing/ScheduleEditorModal.tsx` — swap `mbSectionTitle`→`MbSectionHeader`; ER shell chrome; fix dead `--color-feedback-danger`→`--color-feedback-error`.
- `frontend/src/components/morning-briefing/MbSchedulesView.tsx` — header chrome + rich rows + dashed-card empty state.
- `frontend/src/components/morning-briefing/MbCabinetView.tsx` — header chrome + section icons/counts + dashed upload pills + row hover + empty cards.
- `frontend/src/components/morning-briefing/__tests__/MbConfigFields.test.tsx` — language change becomes a click.
- `frontend/src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx` — language prefill assertion reads `aria-checked`.
- `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/zh-TW.json` — new keys.

---

## Task 1: `MbHero` component

**Files:**
- Create: `frontend/src/components/morning-briefing/feed/MbHero.tsx`
- Create: `frontend/src/components/morning-briefing/__tests__/MbHero.test.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/morning-briefing/__tests__/MbHero.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MbHero } from "../feed/MbHero";

describe("MbHero", () => {
  it("renders the three stat values", () => {
    render(
      <MbHero
        briefingsThisWeek={5}
        activeSchedules={2}
        nextRun="Tomorrow · 7:00 AM EST"
      />,
    );
    expect(screen.getByTestId("mb-hero")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Tomorrow · 7:00 AM EST")).toBeInTheDocument();
  });

  it("falls back to an em dash when there is no next run", () => {
    render(<MbHero briefingsThisWeek={0} activeSchedules={0} nextRun={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbHero.test.tsx`
Expected: FAIL — `Failed to resolve import "../feed/MbHero"`.

- [ ] **Step 3: Add i18n keys**

In `frontend/src/i18n/locales/en.json`, inside the `"morning_briefing"` object, add a new `"hero"` key (place it next to the existing `"feed"` key):

```json
"hero": {
  "eyebrow": "Morning Briefing",
  "dept": "Scheduled",
  "headline": "Your morning briefing",
  "lede": "Scheduled briefings written from your templates and instructions — ready before your day starts.",
  "stat_briefings_wk": "Briefings this week",
  "stat_active_schedules": "Active schedules",
  "stat_next_run": "Next run"
},
```

In `frontend/src/i18n/locales/zh-TW.json`, inside `"morning_briefing"`, add:

```json
"hero": {
  "eyebrow": "晨間簡報",
  "dept": "已排程",
  "headline": "您的晨間簡報",
  "lede": "依您的範本與指示自動撰寫的排程簡報——在您一天開始前就緒。",
  "stat_briefings_wk": "本週簡報",
  "stat_active_schedules": "啟用排程",
  "stat_next_run": "下次執行"
},
```

- [ ] **Step 4: Write the component**

Create `frontend/src/components/morning-briefing/feed/MbHero.tsx`:

```tsx
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  briefingsThisWeek: number;
  activeSchedules: number;
  /** Pre-formatted "soonest enabled run" display string, or null when none. */
  nextRun: string | null;
}

const DASH = "—";

export function MbHero({ briefingsThisWeek, activeSchedules, nextRun }: Props) {
  const { t } = useTranslation();
  return (
    <section
      data-testid="mb-hero"
      className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 items-end pb-[22px] border-b border-[--color-border-subtle] mb-6"
    >
      <div>
        <span className="inline-flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] uppercase text-[--color-feedback-success] mb-2.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_0_4px_rgba(var(--color-accent-primary-rgb),0.18)]" />
          {t("morning_briefing.hero.eyebrow")} {String.fromCharCode(0xb7)}{" "}
          {t("morning_briefing.hero.dept")}
        </span>
        <h1 className="text-[38px] font-semibold leading-[1.05] tracking-[-0.02em] m-0 mb-2 text-[--color-text-primary]">
          {t("morning_briefing.hero.headline")}
        </h1>
        <p className="text-base text-[--color-text-secondary] m-0 max-w-[620px] leading-[1.55]">
          {t("morning_briefing.hero.lede")}
        </p>
      </div>
      <div className="flex gap-7">
        <Stat
          label={t("morning_briefing.hero.stat_briefings_wk")}
          value={briefingsThisWeek}
        />
        <Stat
          label={t("morning_briefing.hero.stat_active_schedules")}
          value={activeSchedules}
        />
        {/* Next run is a phrase, not a metric — render it smaller so a long
            "Tomorrow · 7:00 AM EST" string never blows out the stat row. */}
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-[9.5px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
            {t("morning_briefing.hero.stat_next_run")}
          </span>
          <span className="font-mono text-[13px] leading-[1.3] text-[--color-text-primary] max-w-[180px]">
            {nextRun ?? DASH}
          </span>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[9.5px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
        {label}
      </span>
      <span className="font-mono text-[22px] tabular-nums leading-none text-[--color-text-primary]">
        {value}
      </span>
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbHero.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/morning-briefing/feed/MbHero.tsx \
        frontend/src/components/morning-briefing/__tests__/MbHero.test.tsx \
        frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(morning-briefing): add MbHero stat hero"
```

---

## Task 2: `MbEmptyPage` component

**Files:**
- Create: `frontend/src/components/morning-briefing/feed/MbEmptyPage.tsx`
- Create: `frontend/src/components/morning-briefing/__tests__/MbEmptyPage.test.tsx`

Reuses existing i18n keys: `morning_briefing.empty_title`, `morning_briefing.empty_sub`, `morning_briefing.run_now`, `morning_briefing.open_library` (all already present). No new keys.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/morning-briefing/__tests__/MbEmptyPage.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MbEmptyPage } from "../feed/MbEmptyPage";

describe("MbEmptyPage", () => {
  it("fires onRunNow and onOpenLibrary", () => {
    const onRunNow = vi.fn();
    const onOpenLibrary = vi.fn();
    render(<MbEmptyPage onRunNow={onRunNow} onOpenLibrary={onOpenLibrary} />);
    fireEvent.click(screen.getByTestId("mb-empty-run-now"));
    fireEvent.click(screen.getByTestId("mb-empty-open-library"));
    expect(onRunNow).toHaveBeenCalledTimes(1);
    expect(onOpenLibrary).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbEmptyPage.test.tsx`
Expected: FAIL — cannot resolve `../feed/MbEmptyPage`.

- [ ] **Step 3: Write the component**

Create `frontend/src/components/morning-briefing/feed/MbEmptyPage.tsx`:

```tsx
import { CalendarClock, FileText, Library } from "lucide-react";
import { useTranslation } from "react-i18next";

interface Props {
  onRunNow: () => void;
  onOpenLibrary: () => void;
}

export function MbEmptyPage({ onRunNow, onOpenLibrary }: Props) {
  const { t } = useTranslation();
  return (
    <div
      data-testid="mb-empty-page"
      className="flex flex-col items-center justify-center text-center py-20 px-6 border border-dashed border-[--color-border-subtle] rounded-[12px] bg-[--color-bg-elevated]"
    >
      <div
        aria-hidden="true"
        className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] bg-[--color-accent-primary] text-[--color-accent-on] shadow-[0_0_24px_rgba(212,255,0,0.35)]"
      >
        <CalendarClock size={24} strokeWidth={1.6} />
      </div>
      <h2 className="text-[20px] font-semibold text-[--color-text-primary] m-0 mb-2">
        {t("morning_briefing.empty_title")}
      </h2>
      <p className="text-[14px] text-[--color-text-secondary] max-w-[480px] m-0 mb-5 leading-[1.5]">
        {t("morning_briefing.empty_sub")}
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onRunNow}
          data-testid="mb-empty-run-now"
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal]"
        >
          <FileText size={14} /> {t("morning_briefing.run_now")}
        </button>
        <button
          type="button"
          onClick={onOpenLibrary}
          data-testid="mb-empty-open-library"
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md border border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] text-[13px] font-medium transition-colors duration-[--duration-normal]"
        >
          <Library size={14} /> {t("morning_briefing.open_library")}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbEmptyPage.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/morning-briefing/feed/MbEmptyPage.tsx \
        frontend/src/components/morning-briefing/__tests__/MbEmptyPage.test.tsx
git commit -m "feat(morning-briefing): add MbEmptyPage empty state"
```

---

## Task 3: Wire `MbHero` + `MbEmptyPage` into the page

**Files:**
- Modify: `frontend/src/pages/departments/MorningBriefing.tsx`

There is no page-level test (the page mounts many hooks). Verification is the existing suite + build staying green. Each edit below is an exact old→new replacement.

- [ ] **Step 1: Add imports**

In `frontend/src/pages/departments/MorningBriefing.tsx`, find the feed-component imports block (around lines 10-20) and add the two new imports plus the next-briefing helper. Replace:

```tsx
import { MbBigCard } from "../../components/morning-briefing/feed/MbBigCard";
import { MbGeneratingCard } from "../../components/morning-briefing/feed/MbGeneratingCard";
```

with:

```tsx
import { MbBigCard } from "../../components/morning-briefing/feed/MbBigCard";
import { MbEmptyPage } from "../../components/morning-briefing/feed/MbEmptyPage";
import { MbGeneratingCard } from "../../components/morning-briefing/feed/MbGeneratingCard";
import { MbHero } from "../../components/morning-briefing/feed/MbHero";
```

Then, find the grouping-helper import:

```tsx
import {
  groupReports,
  searchReports,
} from "../../components/morning-briefing/feed/mbFeedHelpers";
```

and immediately AFTER it add:

```tsx
import { pickEarliestNextBriefing } from "../../lib/morning-briefing/next-briefing";
```

- [ ] **Step 2: Compute hero stats**

Find this block (around lines 134-144):

```tsx
  const liveCount = useMemo(() => {
    const running = runs.filter(
      (r) => r.status === "running" && r.report_id !== liveReportId,
    ).length;
    return running + (liveReportId ? 1 : 0);
  }, [runs, liveReportId]);
```

Immediately AFTER it, add:

```tsx
  const heroStats = useMemo(() => {
    const all = groupReports(runs);
    return {
      briefingsThisWeek: all.today.length + all.thisWeek.length,
      activeSchedules: schedules.filter((s) => s.is_enabled).length,
      nextRun: pickEarliestNextBriefing(schedules)?.display ?? null,
    };
  }, [runs, schedules]);
```

- [ ] **Step 3: Replace the bare empty state with `MbEmptyPage`**

Replace this block (around lines 250-268):

```tsx
          ) : allEmpty ? (
            <div
              data-testid="mb-empty-page"
              className="flex flex-col items-center justify-center text-center py-24"
            >
              <h2 className="text-[20px] font-semibold text-[--color-text-primary] mb-2">
                {t("morning_briefing.empty_title")}
              </h2>
              <p className="text-[14px] text-[--color-text-secondary] max-w-[420px] mb-6 leading-[1.6]">
                {t("morning_briefing.empty_sub")}
              </p>
              <button
                type="button"
                onClick={() => setCabinetOpen(true)}
                className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover]"
              >
                <Library size={14} /> {t("morning_briefing.open_library")}
              </button>
            </div>
          ) : (
```

with:

```tsx
          ) : allEmpty ? (
            <MbEmptyPage
              onRunNow={() => setRunNowOpen(true)}
              onOpenLibrary={() => setCabinetOpen(true)}
            />
          ) : (
```

- [ ] **Step 4: Insert the hero and tidy the search row**

Replace this block (around lines 271-286):

```tsx
              <div
                className="flex items-center gap-2 flex-wrap mb-[22px]"
                style={{ animationDelay: "80ms" }}
              >
                <div className="flex-1" />
                <div className="inline-flex items-center gap-2 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-[--color-bg-elevated] min-w-[220px]">
                  <Search size={13} className="text-[--color-text-tertiary]" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder={t("morning_briefing.feed.search_placeholder")}
                    aria-label={t("morning_briefing.feed.search_aria")}
                    className="border-0 bg-transparent outline-none text-[13px] text-[--color-text-primary] w-full placeholder:text-[--color-text-tertiary]"
                  />
                </div>
              </div>
```

with:

```tsx
              <div
                className="animate-feed-fade-up"
                style={{ animationDelay: "80ms" }}
              >
                <MbHero
                  briefingsThisWeek={heroStats.briefingsThisWeek}
                  activeSchedules={heroStats.activeSchedules}
                  nextRun={heroStats.nextRun}
                />
              </div>

              <div className="flex items-center gap-2 flex-wrap mb-[22px]">
                <div className="inline-flex items-center gap-2 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-[--color-bg-elevated] flex-1 max-w-[320px]">
                  <Search size={13} className="text-[--color-text-tertiary]" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder={t("morning_briefing.feed.search_placeholder")}
                    aria-label={t("morning_briefing.feed.search_aria")}
                    className="border-0 bg-transparent outline-none text-[13px] text-[--color-text-primary] w-full placeholder:text-[--color-text-tertiary]"
                  />
                </div>
              </div>
```

- [ ] **Step 5: Confirm no import changes are needed**

All four lucide imports on line 2 (`CalendarClock`, `FileText`, `Library`,
`Search`) remain in use: `Library` by the header's Library button (≈line 214),
`CalendarClock` by the Schedules button, `FileText` by the Run Now button, and
`Search` by the search input. So the import line stays as-is. The `npm run lint`
in Step 6 (`tsc --noEmit`) will flag any accidentally-unused import.

Run: `cd frontend && grep -n "Library\|CalendarClock\|FileText\|Search" src/pages/departments/MorningBriefing.tsx`
Expected: each name appears on the import line AND at least one usage line.

- [ ] **Step 6: Typecheck + run the full MB test suite**

Run: `cd frontend && npm run lint`
Expected: no errors.

Run: `cd frontend && npx vitest run src/components/morning-briefing`
Expected: PASS (all existing MB tests + the two new ones).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/departments/MorningBriefing.tsx
git commit -m "feat(morning-briefing): render hero + empty page, tidy search row"
```

---

## Task 4: Rebuild `MbConfigFields` to ER settings parity

This is the largest task: it introduces the `MbSectionHeader` + `MbSegmented`
primitives, converts the section rhythm to bordered blocks, replaces the
template/instructions `<select>`s with ER-style card-list pickers, and converts
Length/Language/Reasoning to Segmented controls. Because it removes the exported
`mbSectionTitle`, it also updates `ScheduleEditorModal`'s import + timing header
in the same task so the build stays green.

**Files:**
- Modify: `frontend/src/components/morning-briefing/MbConfigFields.tsx` (full rewrite)
- Modify: `frontend/src/components/morning-briefing/ScheduleEditorModal.tsx` (import + timing header only)
- Modify: `frontend/src/components/morning-briefing/__tests__/MbConfigFields.test.tsx`
- Modify: `frontend/src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Update the two affected tests first (they will fail)**

In `frontend/src/components/morning-briefing/__tests__/MbConfigFields.test.tsx`,
replace the `"routes a language change through onChange"` test with a click-based
version (the language control becomes a Segmented radiogroup, not a `<select>`):

```tsx
  it("routes a language change through onChange", async () => {
    const onChange = vi.fn();
    render(<MbConfigFields draft={draft()} onChange={onChange} />);
    await screen.findByTestId("mb-template-select");
    fireEvent.click(screen.getByTestId("mb-language-select-option-zh-Hant"));
    expect(onChange).toHaveBeenCalledWith({ language: "zh-Hant" });
  });
```

In `frontend/src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx`,
replace the `"prefills from the remembered draft each time it opens"` test body's
assertion (the language control is no longer an `HTMLSelectElement` with `.value`):

```tsx
  it("prefills from the remembered draft each time it opens", async () => {
    const { rerender } = render(
      <MbRunNowModal open={false} onClose={vi.fn()} onStarted={vi.fn()} />,
    );
    // Seed AFTER the initial (closed) mount so this exercises the open effect.
    window.localStorage.setItem(
      RUN_NOW_LS_KEY,
      JSON.stringify({ language: "zh-Hant" }),
    );
    rerender(<MbRunNowModal open onClose={vi.fn()} onStarted={vi.fn()} />);
    const opt = await screen.findByTestId("mb-language-select-option-zh-Hant");
    expect(opt).toHaveAttribute("aria-checked", "true");
  });
```

- [ ] **Step 2: Run the two tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbConfigFields.test.tsx src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx`
Expected: FAIL — `mb-language-select-option-zh-Hant` not found (selects still rendered).

- [ ] **Step 3: Add i18n keys**

In `frontend/src/i18n/locales/en.json`, inside the existing
`morning_briefing.schedule_editor` object, add these keys (alongside the
existing `template_*` / `instructions_*` keys):

```json
"template_builtin": "built-in",
"template_uploaded": "uploaded",
"template_freeform_sublabel": "no template — analyst designs the structure",
"instructions_builtin": "built-in",
"instructions_uploaded": "uploaded",
```

In `frontend/src/i18n/locales/zh-TW.json`, inside
`morning_briefing.schedule_editor`, add:

```json
"template_builtin": "內建",
"template_uploaded": "已上傳",
"template_freeform_sublabel": "無範本——由分析師設計結構",
"instructions_builtin": "內建",
"instructions_uploaded": "已上傳",
```

(All other labels reuse existing keys: `template_title`, `template_hint`,
`template_freeform`, `template_freeform_hint`, `template_upload`,
`template_delete_aria`, `instructions_title`, `instructions_hint`,
`instructions_none`, `instructions_upload`, `instructions_delete_aria`,
`instructions_delete_confirm`, `model_title`, `model_hint`, `connectors_title`,
`connectors_hint`, `ds_empty`, `length_title`, `length_aria`, `length_concise`,
`length_normal`, `length_elaborative`, `language_title`, `reasoning_title`,
`reasoning_hint`, `reasoning_default`, `reasoning_medium`, `reasoning_high`.)

- [ ] **Step 4: Rewrite `MbConfigFields.tsx`**

Replace the ENTIRE contents of
`frontend/src/components/morning-briefing/MbConfigFields.tsx` with:

```tsx
/**
 * MbConfigFields — the shared Morning Briefing config controls.
 *
 * The model / template / instructions / connectors / length / language /
 * reasoning controls, lifted out of ScheduleEditorModal so both the schedule
 * editor and the Run Now modal render the exact same settings. Owns the
 * template/instructions/data-source hooks and the upload sub-modals; the
 * parent owns the draft state and passes a patcher via `onChange`.
 *
 * Visual structure mirrors the ER (Equity Research v3) settings modal:
 * mono-eyebrow section headers, bordered section rhythm, card-list template /
 * instructions pickers, and Segmented controls for length / language /
 * reasoning. MB is purely template/instructions-driven — no ticker.
 */
import { useState, type ReactNode } from "react";
import { Trash2, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  MbDataSource,
  MbInstructions,
  MbReasoningEffort,
  MbReportLength,
  MbTemplate,
} from "../../api/morning-briefing";
import { useMbDataSources } from "../../hooks/useMbDataSources";
import { useMbInstructions } from "../../hooks/useMbInstructions";
import { useMbTemplates } from "../../hooks/useMbTemplates";

import { MbInstructionsUploadModal } from "./MbInstructionsUploadModal";
import { MbModelPicker, type MbModelSelection } from "./MbModelPicker";
import { MbTemplateUploadModal } from "./MbTemplateUploadModal";

const LENGTH_IDS: readonly MbReportLength[] = [
  "concise",
  "normal",
  "elaborative",
];

/** The per-run config slice shared by the editor and the Run Now modal. */
export interface MbConfigDraft {
  template_id: string;
  instructions_id: string | null;
  provider_ids: string[];
  web_search: boolean;
  provider_kind: string | null;
  model: string | null;
  language: string;
  length: string;
  reasoning_effort: MbReasoningEffort;
}

/** Freeform template with no instructions has nothing to brief on. */
export function isBriefEmpty(draft: MbConfigDraft): boolean {
  return draft.template_id === "freeform" && !draft.instructions_id;
}

/** Mono-eyebrow section label, matching the ER settings modal. */
export function MbSectionHeader({ label }: { label: string }) {
  return (
    <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
      {label}
    </span>
  );
}

interface SegOption<T extends string> {
  value: T;
  label: string;
}

/** Segmented radio control, matching the ER settings modal. */
export function MbSegmented<T extends string>({
  ariaLabel,
  value,
  options,
  onChange,
  testId,
}: {
  ariaLabel: string;
  value: T;
  options: readonly SegOption<T>[];
  onChange: (next: T) => void;
  testId?: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      data-testid={testId}
      className="flex gap-[2px] rounded-lg border border-[--color-border-subtle] bg-[--color-bg-base] p-[3px]"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={opt.value}
            data-testid={testId ? `${testId}-option-${opt.value}` : undefined}
            onClick={() => onChange(opt.value)}
            className={[
              "flex-1 rounded-md px-[10px] py-2 text-center font-display text-[12.5px] transition-colors",
              active
                ? "bg-[--color-bg-elevated] font-medium text-[--color-text-primary] shadow-[0_1px_2px_rgba(13,13,11,0.06)]"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
            ].join(" ")}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function MbToggle({
  on,
  onClick,
  testId,
  label,
  ariaLabel,
  disabled = false,
}: {
  on: boolean;
  onClick: () => void;
  testId: string;
  label: ReactNode;
  ariaLabel?: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={[
        "flex items-center justify-between gap-4 px-4 py-3.5 transition-colors",
        disabled
          ? "opacity-50 cursor-not-allowed pointer-events-none"
          : "cursor-pointer hover:bg-[--color-surface-hover]",
      ].join(" ")}
    >
      <span className="text-[13.5px] font-medium text-[--color-text-primary]">
        {label}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={ariaLabel}
        data-testid={testId}
        disabled={disabled}
        onClick={disabled ? undefined : onClick}
        className={[
          "relative w-10 h-6 rounded-full flex-shrink-0 transition-colors",
          on && !disabled
            ? "bg-[--color-accent-primary]"
            : "bg-[--color-border-subtle]",
        ].join(" ")}
      >
        <span
          className={[
            "absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-[left]",
            on && !disabled ? "left-5" : "left-1",
          ].join(" ")}
        />
      </button>
    </label>
  );
}

/** Dashed mono "Upload" pill, matching the ER settings modal. */
function UploadPill({
  onClick,
  testId,
  label,
}: {
  onClick: () => void;
  testId: string;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="inline-flex items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[10px] py-[3px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-solid hover:border-[--color-feedback-success] hover:text-[--color-feedback-success] transition-colors"
    >
      <Upload size={11} strokeWidth={2} /> {label}
    </button>
  );
}

/** A single selectable card in the template / instructions picker lists. */
function OptionRow({
  active,
  onClick,
  testId,
  title,
  sublabel,
  onDelete,
  deleteAria,
}: {
  active: boolean;
  onClick: () => void;
  testId: string;
  title: string;
  sublabel?: string;
  onDelete?: () => void;
  deleteAria?: string;
}) {
  return (
    <div
      className={[
        "flex items-center gap-2 rounded-md border px-3 py-2",
        active
          ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.06)]"
          : "border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-border-strong]",
      ].join(" ")}
    >
      <button
        type="button"
        onClick={onClick}
        data-testid={testId}
        className="flex min-w-0 flex-1 flex-col text-left"
      >
        <span className="truncate text-[12.5px] font-medium text-[--color-text-primary]">
          {title}
        </span>
        {sublabel ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            {sublabel}
          </span>
        ) : null}
      </button>
      {onDelete ? (
        <button
          type="button"
          aria-label={deleteAria}
          onClick={onDelete}
          className="rounded p-1 text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
        >
          <Trash2 size={12} />
        </button>
      ) : null}
    </div>
  );
}

interface Props {
  draft: MbConfigDraft;
  onChange: (patch: Partial<MbConfigDraft>) => void;
}

export function MbConfigFields({ draft, onChange }: Props) {
  const { t } = useTranslation();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);

  const {
    templates,
    create: createTemplate,
    upload: uploadTemplate,
    remove: removeTemplate,
  } = useMbTemplates();
  const {
    instructions,
    upload: uploadInstructions,
    remove: removeInstructions,
  } = useMbInstructions();
  const { sources } = useMbDataSources({
    provider_kind: draft.provider_kind ?? undefined,
    model: draft.model ?? undefined,
    enabled_provider_ids: draft.provider_ids,
    web_search: draft.web_search,
  });

  const LENGTH_OPTIONS: readonly SegOption<MbReportLength>[] = LENGTH_IDS.map(
    (id) => ({
      value: id,
      label: t(`morning_briefing.schedule_editor.length_${id}`),
    }),
  );

  const LANGUAGE_OPTIONS: readonly SegOption<"en" | "zh-Hant">[] = [
    { value: "en", label: "English" },
    { value: "zh-Hant", label: "繁體中文" },
  ];

  const REASONING_OPTIONS: readonly SegOption<"default" | "medium" | "high">[] =
    [
      {
        value: "default",
        label: t("morning_briefing.schedule_editor.reasoning_default"),
      },
      {
        value: "medium",
        label: t("morning_briefing.schedule_editor.reasoning_medium"),
      },
      {
        value: "high",
        label: t("morning_briefing.schedule_editor.reasoning_high"),
      },
    ];
  const reasoningValue: "default" | "medium" | "high" =
    draft.reasoning_effort ?? "default";

  const sortedTemplates = [...templates].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const sortedInstructions = [...instructions].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  function handleModel(sel: MbModelSelection | null) {
    if (!sel) return;
    onChange({ provider_kind: sel.provider_kind, model: sel.model });
  }

  async function handleUploadMarkdown(name: string, markdown: string) {
    const created = await createTemplate({ name, source_markdown: markdown });
    onChange({ template_id: created.id });
    setUploadOpen(false);
  }

  async function handleUploadFile(name: string, file: File) {
    const created = await uploadTemplate(name, file);
    onChange({ template_id: created.id });
    setUploadOpen(false);
  }

  async function handleDeleteTemplate(tpl: MbTemplate) {
    if (tpl.is_builtin) return;
    await removeTemplate(tpl.id);
    if (draft.template_id === tpl.id) onChange({ template_id: "freeform" });
  }

  async function handleUploadInstructions(name: string, file: File) {
    const created = await uploadInstructions(name, file);
    onChange({ instructions_id: created.id });
    setInstructionsOpen(false);
  }

  async function handleDeleteInstructions(ins: MbInstructions) {
    if (ins.is_builtin) return;
    if (
      !window.confirm(
        t("morning_briefing.schedule_editor.instructions_delete_confirm"),
      )
    ) {
      return;
    }
    await removeInstructions(ins.id);
    if (draft.instructions_id === ins.id) onChange({ instructions_id: null });
  }

  const isWebSearchSource = (s: MbDataSource) =>
    s.routing === "model_native" || s.key === "model_web_search";

  function sourceEnabled(s: MbDataSource): boolean {
    return isWebSearchSource(s)
      ? draft.web_search
      : draft.provider_ids.includes(s.key);
  }

  function toggleSource(s: MbDataSource): void {
    if (isWebSearchSource(s)) {
      onChange({ web_search: !draft.web_search });
      return;
    }
    const has = draft.provider_ids.includes(s.key);
    onChange({
      provider_ids: has
        ? draft.provider_ids.filter((k) => k !== s.key)
        : [...draft.provider_ids, s.key],
    });
  }

  function reasonText(s: MbDataSource): string | null {
    if (s.available || !s.unavailable_reason) return null;
    const key = `morning_briefing.schedule_editor.ds_reason_${s.unavailable_reason}`;
    const resolved = t(key);
    return resolved !== key
      ? resolved
      : t("morning_briefing.schedule_editor.ds_reason_unknown");
  }

  function categoryLabel(category: string): string {
    const key = `morning_briefing.schedule_editor.ds_category_${category}`;
    const resolved = t(key);
    return resolved !== key ? resolved : category;
  }

  function renderSource(s: MbDataSource) {
    const reason = reasonText(s);
    const label = (
      <span className="flex items-center gap-2">
        <span>{s.display_name}</span>
        <span className="inline-flex items-center rounded-full bg-[--color-surface-hover] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.06em] text-[--color-text-tertiary]">
          {categoryLabel(s.category)}
        </span>
      </span>
    );
    return (
      <div key={s.key}>
        <MbToggle
          on={sourceEnabled(s) && s.available}
          onClick={() => toggleSource(s)}
          testId={`mb-connector-${s.key}`}
          label={label}
          ariaLabel={s.display_name}
          disabled={!s.available}
        />
        {reason ? (
          <p className="px-4 pb-3 -mt-1 text-[12px] text-[--color-text-tertiary] leading-[1.4]">
            {reason}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="[&>section]:border-b [&>section]:border-[--color-border-subtle] [&>section]:py-5 [&>section:first-child]:pt-0 [&>section:last-child]:border-b-0 [&>section:last-child]:pb-0">
      {/* Model */}
      <section>
        <MbSectionHeader
          label={t("morning_briefing.schedule_editor.model_title")}
        />
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.model_hint")}
        </p>
        <MbModelPicker
          onChange={handleModel}
          value={{ provider_kind: draft.provider_kind, model: draft.model }}
        />
      </section>

      {/* Template */}
      <section>
        <div className="mb-[10px] flex items-center justify-between">
          <MbSectionHeader
            label={t("morning_briefing.schedule_editor.template_title")}
          />
          <UploadPill
            onClick={() => setUploadOpen(true)}
            testId="mb-template-upload-open"
            label={t("morning_briefing.schedule_editor.template_upload")}
          />
        </div>
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-[10px]">
          {t("morning_briefing.schedule_editor.template_hint")}
        </p>
        <div data-testid="mb-template-select" className="flex flex-col gap-[4px]">
          <OptionRow
            active={draft.template_id === "freeform"}
            onClick={() => onChange({ template_id: "freeform" })}
            testId="mb-template-option-freeform"
            title={t("morning_briefing.schedule_editor.template_freeform")}
            sublabel={t(
              "morning_briefing.schedule_editor.template_freeform_sublabel",
            )}
          />
          {sortedTemplates.map((tpl) => (
            <OptionRow
              key={tpl.id}
              active={draft.template_id === tpl.id}
              onClick={() => onChange({ template_id: tpl.id })}
              testId={`mb-template-option-${tpl.id}`}
              title={tpl.name}
              sublabel={
                tpl.is_builtin
                  ? t("morning_briefing.schedule_editor.template_builtin")
                  : t("morning_briefing.schedule_editor.template_uploaded")
              }
              onDelete={
                tpl.is_builtin
                  ? undefined
                  : () => void handleDeleteTemplate(tpl)
              }
              deleteAria={t(
                "morning_briefing.schedule_editor.template_delete_aria",
              )}
            />
          ))}
        </div>
        {draft.template_id === "freeform" ? (
          <p
            data-testid="mb-template-freeform-hint"
            className="mt-3 text-[12px] text-[--color-text-tertiary] leading-[1.5]"
          >
            {t("morning_briefing.schedule_editor.template_freeform_hint")}
          </p>
        ) : null}
      </section>

      {/* Instructions */}
      <section>
        <div className="mb-[10px] flex items-center justify-between">
          <MbSectionHeader
            label={t("morning_briefing.schedule_editor.instructions_title")}
          />
          <UploadPill
            onClick={() => setInstructionsOpen(true)}
            testId="mb-instructions-upload-open"
            label={t("morning_briefing.schedule_editor.instructions_upload")}
          />
        </div>
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-[10px]">
          {t("morning_briefing.schedule_editor.instructions_hint")}
        </p>
        <div
          data-testid="mb-instructions-select"
          className="flex flex-col gap-[4px]"
        >
          <OptionRow
            active={draft.instructions_id === null}
            onClick={() => onChange({ instructions_id: null })}
            testId="mb-instructions-option-none"
            title={t("morning_briefing.schedule_editor.instructions_none")}
          />
          {sortedInstructions.map((ins) => (
            <OptionRow
              key={ins.id}
              active={draft.instructions_id === ins.id}
              onClick={() => onChange({ instructions_id: ins.id })}
              testId={`mb-instructions-option-${ins.id}`}
              title={ins.name}
              sublabel={
                ins.is_builtin
                  ? t("morning_briefing.schedule_editor.instructions_builtin")
                  : t("morning_briefing.schedule_editor.instructions_uploaded")
              }
              onDelete={
                ins.is_builtin
                  ? undefined
                  : () => void handleDeleteInstructions(ins)
              }
              deleteAria={t(
                "morning_briefing.schedule_editor.instructions_delete_aria",
              )}
            />
          ))}
        </div>
      </section>

      {/* Connectors */}
      <section>
        <MbSectionHeader
          label={t("morning_briefing.schedule_editor.connectors_title")}
        />
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.connectors_hint")}
        </p>
        {sources && sources.length === 0 ? (
          <p
            data-testid="mb-data-sources-empty"
            className="text-[13px] text-[--color-text-tertiary] leading-[1.5] border border-[--color-border-subtle] rounded-lg px-4 py-3"
          >
            {t("morning_briefing.schedule_editor.ds_empty")}
          </p>
        ) : (
          <div className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
            {(sources ?? []).map((s) => renderSource(s))}
          </div>
        )}
      </section>

      {/* Length */}
      <section>
        <MbSectionHeader
          label={t("morning_briefing.schedule_editor.length_title")}
        />
        <MbSegmented
          ariaLabel={t("morning_briefing.schedule_editor.length_aria")}
          value={draft.length as MbReportLength}
          options={LENGTH_OPTIONS}
          onChange={(v) => onChange({ length: v })}
          testId="mb-length-select"
        />
      </section>

      {/* Language */}
      <section>
        <MbSectionHeader
          label={t("morning_briefing.schedule_editor.language_title")}
        />
        <MbSegmented
          ariaLabel={t("morning_briefing.schedule_editor.language_title")}
          value={draft.language as "en" | "zh-Hant"}
          options={LANGUAGE_OPTIONS}
          onChange={(v) => onChange({ language: v })}
          testId="mb-language-select"
        />
      </section>

      {/* Reasoning effort — Anthropic only */}
      {draft.provider_kind === "anthropic" ? (
        <section>
          <MbSectionHeader
            label={t("morning_briefing.schedule_editor.reasoning_title")}
          />
          <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-[10px]">
            {t("morning_briefing.schedule_editor.reasoning_hint")}
          </p>
          <MbSegmented
            ariaLabel={t("morning_briefing.schedule_editor.reasoning_title")}
            value={reasoningValue}
            options={REASONING_OPTIONS}
            onChange={(v) =>
              onChange({
                reasoning_effort: (v === "default"
                  ? null
                  : v) as MbReasoningEffort,
              })
            }
            testId="mb-reasoning-select"
          />
        </section>
      ) : null}

      <MbTemplateUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploadMarkdown={handleUploadMarkdown}
        onUploadFile={handleUploadFile}
      />

      <MbInstructionsUploadModal
        open={instructionsOpen}
        onClose={() => setInstructionsOpen(false)}
        onUpload={handleUploadInstructions}
      />
    </div>
  );
}
```

Notes:
- `mbSectionTitle` is intentionally removed (replaced by `MbSectionHeader`).
- The upload sub-modals are NOT `<section>` elements, so the `[&>section]`
  divider rules never style them.
- Delete buttons now use `--color-feedback-error` (the old code used the
  undefined `--color-feedback-danger`, so its hover color was dead).

- [ ] **Step 5: Update `ScheduleEditorModal` to drop `mbSectionTitle`**

In `frontend/src/components/morning-briefing/ScheduleEditorModal.tsx`, change the
import block:

```tsx
import {
  MbConfigFields,
  MbToggle,
  isBriefEmpty,
  mbSectionTitle,
} from "./MbConfigFields";
```

to:

```tsx
import {
  MbConfigFields,
  MbSectionHeader,
  MbToggle,
  isBriefEmpty,
} from "./MbConfigFields";
```

Then replace the timing section's header line (inside the Timing `<section>`):

```tsx
              {mbSectionTitle(t("morning_briefing.schedule_editor.timing_title"))}
```

with:

```tsx
              <MbSectionHeader
                label={t("morning_briefing.schedule_editor.timing_title")}
              />
```

(Leave the rest of `ScheduleEditorModal` untouched in this task — the Dialog
shell + error-token fixes happen in Task 5.)

- [ ] **Step 6: Run the affected tests**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbConfigFields.test.tsx src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx src/components/morning-briefing/__tests__/ScheduleEditorModal.test.tsx`
Expected: PASS (all three files). The `"renders the config controls"` /
`"renders both…"` tests still pass because `mb-template-select`,
`mb-instructions-select`, and `mb-language-select` remain as container/group
testids.

- [ ] **Step 7: Typecheck**

Run: `cd frontend && npm run lint`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/morning-briefing/MbConfigFields.tsx \
        frontend/src/components/morning-briefing/ScheduleEditorModal.tsx \
        frontend/src/components/morning-briefing/__tests__/MbConfigFields.test.tsx \
        frontend/src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx \
        frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(morning-briefing): rebuild MbConfigFields to ER settings parity"
```

---

## Task 5: ER modal-shell chrome for both MB modals

**Files:**
- Modify: `frontend/src/components/morning-briefing/MbRunNowModal.tsx`
- Modify: `frontend/src/components/morning-briefing/ScheduleEditorModal.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/zh-TW.json`

Existing modal tests assert behavior + testids only (not classNames), so they
keep passing. Verify at the end.

- [ ] **Step 1: Add the Run Now eyebrow i18n key**

In `frontend/src/i18n/locales/en.json`, inside
`morning_briefing.run_now_modal`, add:

```json
"eyebrow": "Morning Briefing",
```

In `frontend/src/i18n/locales/zh-TW.json`, inside
`morning_briefing.run_now_modal`, add:

```json
"eyebrow": "晨間簡報",
```

- [ ] **Step 2: Restyle the `MbRunNowModal` shell**

In `frontend/src/components/morning-briefing/MbRunNowModal.tsx`:

Replace the overlay:

```tsx
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
```

with:

```tsx
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(13,13,11,0.45)]" />
```

Replace the content className:

```tsx
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] shadow-lg flex flex-col overflow-hidden">
```

with:

```tsx
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[14px] shadow-[0_16px_40px_rgba(13,13,11,0.18)] flex flex-col overflow-hidden">
```

Replace the header (the whole `<header>…</header>` block):

```tsx
          <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle] flex-shrink-0">
            <div>
              <Dialog.Title asChild>
                <h2 className="text-[15px] font-semibold text-[--color-text-primary] m-0">
                  {t("morning_briefing.run_now_modal.title")}
                </h2>
              </Dialog.Title>
              <Dialog.Description asChild>
                <p className="text-[12px] text-[--color-text-tertiary] m-0">
                  {t("morning_briefing.run_now_modal.description")}
                </p>
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label={t("morning_briefing.run_now_modal.cancel")}
                className="text-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={16} />
              </button>
            </Dialog.Close>
          </header>
```

with:

```tsx
          <header className="flex items-start justify-between px-[22px] py-[18px] border-b border-[--color-border-subtle] flex-shrink-0">
            <div>
              <div className="flex items-center gap-3">
                <Dialog.Title asChild>
                  <h2 className="text-[16px] font-semibold tracking-[-0.005em] text-[--color-text-primary] m-0">
                    {t("morning_briefing.run_now_modal.title")}
                  </h2>
                </Dialog.Title>
                <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                  {t("morning_briefing.run_now_modal.eyebrow")}
                </span>
              </div>
              <Dialog.Description asChild>
                <p className="mt-1 text-[12px] text-[--color-text-tertiary] m-0">
                  {t("morning_briefing.run_now_modal.description")}
                </p>
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label={t("morning_briefing.run_now_modal.cancel")}
                className="ml-3 inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={14} strokeWidth={2} />
              </button>
            </Dialog.Close>
          </header>
```

Replace the footer opening tag:

```tsx
          <footer className="flex items-center justify-end gap-3 px-5 h-14 border-t border-[--color-border-subtle] flex-shrink-0">
```

with:

```tsx
          <footer className="flex items-center justify-end gap-3 px-[22px] py-[14px] rounded-b-[14px] border-t border-[--color-border-subtle] bg-[--color-bg-base] flex-shrink-0">
```

- [ ] **Step 3: Restyle the `ScheduleEditorModal` shell + fix dead error token**

In `frontend/src/components/morning-briefing/ScheduleEditorModal.tsx`:

Replace the overlay:

```tsx
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
```

with:

```tsx
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(13,13,11,0.45)]" />
```

Replace the content className:

```tsx
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] shadow-lg flex flex-col overflow-hidden">
```

with:

```tsx
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[14px] shadow-[0_16px_40px_rgba(13,13,11,0.18)] flex flex-col overflow-hidden">
```

Replace the header opening tag:

```tsx
          <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle] flex-shrink-0">
```

with:

```tsx
          <header className="flex items-center justify-between px-[22px] py-[18px] border-b border-[--color-border-subtle] flex-shrink-0">
```

Replace the close button:

```tsx
              <button
                type="button"
                aria-label={t("morning_briefing.schedule_editor.close_aria")}
                className="text-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={16} />
              </button>
```

with:

```tsx
              <button
                type="button"
                aria-label={t("morning_briefing.schedule_editor.close_aria")}
                className="ml-3 inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={14} strokeWidth={2} />
              </button>
```

Replace the footer opening tag:

```tsx
          <footer className="flex items-center justify-end gap-3 px-5 h-14 border-t border-[--color-border-subtle] flex-shrink-0">
```

with:

```tsx
          <footer className="flex items-center justify-end gap-3 px-[22px] py-[14px] rounded-b-[14px] border-t border-[--color-border-subtle] bg-[--color-bg-base] flex-shrink-0">
```

Fix the two dead error-color tokens. Replace the no-days error paragraph:

```tsx
                  <p
                    data-testid="mb-schedule-no-days"
                    className="mt-2 text-[12px] text-[--color-feedback-danger]"
                  >
```

with:

```tsx
                  <p
                    data-testid="mb-schedule-no-days"
                    className="mt-2 text-[12px] text-[--color-feedback-error]"
                  >
```

And replace the both-empty error paragraph:

```tsx
              <p
                data-testid="mb-both-empty-error"
                className="mr-auto text-[12px] text-[--color-feedback-danger] leading-[1.4]"
              >
```

with:

```tsx
              <p
                data-testid="mb-both-empty-error"
                className="mr-auto text-[12px] text-[--color-feedback-error] leading-[1.4]"
              >
```

- [ ] **Step 4: Typecheck + run both modal test files**

Run: `cd frontend && npm run lint`
Expected: no errors.

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx src/components/morning-briefing/__tests__/ScheduleEditorModal.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/morning-briefing/MbRunNowModal.tsx \
        frontend/src/components/morning-briefing/ScheduleEditorModal.tsx \
        frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(morning-briefing): align modal shells to ER chrome"
```

---

## Task 6: Polish `MbSchedulesView`

**Files:**
- Modify: `frontend/src/components/morning-briefing/MbSchedulesView.tsx` (full rewrite)
- Create: `frontend/src/components/morning-briefing/__tests__/MbSchedulesView.test.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/morning-briefing/__tests__/MbSchedulesView.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MbSchedule } from "../../../api/morning-briefing";
import { MbSchedulesView } from "../MbSchedulesView";

function makeSchedule(over: Partial<MbSchedule> = {}): MbSchedule {
  return {
    id: "s1",
    time: "07:00",
    timezone: "America/New_York",
    days_of_week: ["mon", "tue", "wed", "thu", "fri"],
    label: "Pre-Market",
    is_enabled: true,
    template_id: "freeform",
    instructions_id: null,
    enabled_connectors: { provider_ids: [], web_search: false },
    provider_kind: null,
    model: null,
    language: "en",
    length: "normal",
    reasoning_effort: null,
    web_search: false,
    ...over,
  };
}

describe("MbSchedulesView", () => {
  it("renders an empty state with an add CTA when there are no schedules", () => {
    const onAdd = vi.fn();
    render(
      <MbSchedulesView
        schedules={[]}
        onBack={vi.fn()}
        onAdd={onAdd}
        onEdit={vi.fn()}
        onRemove={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    expect(screen.getByTestId("mb-schedules-empty")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("mb-schedules-empty-add"));
    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it("renders a schedule row and routes Edit", () => {
    const onEdit = vi.fn();
    render(
      <MbSchedulesView
        schedules={[makeSchedule()]}
        onBack={vi.fn()}
        onAdd={vi.fn()}
        onEdit={onEdit}
        onRemove={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    expect(screen.getByTestId("mb-schedule-row")).toBeInTheDocument();
    expect(screen.getByText("Pre-Market")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("mb-schedule-edit-s1"));
    expect(onEdit).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbSchedulesView.test.tsx`
Expected: FAIL — `mb-schedules-empty` / `mb-schedule-edit-s1` not found (current view uses different markup).

- [ ] **Step 3: Add i18n keys**

In `frontend/src/i18n/locales/en.json`, inside `morning_briefing.schedules`, add:

```json
"eyebrow": "Schedules",
"enabled_badge": "Enabled",
```

In `frontend/src/i18n/locales/zh-TW.json`, inside `morning_briefing.schedules`, add:

```json
"eyebrow": "排程",
"enabled_badge": "已啟用",
```

(Reuses existing `schedules.back`, `schedules.title`, `schedules.add`,
`schedules.empty`, `schedules.next_run`, `schedules.edit`,
`schedules.disabled_badge`, `schedules.delete_aria`, and the `days.*` keys.)

- [ ] **Step 4: Rewrite `MbSchedulesView.tsx`**

Replace the ENTIRE contents of
`frontend/src/components/morning-briefing/MbSchedulesView.tsx` with:

```tsx
/**
 * MbSchedulesView — full-screen list of Morning Briefing schedules.
 *
 * Lists each schedule with its next fire time (via formatNextBriefing),
 * day-of-week chips, enabled state, and edit / delete affordances. "New
 * schedule" and per-row "Edit" open the ScheduleEditorModal (owned by the
 * parent page). Chrome mirrors the EU/ER overlay views.
 */
import { useState } from "react";
import { CalendarClock, ChevronLeft, Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbDayOfWeek, MbSchedule } from "../../api/morning-briefing";
import { formatNextBriefing } from "../../lib/morning-briefing/next-briefing";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

interface Props {
  schedules: MbSchedule[];
  onBack: () => void;
  onAdd: () => void;
  onEdit: (schedule: MbSchedule) => void;
  onRemove: (id: string) => Promise<void>;
}

const DAY_ORDER: readonly MbDayOfWeek[] = [
  "mon",
  "tue",
  "wed",
  "thu",
  "fri",
  "sat",
  "sun",
];

export function MbSchedulesView({
  schedules,
  onBack,
  onAdd,
  onEdit,
  onRemove,
}: Props) {
  const { t } = useTranslation();
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null);

  return (
    <div
      className="fixed inset-0 bg-[--color-bg-base] z-50 overflow-y-auto"
      data-testid="mb-schedules"
    >
      <header className="flex items-center justify-between h-14 px-4 sm:px-6 border-b border-[--color-border-subtle]">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors"
        >
          <ChevronLeft size={14} /> {t("morning_briefing.schedules.back")}
        </button>
        <div className="flex flex-col items-center">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            {t("morning_briefing.schedules.eyebrow")}
          </span>
          <h2 className="text-[16px] font-semibold text-[--color-text-primary] m-0">
            {t("morning_briefing.schedules.title")}
          </h2>
        </div>
        <button
          type="button"
          onClick={onAdd}
          data-testid="mb-schedules-add"
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors"
        >
          <Plus size={13} /> {t("morning_briefing.schedules.add")}
        </button>
      </header>

      <div className="max-w-[800px] mx-auto px-4 sm:px-6 py-6">
        {schedules.length === 0 ? (
          <div
            data-testid="mb-schedules-empty"
            className="flex flex-col items-center justify-center text-center py-20 px-6 border border-dashed border-[--color-border-subtle] rounded-[12px] bg-[--color-bg-elevated]"
          >
            <div
              aria-hidden="true"
              className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] bg-[--color-accent-primary] text-[--color-accent-on] shadow-[0_0_24px_rgba(212,255,0,0.35)]"
            >
              <CalendarClock size={24} strokeWidth={1.6} />
            </div>
            <p className="text-[14px] text-[--color-text-secondary] max-w-[420px] m-0 mb-5 leading-[1.5]">
              {t("morning_briefing.schedules.empty")}
            </p>
            <button
              type="button"
              onClick={onAdd}
              data-testid="mb-schedules-empty-add"
              className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors"
            >
              <Plus size={14} /> {t("morning_briefing.schedules.add")}
            </button>
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {schedules.map((s) => {
              const days = DAY_ORDER.filter((d) =>
                (s.days_of_week as MbDayOfWeek[]).includes(d),
              );
              return (
                <li
                  key={s.id}
                  data-testid="mb-schedule-row"
                  className="group relative flex items-center gap-3 pl-5 pr-4 py-3.5 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px] hover:border-[--color-border-strong] hover:-translate-y-0.5 transition-[transform,border-color] duration-[--duration-normal]"
                >
                  <span
                    aria-hidden="true"
                    className={[
                      "absolute left-0 top-2 bottom-2 w-[3px] rounded-full",
                      s.is_enabled
                        ? "bg-[--color-accent-primary]"
                        : "bg-transparent",
                    ].join(" ")}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[14px] tabular-nums text-[--color-text-primary]">
                        {s.time}
                      </span>
                      <span className="text-[13px] text-[--color-text-secondary] truncate">
                        {s.label}
                      </span>
                      {s.is_enabled ? (
                        <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-feedback-success]">
                          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
                          {t("morning_briefing.schedules.enabled_badge")}
                        </span>
                      ) : (
                        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary] border border-[--color-border-subtle] rounded px-1.5 py-px">
                          {t("morning_briefing.schedules.disabled_badge")}
                        </span>
                      )}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1">
                      {days.map((d) => (
                        <span
                          key={d}
                          className="inline-flex items-center justify-center h-5 min-w-[28px] px-1 rounded font-mono text-[10px] uppercase tracking-[0.06em] text-[--color-text-secondary] bg-[--color-surface-hover]"
                        >
                          {t(`morning_briefing.days.${d}`)}
                        </span>
                      ))}
                    </div>
                    <p className="text-[12px] text-[--color-text-tertiary] m-0 mt-1.5">
                      {t("morning_briefing.schedules.next_run", {
                        when: formatNextBriefing(s),
                      })}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onEdit(s)}
                    data-testid={`mb-schedule-edit-${s.id}`}
                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors"
                  >
                    <Pencil size={13} /> {t("morning_briefing.schedules.edit")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingRemoval(s.id)}
                    aria-label={t("morning_briefing.schedules.delete_aria")}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover] transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={pendingRemoval !== null}
        title={t("morning_briefing.schedules.remove_title")}
        description={t("morning_briefing.schedules.remove_description")}
        confirmLabel={t("morning_briefing.schedules.remove_confirm")}
        destructive
        onCancel={() => setPendingRemoval(null)}
        onConfirm={() => {
          const id = pendingRemoval;
          setPendingRemoval(null);
          if (id) void onRemove(id);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 5: Run test + typecheck**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbSchedulesView.test.tsx`
Expected: PASS (2 tests).

Run: `cd frontend && npm run lint`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/morning-briefing/MbSchedulesView.tsx \
        frontend/src/components/morning-briefing/__tests__/MbSchedulesView.test.tsx \
        frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(morning-briefing): polish schedules view rows + chrome"
```

---

## Task 7: Polish `MbCabinetView`

**Files:**
- Modify: `frontend/src/components/morning-briefing/MbCabinetView.tsx` (full rewrite)
- Create: `frontend/src/components/morning-briefing/__tests__/MbCabinetView.test.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/morning-briefing/__tests__/MbCabinetView.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MbCabinetView } from "../MbCabinetView";

const noop = vi.fn().mockResolvedValue(undefined);

const STAMP = "2026-06-01T00:00:00Z";

function renderCabinet() {
  render(
    <MbCabinetView
      templates={[
        {
          id: "t1",
          name: "Builtin Tpl",
          is_builtin: true,
          created_at: STAMP,
          updated_at: STAMP,
        },
        {
          id: "t2",
          name: "My Tpl",
          is_builtin: false,
          created_at: STAMP,
          updated_at: STAMP,
        },
      ]}
      instructions={[]}
      onBack={vi.fn()}
      onUploadTemplateMarkdown={noop}
      onUploadTemplateFile={noop}
      onUploadInstructions={noop}
      onRemoveTemplate={noop}
      onRemoveInstructions={noop}
    />,
  );
}

describe("MbCabinetView", () => {
  it("renders template rows with a built-in badge and an upload trigger", () => {
    renderCabinet();
    expect(screen.getByText("Builtin Tpl")).toBeInTheDocument();
    expect(screen.getByText("My Tpl")).toBeInTheDocument();
    expect(
      screen.getByTestId("mb-cabinet-upload-template"),
    ).toBeInTheDocument();
  });

  it("opens the delete confirm for a user template", () => {
    renderCabinet();
    fireEvent.click(screen.getByTestId("mb-cabinet-delete-template-t2"));
    expect(screen.getByText("My Tpl")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbCabinetView.test.tsx`
Expected: FAIL — `mb-cabinet-delete-template-t2` not found (current rows use an unkeyed delete button).

- [ ] **Step 3: Add i18n keys**

In `frontend/src/i18n/locales/en.json`, inside `morning_briefing.library`, add:

```json
"eyebrow": "Library",
```

In `frontend/src/i18n/locales/zh-TW.json`, inside `morning_briefing.library`, add:

```json
"eyebrow": "資料庫",
```

(Reuses existing `library.back`, `library.title`, `library.templates_heading`,
`library.instructions_heading`, `library.upload_template`,
`library.upload_instructions`, `library.empty_templates`,
`library.empty_instructions`, `library.builtin_badge`, `library.delete_aria`,
and the remove-confirm keys.)

- [ ] **Step 4: Rewrite `MbCabinetView.tsx`**

Replace the ENTIRE contents of
`frontend/src/components/morning-briefing/MbCabinetView.tsx` with:

```tsx
/**
 * MbCabinetView — Morning Briefing template + instructions library.
 *
 * Lists built-in and user templates / instruction profiles, supports
 * uploading new ones and deleting user-owned entries. Full-screen overlay
 * whose chrome mirrors the EU/ER overlay views (back button + mono eyebrow,
 * icon'd section headers, dashed upload pills, hover rows, dashed-card empty
 * states).
 */
import { useState } from "react";
import {
  ChevronLeft,
  FileText,
  ListChecks,
  Trash2,
  Upload,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbInstructions, MbTemplate } from "../../api/morning-briefing";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

import { MbInstructionsUploadModal } from "./MbInstructionsUploadModal";
import { MbTemplateUploadModal } from "./MbTemplateUploadModal";

interface Props {
  templates: MbTemplate[];
  instructions: MbInstructions[];
  onBack: () => void;
  onUploadTemplateMarkdown: (name: string, markdown: string) => Promise<void>;
  onUploadTemplateFile: (name: string, file: File) => Promise<void>;
  onUploadInstructions: (name: string, file: File) => Promise<void>;
  onRemoveTemplate: (id: string) => Promise<void>;
  onRemoveInstructions: (id: string) => Promise<void>;
}

type PendingDelete =
  | { kind: "template"; id: string }
  | { kind: "instructions"; id: string }
  | null;

export function MbCabinetView({
  templates,
  instructions,
  onBack,
  onUploadTemplateMarkdown,
  onUploadTemplateFile,
  onUploadInstructions,
  onRemoveTemplate,
  onRemoveInstructions,
}: Props) {
  const { t } = useTranslation();
  const [templateUploadOpen, setTemplateUploadOpen] = useState(false);
  const [instructionsUploadOpen, setInstructionsUploadOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);

  const sortedTemplates = [...templates].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const sortedInstructions = [...instructions].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  const removeTitle =
    pendingDelete?.kind === "instructions"
      ? t("morning_briefing.library.remove_instructions_title")
      : t("morning_briefing.library.remove_template_title");

  return (
    <div
      className="fixed inset-0 bg-[--color-bg-base] z-50 overflow-y-auto"
      data-testid="mb-cabinet"
    >
      <header className="flex items-center justify-between h-14 px-4 sm:px-6 border-b border-[--color-border-subtle]">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors"
        >
          <ChevronLeft size={14} /> {t("morning_briefing.library.back")}
        </button>
        <div className="flex flex-col items-center">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            {t("morning_briefing.library.eyebrow")}
          </span>
          <h2 className="text-[16px] font-semibold text-[--color-text-primary] m-0">
            {t("morning_briefing.library.title")}
          </h2>
        </div>
        <span className="w-[92px]" />
      </header>

      <div className="max-w-[900px] mx-auto px-4 sm:px-6 py-6">
        <CabinetSection
          icon={<FileText size={14} />}
          heading={t("morning_briefing.library.templates_heading")}
          count={sortedTemplates.length}
          uploadLabel={t("morning_briefing.library.upload_template")}
          uploadTestId="mb-cabinet-upload-template"
          onUpload={() => setTemplateUploadOpen(true)}
          emptyLabel={t("morning_briefing.library.empty_templates")}
          isEmpty={sortedTemplates.length === 0}
          className="mb-8"
        >
          {sortedTemplates.map((tpl) => (
            <CabinetRow
              key={tpl.id}
              icon={<FileText size={13} />}
              name={tpl.name}
              isBuiltin={tpl.is_builtin}
              builtinLabel={t("morning_briefing.library.builtin_badge")}
              deleteAria={t("morning_briefing.library.delete_aria")}
              deleteTestId={`mb-cabinet-delete-template-${tpl.id}`}
              onDelete={() =>
                setPendingDelete({ kind: "template", id: tpl.id })
              }
            />
          ))}
        </CabinetSection>

        <CabinetSection
          icon={<ListChecks size={14} />}
          heading={t("morning_briefing.library.instructions_heading")}
          count={sortedInstructions.length}
          uploadLabel={t("morning_briefing.library.upload_instructions")}
          uploadTestId="mb-cabinet-upload-instructions"
          onUpload={() => setInstructionsUploadOpen(true)}
          emptyLabel={t("morning_briefing.library.empty_instructions")}
          isEmpty={sortedInstructions.length === 0}
        >
          {sortedInstructions.map((ins) => (
            <CabinetRow
              key={ins.id}
              icon={<ListChecks size={13} />}
              name={ins.name}
              isBuiltin={ins.is_builtin}
              builtinLabel={t("morning_briefing.library.builtin_badge")}
              deleteAria={t("morning_briefing.library.delete_aria")}
              deleteTestId={`mb-cabinet-delete-instructions-${ins.id}`}
              onDelete={() =>
                setPendingDelete({ kind: "instructions", id: ins.id })
              }
            />
          ))}
        </CabinetSection>
      </div>

      <MbTemplateUploadModal
        open={templateUploadOpen}
        onClose={() => setTemplateUploadOpen(false)}
        onUploadMarkdown={onUploadTemplateMarkdown}
        onUploadFile={onUploadTemplateFile}
      />
      <MbInstructionsUploadModal
        open={instructionsUploadOpen}
        onClose={() => setInstructionsUploadOpen(false)}
        onUpload={onUploadInstructions}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title={removeTitle}
        description={t("morning_briefing.library.remove_description")}
        confirmLabel={t("morning_briefing.library.remove_confirm")}
        destructive
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          const target = pendingDelete;
          setPendingDelete(null);
          if (!target) return;
          if (target.kind === "template") void onRemoveTemplate(target.id);
          else void onRemoveInstructions(target.id);
        }}
      />
    </div>
  );
}

function CabinetSection({
  icon,
  heading,
  count,
  uploadLabel,
  uploadTestId,
  onUpload,
  emptyLabel,
  isEmpty,
  className = "",
  children,
}: {
  icon: React.ReactNode;
  heading: string;
  count: number;
  uploadLabel: string;
  uploadTestId: string;
  onUpload: () => void;
  emptyLabel: string;
  isEmpty: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={className}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="inline-flex items-center gap-2 text-[15px] font-semibold text-[--color-text-primary]">
          <span className="text-[--color-text-secondary]">{icon}</span>
          {heading}
          <span className="font-mono text-[11px] tabular-nums text-[--color-text-tertiary]">
            {count}
          </span>
        </h3>
        <button
          type="button"
          onClick={onUpload}
          data-testid={uploadTestId}
          className="inline-flex items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[10px] py-[5px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-solid hover:border-[--color-feedback-success] hover:text-[--color-feedback-success] transition-colors"
        >
          <Upload size={11} strokeWidth={2} /> {uploadLabel}
        </button>
      </div>
      {isEmpty ? (
        <p className="text-[13px] text-[--color-text-tertiary] border border-dashed border-[--color-border-subtle] rounded-[12px] bg-[--color-bg-elevated] px-4 py-8 text-center">
          {emptyLabel}
        </p>
      ) : (
        <ul className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
          {children}
        </ul>
      )}
    </section>
  );
}

function CabinetRow({
  icon,
  name,
  isBuiltin,
  builtinLabel,
  deleteAria,
  deleteTestId,
  onDelete,
}: {
  icon: React.ReactNode;
  name: string;
  isBuiltin: boolean;
  builtinLabel: string;
  deleteAria: string;
  deleteTestId: string;
  onDelete: () => void;
}) {
  return (
    <li className="flex items-center gap-3 px-4 py-3 bg-[--color-bg-elevated] hover:bg-[--color-surface-hover] transition-colors">
      <span className="text-[--color-text-tertiary]">{icon}</span>
      <span className="flex-1 text-[14px] text-[--color-text-primary] truncate">
        {name}
      </span>
      {isBuiltin ? (
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary] border border-[--color-border-subtle] rounded px-1.5 py-px">
          {builtinLabel}
        </span>
      ) : (
        <button
          type="button"
          onClick={onDelete}
          aria-label={deleteAria}
          data-testid={deleteTestId}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover] transition-colors"
        >
          <Trash2 size={14} />
        </button>
      )}
    </li>
  );
}
```

- [ ] **Step 5: Run test + typecheck**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MbCabinetView.test.tsx`
Expected: PASS (2 tests).

Run: `cd frontend && npm run lint`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/morning-briefing/MbCabinetView.tsx \
        frontend/src/components/morning-briefing/__tests__/MbCabinetView.test.tsx \
        frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(morning-briefing): polish library/cabinet view"
```

---

## Task 8: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire frontend test suite**

Run: `cd frontend && npm test`
Expected: PASS — all suites green (MB suites plus the rest of the app).

- [ ] **Step 2: Production build (typecheck + bundle)**

Run: `cd frontend && npm run build`
Expected: `tsc -b` clean, Vite build succeeds, no errors.

- [ ] **Step 3: Confirm no `--color-feedback-danger` remains in MB code**

Run: `cd frontend && grep -rn "feedback-danger" src/components/morning-briefing src/pages/departments/MorningBriefing.tsx || echo "clean"`
Expected: `clean` (every MB danger token is now `--color-feedback-error`).

- [ ] **Step 4: Manual browser smoke (optional but recommended)**

Start the app (`cd frontend && npm run dev`, backend on :8080 per project
defaults) and visually confirm against EU/ER:
- Populated page shows the hero (3 stats) above the search row; feed unchanged.
- Empty page shows the dashed card with glowing icon + Run Now / Open Library.
- Run Now + Schedule Editor modals: rounded-14 shell, eyebrow header, card-list
  template/instructions pickers, Segmented length/language/reasoning.
- Schedules view: accent rows, day chips, enabled pulse dot, hover lift; empty
  card with CTA.
- Library view: icon'd section headers with counts, dashed upload pills, row
  hover, dashed empty cards.

- [ ] **Step 5: (Optional) open a PR**

```bash
git push -u origin feat/mb-design-parity
```
Then open a PR from `feat/mb-design-parity` into `main`.

---

## Self-Review (completed during authoring)

**Spec coverage:** A (hero) → Task 1+3; B (empty page) → Task 2+3; C (feed-top
cleanup) → Task 3; D (schedules) → Task 6; E (cabinet) → Task 7; F (config
fields incl. card-list pickers + segmented + mono headers) → Task 4; G (modal
shells) → Task 5. Out-of-scope items (feed cards, streaming, backend) are not
touched. All covered.

**Placeholder scan:** No TBD/TODO/"handle edge cases". Every code step shows
complete code or an exact old→new replacement.

**Type/name consistency:** `MbConfigDraft`, `isBriefEmpty`, `MbToggle`,
`MbSectionHeader`, `MbSegmented` exports are defined in Task 4 and consumed in
Tasks 4/5. Picker container testids (`mb-template-select`,
`mb-instructions-select`, `mb-language-select`) are preserved so Task 4's
unchanged existence-assertions keep passing. `pickEarliestNextBriefing`,
`formatNextBriefing`, `groupReports`, and the `MbSchedule` / `MbDayOfWeek` /
`MbTemplate` / `MbInstructions` types are all real exports verified against the
codebase.
