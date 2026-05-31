# Equity Research v3 — Generation UI Polish

**Date:** 2026-05-31
**Status:** Approved design, pre-implementation
**Scope:** Frontend only (React/TS, ER v3 page + shared shell). No core/engine or SSE-contract changes.

## Problem

The v3 generation experience is the weakest part of an otherwise polished page. Today
`V3ChatThread` renders a raw `StreamPanel` (a scrolling event log plus numeric counter
chips) while a run streams, then **swaps** that panel for a finished `V3ReportCard` on
completion. The swap is abrupt, the event log reads as debug output, and there is no
sense of a report taking shape.

A standalone mockup (`Equity Research - Generating (standalone) v2.html`) defines the
target: a report card that is present from the first stream frame, carries a
`GENERATING` status pill that flips to `READY`, fills its meta-row live, and folds the
activity detail into a tasteful in-card feed. The whole page enters with a staggered
motion choreography.

Confirmed: the mockup's design tokens (`#D4FF00` accent, `#F2F1E8` base, Geist /
IBM Plex Mono) are identical to the app's existing `frontend/src/styles/tokens.css`.
This is a structural and motion redesign that reuses existing tokens — **no recoloring**.

## Goals

- Replace the swap (StreamPanel -> ReportCard) with a single card that evolves in place.
- Show real generation progress: live section/source counts and an elapsed timer.
- Integrate the activity log into the new design as a styled in-card feed, not a raw box.
- Keep a functional Stop control; show a subtle generating indicator on composer + topbar.
- Port the full `om-anim` entrance choreography, gated by `prefers-reduced-motion`.
- Apply the mockup's spacing/type to the welcome stage and finished card.

## Non-goals

- No fabricated/synthesized prose status sentence. Status is driven by real stream state.
- No engine, core, or SSE event-contract changes. Frontend consumes existing events.
- No `Replay` button (a mockup demo artifact).
- No new "fully locked" composer (`opacity:.55; pointer-events:none`). Stop stays usable.
- No backend changes to counts/timing; the meta-row uses existing stream counters.

## Decisions (from brainstorming)

| Topic | Decision |
| --- | --- |
| Scope | Full-surface polish: welcome, generating, finished card, composer. |
| Activity log | Integrate into the new design as a styled in-card feed (do not drop). |
| Status prose | Not needed. Drive status from real stream state. |
| Card timing | Card present throughout; `GENERATING` -> `READY`; meta-row fills live. |
| Composer | Keep functional Stop; no hard lock; drop Replay; add generating indicator. |
| Motion | Full `om-anim` choreography + local card motion; respect reduced-motion. |

## Architecture

### One phase-aware card (no swap)

`V3ReportCard` becomes phase-aware instead of being a completion-only component. A new
`phase` prop drives every mutable region:

```
phase: "generating" | "ready"
```

`V3ChatThread` renders this single card from the first stream frame and feeds it live
stream state. The `cardIn` reveal animation plays once on mount; the status pill,
meta-row, preview region, and action row mutate in place as the run progresses. The
raw `StreamPanel` (event log + counter chips) is retired — its data now flows into the
card's meta-row and the new activity feed.

Boundaries:

- **`V3ReportCard`** — owns the card chrome, header, status pill, meta-row, preview
  region, action row, and the generating/ready transition. Pure presentational; all
  state arrives via props.
- **`V3ActivityFeed`** (new) — owns the styled in-card activity timeline. Takes the
  `V3Event[]` from the stream, renders the last ~6 as a fading timeline, and offers a
  "Show all activity" disclosure for full history. Self-contained; testable in isolation.
- **`useV3RunStream`** — unchanged SSE lifecycle, plus an exposed client-side elapsed
  timer (see below). Still the single source of `status`, `events`, and counters.
- **Composer / topbar indicators** — read `isStreaming` only; no new state.

### Component responsibilities

