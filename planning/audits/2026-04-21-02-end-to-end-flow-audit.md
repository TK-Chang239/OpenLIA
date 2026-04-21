# End-to-End Flow Audit

Date: 2026-04-21

Scope: product journeys from boot to useful output, checked against current
Phase 0-8 implementation and future Plan 9+ dependencies.

Validation commands run: none. Static audit using source reads and current
route/frontend inventory.

## Executive Summary

The current app has infrastructure for DB, auth, providers, LLM runtime,
scheduler internals, CLI, and a frontend shell. It does not yet have working
end-to-end product flows. Most visible frontend pages are placeholders, setup
wizard routes do not exist, report/department routes do not exist, and the
implemented frontend auth boundary is currently incompatible with the backend.

The product can only be considered viable after smoke tests exercise full
journeys in both personal and company mode.

## Flow Findings

### 1. High - First-Run Personal Mode Is Not Implemented End To End

Expected flow:

1. `openlia serve`.
2. Frontend loads.
3. Setup wizard detects incomplete setup.
4. User configures mode/providers/models.
5. App enters usable department shell.

Current state:

- Backend seeds `wizard.completed=false`.
- Frontend has `/setup`, but it is a placeholder page.
- No `/setup/*` backend routes are mounted.
- No setup status gate runs before `AuthProvider`.
- Auth personal-mode fallback depends on `/auth/session` returning 404, which
  only happens because auth routes are not mounted in personal mode.

Impact: first-run setup cannot happen.

Required tests:

- Fresh personal DB -> browser route `/setup` shown before app shell.
- Finish wizard -> `wizard.completed=true`.
- Reload -> `/secretary` shell shown as local admin.

### 2. High - First-Run Company Mode Is Only Partly Available

Expected flow:

1. Operator sets company mode.
2. CLI creates invite.
3. User registers.
4. User logs in.
5. Setup wizard completes.
6. User enters shell.

Current state:

- CLI admin/invite commands exist.
- Backend auth/register/login routes exist in company mode.
- Frontend login page is a placeholder.
- Frontend auth API expects wrong response shape.
- Setup wizard is not implemented.
- `.env.example` documents `OPENLIA_DEPLOYMENT_MODE`, but source reads
  `OPENLIA_MODE`.

Impact: company onboarding cannot complete in the UI.

Required tests:

- `OPENLIA_MODE=company` app has `/auth/register` and `/auth/login`.
- CLI invite raw token registers exactly one user.
- Login sets `openlia_session` and maps flat DTO correctly.
- Setup wizard remains pre-auth or intentionally post-auth per Plan 10.

### 3. High - Department Pages Are Shell Placeholders

Current frontend routes exist for:

- `/secretary`
- `/equity-research`
- `/earnings-update`
- `/morning-briefing`
- `/retail-sentiment`
- `/macro-research`
- `/panic-thermometer`

But these pages render `PagePlaceholder`. No current backend department routes
exist.

Impact: the product shell navigates, but none of the core product experiences
work.

Required tests:

- Secretary chat opens and streams.
- Equity Research report generates and persists.
- Earnings Update dashboard can add ticker and generate report.
- Repository opens a generated/saved report.

### 4. High - Report Generation Flow Has No Server Route Yet

Expected flow:

1. User submits request.
2. Server streams report SSE.
3. `report.complete` persists `reports` row.
4. UI opens report in file viewer.
5. Save-to-repo works.

Current state:

- `ReportRunner` exists in core.
- `reports` table exists.
- No report route exists.
- No report store service exists.
- No frontend chat/file viewer/report components exist yet.
- Plan 13-15 snippets still include stale runtime/auth imports.

Impact: runtime exists, but no product path reaches it.

Required tests:

- SSE route serializes `to_wire(event)` frames.
- On `ReportComplete`, a report row is persisted with `content_structured`.
- `GET /reports/{id}` is user-scoped.
- Frontend receives stream and opens report artifact.

### 5. High - Scheduled Earnings Flow Is Stubbed

Expected flow:

1. User configures EU watchlist/schedule.
2. Scheduler rehydrates schedule.
3. EU planner builds targets.
4. Executor generates reports.
5. Notifications appear.

Current state:

- Scheduler internals and `EUScanExecutor` exist.
- Wiring defaults to `StubEUScanPlanner`.
- No EU watchlist/config routes exist.
- No app startup injection for real EU planner exists.
- Notifications route works against scheduler state once data exists.

Impact: scheduler engine is ready, but scheduled department behavior is not.

Required tests:

- Plan 15 registers real `EUScanPlanner` in `build_scheduler_service`.
- Adding schedule calls `SchedulerService.add_schedule`.
- Scheduled run creates `JobRun`, report, and unread notification.

### 6. Medium - Repository Flow Has Conflicting Persistence Direction

Plan 12 says create `repo_items`; Plan 14 says save-to-repo flips
`reports.is_starred` and tags. Current schema has `reports.is_starred` but no
`repo_items`.

Impact: repository/save semantics are not settled.

Decision needed:

- Use `repo_items` as canonical saved-report repository, or
- Use `reports.is_starred` plus tags, and drop `repo_items` from Plan 12.

## Required E2E Smoke Matrix

Before final product acceptance, add smoke tests for:

- personal first-run setup
- company invite/register/login/setup
- auth logout/reload
- provider create/test/edit/delete
- Secretary chat
- Equity report generation
- Earnings on-demand report generation
- EU schedule -> notification
- repository open/save/download
- password reset and must-change-password

## Recommended Fix Order

1. Fix auth DTO and Vite proxy first.
2. Implement setup status gate and backend `/setup/status`.
3. Add smoke tests for personal/company boot before building departments.
4. Add Secretary as the first real department route/UI.
5. Add report persistence and repository semantics before ER/EU pages.
