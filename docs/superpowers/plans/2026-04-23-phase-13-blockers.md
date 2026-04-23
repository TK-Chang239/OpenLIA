# Phase 13 Pre-Implementation Blockers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the five open items that gate Phase 13-15 implementation: harden LLM registry tests (REM-P1-010), protect multi-round tool loop behavior (REM-P1-011), wire a real ReportRunner into the production scheduler (REM-P1-012), implement EU schedule CRUD routes with hot-reload (REM-P1-013), and mark the already-satisfied notification transaction test (REM-P1-015).

**Architecture:** Tasks 1-3 are test-only additions to existing files; production code already handles all cases correctly. Task 4 adds a `RefreshingReportRunner` class to `services/runtime.py` and wires it in `app.py`. Task 5 creates a new `routes/eu_schedules.py` router mounted at `/departments/earnings-update/schedules`. Task 6 updates the remediation checklist.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, pytest, APScheduler 4.x (faked in tests).

---

## File Map

| File | Action |
|------|--------|
| `packages/server/tests/test_services/test_llm_registry.py` | Append 4 tests |
| `packages/core/tests/test_llm/test_runtime/test_chat.py` | Append 3 tests |
| `packages/core/tests/test_llm/test_runtime/test_report.py` | Append 3 tests |
| `packages/server/src/openlia_server/services/runtime.py` | Append `_build_report_runner_with_registry`, `RefreshingReportRunner`, `build_report_runner` |
| `packages/server/tests/test_scheduler/test_wiring.py` | Append 1 test |
| `packages/server/src/openlia_server/app.py` | Wire `build_report_runner`; mount EU schedules router |
| `packages/server/src/openlia_server/routes/eu_schedules.py` | Create new file |
| `packages/server/tests/test_scheduler/test_eu_schedules.py` | Create new file with 5 tests |
| `planning/audits/2026-04-21-remediation-checklist.md` | Update status fields |

---

## Task 1: REM-P1-010 — Registry disabled-provider hardening tests

**Files:**
- Append: `packages/server/tests/test_services/test_llm_registry.py`

The `SQLModelRegistry` already filters `is_enabled` on both model and provider in `get_tier_default`, `get_any_in_tier`, and `_load_row`. The existing tests only cover disabled *models*. These four tests cover disabled *providers*.

- [ ] **Step 1: Write the four failing tests**

Append to `packages/server/tests/test_services/test_llm_registry.py`:

```python
def test_get_tier_default_skips_disabled_provider(_env_secret, db_session) -> None:
    p = svc.create_provider(
        db_session, kind="openai", label="main", api_key="sk-test",
        base_url=None, env_var_name=None, extra_config=None,
    )
    svc.create_model(
        db_session, provider_id=p.id, tier="thinking",
        model_ref="gpt-5.4-pro", display_name="Pro", is_tier_default=True,
    )
    svc.update_provider(db_session, p.id, is_enabled=False)
    reg = SQLModelRegistry(db_session)
    assert reg.get_tier_default(ModelTier.THINKING) is None


def test_get_any_in_tier_skips_disabled_provider(_env_secret, db_session) -> None:
    p1 = svc.create_provider(
        db_session, kind="openai", label="p1", api_key="k1",
        base_url=None, env_var_name=None, extra_config=None,
    )
    svc.create_model(
        db_session, provider_id=p1.id, tier="quick",
        model_ref="fast-1", display_name="Fast1", is_tier_default=False,
    )
    svc.update_provider(db_session, p1.id, is_enabled=False)

    p2 = svc.create_provider(
        db_session, kind="anthropic", label="p2", api_key="k2",
        base_url=None, env_var_name=None, extra_config=None,
    )
    enabled = svc.create_model(
        db_session, provider_id=p2.id, tier="quick",
        model_ref="fast-2", display_name="Fast2", is_tier_default=False,
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_any_in_tier(ModelTier.QUICK)
    assert row is not None
    assert row.model_id == enabled.id


def test_user_preference_with_disabled_provider_returns_none(
    _env_secret, db_session, make_user
) -> None:
    p = svc.create_provider(
        db_session, kind="openai", label="main", api_key="sk-test",
        base_url=None, env_var_name=None, extra_config=None,
    )
    m = svc.create_model(
        db_session, provider_id=p.id, tier="thinking",
        model_ref="gpt-5.4-pro", display_name="Pro", is_tier_default=True,
    )
    user = make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    svc.set_user_preference(db_session, user_id=user.id, tier="thinking", model_id=m.id)
    svc.update_provider(db_session, p.id, is_enabled=False)
    reg = SQLModelRegistry(db_session)
    assert reg.get_user_preference(user.id, ModelTier.THINKING) is None


def test_resolve_raises_tier_not_configured_when_all_disabled(
    _env_secret, db_session
) -> None:
    from openlia.llm.exceptions import TierNotConfiguredError
    from openlia.llm.resolver import resolve

    p = svc.create_provider(
        db_session, kind="openai", label="main", api_key="sk-test",
        base_url=None, env_var_name=None, extra_config=None,
    )
    m = svc.create_model(
        db_session, provider_id=p.id, tier="thinking",
        model_ref="gpt-5.4-pro", display_name="Pro", is_tier_default=True,
    )
    svc.update_model(db_session, m.id, is_enabled=False)
    reg = SQLModelRegistry(db_session)
    with pytest.raises(TierNotConfiguredError):
        resolve(department_id="equity_research", registry=reg, user_id=None)
```

