# Earnings Update — Generating Card + Less-Empty Report Cards

Date: 2026-06-02
Status: Approved (design)
Scope: Earnings Update v2 (`/earnings-update`) frontend + one backend feed-payload extension.

## Goal

Two tightly-scoped UI improvements, shipped together:

1. **Rich generating card** — replace the tiny "Generating" pill shown during a
   live run with a mockup-grade generating card (badge, elapsed timer, title,
   current-phase row, progress bar, phase pips, cancel).
2. **Less-empty report cards** — surface the cover highlights the engine already
   produces (thesis subtitle, key-metric chips, rating) on the feed cards, which
   today show only ticker · subject · timestamp.

This is a deliberately "slight" improvement: **every card highlight is backed by
data the EU engine already emits** (`CoverSpec`). No new engine output, no price
plumbing, no migration. The mockup's literal Beat/Miss verdict pill, Rev/EPS
surprise %, after-hours move, signal score, and sparkline are explicitly **out of
scope** — those fields do not exist today.

Reference mockup: `~/Downloads/earnings-update-generating-standalone.html`
(`.lc-generating` block for the generating card; `.lc-grid` / row `.surprise` for
card metrics — we adapt these to real data).

## Background (verified)

- **SSE stream** (`useEuRunStream`) already exposes everything the generating card
  needs: `run.started` (subject), `tool.called`/`tool.completed` (`tool_name`,
  `args_summary`, `summary`, `ok`), `section.written` (`title`, `char_count`),
  `chart.emitted` (`title`), plus running counts (`sectionsWritten`,
  `chartsEmitted`, `toolCallsInflight`) and `cancel()`.
- **Cover data** is produced by the engine via `set_cover` and stored as
  `ReportEu.cover_json` (JSON text). It is exposed only on the per-report detail
  (`RunDetail.cover`), not on the feed list (`RunSummary`).
  `CoverSpec` fields: `subtitle`, `tagline`, `tldr[]`, `key_metrics[]`
  (label / value / change / tone), `rating`, `upside_pct`.
- The feed handler `GET /runs` (`list_runs`) already selects full `ReportEu` rows
  and maps each through `_summary(row)` — so `cover_json` is already in hand.
  Enriching the feed needs **no new query and no migration**.
- EU tool names are largely dynamic (built from connector/dispatcher descriptors);
  only `get_earnings_calendar`, `write_section`, `set_cover`, `emit_chart`,
  `finalize` are fixed. Phase mapping must therefore key off the **fixed output
  tools + event types**, treating any other tool call as generic "Researching".
- The page is fully i18n-driven (`en.json` + `zh-TW.json`); new strings need both
  locales. Tokens `--color-accent-primary`, `--color-feedback-success/error`,
  and animations `animate-live-pulse` / `animate-feed-fade-up` already exist.

## A. Generating card

### Component split

Introduce a dedicated **`EuGeneratingCard`** for the streaming state, rather than
overloading `EuBigCard` with two visual modes. `EuBigCard` stays responsible for
the resolved/complete state only. `EarningsUpdate.tsx` renders `EuGeneratingCard`
while `stream.status !== "completed"` and `EuBigCard` once complete.

### Phase derivation (pure, testable)

`feed/euPhase.ts` exports `deriveEuPhase(stream)` returning:

```
{
  phaseKey: "connect" | "research" | "write" | "finalize",
  label: string,        // i18n key resolved by the component
  monoCode: string,     // mono status line: tool name / args summary / section title
  pips: Record<phaseKey, "pending" | "active" | "done">,
}
```

Mapping (latest meaningful event wins):

| Trigger | phaseKey | monoCode source |
|---|---|---|
| `run.started`, before any tool | `connect` | `RUN_STARTED` |
| any non-output tool call (`get_earnings_calendar`, data/web tools) | `research` | `args_summary` ?? `tool_name` |
| `section.written` seen | `write` | latest section `title` |
| `set_cover` / `finalize` tool call | `finalize` | `FINALIZING` |

Pip state: phases at or before the current phase are `done`, the current is
`active`, later are `pending`. (4 fixed pips: Connect · Research · Write · Finalize.)

### Elapsed timer

A local `useElapsed(active)` (or inline `setInterval`) starts when the card mounts
in streaming state, formats `mm:ss`, and stops on terminal status. Resets when
`reportId` changes.

### Markup / styling (adapted from `.lc-generating`)

- Accent-bordered card (`--color-accent-primary` at ~0.55 alpha) with an animated
  scanning top edge.
- Badge: pulsing dot + "Generating Update" (mono, uppercase).
- Right-aligned elapsed timer (mono, tabular-nums).
- Title: subject from `run.started` payload; fallback `{ticker} — Earnings Update`.
- Phase row: spinner + human phase label + mono status code (left border divider).
- Indeterminate progress bar (sweep animation).
- Phase pips (flex row; active fills, done solid).
- **Cancel**: subtle ghost button wired to `stream.cancel()`; disabled once a
  terminal status lands.

