# Endpoint Contract Matrix

Regenerated: 2026-08-16 (Stage 4.4 of `docs/audit-2026-08-16.md`).
Supersedes the 2026-04-21 version, which listed Plan-9–23 placeholders and
still referenced removed v1/v2/v2.3 engine and data-provider endpoints.

This matrix is the endpoint-level companion to `route-authorization-matrix.md`
(which owns the auth/owner-scoping semantics). It enumerates the live HTTP
surface of `create_app()`, grouped by router, with method, path, and a short
contract note. It is reconciled against the running app — regenerate by
iterating `app.routes` (see `packages/server/tests/test_route_matrix_coverage.py`).

## Conventions

- **Paths** are the FastAPI mount paths. At runtime the frontend calls the
  `/api/<path>` form; `_StripApiPrefixMiddleware` strips `/api` so the same
  bundle works in dev (Vite proxy) and prod.
- **Auth** values: `public`, `authed`, `active-user`, `admin`, `wizard-session`,
  `cookie-optional` — defined in the authorization matrix.
- **Mode**: `both` unless marked `company` (auth + admin routers only).
- SSE endpoints are marked `(SSE)`.

## Setup — `build_setup_router` · `/setup` · both

| Path | Method | Auth | Note |
|---|---|---|---|
| `/setup/status` | GET | public | `{mode, current_step, completed, ...}`; only public setup route. |
| `/setup/state` | GET | wizard-session | Full wizard state snapshot. |
| `/setup/mode` | POST | wizard-session | Choose personal vs company. |
| `/setup/identity` | POST | wizard-session | Instance identity. |
| `/setup/providers` | POST | wizard-session | Connector/provider config during wizard. |
| `/setup/models` | POST | wizard-session | Slot model selection. |
| `/setup/models/test` | POST | wizard-session | Test a model selection. |
| `/setup/access_control` | POST | wizard-session | Signup policy / access mode. |
| `/setup/admin` | POST | wizard-session | Bootstrap first admin (company). |
| `/setup/takeover` | POST | wizard-session | Reclaim an abandoned wizard session; Stage 0.2 adds `require_wizard_active`. |
| `/setup/finish` | POST | wizard-session | Flips `wizard.completed = true`; subsequent writes 410. |

All writes: loopback-gated + `wizard-active`; personal mode rejects non-loopback.

## Auth — `build_auth_router` · `/auth` · company

| Path | Method | Auth | Request → Response |
|---|---|---|---|
| `/auth/register` | POST | public (rate-limited) | `RegisterIn` → `{user_id, email, display_name}` + Set-Cookie |
| `/auth/login` | POST | public (rate-limited) | `LoginIn` → `{..., is_admin, must_change_password}` + Set-Cookie |
| `/auth/logout` | POST | cookie-optional | → 204; clears cookie regardless of validity |
| `/auth/logout-all` | POST | authed | Revoke all sessions → 204 |
| `/auth/session` | GET | authed | `{user_id, email, display_name, is_admin}` |
| `/auth/sessions` | GET | authed | List active sessions for the user |
| `/auth/sessions/{session_id}` | DELETE | authed | Revoke one session |
| `/auth/signup-policy` | GET | public | `{mode, invite_required}` |
| `/auth/password-reset/request` | POST | public (rate-limited) | `{email}` → `{status:"ok"}` (no account-existence leak) |
| `/auth/password-reset/consume` | POST | public (token) | `{token, new_password}` → `{status:"ok"}` |
| `/auth/change-password` | POST | authed (primary unblock) | `{current_password, new_password}` → `{status:"ok"}` |

Register error-code → HTTP map (unchanged from 2026-04): `weak_password`→400,
`registration_failed`→400, `signup_closed`→403, `invite_required`→403,
`invite_invalid`→403, `email_domain_not_allowed`→403, `rate_limited`→429.
`must_change_password` is a response-body flag, not an `_STATUS_MAP` code.

## Admin — `build_admin_router` · `/admin` · company

All `admin`.