- [ ] **Step 2: Run the tests to confirm they all pass**

```bash
uv run pytest packages/server/tests/test_services/test_llm_registry.py -v
```

Expected: all tests PASS (production code already handles this).

- [ ] **Step 3: Commit**

```bash
git add packages/server/tests/test_services/test_llm_registry.py
git commit -m "test(registry): add disabled-provider hardening tests (REM-P1-010)"
```

---

## Task 2: REM-P1-011a — ChatRunner multi-round tool loop tests

**Files:**
- Append: `packages/core/tests/test_llm/test_runtime/test_chat.py`

`ChatRunner` already has a 10-round bounded tool loop. These tests protect that behavior. The `FakeProviderScript` already supports chained turns via `_turn_index`. The test file already imports everything needed — just append these three tests.

- [ ] **Step 1: Write the three tests**

Append to `packages/core/tests/test_llm/test_runtime/test_chat.py`:

```python
async def test_two_round_tool_loop_appends_both_results(prompts_root: Path) -> None:
    call_a = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    call_b = ToolCall(id="c2", name="stock_quote", arguments={"symbol": "MSFT"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call_a]),
                ("tool_calls", [call_b]),
                ("final", ""),
                ("tokens", ["Both done"]),
            ]
        )
    )
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(
        manifest=manifest,
        results={"stock_quote": {"price": 100}},
    )
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        message_id_factory=lambda: "m_1",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="AAPL and MSFT?")],
        )
    )
    starts = [e for e in events if isinstance(e, ChatToolCallStart)]
    assert len(starts) == 2
    assert starts[0].call_id == "c1"
    assert starts[1].call_id == "c2"
    assert type(events[-1]) is ChatDone


async def test_max_rounds_falls_through_to_final_text(prompts_root: Path) -> None:
    call = ToolCall(id="cx", name="stock_quote", arguments={"symbol": "X"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[("tool_calls", [call])] * 10 + [("tokens", ["done"])]
        )
    )
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 1}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        message_id_factory=lambda: "m_1",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="go")],
        )
    )
    assert type(events[-1]) is ChatDone
    tokens = [e.text for e in events if isinstance(e, ChatToken)]
    assert "".join(tokens) == "done"


async def test_provider_error_in_tool_loop_emits_chat_error(prompts_root: Path) -> None:
    from openlia.llm.exceptions import LLMProviderError
    from openlia.llm.types import LLMRequest

    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})

    class _LoopErrorProvider(FakeProvider):
        async def generate(self, request: LLMRequest):
            if self._turn_index >= 1:
                raise LLMProviderError("mid-loop failure")
            return await super().generate(request)

    provider = _LoopErrorProvider(
        script=FakeProviderScript(turns=[("tool_calls", [call])])
    )
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 1}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        message_id_factory=lambda: "m_1",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="AAPL?")],
        )
    )
    assert type(events[-1]) is ChatError
    assert "mid-loop failure" in events[-1].message
```

