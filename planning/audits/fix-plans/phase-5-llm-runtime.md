# Phase 5 — LLM Runtime fix plan (→ 100%)


**Current:** ~88% shipped. **Root cause:** IMPLEMENTER.

**Gap summary:** Runtime scaffolding, events, tool dispatcher, chat/report/batch runners, and the prompt loader all landed, but three spec-mandated behaviors are not wired: `await_with_grace` never used in runners (polling-only cancellation), no startup slot validation, and two prompt YAMLs need a slot-contents verification pass.

**Tasks (in execution order):**

1. **P1-12 — Apply `await_with_grace` inside ChatRunner and ReportRunner.**
   - Files: `packages/core/src/openlia/llm/runtime/chat.py:73-180`; `runtime/report.py:117-230`; `runtime/batch.py` (per-item wrap).
   - Plan ref: Task 4 (`cancellation.py`) + Tasks 9/10/11.
   - Spec ref: `llm-runtime-design.md` §Cancellation — "2-second grace for in-flight tool calls".
   - Acceptance: new test `test_cancel_streaming_grace.py` asserts that a cancelled stream-in-flight returns within grace_seconds+epsilon, and tool-call results already produced inside the grace window are yielded before the `cancelled` event.

2. **P1-13 — Audit prompt YAML slot contents for MR + MB.**
   - Files: `packages/core/src/openlia/prompts/morning_briefing.yaml`, `macro_research.yaml`; `prompts/secretary.yaml` (remove dead top-level `system`/`user` keys — P2-10).
   - Plan ref: Task 6.
   - Spec ref: `llm-runtime-design.md` §Prompt Authoring.
   - Acceptance: `test_prompt_contents.py` exercises `PromptLoader.validate_department_slots` for `morning_briefing` (`briefing.system`, `briefing.user`) and `macro_research` (`assessment.system`, `assessment.user`, `framework_four_seasons`, `framework_all_weather`).

3. **P1-14 — Wire `PromptLoader.validate_department_slots` into FastAPI lifespan.**
   - Files: `packages/server/src/openlia_server/app.py:201-306` (add a single call in `_make_lifespan` before `yield`).
   - Plan ref: Tasks 5 + 12.
   - Spec ref: `llm-runtime-design.md` §Loader Contract — "validation runs at startup so typos fail fast".
   - Acceptance: booting with a deliberately renamed slot raises `PromptSlotNotFound` before `yield`; test `test_startup_validates_prompt_slots`.

4. **P2-10 — Remove orphan top-level `system`/`user` keys in `secretary.yaml`.**
   - Files: `packages/core/src/openlia/prompts/secretary.yaml`.
   - Acceptance: `yq '.system, .user' secretary.yaml` returns null; existing `chat:` block untouched.

5. **NEW-5-01 — Add missing focused unit tests for events + messages shapes.**
   - Files: `packages/core/tests/test_llm/test_runtime/test_events.py` (new), `test_messages.py` (new).
   - Spec ref: `llm-runtime-design.md` §Event Taxonomy + §SSE Protocol.
   - Acceptance: assertions for every documented event type and every `ChatMessage`/`ReportRequest`/`BatchItem` round-trip.

**Verification:** `uv run pytest packages/core/tests/test_llm/test_runtime packages/server/tests/test_app_lifespan.py` green; `grep -R "await_with_grace" packages/core/src/openlia/llm/runtime/` returns hits in chat.py, report.py, batch.py.
