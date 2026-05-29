# Earnings Update v2 — Design

Date: 2026-05-29
Status: Design approved, pending spec review → implementation plan
Scope this effort: backend only (frontend is phase 2, designed here but built after backend proven)

## 1. Purpose

Rebuild the Earnings Update department on the v3-style engine model:

- User chooses the LLM model per run (any enabled model).
- A template enforces report shape (like Equity Research v3). The current EU prompts become the built-in default template. Users upload their own templates.
- No required connectors. The user toggles, in settings, which connectors the LLM may call.
- User maintains a watchlist of tickers (as before).
- The system pulls the EODHD earnings calendar weekly to build a forward release schedule, then fires a report automatically when a watchlisted ticker releases earnings.

EU v2 coexists with EU v1; v1 stays as rollback. EU v2 is gated by `EARNINGS_ENGINE_VERSION=v2` (mirrors `REPORT_ENGINE_VERSION=v3`).

## 2. Architecture decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Engine | Fork `report_v3` into a new `report_eu` runtime + own tables + own routes | Independence rule (no coupling to ER); earnings-specific behavior stays clean |
| Trigger | Weekly EODHD calendar sync → forward schedule table → hourly dispatcher fires due runs | Decouples calendar polling from triggering; absorbs date drift via weekly re-sync |
| Connectors | Per-user global toggles (financial, earnings_calendar, web_search); none required | Matches "in the settings"; simplest plumbing |
| v1 coexistence | Env-gated, additive, v1 untouched | Rollback safety, mirrors ER v1/v2/v3 |
| Build order | Backend first, then frontend | Prove engine before UI |

## 3. Engine fork: `report_eu`

New package `packages/core/src/openlia/llm/runtime/report_eu/`, forked from `report_v3`.

- `runner.py` — single tool-use loop, forked near-verbatim from `report_v3/runner.py`: up to `max_turns`, per-turn generate → dispatch tool calls (error-wrapped so loop never crashes) → emit events → check `workspace.finalized` + deadline. Model must call `finalize()` after writing all template sections.
- `session.py` — model resolution via `provider_kind` + `model` (forked from `report_v3/session.py`, including `_ensure_adapter()` lazy adapter build and `_ENV_VAR_BY_PROVIDER` credential resolution). **Key change: remove the mandatory `web_search_native` capability gate.** No connector is required, so any enabled model is allowed. `reasoning_effort` stays optional.
- `prompts.py` — earnings-flavored `build_system_prompt(request, catalog, trigger_context)`:
  - Template shape: fixed section ids/titles/intents (or freeform directive if a template has no sections).
  - Earnings trigger context block: ticker, company name, fiscal quarter/period, release date, release timing, consensus EPS/revenue estimates (from the schedule row, when present).
  - Available-connectors block: tells the model which tool groups are enabled this run, so it does not attempt disabled tools.
- `schemas.py` — reuse `TemplateSpec` / `SectionSpec` (`template_id, name, shape_description, ticker_anchored, default_length, sections`). Reuse from the existing shared spec rather than redefining.
- `tools/`
  - `registry.build_catalog(*, enabled_connectors, transports, ledger, workspace, ...)` — only assembles tool groups whose connector is toggled on. Output tools (`write_section`, `set_cover`, `finalize`, and `emit_chart`) are always present. All connectors off → output tools only; the LLM writes from prompt + trigger context alone.
  - `data_tools.build_data_tools(...)` — EODHD fundamentals/prices/news (forked from v3), each ledger-wrapped with `source_id` annotation.
  - earnings-calendar tool — wraps the existing helper `eodhd_upcoming_earnings.execute(ticker, exchange="US", from_date=None, to_date=None)` returning `{ticker, upcoming_earnings: [...]}`; included only when the `earnings_calendar` connector is enabled.
  - web search — native provider tool, included only when `web_search` connector is enabled.

### Charts

Keep `emit_chart` / `report_eu_charts` from the v3 fork. Earnings reports benefit from simple charts (revenue/EPS vs estimate, segment trends) and the cost of keeping the machinery is low. Templates that do not want charts simply never instruct the model to emit them.

## 4. Connectors as toggleable tool groups

Three independent groups, each gated by a per-user setting:

