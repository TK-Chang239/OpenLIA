# Morning Briefing Rework — Design Spec

Date: 2026-06-02
Status: Approved, ready for implementation plan
Author: brainstormed with TK Chang

## 1. Goal

Replace the legacy Morning Briefing (MB) implementation with a tool-use briefing
engine that mirrors the Earnings Update v2 (EU v2) architecture. The reworked MB
generates a briefing report at user-scheduled times, using the connectors the user
has toggled and the templates/instructions the user has uploaded.

The product idea is unchanged: a scheduled, recurring market briefing. What changes
is the engine and configuration model — from a single hardcoded prompt with a
flat sections-config, to a connector-gated tool-use loop driven by user-selectable
templates and instructions.

## 2. Foundational decisions (locked)

1. **New forked engine.** Build `report_mb` as a fork of `report_eu` (which is
   itself a fork of the v3 tool-use loop). Single-model tool-use loop, no revision
   flow, fixed connector-gated tool catalog. Reuse the shared `report_v2_3`
   library submodules (`TemplateSpec`, `SectionSpec`, `Language`, `ReportLength`,
   `research/`). The old deterministic MB engine path is retired.
2. **Per-schedule config binding.** Each MB schedule row carries its own
   `template_id`, `instructions_id`, enabled connectors, model/provider, and run
   knobs. A pre-market briefing can use a different template/methodology than an
   evening wrap. On-demand runs pick a saved schedule's config or set one ad-hoc.
3. **Purely template/instructions-driven scope.** No MB watchlist, no portfolio
   coupling. The template defines the briefing skeleton; the instructions define
   methodology and focus (which markets/sectors/themes to cover); the toggled
   connectors give the engine broad market tools. The user bakes focus into prose.
4. **Clean replacement, no feature gate.** Retire the old MB-specific engine,
   config, prompt, route, and frontend. Reuse the existing cron scheduler
   mechanism. New `report_mb*` tables; old v1 `reports` rows stop being written
   (kept readable in archive). No `MORNING_BRIEFING_ENGINE_VERSION` env gate.

## 3. Reference architecture

MB mirrors EU v2 layer-for-layer. The key structural difference: **MB is
time-triggered (cron), not event-triggered.** EU fans out per-ticker off an
earnings calendar; MB fires one broad briefing per scheduled time. So EU's
watchlist → calendar-sync → dispatch layer does **not** port. Everything else
(engine, templates, instructions, connector toggles, run/render services, feed
UI) does.

| Layer | EU v2 reference | MB target |
| --- | --- | --- |
| Core engine | `runtime/report_eu/` | `runtime/report_mb/` (fork) |
| Run tables | `report_eu` + 4 children | `report_mb` + 4 children |
| Templates/instructions | `report_eu_templates` / `_instructions` | `report_mb_templates` / `_instructions` |
| Config storage | `eu_v2_settings` (one row/user) | `mb_schedules` extended (per-schedule) |
| Trigger | watchlist → `eu_v2_earnings_schedule` → dispatcher | existing cron (`mb_schedules` + APScheduler) |
| Services | `eu_v2_*` | `mb_v2_*` |
| Route | `routes/departments/earnings_update_v2.py` | rewrite `routes/departments/morning_briefing.py` |
| Repo pointer | `repo_items.eu_v2_report_id` | `repo_items.mb_v2_report_id` |
| Frontend | `EarningsUpdate.tsx` + `components/` | rewrite `MorningBriefing.tsx` + `components/` |

## 4. Layer 1 — Core engine (`packages/core/src/openlia/llm/runtime/report_mb/`)

Fork `report_eu`. Mirror its module layout: `runner.py`, `session.py`,
`workspace.py`, `schemas.py`, `events.py`, `ledger.py`, `prompts.py`,
`transports.py`, `tools/`, `rendering/`.

Deltas vs `report_eu`:

