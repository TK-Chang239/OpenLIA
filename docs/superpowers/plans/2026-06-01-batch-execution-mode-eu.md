# Batch Execution Mode (EU) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users opt scheduled Earnings Update v2 reports into the provider Batch API (OpenAI + Anthropic) instead of the live API, to cut LLM cost ~50%, accepting async delivery.

**Architecture:** A per-user `batch_enabled` toggle routes EU scheduled dispatch through a turn-synchronized batch orchestrator: the EU runner's turn loop is extracted into a step-wise `EuRunState`; the orchestrator drives a group of runs together, submitting every active run's next turn as one provider batch, polling, distributing responses, running tools locally, and advancing. Batch job + per-run state persist to new tables so an in-flight batch survives server restarts.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy + Alembic (SQLite), httpx, pydantic; React/TypeScript/Vite frontend. `uv` + `ruff` + `pytest`.

Spec: `planning/specs/systems/batch-execution-mode-design.md`

---

## File Structure

New (core):
- `packages/core/src/openlia/llm/batch_transport.py` — `BatchTransport` protocol, `BatchRequestItem`, `BatchStatus`, `BatchResultItem`, `supports_batch()`.
- `packages/core/src/openlia/llm/adapters/openai_batch.py` — OpenAI Responses batch transport.
- `packages/core/src/openlia/llm/adapters/anthropic_batch.py` — Anthropic Message Batches transport.
- `packages/core/src/openlia/llm/runtime/report_eu/run_state.py` — `EuRunState` (step-wise loop body extracted from `runner.py`) + snapshot/restore.
- `packages/core/src/openlia/llm/runtime/batch_orchestrator.py` — `BatchOrchestrator` driving N `EuRunState`s in lockstep.

New (server):
- `packages/server/src/openlia_server/db/models/report_eu.py` — add `EuV2BatchJob`, `EuV2BatchRun` (same module).
- migrations: `..._eu_v2_settings_batch_enabled.py`, `..._eu_v2_batch_tables.py`.
- `packages/server/src/openlia_server/services/eu_v2_batch_service.py` — orchestrator wiring + persistence + startup recovery.

Changed:
- `packages/core/src/openlia/llm/adapters/openai_responses.py` — extract `build_responses_payload()` from `generate()`.
- `packages/core/src/openlia/llm/adapters/anthropic.py` — extract payload builder + result parser.
- `packages/core/src/openlia/llm/runtime/report_eu/runner.py` — `Runner.run` drives an `EuRunState`.
- `packages/server/src/openlia_server/services/eu_v2_settings.py` — carry `batch_enabled`.
- `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py` — settings I/O carries `batch_enabled`.
- `packages/server/src/openlia_server/services/eu_v2_scheduler_impl.py` — partition due rows (batch vs sync), spawn orchestrator.
- `packages/server/src/openlia_server/services/eu_v2_run_service.py` — `cleanup_orphaned_running_rows` skips live batch rows.
- frontend: `ReportSettingsModal.tsx`, `api/earnings-update.ts`, `hooks/useEuSettings`.

---

## Phase 1 — Settings toggle (`batch_enabled`)

Self-contained, fully testable, ships independently. No behavior change until later phases read the flag.

### Task 1.1: DB column + migration

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/report_eu.py` (class `EuV2Settings`)
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-06-01-1200_eu_v2_settings_batch_enabled.py`

- [ ] **Step 1: Add the column to the model** (after `web_search_enabled`, before `created_at`):

```python
    batch_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
```

- [ ] **Step 2: Get the current migration head**

Run: `uv run alembic -c packages/server/alembic.ini heads` (or inspect `git log` of versions dir). Current head: `2026-06-01-1130_encrypt_connector_secrets` (verify; use its `revision` as `down_revision`).

- [ ] **Step 3: Write the migration**

```python
"""eu_v2_settings.batch_enabled

Revision ID: 2026_06_01_1200_batch_enabled
Revises: <HEAD_REVISION_ID>
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "2026_06_01_1200_batch_enabled"
down_revision = "<HEAD_REVISION_ID>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eu_v2_settings",
        sa.Column("batch_enabled", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("eu_v2_settings", "batch_enabled")
```

- [ ] **Step 4: Apply + verify**

Run: `uv run alembic -c packages/server/alembic.ini upgrade head`
Expected: no error; `eu_v2_settings` has `batch_enabled`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(eu-batch): add batch_enabled column + migration"`

