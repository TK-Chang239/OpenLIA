# Deferred Tasks — Post Phase 16-23 Merge

Date: 2026-04-24

All 23 implementation plans (Phases 0-23) are Done in the status table. This
document lists every task that was compressed or deferred during the Phase
16-23 execution sprint so follow-up work has a single source of truth.

## Phase 16 — Morning Briefing

- **Atomic frontend components.** Plan specified `SectionRow`, `TopicChip`,
  `NotesPopover`, `CustomSectionRow`, `ScheduleRow`, `AddScheduleModal` as
  separate files. Shipped composed into one `MBSettingsView.tsx` with inline
  `TopicsEditor` + `ScheduleEditor`. Refactor to atomic components if UX team
  wants them.
- **Hook unit tests.** `useMbConfig.test.tsx` and `useMbChatSession.test.tsx`
  not shipped. API client + section catalog covered; hook behavior covered
  implicitly via page integration.
- **`ChatInterface` / `ChatReportThumbnail` / `useReportStream` wiring inside
  the MB page.** Page currently uses inline `OnDemandBriefingButton` SSE
  stream. Shared chat surface from Plan 12 not wired for MB follow-up Q&A.
- **Endpoint-contract-matrix + route-authorization-matrix rows.** MB routes
  not yet documented in the two planning matrices.
- **Manual smoke test.** Not executed.

## Phase 18 — Panic Thermometer

- **Per-panel drill-down dashboards.** Plan specified 5 Chart.js dashboards
  (one per panel — Oil, Inflation, FedLanguage, WageGrowth, Diplomacy); not
  shipped.
- **`RuleEditor` / `FormulaInput` inline validation UI.** Formula editing
  works through the /formula helper routes but no inline UI ships.
- **Share-link pako/base64 encoder.** Export/import via Blob/File works;
  URL-encoded share link not shipped.

## Phase 19 — Macro Research (load-bearing gap)

- **Entire frontend page composition.** 5 dashboard React views + hooks not
  shipped. `pages/departments/MacroResearch.tsx` remains the Phase 8
  placeholder.
  - Backend, persistence, scheduler integration, and all 5 Dalio dashboards
    (Debt Cycle, Four Seasons, All-Weather, World Order, Five Forces) are
    complete.
  - Backend computes and persists assessments; users cannot see them until
    this frontend work lands.

## Phase 20 — Retail Sentiment

- **Per-metric drill-down UIs.** Plan specified per-metric charts; compressed
  into a single tabbed dashboard grid.
- **Batch NLP classification layer.** Current path returns metric snapshots
  directly without the documented NLP classification pass.
- **`rs_classification_log` table.** Not created.

## Phase 21 — Portfolio

- **SVG sparkline + area chart.** Not shipped.
- **Group tabs + context menu.** Not shipped.
- **Dedicated CSV import/export dialog.** CSV endpoints work; dialog UI is
  minimal.
- **Slide-out edit drawer.** Not shipped; edits use inline form.
- **React-query hooks for holdings / analytics / localPref.** Page uses
  direct fetch.
- **URL-synced filter hook.** Not shipped.

## Phase 22 — Repository

- **Date-range picker UI.** Backend accepts the filter params; no picker UI.
- **Framer-motion animations.** Not shipped.
- **Radix `Popover` / `DropdownMenu` primitives.** Page uses native form
  controls.
- **`useSearchParams` URL sync.** Filter state is in-memory only.
- **Per-component unit tests.** 3 page-level tests shipped; no per-component
  unit tests for `RepoFilterBar`, `RepoFilterChips`, `RepoListItem`,
  `RepoListSkeleton`, `RepoEmptyState`, `RemoveConfirmDialog`, `UndoToast`.
- **Endpoint-contract-matrix + route-authorization-matrix rows.** Not added.
  The new filter query params are additive — legacy row unchanged.

## Phase 23 — Docker packaging + final acceptance

- **`.github/workflows/release.yml`.** GHCR image publish + PyPI publish not
  wired.
- **Dedicated Caddyfile.** One reverse-proxy compose example covers the
  Cloudflare Tunnel + Caddy variants the plan itemized.
- **Container-runtime smoke.** `docker run openlia:dev && curl /healthz`
  needs a Docker daemon — not executed.
- **CHANGELOG + PyPI metadata.** `[project.urls]`, classifiers, readme fields
  not polished.
- **Frontend `prodBase.test.ts` / `buildOutput.test.ts`.** The existing
  `frontend/dist` build verifies the same invariants; dedicated vitests not
  shipped.

## Remediation Checklist Residual

| ID | Status | Gap |
|---|---|---|
| REM-P1-019 | `[~]` | ASGI-level smoke shipped; container-boot curl + full product-journey smoke matrix still open. |
| REM-P2-001 | partial | MR department page still placeholder (see Phase 19). |

All other REM items closed through Phase 16-23 execution.

## Priority Ranking (subjective)

1. **Phase 19 frontend (P0).** Blocks MR dashboards from being usable.
2. **Remediation REM-P1-019 final product-journey smoke matrix (P1).** Needed
   before real production acceptance.
3. **Phase 20 NLP classification + `rs_classification_log` (P1).** Retail
   Sentiment's documented behavior differs from what ships.
4. **Phase 16 `ChatInterface` wiring (P2).** Users cannot chat about their
   generated MB briefing.
5. **Phase 23 release workflow + container smoke (P2).** Needed for "pip
   install openlia" and Docker publish but not needed to run the app.
6. **Frontend UX polish across 16/18/21/22 (P3).** Nice-to-have; product is
   functional without.
7. **Endpoint / authorization matrix rows for Plans 16, 22 (P3).** Planning
   doc hygiene.
