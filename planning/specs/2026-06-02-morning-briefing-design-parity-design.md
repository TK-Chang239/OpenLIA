# Design: Morning Briefing visual parity with Earnings Update / Equity Research

Date: 2026-06-02
Status: Approved (brainstorm)
Surface: Morning Briefing department page

## Problem

The Morning Briefing page reads as visually "cheap" next to Earnings Update
(EU) and Equity Research v3 (ER) — the two pages the team treats as the
quality bar. The feed body is fine (`MbBigCard` / `MbReportRow` /
`MbGeneratingCard` are already EU clones), but everything *around* the feed is
under-finished:

- **No top-of-page anchor.** EU opens with `EuHero` (eyebrow + 38px headline +
  three stat cards). ER opens with `WelcomeStage`. MB jumps straight from the
  52px header into a lone, right-floated search input.
- **Bare empty state.** MB's empty state is a centered `h2` + `p` + button at
  `py-24` — no card framing, no icon. EU's `EuEmptyPage` is a dashed-border
  `bg-elevated` card; ER's welcome has a glowing icon block.
- **Utilitarian overlay views.** `MbSchedulesView` and `MbCabinetView` use a
  plain text "back" link, flat rows with no hover, and plain-bordered upload
  buttons.
- **Under-styled config panel.** `MbConfigFields` uses 15px-bold section
  headers, `<hr>` dividers, and plain `<select>` pickers — where ER's settings
  modal uses mono-eyebrow headers, full-bleed `border-b` sections, card-list
  pickers, and Segmented controls.
- **Plainer modal shells.** `MbRunNowModal` / `ScheduleEditorModal` use
  `rounded-[12px]`, `shadow-lg`, and a `bg-black/40` overlay vs ER's
  `rounded-[14px]`, layered shadow, eyebrow header, and `bg-base` footer.

## Goal

Bring every Morning Briefing surface up to the EU/ER finish level so the three
department pages read as one design system. Port proven EU/ER patterns; no new
dependencies, no backend or API changes, no change to streaming/run logic.

## Constraints and conventions

- **Per-department duplication is the house pattern.** EU, MB, and ER each own
  their own near-twin components (`Eu*` / `Mb*` / `V3*`). Follow it: create
  MB-local components rather than extracting shared primitives across
  departments. (`Segmented` and `SectionHeader` are currently defined locally
  inside `V3ReportSettingsModal`; MB gets its own local copies.)
- **Tokens only.** All colors/spacing/radii/shadows/motion come from the
  existing `styles/tokens.css` vocabulary. No hardcoded hex.