### Task 1.2: Service carries `batch_enabled`

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_settings.py`
- Test: `packages/server/tests/services/test_eu_v2_settings.py` (create if absent)

- [ ] **Step 1: Failing test**

```python
def test_update_and_get_batch_enabled(db_session, user_id):
    from openlia_server.services import eu_v2_settings as svc
    dto = svc.update_settings(
        db_session, user_id=user_id, provider_kind="openai", model="gpt-5.4-2026-03-05",
        template_id="eu_default", language="en", length="normal", reasoning_effort=None,
        enabled_provider_ids=["eodhd"], web_search_enabled=False, instructions_id=None,
        batch_enabled=True,
    )
    assert dto.batch_enabled is True
    assert svc.get_settings(db_session, user_id=user_id).batch_enabled is True

def test_get_defaults_batch_disabled(db_session):
    from openlia_server.services import eu_v2_settings as svc
    assert svc.get_settings(db_session, user_id="nobody").batch_enabled is False
```

- [ ] **Step 2: Run → fails** (`update_settings() got unexpected kwarg 'batch_enabled'`).

- [ ] **Step 3: Implement** — add `batch_enabled: bool` to `EuSettingsDTO`; map it in `_row_to_dto`; default `False` in `get_settings`'s defaults branch; add `batch_enabled: bool = False` param to `update_settings` and set it on insert + update.

- [ ] **Step 4: Run → pass.**

- [ ] **Step 5: Commit** — `git commit -am "feat(eu-batch): settings service carries batch_enabled"`

### Task 1.3: Route I/O

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py` (settings GET/PUT models + handlers)
- Test: `packages/server/tests/routes/...eu_v2 settings test` (extend existing)

- [ ] **Step 1: Failing test** — PUT settings with `batch_enabled: true`, GET returns it.

```python
def test_settings_roundtrip_batch_enabled(client, auth_headers):
    body = {... existing fields ..., "batch_enabled": True}
    r = client.put("/api/earnings-update/settings", json=body, headers=auth_headers)
    assert r.status_code == 200 and r.json()["batch_enabled"] is True
    g = client.get("/api/earnings-update/settings", headers=auth_headers)
    assert g.json()["batch_enabled"] is True
```

- [ ] **Step 2: Run → fails** (field missing / ignored).

- [ ] **Step 3: Implement** — add `batch_enabled: bool = False` to the settings request + response pydantic models; pass through to `update_settings`; include in the GET response mapping.

- [ ] **Step 4: Run → pass.**

- [ ] **Step 5: Commit** — `git commit -am "feat(eu-batch): expose batch_enabled on EU settings API"`

### Task 1.4: Frontend toggle

**Files:**
- Modify: `frontend/src/api/earnings-update.ts` (settings type + payload)
- Modify: `frontend/src/components/earnings-update/ReportSettingsModal.tsx` (toggle UI)
- Test: `frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx`

- [ ] **Step 1: Failing test** — render modal, assert a "Batch mode" toggle exists, toggling it and saving calls the API with `batch_enabled: true`.

- [ ] **Step 2: Run → fails.**

- [ ] **Step 3: Implement** — add `batchEnabled` / `batch_enabled` to the settings type + (de)serialization; add a toggle row mirroring `web_search_enabled`, with helper text: "Generate scheduled reports via the provider Batch API at ~50% cost. Reports arrive within hours, not live." Show a disabled/explanatory state when the selected provider is not OpenAI/Anthropic.

- [ ] **Step 4: Run → pass** (`cd frontend && npm test -- ReportSettingsModal`).

- [ ] **Step 5: Commit** — `git commit -am "feat(eu-batch): batch mode toggle in EU settings UI"`

---

## Phase 2 — Provider batch transport

### Task 2.1: Transport types + `supports_batch`

**Files:**
- Create: `packages/core/src/openlia/llm/batch_transport.py`
- Test: `packages/core/tests/llm/test_batch_transport.py`

- [ ] **Step 1: Failing test** — `supports_batch("openai_responses", any)` and `supports_batch("anthropic", any)` are True; `supports_batch("ollama"/"openrouter"/"gemini", any)` is False.

- [ ] **Step 2: Run → fails.**

- [ ] **Step 3: Implement**

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from openlia.llm.types import LLMRequest, LLMResponse

@dataclass(frozen=True)
class BatchRequestItem:
    custom_id: str
    request: LLMRequest

class BatchStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

@dataclass(frozen=True)
class BatchResultItem:
    custom_id: str
    response: LLMResponse | None
    error: str | None