```
V3ChatThread
  ├─ UserMessage (+ SettingsChips)          unchanged
  └─ V3ReportCard  phase={status==="completed" ? "ready" : "generating"}
       ├─ header (icon, title, subtitle)    static once submitted
       ├─ StatusPill  GENERATING ↔ READY    pulse dot while generating
       ├─ preview region
       │    ├─ generating → <V3ActivityFeed events=… />
       │    └─ ready      → exec-summary + "read more →"   (current behavior)
       ├─ meta-row  sections · sources · elapsed/Generated-in   live counters
       └─ actions  Open · Download · Save to Repo            hidden until ready
```

## Detailed behavior

### Status pill

- `generating`: text `GENERATING`, leading `.pulse` dot (`--color-accent-primary`,
  `pulseDot 1.2s` glow). Reuses `.rc-status-pill` geometry (mono 9px, 0.1em tracking,
  uppercase, yellow-800 on `rgba(212,255,0,0.12)`).
- `ready`: text `READY`, steady dot, no animation.
- Failed/cancelled (existing terminal states): `FAILED` / `CANCELLED` tones reusing the
  current danger/warning treatment from `StatusBadge`. The card still renders; the
  preview region shows the terminal/error message instead of the feed.

### Meta-row (live)

Order and format follow the mockup (`.rc-meta-row`: mono 10px, 0.06em, tertiary):

- `N sections` — from `sectionsWritten`.
- `N sources cited` — from citations/sources counter.
- charts — `N charts` when `chartsEmitted > 0` (omit at zero).
- elapsed/time — while generating: `Elapsed Xs` ticking; on completion: `Generated in Xs`.

Elapsed timer: `useV3RunStream` records a `startedAt` timestamp when status enters
`streaming` and exposes `elapsedSeconds`. A 1s interval updates it while streaming;
on a terminal event the value freezes at its final reading. Reduced-motion does not
disable the timer (it is information, not decoration), but the count-up easing is dropped.

### Activity feed (`V3ActivityFeed`)

- Renders the last ~6 `V3Event` rows as a vertical timeline: mono micro-label
  (event type, humanized) + short payload summary, each row fading in on arrival.
- Newest at the bottom, container auto-scrolls to latest while generating.
- A "Show all activity" disclosure expands to the full reversed history (the data the
  old StreamPanel showed), styled to match — bordered, scrollable, max-height ~18rem.
- Collapses to the recent-6 view by default; remembers expanded state within the turn.
- Empty/initial state: a single "Starting run…" row.

### Composer

- Keep the functional **Stop** button while `isStreaming` (current cancel path intact).
- Do **not** apply the mockup's hard lock. The textarea stays mounted; submit remains
  disabled during a run as today.
- Mode pill gains a generating affordance while streaming: a leading `.pulse` dot and a
  `GENERATING` tone (reuse `.topbar-pill` palette). Reverts on completion.
- No `Replay` button.

### Topbar

- While a run is active, render the mockup's `topbar-pill` (`GENERATING`, pulse dot,
  `rgba(212,255,0,0.10)` bg, yellow-800). Removed on completion. Driven by `isStreaming`.

### Motion choreography (full)

- New global stylesheet `frontend/src/styles/motion-shell.css` ports the `om-anim`
  system: `om-side-in`, `om-bar-rise`, `om-content-in`, `om-fade-up`, and the staggered
  `nth-child` delays for `.sidebar`, `.topbar`/`.pageheader`, and `.content > *`. Keyed
  off `html.om-anim body[data-om-auto]`. Imported once from `global.css`.
- The shared shell/layout components get stable hook attributes
  (`data-om-shell="sidebar" | "topbar" | "content"`) so the choreography can target them
  without depending on Tailwind class output. Additive only; no layout change.
- ER v3 opts in: on mount, `EquityResearchV3` adds `om-anim` to `<html>` and
  `data-om-auto` to `<body>` (and removes on unmount). Opt-in per page keeps other
  departments unaffected unless they later adopt the same hook.
- Local card motion: `cardIn` reveal on card mount, `pulseDot` for status/composer dots,
  status-pill cross-fade on phase flip, meta count-up.
