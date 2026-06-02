# Batch Execution Mode (Design)

Status: design / approved-to-plan
Date: 2026-06-01
Scope: Feature 2 of 2 in the "batch reports" initiative. This spec covers
**only** batch execution for **Earnings Update v2 scheduled runs**. Equity
Research scheduling (Feature 1) and ER batch are out of scope here (see
"Sequencing & out of scope").

## Goal

Let a user opt scheduled Earnings Update reports into the provider **Batch
API** (OpenAI / Anthropic) instead of the live ("on-demand") API, to cut
LLM **cost** (~50% off input+output per token). Async delivery is accepted:
batch reports arrive within hours (provider SLA 24h, usually under 1h), with
no live progress stream.

This is opt-in per user via a settings toggle. Default is unchanged (sync).

## Non-goals / honest constraints

- **Batch does not reduce token *count*** — it halves token *price*. "Save
  tokens" here means "save cost."
- **No interactive loop inside one batch request.** The EU engine is a
  multi-turn tool-use loop (4-60 turns); each turn depends on the prior
  turn's locally-executed tools. A batch request is one model turn. So a
  batched report submits **one turn at a time** through the batch queue.
- **Cross-turn prompt caching likely goes cold.** Batch turns land
  minutes-to-hours apart, longer than the prefix-cache TTL. So the growing
  conversation re-bills at the 50% batch rate each turn rather than ~10%
  cached. Net cheaper than uncached sync; on Anthropic (cache read = 90%
  off) it may not beat sync+warm-cache when the prefix dominates. **Measure
  real savings** (via `report_eu_tool_call_log` token columns) before
  extending. This is a known characteristic, not a blocker — the user has
  opted into it.
- Where batch genuinely pays off: **many scheduled reports dispatched
  together**, run in lockstep so each batch carries every active report's
  next turn (parallelism + discount). A single isolated report is the worst
  case (no parallelism, full per-turn latency compounded).

## Decisions (locked)

| Decision | Choice |
|---|---|
| Goal | Cost reduction via Batch API; async accepted |
| Trigger scope | Scheduled runs only (EU `EU_V2_DISPATCH`) |
| Providers (v1) | OpenAI + Anthropic; others (OpenRouter/Ollama/Gemini) fall back to sync |
| Toggle | Per-user, per-department: `eu_v2_settings.batch_enabled` |
| Sequencing | Batch (this) first, validated on EU; ER scheduling + ER batch later |

## Architecture overview

Today: `EuV2DispatcherImpl.dispatch_due` loops due rows and calls
`start_run_async` per ticker — N independent background tasks, each running
the inline sync turn loop (`session.generate()` per turn).

New: a **turn-synchronized batch orchestrator** drives a group of due
reports together. Each cycle: collect every active run's next-turn request →
submit as one provider batch → poll → distribute responses → run each run's
tools locally → advance. Runs finish at different turn counts and drop out;
the next batch carries only still-active runs.

```
EuV2DispatcherImpl.dispatch_due(now)
  partition due rows:
    batch-eligible  = user.batch_enabled AND supports_batch(provider, model)
    sync-eligible   = everything else  -> existing start_run_async (unchanged)
  group batch-eligible by (provider_kind, model)   # a batch is single-model
  for each group:
    create eu_v2_batch_job + one report_eu row (status=running) per run
    build each run's initial EuRunState
    spawn BatchOrchestrator(group) as a background task
```

### Components

**1. Provider batch transport** — `core/llm/batch_transport.py` (new)

A capability separate from `LLMProvider` (not all providers support it):

```python
class BatchTransport(Protocol):
    async def submit_batch(self, items: list[BatchRequestItem]) -> str        # provider batch_id
    async def poll_batch(self, batch_id: str) -> BatchStatus                  # in_progress|completed|failed|expired
    async def fetch_results(self, batch_id: str) -> dict[str, LLMResponse]    # keyed by custom_id
    async def cancel_batch(self, batch_id: str) -> None
```

