# Stage 3 notes — audit-2026-08-16 (items 3.7, 3.8, 3.9)

Investigation + fix notes for three Stage 3 (multi-user hardening) items.
Every claim carries a `file:line` citation. Branch: `fix/audit-stage-3`.

---

## 3.7 — Graph `is_trigger_disabled` global flag (RESOLVED — no change needed)

**Concern:** `graph_entities.is_trigger_disabled`
(`packages/server/src/openlia_server/db/models/graph.py:46-51`) is a global,
unowned boolean on a shared table (`graph_entities` / `graph_edges` have no
`user_id` — by design; retrieval scopes through `graph_user_constructs`).
If a non-admin route could flip it, one user could globally suppress a shared
entity's trigger for everyone.

**Full grep of every writer of the flag (packages/, `*.py`):**

| Site | Kind | Notes |
|---|---|---|
| `db/models/graph.py:46-51` | model column def | `default=False`, `server_default="0"` |
| `db/migrations/versions/2026-05-10-2400_entity_trigger_flag.py:30,40` | migration | add/drop column only |
| `services/graph_retrieval.py:60,68-69,86` | **read only** | retrieval filter `is_trigger_disabled.is_(False)` |
| `tests/test_services/test_graph_retrieval.py:174,185` | test | `entity.is_trigger_disabled = True` (in-test setup) |

**Verdict: no HTTP surface writes this flag at all — not admin, not non-admin.**
- The entity-creating service, `services/graph_store.py:69-90` (`create_entity`),
  constructs `GraphEntity(id=pk, kind=kind, value=normalized, props=props)`
  (`graph_store.py:87`) and never touches `is_trigger_disabled`.
- Both graph routers were read: `routes/graph.py` (proposals + constructs, all
  scoped to `user.id`) and `routes/admin_graph.py` (admin-only `extract-now`,
  guarded by `build_require_active_admin` at `admin_graph.py:88`). Neither
  references the flag.
- The flag is currently only settable by direct DB access (or a migration/test).

This is the safest possible state: there is no writer to gate. **No code change
made.** No new test added (nothing changed). If a future feature adds a
"disable trigger" endpoint, it must live on an admin router
(`build_require_active_admin`) because the flag is global — recorded here as the
design constraint.

---

## 3.8 — Scheduler executors & `job_runs.user_id` propagation (INVESTIGATION — no leak found)

`job_runs.user_id` is nullable (`db/models/scheduler.py:155-159`). Two job
classes exist; both handle `user_id` correctly.

### Dispatch mechanics
- Per-user schedules register with the owning row's id:
  `service.py:331` → `args=(job_type, schedule.user_id, schedule_id)`
  (backfill path identical at `service.py:478`).
- The APScheduler callback threads it straight through:
  `_run_job(job_type, user_id, schedule_id)` → `executor.execute(user_id=user_id, ...)`
  (`service.py:297-302`).
- `job_runs.user_id` is stamped from that same value:
  `BaseExecutor._start_run` → `jobs_svc.start_run(..., user_id=user_id)`
  (`executors/base.py:143-155`).

### Per-user executors (user_id required + all queries scoped) — FINE
| Executor | File | Evidence |
|---|---|---|
| MB briefing | `executors/mb.py:81-122` | `assert user_id is not None`; loads `MbSchedule` by `schedule_id`; `build_run_request(..., user_id=user_id)`; `run_to_completion(..., user_id=user_id)` |
| EU scan (v1) | `executors/eu.py:52-107` | `assert user_id is not None`; planner `plan(user_id=...)`; runner `run(user_id=...)`; `report_store.save(user_id=...)` |
| MR dashboard | `executors/mr_dash.py:81-91` | `assert user_id is not None`; `run_to_cache(..., user_id=user_id, dashboard_slug=schedule_id)` |
| RS snapshot | `executors/rs.py:76-107` | `assert user_id is not None`; watchlist query `where(EuWatchlistEntry.user_id == user_id)`; `run_to_cache(..., user_id=user_id)` |
| Graph extraction | `executors/graph_extraction.py:148,266,302` | `assert user_id is not None`; both phases filter `ChatSession.user_id == user_id` / `Report.user_id == user_id` |

### Global executors (registered with `user_id=None`) — FINE by design
| Executor | Registration | How it stays isolated |
|---|---|---|
| EU v2 sync | `service.py:434` `args=(EU_V2_SYNC, None, None)` | Operates on shared EODHD earnings-calendar; `sync_all_watchlists` sweeps all watchlists (`eu_v2_scheduler_impl.py:57-66`). No per-user output. |
| EU v2 dispatch | `service.py:448` `args=(EU_V2_DISPATCH, None, None)` | Fans out per due row using `row.user_id` for both `build_run_request(user_id=row.user_id)` and `start_run_async(user_id=row.user_id)` (`eu_v2_scheduler_impl.py:100-119`). Each fired run is correctly attributed to its own owner. |
| Portfolio price refresh | `service.py:418` `args=(PORTFOLIO_PRICE_REFRESH, None, None)` | Refreshes a **shared** ticker quote cache (`refresh_due_quotes`, `executors/portfolio_prices.py:49-64`), not user rows. Notification path is naturally skipped (`base.py:174` gates on `user_id is not None`). No cross-user data touched. |
| System maintenance | `_register_maintenance_job` (`service.py:337-344`) | Global retention sweep (`executors/maintenance.py:37-185`): expired sessions, password-resets, notifications, job_runs, guardrail log, unsaved-report tombstoning, RS-cache prune. Cross-user by definition (admin-level housekeeping). Deletes by age/status, never re-attributes ownership. |