class BatchTransport(Protocol):
    async def submit_batch(self, items: list[BatchRequestItem]) -> str: ...
    async def poll_batch(self, batch_id: str) -> BatchStatus: ...
    async def fetch_results(self, batch_id: str) -> dict[str, BatchResultItem]: ...
    async def cancel_batch(self, batch_id: str) -> None: ...

_BATCH_PROVIDERS = {"openai_responses", "anthropic"}

def supports_batch(provider_kind: str, model: str) -> bool:
    return provider_kind in _BATCH_PROVIDERS
```

- [ ] **Step 4: Run → pass.** — [ ] **Step 5: Commit.**

### Task 2.2: Refactor OpenAI Responses payload builder (no behavior change)

**Files:** Modify `packages/core/src/openlia/llm/adapters/openai_responses.py`; Test: existing adapter tests must stay green.

- [ ] **Step 1:** Extract the payload dict construction inside `generate()` into a module function `build_responses_payload(model: str, request: LLMRequest) -> dict` (the block building `payload` with input/instructions/max_output_tokens/tools/tool_choice/reasoning). Have `generate()` call it.
- [ ] **Step 2:** Extract response→`LLMResponse` mapping into `parse_responses_body(body: dict) -> LLMResponse` (wraps `_parse_responses_output` + usage). `generate()` calls it.
- [ ] **Step 3: Run existing openai_responses tests → pass** (pure refactor). — [ ] **Step 4: Commit.**

### Task 2.3: OpenAI batch transport

**Files:** Create `openai_batch.py`; Test `test_openai_batch.py` (fake httpx via `respx` or a stub client).

- [ ] **Step 1: Failing test** — `submit_batch([item1,item2])` uploads JSONL (each line `{custom_id, method:"POST", url:"/v1/responses", body: build_responses_payload(model, req)}`), creates a batch (`endpoint:"/v1/responses", completion_window:"24h"`), returns batch id; `poll_batch` maps provider statuses (`validating/in_progress/finalizing`→IN_PROGRESS, `completed`→COMPLETED, `failed/cancelled`→FAILED, `expired`→EXPIRED); `fetch_results` downloads the output file and maps each line's `response.body` via `parse_responses_body`, keyed by custom_id, with per-line error captured into `BatchResultItem.error`.

- [ ] **Step 2: Run → fails.**

- [ ] **Step 3: Implement** `OpenAIBatchTransport` using `make_client`/`_http` helpers + `build_responses_payload`/`parse_responses_body`. Files API: `POST /v1/files` (purpose `batch`), `POST /v1/batches`, `GET /v1/batches/{id}`, `GET /v1/files/{output_file_id}/content`.

- [ ] **Step 4: Run → pass.** — [ ] **Step 5: Commit.**

### Task 2.4: Anthropic payload refactor + batch transport

**Files:** Modify `anthropic.py` (extract `build_messages_payload`/`parse_messages_body`); Create `anthropic_batch.py`; Test `test_anthropic_batch.py`.

- [ ] **Step 1:** Read `anthropic.py`, extract its request-body builder + response parser (mirror Task 2.2).
- [ ] **Step 2: Failing test** — `submit_batch` POSTs `/v1/messages/batches` with `requests:[{custom_id, params: build_messages_payload(...)}]`; `poll_batch` maps `processing_status` (`in_progress`→IN_PROGRESS, `ended`→COMPLETED); `fetch_results` GETs the results URL (JSONL of `{custom_id, result:{type:"succeeded", message}}`), maps via `parse_messages_body`, captures `errored`/`expired`/`canceled` per item.
- [ ] **Step 3: Implement** `AnthropicBatchTransport` (header `anthropic-beta: message-batches-2024-09-24` if required by the SDK version; verify at impl time).
- [ ] **Step 4: Run → pass.** — [ ] **Step 5: Commit.**

### Task 2.5: Transport factory

**Files:** add `build_batch_transport(provider_kind, credentials, model, capabilities) -> BatchTransport | None` (in `batch_transport.py` or `adapters/__init__.py`); returns the right transport or `None` for unsupported providers. Test both providers + None path. Commit.

---

## Phase 3 — Step-wise EU run state

### Task 3.1: Extract `EuRunState` from the runner

**Files:** Create `report_eu/run_state.py`; Modify `report_eu/runner.py`; Test `packages/core/tests/llm/runtime/report_eu/test_run_state.py`.

The current `_run_turn_loop` body becomes two methods. Build state from the same inputs `Runner.run` assembles (catalog, system prompt, tool schemas, messages, deadline, ledger, workspace).

- [ ] **Step 1: Failing test** — drive an `EuRunState` with scripted `LLMResponse`s (a `write_section` turn, then a `finalize` turn) and assert: `pending_request()` returns an `LLMRequest` with the growing message list + system + tool schemas; after `apply_response(finalize_resp)`, `result()` is a completed `RunResult` with the section.

```python
def test_run_state_two_turns_to_finalize(fake_catalog_and_workspace):
    state = EuRunState(...)              # built from request + transports like Runner.run
    req1 = state.pending_request()
    assert req1 is not None and req1.system and req1.tools
    state.apply_response(resp_write_section)   # contains tool_call write_section
    assert state.pending_request() is not None # not yet finalized
    state.apply_response(resp_finalize)        # contains tool_call finalize
    assert state.pending_request() is None
    assert state.result().status == "completed"
