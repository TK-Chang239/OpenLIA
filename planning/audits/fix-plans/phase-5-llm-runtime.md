# Phase 5 — LLM Runtime fix plan (→ 100%)

**Current:** ~82% shipped (revised down from prior 88% after deep audit).
**Root cause:** IMPLEMENTER, with two small PLAN drifts.

**Audit date:** 2026-04-24
**Files verified against code:**
- `packages/core/src/openlia/llm/runtime/{chat.py, report.py, batch.py, cancellation.py, events.py, messages.py, prompts.py, tools.py, web_search.py, __init__.py}`
- `packages/core/src/openlia/prompts/{secretary.yaml, equity_research.yaml, earnings_update.yaml, morning_briefing.yaml, macro_research.yaml, retail_sentiment.yaml, shared/}`
- `packages/server/src/openlia_server/services/{runtime.py, rs_sync_classifier.py, equity_research_runner.py}`
- `packages/server/src/openlia_server/routes/{chat_stream.py, departments/earnings_update.py, departments/morning_briefing.py, departments/equity_research.py}`
- `packages/server/src/openlia_server/app.py`
- `packages/core/tests/test_llm/test_runtime/*`, `packages/server/tests/test_services/test_rs_sync_classifier.py`
- `frontend/src/components/chat/useChatStream.ts`

**Gap summary:** Core runtime dataclasses, events, prompt loader, tool
dispatcher, web-search resolver, and the three runners all landed with
adequate unit coverage. Three classes of gaps remain: (1) **cancellation
is polling-only** — `await_with_grace` is exported but never called, so
the 2-second spec grace for in-flight tool calls is not honored, and the
SSE routes cannot propagate client-disconnect into the runner (no
`request.is_disconnected()` polling task on the chat route); (2) **startup
slot validation is never wired** into the FastAPI lifespan, so prompt
typos fail at first user call; (3) **multiple event-schema drifts** —
`ChatReportThumbnail` ships `filename` instead of spec's `mode`,
`ReportToolCall` omits a `call_id`, `report.complete.schema` is raw dict
instead of the spec's `ReportSchema`, and no timestamp is attached to
any event (frontend cannot order by-wall-clock). Plus a handful of
smaller items: `secretary.yaml` has dead top-level keys, the tool-loop
cap of 10 is hard-coded (spec requires `max_expansions_per_report`
budgeting on `find_more_data`), `ChatRunner` never surfaces
`chat.report_thumbnail` (no code path emits it), and server-side wiring
only provides a `RefreshingReportRunner` wrapper and a
`RefreshingSyncLlmClassifier` — no analogous `RefreshingChatRunner` or
`RefreshingBatchRunner`, so a single boot-time DB session gets reused
across every chat turn, breaking long-running processes if session state
rots.

---

## Tasks (in execution order)

### P1 — correctness gaps (runtime behavior diverges from spec)

1. **P1-12 — Apply `await_with_grace` inside ChatRunner, ReportRunner, BatchRunner.**
   - Files:
     - `packages/core/src/openlia/llm/runtime/chat.py` — wrap `provider.generate()` (line 109) and each `stream()` chunk-await (line 158) with `await_with_grace(..., token=cancel_token)`; wrap `tools.dispatch_many()` (line 135) so in-flight tool calls get the 2s grace.
     - `packages/core/src/openlia/llm/runtime/report.py` — same wrapping on `provider.generate()` (lines 170, 206) and `tools.dispatch_many()` (line 187).
     - `packages/core/src/openlia/llm/runtime/batch.py` — wrap per-item `provider.generate()` (line 76) so a cancelled batch releases semaphore slots within grace.
   - Behaviour: a `None` token short-circuits to direct `await` (no grace path); wrapping only engages when a token is passed.
   - Plan ref: Task 4 (`cancellation.py`) + Tasks 9/10/11.
   - Spec ref: `llm-runtime-design.md` §Cancellation — "in-flight tool calls get a 2-second grace period, then are abandoned".
   - Acceptance: new `packages/core/tests/test_llm/test_runtime/test_cancel_streaming_grace.py` asserts:
     - Token flipped mid-stream stops yielding within `grace_seconds + 0.5s`.
     - Tool-call results completing inside the grace window are yielded before the iterator terminates.
     - A slow tool still running at end-of-grace raises `asyncio.CancelledError` inside the runner, which the async generator swallows (the iterator just stops — no terminal SSE event, per spec).