| Path | Method | Note |
|---|---|---|
| `/admin/invites` | GET, POST | list / create invite |
| `/admin/invites/{invite_id}/revoke` | POST | → 204 |
| `/admin/users` | GET | list users |
| `/admin/users/{user_id}/disable` | POST | → 204 |
| `/admin/users/{user_id}/enable` | POST | → 204 |
| `/admin/users/{user_id}/reset-password` | POST | → 204 |
| `/admin/users/{user_id}/role` | POST | **NEW** — in-app promote/demote (Stage 3 admin lifecycle) |
| `/admin/password-reset-requests` | GET | pending list |
| `/admin/password-reset-requests/{request_id}/approve` | POST | approval payload |
| `/admin/password-reset-requests/{request_id}/reject` | POST | → 204 |

## Admin graph — `build_admin_graph_router` · `/admin/graph` · both

| Path | Method | Auth | Note |
|---|---|---|---|
| `/admin/graph/extract-now` | POST | admin | Trigger system-wide graph extraction. |

## Admin skills — `build_admin_skills_router` · `/admin/skills` · both

| Path | Method | Auth | Note |
|---|---|---|---|
| `/admin/skills` | GET | active-user + in-handler admin | List all skills across scopes. |
| `/admin/skills/audit` | GET | active-user + in-handler admin | Skill audit log. |

## Guardrail events — `build_guardrail_events_router` · `/admin/guardrail-events` · both

| Path | Method | Auth | Note |
|---|---|---|---|
| `/admin/guardrail-events` | GET | admin | Stage 0.3: all users' rows incl. `response_excerpt`. |
| `/admin/guardrail-events` | DELETE | admin | Purge the global guardrail audit log. |

## Connectors — `build_connectors_router` · `/connectors` · both · admin

| Path | Method | Note |
|---|---|---|
| `/connectors` | GET, POST | list / install |
| `/connectors/builtins` | GET | catalog of builtin connectors |
| `/connectors/install-builtin` | POST | install a builtin by id |
| `/connectors/install-python-package` | POST | install from a pip package |
| `/connectors/introspect-python-lib` | POST | inspect an importable lib for capabilities |
| `/connectors/{connector_id}` | GET, PUT, DELETE | get / update / uninstall |
| `/connectors/{connector_id}/validate` | POST | credential/health check |
| `/connectors/{connector_id}/sync-template-specs` | POST | re-sync capability specs |

## Cache — `build_cache_router` · `/cache` · both · admin

| Path | Method | Note |
|---|---|---|
| `/cache/stats` | GET | document-cache stats |
| `/cache/documents` | DELETE | purge cached documents |

## Settings — LLM admin — `build_llm_providers_admin_router` · `/settings/admin/llm` · both · admin

| Path | Method | Note |
|---|---|---|
| `/settings/admin/llm/providers` | GET, POST | list / create provider |
| `/settings/admin/llm/providers/test` | POST | test provider creds |
| `/settings/admin/llm/providers/{provider_id}` | PUT, DELETE | update / delete |
| `/settings/admin/llm/providers/{provider_id}/models` | GET | provider's models |
| `/settings/admin/llm/providers/{provider_id}/remote-models` | GET | discovery |
| `/settings/admin/llm/models` | POST | create model |
| `/settings/admin/llm/models/{model_id}` | PUT, DELETE | update / delete |
| `/settings/admin/llm/department/{department_id}` | POST | department→model mapping |
| `/settings/admin/llm/capability_override/{provider_kind}/{model:path}` | POST | capability override |

## Settings — LLM slot defaults — `build_llm_slot_defaults_router` · `/settings/admin/llm/slot-defaults` · both · admin

| Path | Method | Note |
|---|---|---|
| `/settings/admin/llm/slot-defaults` | GET | list slot defaults |
| `/settings/admin/llm/slot-defaults/{slot_kind}/{slot_id}` | PUT, DELETE | upsert / clear a slot default |

## Settings — general — `build_settings_general_router` · `/settings` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/settings/prefs` | GET, PATCH | user prefs (display/response/report language, etc.) |
| `/settings/timezone` | PUT | user timezone |
| `/settings/departments` | GET | per-department enable/health view |
| `/settings/enabled-models` | GET | models available to the user (picker) |
| `/settings/preferences/market-basket` | GET, PUT | Home ticker-strip basket |
| `/settings/graph-extraction-time` | PUT | nightly graph-extraction time |

