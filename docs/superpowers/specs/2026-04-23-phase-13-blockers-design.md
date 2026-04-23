# Phase 13 Blockers Design

Date: 2026-04-23  
Branch: fix/phase-13-blockers  
Resolves: REM-P1-010, REM-P1-011, REM-P1-012, REM-P1-013, REM-P1-015

## Scope

Five open items from the remediation checklist block Phase 13-15 implementation.
REM-P1-015 is already satisfied by existing code and tests (see §5). The other
four require new tests and/or new production code.

---

## 1. REM-P1-010 — Runtime provider/model hardening tests

### What already exists

`SQLModelRegistry` correctly filters `is_enabled` on both model and provider in
`get_tier_default`, `get_any_in_tier`, and `_load_row`. `test_llm_registry.py`
has one disabled-model test (`test_get_any_in_tier_skips_disabled`) but no
disabled-provider tests.

### What to add

Add to `packages/server/tests/test_services/test_llm_registry.py`:

1. `test_get_tier_default_skips_disabled_provider` — seed a model with
   `is_tier_default=True` but disable its provider; assert `get_tier_default`
   returns `None`.
2. `test_get_any_in_tier_skips_disabled_provider` — seed two models in the same
   tier; disable the first model's provider; assert `get_any_in_tier` returns
   the second.
3. `test_user_preference_with_disabled_provider_falls_back` — set a user pref
   on a model whose provider is disabled; assert `get_user_preference` returns
   `None` (falls back in `resolve()`).
4. `test_resolve_raises_tier_not_configured_when_all_disabled` — disable all
   models in a tier; assert `resolve()` raises `TierNotConfiguredError`.

No production code changes — the queries already guard this correctly.

---

## 2. REM-P1-011 — Multi-round tool loop tests

### What already exists

`test_chat.py` and `test_report.py` each have one single-round tool-call test.
`FakeProviderScript` supports chained turns naturally via `_turn_index`.

### What to add

**`packages/core/tests/test_llm/test_runtime/test_chat.py` — 3 new tests:**

1. `test_two_round_tool_loop_appends_both_results` — script: `tool_calls([A])`,
   `tool_calls([B])`, `final("")`, `tokens(["ok"])`. Assert `ChatToolCallStart`
   appears twice with `call_id` A and B, and `ChatDone` is the last event.
2. `test_max_rounds_falls_through_to_final_text` — script: 10× `tool_calls([X])`
   then `tokens(["done"])`. Assert `ChatDone` is the last event (loop exits after
   10 rounds and goes to the stream turn). This protects the runaway guard.
3. `test_provider_error_in_tool_loop_emits_chat_error` — script: `tool_calls([A])`,
   then `generate` raises `LLMProviderError`. Assert last event is `ChatError`.
   (Covers the mid-loop error path, not covered by existing tests.)

**`packages/core/tests/test_llm/test_runtime/test_report.py` — 3 new tests:**

1. `test_two_round_tool_loop_uses_both_results` — same pattern for `ReportRunner`;
   both tool calls appear as `ReportToolCall` events before `ReportComplete`.
2. `test_max_rounds_falls_through_to_writing` — 10× `tool_calls` then
   `final_json`. Assert `ReportComplete` is the last event.
3. `test_provider_error_in_report_tool_loop_emits_report_error` — mid-loop error
   becomes `ReportError`.

---

## 3. REM-P1-012 — Wire production scheduler dependencies

### Problem

`app.py` lifespan passes `report_runner=None, batch_runner=None` to
`build_scheduler_service`. If the scheduler is enabled and an EU/MB job fires,
the executor calls `None.run(...)` and crashes.

### Solution

**New function in `packages/server/src/openlia_server/services/runtime.py`:**

```python
class RefreshingReportRunner:
    """Wraps ReportRunner construction so the scheduler gets a fresh DB
    session and registry for each job run."""

    def __init__(self, db_session_factory):
        self._factory = db_session_factory

    async def run(self, *, department_id, user_id, request, cancel_token=None):
        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            runner = _build_report_runner_with_registry(registry)
            async for event in runner.run(
                department_id=department_id,
                user_id=user_id,
                request=request,
                cancel_token=cancel_token,
            ):
                yield event
        finally:
            db.close()


def build_report_runner(db_session_factory) -> RefreshingReportRunner:
    return RefreshingReportRunner(db_session_factory)
```