| Connector toggle | Tools exposed to LLM |
|---|---|
| `financial_enabled` | EODHD fundamentals, prices, news |
| `calendar_enabled` | `eodhd_upcoming_earnings` |
| `web_search_enabled` | native provider web search |

The system's weekly sync always calls EODHD to trigger runs, independent of these toggles. The toggles only govern which tools the LLM can call during report generation.

## 5. Database tables

Forked, EU-scoped. New Alembic migration.

### Run + artifact tables (mirror `report_v3_*`)

- `report_eu` — `id (str pk), user_id (fk users cascade), ticker, subject, template_id, language, length, provider_kind, model, reasoning_effort (nullable), status (running|completed|failed), error_message (nullable), trigger_kind (scheduled|on_demand), fiscal_date (nullable), created_at, completed_at (nullable), cover_json (nullable)`. Indexes: `(user_id, created_at)`, `(user_id, status)`.
- `report_eu_sections` — `id (int ai), report_id (fk cascade), section_id, section_index, title, markdown, version (default 1)`. Unique `(report_id, section_id, version)`.
- `report_eu_charts` — `id (int ai), report_id (fk cascade), chart_id, chart_type, title, spec_json, rendered_url (nullable), version`. Unique `(report_id, chart_id, version)`.
- `report_eu_citations` — `id (int ai), report_id (fk cascade), source_id, tool_name, display_index (nullable), provenance_json`. Unique `(report_id, source_id)`.
- `report_eu_tool_call_log` — `id (int ai), report_id (fk cascade), turn_index, tool_name, arguments_json, result_summary, provenance_json, source_id (nullable), input_tokens, output_tokens, wall_time_ms, timestamp`.
- `report_eu_templates` — `id (str pk), user_id (nullable fk users cascade), name, is_builtin (bool), template_spec_json, source_markdown (nullable), source_doc_blob (nullable), source_doc_mime (nullable), created_at, updated_at, deleted_at (nullable, soft-delete)`.

### EU v2 control tables

- `eu_v2_watchlist` — `id (str pk), user_id (fk users cascade), ticker, company_name (nullable), created_at`. Unique `(user_id, ticker)`. Independent of v1's `eu_watchlist`.
- `eu_v2_earnings_schedule` — forward calendar built by weekly sync:
  - `id (str pk), user_id (fk users cascade), ticker, fiscal_date (date), release_timing (pre_market|post_market|null), eps_estimate (nullable), revenue_estimate (nullable), scheduled_run_at (datetime), status (pending|reported|skipped), report_id (nullable fk report_eu), synced_at, created_at`
  - Unique `(user_id, ticker, fiscal_date)` — the dedup key (one report per ticker per release).
- `eu_v2_settings` — per-user defaults + connector toggles:
  - `user_id (pk, fk users cascade), provider_kind, model, template_id, language, length, reasoning_effort (nullable), financial_enabled (bool default true), calendar_enabled (bool default true), web_search_enabled (bool default false)`. Returns defaults if no row exists.

## 6. Trigger pipeline

Two scheduler jobs, built on the existing `scheduler/` infra (new `JobType.EU_V2_SYNC`, `JobType.EU_V2_DISPATCH`, executors, wiring).

### Weekly sync job

- Runs weekly (configurable time). Sweeps every user's `eu_v2_watchlist`.
- For each ticker, calls the EODHD earnings calendar, reads upcoming release(s).
- Upserts `eu_v2_earnings_schedule` rows keyed on `(user_id, ticker, fiscal_date)`:
  - New release → insert `status=pending`, compute `scheduled_run_at` = release datetime + timing offset (pre_market → after market open; post_market → that evening; unknown timing → end of release day).
  - Existing pending row whose date shifted → update `fiscal_date` / `scheduled_run_at` (re-sync corrects drift).
  - Already `reported` row → left untouched.
- Also invoked for a single ticker when it is added to the watchlist, so a freshly added ticker gets its forward schedule immediately rather than waiting for the weekly sweep.

### Dispatcher job (hourly)

- Finds `eu_v2_earnings_schedule` rows where `status=pending` and `scheduled_run_at <= now`.
- For each, loads the user's `eu_v2_settings`, fires a run via the EU run service with `trigger_kind=scheduled`, then sets `status=reported` and `report_id`.
- A run failure leaves the row `pending` for retry on the next dispatcher tick (bounded retry count to avoid loops; after N failures mark `skipped`).