## Settings — email — `build_settings_email_router` · `/settings` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/settings/email` | PATCH | email-notification prefs |

## Jobs — `build_jobs_router` · `/jobs` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/jobs/history` | GET | `JobRun` history (owner-scoped); query `department?`, `status?`, `limit` |
| `/jobs/{run_id}/retry` | POST | 503 if scheduler disabled |

## Notifications — `build_notifications_router` · `/notifications` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/notifications/unread` | GET | `{counts_by_department}` |
| `/notifications/read` | POST | mark a department read |

## Notifications stream — `build_notifications_stream_router` · bare · both · active-user

| Path | Method | Note |
|---|---|---|
| `/notifications/stream` | GET (SSE) | live notification + report events |
| `/notifications/presence-close` | POST | tab-close beacon → drives auto-cancel |

## Dept health — `build_dept_health_router` · `/dept-health` · both · public

| Path | Method | Note |
|---|---|---|
| `/dept-health` | GET | serialized health cache (drives sidebar) |
| `/dept-health/refresh` | POST | recompute + return |

## Capabilities — `capabilities_router` · bare · both · public

| Path | Method | Note |
|---|---|---|
| `/capabilities` | GET | engine capability manifest |

## Markets — `build_markets_router` · `/markets` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/markets/indices` | GET | `{available, indices}`; `available:false` when no EODHD key (Home ticker-strip empty state) |

## Portfolio — `build_portfolio_router` · `/portfolio` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/portfolio/holdings` | GET, POST | list / add holding |
| `/portfolio/holdings/{holding_id}` | PATCH, DELETE | edit / remove (PATCH, not PUT) |
| `/portfolio/analytics` | GET | KPI/analytics over user's holdings |
| `/portfolio/refresh-prices` | POST | 30s per-user cooldown → 429 `{retry_after}` |
| `/portfolio/import-csv` | POST | bulk import |
| `/portfolio/export-csv` | GET | export |
| `/portfolio/search` | GET | adapter-backed ticker lookup |
| `/portfolio/groups` | GET, POST | list / create group |
| `/portfolio/groups/{name}` | PATCH, DELETE | rename / delete group |
| `/portfolio/groups/reorder` | POST | persist group order |
| `/portfolio/prefs` | GET, PUT | per-user portfolio view prefs |
| `/portfolio/value-series` | GET | portfolio value time series |
| `/portfolio/ticker-series` | GET | per-ticker series (sparklines) |

## Reports (v1 engine) — `build_reports_router` · `/reports` · both · active-user

Serves the generic v1 report pipeline (Morning Briefing legacy + Earnings
Update v1). NOT the equity engine.

| Path | Method | Note |
|---|---|---|
| `/reports` | GET | list (query `department?`) |
| `/reports/generate` | POST | kick off a v1 report run |
| `/reports/{report_id}` | GET | fetch report |
| `/reports/{report_id}/render` | GET | HTML render |
| `/reports/{report_id}/retry` | POST | retry a failed run |
| `/reports/{report_id}/export/docx` | GET | DOCX export |
| `/reports/{report_id}/docx` | GET | legacy DOCX alias (slated for removal) |
| `/reports/{report_id}/export/pdf` | GET, POST | PDF export |
| `/reports/{report_id}` | DELETE | delete |

## Reports stream / revise — bare · both · active-user

| Path | Method | Router | Note |
|---|---|---|---|
| `/reports/{report_id}/stream` | GET (SSE) | `build_reports_stream_router` | resume a v1 run |
| `/reports/{source_report_id}/revise` | POST | `build_reports_revise_router` | v1 revision kickoff |

## Repo — `build_repo_router` · `/repo` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/repo/items` | GET | dual-shape: unfiltered flat list, or filtered/paginated `{items, page, page_size, has_more}` with `q/department/generated_*/saved_*/sort/page/page_size` |
| `/repo/items` | POST | save a report (idempotent via `report_id`) |
| `/repo/items` | DELETE | unsave by `?report_id=` |
| `/repo/facets` | GET | `{departments:[{slug,count}], total}` |
| `/repo/v2-runs` | GET, POST, DELETE | saved v2 engine runs |
| `/repo/v3-runs` | GET, POST, DELETE | saved equity v3 runs |
| `/repo/eu-runs` | GET, POST, DELETE | saved Earnings Update v2 runs |
| `/repo/mb-runs` | GET, POST, DELETE | saved Morning Briefing v2 runs |

