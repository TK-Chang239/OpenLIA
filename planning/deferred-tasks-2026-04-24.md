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

## Phase 19 — Macro Research

- **Entire frontend page composition.** Shipped 2026-04-24 on branch
  `feat/phase-19-frontend`: six-tab shell + SummaryView + DebtCycleView +
  FourSeasonsView + AllWeatherView + WorldOrderView + FiveForcesView +
  ScheduleEditor modal, typed API client, `MRSnapshot` department integration
  test.

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
| REM-P1-019 | `[~]` | ASGI-level smoke + product-journey smoke matrix landed (`packages/server/tests/test_e2e_smoke_matrix.py`, 6 journeys). Container-boot curl (`docker run openlia:dev` + `curl /healthz`) still open — needs Docker daemon. |
| REM-P2-001 | partial | MR department page shipped 2026-04-24; remaining placeholders resolve as each plan ships real product surfaces. |

All other REM items closed through Phase 16-23 execution.

## Project Stage

**Feature-complete backend + frontend, pre-release.** All 23 plan specs
shipped backend + persistence + routes; all department pages now render real
product surface. Deployment artifacts exist (Dockerfile + two compose
recipes) but have not been run through a real container boot.

- Tests: ~1400 backend + 415 frontend passing; 23 migrations; 7 department
  routers mounted.
- Gap — source vs deployable: Docker image defined but never built and
  smoke-tested in a real container; no publish workflow.

## Roadmap

Ranked by what blocks shipping vs polish.

### P0 — blocks public alpha

- **Container-runtime smoke.** Build the Dockerfile, run it, hit `/healthz`
  and `/` from outside the container. Closes REM-P1-019's last hole and
  proves the deploy recipe actually works.

### P1 — blocks confident production

- **End-to-end smoke matrix (REM-P1-019).** Initial journey set landed
  2026-04-24 in `packages/server/tests/test_e2e_smoke_matrix.py` — personal
  first-run setup, company invite → register → login, auth logout/reload,
  provider CRUD (without live connection test), password reset +
  must-change-password gate, repo save/open/unsave. Remaining gaps:
  Secretary chat stream journey, Equity/Earnings report generation,
  EU schedule → notification, and real provider connection tests (respx).
  Plus container-boot curl (`docker run openlia:dev` + `curl /healthz`)
  from Phase 23.
- **Phase 20 NLP classification + `rs_classification_log`.** Retail
  Sentiment's documented behavior differs from what ships — decide whether
  to implement or amend the spec.
- **Phase 16 `ChatInterface` + `ChatReportThumbnail` + `useReportStream`
  wiring in MB page.** Users currently cannot follow-up chat about a
  generated MB briefing.

### P2 — release hygiene

- **`.github/workflows/release.yml`.** GHCR image publish + PyPI publish so
  `pip install openlia` works.
- **CHANGELOG + PyPI metadata polish.** `[project.urls]`, classifiers, long
  description.
- **Endpoint-contract-matrix + route-authorization-matrix rows** for Plans
  16, 19, 20, 21, 22. Planning doc hygiene — every row the sprint added or
  changed.

### P3 — UX polish

- **Atomic component refactors** for MB (`MBSettingsView.tsx` →
  `SectionRow`/`TopicChip`/`NotesPopover`/`CustomSectionRow`/`ScheduleRow`/
  `AddScheduleModal`), Portfolio (slide-out drawer, group tabs, dedicated
  CSV dialog), Repository (Radix Popover/DropdownMenu primitives,
  `RepoFilterBar`/`RepoFilterChips`/`RepoListItem`/`RepoListSkeleton`/
  `RepoEmptyState`/`RemoveConfirmDialog`/`UndoToast`).
- **Charts and animations across new pages.** PT per-panel Chart.js
  drill-downs, PT `RuleEditor`/`FormulaInput` inline UI, PT pako share-link,
  Portfolio SVG sparkline + area chart, Repository framer-motion, Repository
  date-range picker UI.
- **URL-synced filter hooks** for Portfolio and Repository
  (`useSearchParams`).
- **Per-component unit tests** for Repository and Portfolio.
- **React-query hooks** for Portfolio (holdings / analytics / localPref).
- **Frontend build invariant tests.** `prodBase.test.ts` /
  `buildOutput.test.ts` — existing `frontend/dist` build verifies these
  invariants but no dedicated vitests run.

### Suggested next concrete move

Phase 19 frontend as one branch, then a single "ship-prep" branch bundling
container smoke + release workflow + E2E smoke scripts. Everything below P2
can wait for user feedback.
