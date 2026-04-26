# OpenLIA Phase Fix-Plan Completion Report

**Date:** 2026-04-25
**Scope:** All 21 fix-plans in `planning/audits/fix-plans/` (Phases 1a/1b/2/3 closed in prior session; Phases 4-24 closed in this session)
**Status:** **100% — every phase RESOLVED**

---

## Aggregate metrics

| Metric | Session start | Session end | Δ |
|---|---|---|---|
| Backend pytest | 1,005 passing | **2,012 passing** | **+1,007** |
| Frontend vitest | gaps everywhere | **732 passing** | **+732** |
| Pre-existing failures | 3 (ModelsAdminPanel, ModelsSection, WatchlistCard) | **0** | -3 |
| `uv run ruff check .` | dirty | clean | — |
| `uv run ruff format --check .` | dirty | clean | — |
| `cd frontend && npm run lint` | dirty | clean | — |
| `cd frontend && npm run build` | broken on some branches | clean | — |
| Master tracker §1 phases at 100% | 4 of 24 | **24 of 24** | +20 |

**21 PRs merged** to `main` (`#55` through `#75`, sequential), totaling roughly **+33,000 lines** of source/tests/docs across both packages and frontend.

---

## Per-phase summary

| # | Phase | PR | Items | Highlights |
|---|---|---|---|---|
| 4 | LLM Provider System | #55 | 22 | `update_model` persists tier+model_ref; `/settings/models` user router; `with_retries` in 6 adapters; `openlia.llm` public API populated; wizard Step 3 backend; encrypted-key tamper → `AuthError`; ModelsSection + ModelsAdminPanel rewired |
| 5 | LLM Runtime | #56 | 15 | `await_with_grace` honors 2-second cancellation grace across chat/report/batch; SSE routes propagate client-disconnect; `_make_lifespan` validates prompt slots; `ChatReportThumbnail` gains `mode`; `ReportToolCall` gains `call_id`; `RefreshingChatRunner` + `RefreshingBatchRunner` parity with `RefreshingReportRunner`; `MAX_TOOL_TURNS=32`; unicode-safe args_preview |
| 17 | Formula Engine | #57 | 17 | Option A (plan-wins, additive spec amendment); case-insensitive AND/OR/NOT; `null` literal + propagation; `STRING` literal; reserved scalars in new `openlia.formula.derived` (`ma20/50/100/200`, `atr_14`, `std_20`, `high_52w`, etc.); `Rule`/`RuleSet`/`PanelResult`/`FormulaResult` in new `rules.py`; `compute_streak` moved into engine with bar-by-bar MA recompute; 7 new functions (`avg`, `slope`, `percentile`, `cross_above/below`, `consecutive`, `days_since`); error taxonomy split (`ParseError`/`UnknownIdentifierError`/`TypeMismatchError`); div-by-zero/insufficient-history return null + warning; `pt_runner` private helpers deleted (-260 lines net) |
| 6 | Background Scheduler | #58 | 13 | `build_batch_runner` wired (MR jobs no longer crash on first fire); `MRScheduleService` unified to one scheduler-bound instance via `app.state`; stub builders removed from `wiring.py`; `JobType.RS_SNAPSHOT` registered; `max_instances=1, coalesce=True` on every schedule; `OPENLIA_SCHEDULER_MAX_CONCURRENT_JOBS` env knob; MR cron validated at write time |
| 7 | CLI Surface | #59 | 9 | Startup banner shipped (mode/db/host/port/scheduler/wizard-pending); `secrets rotate-key --from-stdin`; spec reconciled (list-invites header, create-invite output, banner version placeholder, admin unlock audit decision) |
| 8 | Frontend Shell | #60 | 18 | Mobile shell (hamburger + overlay + bottom tab bar); ErrorBoundary wrapping RouterProvider; skip-to-main-content link; `SetupGate` uses React Router; `VITE_API_BASE_URL` env var; `ShellSkeleton` replaces bare loading text; Geist preload; `useTheme` reads `prefers-color-scheme`; `useNotificationPoll` stops on 401; multi-segment breadcrumbs (`/settings/providers` → Home / Settings / Providers); plan body backfilled (was 1-line stub) |
| 24 | Design System Refresh | #61 | 12 | Button `::before` fill-wipe hover overlay; Card hover contract tested; DataRow + MonoLabel smoke tests; Sidebar 220/52 width tests; NavItem active-rail test; sidebar-scoped tokens documented; Setup wizard tokens normalized; AuthLayout/Sidebar Tailwind class swap; vitest locks for no-blue-tokens + no-hex-literals; final acceptance walkthrough doc |
| 12 | Shared Chat Components | #62 | 22 | 7-department `DepartmentSlug` union; drawer search + scope + archived filter; `AssistantMessage` markdown via react-markdown + remark-gfm + CodeBlock; chunks-aware `useChatStream` (text + thumbnail interleaved); `AbortController` + POST + `eventsource-parser` replace EventSource; FileViewer focus mgmt + mobile fullscreen + scroll preservation; renderer error/retry/empty states; `services/files.py` extracted; FileDownload feedback contract; SaveToRepo idempotency; `chat_messages.stopped_at` migration; auto-titles on first user message; `useReducedMotion` |
| 9 | Login / Account UI | #63 | 12 | `display_name` optional with email-local-part fallback; signup policy gates Sign-up link; `account_locked` payload `{code, message, metadata}` surfaces retry-after minutes; `aria-describedby` across 6 forms; `aria-busy` audit; register response 5-field shape; `mapTransportError` helper distinguishes offline/5xx/429; `SessionsPanel` async onClick wrap; vitest coverage gaps closed |
| 10 | Setup Wizard | #64 | 19 | `/setup/providers*` shipped (GET/POST/PATCH/DELETE/test/confirm); `services/wizard_models.py` + `wizard_providers.py` + `wizard_review.py`; dynamic `GET /setup/required_tiers` from dept registry; `wizard_gate.py` factory-injected sessions; review runner opens its own DB session (fixes detached-instance race); `require_loopback_during_wizard`; takeover-on-409 modal; e2e smoke for fresh install; background tasks lifecycle managed |
| 11 | Settings Page | #65 | 16 | Real `ModelsAdminPanel` + `DataProvidersAdminPanel` CRUD (replaced 15-line stubs); `SettingsDirtyContext` + `useBlocker` + `beforeunload` wire `UnsavedChangesModal`; admin direct-reset returns server-generated `temporary_password` to `OneTimeSecretModal`; per-department tier defaults read-only panel; new `api/_request.ts` shared helper; admin service tests added (invites, users, password_reset); 2 of 3 pre-existing vitest failures fixed (Models panels) |
| 13 | Report Pipeline & Secretary | #66 | 12 | Secretary HTTP route + chat-runner; PDF `_render_block` field-name fixes (`metric_cards.metrics`, `table.headers/rows` keyed by `header.key`, `key_finding.content`, `rating_badge.rating`); cover/furniture/section anchors rendered; SPA print route at `/reports/:id/render` with `ReportPrintPage`; `services/report_store.py` deleted (callers rewritten); `save_report_to_repo` extra-tool; assembler unsubstituted-placeholder guard |
| 14 | Equity Research | #67 | 12 | `session_id` threaded through `POST /chat`; `ChatInterface` accepts `streamUrl` + `bodyExtras`; split-panel removed → single-column `ChatInterface` with `extraInlineMessages`; chip auto-submit; Radix dropdown PDF/DOCX; `python-docx` `export_report_docx`; saveReportToRepo wired; per-section streaming events (`ReportSectionStart/Chunk/Complete`); inline error retry with `RotateCcw`; `PageSkeleton` |
| 15 | Earnings Update | #68 | 21 | `/schedules` consolidated into EU router with `zoneinfo`/time/days_of_week 422 validation; Cabinet `DELETE /reports/{id}` + `ConfirmDialog`; WatchlistCard Overdue + pre/post-market badges (fixes WatchlistCard pre-existing failure); New badge dot via `localStorage` opened-tracker; backend search/filter (q/ticker/from/to); OnDemand modal CheckCircle + last-earnings; loading skeletons; error banner with Retry; mobile responsive; framework JSON section IDs match `DEFAULT_SECTION_IDS`; full cascade test on User delete |
| 16 | Morning Briefing | #69 | 8 | `ReportRequest` gains optional `section_topics` + `reference_portfolio` fields (replaces `MB_EXTRAS_JSON` stuffing); migration `server_default` switched from `sa.text("0")` to `sa.text("false")` for Postgres; `MBSettingsView` decomposed into 6 atomic components (SectionRow, TopicChip, NotesPopover, CustomSectionRow, ScheduleRow, AddScheduleModal); 10 per-component vitests; spec amended to document shipped 3-tab nav + viewer-split |
| 18 | Panic Thermometer | #70 | 16 | 5 dashboards shipped (Oil/Inflation/WageGrowth/FedLanguage/Diplomacy) using inline SVG charts; `RuleEditor` + `FormulaInput` (300ms debounced parseFormula) + `PanelSettingsPane`; `ManualOverridePopover`; `ImportExportModal` with `share-link.ts` base64 hydration; `PresetLibrary` save-as + rename; `PanelDashboard` frame; `PtTriggerEvent` model + migration; `pt_runner.compute_dashboard` records level transitions + emits `PANIC_LEVEL_CHANGE` notifications; per-panel core unit tests; `--color-feedback-error-strong` token |
| 19 | Macro Research | #71 | 15 | `SchedulerService.run_now` + real `JobRun` dispatch (was random-UUID stub); `AllWeatherView` run-button removed (T3, no LLM); `four_seasons.py` `T4_PROMPT_KEY = None` + `FourSeasonsView` button removed; `smart_mode` query param plumbed; `mr_runner.run` no longer swallows non-IntegrityError; `PUT /dashboards/{slug}/threshold-overrides` split; `MRSettingsPanel` wraps `ScheduleEditor` + threshold panel; `SummaryView` fetches all 5 dashboards concurrently with severity + freshness; refresh-interval select (60s/5m/15m/off); `FreshnessBadge` |
| 20 | Retail Sentiment | #72 | 15 | `RsSchedule` model + migration; `services/rs_schedules.py`; GET/PUT `/schedule` routes; `core/openlia/retail_sentiment/reliability.py` extracted; spec-correct Buzz Volume (ratio against 30-day mean) with `buzz_count` preserved; metrics 8/9/11/12 with graceful None-on-missing-input; insights synthesis prompt + `synthesize_narrative`; `MetricSnapshot.narrative` field; full frontend rebuild — 12 components (OverviewTab/EvidenceTab/InsightsTab/TickerSelector/MetricCard/SentimentGauge/TrendChart/ReliabilityBadge/SignalAlert/ScheduleEditor/SettingsDrawer/MetricsDeepDive); 5 SWR hooks; metric catalogue |
| 21 | Portfolio | #73 | 15 | `AdapterPriceProvider` replaces `_NoopPriceProvider`; `PriceCache.invalidate` public method; adapter-backed `/portfolio/search` with `SearchResultOut(BaseModel)`; 14 components + 4 hooks under `frontend/src/portfolio/`; group endpoints + `GroupTabs` + `GroupContextMenu` (rename in single transaction; `__GROUPS__` sentinel for ordering); `useSortedHoldings` per-group localStorage sort; `HoldingsList` + `HoldingsGrid` with `Sparkline` + `AreaChart`; ticker → ER deep-link via `?ticker=` URL param; new shared `Toast` primitive at `components/primitives/`; `AddEditDrawer` + `ImportCsvDialog` real components |
| 22 | Repository | #74 | 15 | Verified `FileViewerProvider` already mounted (Phase 12); row click → FileViewer with `hideSaveToRepoButton` flag; new `useRepoList` hook with URL-state via `useSearchParams` + 250ms debounce + IntersectionObserver sentinel (50/page); 8 new repo components (FilterBar, FiltersDropdown, FilterChips, SortDropdown, ListItem, ListSkeleton, EmptyState, RemoveConfirmDialog); reused Phase 21 Toast primitive with three variants (removed-with-Undo, restored, error); 7 new server route negative tests; sidebar Portfolio icon → `BarChart2` |
| 23 | Docker / Acceptance | #75 | 16 | Container smoke harness (`tests/smoke/`) with SMOKE-gate; `release.yml` PyPI publish gated on `PYPI_API_TOKEN`; `.dockerignore` re-allows `CHANGELOG.md` + `LICENSE*`; deploy reshaped to 3-recipe layout (`cloudflare-tunnel/`, `caddy/` with Caddyfile + SSE flush, `lan/` with `OPENLIA_MODE` env override); per-package READMEs replace `../../README.md` path; `[tool.uv.build-backend].source-include` ships prompts YAML + frameworks JSON in wheel; `test_wheel_contents.py` for both packages; cookie/proxy integration tests + `production_env.yaml` fixture; CLI `admin invite create --json`; OPENLIA_HOST/PORT env-binding tests; migration-on-start verified; CI `docker:` job; `RELEASING.md`; rewritten `README.md` with Quickstart + recipes table; `scripts/acceptance.sh` merge-gate one-shot |