```

- [ ] **Step 2: Run → fails.**

- [ ] **Step 3: Implement** `EuRunState`:
  - `__init__(request, *, catalog, system_prompt, tool_schemas, tools_by_name, native_tools, messages, deadline, ledger, workspace, custom_id)`.
  - `pending_request() -> LLMRequest | None`: returns None when finalized/failed/limit/deadline; else builds the `LLMRequest` exactly as `session.generate` does today (system, tools=tool_schemas, native_tools, max_tokens incl. `_REASONING_OVERHEAD`, temperature 0.4, reasoning_effort, `cache_conversation=True`).
  - `apply_response(LLMResponse)`: replicate one iteration of `_run_turn_loop` — ingest web citations, append assistant message, on no tool_calls finalize-or-fail, dispatch each tool via `_dispatch_one` (sync — but EU tools may be async; orchestrator must `await`; see note), append tool messages, append web-citation notice, set terminal flags + `RunResult` via `_finish` when finalized/failed.
  - Async note: `_dispatch_one` is async (connector tools). Make `apply_response` async (`async def apply_response`). The orchestrator awaits it.
  - `result()`, `snapshot() -> dict`, `classmethod restore(dict, *, transports, dispatcher) -> EuRunState`.

- [ ] **Step 4: Run → pass.**

- [ ] **Step 5:** Build `EuRunState.from_request(request, *, transports, dispatcher, custom_id)` factory mirroring `Runner.run`'s setup (build catalog, system prompt, initial user turn). Then rewrite `Runner._run_turn_loop` to: `state = EuRunState.from_request(...)`; loop `while (req := state.pending_request()) is not None: resp = await session.generate(...from req...); await state.apply_response(resp)`; `return state.result()`. Keep all emitter events (move emits into `apply_response` via an injected emitter, or keep them in the runner loop by exposing per-turn deltas). **Run the full existing EU runner test suite → green (parity).**

- [ ] **Step 6: Commit** — `git commit -am "refactor(eu): extract step-wise EuRunState; runner drives it (parity)"`

### Task 3.2: Snapshot/restore round-trip

**Files:** same; Test `test_run_state.py`.

- [ ] **Step 1: Failing test** — run state through one turn, `snap = state.snapshot()`; `restored = EuRunState.restore(snap, transports=..., dispatcher=...)`; `restored.pending_request()` equals the pre-snapshot pending request (same messages); applying the same next response yields the same `result()`.
- [ ] **Step 2-4:** Implement `snapshot` (serialize messages [role/content/tool_calls/tool_call_id], workspace sections/charts, ledger entries, turn index, terminal flags) and `restore` (rebuild catalog/system prompt from `request`, replay persisted messages + workspace + ledger). Run → pass.
- [ ] **Step 5: Commit.**

---

## Phase 4 — Batch orchestrator

### Task 4.1: `BatchOrchestrator`

**Files:** Create `runtime/batch_orchestrator.py`; Test `test_batch_orchestrator.py`.

- [ ] **Step 1: Failing test** — given a fake `BatchTransport` (returns scripted per-custom_id responses per cycle) and 2 `EuRunState`s finishing at turns 1 and 2, the orchestrator: submits a batch each cycle containing only active runs; calls `on_run_complete(custom_id, RunResult)` for each as it finalizes; second batch contains only the slower run; returns when all done. One run raising in `apply_response` calls `on_run_failed(custom_id, msg)` and does not stop the other.

- [ ] **Step 2: Run → fails.**

- [ ] **Step 3: Implement**

```python
class BatchOrchestrator:
    def __init__(self, *, transport, runs: list[EuRunState],
                 poll_interval_s: float, max_wait_s: float,
                 on_turn_persisted, on_run_complete, on_run_failed,
                 sleep=asyncio.sleep, now=time.monotonic): ...
    async def run(self) -> None:
        deadline = self._now() + self._max_wait_s
        active = {r.custom_id: r for r in self._runs}
        while active:
            items = [BatchRequestItem(cid, r.pending_request()) for cid, r in active.items()]
            batch_id = await self._transport.submit_batch(items)
            self._on_turn_persisted(batch_id, active)         # persistence hook
            while True:
                if self._now() > deadline: ... mark all active failed; return
                status = await self._transport.poll_batch(batch_id)
                if status is BatchStatus.COMPLETED: break
                if status in (FAILED, EXPIRED): ... mark all active failed; return
                await self._sleep(self._poll_interval_s)
            results = await self._transport.fetch_results(batch_id)
            for cid, run in list(active.items()):
                res = results.get(cid)
                if res is None or res.error or res.response is None:
                    self._on_run_failed(cid, ...); del active[cid]; continue
                try:
                    await run.apply_response(res.response)
                except Exception as exc:
                    self._on_run_failed(cid, str(exc)); del active[cid]; continue
                if run.pending_request() is None:
                    (self._on_run_complete if run.result().status == "completed"
                     else self._on_run_failed)(cid, run.result()); del active[cid]
            self._on_turn_persisted(batch_id, active)