- **Reduced motion:** a `@media (prefers-reduced-motion: reduce)` block disables all
  `om-*`/`cardIn`/`pulseDot` animations and count-up easing. Content appears immediately
  in final state. This matches the mockup's own reduced-motion handling.

### Welcome + finished card polish

- `WelcomeStage`: align spacing/type to the mockup (icon box, greeting scale, mode pill).
  Largely already matches; changes are cosmetic.
- Finished `V3ReportCard`: confirm geometry against the mockup spec — icon 36px / radius
  8 on `rgba(212,255,0,0.16)`, card radius 12, header padding `16px 18px 12px`, meta
  mono-10, action row on `--color-bg-base` with top border. Adjust where drifted.

## Styling approach

Components keep the existing Tailwind-plus-tokens approach (matching current
`V3ReportCard`). Component-level styles are expressed as Tailwind utilities referencing
the same CSS custom properties; the mockup's `.report-card`/`.rc-*`/`.mode-pill` rules
are the source of truth for geometry and color values. The `om-anim` choreography is the
one exception — it is keyframe- and `nth-child`-based, so it lives in the dedicated
`motion-shell.css` file rather than as utilities.

## Files

| File | Change |
| --- | --- |
| `frontend/src/components/equity-research-v3/V3ReportCard.tsx` | Add `phase` prop; generating header/pill/meta/preview/actions; mount `cardIn`. |
| `frontend/src/components/equity-research-v3/V3ActivityFeed.tsx` | New. Styled in-card activity timeline + "Show all activity" disclosure. |
| `frontend/src/components/equity-research-v3/V3ChatThread.tsx` | Render unified card from first stream frame; retire raw `StreamPanel`; pass stream state. |
| `frontend/src/components/equity-research-v3/useV3RunStream.ts` | Add `startedAt`/`elapsedSeconds` + 1s tick; freeze on terminal. |
| `frontend/src/components/equity-research/ErComposer.tsx` | Generating indicator on mode pill; keep Stop; no hard lock; no Replay. |
| `frontend/src/pages/departments/EquityResearchV3.tsx` | Topbar generating pill; toggle `om-anim`/`data-om-auto` on mount; pass `phase`. |
| `frontend/src/styles/motion-shell.css` | New. `om-anim` choreography + reduced-motion block. |
| `frontend/src/styles/global.css` | Import `motion-shell.css`. |
| Shared shell/layout components | Add `data-om-shell` hook attributes to sidebar/topbar/content roots. |
| `frontend/src/components/equity-research/WelcomeStage.tsx` | Minor spacing/type alignment. |

## Testing

Vitest component tests:

- `V3ReportCard` renders `GENERATING` pill in `generating` phase, `READY` in `ready`.
- Meta-row reflects counter props; elapsed shows `Elapsed Xs` while generating and
  `Generated in Xs` once ready.
- Action row hidden while generating, present when ready.
- `V3ActivityFeed` renders recent rows; "Show all activity" expands full history;
  empty state shows "Starting run…".
- `ErComposer` shows Stop while streaming and is not hard-locked; mode pill shows the
  generating affordance; no Replay button exists.
- Reduced-motion: with `prefers-reduced-motion: reduce`, no animation classes apply and
  final state renders immediately (assert via class presence / matchMedia mock).

Manual browser pass: navigate to `/equity-research`, run a real report, verify the
entrance choreography, the in-place generating -> ready transition, live meta-row, the
activity feed + disclosure, topbar pill, and Stop.

## Risks / open points

- **Shell hook attributes** touch shared layout components. They are additive
  (`data-*` only) and the choreography is opt-in per page, so other departments are
  unaffected until they adopt `om-anim`. Verify the layout exposes single stable roots
  for sidebar/topbar/content at implementation time.
- **Sources counter**: confirm the stream emits a sources/citations count usable live;
  if only available at completion, the meta-row shows sources from `ready` onward and
  omits it while generating (graceful).
- Retiring `StreamPanel` removes the only current view of the raw event stream; the
  "Show all activity" disclosure preserves that affordance for power users.