Polling the schedule table is preferred over dynamically creating one cron entry per release: simpler, idempotent, and robust to restarts.

## 7. Run service + routes

`build_earnings_update_v2_router(*, db_session_factory, mode)` mounted under `/api/departments/earnings-update/v2/...`, gated by `EARNINGS_ENGINE_VERSION=v2` (503 when disabled). Registered in `app.py` alongside the v1 EU router.

Endpoints:

- Watchlist: `GET /watchlist`, `POST /watchlist`, `DELETE /watchlist/{id}`, `POST /watchlist/sync` (manual calendar refresh for the user)
- Settings: `GET /settings`, `PUT /settings` (connector toggles + default model/template/length/language/reasoning_effort)
- Templates: `GET /templates`, `POST /templates` (upload+compile), `DELETE /templates/{id}` (soft-delete)
- Schedule: `GET /schedule` (read-only upcoming releases for the user)
- Runs: `POST /runs/start` (async, returns `{report_id}`), `GET /runs`, `GET /runs/{id}`, `DELETE /runs/{id}`, `POST /runs/{id}/cancel`, `GET /runs/{id}/events` (SSE)
- Render: `GET /runs/{id}/html`, `GET /runs/{id}/pdf`, `GET /runs/{id}/docx`

On-demand and scheduled runs both flow through one `eu_v2_run_service.start_run_async(...)` → `report_eu` runner → persist artifacts → stream events. Streaming reuses the app-state event broker + cancel registry pattern (separate registry keys from v3).

A scheduled run builds its `user_input` / `subject` from the schedule row's trigger context (ticker, fiscal period, release date, estimates). An on-demand run takes a ticker from the request and synthesizes the same context (querying the calendar if that connector is enabled, else from the request).

## 8. Built-in default template

Convert the report sections in `packages/core/src/openlia/prompts/earnings_update.yaml` into a `TemplateSpec` with the eight default sections: `quick_take, market_reaction, key_financials, operational_highlights, forward_guidance, earnings_call, risk_assessment, thesis_check`. Seed as a builtin row (`is_builtin=true, user_id=null`) in `report_eu_templates` via the migration. User uploads use the same parse/compile path as v3 templates.

## 9. v1 coexistence

v1 EU (department class, prompts, `eu_watchlist` / `eu_user_config` / `eu_schedules`, services, scheduler EU_SCAN path, frontend page) is left untouched as rollback. EU v2 is purely additive behind the env gate. The sidebar/page routing exposes the v2 page only when `EARNINGS_ENGINE_VERSION=v2`.

## 10. Frontend (phase 2, designed not built)

EU v2 page mirrors v3 UI chrome:

- Watchlist row (add/remove tickers; next-release date + timing badge).
- Upcoming-release calendar (read-only `GET /schedule`).
- Reports feed (recent `report_eu` runs; open/delete).
- On-demand run modal: ticker input + model picker (reuse the V3ModelPicker pattern off `getEnabledModels()`).
- Settings modal: connector toggles, default model, default template, length, language, reasoning effort.
- Template upload (same flow as v3 templates).

Live runs stream via the SSE events endpoint with a cancel button, mirroring the v3 fire-and-stream page.

## 11. Testing strategy

- Core: `report_eu` runner loop (finalize contract, max-turns, error-wrapped dispatch), `build_catalog` connector gating (each toggle combination produces the expected tool set), prompt builder (trigger context + connector block render), default-template conversion.
- Server: route-level TestClient tests for every endpoint (watchlist, settings, templates, schedule, runs incl. SSE start — explicitly cover the async `start` handler being `async def`, the bug class that bit v3), services (run service, weekly sync upsert + drift correction, dispatcher due-row selection + dedup + retry), migration (table creation + builtin template seed + cascade delete on user removal).
- Scheduler: weekly sync executor, dispatcher executor, wiring registration for the two new job types.

## 12. Open items deferred

- Notification on completed scheduled report (reuse v1's `user_notifications` pattern) — wire in backend phase if low-cost, else phase 2.
- Bilingual report output already covered by the `language` setting (en / zh-Hant) per existing user-prefs model.