```

(Inject `sleep`/`now` so tests run instantly.)

- [ ] **Step 4: Run → pass.** — [ ] **Step 5: Commit.**

---

## Phase 5 — Persistence + recovery

### Task 5.1: Batch tables + migration

**Files:** Modify `db/models/report_eu.py`; Create migration `..._eu_v2_batch_tables.py`.

- [ ] Add `EuV2BatchJob` (`id` PK str36, `provider_kind`, `model`, `status`, `provider_batch_id` nullable, `turn_index` int default 0, `created_at`, `updated_at`) and `EuV2BatchRun` (`id` PK str36, `batch_job_id` FK→`eu_v2_batch_job` cascade, `report_id` FK→`report_eu` cascade, `custom_id`, `state_json` Text, `status` default "active", `updated_at`; index on `batch_job_id`). Migration creates both. Apply + verify. Commit.

### Task 5.2: Persistence service

**Files:** Create `services/eu_v2_batch_service.py`; Test `test_eu_v2_batch_service.py`.

- [ ] Functions: `create_batch_job(db, provider_kind, model, runs_with_report_ids) -> job_id` (inserts job + run rows with initial snapshots, status active); `persist_turn(session_factory, job_id, batch_id, active_runs)` (update job.provider_batch_id/turn_index + each active run's `state_json`); `complete_run(session_factory, report_id, run_result)` (reuse `eu_v2_run_service.persist_result` + flip `report_eu` row + flip `eu_v2_batch_run` to completed + emit REPORT_READY notification); `fail_run(session_factory, report_id, msg)`; `finalize_job(session_factory, job_id)`. TDD each with a real sqlite session. Commit.

### Task 5.3: Startup recovery + orphan-skip

**Files:** Modify `eu_v2_run_service.cleanup_orphaned_running_rows`; add `recover_inflight_batches(...)` in batch service; wire both into app startup. Test.

- [ ] `cleanup_orphaned_running_rows`: exclude `report_eu` ids that have an `eu_v2_batch_run` whose job is non-terminal (don't fail legitimately in-flight batch reports). Failing test: a running report tied to a live batch job survives cleanup; a plain running report still flips to failed.
- [ ] `recover_inflight_batches`: for each non-terminal `eu_v2_batch_job`, rebuild `EuRunState`s via `restore`, rebuild transport via `build_batch_transport`, and resume a `BatchOrchestrator` from the persisted `provider_batch_id` (poll current batch first, then continue). Test with fakes. Commit.

---

## Phase 6 — Dispatch integration

### Task 6.1: Partition due rows; spawn orchestrator

**Files:** Modify `services/eu_v2_scheduler_impl.py` (`EuV2DispatcherImpl.dispatch_due`); add helper in `eu_v2_batch_service.py` (`dispatch_batch_group`); Test `test_eu_v2_dispatch_batch.py`.

- [ ] **Step 1: Failing test** — two due rows for user A (`batch_enabled=True`, provider openai_responses) and one for user B (`batch_enabled=False`): `dispatch_due` routes A's rows into a single batch job (one `eu_v2_batch_job`, two `report_eu` rows, two `eu_v2_batch_run` rows) and B's row through the unchanged `start_run_async` path. A user with `batch_enabled=True` but an unsupported provider falls back to sync.
- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Implement** — in `dispatch_due`, for each due row resolve the user's `EuSettingsDTO`; `batch = settings.batch_enabled and supports_batch(settings.provider_kind, settings.model)`. Collect batch rows grouped by `(provider_kind, model)`; for each group call `build_run_request` per row, create `report_eu` rows (status running, trigger scheduled) + `eu_v2_batch_job`/`eu_v2_batch_run`, build `EuRunState.from_request` per row, `mark_reported` each schedule row, and spawn `BatchOrchestrator.run()` as a tracked background task (strong-ref set like `start_run_async`). Sync rows: unchanged loop body.
- [ ] **Step 4: Run → pass.** — [ ] **Step 5: Commit.**

### Task 6.2: End-to-end integration

**Files:** Test `test_eu_batch_e2e.py`.

- [ ] Scheduled dispatch with `batch_enabled` + a fake `BatchTransport` + a fake `LLMSession` adapter: assert both report rows reach `completed`, sections persisted, `REPORT_READY` notifications emitted, `eu_v2_batch_job` row `completed`. Commit.

---

## Phase 7 — Verification

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run pytest packages/core/ packages/server/` → all green (note pre-existing skips).
- [ ] `cd frontend && npm test` → green.
- [ ] Manual: enable batch in EU settings, seed a due `eu_v2_earnings_schedule` row, run the dispatch executor, confirm report completes via batch and a notification fires. (Document in PR.)