## Report templates — `build_report_templates_router` · `/report-templates` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/report-templates` | GET, POST | list / create (owner-scoped) |
| `/report-templates/{template_id}` | GET, PUT, DELETE | get / update / delete |
| `/report-templates/ingest` | POST | ingest a template from source |
| `/report-templates/parse` | POST | parse a template body |
| `/report-templates/v23/builtins` | GET | builtin template-FORMAT catalog (shared library helper) |
| `/report-templates/v23/parse` | POST | parse in the v23 template format |
| `/report-templates/v23/validate` | POST | validate a v23-format template |

## Chat sessions / stream — `/chat/sessions` · both · active-user

| Path | Method | Router | Note |
|---|---|---|---|
| `/chat/sessions` | GET, POST | chat_sessions | list / create |
| `/chat/sessions/by-department/{department}` | GET | chat_sessions | resolve-or-fetch per department |
| `/chat/sessions/{session_id}` | GET, PATCH, DELETE | chat_sessions | get / rename / delete |
| `/chat/sessions/{session_id}/messages` | GET, POST | chat_sessions | history / send (POST drives the runner) |
| `/chat/sessions/{session_id}/model` | PUT | chat_sessions | set the session's model |
| `/chat/sessions/{session_id}/stream` | GET (SSE) | chat_stream | live token stream |

## Files — `build_files_router` · bare · both · active-user

| Path | Method | Note |
|---|---|---|
| `/chat/attachments/{attachment_id}/download` | GET | owner-scoped attachment download |

## Graph — `build_graph_router` · `/graph` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/graph/constructs` | GET | user's graph constructs |
| `/graph/constructs/{construct_id}` | DELETE | delete a construct |
| `/graph/proposals` | GET | pending extraction proposals |
| `/graph/proposals/{proposal_id}/accept` | POST | accept → construct |
| `/graph/proposals/{proposal_id}/dismiss` | POST | dismiss |

## Skills — `build_skills_router` · `/skills` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/skills` | GET | list installed skills (layered) |
| `/skills/install` | POST | install a skill (Stage 3: `folder_path` install must be admin-gated) |
| `/skills/{skill_id}` | PATCH, DELETE | toggle/edit (Stage 3: system-skill PATCH must be admin-gated) / uninstall |
| `/skills/{skill_id}/body` | GET | skill body |

## Disclaimer — `build_disclaimer_router` · `/disclaimer` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/disclaimer` | GET | disclaimer content |
| `/disclaimer/status` | GET | acceptance status for the user |
| `/disclaimer/accept` | POST | record acceptance on `UserPrefs` |

## Dev — `build_dev_router` · `/dev` · both · public (env-gated)

| Path | Method | Note |
|---|---|---|
| `/dev/info` | GET | `{enabled:true}` or 404 |
| `/dev/events` | GET | recent dev events |
| `/dev/events/stream` | GET (SSE) | live dev event stream |

Every handler 404s unless `OPENLIA_DEV_MODE` is set.

## Department model pref — `build_department_model_pref_router` · `/departments` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/departments/{department}/model-pref` | GET, PUT, DELETE | per-user per-department model preference |

## Secretary — `build_secretary_router` · `/departments/secretary` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/departments/secretary/chat` | GET | welcome/context |
| `/departments/secretary/chat` | POST (SSE) | Secretary ChatRunner |

## Equity Research v3 — `build_equity_research_v3_router` · `/departments/equity-research/v3` · both · active-user

Sole equity engine. Owner-scoped on `ReportV3Run.user_id`.