`_build_report_runner_with_registry` is a private helper that constructs a
`ReportRunner` with a given registry (same provider factory pattern as
`build_chat_runner`). `BatchRunner` is passed as `None` still — no batch
department ships in Plan 13.

**`app.py` lifespan change:**

```python
from openlia_server.services.runtime import build_report_runner
# ...
scheduler_svc = build_scheduler_service(
    session_factory=_sm,
    settings=scheduler_settings,
    scheduler=adapter,
    report_runner=build_report_runner(_sm),   # was: None
    batch_runner=None,
)
```

**New test in `packages/server/tests/test_scheduler/test_wiring.py`:**

`test_build_scheduler_service_with_real_report_runner` — pass a
`RefreshingReportRunner` instead of a `FakeReportRunner`; assert all four
executor job types are registered (proves wiring accepts the real runner type
without error).

---

## 4. REM-P1-013 — EU schedule CRUD routes with hot-reload

### Rationale for implementing now

`EuSchedule` model exists, the hot-reload API (`add_schedule`, `modify_schedule`,
`remove_schedule`) is complete. Implementing a thin CRUD route factory now:
- satisfies the acceptance criteria with real passing tests
- prevents Plan 15 from accidentally building a parallel schedule surface
- is ~60 lines of route code with no new dependencies

### New file: `packages/server/src/openlia_server/routes/eu_schedules.py`

Route factory `build_eu_schedules_router(*, db_session_factory, mode)` with:

| Method | Path | Action |
|--------|------|--------|
| POST | `/departments/earnings-update/schedules` | Create `EuSchedule`, call `scheduler.add_schedule` |
| PATCH | `/departments/earnings-update/schedules/{id}` | Update `EuSchedule`, call `scheduler.modify_schedule` |
| DELETE | `/departments/earnings-update/schedules/{id}` | Delete `EuSchedule` row, call `scheduler.remove_schedule` |
| GET | `/departments/earnings-update/schedules` | List user's schedules (no scheduler call) |

All write endpoints call `_require_scheduler(request)` (same pattern as
notifications) and return `503` if scheduler is disabled. All endpoints are
authenticated via `build_require_active_user`.

DTOs: `EuScheduleIn` (time, timezone, days_of_week, label, is_enabled),
`EuScheduleOut` (id + all fields + created_at). Delete returns `{"deleted": id}`.

Router is mounted in `create_app()` alongside the other department-prefixed routes.

**Test file: `packages/server/tests/test_routes/test_eu_schedules.py`**

Tests use `FakeAPScheduler` injected via `app.state.scheduler`. Covers:
1. POST creates DB row and calls `fake_scheduler.add_schedule`
2. PATCH updates DB row and calls remove + re-add (via `modify_schedule`)
3. DELETE removes DB row and calls `fake_scheduler.remove_schedule`
4. GET returns user's schedules
5. POST with scheduler disabled returns 503

---

## 5. REM-P1-015 — Notification transaction ownership (already complete)

`notifications.py` line 73-75 documents commit ownership explicitly. The
existing `test_mark_read_flips_all_department_notifications` opens a fresh
session after the route call and asserts DB state — this satisfies "tests cover
mark-read persistence." No code or test changes needed; mark complete in
checklist.

---

## File change summary

| File | Change |
|------|--------|
| `packages/server/tests/test_services/test_llm_registry.py` | +4 tests |
| `packages/core/tests/test_llm/test_runtime/test_chat.py` | +3 tests |
| `packages/core/tests/test_llm/test_runtime/test_report.py` | +3 tests |
| `packages/server/src/openlia_server/services/runtime.py` | +`RefreshingReportRunner`, `build_report_runner` |
| `packages/server/src/openlia_server/app.py` | pass `build_report_runner` instead of `None`; mount EU schedules router |
| `packages/server/tests/test_scheduler/test_wiring.py` | +1 test |
| `packages/server/src/openlia_server/routes/eu_schedules.py` | new file |
| `packages/server/tests/test_routes/test_eu_schedules.py` | new file, 5 tests |
| `planning/audits/2026-04-21-remediation-checklist.md` | update status fields |

Total: ~180 lines new production code, ~200 lines new tests.