---

## Implementation divergences from this plan (recorded per CLAUDE.md #9)

1. **Phase 3 — `EuRunState` is a parallel step-wise driver, NOT a rewrite of
   the live `Runner`.** The plan called for rewriting `Runner._run_turn_loop`
   to drive `EuRunState` (with a parity test). Instead `EuRunState` reuses the
   runner's free functions (`_initial_user_turn`, `_connector_prompt_info`,
   `_dispatch_one`, `_finish`) and the live `Runner` is left untouched. Lower
   risk (the proven sync path can't regress); the small duplication is the
   per-turn orchestration sequence only. The dispatcher context is applied
   per-turn around tool dispatch inside `EuRunState.apply_response` (the live
   runner wraps the whole loop — equivalent, since only tool execution needs
   the connector credentials).
2. **Restart resume — IMPLEMENTED (2026-06-02).** `EuRunState.snapshot()`/
   `restore()` serialize/rebuild a run; `eu_v2_batch_run.state_json` stores the
   per-turn checkpoint. The orchestrator persists ONE checkpoint per cycle
   right after submit (pre-apply state + `provider_batch_id`) and gained a
   `run(resume_batch_id=...)` entry that re-attaches to that batch, applies it,
   and continues — idempotent because the checkpoint is always pre-apply
   (sections overwrite, ledger rebuilt). `recover_inflight_batches` runs at
   startup (in `app.py`, replacing the orphan sweep): it restores run states
   and resumes each non-terminal job; un-resumable jobs (no batch id / no
   snapshot / no transport / no EODHD) are failed via `_fail_job_in_session`.
   `cleanup_orphaned_running_rows` now skips reports tied to a resumable batch
   so it doesn't race recovery. `mark_orphaned_batch_jobs_failed` is retained
   as a fallback. Tested: snapshot/restore round-trip, orchestrator resume,
   `recover_inflight_batches` end-to-end, the cleanup orphan-skip.
3. **No new `REPORT_READY` notification** for batch completions — matches the
   existing sync scheduled path, which also persists silently (the report
   appears in the user's list on completion). Add if/when the sync path does.

## Self-Review notes

- Spec coverage: provider transport (P2), orchestrator (P4), run-state extraction (P3), persistence+resume (P5), dispatch partition + notification (P6), settings toggle (P1), fallback-to-sync (Task 6.1), orphan-skip (Task 5.3). Cost-characteristics are documented in the spec; no task needed.
- Async correctness: EU tools include async connector tools → `EuRunState.apply_response` is async; orchestrator + runner await it.
- Single-model batches: grouping by `(provider_kind, model)` enforces it (a provider batch is one endpoint/model).
- Out of scope (tracked in spec): ER scheduling + ER batch (Feature 1), Gemini/OpenRouter batch, on-demand batch, cost dashboard, extended-cache tuning.