- `BatchRequestItem = (custom_id, LLMRequest)`.
- Request bodies are built with the **same** request->payload translation the
  sync adapters already use (refactor the body-builder out of each adapter's
  `generate` so the batch path reuses it byte-for-byte, including tools,
  native tools, reasoning effort, cache hints).
- OpenAI impl: JSONL input file, lines `{custom_id, method:"POST",
  url:"/v1/responses", body}`, Files+Batches API. (Responses + tool calling
  are batch-supported.)
- Anthropic impl: Message Batches — `requests:[{custom_id, params}]`; tool
  use is supported (any Messages request is batchable).
- `supports_batch(provider_kind, model) -> bool` gate. OpenRouter/Ollama/
  Gemini -> False -> sync fallback.

**2. Step-wise run state** — refactor EU runner into `EuRunState`

Extract the turn-loop body from `report_eu/runner.py` so it can be driven
externally. `EuRunState` owns messages/workspace/ledger/catalog/system
prompt (exactly what `Runner` builds today) and exposes:

- `pending_request() -> LLMRequest | None` — next generate-request, or None
  if terminal (finalized / failed / limit).
- `apply_response(LLMResponse) -> None` — ingest one model turn: append
  assistant message, ingest web citations, dispatch tools locally, append
  tool messages, append web-citation notice, check finalize/limits.
- `result() -> RunResult | None` — populated once terminal.
- `snapshot() / restore()` — serialize/deserialize full state to JSON.

The existing inline `Runner.run` is rewritten to drive an `EuRunState` in a
local loop (sync path keeps identical behavior; this is a pure refactor with
a parity test). Tools still run locally; only `session.generate()` is
externalized for the batch path.

**3. Batch orchestrator** — `core/llm/runtime/batch_orchestrator.py` (new)

```
runs = [EuRunState, ...]   # one group, one (provider, model)
while any run active:
    items   = [(run.custom_id, run.pending_request()) for run in active runs]
    batch_id = transport.submit_batch(items)
    persist job(batch_id, turn) + each run.snapshot()        # resume point
    while poll_batch(batch_id) == in_progress: sleep(poll_interval)
    results = transport.fetch_results(batch_id)
    for run in active: run.apply_response(results[run.custom_id]); persist snapshot
    for run now terminal: persist RunResult + flip report_eu row + notify
    advance turn
on expiry / failed batch: mark remaining runs failed
```

Provider/server-side concerns the orchestrator owns: poll interval, max wall
clock, per-run failure isolation (one bad response fails that run only),
cancellation.

**4. Persistence & resume** (mandatory — a submitted batch bills server-side)

New tables:

- `eu_v2_batch_job`: `id`, `provider_kind`, `model`, `status`
  (submitted|polling|completed|failed), `provider_batch_id` (current
  in-flight batch), `turn_index`, `created_at`, `updated_at`.
- `eu_v2_batch_run`: `id`, `batch_job_id` FK, `report_id` FK (-> `report_eu`),
  `custom_id`, `state_json` (snapshot of messages+workspace+ledger+turn),
  `status` (active|completed|failed), `updated_at`.

Startup recovery (`app` lifespan): for each non-terminal `eu_v2_batch_job`,
re-attach — poll the `provider_batch_id`; if completed, fetch+apply+continue;
if in_progress, resume polling. **`cleanup_orphaned_running_rows` must skip
`report_eu` rows that belong to a live batch job** — batch reports stuck in
`running` are legitimately in-flight and must not be force-failed at startup.

**5. Dispatch integration** — `eu_v2_scheduler_impl.EuV2DispatcherImpl`

Partition due rows (above). Sync path unchanged. Batch path builds the
group, creates job + run rows, spawns the orchestrator as a background task
(same `_BACKGROUND_TASKS` strong-ref pattern as `start_run_async`). Reuses
`build_run_request` per row. `select_due_rows` / `mark_reported` /
`mark_failed` semantics preserved (a row is `reported` once its `report_eu`
row exists).