- [ ] **Step 2: Run the tests**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_chat.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/core/tests/test_llm/test_runtime/test_chat.py
git commit -m "test(runtime): protect multi-round chat tool loop behavior (REM-P1-011)"
```

---

## Task 3: REM-P1-011b — ReportRunner multi-round tool loop tests

**Files:**
- Append: `packages/core/tests/test_llm/test_runtime/test_report.py`

`ReportRunner` uses the same bounded 10-round loop as `ChatRunner`. After tool rounds, it goes to a structured-output writing turn (`generate()` with `response_format`). The existing test file already imports everything needed — just append.

- [ ] **Step 1: Write the three tests**

Append to `packages/core/tests/test_llm/test_runtime/test_report.py`:

```python
async def test_two_round_report_tool_loop_emits_both_tool_calls(
    prompts_root: Path, frameworks_root: Path
) -> None:
    call_a = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    call_b = ToolCall(id="c2", name="stock_quote", arguments={"symbol": "MSFT"})
    filled = {"title": "Two-ticker report", "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call_a]),
                ("tool_calls", [call_b]),
                ("final", ""),
                ("final_json", json.dumps(filled)),
            ]
        )
    )
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(
        manifest=manifest, results={"stock_quote": {"price": 100}}
    )
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL+MSFT"),
        )
    )
    tool_events = [e for e in events if isinstance(e, ReportToolCall)]
    assert len(tool_events) == 2
    assert tool_events[0].tool_name == "stock_quote"
    assert tool_events[1].tool_name == "stock_quote"
    assert isinstance(events[-1], ReportComplete)


async def test_report_max_rounds_falls_through_to_writing(
    prompts_root: Path, frameworks_root: Path
) -> None:
    call = ToolCall(id="cx", name="stock_quote", arguments={"symbol": "X"})
    filled = {"title": "Done", "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[("tool_calls", [call])] * 10 + [("final_json", json.dumps(filled))]
        )
    )
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 1}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="X"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    assert events[-1].schema["title"] == "Done"


async def test_provider_error_in_report_tool_loop_emits_report_error(
    prompts_root: Path, frameworks_root: Path
) -> None:
    from openlia.llm.exceptions import LLMProviderError
    from openlia.llm.types import LLMRequest

    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})

    class _LoopErrorProvider(FakeProvider):
        async def generate(self, request: LLMRequest):
            if self._turn_index >= 1:
                raise LLMProviderError("report mid-loop failure")
            return await super().generate(request)

    provider = _LoopErrorProvider(
        script=FakeProviderScript(turns=[("tool_calls", [call])])
    )
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 1}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportError)
    assert "report mid-loop failure" in events[-1].message
```

- [ ] **Step 2: Run the tests**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_report.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/core/tests/test_llm/test_runtime/test_report.py
git commit -m "test(runtime): protect multi-round report tool loop behavior (REM-P1-011)"
```

---

## Task 4: REM-P1-012 — Wire real ReportRunner into production scheduler