2. **P1-12b — Propagate client-disconnect into `cancel_token` in SSE routes.**
   - Files:
     - `packages/server/src/openlia_server/routes/chat_stream.py:144-216` — `_event_source()` currently never polls `request.is_disconnected()`; the `asyncio.CancelledError` branch only triggers on Starlette-level disconnect which is **not raised during normal disconnect of a streaming response**. Add an `asyncio.create_task(_watch_disconnect(request, token))` that polls `request.is_disconnected()` every 250 ms and calls `token.cancel()` on True.
     - `packages/server/src/openlia_server/routes/departments/earnings_update.py:219` + `morning_briefing.py:227` — already call `is_disconnected()`, verify they flip the runner's token (audit on read showed the call exists but does not reach the runner's `cancel_token` through the `RefreshingReportRunner` wrapper — fix so it does).
   - Plan ref: Task 4.
   - Spec ref: `llm-runtime-design.md` §Cancellation step 2: "Server route polls `request.is_disconnected()` between yields and flips the runner's `CancellationToken`."
   - Acceptance: `packages/server/tests/test_routes/test_chat_stream_cancel.py` (new) starts a stream, aborts the client, asserts the runner yields no further events within 2.5s and no `chat.done`/`chat.error` is persisted.

3. **P1-13 — Verify prompt YAML slot contents for MR + MB + RS.**
   - Files:
     - `packages/core/src/openlia/prompts/macro_research.yaml` — **ships with `batch.t4_assessment.*` and `batch.t5_assessment.*`**, but `test_prompt_contents.py` and the MR executor currently reference `batch.t4.system` / `batch.t5.system` in other places; reconcile naming.
     - `packages/core/src/openlia/prompts/morning_briefing.yaml` — **file ships and has `report.system` + `report.morning_briefing.user`**; confirm the MB request builder's slot key aligns.
     - `packages/core/src/openlia/prompts/retail_sentiment.yaml` — `batch.classify_sentiment.{system,user}` verified.
   - The master-tracker claim "macro_research.yaml and morning_briefing.yaml not in packages/core/src/openlia/prompts/" is **out of date** — both files exist. The real gap is slot-name drift, not missing files.
   - Plan ref: Task 6.
   - Spec ref: `llm-runtime-design.md` §Prompt Authoring.
   - Acceptance: `test_prompt_contents.py` (update) exercises `PromptLoader.validate_department_slots` for:
     - `morning_briefing`: `["report.system", "report.morning_briefing.user"]`
     - `macro_research`: `["batch.t4_assessment.system", "batch.t4_assessment.user", "batch.t5_assessment.system", "batch.t5_assessment.user"]`
     - `retail_sentiment`: `["batch.classify_sentiment.system", "batch.classify_sentiment.user"]`
     - `equity_research`: `["chat.system", "report.system", "report.stock_initiation.user", "report.stock_update.user", "report.sector_research.user"]`
     - `earnings_update`: `["report.system", "report.earnings_update.user"]`
     - `secretary`: `["chat.system", "chat.welcome"]` (see P2-10 below for the orphan top-level keys).

4. **P1-14 — Wire `PromptLoader.validate_department_slots` into FastAPI lifespan.**
   - Files: `packages/server/src/openlia_server/app.py:201-306` — inside `_make_lifespan`, before `yield`, build a single `PromptLoader()` and call `validate_department_slots` once per configured department with the slot list from P1-13 above. Failure raises `PromptSlotNotFound` and prevents the server from starting.
   - Plan ref: Task 5 + Task 12.
   - Spec ref: `llm-runtime-design.md` §Loader Contract — "validation runs at startup so typos fail fast".
   - Acceptance: new `packages/server/tests/test_app_lifespan_prompt_slots.py` — boots with a deliberately renamed slot in a tmp prompts dir, asserts `PromptSlotNotFound` before `yield`; control case boots cleanly with the real prompts.

5. **NEW-5-01 — Fix `ChatReportThumbnail` event shape drift.**
   - Files:
     - `packages/core/src/openlia/llm/runtime/events.py:53-58` — currently `{message_id, report_id, filename}`. Spec §Event Taxonomy says `{message_id, report_id, mode}`. Frontend (`frontend/src/components/chat/useChatStream.ts:28`) consumes `filename`. Two options:
       - (a) Update spec to match shipped reality (add `mode` as optional).
       - (b) Add `mode` and keep `filename` as a convenience field.
     - Decision: option (b) — add `mode: str` as first-class, leave `filename` for UI backwards-compat, add deprecation note.
   - Plan ref: Task 3.
   - Acceptance: `test_events.py::test_chat_report_thumbnail_links_report_id` updated to assert both fields; frontend unit test remains green because `filename` is still present.

6. **NEW-5-02 — Add `call_id` to `ReportToolCall`.**
   - Files: `packages/core/src/openlia/llm/runtime/events.py:96-101` — add `call_id: str` so report streams can correlate a tool-call start (to be added) with its summary. Currently the runner (`report.py:191-195`) discards `r.call_id`.
   - Rationale: the chat side carries `call_id` on both start and result; the report side silently drops it. Frontend narration cannot deduplicate or match up retries without it.
   - Acceptance: `test_events.py::test_report_tool_call_carries_call_id` (new) — assert wire shape; `test_report.py` updated to assert `call_id` passes through.

