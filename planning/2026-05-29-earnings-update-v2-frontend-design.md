# Earnings Update v2 — Frontend Design

Date: 2026-05-29
Status: Design approved, pending spec review → implementation plan
Depends on: `planning/2026-05-29-earnings-update-v2-design.md` (backend, shipped PR #213)

## 1. Purpose

Rewire the existing Earnings Update frontend to the v2 backend while keeping its current visual design. The page, feed sections, watchlist, cabinet, and modals stay visually the same; only the controls and data wiring change to match v2 capabilities (user-chosen model, DB-backed templates, per-user connector toggles, automatic earnings-release triggering, structured reports).

## 2. Strategy (locked decisions)

| Decision | Choice |
|---|---|
| Page handling | Rewire the existing Earnings Update page/components to v2 endpoints in place. v1 frontend retired; v1 backend stays as API rollback. |
| Engine assumption | Page targets v2 (`EARNINGS_ENGINE_VERSION=v2`). When v2 endpoints return 503, show an "engine disabled" banner instead of erroring. |
| Model/template/connectors | Chosen in Settings as per-user defaults (matches the v2 backend, whose `POST /runs/start` body is `{ticker}` only). No per-run override; no backend change. |
| On-demand runs | Ticker-only, like v1, but accept ANY ticker (including past / off-watchlist). Uses saved settings. |
| Report display | Reuse the v3 client-side renderer pipeline. No backend HTML endpoint. |
| Schedule | Cron builder removed; the forward "Up Next" section becomes a read-only upcoming-earnings calendar from `GET /schedule`. |

## 3. API client — `frontend/src/api/earnings-update.ts` (repointed to v2)

All paths move to `/api/departments/earnings-update/v2/...`. Functions and shapes:

- Watchlist: `fetchWatchlist()` `GET /watchlist` → `{entries: WatchlistEntry[]}`; `addWatchlistEntry(ticker)` `POST /watchlist` → `WatchlistEntry`; `removeWatchlistEntry(id)` `DELETE /watchlist/{id}`; `syncWatchlist()` `POST /watchlist/sync` → `{synced: number}`.
- Settings: `fetchSettings()` `GET /settings` → `EuSettings`; `updateSettings(next)` `PUT /settings` → `EuSettings`.
- Templates: `fetchTemplates()` `GET /templates` → `{templates: EuTemplate[]}`; `uploadTemplate({name, source_markdown})` `POST /templates` → `EuTemplate`; `deleteTemplate(id)` `DELETE /templates/{id}`.
- Schedule: `fetchSchedule()` `GET /schedule` → `{schedule: EuScheduleEntry[]}`.
- Runs: `startRun({ticker})` `POST /runs/start` → `{report_id}`; `fetchRuns(status?)` `GET /runs` → `RunSummary[]`; `getRun(id)` `GET /runs/{id}` → `RunDetail`; `deleteRun(id)` `DELETE /runs/{id}`; `cancelRun(id)` `POST /runs/{id}/cancel` → `{cancelled}`; `runEventsUrl(id)` → `/api/.../v2/runs/{id}/events`.

Types:

```typescript
type ReportLength = "concise" | "normal" | "elaborative";
type ReleaseTiming = "pre_market" | "post_market" | null;
type ReasoningEffort = "medium" | "high" | null;

interface WatchlistEntry { id: string; ticker: string; company_name: string | null; created_at: string; }

interface EuSettings {
  provider_kind: string; model: string; template_id: string;
  language: string; length: ReportLength; reasoning_effort: ReasoningEffort;
  financial_enabled: boolean; calendar_enabled: boolean; web_search_enabled: boolean;
}

interface EuTemplate { id: string; name: string; is_builtin: boolean; created_at: string; }

interface EuScheduleEntry {
  id: string; ticker: string; fiscal_date: string; release_timing: ReleaseTiming;
  scheduled_run_at: string; status: "pending" | "reported" | "skipped"; report_id: string | null;
}

interface RunSummary { id: string; ticker: string; subject: string; template_id: string; status: "running" | "completed" | "failed"; trigger_kind: "scheduled" | "on_demand"; created_at: string; }

interface RunDetail { report: RunSummary; error_message: string | null; sections: SectionRow[]; charts: ChartRow[]; citations: CitationRow[]; cover: CoverSpec | null; }
```

(`SectionRow`/`ChartRow`/`CitationRow`/`CoverSpec` mirror the v3 detail row types — reuse the v3 type definitions or copy them verbatim; the shapes are identical.)

## 4. Settings modal — rewrite `ReportSettingsModal`

The largest change. Same modal chrome and visual style; new contents.

Remove:
- The 9-section enable/disable toggle list.
- The custom-section editor. Delete `components/earnings-update/CustomSectionRow.tsx` and `lib/earnings-update/section-catalog.ts`.

Add:
- **Model picker** — clone `equity-research-v3/V3ModelPicker.tsx` into `earnings-update/EuModelPicker.tsx`; localStorage key `eu.v2.model_id`; sources from `getEnabledModels()`. Selection maps to `provider_kind` + `model`.
- **Template picker + upload** — a dropdown listing `fetchTemplates()` results (builtin first) plus an "Upload template" action that opens a clone of `equity-research-v3/V3TemplateUploadModal.tsx` (`earnings-update/EuTemplateUploadModal.tsx`) routed to `POST /templates`. Deleting a non-builtin template via `deleteTemplate`. Selection maps to `template_id`.
- **Connector toggles** — three switches: financial data, earnings calendar, web search (`financial_enabled` / `calendar_enabled` / `web_search_enabled`).
- **Reasoning effort** — dropdown (Default / Medium / High) shown only when the selected provider is Anthropic; maps to `reasoning_effort` (null when Default or non-Anthropic).

Keep:
- Report length (concise / normal / elaborative).
- Language selector (en / zh-Hant per the project's bilingual support).

All fields persist via `updateSettings()` (`PUT /settings`) on save.

## 5. On-demand run modal — `OnDemandReportModal`

Keep the visual design. Changes:
- Allow free-text ticker entry for ANY ticker (past or off-watchlist), not only watchlist matches. Watchlist tickers may still be offered as quick suggestions.
- Start → `startRun({ticker})` → `{report_id}`; then drive the live card via `useEuV2RunStream(report_id)`.
- The model/template/connectors used are the saved settings (a short read-only line can show "Using <model> · <template>" with a link to Settings).

## 6. Schedule → read-only upcoming-earnings calendar

- Delete `components/earnings-update/ScheduleManager.tsx` and `AddScheduleModal.tsx` (cron creation has no v2 equivalent).
- The existing forward-looking "Up Next" feed section renders real data from `fetchSchedule()`: per row show ticker, fiscal date, pre/post-market badge, scheduled run time, and status. Read-only — no create/edit/delete.

## 7. Watchlist

- Components and look unchanged (`WatchlistRow`, `WatchlistCard`, add popover, `CoverageModal`).
- v2 watchlist entries have no `next_earnings_date`/`release_timing` fields. The card's next-earnings date + pre/post badge are derived by joining the watchlist against `fetchSchedule()` by ticker (showing the soonest pending release); when no upcoming release exists, show a neutral "no upcoming date" state.
- "Sync now" affordance (optional) calls `syncWatchlist()` to refresh the calendar on demand.

## 8. Reports feed + report display

- Feed components (`EuHero`, `EuFeedSection`, `EuBigCard`, `EuReportRow`, `EUCabinetView`, `RecentReportsList`, `ReportRowItem`) repoint to `fetchRuns()`. Mapping: `RunSummary.ticker`/`subject`/`status`/`created_at`/`trigger_kind` drive the cards. Client-side grouping/filtering in `feedHelpers.ts` keeps working on the new shape.
- **Stats hero (`EuHero`)** trims to what v2 data supports: reports-this-week count and pending-scheduled count (from `fetchSchedule()`). v1's beats/misses/surprise/latency stats are dropped (v2 run summaries do not carry them).
- **Open report** reuses the v3 client-side renderer:
  - Add `getRun(id)` to the API client (already in §3).
  - Create `components/viewer/renderers/EUV2ReportRenderer.tsx` — a copy of `V3ReportRenderer.tsx` that calls `getRun` and adapts.
  - Create `components/report/adapters/euV2DetailAdapter.ts` — a copy of `v3DetailAdapter.ts` (identical input shape; rewrites `[^source_id]` markers, splits `{{chart:id}}`, builds the `ReportSchema`).
  - Add a `source.kind === "eu_v2_report"` case to `components/viewer/renderers/StructuredReportRenderer.tsx` dispatching to `EUV2ReportRenderer`.
  - Opening a report calls `fileViewer.open({ kind: "report", source: { kind: "eu_v2_report", reportId } })`.
- Delete a report via `deleteRun(id)` (`DELETE /runs/{id}`).

## 9. Hooks (`frontend/src/hooks/`)

- `useEuWatchlist` — repoint to v2 watchlist paths; expose `entries`, `add`, `remove`, `syncNow`, loading/error/refresh.
- `useEuReports` → `useEuRuns` — `fetchRuns()`; expose `runs`, loading/error/refresh.
- `useEuConfig` → `useEuSettings` — `fetchSettings()` / `updateSettings()`; expose `settings`, `save`, loading/error.
- `useEuSchedule` (new) — `fetchSchedule()`; expose `schedule`, loading/error/refresh, plus a `byTicker` map for the watchlist join.
- `useEuTemplates` (new) — `fetchTemplates()` / `uploadTemplate()` / `deleteTemplate()`.
- `useEuV2RunStream` (new) — adapt `equity-research-v3/useV3RunStream.ts` to `runEventsUrl(id)` and `cancelRun(id)`. Same lifecycle (EventSource, parse run.*/section.*/tool.* frames, terminal close, snapshot for late subscribers, `cancel()`).

## 10. Live run UX

On-demand start renders the existing streaming "live card" driven by `useEuV2RunStream`: shows progress (sections written, tools in flight), a cancel button (`cancelRun`), and on completion links to open the rendered report. Scheduled runs surface in the feed when they appear in `fetchRuns()`.

## 11. Engine-disabled handling

When any v2 endpoint returns HTTP 503 (engine gated off), the page renders a non-blocking banner: "Earnings Update v2 is disabled. Set EARNINGS_ENGINE_VERSION=v2 to enable." Hooks surface the 503 as a distinct state so the banner (not a generic error) shows.

## 12. Files

Create:
- `components/earnings-update/EuModelPicker.tsx`
- `components/earnings-update/EuTemplateUploadModal.tsx`
- `components/viewer/renderers/EUV2ReportRenderer.tsx`
- `components/report/adapters/euV2DetailAdapter.ts`
- `hooks/useEuSchedule.ts`, `hooks/useEuTemplates.ts`, `hooks/useEuV2RunStream.ts`

Rewrite / modify:
- `api/earnings-update.ts` (v2 paths + types)
- `pages/departments/EarningsUpdate.tsx` (state + endpoint wiring; "Up Next" → schedule)
- `components/earnings-update/ReportSettingsModal.tsx` (model/template/connectors/reasoning; drop sections/custom)
- `components/earnings-update/OnDemandReportModal.tsx` (free ticker entry + v2 start/stream)
- `components/viewer/renderers/StructuredReportRenderer.tsx` (add eu_v2_report case)
- `hooks/useEuWatchlist.ts`; rename `useEuReports.ts`→`useEuRuns.ts`, `useEuConfig.ts`→`useEuSettings.ts`
- `components/earnings-update/feed/*` (EuHero stats, EuBigCard/EuReportRow shape), `feedHelpers.ts`
- `components/earnings-update/WatchlistCard.tsx` (schedule-join for next date)

Delete:
- `components/earnings-update/ScheduleManager.tsx`
- `components/earnings-update/AddScheduleModal.tsx`
- `components/earnings-update/CustomSectionRow.tsx`
- `lib/earnings-update/section-catalog.ts`

## 13. Testing

Vitest, mirroring existing EU + v3 frontend tests:
- API client: each v2 function hits the right path/shape (mock fetch).
- Hooks: `useEuSettings` (load/save round-trip), `useEuSchedule`, `useEuTemplates`, `useEuV2RunStream` (EventSource lifecycle, terminal close, cancel), `useEuRuns`, `useEuWatchlist`.
- Components: rewritten `ReportSettingsModal` (model/template/connector/reasoning controls render and save the right payload; sections/custom gone), `OnDemandReportModal` (free ticker, start, streaming), the schedule view rendering from `GET /schedule`, watchlist-card schedule join, the 503 engine-disabled banner.
- Report rendering: `euV2DetailAdapter` produces a valid `ReportSchema` from a sample `RunDetail`; `StructuredReportRenderer` dispatches `eu_v2_report` to `EUV2ReportRenderer`.

## 14. Out of scope

- No backend changes (render endpoints stay deferred; browser Print → PDF covers export).
- Completion notifications.
- Any redesign of the visual language — this is a wiring + controls adaptation, not a restyle.

---

## As-built notes (divergences from this spec, recorded per coding standard #9)

Implemented on branch `feat/earnings-update-v2-frontend`. Status: all 15 plan tasks landed; `tsc --noEmit` clean, 115 EU-related tests green across 26 files, production build succeeds. Backend untouched.

Divergences discovered against the real codebase:

- **`RunSummary` primary key is `report_id`, not `id`** (backend `RunSummaryOut` maps `row.id` → `report_id`). All page wiring (open/delete/keys) uses `run.report_id`. The plan's illustrative `run.id` references are stale.
- **API field shapes** were aligned to the backend `*Out` models: added `fiscal_date`/`language`/`length`/`completed_at`/`reasoning_effort` to `RunSummary`; `CoverMetric` typed (`label/value/change/tone`); chart field is `spec` (backend serializes `spec_json` → `spec`); citation field is `provenance`. `GET /runs` returns a bare array.
- **`FileSource` exhaustiveness**: adding `eu_v2_report` also required a guard in `sourceUrl.ts` (exhaustive switch), beyond the plan's listed files.
- **Demo mode removed**: the v1 `isDemoMode()` returned `true` in every real browser, so `useEuWatchlist` never hit the API. The demo gate was dropped and `src/lib/earnings-update/demo-data.ts` deleted (no importers after the rewire). `demo-reports.ts` (used by `api/reports.ts`) is unrelated and untouched.
- **Orphan v1 hook** `src/hooks/useEuSchedules.ts` (plural, cron) was deleted — not in the plan's deletion list but required for a clean typecheck.
- **`byTicker` filters to `status === "pending"`** so a past reported/skipped run can't shadow the upcoming date.
- **Watchlist next-release join** is surfaced in `CoverageModal` (where the watchlist lives on this page), not on a standalone watchlist row — the page renders the watchlist via that modal.
- **`EuTemplateUploadModal`** props were adapted from v3's `onSaved(template)` to an injected `onUpload(name, markdown)` so it routes to `useEuTemplates().upload`; the v3 source-doc-blob fields were dropped.
- **Feed demo-only stats dropped**: `EuReportRow`/`EuBigCard` lost the demo verdict/revenue/EPS-surprise columns (they came from a removed `DEMO_REPORT_META`; no real backend field supplies them). The stats hero shows reports-this-week + pending-scheduled, per spec §8.
- **i18n inconsistency (open follow-up)**: the rewritten `ReportSettingsModal` uses inline English labels (matching the cloned v3-style components like `EuModelPicker`), whereas the rest of the page and the new card components use `t()` keys (en + zh-TW were added for the Up Next / watchlist cards). If full bilingual parity on the settings modal is wanted, re-introducing `t()` keys there is a small follow-up.

Strict-tsc note: Vitest `afterEach(() => vi.restoreAllMocks())` must use a block body (`() => { ... }`) — the bare arrow returns `VitestUtils`, which the project's strict `tsc` rejects.