| Path | Method | Note |
|---|---|---|
| `/departments/equity-research/v3/runs` | GET, POST | list / create run |
| `/departments/equity-research/v3/runs/start` | POST | start a run |
| `/departments/equity-research/v3/runs/{report_id}` | GET, DELETE | fetch / delete |
| `/departments/equity-research/v3/runs/{report_id}/cancel` | POST | cancel |
| `/departments/equity-research/v3/runs/{report_id}/events` | GET (SSE) | run events |
| `/departments/equity-research/v3/runs/{report_id}/revise` | POST | start a revision |
| `/departments/equity-research/v3/runs/{report_id}/revisions` | GET | list revisions |
| `/departments/equity-research/v3/runs/{report_id}/{html,pdf,docx}` | GET | exports |
| `/departments/equity-research/v3/revisions/{revision_id}/events` | GET (SSE) | revision events |
| `/departments/equity-research/v3/revisions/{revision_id}/cancel` | POST | cancel revision |
| `/departments/equity-research/v3/instructions` | GET, POST | methodology profiles |
| `/departments/equity-research/v3/instructions/{instructions_id}` | DELETE | delete profile |
| `/departments/equity-research/v3/templates` | GET, POST | templates |
| `/departments/equity-research/v3/templates/{template_id}` | DELETE | delete template |

## Earnings Update v1 (legacy) — `build_earnings_update_router` · `/departments/earnings-update` · both · active-user

Runs on the generic v1 `reports` pipeline. Kept per CLAUDE.md.

| Path | Method | Note |
|---|---|---|
| `/departments/earnings-update/config` | GET, PUT | per-user config |
| `/departments/earnings-update/report` | POST | on-demand run |
| `/departments/earnings-update/reports` | GET | list |
| `/departments/earnings-update/reports/{report_id}` | DELETE | delete |
| `/departments/earnings-update/schedules` | GET, POST | schedule CRUD |
| `/departments/earnings-update/schedules/{schedule_id}` | PATCH, DELETE | edit / delete |
| `/departments/earnings-update/watchlist` | GET, POST | watchlist |
| `/departments/earnings-update/watchlist/{entry_id}` | DELETE | remove entry |

## Earnings Update v2 — `build_earnings_update_v2_router` · `/departments/earnings-update/v2` · both · active-user

Owner-scoped on `EuV2Run.user_id`.

| Path | Method | Note |
|---|---|---|
| `/departments/earnings-update/v2/runs` | GET | list runs |
| `/departments/earnings-update/v2/runs/start` | POST | start |
| `/departments/earnings-update/v2/runs/{report_id}` | GET, DELETE | fetch / delete |
| `/departments/earnings-update/v2/runs/{report_id}/cancel` | POST | cancel |
| `/departments/earnings-update/v2/runs/{report_id}/events` | GET (SSE) | run events |
| `/departments/earnings-update/v2/runs/{report_id}/{html,pdf,docx}` | GET | exports |
| `/departments/earnings-update/v2/settings` | GET, PUT | engine settings |
| `/departments/earnings-update/v2/instructions` | GET, POST | profiles |
| `/departments/earnings-update/v2/instructions/{instructions_id}` | DELETE | delete |
| `/departments/earnings-update/v2/templates` | GET, POST | templates |
| `/departments/earnings-update/v2/templates/{template_id}` | DELETE | delete |
| `/departments/earnings-update/v2/watchlist` | GET, POST | watchlist |
| `/departments/earnings-update/v2/watchlist/sync` | POST | sync from calendar |
| `/departments/earnings-update/v2/watchlist/{entry_id}` | DELETE | remove |
| `/departments/earnings-update/v2/schedule` | GET | schedule view |
| `/departments/earnings-update/v2/data-sources` | GET | resolved connector/data-source state |

## Morning Briefing v2 — `build_morning_briefing_router` · `/departments/morning-briefing` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/departments/morning-briefing/runs` | GET | list |
| `/departments/morning-briefing/runs/start` | POST | start (SSE via `/events`) |
| `/departments/morning-briefing/runs/{report_id}` | GET, DELETE | fetch / delete |
| `/departments/morning-briefing/runs/{report_id}/cancel` | POST | cancel |
| `/departments/morning-briefing/runs/{report_id}/events` | GET (SSE) | run events |
| `/departments/morning-briefing/runs/{report_id}/{html,pdf,docx}` | GET | exports |
| `/departments/morning-briefing/schedules` | GET, POST | schedule CRUD |
| `/departments/morning-briefing/schedules/{schedule_id}` | PATCH, DELETE | edit / delete |
| `/departments/morning-briefing/instructions` | GET, POST | profiles |
| `/departments/morning-briefing/instructions/{instructions_id}` | DELETE | delete |
| `/departments/morning-briefing/templates` | GET, POST | templates |
| `/departments/morning-briefing/templates/{template_id}` | DELETE | delete |
| `/departments/morning-briefing/data-sources` | GET | resolved data-source state |