7. **NEW-5-03 — Emit `report.tool_call.start` event (optional — marked P2 if too invasive).**
   - Files: `packages/core/src/openlia/llm/runtime/{events.py, report.py}`.
   - Currently report stream only emits a single `report.tool_call` after dispatch — users see nothing while a tool is executing. Spec §Event Taxonomy mentions `report.tool_call` only, so this is strictly a UX enhancement; mark **P2-NEW-5-03** if schedule-tight.

8. **NEW-5-04 — `find_more_data` budget not enforced.**
   - Files: `packages/core/src/openlia/llm/runtime/tools.py:243-274` and `report.py:166`, `chat.py:105`.
   - Both runners hard-cap the tool loop at `range(10)`. The spec §Tool Schema Construction / `find_more_data` says "Bounded by `max_expansions_per_report`; Secretary is unlimited". Today:
     - Chat (Secretary) is bounded to 10 despite spec saying "unlimited".
     - Reports share the same 10-cap for all tool calls combined, not specifically for expansions.
   - Fix: pass `max_expansions` through from the department-requirement manifest (Plan 3 territory) into `ToolDispatcher.build`/`_dispatch_find_more_data`; count only `find_more_data` hits against the budget; leave the 10-iteration runaway guard as a hard outer bound (rename to `MAX_TOOL_TURNS`).
   - Acceptance: `test_tools.py::test_find_more_data_budget` — on budget exhaustion returns `ok=False, summary="expansion budget exhausted"` without calling the catalog.

9. **NEW-5-05 — Add `RefreshingChatRunner` / lifecycle parity.**
   - Files:
     - `packages/server/src/openlia_server/services/runtime.py:43-70` — `build_chat_runner()` builds **one** `ChatRunner` with **one** `SQLModelRegistry` at call time — but because `chat_runner_factory` is a lambda, it only runs once on app start in practice (the factory captures the pre-built runner for the lifetime of the app).
     - Check `app.py:444`: `app.state.chat_runner_factory = lambda: build_chat_runner(db_session_factory=factory)`. Each call to `factory()` **does** build a fresh runner, good — but the runner itself uses a single DB session (leaked on every request). Compare to the `RefreshingReportRunner` pattern (`runtime.py:97-123`) which closes the session in `finally`.
   - Fix: mirror `RefreshingReportRunner` — add `RefreshingChatRunner` that opens/closes a DB session per `.run()`, reassign `build_chat_runner` to return it.
   - Acceptance: `test_services/test_refreshing_chat_runner.py` — asserts a fresh session is opened per run and closed on iterator exhaustion / exception / client-disconnect.

10. **NEW-5-06 — `BatchRunner` has no refreshing wrapper nor server-side wiring.**
    - Files: `packages/server/src/openlia_server/services/runtime.py` — no `build_batch_runner` exists. `FakeBatchRunner` in scheduler tests papers over the gap, but the MR executor depends on a real `BatchRunner` via dependency injection (see P0-04 in master tracker). That P0 lives in Phase 19, not here, but **wiring a `RefreshingBatchRunner` belongs to Phase 5 hygiene**.
    - Acceptance: `build_batch_runner(db_session_factory)` returns a `RefreshingBatchRunner` that spins up a fresh `ChatRunner`-style registry per call.

### P2 — polish / plan-spec drift

11. **P2-10 — Remove orphan top-level `system`/`user` keys in `secretary.yaml`.**
    - Files: `packages/core/src/openlia/prompts/secretary.yaml:1-27` — top-level `system:` and `user:` keys are dead (loader only follows `chat.*`). Remove.
    - Spec ref: `llm-runtime-design.md` §Prompt Authoring — only nested dept.mode.role slots are valid.
    - Acceptance: `yq '.system, .user' secretary.yaml` returns null; `chat:` block untouched; existing tests remain green.

12. **P2-NEW-5-07 — Add timestamp (ISO-8601 UTC) to every event.**
    - Files: `packages/core/src/openlia/llm/runtime/events.py`.
    - Currently no `ts` field. Spec §SSE Protocol doesn't explicitly require it, but the DB persistence layer and frontend chat bubble use `message.created_at` — having server-side timestamps on the wire avoids clock-skew bugs and makes replay testing deterministic.
    - Decision: add `ts: str` on `ChatDone`, `ReportComplete`, `ChatError`, `ReportError` only (terminal events) — leaves non-terminal events unchanged so existing tests need no rework.
    - Acceptance: `test_events.py::test_done_includes_ts` — asserts ISO-8601 Z format.