**Files:**
- Modify: `packages/server/src/openlia_server/services/runtime.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Modify: `packages/server/tests/test_scheduler/test_wiring.py`

`app.py` currently passes `report_runner=None` to `build_scheduler_service`. If an EU or MB job fires in production, the executor calls `None.run(...)` and crashes. `RefreshingReportRunner` constructs a fresh `ReportRunner` (with fresh DB session and `SQLModelRegistry`) per `.run()` call — necessary because the scheduler holds one instance across many job runs while sessions must not be shared across transactions.

- [ ] **Step 1: Write the wiring test (it will fail: ImportError)**

Append to `packages/server/tests/test_scheduler/test_wiring.py`:

```python
def test_build_scheduler_service_with_real_report_runner(
    session_factory,
) -> None:
    from openlia_server.services.runtime import build_report_runner

    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=build_report_runner(session_factory),
        batch_runner=None,
    )
    assert JobType.MB_BRIEFING in svc.executors
    assert JobType.EU_SCAN in svc.executors
    assert JobType.MR_ASSESSMENT in svc.executors
    assert JobType.SYSTEM_MAINTENANCE in svc.executors
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest packages/server/tests/test_scheduler/test_wiring.py::test_build_scheduler_service_with_real_report_runner -v
```

Expected: FAIL with `ImportError: cannot import name 'build_report_runner' from 'openlia_server.services.runtime'`.

- [ ] **Step 3: Add `_build_report_runner_with_registry`, `RefreshingReportRunner`, and `build_report_runner` to `runtime.py`**

Replace the entire content of `packages/server/src/openlia_server/services/runtime.py` with:

```python
"""Build ChatRunner and ReportRunner wired to the server's LLM admin settings.

Tests stub these factories entirely — the routes and executors accept
runner instances so the builders below are only exercised by the running
application.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from openlia.llm.adapters import build_adapter
from openlia.llm.resolver import resolve
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import SseEvent
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from sqlalchemy.orm import Session as DBSession

from openlia_server.services.llm_registry import SQLModelRegistry


class _EmptyDataDispatcher:
    """No data-provider tools wired yet. Plan 13 replaces this."""

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]:
        return []

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise RuntimeError(f"no data-provider tools registered (attempted {tool_name!r})")

    async def find_more_data(
        self, *, department_id: str, description: str
    ) -> dict[str, Any] | None:
        return None


def _provider_factory(resolved):
    return build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=resolved.capabilities,
    )


def build_chat_runner(
    *,
    db_session_factory: Callable[[], DBSession],
) -> ChatRunner:
    """Construct a `ChatRunner` using the current LLM admin config."""
    db = db_session_factory()
    registry = SQLModelRegistry(db)
    prompts = PromptLoader()
    tools = ToolDispatcher(
        data_dispatcher=_EmptyDataDispatcher(),
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    return ChatRunner(
        prompts=prompts,
        tools=tools,
        resolve=resolve,
        registry=registry,
        provider_factory=_provider_factory,
    )


def _build_report_runner_with_registry(registry: SQLModelRegistry) -> ReportRunner:
    prompts = PromptLoader()
    tools = ToolDispatcher(
        data_dispatcher=_EmptyDataDispatcher(),
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    return ReportRunner(
        prompts=prompts,
        tools=tools,
        resolve=resolve,
        registry=registry,
        provider_factory=_provider_factory,
    )


class RefreshingReportRunner:
    """Constructs a fresh ReportRunner (with fresh DB session and registry)
    per run() call — required for scheduler use where one instance is held
    across multiple job runs."""

    def __init__(self, db_session_factory: Callable[[], DBSession]) -> None:
        self._factory = db_session_factory

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
        cancel_token: CancellationToken | None = None,
    ) -> AsyncIterator[SseEvent]:
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


def build_report_runner(
    db_session_factory: Callable[[], DBSession],
) -> RefreshingReportRunner:
    """Return a `RefreshingReportRunner` for use by the production scheduler."""
    return RefreshingReportRunner(db_session_factory)
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
uv run pytest packages/server/tests/test_scheduler/test_wiring.py -v
```

Expected: all tests PASS including the new one.

- [ ] **Step 5: Wire `build_report_runner` into `app.py`**

In `packages/server/src/openlia_server/app.py`, change the import at line 38:

```python
from openlia_server.services.runtime import build_chat_runner
```

to:

```python
from openlia_server.services.runtime import build_chat_runner, build_report_runner
```

Then inside `_make_lifespan`, change the `build_scheduler_service` call (currently lines ~149-155) from:

```python
                scheduler_svc = build_scheduler_service(
                    session_factory=_sm,
                    settings=scheduler_settings,
                    scheduler=adapter,
                    report_runner=None,
                    batch_runner=None,
                )
```

to:

```python
                scheduler_svc = build_scheduler_service(
                    session_factory=_sm,
                    settings=scheduler_settings,
                    scheduler=adapter,
                    report_runner=build_report_runner(_sm),
                    batch_runner=None,
                )
```

- [ ] **Step 6: Run the full server test suite to verify no regressions**

```bash
uv run pytest packages/server/tests/ -v --tb=short
```

Expected: all existing tests PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/services/runtime.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_scheduler/test_wiring.py
git commit -m "feat(scheduler): wire real ReportRunner into production app startup (REM-P1-012)"
```

---

## Task 5: REM-P1-013 — EU schedule CRUD routes with hot-reload

**Files:**
- Create: `packages/server/src/openlia_server/routes/eu_schedules.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Create: `packages/server/tests/test_scheduler/test_eu_schedules.py`

`EuSchedule` model and `SchedulerService.add_schedule` / `modify_schedule` / `remove_schedule` APIs are complete. The routes call the scheduler hot-reload API after every DB write so APScheduler stays in sync. All write endpoints return 503 when the scheduler is disabled.

`job_key(JobType.EU_SCAN, user_id)` produces the string `"eu_scan:{user_id}"`. After `svc.start()` with an empty DB, `FakeAPScheduler.jobs` contains only `"system_maintenance"`. After a successful POST, it additionally contains `"eu_scan:local"`.

- [ ] **Step 1: Write the test file**

Create `packages/server/tests/test_scheduler/test_eu_schedules.py`:

```python
"""Tests for EU schedule CRUD routes with scheduler hot-reload."""

from __future__ import annotations

from contextlib import asynccontextmanager

import openlia_server.db.models  # noqa: F401 — register all models
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.routes.eu_schedules import build_eu_schedules_router
from openlia_server.scheduler.registry import JobType, job_key
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def route_engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def route_session_factory(route_engine):
    return sessionmaker(
        bind=route_engine,
        future=True,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
def eu_fixtures(route_session_factory):
    """Returns (TestClient, FakeAPScheduler) with a seeded user and running scheduler."""
    from _scheduler_fakes import FakeAPScheduler, FakeBatchRunner, FakeReportRunner
    from openlia_server.scheduler import wiring as wiring_mod
    from openlia_server.scheduler.settings import SchedulerSettings

    with route_session_factory() as s:
        s.add(
            User(
                id="local",
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        s.commit()

    fake_ap = FakeAPScheduler()
    svc = wiring_mod.build_scheduler_service(
        session_factory=route_session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=fake_ap,
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await svc.start()
        app.state.scheduler = svc
        yield
        await svc.shutdown()

    app = FastAPI(lifespan=lifespan)
    app.include_router(
        build_eu_schedules_router(
            db_session_factory=route_session_factory, mode="personal"
        )
    )

    with TestClient(app) as client:
        yield client, fake_ap


@pytest.fixture
def client_no_scheduler(route_session_factory):
    """Client where scheduler is disabled (app.state.scheduler is None)."""
    with route_session_factory() as s:
        s.add(
            User(
                id="local",
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        s.commit()

    app = FastAPI()
    app.state.scheduler = None
    app.include_router(
        build_eu_schedules_router(
            db_session_factory=route_session_factory, mode="personal"
        )
    )
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_SCHEDULE_BODY = {
    "time": "08:00",
    "timezone": "UTC",
    "days_of_week": ["mon", "fri"],
    "label": "Pre-market",
    "is_enabled": True,
}


def test_post_creates_db_row_and_registers_job(eu_fixtures, route_session_factory) -> None:
    client, fake_ap = eu_fixtures
    r = client.post("/departments/earnings-update/schedules", json=_SCHEDULE_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["time"] == "08:00"
    assert body["timezone"] == "UTC"
    assert body["days_of_week"] == ["mon", "fri"]
    assert body["label"] == "Pre-market"
    assert body["user_id"] == "local"

    eu_key = job_key(JobType.EU_SCAN, "local")
    assert eu_key in fake_ap.jobs

    with route_session_factory() as s:
        rows = s.query(EuSchedule).filter(EuSchedule.user_id == "local").all()
        assert len(rows) == 1
        assert rows[0].time == "08:00"


def test_patch_updates_db_row_and_reregisters_job(eu_fixtures, route_session_factory) -> None:
    client, fake_ap = eu_fixtures
    r = client.post("/departments/earnings-update/schedules", json=_SCHEDULE_BODY)
    schedule_id = r.json()["id"]

    updated = {**_SCHEDULE_BODY, "time": "09:30", "days_of_week": ["tue", "thu"]}
    r2 = client.patch(
        f"/departments/earnings-update/schedules/{schedule_id}", json=updated
    )
    assert r2.status_code == 200
    assert r2.json()["time"] == "09:30"
    assert r2.json()["days_of_week"] == ["tue", "thu"]

    eu_key = job_key(JobType.EU_SCAN, "local")
    assert eu_key in fake_ap.jobs

    with route_session_factory() as s:
        row = s.get(EuSchedule, schedule_id)
        assert row.time == "09:30"


def test_delete_removes_db_row_and_unregisters_job(eu_fixtures, route_session_factory) -> None:
    client, fake_ap = eu_fixtures
    r = client.post("/departments/earnings-update/schedules", json=_SCHEDULE_BODY)
    schedule_id = r.json()["id"]

    eu_key = job_key(JobType.EU_SCAN, "local")
    assert eu_key in fake_ap.jobs

    r2 = client.delete(f"/departments/earnings-update/schedules/{schedule_id}")
    assert r2.status_code == 200
    assert r2.json() == {"deleted": schedule_id}

    assert eu_key not in fake_ap.jobs

    with route_session_factory() as s:
        assert s.get(EuSchedule, schedule_id) is None


def test_get_returns_users_schedules(eu_fixtures, route_session_factory) -> None:
    client, _ = eu_fixtures
    client.post("/departments/earnings-update/schedules", json=_SCHEDULE_BODY)
    client.post(
        "/departments/earnings-update/schedules",
        json={**_SCHEDULE_BODY, "time": "10:00", "label": "Mid-day"},
    )
    r = client.get("/departments/earnings-update/schedules")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    times = {it["time"] for it in items}
    assert times == {"08:00", "10:00"}


def test_post_with_scheduler_disabled_returns_503(client_no_scheduler) -> None:
    r = client_no_scheduler.post(
        "/departments/earnings-update/schedules", json=_SCHEDULE_BODY
    )
    assert r.status_code == 503
```

- [ ] **Step 2: Run the test file to confirm it fails with ImportError**

```bash
uv run pytest packages/server/tests/test_scheduler/test_eu_schedules.py -v
```

Expected: FAIL — `ImportError: cannot import name 'build_eu_schedules_router'`.

- [ ] **Step 3: Create `routes/eu_schedules.py`**

Create `packages/server/src/openlia_server/routes/eu_schedules.py`:

```python
"""Earnings Update schedule management routes.