- **Reuse existing motion.** Page-entry uses the existing `animate-feed-fade-up`
  + staggered inline `animationDelay` already used on the feed. No new
  framer-motion usage required (EU's hero has none of its own).
- **i18n.** Every new string goes through `react-i18next` with keys added to
  both `en.json` and `zh-TW.json`, matching existing `morning_briefing.*`
  namespacing.

## What already exists (no backend work)

- `useMbRuns()` → `runs` (with `created_at`, `status`, `subject`,
  `highlights`), `useMbSchedules()` → `schedules` (with `is_enabled`, `time`,
  `label`, day fields), `useMbTemplates()`, `useMbInstructions()`,
  `useMbDataSources()`.
- `formatNextBriefing(schedule)` and `pickEarliestNextBriefing(schedules)` in
  `lib/morning-briefing/next-briefing` (the latter returns the soonest enabled
  occurrence with a `.display` string), plus the grouping helpers
  `groupReports` / `searchReports` in
  `components/morning-briefing/feed/mbFeedHelpers.ts`.
- Reference implementations to mirror: `EuHero`, `EuEmptyPage`,
  `EuFeedSection`, `EUCabinetView`, `CoverageDrawer`, and
  `V3ReportSettingsModal` (the `Segmented` + `SectionHeader` + card-list
  picker patterns).

This work is therefore **frontend-only**.

## Design

### A. New component: `MbHero`

Path: `frontend/src/components/morning-briefing/feed/MbHero.tsx`

Mirrors `EuHero`'s structure: a `grid md:grid-cols-[1fr_auto]` section with a
bottom border and `mb-6`. Shown above the feed whenever briefings exist (the
populated branch), not in the empty/loading branches.

- Left column:
  - Eyebrow: `font-mono text-[10px] tracking-[0.14em] uppercase
    text-[--color-feedback-success]` with a glowing accent dot
    (`shadow-[0_0_0_4px_rgba(var(--color-accent-primary-rgb),0.18)]`), reading
    `MORNING BRIEFING · SCHEDULED`.
  - Headline: `text-[38px] font-semibold leading-[1.05] tracking-[-0.02em]`.
  - Lede: `text-base text-[--color-text-secondary] max-w-[620px]`.
- Right column: three `Stat` cells (mono label + `text-[22px] tabular-nums`
  value), identical to `EuHero`'s `Stat`:
  - **Briefings this week** — count of `runs` with `created_at` within the last
    7 days (derive from the same grouping the feed uses; `today.length +
    thisWeek.length`).
  - **Active schedules** — `schedules.filter(s => s.is_enabled).length`.
  - **Next run** — `pickEarliestNextBriefing(schedules)?.display ?? "—"`. This
    existing helper already returns the soonest occurrence's display string and
    skips disabled schedules, so no string-sorting is needed.

Props: `{ briefingsThisWeek: number; activeSchedules: number; nextRun: string |
null }`. The page computes these (it already holds `runs`, `groups`, and
`schedules`) and passes them down, keeping `MbHero` a pure presentational unit.

### B. New component: `MbEmptyPage`

Path: `frontend/src/components/morning-briefing/feed/MbEmptyPage.tsx`

Replaces the inline `allEmpty` block in `MorningBriefing.tsx`. Mirrors
`EuEmptyPage` (dashed-border `bg-[--color-bg-elevated]` `rounded-[12px]` card,
`py-20 px-6`, centered) and borrows the small glowing-icon block from
`WelcomeStage`:

- Top: a `h-12 w-12 rounded-[14px] bg-[--color-accent-primary]
  text-[--color-accent-on] shadow-[0_0_24px_rgba(212,255,0,0.35)]` icon tile
  containing `CalendarClock`.
- `h2` title + `p` sub (existing `empty_title` / `empty_sub` keys).
- Two CTAs side by side: **Run Now** (primary, accent) and **Open Library**
  (secondary, bordered) — wired to the page's existing `setRunNowOpen` /
  `setCabinetOpen`.

Props: `{ onRunNow: () => void; onOpenLibrary: () => void }`.

### C. `MorningBriefing.tsx` wiring + feed-top cleanup

Path: `frontend/src/pages/departments/MorningBriefing.tsx`

- Populated branch: render `<MbHero …>` first (with `animate-feed-fade-up`,
  `animationDelay: "80ms"`), then the search row, then the feed sections
  (existing 160/240/320ms stagger preserved).
- Remove the `<div className="flex-1" />` spacer hack on the search row; keep
  the search input but let it sit at the start (or full-width with a max) under
  the hero so it no longer reads as orphaned.
- Empty branch: replace the inline block with `<MbEmptyPage … />`.
- Compute and pass the three hero stats (see A). Add a small helper for "soonest
  enabled next run" near `formatHeroStamp`.

### D. `MbSchedulesView` polish

Path: `frontend/src/components/morning-briefing/MbSchedulesView.tsx`

- **Header chrome:** replace the bare colored-text back link with a styled back
  button (`ChevronLeft` + label, subtle border/hover, `h-8`), left-aligned, and
  add a `font-mono text-[10px] uppercase tracking-[0.1em]
  text-[--color-text-tertiary]` eyebrow ("SCHEDULES") above the title. Keep the
  accent "Add schedule" button on the right.
- **Rows:** upgrade each `<li>` to a card with:
  - a 3px left accent bar shown for enabled schedules (mirrors `MbBigCard`);
  - the time rendered in `font-mono` prominently;
  - day-of-week chips (small bordered pills) derived from the schedule's
    `days_of_week`;
  - an enabled state shown as an `animate-live-pulse` dot (enabled) / muted
    "disabled" pill (disabled), replacing the current text-only badge;
  - hover `-translate-y-0.5` + `hover:border-[--color-border-strong]` lift and
    a `transition` (matches `MbReportRow`).
- **Empty state:** dashed-border `bg-elevated` card with a `CalendarClock` icon,
  message, and an "Add schedule" CTA (replaces the bare `<p>`).

### E. `MbCabinetView` polish

Path: `frontend/src/components/morning-briefing/MbCabinetView.tsx`

- **Header chrome:** same back button + eyebrow ("LIBRARY") treatment as D.
- **Sections:** give each section heading a small leading icon (`FileText` for
  Templates, `ListChecks` for Instructions) and an item count; keep the two-up
  Templates / Instructions structure.
- **Upload buttons:** swap the plain bordered button for ER's dashed mono
  Upload pill (`border-dashed border-[--color-border-strong] … hover:border-solid
  hover:border-[--color-feedback-success] hover:text-[--color-feedback-success]`,
  with `Upload` icon).
- **List rows:** add `hover:bg-[--color-surface-hover]` and a small leading
  icon per row; render the built-in badge as a bordered pill (consistent with
  the schedules disabled pill). Keep inline delete for user-owned items.
- **Empty states:** dashed-border cards with an icon (replace bare `<p>`s).

### F. `MbConfigFields` → ER settings parity

Path: `frontend/src/components/morning-briefing/MbConfigFields.tsx`

Shared by both `MbRunNowModal` and `ScheduleEditorModal`, so both upgrade at
once. Introduce two MB-local primitives in this file (copying
`V3ReportSettingsModal`'s shapes):

- `MbSectionHeader({ label })` — `font-mono text-[10px] uppercase
  tracking-[0.1em] text-[--color-text-tertiary]`, replacing `mbSectionTitle`
  (15px bold). `mbSectionTitle` is removed; update any importers.
- `MbSegmented<T>({ ariaLabel, value, options, onChange })` — ER's Segmented
  (`flex gap-[2px] rounded-lg border bg-[--color-bg-base] p-[3px]`, active =
  `bg-[--color-bg-elevated] font-medium shadow-[0_1px_2px_rgba(13,13,11,0.06)]`).

Section-by-section:

- **Structure:** replace `<hr className="… my-7" />` dividers with full-bleed
  `border-b border-[--color-border-subtle]` sections using consistent
  `py-[18px]` rhythm (the body padding stays on the modal; sections divide
  edge-to-edge as in ER).
- **Model:** keep `MbModelPicker`; just swap the header to `MbSectionHeader`.
- **Template → card-list picker:** replace the `<select>` with an ER-style list:
  a leading "Freeform" option card (active = `border-[--color-accent-primary]
  bg-[rgba(212,255,0,0.06)]`), then one card per template showing the name +
  a `built-in` / `uploaded` mono sublabel, with inline `Trash` delete on
  user-owned items. Preserve current freeform hint + behavior. Keep the dashed
  mono Upload pill (header-right).
- **Instructions → card-list picker:** same pattern, with a leading "None"
  option; inline delete on user-owned; dashed mono Upload pill. Preserve the
  existing freeform-needs-instructions gating (`isBriefEmpty`).
- **Connectors:** keep the `MbToggle` list (already animated/polished); just
  swap the header to `MbSectionHeader`.
- **Length:** keep as a segmented control but re-skin via `MbSegmented` for
  consistency with Language/Reasoning.
- **Language → `MbSegmented`** (English / 繁體中文), replacing the `<select>`.
- **Reasoning effort → `MbSegmented`** (Default / Medium / High), replacing the
  `<select>`; Anthropic-only visibility unchanged.

Exports: `MbConfigFields`, `isBriefEmpty`, `MbConfigDraft`, `MbToggle` stay.
`mbSectionTitle` is replaced by `MbSectionHeader`. Behavior, the `MbConfigDraft`
shape, and all `data-testid`s on inputs are preserved (selects become
buttons — update the affected tests to click cards instead of selecting
options; keep stable `data-testid`s like `mb-template-select`/
`mb-instructions-select` on the picker container, plus per-option testids
matching ER's `…-option-{id}` convention).

### G. Modal shells: `MbRunNowModal` + `ScheduleEditorModal`

Paths: `frontend/src/components/morning-briefing/MbRunNowModal.tsx`,
`frontend/src/components/morning-briefing/ScheduleEditorModal.tsx`

Align both shells to `V3ReportSettingsModal`:

- Content: `rounded-[14px]`, `shadow-[0_16px_40px_rgba(13,13,11,0.18)]`,
  `border-[--color-border-subtle] bg-[--color-bg-elevated]`.
- Overlay: `bg-[rgba(13,13,11,0.45)]`.
- Header: `px-[22px] py-[18px]`, title `text-[16px] font-semibold`, plus a
  mono eyebrow ("MORNING BRIEFING" for Run Now; keep "SCHEDULE" for the
  editor), `X` close button on the right.
- Footer: `bg-[--color-bg-base]`, `rounded-b-[14px]`, `border-t`,
  `px-[22px] py-[14px]`; keep the existing left-aligned error/empty messaging
  and Cancel / Generate (or Save) buttons.
- `ScheduleEditorModal`'s timing block (time / timezone / day toggles / label /
  enabled) is restyled to sit above the `MbConfigFields` sections using the
  same `MbSectionHeader` + `border-b` rhythm; day toggles keep their current
  accent-active treatment.

### Out of scope (do not touch)

- Feed cards (`MbBigCard`, `MbReportRow`, `MbGeneratingCard`, `MbFeedSection`,
  `mbHighlightBits`) — already at parity.
- Streaming / run lifecycle (`useMbRunStream`, `mbPhase`), data hooks, and all
  backend/API/i18n contracts beyond adding new UI strings.
- The upload sub-modals' internals (`MbTemplateUploadModal`,
  `MbInstructionsUploadModal`) beyond shell alignment if trivially consistent.

## Testing

- Update existing component tests for the picker change: `MbRunNowModal.test.tsx`
  and any `MbConfigFields` / `ScheduleEditorModal` tests that selected `<option>`s
  must now click option cards. Keep coverage of: empty-brief gating, ad-hoc
  payload shape, reopen-prefill, and (editor) day-selection validation.
- Add a light `MbHero` test (renders the three stats, falls back to `—` for
  next run with no enabled schedules) and an `MbEmptyPage` test (both CTAs
  fire).
- `npm run build` (tsc) clean; `npm test` green.

## Build sequence

1. `MbHero` + `MbEmptyPage` (new, isolated) and wire into `MorningBriefing.tsx`
   (A, B, C). Highest visual payoff, lowest risk.
2. `MbConfigFields` parity incl. card-list pickers + `MbSegmented` /
   `MbSectionHeader` (F). Both modals inherit it.
3. Modal shells (G).
4. `MbSchedulesView` (D) and `MbCabinetView` (E).
5. i18n keys (en + zh-TW), test updates, build + test pass.