13. **P2-NEW-5-08 — `ReportComplete.schema` typing.**
    - Files: `packages/core/src/openlia/llm/runtime/events.py:107` — `schema: dict[str, Any]`. Plan 13 defines `ReportSchema`. Import the TypedDict / Pydantic model (once Plan 13 ships) and narrow the type.
    - Acceptance: mypy-clean; no runtime change.

14. **P2-NEW-5-09 — Tool-call `args_preview` truncation edge case.**
    - Files: `packages/core/src/openlia/llm/runtime/chat.py:133` — `json.dumps(call.arguments, separators=(",", ":"))[:120]` can cut mid-UTF-8 codepoint, corrupting the preview. Use `textwrap.shorten` or slice by decoded codepoints.
    - Acceptance: `test_chat.py::test_args_preview_unicode_safe` — ensure a preview containing multi-byte characters truncates at a boundary.

15. **P2-NEW-5-10 — Token / cost accounting missing.**
    - Files: runtime has no event type for `LLMResponse.usage` (prompt_tokens, completion_tokens). The provider layer (Phase 4) exposes it on the response; runtime discards it. Plan 11's Settings page and Plan 22's Repository both want per-run cost stats.
    - Decision: out-of-scope for Phase 5 unless a downstream plan pulls it in; track as `P2-NEW-5-10` and defer to whichever plan first consumes the data.

### Tests (to add alongside fixes)

| ID | File | Verifies |
|----|------|----------|
| T5-01 | `packages/core/tests/test_llm/test_runtime/test_cancel_streaming_grace.py` | P1-12 — grace window for in-flight tool calls |
| T5-02 | `packages/server/tests/test_routes/test_chat_stream_cancel.py` | P1-12b — route-level disconnect propagation |
| T5-03 | `packages/server/tests/test_app_lifespan_prompt_slots.py` | P1-14 — startup slot validation |
| T5-04 | `packages/core/tests/test_llm/test_runtime/test_prompt_contents.py` (update) | P1-13 — all 6 department slot-maps |
| T5-05 | `packages/core/tests/test_llm/test_runtime/test_events.py` (update) | NEW-5-01, NEW-5-02, P2-NEW-5-07 |
| T5-06 | `packages/core/tests/test_llm/test_runtime/test_tools.py` (update) | NEW-5-04 — `find_more_data` budget |
| T5-07 | `packages/server/tests/test_services/test_refreshing_chat_runner.py` | NEW-5-05 — session lifecycle parity |
| T5-08 | `packages/server/tests/test_services/test_refreshing_batch_runner.py` | NEW-5-06 — batch runner wiring |
| T5-09 | `packages/core/tests/test_llm/test_runtime/test_report.py` (update) | NEW-5-02 — `call_id` on report tool-call |
| T5-10 | `packages/core/tests/test_llm/test_runtime/test_chat.py` (update) | P2-NEW-5-09 — unicode-safe preview |

---

## Verification checklist

Runs from repo root:

```bash
# Core runtime tests
uv run pytest packages/core/tests/test_llm/test_runtime/ -v

# Server startup / cancellation tests
uv run pytest packages/server/tests/test_app_lifespan.py \
              packages/server/tests/test_app_lifespan_prompt_slots.py \
              packages/server/tests/test_routes/test_chat_stream_cancel.py \
              packages/server/tests/test_services/test_refreshing_chat_runner.py \
              packages/server/tests/test_services/test_refreshing_batch_runner.py -v

# Static checks
uv run ruff check packages/core/src/openlia/llm/runtime/ \
                  packages/core/src/openlia/prompts/ \
                  packages/server/src/openlia_server/services/runtime.py
grep -n "await_with_grace" packages/core/src/openlia/llm/runtime/{chat,report,batch}.py
# Expect: hits in all three files.
grep -n "is_disconnected" packages/server/src/openlia_server/routes/chat_stream.py
# Expect: at least one hit inside a watcher task.
grep -n "validate_department_slots" packages/server/src/openlia_server/app.py
# Expect: at least one call inside _make_lifespan.
```

---

## Ownership map (to master tracker)

| Master-tracker ID | This plan | Blocking? |
|-------------------|-----------|-----------|
| P1-12 | Task 1 | Runtime correctness — cancellation leaks tool calls |
| P1-13 | Task 3 | Prompt slot naming; both MR + MB files already exist |
| P1-14 | Task 4 | Startup hardening |
| P2-10 | Task 11 | Hygiene |
| (new) NEW-5-01 … NEW-5-06 | Tasks 2, 5–10 | Filed fresh — not in master tracker |
| (new) P2-NEW-5-07 … P2-NEW-5-10 | Tasks 12–15 | Polish |

Hand any cross-phase items (P0-04 BatchRunner injection into MR
executor; P1-04 MB prompt/builder JSON-blob) back to their owning phase
fix-plans — Phase 5 fixes only make those resolutions possible, it does
not do them.