---

## Cross-cutting themes

### 1. Boundary discipline

Every phase respected the rule that `packages/core/` cannot import FastAPI/SQLAlchemy/openlia_server. Phase 17 in particular moved heavy logic (streak compute, derived scalars, ruleset evaluation) **out of** `services/pt_runner.py` and **into** the core formula engine, deleting ~260 lines of server-side private helpers that violated the boundary.

### 2. Reusable primitives shipped early benefit later phases

| Primitive | Phase shipped | Reused in |
|---|---|---|
| `RefreshingReportRunner` pattern | (pre-session) | Phase 5 → `RefreshingChatRunner` + `RefreshingBatchRunner` |
| `build_batch_runner` | Phase 5 | Phase 6 P0-04 (MR scheduler) |
| `FileViewerProvider` mount | Phase 12 (NEW-12-18) | Phase 22 row-click verified already in place |
| `ConfirmDialog` | Phase 12 | Phases 15 (Cabinet remove), 22 (Repository remove) |
| `Toast` | Phase 21 | Phase 22 (undo/restored/error variants) |
| `useReducedMotion` | Phase 12 | Phases 16 (WelcomeOverlay), 18 (FileViewer) |
| `request` shared helper | Phase 11 (NEW-11-11) | All later API clients |
| Engine `compute_derived_scalars` + `compute_streak` | Phase 17 | Phase 18 panels (made NEW-18-01..03 mostly closed-on-arrival) |
| `JobType.RS_SNAPSHOT` registry | Phase 6 | Phase 20 RS executor (NEW-20-03/04 mostly closed-on-arrival) |