## Macro Research — `build_macro_research_router` · `/departments/macro_research` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/departments/macro_research/dashboards` | GET | enumerate Dalio dashboards |
| `/departments/macro_research/dashboards/{slug}` | GET | one dashboard snapshot |
| `/departments/macro_research/dashboards/{slug}/refresh` | POST | recompute snapshot |

### MR schedule — `build_mr_schedule_router` · `/departments/macro_research/schedule` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/departments/macro_research/schedule` | GET, PUT, DELETE | assessment schedule; validates ownership before scheduler calls |

## Retail Sentiment — `build_retail_sentiment_router` · `/departments/retail_sentiment` · both · active-user

Redesigned as the `report_dash_rs` web-search dashboard engine.

| Path | Method | Note |
|---|---|---|
| `/departments/retail_sentiment/dashboard/{ticker}` | GET | per-ticker sentiment dashboard |
| `/departments/retail_sentiment/dashboard/{ticker}/history` | GET | snapshot history |
| `/departments/retail_sentiment/dashboard/{ticker}/refresh` | POST | recompute |
| `/departments/retail_sentiment/config` | GET, PUT | per-user config |
| `/departments/retail_sentiment/schedule` | GET, PUT | refresh schedule |

## Panic Thermometer — `build_panic_thermometer_router` · `/departments/panic_thermometer` · both · active-user

| Path | Method | Note |
|---|---|---|
| `/departments/panic_thermometer/dashboard` | GET | computed dashboard |
| `/departments/panic_thermometer/config` | GET, PUT | per-user config |
| `/departments/panic_thermometer/config/export` | GET | export config |
| `/departments/panic_thermometer/config/import` | POST | import config |
| `/departments/panic_thermometer/presets` | GET, POST | shipped (global) + user presets |
| `/departments/panic_thermometer/presets/{preset_id}` | PUT, DELETE | edit / delete user preset |
| `/departments/panic_thermometer/presets/{preset_id}/apply` | POST | apply a preset |
| `/departments/panic_thermometer/formula/parse` | POST | parse a formula |
| `/departments/panic_thermometer/formula/test` | POST | evaluate a formula |
| `/departments/panic_thermometer/ruleset/preview` | POST | preview ruleset output |

## Infrastructure (app-level)

| Path | Method | Auth | Note |
|---|---|---|---|
| `/health` | GET | public | `{status:"ok"}` |
| `/healthz` | GET | public | `{status:"ok", mode}` |
| `/_debug/client_host` | GET | public | `include_in_schema=false`; peer-IP debug |
| `/{full_path}` | GET | public | SPA fallback; only when `OPENLIA_FRONTEND_DIST` set; `/api/*` and non-GET 404 as JSON |

## Merge gate

- Every new or renamed endpoint lands here in the same PR as the code.
- `test_route_matrix_coverage.py` fails CI if a new router prefix is missing
  from the authorization matrix; keep both files in sync.
- Auth/DTO changes update this row and the frontend client together.

## Removed since April 2026 (do not re-add)

- Equity-research v1 / v2 / v2.3 engine endpoints, their per-user config CRUD,
  and the legacy equity chat route — removed with the old engines (PRs
  #220/#222). v3 is the sole equity surface.
- The standalone data-provider admin registry under `/settings/...` — folded
  into `/connectors`.
- Retail Sentiment's old per-post pipeline endpoints (`/run`, `/spikes`,
  `/stocks/{ticker}/sentiment`, global `/dashboard`) — replaced by the
  per-ticker dashboard routes above.
- The old MB config/schedule/report/chat-session route shape — replaced by the
  MB v2 runs/schedules/instructions/templates surface.