### `job_runs.user_id=NULL` rows never leak to users — FINE
- Read surface `routes/jobs.py` scopes strictly: `get_history` calls
  `jobs_service.list_for_user(..., user_id=user.id)` (`routes/jobs.py:83`) and
  `retry_run` guards `run.user_id != user.id` → 404 (`routes/jobs.py:101-102`).
  A `NULL`-`user_id` global-job row matches no user filter, so it is invisible
  to every non-admin. Notifications are only inserted when `user_id is not None`
  (`base.py:174,189`).
- Manual RS single-ticker refresh passes the caller's own id:
  `routes/departments/retail_sentiment.py:250-253`
  (`scheduler.run_now(..., user_id=user.id, schedule_id=ticker)`); the RS
  executor then processes only that ticker for that user
  (`executors/rs.py:88-91,99-106`).

**Verdict (3.8): no problem found.** Per-user jobs propagate `user_id` from the
owning schedule row and scope every query by it; global jobs use `user_id=None`
intentionally and either fan out per-row by `row.user_id` or act on
shared/global data. No job reads or writes another user's data. The nullable
`job_runs.user_id` is correct — it is `NULL` only for genuinely
system/global jobs, which the read side filters out. No follow-up required.

---

## 3.9 — CSRF posture (INVESTIGATION — two state-changing GETs found; recommend follow-up)

**Current defense:** session cookie only, `SameSite=Lax`, no CSRF token.
`SameSite=Lax` blocks cross-site cookie attachment on cross-site **POST/PUT/
PATCH/DELETE**, but **does** send the cookie on a **top-level cross-site GET
navigation** (link click, `window.location`, 302 redirect). So the residual
CSRF surface is exactly: any GET handler that mutates state or triggers a
costly side effect. (The attacker cannot read the opaque cross-origin response,
but the side effect still fires.)

**Method:** scanned all 116 `@router.get` handlers; flagged any whose body (up
to the next route decorator) contains a write/side-effect token
(`.commit()`, `.add(`, `run_now(`, `start_run`, `upsert_`, `delete/update`
execute, `record_run`, `mark_*`). Three matched; one is benign.

| GET endpoint | File:line | Side effect | Verdict |
|---|---|---|---|
| `GET /secretary/chat?q=&session_id=` | `routes/departments/secretary.py:380` → `_stream` (`:72-133`) | Triggers an LLM chat run unconditionally (token/cost burn, `dev_events` record). When `session_id` is a valid owned session, also persists a user `ChatMessage` + `db.commit()` (`:124-133`) and auto-titles. When `session_id` omitted, no DB write but the LLM run still executes. | **Exposed.** Needs only the victim's auth cookie (no id required for the token-burn variant). Real state-changing GET. |
| `GET /chat/sessions/{session_id}/stream?q=` | `routes/chat_stream.py:65` | Persists a user `ChatMessage` via `db.add(...)` + `db.commit()` (`chat_stream.py:85-96`), auto-titles the session, then triggers an LLM run. | **Exposed but id-gated.** `session_id` is an unguessable UUID scoped to the owner (`svc.get_session(..., user_id=user.id)` → 404 otherwise), so mutation requires knowing a victim-owned id; lower exploitability but still a mutating GET. |
| `GET /reports/{report_id}/stream` | `routes/reports_stream.py:68` | `.add(` is `task.subscriber_queues.add(queue)` — an **in-memory set** subscribe to an already-running background run (`reports_stream.py:88`). No DB write, no run trigger. | **Benign** — not a CSRF concern. |

Read-only GETs confirmed clean (no write tokens): all report export/render GETs
(`.../runs/{id}/html|pdf|docx`, `reports/{id}/render`, `export/docx`) generate
artifacts without DB mutation; `portfolio GET /search` and
`settings GET /providers/{id}/remote-models` make outbound provider calls but
persist nothing; all dashboard GETs (`retail_sentiment`, `macro_research`,
`panic_thermometer`) are pure reads — their writes/`run_now` live in the sibling
`POST .../refresh` handlers (`retail_sentiment.py:199`, `macro_research.py:81`,
`portfolio.py:476`), not the GETs.

**Why these two are GET:** both are SSE endpoints; browser `EventSource` only
issues GET, so the message payload rides in the query string and the mutation
was folded into the stream open.

**Recommendation (do NOT implement a token system as part of this audit item):**
1. Preferred: move the message-persist + run-trigger out of the GET. Have a
   `POST` create the user message and mint a short-lived one-time stream token;
   the SSE `GET` then only replays events for that token and performs no
   mutation. This closes the gap without a global CSRF-token framework and keeps
   `EventSource` working.
2. Cheaper interim: require a custom request header (e.g. `X-Requested-With`) on
   these two endpoints — impossible to set on a cross-site top-level navigation
   — and/or switch the frontend from `EventSource` to a `fetch`-based SSE reader
   that can send it. Note this changes the client, so treat as a follow-up.
3. At minimum, document the exposure and the unguessable-UUID mitigation for the
   `/chat/sessions/{id}/stream` variant.

**Verdict (3.9):** `SameSite=Lax` covers the mutating POST/PUT/DELETE surface,
but two SSE GET endpoints carry state changes / LLM-cost side effects and are
reachable via cross-site top-level GET. `/secretary/chat` is the more exposed of
the two (no id required for the token-burn path). Recommend the POST-mint-token
refactor above in a dedicated follow-up.