- **`schemas.py`**
  - Drop `TriggerContext` (earnings/ticker anchor). Add `BriefingContext`:
    ```
    class BriefingContext(BaseModel):
        run_date: str            # e.g. "2026-06-02"
        schedule_label: str | None = None   # e.g. "Pre-market briefing"
        time_label: str | None = None       # e.g. "06:30"
        timezone: str | None = None          # e.g. "America/New_York"
    ```
  - `RunRequest.subject` is the briefing label (e.g. "Morning Briefing —
    2026-06-02"), not a ticker. Remove any `ticker_anchored` template branch.
    Replace `trigger_context` with `briefing_context: BriefingContext | None`.
    Keep: `template`, `language`, `length`, `provider_kind`, `model`,
    `reasoning_effort`, `enabled_connectors`, `instructions`.
  - Keep `EnabledConnectors`, `CoverSpec`/`CoverMetric`, `ChartSpec`,
    `CitationLogEntry`, `RunResult`, `RunStatus` as-is.
- **`transports.py`** — `MbDataTransports` dataclass of callables:
  `quotes(tickers)` (multi-ticker / index real-time or EOD), `prices(ticker,
  range)` (historical), `news(symbol|None)` (per-symbol and market-wide
  headlines), `economic_calendar(window)` (macro/economic events),
  `macro_indicators(keys)` (key macro series). (vs EU's `fundamentals` +
  single-ticker `earnings_calendar`.)
- **`tools/`** — connector-gated catalog: curated EODHD tools (multi-ticker
  quotes, historical prices, market+symbol news, economic calendar, macro
  indicators), dispatcher-routed tools for other enabled connectors, model-native
  web search, plus shared output tools (`write_section`, `emit_chart`,
  `set_cover`, finalize). No `earnings_calendar` tool. No batch.
- **`prompts.py`** — system prompt frames the analyst as writing a recurring
  market briefing for `briefing_context` (date/label/time), following the
  selected template skeleton and free-form instructions, citing tool sources via
  Markdown footnotes. Positive phrasing per project convention.
- **`runner.py` / `session.py` / `workspace.py` / `ledger.py` / `events.py`** —
  carry over from `report_eu` unchanged in shape (turn loop, no capability gate,
  no revision, broker events: `run.started`, `tool.called`, `tool.completed`,
  `section.written`, `chart.emitted`, `run.completed/failed/cancelled`).

Public surface (`__init__.py`) mirrors `report_eu`'s `__all__`, swapping
`TriggerContext` → `BriefingContext` and `EuDataTransports` → `MbDataTransports`.

## 5. Layer 2 — Data model (`db/models/report_mb.py` + migrations)

Mirror the `report_eu` family (5 run tables + 2 config tables):

- `report_mb` — one run. Columns: `id`, `user_id` (FK→users, cascade), `subject`,
  `trigger_kind` (`scheduled` | `on_demand`), `schedule_id` (nullable, FK→
  mb_schedules), `template_id`, `instructions_id` (nullable), `language`,
  `length`, `provider_kind`, `model`, `reasoning_effort` (nullable), `status`
  (`running` | `completed` | `failed`), `error_message` (nullable), `cover_json`
  (nullable), `created_at`, `completed_at` (nullable). Indexes: `(user_id,
  created_at)`, `(user_id, status)`. No `ticker`/`fiscal_date` columns.
- `report_mb_sections` / `report_mb_charts` / `report_mb_citations` /
  `report_mb_tool_call_log` — identical structure to the `report_eu` children
  (no `version`/revision columns needed; keep `version=1` default like EU for
  schema parity).
- `report_mb_templates` / `report_mb_instructions` — identical schema to
  `report_eu_templates` / `report_eu_instructions` (`id`, `user_id` nullable,
  `name`, `is_builtin`, `template_spec_json` / `body_text`, `source_markdown`,
  `source_doc_blob`, `source_doc_mime`, `created_at`, `updated_at`, `deleted_at`).
  Seed one built-in `mb_default` template via migration (a general market
  briefing skeleton: market wrap, macro/economic calendar, headlines, watch-list
  of themes, outlook).
- **`mb_schedules` extension** — add per-schedule config binding columns:
  `template_id` (FK→report_mb_templates, nullable until set), `instructions_id`
  (FK→report_mb_instructions, nullable), `enabled_connectors` (JSON: provider_ids
  list + web_search bool), `provider_kind`, `model`, `language` (default `en`),
  `length` (default `normal`), `reasoning_effort` (nullable), `web_search`
  (bool). Keep existing `time` / `timezone` / `days_of_week` / `label` /
  `is_enabled` / `last_run_at` / `created_at`.
- **`repo_items`** — add `mb_v2_report_id` FK → `report_mb.id` (cascade,
  nullable). Update the polymorphic CHECK constraint (exactly one of five
  targets) and the listing fan-out in `services/repo.py`.

Drop `mb_user_configs` table (and its migration's model) — fully replaced by
templates/instructions/per-schedule config.

## 6. Layer 3 — Server services (`services/mb_v2_*.py`)

Mirror `eu_v2_*` services:

- `mb_v2_run_service.py` — `build_run_request(...)` assembles a `report_mb`
  `RunRequest` from a schedule's bound config (or an on-demand ad-hoc config) +
  resolved template + resolved instructions + `BriefingContext`. `insert_report_row`,
  `start_run_async` (background task, returns `report_id`, streams via broker),
  `persist_result` (sections/charts/citations/tool-log → tables, status update).
- `mb_v2_template_service.py` — `resolve_template`, `list_templates`,
  `create_template_from_markdown`, `create_template_from_document`, soft-delete.
  Reuse shared `template_parser` / `template_compile`.
- `mb_v2_instructions_service.py` — `resolve_instructions`, `list_instructions`,
  `create_instructions_from_upload`, soft-delete.
- `mb_v2_data_sources.py` — compute the effective data-source list for a given
  enabled-connectors set (available/enabled/routing flags), driven by the
  connector registry. Department-agnostic logic copied from `eu_v2_data_sources`.
- `mb_v2_render_service.py` — `render_html`, `render_docx`, `render_pdf`.
  Generalize `eu_v2_docx` / `eu_v2_render_service` where they are not
  earnings-specific (extract shared helpers if cheap; otherwise fork).
- `mb_v2_wiring.py` — `build_mb_transports()` returning `MbDataTransports`
  (EODHD callables: quotes, prices, news, economic calendar, macro indicators),
  resolving the EODHD key from env or installed connector (reuse
  `resolve_eodhd_api_key`).
- `mb_v2_schedules.py` — schedule CRUD carrying the config bindings; keep the
  `SchedulerControl` hot-reload protocol (`add_schedule` / `modify_schedule` /
  `remove_schedule`) so APScheduler stays in sync.

Retire `mb_config.py`, `mb_request_builder.py`.

## 7. Layer 4 — Scheduler dispatch

Keep APScheduler + `JobType.MB_BRIEFING` + hot-reload. Rewrite
`scheduler/executors/mb.py` (`MBBriefingExecutor._do_work`):

1. Load the due `mb_schedules` row and its bound config.
2. `mb_v2_run_service.build_run_request(...)` (trigger_kind=`scheduled`,
   `BriefingContext` from the schedule's label/time/tz + run date).
3. Run the `report_mb` engine; persist to `report_mb` + children.
4. Insert the `repo_items` pointer; set `mb_schedules.last_run_at`.
5. Emit `REPORT_READY` notification ("Your {label} briefing is ready.").

Scheduled-run engine events go to the broker with no live listener (same as EU).
Update `scheduler/wiring.py` and `scheduler/payloads.py` to inject the new
service collaborators instead of the old `MBRequestBuilder` / generic
`ReportRunner` / `ReportStore`.

## 8. Layer 5 — Route (`routes/departments/morning_briefing.py`, rewritten)

Prefix `/departments/morning-briefing`. Endpoints (mirroring EU v2):

- **Schedules:** `GET /schedules`, `POST /schedules`, `PATCH /schedules/{id}`,
  `DELETE /schedules/{id}` — now carrying the per-schedule config binding
  (template/instructions/connectors/model/knobs + time/days/tz/label/enabled).
- **Templates:** `GET /templates`, `POST /templates` (markdown or document
  upload), `DELETE /templates/{id}`.
- **Instructions:** `GET /instructions`, `POST /instructions` (document upload),
  `DELETE /instructions/{id}`.
- **Data sources:** `GET /data-sources` — available + enabled connector list for
  the toggle UI.
- **Runs:** `POST /runs/start` (on-demand; body either references a `schedule_id`
  to reuse its config, or supplies an ad-hoc config), returns `{report_id}`;
  `GET /runs` (summaries); `GET /runs/{id}` (detail: sections/charts/citations/
  cover); `DELETE /runs/{id}` (hard-delete, mirroring EU); `POST /runs/{id}/cancel`.
- **Events:** `GET /runs/{id}/events` — SSE stream of engine events.
- **Downloads:** `GET /runs/{id}/html` | `/pdf` | `/docx`.

## 9. Layer 6 — Frontend (`pages/departments/MorningBriefing.tsx`, rewritten)

Adopt the EU page shape, reusing EU components where they are not
earnings-specific (feed cards, generating card, upload modals, ConfirmDialog
delete, viewer integration):

- **Feed** — time-grouped briefing cards (Today / This Week / Older); each card
  shows cover subtitle + key highlights. Live **generating card** driven by SSE
  (phases/current section). Click → report **viewer** (with delete affordance,
  matching the EU delete feature just shipped).
- **Schedule editor** — list + add/edit; each schedule binds template,
  instructions, connector toggles, model/provider, language/length/reasoning, and
  the time/days/timezone/label/enabled fields. Hot-reloads on save.
- **Template & instructions library** (cabinet view) — list/upload/delete
  templates and instructions (markdown or document upload modals).
- **On-demand "Run now"** modal — pick a saved schedule's config or set an ad-hoc
  config, then start a run and stream it in the feed.
- New `api/morning-briefing.ts` client + types; new hooks (`useMbSchedules`,
  `useMbRuns`, `useMbRunStream`, `useMbTemplates`, `useMbInstructions`,
  `useMbDataSources`). Bilingual (en + zh-TW) i18n keys for all new copy.

Retire the old 4-tab page and its `mb_user_configs`-driven settings/run views.

## 10. Core department declaration

`packages/core/src/openlia/departments/morning_briefing.py` — keep the connector
declaration (`required_categories = (FINANCIAL,)`, `required_any_of =
((NEWS, WEB_SEARCH),)`). Keep `routing_context.md`. The department remains a
report-producing department; `requires_runner` stays `False` (the briefing runs
through the new engine + scheduler, not the chat runner).

## 11. Removed

Removed in Phase 6 (commit `e733761b`):

- Legacy services `mb_config.py`, `mb_request_builder.py`, `mb_runner.py`, and
  the OLD `mb_schedules.py` (superseded by `mb_v2_schedules.py`) — plus their
  tests.
- `mb_user_configs` table + `MbUserConfig` model. Dropped via the
  `drop_mb_user_configs` migration (down_revision `morning_briefing_v2`;
  `downgrade` recreates the original shape). The drop was deliberately deferred
  out of the Phase 2 migration so it lands atomically with the model + service
  deletion, keeping `Base.metadata` and the alembic head in sync.
- `MBRequestBuilder` protocol (`scheduler/payloads.py`), the now-dead
  `mb_builder` param of `build_scheduler_service` (`scheduler/wiring.py`), and
  its `MbRequestBuilderImpl` instantiation in `app.py`. The matching test
  doubles (`StubMBRequestBuilder`, `FakeMBBuilder`) and every `mb_builder=` call
  site were removed too. `ReportStore` stays — the EU scan executor uses it.
- Report (`report:*`) blocks of `prompts/morning_briefing.yaml`. The
  `chat:system` block STAYS — it is still referenced by the Secretary "ask about
  a past briefing" desk (and the persona / chat-formatting prompt tests). Because
  `report_mb` builds its own system prompt in code, the startup
  `_DEPARTMENT_SLOTS` (app.py) and the `EXPECTED` slot map in
  `test_prompt_contents.py` for `morning_briefing` collapse to `["chat.system"]`.
- Old route handlers and old frontend tabs/components driven by the sections
  config; old pre-rework `tests/db/test_mb_models.py` + `test_mb_migration.py`.

MB no longer uses the generic `ReportRunner` for generation. The generic
`ReportRunner` / `runtime/report.py` / `reports` table stay (legacy
`earnings_update` route still uses them). Old v1 MB report rows stop being
written; they remain readable in the archive listing.

## 12. Out of scope (YAGNI)

Batch mode, MB watchlist, portfolio coupling, revision/edit flow. Add later only
if a concrete need appears.

### Tracked follow-up (surfaced during execution)

- **MB save-to-repo frontend wiring (deferred).** The backend exposes
  `/api/repo/mb-runs` (save/unsave/list, Phase 3.7) and the repo listing fan-out
  includes MB, but the frontend MB viewer does not yet offer a save-to-repo
  button (`hideSaveToRepoButton`, and `SaveToRepoEngine` has no `"mb"` case).
  Briefings live in the MB feed, so this is a v1-acceptable omission; wiring it
  needs `"mb"` in `SaveToRepoButton`/`repo.ts`/`SavedReportsContext` + a list call.

- **Schedule enable/disable toggle — DONE.** Wired end-to-end: `is_enabled` on
  `ScheduleIn` + `mb_v2_schedules.create_schedule`/`update_schedule`, with
  transition-driven scheduler calls (off→on add, on→off remove, on→on modify,
  off→off no-op) so no shared `scheduler/service.py` change was needed.

## 13. Implementation phasing (hand-off to writing-plans)

1. Core `report_mb` engine fork (schemas, transports, tools, prompts, runner,
   rendering) + unit tests with fake transports.
2. DB models + Alembic migrations (`report_mb*`, `report_mb_templates`/
   `_instructions`, `mb_schedules` config columns, `repo_items.mb_v2_report_id`,
   seed `mb_default`). NOTE: the `mb_user_configs` drop was deferred from this
   phase to Phase 6 so it lands atomically with the model/service deletion.
3. Server services (`mb_v2_run/template/instructions/data_sources/render/wiring/
   schedules`) + executor + wiring rewire + repo fan-out + tests.
4. Route rewrite + route tests.
5. Frontend rework (page, components, api, hooks, i18n) + tests.
6. Delete old MB code (services, model, builder/wiring, prompt report blocks) +
   drop `mb_user_configs` atomically; final targeted-suite + tsc + ruff
   verification. DONE — see §11.

## 14. Testing strategy

- Core: engine turn-loop tests with injected fake `MbDataTransports`; schema
  validation; prompt rendering snapshot.
- Server: route tests (schedules CRUD with config binding, templates/instructions
  upload, runs start/list/detail/delete, data-sources); run-service persistence;
  executor dispatch with a fake engine. Note: full `packages/server/` suite hangs
  on SSE/stream tests (no pytest-timeout) — run targeted test dirs.
- Frontend: page + component tests (feed render, generating card SSE, schedule
  editor config binding, upload modals, delete flow), bilingual key presence.
- Aim ~80% coverage; only necessary tests.