This is the dependency-ordered execution paying off: each phase landed primitives the next one consumed, often closing items in subsequent fix-plans before the subagent even read them.

### 3. Spec drift reconciliation

Several phases involved spec-vs-shipped reconciliation rather than pure implementation. Resolution pattern: spec amended to document shipped reality when shipped was reasonable (Phase 16 MB 3-tab nav, Phase 17 `%`/`**`/ternary operators, Phase 19 single global MR schedule, Phase 24 sidebar tokens beyond plan surface). Spec held authoritative when shipped diverged unhelpfully (Phase 12 Department union, Phase 13 PDF block field names, Phase 14 single-column Active layout, Phase 20 tab labels Overview/Evidence/Insights).

### 4. Test debt closure

| Domain | Tests at session start | Tests at session end |
|---|---|---|
| Backend | 1,005 | 2,012 (+1,007) |
| Frontend vitest | unstructured / gaps | 732 |
| Smoke (SMOKE-gated) | 0 | 8 |
| Wheel-contents | 0 | 2 |
| Production env snapshot | 0 | 1 |

Many phases shipped per-component vitest suites that didn't exist before (Phase 16 MB: 10 component tests; Phase 18 PT: 7; Phase 20 RS: 11; Phase 21 Portfolio: 14; Phase 22 Repo: 9). The 3 pre-existing vitest failures from PRs before Phase 11 (`ModelsAdminPanel`, `ModelsSection`, `WatchlistCard`) were resolved by Phases 11 and 15.