Each write endpoint updates the EuSchedule row then calls the scheduler
hot-reload API so APScheduler stays in sync without a restart.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.scheduler.registry import JobType


class EuScheduleIn(BaseModel):
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    timezone: str = Field(min_length=1, max_length=64)
    days_of_week: list[str] = Field(min_length=1)
    label: str | None = Field(default=None, max_length=64)
    is_enabled: bool = True


class EuScheduleOut(BaseModel):
    id: str
    user_id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str | None
    is_enabled: bool
    created_at: datetime
    last_run_at: datetime | None


def _require_scheduler(request: Request):
    svc = getattr(request.app.state, "scheduler", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="scheduler is disabled; scheduler-backed actions are unavailable",
        )
    return svc


def _row_to_out(row: EuSchedule) -> EuScheduleOut:
    return EuScheduleOut(
        id=row.id,
        user_id=row.user_id,
        time=row.time,
        timezone=row.timezone,
        days_of_week=json.loads(row.days_of_week),
        label=row.label,
        is_enabled=row.is_enabled,
        created_at=row.created_at,
        last_run_at=row.last_run_at,
    )


def build_eu_schedules_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    require_auth = build_require_active_user(
        db_session_factory=db_session_factory, mode=mode
    )
    router = APIRouter(
        prefix="/departments/earnings-update/schedules",
        tags=["eu-schedules"],
    )

    @router.get("", response_model=list[EuScheduleOut])
    def list_schedules(user: User = require_auth) -> list[EuScheduleOut]:
        with db_session_factory() as session:
            rows = (
                session.query(EuSchedule)
                .filter(EuSchedule.user_id == user.id)
                .order_by(EuSchedule.created_at.asc())
                .all()
            )
        return [_row_to_out(r) for r in rows]

    @router.post("", response_model=EuScheduleOut)
    async def create_schedule(
        body: EuScheduleIn,
        request: Request,
        user: User = require_auth,
    ) -> EuScheduleOut:
        svc = _require_scheduler(request)
        row = EuSchedule(
            id=str(uuid.uuid4()),
            user_id=user.id,
            time=body.time,
            timezone=body.timezone,
            days_of_week=json.dumps(body.days_of_week),
            label=body.label,
            is_enabled=body.is_enabled,
            created_at=datetime.now(UTC),
            last_run_at=None,
        )
        with db_session_factory() as session:
            session.add(row)
            session.commit()
            session.expunge(row)
        if body.is_enabled:
            await svc.add_schedule(row)
        return _row_to_out(row)

    @router.patch("/{schedule_id}", response_model=EuScheduleOut)
    async def update_schedule(
        schedule_id: str,
        body: EuScheduleIn,
        request: Request,
        user: User = require_auth,
    ) -> EuScheduleOut:
        svc = _require_scheduler(request)
        with db_session_factory() as session:
            row = session.get(EuSchedule, schedule_id)
            if row is None or row.user_id != user.id:
                raise HTTPException(status_code=404, detail="schedule not found")
            row.time = body.time
            row.timezone = body.timezone
            row.days_of_week = json.dumps(body.days_of_week)
            row.label = body.label
            row.is_enabled = body.is_enabled
            session.commit()
            session.expunge(row)
        await svc.modify_schedule(row)
        return _row_to_out(row)

    @router.delete("/{schedule_id}")
    async def delete_schedule(
        schedule_id: str,
        request: Request,
        user: User = require_auth,
    ) -> dict:
        svc = _require_scheduler(request)
        with db_session_factory() as session:
            row = session.get(EuSchedule, schedule_id)
            if row is None or row.user_id != user.id:
                raise HTTPException(status_code=404, detail="schedule not found")
            user_id = row.user_id
            session.delete(row)
            session.commit()
        await svc.remove_schedule(job_type=JobType.EU_SCAN, user_id=user_id)
        return {"deleted": schedule_id}

    return router