**6. Completion / notification**

On terminal run: existing `persist_result` + flip `report_eu` row to
completed/failed (same as `_persist_background_outcome`), then reuse the
`REPORT_READY` notification so the user learns the scheduled batch report
landed. No live SSE (scheduled runs already use a throwaway broker).

**7. Settings toggle**

- DB: add `batch_enabled` Boolean (default False, `server_default "0"`) to
  `eu_v2_settings` + Alembic migration.
- Service `eu_v2_settings` get/update carries the field.
- API: EU settings route exposes `batch_enabled`.
- Frontend: a toggle in EU settings: "Batch mode — generate scheduled
  reports via the provider Batch API at ~50% cost. Reports arrive within
  hours, not live." Disabled/explained when the selected provider has no
  batch support.

**8. Config & guards**

- `OPENLIA_BATCH_POLL_INTERVAL_SECONDS` (default 120), `OPENLIA_BATCH_MAX_WAIT_HOURS` (default 24).
- `batch_enabled` true but provider unsupported -> sync fallback + warning log (no error).
- Per-run failure isolation; batch expiry -> remaining runs failed with a clear message.

## Data flow (batch happy path)

1. Cron fires `EU_V2_DISPATCH`. `dispatch_due` finds due rows.
2. Batch-eligible rows grouped by (provider, model); `eu_v2_batch_job` +
   `report_eu` rows (running) + `eu_v2_batch_run` rows created.
3. Orchestrator turn 0: submit all initial requests as one batch; persist.
4. Poll until complete; fetch; each run applies its response, runs tools.
5. Repeat per turn; finalized runs persist `RunResult`, flip to completed,
   emit `REPORT_READY`.
6. Job terminal when all runs terminal; job row -> completed.

## Testing

- Transport adapters (fake HTTP): submit/poll/fetch round-trip, custom_id mapping, expiry/failed.
- `EuRunState` parity: stepwise drive vs current inline runner over scripted responses produces identical `RunResult` (reuse existing fake-adapter EU runner test).
- Snapshot/restore round-trip; resume-on-startup recovers an in-flight job and finishes it.
- Orchestrator: N runs finishing at different turns -> batches shrink, terminal runs persisted; one failing run doesn't sink the group.
- Dispatch partitioning: batch vs sync by setting + provider support; unsupported provider falls back to sync.
- Integration: scheduled dispatch with `batch_enabled` + fake transport -> report rows complete + `REPORT_READY` emitted.

## Sequencing & out of scope

- **This spec (now):** EU scheduled batch, OpenAI + Anthropic.
- **Later, Feature 1:** Equity Research scheduling (new `JobType`, saved
  scheduled-report definitions + cadence, dispatch executor). Once it exists,
  ER batch reuses the same `BatchTransport` + orchestrator (generalize
  `EuRunState` extraction to a shared `RunState` protocol covering report_v3).
- Out of scope here: on-demand/manual batch; Gemini/OpenRouter batch; a
  cost-savings dashboard; extended-cache (1h TTL) cross-turn cache tuning.

## Key files

New (core): `llm/batch_transport.py`, `llm/adapters/openai_batch.py`,
`llm/adapters/anthropic_batch.py`, `llm/runtime/batch_orchestrator.py`,
`llm/runtime/report_eu/run_state.py` (extracted from `runner.py`).

New (server): `db/models` additions (`EuV2BatchJob`, `EuV2BatchRun`) +
Alembic migrations (new tables + `eu_v2_settings.batch_enabled`),
`services/eu_v2_batch_service.py` (orchestrator wiring + persistence),
startup recovery hook.

Changed: `report_eu/runner.py` (drive `EuRunState`), `eu_v2_scheduler_impl.py`
(partition + spawn orchestrator), `eu_v2_settings.py` + EU settings route +
frontend EU settings, `cleanup_orphaned_running_rows` (skip live batch rows).