### 5. Migration safety

Two new migrations shipped in this session:
- `2026-04-25-1400_pt_trigger_events.py` (Phase 18) — composite-level transition log.
- `2026-04-25-1500_rs_schedules.py` (Phase 20) — RS scheduler integration.

Both registered in `EXPECTED_TABLES` for `test_migrations.py`. Phase 16 also fixed `mb_user_configs` migration's `server_default=sa.text("0")` → `sa.text("false")` for Postgres compatibility.

---

## Manual follow-ups (carried in commit messages / PR bodies)

These items can't be fully automated and need human verification:

1. **Browser smoke** — most frontend phases (8, 9, 11, 12, 14, 15, 16, 18, 19, 20, 21, 22) ship with vitest coverage but never opened in a real browser. Recommended pass at viewports 320 / 768 / 1024 / 1440px, with light/dark `prefers-color-scheme` flip on first boot.
2. **PR #56 chat-stream cancel** — actual TCP-level disconnect during a streaming chat (cancel button or browser close) needs end-to-end verification that `chat_messages.stopped_at` populates.
3. **Phase 23 SMOKE=1 docker** — `SMOKE=1 OPENLIA_IMAGE=openlia:dev uv run pytest tests/smoke/ -v` must run on a host with Docker installed (CI's `docker:` job covers this on PR).
4. **Phase 19 production data registry** — `_MRDataFetchAdapter` no longer swallows fetch errors, but production hosts need to install a registry-backed `app.state.mr_data_provider` (no shipped `DataProviderRegistry` class exists; documented inline).
5. **Phase 13 Option A SPA Playwright PDF** — PDF route now serves SPA shell when `frontend/dist/index.html` exists; flipping production to use the SPA path requires `OPENLIA_REPORT_RENDER_BASE_URL=http://127.0.0.1:8000` in deploy env.
6. **PyPI trusted publisher OIDC** — release workflow now gates on `PYPI_API_TOKEN`; first real release requires either configuring a trusted publisher on PyPI or setting the secret.
7. **Caddy DNS prereq** — `deploy/caddy/` requires `OPENLIA_HOSTNAME` to point at the host with TLS-issuance reachable; first deploy needs DNS A-record before `docker compose up`.

---

## Reference artifacts

- **PRs:** [#55](https://github.com/TK-Chang239/OpenLIA/pull/55) through [#75](https://github.com/TK-Chang239/OpenLIA/pull/75)
- **Master tracker:** `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md` (every phase row 100% RESOLVED)
- **Fix-plans:** `planning/audits/fix-plans/phase-*.md` (every entry struck-through with closure note)
- **Acceptance script:** `scripts/acceptance.sh` (one-shot merge gate)
- **Release docs:** `RELEASING.md`, `deploy/README.md`, root `README.md` Quickstart

---

**Final state:** `main` at PR #75 merge, every fix-plan closed, suite green (2012 backend + 732 frontend), build clean, docs current.