```

- [ ] **Step 4: Mount the router in `create_app()`**

In `packages/server/src/openlia_server/app.py`, add this import after the existing route imports (around line 36):

```python
from openlia_server.routes.eu_schedules import build_eu_schedules_router
```

Then inside `create_app()`, add the mount after `build_chat_stream_router` (around line 203):

```python
    app.include_router(build_eu_schedules_router(db_session_factory=factory, mode=mode))
```

- [ ] **Step 5: Run the tests to confirm they all pass**

```bash
uv run pytest packages/server/tests/test_scheduler/test_eu_schedules.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Run the full server test suite to verify no regressions**

```bash
uv run pytest packages/server/tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/routes/eu_schedules.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_scheduler/test_eu_schedules.py
git commit -m "feat(eu-schedules): add CRUD routes with APScheduler hot-reload (REM-P1-013)"
```

---

## Task 6: Update remediation checklist and run full test suite

**Files:**
- Modify: `planning/audits/2026-04-21-remediation-checklist.md`

- [ ] **Step 1: Update checklist status fields**

In `planning/audits/2026-04-21-remediation-checklist.md`, update the following status lines:

| Item | Old status | New status |
|------|-----------|-----------|
| `REM-P1-010` | `[ ]` | `[x]` |
| `REM-P1-011` | `[ ]` | `[x]` |
| `REM-P1-012` | `[ ]` | `[x]` |
| `REM-P1-013` | `[ ]` | `[x]` |
| `REM-P1-015` | `[ ]` | `[x]` |

Also update the "Before Plan 13-15 Implementation" merge gate block:

```
- `[x]` REM-P1-010
- `[x]` REM-P1-011
- `[x]` REM-P1-012
- `[x]` REM-P1-013
- `[x]` REM-P1-014
- `[x]` REM-P1-015
```

- [ ] **Step 2: Run the complete test suite**

```bash
uv run pytest packages/core/tests/ packages/server/tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add planning/audits/2026-04-21-remediation-checklist.md
git commit -m "docs(checklist): mark REM-P1-010 through P1-015 complete"
```