### Animations (new CSS keyframes)

Add alongside existing keyframes: bar-sweep, scan-edge, pip-fill. Reuse
`animate-live-pulse` (dot) and an existing/standard spin for the spinner.
**Excluded**: scramble / odometer text effects (imperative DOM, out of scope).

## B. Report card highlights

### Backend — `RunSummaryOut.highlights`

Add a compact model and populate it in `_summary()` from `row.cover_json`:

```python
class CardHighlightsOut(BaseModel):
    subtitle: str | None = None
    rating: str | None = None
    metrics: list[CoverMetricOut] = Field(default_factory=list)  # capped at 4

class RunSummaryOut(BaseModel):
    ...
    highlights: CardHighlightsOut | None = None
```

`_summary` parses `cover_json` (reuse the existing tolerant `_cover_out` parse
path), maps `subtitle` + `rating` + first 4 `key_metrics`, and returns
`highlights=None` when there is no cover or no usable content. Trimming `tldr`
and capping metrics keeps the list payload lean even in the cabinet view.
(The big card renders up to 4 chips; `EuReportRow` renders the first 2.)

### Frontend types

Extend `api/earnings-update.ts`:

```ts
export interface CardHighlights {
  subtitle: string | null;
  rating: string | null;
  metrics: CoverMetric[];   // CoverMetric already defined
}
// RunSummary gains: highlights?: CardHighlights | null;
```

### `EuBigCard`

- Below the subtitle, render a row of **≤4** metric chips (`label` + `value`, with
  `change` and tone color when present).
- Render a `rating` pill in the tag row when present.
- Use `highlights.subtitle` as the subtitle when no explicit `subtitle` prop is
  passed (the "today/hero" path passes `subject` as title only).

### `EuReportRow`

Currently: `ticker · time | subject | chevron`. Becomes:

- Title line: `subject` (unchanged).
- Second line: `highlights.subtitle`, 1-line clamp (the mockup's `.s`).
- Right cluster: **≤2** metric chips + a `rating` chip, before the chevron.

### Tone → color

`positive` → `--color-feedback-success`, `negative` → `--color-feedback-error`,
`neutral`/unset → `--color-text-secondary`. Metric `value`/`change` are
model-provided pre-formatted strings — rendered verbatim, never re-formatted or
translated.

### Graceful degradation

`highlights == null` (older reports, or runs where the model skipped `set_cover`)
→ both cards render exactly as today. Empty metric/subtitle slots are suppressed.

## Cross-cutting

- **i18n**: new keys in `en.json` + `zh-TW.json` — phase labels (Connecting /
  Researching / Writing / Finalizing), "Generating Update", "Cancel", elapsed
  aria-label, and any new card labels. Mono codes and metric strings are not
  translated.
- **Boundary check**: backend change lives entirely in the route layer
  (`RunSummaryOut` + `_summary`), reading an existing column — no core changes.

## Testing

- **Backend** (`packages/server/.../earnings_update_v2` route test): `_summary`
  populates `highlights` from `cover_json`; caps metrics at 4; returns `None` when
  cover is absent or empty/invalid JSON.
- **Frontend**:
  - `deriveEuPhase` unit: event sequences → expected phaseKey / monoCode / pip
    states (connect → research → write → finalize; pip progression).
  - `EuGeneratingCard`: renders badge/title/phase/elapsed/pips; cancel calls
    `stream.cancel`; disabled after terminal status.
  - `EuBigCard`: metric chips + rating render when highlights present; degrade to
    today's layout when absent; chips capped at 4.
  - `EuReportRow`: subtitle line + ≤2 chips + rating render when present; degrade
    when absent.
- Existing EU tests must stay green.

## Files

**New**
- `frontend/src/components/earnings-update/feed/EuGeneratingCard.tsx`
- `frontend/src/components/earnings-update/feed/euPhase.ts`
- `frontend/src/components/earnings-update/feed/__tests__/EuGeneratingCard.test.tsx`
- `frontend/src/components/earnings-update/feed/__tests__/euPhase.test.ts`

**Edit**
- `frontend/src/components/earnings-update/feed/EuBigCard.tsx`
- `frontend/src/components/earnings-update/feed/EuReportRow.tsx`
- `frontend/src/pages/departments/EarningsUpdate.tsx` (render `EuGeneratingCard`
  while streaming)
- `frontend/src/api/earnings-update.ts` (`CardHighlights`, `RunSummary.highlights`)
- `frontend/src/locales/en.json`, `frontend/src/locales/zh-TW.json`
- CSS keyframes file (bar-sweep / scan-edge / pip-fill)
- `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py`
  (`CardHighlightsOut`, `RunSummaryOut.highlights`, `_summary`)
- Backend route test for `_summary` highlights

## Out of scope

- Beat/Miss verdict pill, Rev/EPS surprise %, after-hours move, signal score,
  sparkline (no backing data).
- Scramble / odometer text animations.
- Cabinet view (`EUCabinetView`) card styling — unchanged this pass.
