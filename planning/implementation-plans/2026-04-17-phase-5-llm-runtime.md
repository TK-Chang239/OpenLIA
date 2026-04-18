# Phase 5 — LLM Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the execution layer under `packages/core/src/openlia/llm/runtime/` so every department plan (Plans 13–16, 19, 20) can call `ChatRunner.run()`, `ReportRunner.run()`, or `BatchRunner.run()` against a resolved `LLMProvider` with department prompts, framework + style-guide injection, tool dispatch (requirement tools + `find_more_data` + `web_search`), SSE streaming (`chat.*` / `report.*`), client-disconnect cancellation, and `TierNotConfiguredError`-aware error events.

**Architecture:** Three async-iterator runners sit on top of Plan 4's `LLMProvider` contract and Plan 3's `DataProviderDispatcher` Protocol. Prompts live as Jinja2-templated YAML files (`packages/core/src/openlia/prompts/<department>.yaml`), with shared snippets under `shared/`. Report frameworks and style guides physically move from `planning/frameworks/` into `packages/core/src/openlia/reports/frameworks/` so the core wheel ships them. SSE events are flat typed dataclasses serialized to `data: {"type": "...", ...}` lines at the server edge. Cancellation is driven by a `CancellationToken` flipped by the FastAPI route when the client disconnects; runners give in-flight tool calls a 2-second grace, then stop yielding (no terminal SSE event on cancellation).

**Tech Stack:** Python 3.12, `asyncio`, `jinja2` ≥ 3.1, `PyYAML` ≥ 6.0, `pydantic` ≥ 2.5 (for `BatchRunner.schema`), `httpx` (reused for search adapters). Tests use `pytest` + `pytest-asyncio` with fake `LLMProvider` implementations.

**Source spec:** `planning/specs/systems/llm-runtime-design.md` (full spec — every in-scope section is covered by a task in this plan). Supporting: `planning/specs/systems/report-rendering-pipeline-design.md` (framework/style-guide injection), `planning/specs/systems/data-provider-design.md` (`search` category, mapping files), `planning/specs/pages/ChatInterfaceSpec.md` (frontend event handling that Plan 12 will implement).

**Depends on:**
- **Plan 4** — `LLMProvider` ABC (`openlia.llm.base.LLMProvider`), `resolve()` (`openlia.llm.resolver.resolve`), `ModelRegistry` Protocol, type surface (`openlia.llm.types`: `Capabilities`, `Capability`, `Message`, `ToolSchema`, `ToolCall`, `LLMRequest`, `LLMResponse`, `LLMChunk`, `ResponseFormat`, `ResolvedModel`, `ModelTier`, `DepartmentRequirements`), exception hierarchy (`openlia.llm.exceptions`: `TierNotConfiguredError`, `AuthError`, `ModelNotFoundError`, `CapabilityError`, `ContextLengthError`, `RateLimitError`, `ProviderOutageError`, `TransportError`).
- **Plan 3** — `DataProviderDispatcher` Protocol (ships as `openlia.data.dispatcher.DataProviderDispatcher` in Plan 3). This plan defines the Protocol surface it consumes inline so tests can stand up fakes without a real Plan 3 implementation.
- **Plan 1a** — no direct DB access from runtime code (runtime is stateless), but `user_id: str` typing matches `users.id`.

**Unblocks:** every department plan (13–16, 19, 20) — runtime is the last prerequisite before a department page can stream tokens to the frontend.

**Out of scope (handled elsewhere):**
- Provider adapters, resolver, capability map, credential encryption — Plan 4.
- Data-provider adapter classes, mapping-file generation, catalog search for `find_more_data`, EODHD adapter — Plan 3.
- Chat-session DB persistence (`chat_sessions`, `chat_messages`) and server SSE routes — Plans 12 / department plans.
- `ReportSchema` definition and markdown renderer — Plan 13 (`report-rendering-pipeline-design.md`).
- Retail Sentiment / Macro Research dashboard orchestration — Plans 19, 20 (they call `BatchRunner.run()` but own the batching semantics).
- Frontend consumption of SSE events — Plan 12.
- Vision / image attachments — explicitly deferred; `ChatMessage.attachments` accepts an empty list only in v1.
- User-authored custom tools — deferred to a future plan (see spec dev note).
- Persistence of partial chat text with `stopped_at` marker on cancellation — server route's job, not runtime.

---

## File Structure

Files created or modified in this plan:

```
openlia/
├── packages/
│   └── core/
│       ├── pyproject.toml                                 # MODIFIED — +jinja2, +pyyaml, +pydantic
│       └── src/openlia/
│           ├── llm/
│           │   └── runtime/                               # NEW package
│           │       ├── __init__.py                        # Public exports
│           │       ├── messages.py                        # ChatMessage, ReportRequest, BatchItem, BatchResult, Attachment
│           │       ├── events.py                          # SseEvent discriminated-union dataclasses
│           │       ├── cancellation.py                    # CancellationToken + 2s-grace helper
│           │       ├── prompts.py                         # YAML loader + Jinja2 rendering, PromptSlotNotFound
│           │       ├── web_search.py                      # resolve_web_search(), WebSearchAdapter Protocol
│           │       ├── tools.py                           # ToolDispatcher, DataProviderDispatcher Protocol
│           │       ├── chat.py                            # ChatRunner
│           │       ├── report.py                          # ReportRunner
│           │       └── batch.py                           # BatchRunner
│           ├── prompts/                                   # NEW package (data only — no Python)
│           │   ├── __init__.py                            # Sentinel so importlib.resources can locate prompts/
│           │   ├── secretary.yaml
│           │   ├── equity_research.yaml
│           │   ├── earnings_update.yaml
│           │   ├── morning_briefing.yaml
│           │   ├── macro_research.yaml                    # batch slots only (T4/T5 assessments)
│           │   ├── retail_sentiment.yaml                  # batch slot only (classify_sentiment)
│           │   └── shared/
│           │       ├── voice.yaml.j2
│           │       └── output_discipline.yaml.j2
│           └── reports/
│               └── frameworks/                            # NEW package (data only)
│                   ├── __init__.py                        # Sentinel for importlib.resources
│                   ├── stock_initiation.json              # MOVED from planning/frameworks/stock_initiation_framework.json
│                   ├── stock_initiation_style_guide.md    # MOVED from planning/frameworks/
│                   ├── stock_update.json                  # MOVED + renamed
│                   ├── stock_update_style_guide.md        # MOVED
│                   ├── sector_research.json               # MOVED + renamed
│                   ├── sector_research_style_guide.md     # MOVED
│                   ├── earnings_update.json               # MOVED + renamed
│                   ├── earnings_update_style_guide.md     # MOVED
│                   ├── morning_briefing.json              # MOVED + renamed
│                   └── morning_briefing_style_guide.md    # MOVED
└── packages/core/tests/
    └── test_llm/
        └── test_runtime/                                  # NEW
            ├── __init__.py
            ├── conftest.py                                # FakeProvider, FakeDataDispatcher, FakeSearchAdapter
            ├── test_messages.py
            ├── test_events.py
            ├── test_cancellation.py
            ├── test_prompts.py
            ├── test_web_search.py
            ├── test_tools.py
            ├── test_chat.py
            ├── test_report.py
            └── test_batch.py
```

Design rules:

- **Core-only.** Nothing under `llm/runtime/` may import FastAPI, SQLAlchemy, or anything from `openlia_server.*`. The runtime consumes Protocols (`ModelRegistry`, `DataProviderDispatcher`, `WebSearchAdapter`) and is handed instances by the server at call time.
- **Async-first.** Every public function that performs I/O is `async`. `ChatRunner.run()` / `ReportRunner.run()` return `AsyncIterator[SseEvent]`; `BatchRunner.run()` returns `list[BatchResult]`.
- **Stateless per call.** Runners hold no per-user cache, no cross-call memoization. Construct a new runner (or reuse a per-process singleton — both are safe) and call `run()`; nothing lingers.
- **One file per concern.** `chat.py`, `report.py`, `batch.py` stay under ~300 lines each. If a runner balloons past that, the shared logic gets lifted into `runtime/_shared.py`.
- **Tool schemas are provider-agnostic.** `ToolSchema.parameters` is a JSON-schema dict; adapters in Plan 4 translate this into each provider's tool-format on the wire.
- **SSE events are data, not strings.** Events are dataclasses with a `type` string field. Serialization into `data: {...}\n\n` SSE frames happens in the server route (Plan 12), not here.

---

## Task 1: Scaffold `runtime/` + add dependencies + move frameworks

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/__init__.py` (empty at this step)
- Create: `packages/core/src/openlia/prompts/__init__.py` (empty)
- Create: `packages/core/src/openlia/prompts/shared/` (directory)
- Create: `packages/core/src/openlia/reports/__init__.py` (empty if missing)
- Create: `packages/core/src/openlia/reports/frameworks/__init__.py` (empty)
- Create: `packages/core/tests/test_llm/test_runtime/__init__.py` (empty)
- Modify: `packages/core/pyproject.toml` — add `jinja2`, `pyyaml`
- Move: `planning/frameworks/*.json` + `*.md` → `packages/core/src/openlia/reports/frameworks/` (rename `_framework.json` → `.json`)

- [ ] **Step 1: Create empty package directories**

```bash
mkdir -p packages/core/src/openlia/llm/runtime
mkdir -p packages/core/src/openlia/prompts/shared
mkdir -p packages/core/src/openlia/reports/frameworks
mkdir -p packages/core/tests/test_llm/test_runtime
touch packages/core/src/openlia/llm/runtime/__init__.py
touch packages/core/src/openlia/prompts/__init__.py
touch packages/core/src/openlia/reports/__init__.py
touch packages/core/src/openlia/reports/frameworks/__init__.py
touch packages/core/tests/test_llm/test_runtime/__init__.py
```

If `packages/core/src/openlia/reports/__init__.py` already exists (from a prior plan), leave it as-is.

- [ ] **Step 2: Add dependencies to the core package**

Modify `packages/core/pyproject.toml`, replace the `dependencies = [...]` array so it reads:

```toml
dependencies = [
    "pydantic>=2.6",
    "jinja2>=3.1",
    "pyyaml>=6.0",
]
```

Run: `uv sync` (from repo root).
Expected: `jinja2` and `pyyaml` resolve and install.

- [ ] **Step 3: Move framework JSON + style-guide markdown into the core package**

```bash
git mv planning/frameworks/stock_initiation_framework.json \
       packages/core/src/openlia/reports/frameworks/stock_initiation.json
git mv planning/frameworks/stock_initiation_style_guide.md \
       packages/core/src/openlia/reports/frameworks/stock_initiation_style_guide.md
git mv planning/frameworks/stock_update_framework.json \
       packages/core/src/openlia/reports/frameworks/stock_update.json
git mv planning/frameworks/stock_update_style_guide.md \
       packages/core/src/openlia/reports/frameworks/stock_update_style_guide.md
git mv planning/frameworks/sector_research_framework.json \
       packages/core/src/openlia/reports/frameworks/sector_research.json
git mv planning/frameworks/sector_research_style_guide.md \
       packages/core/src/openlia/reports/frameworks/sector_research_style_guide.md
git mv planning/frameworks/earnings_update_framework.json \
       packages/core/src/openlia/reports/frameworks/earnings_update.json
git mv planning/frameworks/earnings_update_style_guide.md \
       packages/core/src/openlia/reports/frameworks/earnings_update_style_guide.md
git mv planning/frameworks/morning_briefing_framework.json \
       packages/core/src/openlia/reports/frameworks/morning_briefing.json
git mv planning/frameworks/morning_briefing_style_guide.md \
       packages/core/src/openlia/reports/frameworks/morning_briefing_style_guide.md
rmdir planning/frameworks
```

Expected: `ls packages/core/src/openlia/reports/frameworks/` shows 10 files + `__init__.py`; `ls planning/frameworks 2>/dev/null` returns nothing.

- [ ] **Step 4: Ensure framework files are packaged in the wheel**

Modify `packages/core/pyproject.toml`, append under `[tool.uv.build-backend]`:

```toml
[tool.uv.build-backend]
module-name = "openlia"
module-root = "src"

[tool.hatch.build.targets.wheel.force-include]
"src/openlia/prompts" = "openlia/prompts"
"src/openlia/reports/frameworks" = "openlia/reports/frameworks"
```

(`uv_build` is the build backend but understands `tool.hatch.build.targets.wheel` for file inclusion, per the Phase 0 pattern. If `uv_build` does not honor these keys, fall back to adding `include = ["openlia/prompts/**/*", "openlia/reports/frameworks/**/*"]` under `[tool.uv.build-backend]`.)

- [ ] **Step 5: Commit**

```bash
git add packages/core/pyproject.toml \
        packages/core/src/openlia/llm/runtime/__init__.py \
        packages/core/src/openlia/prompts/__init__.py \
        packages/core/src/openlia/reports/__init__.py \
        packages/core/src/openlia/reports/frameworks/ \
        packages/core/tests/test_llm/test_runtime/__init__.py \
        planning/frameworks
git commit -m "phase-5(runtime): scaffold runtime/ + prompts/ packages; move frameworks into core wheel"
```

---

## Task 2: `messages.py` — ChatMessage, ReportRequest, BatchItem, BatchResult, Attachment

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/messages.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_messages.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/core/tests/test_llm/test_runtime/test_messages.py`:

```python
from __future__ import annotations

import pytest

from openlia.llm.runtime.messages import (
    Attachment,
    BatchItem,
    BatchResult,
    ChatMessage,
    ReportRequest,
)


def test_chat_message_basic() -> None:
    m = ChatMessage(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"
    assert m.attachments == []


def test_chat_message_roles_are_open_strings() -> None:
    assert ChatMessage(role="assistant", content="hi").role == "assistant"
    assert ChatMessage(role="system", content="be nice").role == "system"


def test_chat_message_with_attachments_v1_reserved_only() -> None:
    a = Attachment(kind="image", url="https://example.com/a.png", mime_type="image/png")
    m = ChatMessage(role="user", content="see this", attachments=[a])
    assert m.attachments[0].kind == "image"
    assert m.attachments[0].url == "https://example.com/a.png"


def test_report_request_minimal() -> None:
    r = ReportRequest(
        mode="stock_initiation",
        user_input="Initiate AAPL.",
    )
    assert r.mode == "stock_initiation"
    assert r.user_input == "Initiate AAPL."
    assert r.enabled_sections == []
    assert r.custom_sections == []
    assert r.length == "standard"


def test_report_request_full() -> None:
    r = ReportRequest(
        mode="sector_research",
        user_input="US semis.",
        enabled_sections=["overview", "thesis"],
        custom_sections=[{"title": "Regulatory outlook", "instructions": "US-only."}],
        length="long",
    )
    assert r.enabled_sections == ["overview", "thesis"]
    assert r.custom_sections[0]["title"] == "Regulatory outlook"
    assert r.length == "long"


def test_report_request_rejects_unknown_length() -> None:
    with pytest.raises(ValueError, match="length"):
        ReportRequest(mode="stock_update", user_input="AAPL", length="gargantuan")


def test_batch_item_shape() -> None:
    item = BatchItem(id="post-1", context={"text": "YOLO AAPL calls"})
    assert item.id == "post-1"
    assert item.context["text"] == "YOLO AAPL calls"


def test_batch_result_ok() -> None:
    r = BatchResult(id="post-1", ok=True, data={"sentiment": "bullish"}, error=None)
    assert r.ok is True
    assert r.data == {"sentiment": "bullish"}
    assert r.error is None


def test_batch_result_failure_carries_error() -> None:
    r = BatchResult(id="post-2", ok=False, data=None, error="ContextLengthError: 8192")
    assert r.ok is False
    assert r.data is None
    assert r.error == "ContextLengthError: 8192"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_messages.py -v`
Expected: `ModuleNotFoundError: No module named 'openlia.llm.runtime.messages'`.

- [ ] **Step 3: Implement the messages module**

Create `packages/core/src/openlia/llm/runtime/messages.py`:

```python
"""Runtime-facing message and request dataclasses.

Kept distinct from `openlia.llm.types.Message` which is the provider-facing
atom. A runtime ChatMessage can also carry attachments (reserved for vision
in v1) and is mapped into provider `Message` objects inside ChatRunner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

_ALLOWED_LENGTHS = ("brief", "standard", "long")


@dataclass(frozen=True)
class Attachment:
    """Reserved for vision inputs. v1 runners accept but never forward them."""

    kind: Literal["image", "file"]
    url: str
    mime_type: str


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    attachments: list[Attachment] = field(default_factory=list)


@dataclass(frozen=True)
class ReportRequest:
    mode: str
    user_input: str
    enabled_sections: list[str] = field(default_factory=list)
    custom_sections: list[dict[str, Any]] = field(default_factory=list)
    length: str = "standard"

    def __post_init__(self) -> None:
        if self.length not in _ALLOWED_LENGTHS:
            raise ValueError(
                f"length must be one of {_ALLOWED_LENGTHS}, got {self.length!r}"
            )


@dataclass(frozen=True)
class BatchItem:
    id: str
    context: dict[str, Any]


@dataclass(frozen=True)
class BatchResult:
    id: str
    ok: bool
    data: dict[str, Any] | None
    error: str | None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_messages.py -v`
Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/messages.py
uv run ruff format packages/core/src/openlia/llm/runtime/messages.py \
                   packages/core/tests/test_llm/test_runtime/test_messages.py
git add packages/core/src/openlia/llm/runtime/messages.py \
        packages/core/tests/test_llm/test_runtime/test_messages.py
git commit -m "phase-5(runtime): runtime message/request dataclasses (ChatMessage/ReportRequest/BatchItem/BatchResult)"
```

---

## Task 3: `events.py` — SSE event taxonomy

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/events.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_events.py`

The runtime ships events as frozen dataclasses. A single `SseEvent` union alias covers the 12 event shapes from the spec. `to_wire()` returns a JSON-safe dict with `type` plus the event fields — the server route serializes that dict as `data: {...}\n\n`.

- [ ] **Step 1: Write the failing event tests**

Create `packages/core/tests/test_llm/test_runtime/test_events.py`:

```python
from __future__ import annotations

import json

import pytest

from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatReportThumbnail,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    ReportToolCall,
    to_wire,
)


def test_chat_start_wire_shape() -> None:
    e = ChatStart(message_id="m_1")
    assert to_wire(e) == {"type": "chat.start", "message_id": "m_1"}


def test_chat_token_wire_shape() -> None:
    e = ChatToken(message_id="m_1", text="Apple")
    assert to_wire(e) == {"type": "chat.token", "message_id": "m_1", "text": "Apple"}


def test_chat_tool_call_start_carries_preview() -> None:
    e = ChatToolCallStart(
        message_id="m_1",
        call_id="c_1",
        tool_name="stock_quote",
        args_preview='{"symbol":"AAPL"}',
    )
    d = to_wire(e)
    assert d["type"] == "chat.tool_call.start"
    assert d["call_id"] == "c_1"
    assert d["tool_name"] == "stock_quote"
    assert d["args_preview"] == '{"symbol":"AAPL"}'


def test_chat_tool_call_result_carries_ok_and_summary() -> None:
    e = ChatToolCallResult(
        message_id="m_1", call_id="c_1", ok=True, summary="Fetched quote for AAPL"
    )
    d = to_wire(e)
    assert d["type"] == "chat.tool_call.result"
    assert d["ok"] is True
    assert d["summary"] == "Fetched quote for AAPL"


def test_chat_done_carries_stop_reason() -> None:
    e = ChatDone(message_id="m_1", stop_reason="complete")
    assert to_wire(e)["stop_reason"] == "complete"


def test_chat_error_includes_class_and_message() -> None:
    e = ChatError(
        message_id="m_1",
        error_class="TierNotConfiguredError",
        message="No enabled models configured in tier 'thinking'.",
    )
    d = to_wire(e)
    assert d["type"] == "chat.error"
    assert d["error_class"] == "TierNotConfiguredError"
    assert "thinking" in d["message"]


def test_chat_report_thumbnail_links_report_id() -> None:
    e = ChatReportThumbnail(message_id="m_1", report_id="r_1", mode="stock_initiation")
    assert to_wire(e) == {
        "type": "chat.report_thumbnail",
        "message_id": "m_1",
        "report_id": "r_1",
        "mode": "stock_initiation",
    }


def test_report_start_includes_section_titles() -> None:
    e = ReportStart(
        report_id="r_1",
        department="equity_research",
        mode="stock_initiation",
        section_titles=["Overview", "Thesis"],
    )
    assert to_wire(e)["section_titles"] == ["Overview", "Thesis"]


def test_report_phase_values() -> None:
    assert to_wire(ReportPhase(report_id="r_1", phase="fetching_data"))["phase"] == "fetching_data"
    assert to_wire(ReportPhase(report_id="r_1", phase="writing"))["phase"] == "writing"
    assert to_wire(ReportPhase(report_id="r_1", phase="finalizing"))["phase"] == "finalizing"


def test_report_phase_rejects_unknown_phase() -> None:
    with pytest.raises(ValueError, match="phase"):
        ReportPhase(report_id="r_1", phase="blasting_off")


def test_report_tool_call_wire_shape() -> None:
    e = ReportToolCall(
        report_id="r_1", tool_name="financial_statements", summary="Fetched 10-K for AAPL"
    )
    d = to_wire(e)
    assert d["type"] == "report.tool_call"
    assert d["tool_name"] == "financial_statements"


def test_report_complete_carries_schema_payload() -> None:
    schema = {"title": "AAPL Initiation", "sections": []}
    e = ReportComplete(report_id="r_1", schema=schema)
    d = to_wire(e)
    assert d["type"] == "report.complete"
    assert d["schema"] == schema


def test_report_error_wire_shape() -> None:
    e = ReportError(
        report_id="r_1", error_class="CapabilityError", message="Tools not supported"
    )
    assert to_wire(e) == {
        "type": "report.error",
        "report_id": "r_1",
        "error_class": "CapabilityError",
        "message": "Tools not supported",
    }


def test_to_wire_output_is_json_serializable() -> None:
    e = ReportComplete(report_id="r_1", schema={"title": "x", "sections": []})
    json.dumps(to_wire(e))  # must not raise
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_events.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the events module**

Create `packages/core/src/openlia/llm/runtime/events.py`:

```python
"""SSE event dataclasses (chat.* and report.* discriminated union).

Every event has a class-level `TYPE` literal used by `to_wire()` to build
the on-the-wire dict. Serialization into SSE frames (`data: ...\\n\\n`)
happens in the server route; this module stays pure-data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Union

ReportPhaseName = Literal["fetching_data", "writing", "finalizing"]
_ALLOWED_PHASES: tuple[str, ...] = ("fetching_data", "writing", "finalizing")


@dataclass(frozen=True)
class ChatStart:
    TYPE = "chat.start"
    message_id: str


@dataclass(frozen=True)
class ChatToolCallStart:
    TYPE = "chat.tool_call.start"
    message_id: str
    call_id: str
    tool_name: str
    args_preview: str


@dataclass(frozen=True)
class ChatToolCallResult:
    TYPE = "chat.tool_call.result"
    message_id: str
    call_id: str
    ok: bool
    summary: str


@dataclass(frozen=True)
class ChatToken:
    TYPE = "chat.token"
    message_id: str
    text: str


@dataclass(frozen=True)
class ChatReportThumbnail:
    TYPE = "chat.report_thumbnail"
    message_id: str
    report_id: str
    mode: str


@dataclass(frozen=True)
class ChatDone:
    TYPE = "chat.done"
    message_id: str
    stop_reason: str


@dataclass(frozen=True)
class ChatError:
    TYPE = "chat.error"
    message_id: str
    error_class: str
    message: str


@dataclass(frozen=True)
class ReportStart:
    TYPE = "report.start"
    report_id: str
    department: str
    mode: str
    section_titles: list[str]


@dataclass(frozen=True)
class ReportPhase:
    TYPE = "report.phase"
    report_id: str
    phase: str

    def __post_init__(self) -> None:
        if self.phase not in _ALLOWED_PHASES:
            raise ValueError(
                f"phase must be one of {_ALLOWED_PHASES}, got {self.phase!r}"
            )


@dataclass(frozen=True)
class ReportToolCall:
    TYPE = "report.tool_call"
    report_id: str
    tool_name: str
    summary: str


@dataclass(frozen=True)
class ReportComplete:
    TYPE = "report.complete"
    report_id: str
    schema: dict[str, Any]


@dataclass(frozen=True)
class ReportError:
    TYPE = "report.error"
    report_id: str
    error_class: str
    message: str


SseEvent = Union[
    ChatStart,
    ChatToolCallStart,
    ChatToolCallResult,
    ChatToken,
    ChatReportThumbnail,
    ChatDone,
    ChatError,
    ReportStart,
    ReportPhase,
    ReportToolCall,
    ReportComplete,
    ReportError,
]


def to_wire(event: SseEvent) -> dict[str, Any]:
    """Return a JSON-serializable dict with `type` plus the event fields."""
    payload = {"type": event.TYPE}
    payload.update(asdict(event))
    return payload
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_events.py -v`
Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/events.py
uv run ruff format packages/core/src/openlia/llm/runtime/events.py \
                   packages/core/tests/test_llm/test_runtime/test_events.py
git add packages/core/src/openlia/llm/runtime/events.py \
        packages/core/tests/test_llm/test_runtime/test_events.py
git commit -m "phase-5(runtime): SSE event taxonomy (chat.*/report.* dataclasses + to_wire)"
```

---

## Task 4: `cancellation.py` — CancellationToken + grace helper

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/cancellation.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_cancellation.py`

The token is a single boolean flag plus an `asyncio.Event` so callers can `await token.wait()` or poll `token.is_cancelled`. `await_with_grace(coro, grace_seconds=2)` wraps an in-flight tool call — if the token is flipped mid-call, the coroutine gets `grace_seconds` to finish; otherwise it is cancelled. No timer starts unless/until the flip happens.

- [ ] **Step 1: Write the failing cancellation tests**

Create `packages/core/tests/test_llm/test_runtime/test_cancellation.py`:

```python
from __future__ import annotations

import asyncio
import time

import pytest

from openlia.llm.runtime.cancellation import (
    CancellationToken,
    await_with_grace,
)

pytestmark = pytest.mark.asyncio


async def test_new_token_is_not_cancelled() -> None:
    tok = CancellationToken()
    assert tok.is_cancelled is False


async def test_cancel_sets_flag() -> None:
    tok = CancellationToken()
    tok.cancel()
    assert tok.is_cancelled is True


async def test_wait_returns_on_cancel() -> None:
    tok = CancellationToken()

    async def flip() -> None:
        await asyncio.sleep(0.01)
        tok.cancel()

    asyncio.create_task(flip())
    await asyncio.wait_for(tok.wait(), timeout=1.0)
    assert tok.is_cancelled is True


async def test_await_with_grace_returns_result_when_not_cancelled() -> None:
    tok = CancellationToken()

    async def slow() -> int:
        await asyncio.sleep(0.05)
        return 42

    result = await await_with_grace(slow(), token=tok, grace_seconds=1.0)
    assert result == 42


async def test_await_with_grace_cancels_after_grace_window() -> None:
    tok = CancellationToken()

    async def never_finishes() -> None:
        await asyncio.sleep(10)

    coro = never_finishes()
    tok.cancel()
    t0 = time.monotonic()
    with pytest.raises(asyncio.CancelledError):
        await await_with_grace(coro, token=tok, grace_seconds=0.2)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0  # definitely cancelled well before 10s


async def test_await_with_grace_still_returns_if_task_finishes_within_grace() -> None:
    tok = CancellationToken()

    async def finishes_fast() -> str:
        await asyncio.sleep(0.05)
        return "ok"

    coro = finishes_fast()
    tok.cancel()  # flipped before awaiting
    result = await await_with_grace(coro, token=tok, grace_seconds=1.0)
    assert result == "ok"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_cancellation.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement cancellation**

Create `packages/core/src/openlia/llm/runtime/cancellation.py`:

```python
"""Cancellation primitives for the runtime.

Driven by client disconnect: the server route flips the token when
`request.is_disconnected()` returns True. Runners poll the flag between
yields; in-flight tool calls get a bounded grace period before being
cancelled.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, TypeVar

T = TypeVar("T")


class CancellationToken:
    """Single-shot boolean flag + event. Idempotent on repeated cancel()."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()


async def await_with_grace(
    awaitable: Awaitable[T],
    *,
    token: CancellationToken,
    grace_seconds: float = 2.0,
) -> T:
    """Await `awaitable`; if `token` is flipped, allow at most `grace_seconds`.

    Behavior:
      - Token never flips -> returns the coroutine's result normally.
      - Token flips AND coroutine finishes within grace -> returns the result.
      - Token flips AND coroutine does not finish within grace -> raises
        asyncio.CancelledError after cancelling the underlying task.
    """
    task: asyncio.Task[T] = asyncio.ensure_future(awaitable)
    cancel_waiter = asyncio.ensure_future(token.wait())

    try:
        done, _ = await asyncio.wait(
            {task, cancel_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if task in done:
            cancel_waiter.cancel()
            return task.result()

        # Token flipped; give the task the grace window.
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=grace_seconds)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            raise asyncio.CancelledError()
    finally:
        if not cancel_waiter.done():
            cancel_waiter.cancel()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_cancellation.py -v`
Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/cancellation.py
uv run ruff format packages/core/src/openlia/llm/runtime/cancellation.py \
                   packages/core/tests/test_llm/test_runtime/test_cancellation.py
git add packages/core/src/openlia/llm/runtime/cancellation.py \
        packages/core/tests/test_llm/test_runtime/test_cancellation.py
git commit -m "phase-5(runtime): CancellationToken + 2s-grace helper for in-flight tool calls"
```

---

## Task 5: `prompts.py` — YAML loader + Jinja2 rendering

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/prompts.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_prompts.py`

The loader locates a department YAML via `importlib.resources` (so the package works both from source and from an installed wheel). Each YAML is parsed once, cached in-process, and its leaf string values are rendered through a Jinja2 `Environment` with `shared/*.yaml.j2` available as `{% include %}` targets. `render(department_id, slot, **context) -> str` walks dotted slot names (e.g. `"report.stock_initiation.user"`). Missing slots raise `PromptSlotNotFound` at call time — plus a `validate_department_slots(department_id, expected_slots)` helper lets startup code loudly catch typos.

- [ ] **Step 1: Write the failing prompt-loader tests**

Create `packages/core/tests/test_llm/test_runtime/test_prompts.py`:

```python
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from openlia.llm.runtime.prompts import (
    PromptLoader,
    PromptSlotNotFound,
)


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    pdir = tmp_path / "prompts"
    shared = pdir / "shared"
    shared.mkdir(parents=True)
    (shared / "voice.yaml.j2").write_text("Speak concisely.\n")
    (shared / "output_discipline.yaml.j2").write_text(
        "Return only the required format."
    )

    (pdir / "secretary.yaml").write_text(
        dedent(
            """\
            chat:
              system: |
                You are the Secretary.
                {% include "shared/voice.yaml.j2" %}
              welcome: |
                Hello {{ user_name | default('friend') }}.
            """
        )
    )

    (pdir / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Follow this style guide:
                {{ style_guide }}
                {% include "shared/output_discipline.yaml.j2" %}
              stock_initiation:
                user: |
                  Initiate {{ user_input }}.
                  Length: {{ length }}
                  Sections: {{ enabled_sections | join(', ') }}
            """
        )
    )
    return pdir


def test_render_simple_slot(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    out = loader.render("secretary", "chat.welcome", user_name="Ada")
    assert "Hello Ada." in out


def test_render_simple_slot_with_default_context(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    out = loader.render("secretary", "chat.welcome")
    assert "Hello friend." in out


def test_render_supports_shared_includes(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    out = loader.render("secretary", "chat.system")
    assert "Secretary" in out
    assert "Speak concisely." in out


def test_render_nested_slot_with_context(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    out = loader.render(
        "equity_research",
        "report.stock_initiation.user",
        user_input="AAPL",
        length="standard",
        enabled_sections=["overview", "thesis"],
    )
    assert "Initiate AAPL." in out
    assert "overview, thesis" in out


def test_missing_slot_raises_prompt_slot_not_found(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    with pytest.raises(PromptSlotNotFound) as excinfo:
        loader.render("secretary", "chat.nope")
    assert "secretary" in str(excinfo.value)
    assert "chat.nope" in str(excinfo.value)


def test_missing_department_raises_prompt_slot_not_found(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    with pytest.raises(PromptSlotNotFound):
        loader.render("made_up", "chat.system")


def test_validate_department_slots_passes_when_all_declared(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    loader.validate_department_slots(
        "secretary", expected=["chat.system", "chat.welcome"]
    )


def test_validate_department_slots_raises_on_missing(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    with pytest.raises(PromptSlotNotFound, match="chat.nope"):
        loader.validate_department_slots(
            "secretary", expected=["chat.system", "chat.nope"]
        )


def test_loader_caches_yaml_parse(prompts_dir: Path, monkeypatch) -> None:
    loader = PromptLoader(root=prompts_dir)
    loader.render("secretary", "chat.welcome", user_name="A")

    # Corrupt the file on disk; cached render should still succeed.
    (prompts_dir / "secretary.yaml").write_text("not: valid: yaml: at all")
    out = loader.render("secretary", "chat.welcome", user_name="B")
    assert "Hello B." in out


def test_rendered_string_is_jinja2_safe_for_json_values(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    (prompts_dir / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              data:
                user: |
                  {{ blob | tojson }}
            """
        )
    )
    # Force cache invalidation by constructing a fresh loader.
    loader = PromptLoader(root=prompts_dir)
    out = loader.render("equity_research", "report.data.user", blob={"k": "v"})
    assert '{"k": "v"}' in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_prompts.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the prompt loader**

Create `packages/core/src/openlia/llm/runtime/prompts.py`:

```python
"""Per-department YAML prompt loader.

Each department has `<department_id>.yaml` under a prompts root. Leaf
string values are Jinja2 templates — shared snippets live under
`shared/*.yaml.j2` and are available via `{% include %}`.

Slot paths are dot-joined nested-dict keys, e.g. `"chat.system"` or
`"report.stock_initiation.user"`. `PromptSlotNotFound` is raised both
when the YAML file is missing and when the slot doesn't resolve to a
string.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


class PromptSlotNotFound(Exception):
    """Raised when a requested (department_id, slot) does not resolve."""


def _default_prompts_root() -> Path:
    """Resolve the `openlia.prompts` package directory as a filesystem Path."""
    root = resources.files("openlia.prompts")
    # `resources.files` returns a MultiplexedPath or PosixPath; cast via str.
    return Path(str(root))


class PromptLoader:
    """Loads and renders prompt slots for a department.

    Construct once per process (or once per test). YAML parse results are
    cached in-memory; edits on disk after first access are invisible.
    """

    def __init__(self, *, root: Path | None = None) -> None:
        self._root = root if root is not None else _default_prompts_root()
        self._env = Environment(
            loader=FileSystemLoader(str(self._root)),
            autoescape=select_autoescape(
                enabled_extensions=(),  # plain text, no escaping
                default=False,
            ),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        self._cache: dict[str, dict[str, Any]] = {}

    def _load(self, department_id: str) -> dict[str, Any]:
        if department_id in self._cache:
            return self._cache[department_id]
        path = self._root / f"{department_id}.yaml"
        if not path.exists():
            raise PromptSlotNotFound(
                f"Prompt file not found for department '{department_id}': {path}"
            )
        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            raise PromptSlotNotFound(
                f"Prompt file for '{department_id}' must be a mapping, got {type(data).__name__}"
            )
        self._cache[department_id] = data
        return data

    def _resolve_slot(self, data: dict[str, Any], slot: str) -> str:
        node: Any = data
        for part in slot.split("."):
            if not isinstance(node, dict) or part not in node:
                raise PromptSlotNotFound(slot)
            node = node[part]
        if not isinstance(node, str):
            raise PromptSlotNotFound(
                f"Slot '{slot}' resolved to {type(node).__name__}, expected str"
            )
        return node

    def render(self, department_id: str, slot: str, **context: Any) -> str:
        """Render a slot with the provided context. Raises PromptSlotNotFound."""
        try:
            data = self._load(department_id)
            template_src = self._resolve_slot(data, slot)
        except PromptSlotNotFound as exc:
            raise PromptSlotNotFound(
                f"{department_id}:{slot} — {exc}"
            ) from None
        template = self._env.from_string(template_src)
        return template.render(**context)

    def validate_department_slots(
        self, department_id: str, *, expected: list[str]
    ) -> None:
        """Startup-time check: every expected slot exists. Raises on the first miss."""
        data = self._load(department_id)
        for slot in expected:
            self._resolve_slot(data, slot)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_prompts.py -v`
Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/prompts.py
uv run ruff format packages/core/src/openlia/llm/runtime/prompts.py \
                   packages/core/tests/test_llm/test_runtime/test_prompts.py
git add packages/core/src/openlia/llm/runtime/prompts.py \
        packages/core/tests/test_llm/test_runtime/test_prompts.py
git commit -m "phase-5(runtime): prompt YAML loader + Jinja2 rendering with shared includes"
```

---

## Task 6: Author department prompt YAMLs + shared includes

**Files (all under `packages/core/src/openlia/prompts/`):**
- Create: `shared/voice.yaml.j2`
- Create: `shared/output_discipline.yaml.j2`
- Create: `secretary.yaml`
- Create: `equity_research.yaml`
- Create: `earnings_update.yaml`
- Create: `morning_briefing.yaml`
- Create: `macro_research.yaml` (batch slot only)
- Create: `retail_sentiment.yaml` (batch slot only)
- Create: `packages/core/tests/test_llm/test_runtime/test_prompt_contents.py` — startup validation that every department declares its expected slots.

These are v1 authoring stubs. They are intentionally concise; each department plan (13–16, 19, 20) will refine its own YAML with production-grade voice. The goal of this task is:

1. Every slot the runtime code (ChatRunner, ReportRunner, BatchRunner) will reference resolves.
2. Shared includes work end-to-end.
3. A CI-time validation test catches typos before a user-facing call fails.

- [ ] **Step 1: Write the shared includes**

Create `packages/core/src/openlia/prompts/shared/voice.yaml.j2`:

```jinja2
Write in a clear, professional tone.
Prefer short sentences over long ones.
Cite every number to its source endpoint when reporting data.
Never guess a ticker or company name — ask, or call the search tool.
```

Create `packages/core/src/openlia/prompts/shared/output_discipline.yaml.j2`:

```jinja2
Output discipline:
- Follow the requested output format exactly. No extra commentary before or after.
- If the user asks for a report, fill the provided schema. Leave instruction-only fields empty.
- When data is missing, state it plainly. Do not fabricate numbers.
- When unsure, call `find_more_data` with a plain-language description.
```

- [ ] **Step 2: Author `secretary.yaml`**

Create `packages/core/src/openlia/prompts/secretary.yaml`:

```yaml
chat:
  system: |
    You are the Secretary for OpenLIA — a general-purpose assistant to an
    investor. You answer free-form questions, handle meta requests
    ("save this report to the repository"), and route to other departments
    only when the user asks.

    You have access to data tools for quotes, news, company profiles, and
    more. When a user asks a factual question, call the relevant tool;
    never answer from memory for time-sensitive facts.

    {% include "shared/voice.yaml.j2" %}
    {% include "shared/output_discipline.yaml.j2" %}
```

- [ ] **Step 3: Author `equity_research.yaml`**

Create `packages/core/src/openlia/prompts/equity_research.yaml`:

```yaml
chat:
  system: |
    You are the Equity Research analyst. In chat mode you answer
    follow-up questions about tickers, sectors, and prior reports.

    {% include "shared/voice.yaml.j2" %}

report:
  system: |
    You are the Equity Research analyst drafting a professional report.
    Follow the style guide below exactly. Fill the framework schema.

    --- STYLE GUIDE ---
    {{ style_guide }}
    --- END STYLE GUIDE ---

    {% include "shared/output_discipline.yaml.j2" %}

  stock_initiation:
    user: |
      Generate a Stock Initiation Report for {{ user_input }}.

      Apply these customizations:
      - Enabled sections: {{ enabled_sections | join(', ') if enabled_sections else 'all' }}
      - Custom sections: {{ custom_sections | tojson }}
      - Length preference: {{ length }}

      Call data tools as needed to collect financials, analyst views,
      recent news, and any other inputs the framework requests.

      --- FRAMEWORK ---
      {{ framework | tojson(indent=2) }}
      --- END FRAMEWORK ---

  stock_update:
    user: |
      Generate a Stock Update Report for {{ user_input }}.
      Focus on what has changed since the last coverage turn: new
      filings, price action, earnings, analyst revisions, macro context.

      - Enabled sections: {{ enabled_sections | join(', ') if enabled_sections else 'all' }}
      - Custom sections: {{ custom_sections | tojson }}
      - Length preference: {{ length }}

      --- FRAMEWORK ---
      {{ framework | tojson(indent=2) }}
      --- END FRAMEWORK ---

  sector_research:
    user: |
      Generate a Sector Research Report for {{ user_input }}.
      Cover competitive dynamics, key players, regulation, demand
      drivers, and risks.

      - Enabled sections: {{ enabled_sections | join(', ') if enabled_sections else 'all' }}
      - Custom sections: {{ custom_sections | tojson }}
      - Length preference: {{ length }}

      --- FRAMEWORK ---
      {{ framework | tojson(indent=2) }}
      --- END FRAMEWORK ---
```

- [ ] **Step 4: Author `earnings_update.yaml`**

Create `packages/core/src/openlia/prompts/earnings_update.yaml`:

```yaml
report:
  system: |
    You are the Earnings Update analyst. Produce a scorecard-focused
    post-earnings report: beat/miss on headline metrics, guidance
    changes, thesis check, analyst reaction.

    --- STYLE GUIDE ---
    {{ style_guide }}
    --- END STYLE GUIDE ---

    {% include "shared/output_discipline.yaml.j2" %}

  earnings_update:
    user: |
      Produce an Earnings Update for {{ user_input }}.

      Use the earnings-calendar and financial-statements tools to pull
      the latest quarter. Compare against the prior quarter and the
      consensus estimate. Highlight guidance changes verbatim.

      - Enabled sections: {{ enabled_sections | join(', ') if enabled_sections else 'all' }}
      - Custom sections: {{ custom_sections | tojson }}
      - Length preference: {{ length }}

      --- FRAMEWORK ---
      {{ framework | tojson(indent=2) }}
      --- END FRAMEWORK ---
```

- [ ] **Step 5: Author `morning_briefing.yaml`**

Create `packages/core/src/openlia/prompts/morning_briefing.yaml`:

```yaml
report:
  system: |
    You are the Morning Briefing analyst. Produce a daily pre-open
    briefing covering market overview, portfolio-relevant news, macro
    context, and any custom sections the user defined.

    --- STYLE GUIDE ---
    {{ style_guide }}
    --- END STYLE GUIDE ---

    {% include "shared/output_discipline.yaml.j2" %}

  morning_briefing:
    user: |
      Generate today's Morning Briefing.

      Standard sections (use unless excluded): market overview,
      portfolio-relevant news, macro context, upcoming earnings,
      sector rotation, notable analyst actions, key risks.

      - Enabled sections: {{ enabled_sections | join(', ') if enabled_sections else 'all' }}
      - Custom sections: {{ custom_sections | tojson }}
      - Length preference: {{ length }}
      - Reference portfolio: {{ reference_portfolio | tojson if reference_portfolio else 'none' }}

      --- FRAMEWORK ---
      {{ framework | tojson(indent=2) }}
      --- END FRAMEWORK ---
```

- [ ] **Step 6: Author `macro_research.yaml` (batch only)**

Create `packages/core/src/openlia/prompts/macro_research.yaml`:

```yaml
batch:
  t4_assessment:
    system: |
      You are a Macro Research analyst scoring one framework question.

      {% include "shared/output_discipline.yaml.j2" %}
    user: |
      Question: {{ question }}
      Framework: {{ framework_name }}
      Live data bundle:
      {{ data_bundle | tojson(indent=2) }}

      Return a JSON object matching the response schema with fields:
      - score (integer 0-100)
      - justification (concise paragraph)
      - citations (list of data-source identifiers you relied on)

  t5_assessment:
    system: |
      You are a Macro Research analyst synthesizing a composite
      regime assessment from Tier-4 sub-scores.

      {% include "shared/output_discipline.yaml.j2" %}
    user: |
      Framework: {{ framework_name }}
      Tier-4 sub-scores:
      {{ sub_scores | tojson(indent=2) }}

      Return a JSON object matching the response schema.
```

- [ ] **Step 7: Author `retail_sentiment.yaml` (batch only)**

Create `packages/core/src/openlia/prompts/retail_sentiment.yaml`:

```yaml
batch:
  classify_sentiment:
    system: |
      You classify a single social media post's sentiment toward a
      ticker. Return strict JSON matching the response schema.

      Sentiment is one of: bullish, bearish, neutral.
      Confidence is a float in [0.0, 1.0].

      {% include "shared/output_discipline.yaml.j2" %}
    user: |
      Ticker: {{ ticker }}
      Source: {{ source }}
      Post text:
      ---
      {{ text }}
      ---

      Classify this post's sentiment toward {{ ticker }}.
```

- [ ] **Step 8: Write the prompt-contents validation test**

Create `packages/core/tests/test_llm/test_runtime/test_prompt_contents.py`:

```python
"""Startup-time validation that every department declares its expected slots.

Keeps prompt typos loud: if someone renames `report.stock_initiation.user` to
`report.stock_initiation.user_prompt` without updating ReportRunner, this test
fails in CI instead of failing a user's report generation at runtime.
"""
from __future__ import annotations

import pytest

from openlia.llm.runtime.prompts import PromptLoader, PromptSlotNotFound

EXPECTED: dict[str, list[str]] = {
    "secretary": ["chat.system"],
    "equity_research": [
        "chat.system",
        "report.system",
        "report.stock_initiation.user",
        "report.stock_update.user",
        "report.sector_research.user",
    ],
    "earnings_update": [
        "report.system",
        "report.earnings_update.user",
    ],
    "morning_briefing": [
        "report.system",
        "report.morning_briefing.user",
    ],
    "macro_research": [
        "batch.t4_assessment.system",
        "batch.t4_assessment.user",
        "batch.t5_assessment.system",
        "batch.t5_assessment.user",
    ],
    "retail_sentiment": [
        "batch.classify_sentiment.system",
        "batch.classify_sentiment.user",
    ],
}


@pytest.mark.parametrize("department_id,slots", list(EXPECTED.items()))
def test_every_department_declares_expected_slots(
    department_id: str, slots: list[str]
) -> None:
    loader = PromptLoader()  # default root: openlia.prompts
    loader.validate_department_slots(department_id, expected=slots)


def test_shared_include_voice_is_rendered_into_secretary_system() -> None:
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system")
    assert "clear, professional tone" in out


def test_shared_include_output_discipline_is_rendered_into_report_system() -> None:
    loader = PromptLoader()
    out = loader.render("equity_research", "report.system", style_guide="x")
    assert "Output discipline" in out


def test_missing_slot_surfaces_prompt_slot_not_found() -> None:
    loader = PromptLoader()
    with pytest.raises(PromptSlotNotFound):
        loader.render("secretary", "report.system")
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_prompt_contents.py -v`
Expected: all pass. If a department YAML is missing a slot listed in `EXPECTED`, the test names it — fix the YAML and re-run.

- [ ] **Step 10: Lint + commit**

```bash
uv run ruff check packages/core/tests/test_llm/test_runtime/test_prompt_contents.py
uv run ruff format packages/core/tests/test_llm/test_runtime/test_prompt_contents.py
git add packages/core/src/openlia/prompts/shared/ \
        packages/core/src/openlia/prompts/secretary.yaml \
        packages/core/src/openlia/prompts/equity_research.yaml \
        packages/core/src/openlia/prompts/earnings_update.yaml \
        packages/core/src/openlia/prompts/morning_briefing.yaml \
        packages/core/src/openlia/prompts/macro_research.yaml \
        packages/core/src/openlia/prompts/retail_sentiment.yaml \
        packages/core/tests/test_llm/test_runtime/test_prompt_contents.py
git commit -m "phase-5(runtime): author v1 department prompt YAMLs + shared includes + slot validation"
```

---

## Task 7: `web_search.py` — native-first, configured-fallback resolution

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/web_search.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_web_search.py`

Resolution per call (per spec §Web Search):

```
1. resolved_model.capabilities.web_search_native is True → use native
2. else if a configured search adapter is available → use configured
3. else → web_search unavailable (has_web_search=False)
```

The runtime doesn't know how to build Plan 3's search adapters itself — the server hands in a `search_adapter_factory` callable (`() -> WebSearchAdapter | None`). This keeps the core layer free of HTTP-client wiring for a specific search provider.

Return shapes are normalized: both native and configured variants produce `list[WebSearchResult]` with `title`, `url`, `snippet` fields. The LLM sees identical text either way.

- [ ] **Step 1: Write the failing web-search tests**

Create `packages/core/tests/test_llm/test_runtime/test_web_search.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import pytest

from openlia.llm.runtime.web_search import (
    WebSearchAdapter,
    WebSearchResolution,
    WebSearchResult,
    resolve_web_search,
)
from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel, ModelTier

pytestmark = pytest.mark.asyncio


def _resolved(*, web_search_native: bool) -> ResolvedModel:
    return ResolvedModel(
        provider_kind="openai",
        provider_id="p1",
        model_id="m1",
        model_ref="gpt-5.4",
        tier=ModelTier.EVERYDAY,
        credentials=ProviderCredentials(api_key="sk", base_url=None),
        capabilities=Capabilities(
            streaming=True,
            tool_calling=True,
            structured_output=True,
            vision=False,
            web_search_native=web_search_native,
        ),
        overrides={},
    )


@dataclass
class _FakeAdapter:
    name: str = "brave"
    will_return: list[WebSearchResult] | None = None

    async def search(self, query: str) -> list[WebSearchResult]:
        if self.will_return is None:
            return [WebSearchResult(title=f"Result for {query}", url="https://x", snippet="s")]
        return self.will_return


async def test_native_preferred_when_available() -> None:
    resolution = resolve_web_search(
        resolved=_resolved(web_search_native=True),
        search_adapter_factory=lambda: _FakeAdapter(),
    )
    assert resolution.available is True
    assert resolution.variant == "native"
    assert resolution.adapter is None


async def test_falls_back_to_configured_when_native_unavailable() -> None:
    adapter = _FakeAdapter(name="tavily")
    resolution = resolve_web_search(
        resolved=_resolved(web_search_native=False),
        search_adapter_factory=lambda: adapter,
    )
    assert resolution.available is True
    assert resolution.variant == "configured"
    assert resolution.adapter is adapter


async def test_unavailable_when_no_native_and_no_configured() -> None:
    resolution = resolve_web_search(
        resolved=_resolved(web_search_native=False),
        search_adapter_factory=lambda: None,
    )
    assert resolution.available is False
    assert resolution.variant is None
    assert resolution.adapter is None


async def test_configured_adapter_search_returns_normalized_results() -> None:
    adapter = _FakeAdapter(
        will_return=[WebSearchResult(title="T", url="https://u", snippet="S")]
    )
    results = await adapter.search("AAPL earnings")
    assert results[0].title == "T"
    assert results[0].url == "https://u"
    assert results[0].snippet == "S"


async def test_web_search_adapter_protocol_accepts_any_async_callable() -> None:
    class _Custom:
        async def search(self, query: str) -> list[WebSearchResult]:
            return [WebSearchResult(title=query, url="https://q", snippet="")]

    a: WebSearchAdapter = _Custom()
    out = await a.search("x")
    assert out[0].title == "x"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_web_search.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the web-search module**

Create `packages/core/src/openlia/llm/runtime/web_search.py`:

```python
"""Web search resolution.

The runtime sees web search through one abstraction: `WebSearchResolution`
with `available`, `variant` ("native" | "configured"), and an optional
`adapter`. When `native`, the tool is handed to the provider via
`LLMRequest.tools` with a provider-specific name (the adapter layer
recognizes `web_search` and swaps in the native tool). When `configured`,
`ToolDispatcher.dispatch()` calls `adapter.search(query)`.

The server layer builds the adapter factory from the `search` data-provider
category (Brave / Tavily / Serper / You.com) and passes it in. The runtime
never reads DB state directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Protocol, runtime_checkable

from openlia.llm.types import ResolvedModel


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


@runtime_checkable
class WebSearchAdapter(Protocol):
    """Structural contract for a configured web-search provider."""

    async def search(self, query: str) -> list[WebSearchResult]: ...


@dataclass(frozen=True)
class WebSearchResolution:
    available: bool
    variant: Literal["native", "configured"] | None
    adapter: WebSearchAdapter | None


def resolve_web_search(
    *,
    resolved: ResolvedModel,
    search_adapter_factory: Callable[[], WebSearchAdapter | None],
) -> WebSearchResolution:
    """Pick native-first, then configured, then unavailable."""
    if resolved.capabilities.web_search_native:
        return WebSearchResolution(available=True, variant="native", adapter=None)
    adapter = search_adapter_factory()
    if adapter is not None:
        return WebSearchResolution(available=True, variant="configured", adapter=adapter)
    return WebSearchResolution(available=False, variant=None, adapter=None)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_web_search.py -v`
Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/web_search.py
uv run ruff format packages/core/src/openlia/llm/runtime/web_search.py \
                   packages/core/tests/test_llm/test_runtime/test_web_search.py
git add packages/core/src/openlia/llm/runtime/web_search.py \
        packages/core/tests/test_llm/test_runtime/test_web_search.py
git commit -m "phase-5(runtime): web-search resolution (native-first, configured-fallback) + adapter Protocol"
```

---

## Task 8: `tools.py` — ToolDispatcher

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/tools.py`
- Create: `packages/core/tests/test_llm/test_runtime/_fakes.py` (shared fakes imported by Tasks 8/9/10/11 tests)
- Create: `packages/core/tests/test_llm/test_runtime/conftest.py` (sys.path helper so `_fakes` is importable)
- Create: `packages/core/tests/test_llm/test_runtime/test_tools.py`

> **Note on test imports.** The repo runs pytest with `--import-mode=importlib` and no package `__init__.py` files under `tests/`. To let sibling test files share helper classes, the pattern used below is: put the helpers in `_fakes.py`, have `conftest.py` insert the test directory into `sys.path`, and import via `from _fakes import FakeProvider`. Tasks 9, 10, 11 re-use the same `_fakes` module.

ToolDispatcher responsibilities:

1. **`build(department_id, has_web_search)`** — load the department's tool mapping file, produce `ToolSchema` entries per mapped requirement, always append `find_more_data`, conditionally append `web_search`.
2. **`dispatch(call)`** — route by `call.name`:
   - Mapped-requirement name → delegate to the injected `DataProviderDispatcher` Protocol.
   - `find_more_data` → delegate to the injected catalog-search callable (Plan 3 owns the Quick-tier LLM call; dispatcher accepts a result for now).
   - `web_search` → if the resolution was `configured`, call `adapter.search()`; if `native`, this should never reach the dispatcher (the provider handles it on their side).
3. **Parallel dispatch** — `dispatch_many(calls)` runs all provided calls with `asyncio.gather` so providers that emit multiple tool calls per turn get single-round-trip dispatching.
4. **Response normalization** — every tool result passes through `_normalize(payload, max_array_len=50)` which drops nulls and caps arrays with a `"truncated": true` sentinel.
5. **Summary formatting** — each tool owns a `summary(result) -> str` formatter registered at construction time. Raw payloads never cross to the SSE stream; only the summary.

The tool-mapping file format (Plan 3's output) is consumed here as a dict with this shape:

```yaml
# example: ~/.openlia/mappings/equity_research.yaml
tools:
  - name: stock_quote
    description: Real-time stock quote for a ticker.
    parameters:
      type: object
      properties:
        symbol: {type: string, description: "Ticker symbol"}
      required: [symbol]
    provider_priority: [eodhd, fmp]  # informational; the DataProviderDispatcher already knows this
```

- [ ] **Step 1a: Write `conftest.py` (sys.path helper only)**

Create `packages/core/tests/test_llm/test_runtime/conftest.py`:

```python
"""Ensure `_fakes.py` (sibling module with shared helper classes) is importable.

Pytest runs with --import-mode=importlib and no package __init__.py files,
so sibling test files cannot import each other by package path. This
conftest puts the current directory on sys.path so `from _fakes import X`
works inside every test module in this folder.
"""
from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
```

- [ ] **Step 1b: Write the shared test fakes (`_fakes.py`)**

Create `packages/core/tests/test_llm/test_runtime/_fakes.py`:

```python
"""Shared fakes for runtime tests: FakeProvider, FakeDataDispatcher, FakeSearchAdapter."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.web_search import WebSearchResult
from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ProviderCredentials,
    TestResult,
    ToolCall,
)


@dataclass
class FakeProviderScript:
    """Declarative description of what FakeProvider should yield.

    Entries correspond to one provider turn each. Each entry is either:
      - ("text", "...") — yield a single LLMChunk with that text
      - ("tokens", ["Apple", " sold"]) — yield one LLMChunk per token
      - ("tool_calls", [ToolCall(...), ...]) — yield a synthetic tool-calling
         LLMResponse (via generate) as the final result of this turn
      - ("final", "text", {"finish_reason": "stop", ...}) — emit final text
         and stop the stream.
    """

    turns: list[tuple[str, Any]] = field(default_factory=list)


class FakeProvider(LLMProvider):
    kind = "fake"

    def __init__(
        self,
        *,
        credentials: ProviderCredentials | None = None,
        model: str = "fake-1",
        capabilities: Capabilities | None = None,
        script: FakeProviderScript | None = None,
    ) -> None:
        super().__init__(
            credentials=credentials or ProviderCredentials(api_key="k", base_url=None),
            model=model,
            capabilities=capabilities or Capabilities(
                streaming=True, tool_calling=True, structured_output=True
            ),
        )
        self._script = script or FakeProviderScript()
        self._turn_index = 0
        self.captured_requests: list[LLMRequest] = []

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=self.model, display_name=self.model, context_window=8192)]

    async def test_connection(self, model: str) -> TestResult:
        return TestResult(ok=True, latency_ms=1, error_class=None, error_msg=None)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.captured_requests.append(request)
        kind, payload = self._script.turns[self._turn_index]
        self._turn_index += 1
        if kind == "tool_calls":
            return LLMResponse(
                text="",
                finish_reason="tool_calls",
                input_tokens=0,
                output_tokens=0,
                tool_calls=list(payload),
            )
        if kind == "final_json":
            return LLMResponse(
                text=payload,
                finish_reason="stop",
                input_tokens=0,
                output_tokens=0,
                tool_calls=[],
            )
        if kind == "final":
            return LLMResponse(
                text=payload,
                finish_reason="stop",
                input_tokens=0,
                output_tokens=0,
                tool_calls=[],
            )
        raise AssertionError(f"unknown turn kind {kind}")

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        self.captured_requests.append(request)
        kind, payload = self._script.turns[self._turn_index]
        self._turn_index += 1
        if kind == "tokens":
            for t in payload:
                yield LLMChunk(delta=t, finish_reason=None)
            yield LLMChunk(delta="", finish_reason="stop")
            return
        if kind == "tool_calls":
            yield LLMChunk(delta="", finish_reason="tool_calls")
            # Tool calls are surfaced via generate's LLMResponse; stream signals via finish_reason.
            return
        if kind == "text":
            yield LLMChunk(delta=payload, finish_reason="stop")
            return
        raise AssertionError(f"unknown stream turn {kind}")


@dataclass
class FakeDataDispatcher:
    """Implements the DataProviderDispatcher Protocol used by ToolDispatcher."""

    manifest: dict[str, dict[str, Any]] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    raise_for: set[str] = field(default_factory=set)

    async def list_requirement_tools(
        self, department_id: str
    ) -> list[dict[str, Any]]:
        return list(self.manifest.get(department_id, {}).values())

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_name in self.raise_for:
            raise RuntimeError(f"provider blew up for {tool_name}")
        return self.results.get(tool_name, {"tool": tool_name, "args": arguments})

    async def find_more_data(
        self, *, department_id: str, description: str
    ) -> dict[str, Any] | None:
        return self.results.get(f"expand::{description}")


@dataclass
class FakeSearchAdapter:
    results: list[WebSearchResult] = field(default_factory=list)

    async def search(self, query: str) -> list[WebSearchResult]:
        return self.results or [
            WebSearchResult(title=f"Result for {query}", url="https://x", snippet="")
        ]
```

- [ ] **Step 2: Write the failing tool-dispatcher tests**

Create `packages/core/tests/test_llm/test_runtime/test_tools.py`:

```python
from __future__ import annotations

import asyncio

import pytest

from openlia.llm.runtime.tools import (
    ToolCallResult,
    ToolDispatcher,
)
from openlia.llm.runtime.web_search import WebSearchResolution, WebSearchResult
from openlia.llm.types import ToolCall, ToolSchema

from _fakes import FakeDataDispatcher, FakeSearchAdapter

pytestmark = pytest.mark.asyncio

_MANIFEST = {
    "equity_research": {
        "stock_quote": {
            "name": "stock_quote",
            "description": "Real-time stock quote for a ticker.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
        "financial_statements": {
            "name": "financial_statements",
            "description": "Latest 10-K/10-Q filings.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    }
}


async def test_build_returns_mapping_tools_plus_find_more_data() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    tools = await disp.build("equity_research", has_web_search=False)
    names = [t.name for t in tools]
    assert "stock_quote" in names
    assert "financial_statements" in names
    assert "find_more_data" in names
    assert "web_search" not in names


async def test_build_appends_web_search_when_available() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(
            available=True, variant="configured", adapter=FakeSearchAdapter()
        ),
    )
    tools = await disp.build("equity_research", has_web_search=True)
    assert "web_search" in [t.name for t in tools]


async def test_build_omits_web_search_even_if_has_flag_when_unavailable() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    tools = await disp.build("equity_research", has_web_search=True)
    assert "web_search" not in [t.name for t in tools]


async def test_dispatch_requirement_tool_returns_ok_result() -> None:
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={"stock_quote": {"symbol": "AAPL", "price": 190.5}},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
    )
    assert isinstance(result, ToolCallResult)
    assert result.ok is True
    assert result.payload == {"symbol": "AAPL", "price": 190.5}
    assert "AAPL" in result.summary


async def test_dispatch_requirement_tool_surfaces_failure_as_ok_false() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST, raise_for={"stock_quote"})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
    )
    assert result.ok is False
    assert "Failed" in result.summary


async def test_dispatch_find_more_data_hit_adds_tool_for_next_turn() -> None:
    new_tool = {
        "name": "options_chain",
        "description": "Options chain",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    }
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={"expand::options chain": new_tool},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    before = await disp.build("equity_research", has_web_search=False)
    assert "options_chain" not in [t.name for t in before]

    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c1", name="find_more_data", arguments={"description": "options chain"}
        ),
    )
    assert result.ok is True
    after = await disp.build("equity_research", has_web_search=False)
    assert "options_chain" in [t.name for t in after]


async def test_dispatch_find_more_data_miss_returns_ok_false() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c1", name="find_more_data", arguments={"description": "nonsense data"}
        ),
    )
    assert result.ok is False
    assert "not available" in result.summary.lower() or "no match" in result.summary.lower()


async def test_dispatch_web_search_configured_calls_adapter() -> None:
    adapter = FakeSearchAdapter(
        results=[WebSearchResult(title="AAPL news", url="https://u", snippet="...")]
    )
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(True, "configured", adapter),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="web_search", arguments={"query": "AAPL earnings"}),
    )
    assert result.ok is True
    assert result.payload["results"][0]["title"] == "AAPL news"


async def test_dispatch_many_runs_in_parallel() -> None:
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={
            "stock_quote": {"symbol": "AAPL", "price": 1},
            "financial_statements": {"symbol": "AAPL", "filings": []},
        },
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    results = await disp.dispatch_many(
        department_id="equity_research",
        calls=[
            ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
            ToolCall(id="c2", name="financial_statements", arguments={"symbol": "AAPL"}),
        ],
    )
    assert len(results) == 2
    assert all(r.ok for r in results)
    assert [r.call_id for r in results] == ["c1", "c2"]


async def test_response_normalization_caps_arrays() -> None:
    from openlia.llm.runtime.tools import _normalize_payload

    big = {"items": list(range(100)), "nullable": None, "ok": True}
    out = _normalize_payload(big, max_array_len=10)
    assert len(out["items"]) == 10
    assert out["truncated"] is True
    assert "nullable" not in out
    assert out["ok"] is True


async def test_response_normalization_leaves_small_arrays_alone() -> None:
    from openlia.llm.runtime.tools import _normalize_payload

    out = _normalize_payload({"items": [1, 2, 3]}, max_array_len=10)
    assert out == {"items": [1, 2, 3]}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_tools.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement the tool dispatcher**

Create `packages/core/src/openlia/llm/runtime/tools.py`:

```python
"""Tool dispatcher: build the tool list + route calls.

Three sources:
  1. Mapped requirement tools — loaded from DataProviderDispatcher
     (which reads ~/.openlia/mappings/<department>.yaml).
  2. `find_more_data` meta-tool — always present when any data tools exist.
  3. `web_search` — present only when resolve_web_search() returned available.

Dispatch:
  - Routes by call.name; unknown names get ok=False.
  - `dispatch_many` runs parallel tool calls with asyncio.gather.
  - Response payloads pass through `_normalize_payload` (nulls dropped,
    arrays capped). Summaries are one-line human strings suitable for SSE.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import ToolCall, ToolSchema

_FIND_MORE_DATA_SCHEMA = ToolSchema(
    name="find_more_data",
    description=(
        "Search all configured data providers for an endpoint matching a "
        "description. If found, the endpoint becomes available as a new tool "
        "you can call in a follow-up turn."
    ),
    parameters={
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Plain-language description of the data you need.",
            }
        },
        "required": ["description"],
    },
)

_WEB_SEARCH_SCHEMA = ToolSchema(
    name="web_search",
    description="Search the web for recent information not covered by configured data providers.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)


@runtime_checkable
class DataProviderDispatcher(Protocol):
    """Plan 3 implements this.

    `list_requirement_tools(department_id)` returns the mapped-tool entries
    from `~/.openlia/mappings/<department>.yaml` (name/description/parameters).

    `dispatch_requirement(tool_name, arguments)` invokes the winning data
    provider for this requirement and returns its normalized JSON payload.

    `find_more_data(department_id, description)` runs the Quick-tier LLM
    catalog search; returns a mapping-tool entry on hit, None on miss.
    """

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]: ...

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def find_more_data(
        self, *, department_id: str, description: str
    ) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class ToolCallResult:
    """Dispatcher output. `summary` is UI-ready; `payload` goes back to the LLM."""

    call_id: str
    ok: bool
    summary: str
    payload: dict[str, Any]


def _normalize_payload(payload: Any, *, max_array_len: int = 50) -> dict[str, Any]:
    """Strip nulls, cap arrays, convert recursively. Marks truncation."""
    if not isinstance(payload, dict):
        return {"value": payload}
    out: dict[str, Any] = {}
    truncated = False
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, list) and len(v) > max_array_len:
            out[k] = v[:max_array_len]
            truncated = True
        else:
            out[k] = v
    if truncated:
        out["truncated"] = True
    return out


def _short_args(arguments: dict[str, Any], *, max_len: int = 80) -> str:
    import json

    try:
        text = json.dumps(arguments, separators=(",", ":"))
    except (TypeError, ValueError):
        text = str(arguments)
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def _summarize_requirement(tool_name: str, arguments: dict[str, Any]) -> str:
    for key in ("symbol", "ticker", "query", "name"):
        if key in arguments:
            return f"Fetched {tool_name} for {arguments[key]}"
    return f"Fetched {tool_name}"


class ToolDispatcher:
    def __init__(
        self,
        *,
        data_dispatcher: DataProviderDispatcher,
        web_search: WebSearchResolution,
    ) -> None:
        self._data = data_dispatcher
        self._web_search = web_search
        self._expanded: dict[str, list[ToolSchema]] = {}  # per-department

    async def build(
        self, department_id: str, *, has_web_search: bool
    ) -> list[ToolSchema]:
        mapped_raw = await self._data.list_requirement_tools(department_id)
        mapped: list[ToolSchema] = [
            ToolSchema(
                name=entry["name"],
                description=entry["description"],
                parameters=entry["parameters"],
            )
            for entry in mapped_raw
        ]
        mapped.extend(self._expanded.get(department_id, []))
        tools: list[ToolSchema] = list(mapped)

        if mapped:
            tools.append(_FIND_MORE_DATA_SCHEMA)
        if has_web_search and self._web_search.available:
            tools.append(_WEB_SEARCH_SCHEMA)
        return tools

    async def dispatch(
        self, *, department_id: str, call: ToolCall
    ) -> ToolCallResult:
        name = call.name
        if name == "find_more_data":
            return await self._dispatch_find_more_data(department_id, call)
        if name == "web_search":
            return await self._dispatch_web_search(call)
        return await self._dispatch_requirement(call)

    async def dispatch_many(
        self, *, department_id: str, calls: list[ToolCall]
    ) -> list[ToolCallResult]:
        coros = [self.dispatch(department_id=department_id, call=c) for c in calls]
        return await asyncio.gather(*coros)

    async def _dispatch_requirement(self, call: ToolCall) -> ToolCallResult:
        try:
            payload = await self._data.dispatch_requirement(
                tool_name=call.name, arguments=call.arguments
            )
        except Exception as exc:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"Failed to fetch {call.name}: {exc!s}",
                payload={"error": str(exc)},
            )
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=_summarize_requirement(call.name, call.arguments),
            payload=_normalize_payload(payload),
        )

    async def _dispatch_find_more_data(
        self, department_id: str, call: ToolCall
    ) -> ToolCallResult:
        description = str(call.arguments.get("description", ""))
        try:
            entry = await self._data.find_more_data(
                department_id=department_id, description=description
            )
        except Exception as exc:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"find_more_data failed: {exc!s}",
                payload={"error": str(exc)},
            )
        if entry is None:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"No matching endpoint available for '{description}'",
                payload={"found": False},
            )
        schema = ToolSchema(
            name=entry["name"],
            description=entry["description"],
            parameters=entry["parameters"],
        )
        self._expanded.setdefault(department_id, []).append(schema)
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=f"Added tool: {schema.name}",
            payload={"added_tool": schema.name, "found": True},
        )

    async def _dispatch_web_search(self, call: ToolCall) -> ToolCallResult:
        if not self._web_search.available or self._web_search.variant != "configured":
            # Native variant should never arrive here — the provider handles it.
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary="web_search unavailable",
                payload={"error": "web_search not available"},
            )
        adapter = self._web_search.adapter
        assert adapter is not None  # available + configured => adapter present
        query = str(call.arguments.get("query", ""))
        try:
            results = await adapter.search(query)
        except Exception as exc:
            return ToolCallResult(
                call_id=call.id,
                ok=False,
                summary=f"web_search failed: {exc!s}",
                payload={"error": str(exc)},
            )
        return ToolCallResult(
            call_id=call.id,
            ok=True,
            summary=f"Searched the web for: {query}",
            payload={
                "results": [
                    {"title": r.title, "url": r.url, "snippet": r.snippet}
                    for r in results
                ]
            },
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_tools.py -v`
Expected: all pass.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/tools.py \
                  packages/core/tests/test_llm/test_runtime/conftest.py \
                  packages/core/tests/test_llm/test_runtime/_fakes.py \
                  packages/core/tests/test_llm/test_runtime/test_tools.py
uv run ruff format packages/core/src/openlia/llm/runtime/tools.py \
                   packages/core/tests/test_llm/test_runtime/conftest.py \
                   packages/core/tests/test_llm/test_runtime/_fakes.py \
                   packages/core/tests/test_llm/test_runtime/test_tools.py
git add packages/core/src/openlia/llm/runtime/tools.py \
        packages/core/tests/test_llm/test_runtime/conftest.py \
        packages/core/tests/test_llm/test_runtime/_fakes.py \
        packages/core/tests/test_llm/test_runtime/test_tools.py
git commit -m "phase-5(runtime): ToolDispatcher (build + dispatch + parallel + response normalization)"
```

---

## Task 9: `chat.py` — ChatRunner

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/chat.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_chat.py`

ChatRunner sequence per `run()` call:

1. Emit `ChatStart(message_id)`.
2. Call `resolve(department_id, registry, user_id)`; on `TierNotConfiguredError` or any other `LLMProviderError`, emit `ChatError` and return.
3. Instantiate a provider via `provider_factory(resolved)` (injected — Plan 4's registry returns the factory).
4. Resolve web search via `resolve_web_search()`.
5. Build tool list via `ToolDispatcher.build(department_id, has_web_search=True)`.
6. Render `chat.system` slot via `PromptLoader`.
7. Loop:
   a. Call `provider.generate(LLMRequest(...))` or `provider.stream(...)` depending on whether tools are in flight.
   b. If tool calls returned, emit `ChatToolCallStart` per call, dispatch in parallel, emit `ChatToolCallResult` per result, append tool-result messages to the conversation, loop.
   c. If final text: stream tokens via `provider.stream()`, emit `ChatToken` per chunk, then `ChatDone(stop_reason="complete")`.
8. Between yields, check `cancel_token.is_cancelled`; if flipped, stop yielding.

For v1, we simplify the chat loop to **always use `generate()`** for tool-calling turns and **only use `stream()`** for the final text turn. This matches how every Plan 4 adapter stubs `generate` and `stream` separately.

- [ ] **Step 1: Write the failing ChatRunner tests**

Create `packages/core/tests/test_llm/test_runtime/test_chat.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from openlia.llm.exceptions import TierNotConfiguredError
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
)
from openlia.llm.runtime.messages import ChatMessage
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)

from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript

pytestmark = pytest.mark.asyncio


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    root.mkdir()
    (root / "secretary.yaml").write_text(
        dedent(
            """\
            chat:
              system: You are the Secretary.
            """
        )
    )
    return root


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        tier=ModelTier.EVERYDAY,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True, tool_calling=True, structured_output=True
        ),
        overrides={},
    )


class _Registry:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises

    def get_department_tier_override(self, department_id: str):
        return None

    def get_user_preference(self, user_id, tier):
        return None

    def get_tier_default(self, tier):
        return None

    def get_any_in_tier(self, tier):
        return None


def _always_resolved(*, resolved: ResolvedModel):
    def _resolve(*, department_id, user_id, registry, tier_override=None):
        return resolved

    return _resolve


def _always_raises():
    def _resolve(*, department_id, user_id, registry, tier_override=None):
        raise TierNotConfiguredError("everyday")

    return _resolve


async def _collect(it):
    return [e async for e in it]


async def test_streams_simple_reply_with_no_tools(prompts_root: Path) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[("tokens", ["Hi", " there"])]))
    data = FakeDataDispatcher(manifest={"secretary": {}})
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
            messages=[ChatMessage(role="user", content="hello")],
        )
    )
    types = [type(e) for e in events]
    assert types[0] is ChatStart
    assert ChatToken in types
    assert types[-1] is ChatDone
    tokens = [e.text for e in events if isinstance(e, ChatToken)]
    assert "".join(tokens) == "Hi there"


async def test_tool_calling_turn_emits_tool_events(prompts_root: Path) -> None:
    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("tokens", ["AAPL", " is", " up"]),
            ]
        )
    )
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Stock quote",
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
        results={"stock_quote": {"symbol": "AAPL", "price": 190}},
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
            messages=[ChatMessage(role="user", content="AAPL?")],
        )
    )
    types = [type(e) for e in events]
    assert ChatToolCallStart in types
    assert ChatToolCallResult in types
    assert ChatDone in types


async def test_tier_not_configured_emits_chat_error_and_stops(prompts_root: Path) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[]))
    data = FakeDataDispatcher(manifest={"secretary": {}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_raises(),
        registry=_Registry(raises=True),
        provider_factory=lambda resolved: provider,
        message_id_factory=lambda: "m_1",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )
    types = [type(e) for e in events]
    assert types == [ChatStart, ChatError]
    err = events[-1]
    assert isinstance(err, ChatError)
    assert err.error_class == "TierNotConfiguredError"
    assert "everyday" in err.message


async def test_cancellation_stops_yielding_without_terminal_event(
    prompts_root: Path,
) -> None:
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("tokens", ["A", "B", "C", "D", "E"])])
    )
    data = FakeDataDispatcher(manifest={"secretary": {}})
    token = CancellationToken()
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
    events: list[Any] = []
    async for e in runner.run(
        department_id="secretary",
        user_id="u_1",
        messages=[ChatMessage(role="user", content="hi")],
        cancel_token=token,
    ):
        events.append(e)
        if isinstance(e, ChatToken) and e.text == "B":
            token.cancel()
    assert ChatDone not in [type(e) for e in events]
    assert ChatError not in [type(e) for e in events]
    tokens_seen = [e.text for e in events if isinstance(e, ChatToken)]
    assert "E" not in tokens_seen


async def test_user_message_includes_prior_history(prompts_root: Path) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[("tokens", ["ok"])]))
    data = FakeDataDispatcher(manifest={"secretary": {}})
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
    await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[
                ChatMessage(role="user", content="hi"),
                ChatMessage(role="assistant", content="hello"),
                ChatMessage(role="user", content="what's up?"),
            ],
        )
    )
    req = provider.captured_requests[0]
    contents = [m.content for m in req.messages]
    assert contents == ["hi", "hello", "what's up?"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_chat.py -v`
Expected: `ModuleNotFoundError: No module named 'openlia.llm.runtime.chat'`.

- [ ] **Step 3: Implement ChatRunner**

Create `packages/core/src/openlia/llm/runtime/chat.py`:

```python
"""ChatRunner — multi-turn chat with tool calls and token streaming.

Loop contract:
  - chat.start
  - while True:
      request the model; if it returns tool calls, emit tool events,
      dispatch, append tool-result messages, loop.
      if it returns text, stream tokens and emit chat.done.
  - chat.error on any LLMProviderError (including TierNotConfiguredError).

Cancellation: poll cancel_token between yields; stop yielding with no
terminal event when flipped.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Callable

from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
    SseEvent,
)
from openlia.llm.runtime.messages import Attachment, ChatMessage
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolCallResult, ToolDispatcher
from openlia.llm.types import (
    LLMRequest,
    Message,
    ModelTier,
    ResolvedModel,
)

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


class ChatRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        tools: ToolDispatcher,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
        message_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._prompts = prompts
        self._tools = tools
        self._resolve = resolve
        self._registry = registry
        self._provider_factory = provider_factory
        self._message_id_factory = message_id_factory or (lambda: f"m_{uuid.uuid4().hex[:12]}")

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages: list[ChatMessage],
        attachments: list[Attachment] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> AsyncIterator[SseEvent]:
        message_id = self._message_id_factory()
        yield ChatStart(message_id=message_id)

        try:
            resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
            )
        except LLMProviderError as exc:
            yield ChatError(
                message_id=message_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        provider = self._provider_factory(resolved)
        system = self._prompts.render(department_id, "chat.system")
        tools = await self._tools.build(department_id, has_web_search=True)

        conversation = [Message(role=m.role, content=m.content) for m in messages]

        # Tool loop — up to 10 rounds to stop runaway expansions.
        for _ in range(10):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            try:
                response = await provider.generate(
                    LLMRequest(
                        messages=conversation,
                        system=system,
                        tools=tools or None,
                        max_tokens=2048,
                    )
                )
            except LLMProviderError as exc:
                yield ChatError(
                    message_id=message_id,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return

            if not response.tool_calls:
                break

            # Emit start events, dispatch in parallel, emit result events.
            for call in response.tool_calls:
                yield ChatToolCallStart(
                    message_id=message_id,
                    call_id=call.id,
                    tool_name=call.name,
                    args_preview=json.dumps(call.arguments, separators=(",", ":"))[:120],
                )
            results: list[ToolCallResult] = await self._tools.dispatch_many(
                department_id=department_id, calls=response.tool_calls
            )
            for r in results:
                yield ChatToolCallResult(
                    message_id=message_id,
                    call_id=r.call_id,
                    ok=r.ok,
                    summary=r.summary,
                )
            # Append tool-result messages to the conversation for the next turn.
            for r in results:
                conversation.append(
                    Message(role="tool", content=json.dumps(r.payload))
                )
            tools = await self._tools.build(department_id, has_web_search=True)

        # Final text turn — stream tokens.
        if cancel_token is not None and cancel_token.is_cancelled:
            return
        try:
            async for chunk in provider.stream(
                LLMRequest(
                    messages=conversation,
                    system=system,
                    max_tokens=2048,
                )
            ):
                if cancel_token is not None and cancel_token.is_cancelled:
                    return
                if chunk.delta:
                    yield ChatToken(message_id=message_id, text=chunk.delta)
        except LLMProviderError as exc:
            yield ChatError(
                message_id=message_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        if cancel_token is not None and cancel_token.is_cancelled:
            return
        yield ChatDone(message_id=message_id, stop_reason="complete")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_chat.py -v`
Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/chat.py
uv run ruff format packages/core/src/openlia/llm/runtime/chat.py \
                   packages/core/tests/test_llm/test_runtime/test_chat.py
git add packages/core/src/openlia/llm/runtime/chat.py \
        packages/core/tests/test_llm/test_runtime/test_chat.py
git commit -m "phase-5(runtime): ChatRunner (tool loop + token streaming + cancellation + error mapping)"
```

---

## Task 10: `report.py` — ReportRunner

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_report.py`

ReportRunner maps a `ReportRequest` into a report-generation flow:

1. `report.start` with `section_titles` derived from the framework JSON (after applying enabled/custom-section customizations).
2. `report.phase("fetching_data")`.
3. Tool-call loop: request the LLM (with tools), emit `report.tool_call` per tool result, dispatch, feed results back, repeat until no more tool calls.
4. `report.phase("writing")`.
5. Final structured-output turn: call `generate()` with `response_format=ResponseFormat(kind="json_schema", json_schema=<framework-as-schema>)`.
6. `report.phase("finalizing")`.
7. Parse the response JSON into a plain dict. Emit `report.complete(schema=...)` with the full structured object.

Framework / style-guide loading uses `importlib.resources` to read the JSON + markdown from `openlia.reports.frameworks`. User customizations are applied:

- `enabled_sections` — if non-empty, drop framework sections whose `id`/`slug` is not in this list.
- `custom_sections` — append to framework sections verbatim.
- `length` — write into a top-level `length_preference` key the LLM is told to honor.

On `LLMProviderError` → emit `report.error(error_class=..., message=...)`, return.
On cancellation → stop yielding without a terminal event.

- [ ] **Step 1: Write the failing ReportRunner tests**

Create `packages/core/tests/test_llm/test_runtime/test_report.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from openlia.llm.exceptions import CapabilityError, TierNotConfiguredError
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    ReportToolCall,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)

from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript

pytestmark = pytest.mark.asyncio


@pytest.fixture
def frameworks_root(tmp_path: Path) -> Path:
    root = tmp_path / "frameworks"
    root.mkdir()
    (root / "stock_initiation.json").write_text(
        json.dumps(
            {
                "title": "Stock Initiation",
                "sections": [
                    {"id": "overview", "title": "Overview", "instructions": "..."},
                    {"id": "thesis", "title": "Thesis", "instructions": "..."},
                    {"id": "risks", "title": "Risks", "instructions": "..."},
                ],
            }
        )
    )
    (root / "stock_initiation_style_guide.md").write_text(
        "# Style\nProfessional tone.\n"
    )
    return root


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    shared = root / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("discipline.\n")
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              stock_initiation:
                user: |
                  Topic: {{ user_input }}
                  Framework: {{ framework | tojson }}
            """
        )
    )
    return root


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        tier=ModelTier.THINKING,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True, tool_calling=True, structured_output=True
        ),
        overrides={},
    )


class _Registry:
    def get_department_tier_override(self, department_id: str):
        return None

    def get_user_preference(self, user_id, tier):
        return None

    def get_tier_default(self, tier):
        return None

    def get_any_in_tier(self, tier):
        return None


def _always(resolved):
    def _r(*, department_id, user_id, registry, tier_override=None):
        return resolved

    return _r


def _raises(exc):
    def _r(*, department_id, user_id, registry, tier_override=None):
        raise exc

    return _r


async def _collect(it):
    return [e async for e in it]


async def test_report_run_emits_start_phases_and_complete(
    prompts_root: Path, frameworks_root: Path
) -> None:
    filled = {"title": "AAPL Initiation", "sections": [{"id": "overview", "body": "..."}]}
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final_json", json.dumps(filled))])
    )
    data = FakeDataDispatcher(manifest={"equity_research": {}})
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
    kinds = [type(e) for e in events]
    assert kinds[0] is ReportStart
    assert ReportPhase in kinds
    phases = [e.phase for e in events if isinstance(e, ReportPhase)]
    assert phases[:3] == ["fetching_data", "writing", "finalizing"]
    assert isinstance(events[-1], ReportComplete)
    assert events[-1].schema["title"] == "AAPL Initiation"


async def test_report_start_includes_section_titles_after_filter(
    prompts_root: Path, frameworks_root: Path
) -> None:
    filled = {"title": "x", "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final_json", json.dumps(filled))])
    )
    data = FakeDataDispatcher(manifest={"equity_research": {}})
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
            request=ReportRequest(
                mode="stock_initiation",
                user_input="AAPL",
                enabled_sections=["overview", "thesis"],
            ),
        )
    )
    start = events[0]
    assert isinstance(start, ReportStart)
    assert start.section_titles == ["Overview", "Thesis"]


async def test_report_tool_loop_emits_tool_events(
    prompts_root: Path, frameworks_root: Path
) -> None:
    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    filled = {"title": "x", "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
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
        manifest=manifest, results={"stock_quote": {"symbol": "AAPL", "price": 190}}
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
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert any(isinstance(e, ReportToolCall) for e in events)


async def test_report_tier_not_configured_emits_report_error(
    prompts_root: Path, frameworks_root: Path
) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[]))
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_raises(TierNotConfiguredError("thinking")),
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
    assert events[-1].error_class == "TierNotConfiguredError"


async def test_report_capability_error_terminates(
    prompts_root: Path, frameworks_root: Path
) -> None:
    class _FailingProvider(FakeProvider):
        async def generate(self, request):
            raise CapabilityError("no structured output")

    provider = _FailingProvider()
    data = FakeDataDispatcher(manifest={"equity_research": {}})
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
    assert events[-1].error_class == "CapabilityError"


async def test_report_cancellation_stops_yielding(
    prompts_root: Path, frameworks_root: Path
) -> None:
    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final_json", "{}"),
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
    data = FakeDataDispatcher(manifest=manifest)
    token = CancellationToken()
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
    collected: list[Any] = []
    async for e in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        cancel_token=token,
    ):
        collected.append(e)
        if isinstance(e, ReportToolCall):
            token.cancel()
    types = [type(e) for e in collected]
    assert ReportComplete not in types
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement ReportRunner**

Create `packages/core/src/openlia/llm/runtime/report.py`:

```python
"""ReportRunner — single-pass structured report generation.

Flow per run():
  report.start
  → report.phase("fetching_data")
    → tool loop until the LLM returns no more tool calls
      (emit report.tool_call per dispatched tool)
  → report.phase("writing")
    → one structured-output turn (response_format=json_schema)
  → report.phase("finalizing")
  → report.complete(schema=parsed_json)

On LLMProviderError: report.error, stop.
On cancellation: stop yielding, no terminal event.
"""
from __future__ import annotations

import copy
import json
import uuid
from collections.abc import AsyncIterator
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    ReportToolCall,
    SseEvent,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResponseFormat,
    ResolvedModel,
)

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


def _default_frameworks_root() -> Path:
    return Path(str(resources.files("openlia.reports.frameworks")))


def _load_framework(frameworks_root: Path, mode: str) -> dict[str, Any]:
    path = frameworks_root / f"{mode}.json"
    return json.loads(path.read_text())


def _load_style_guide(frameworks_root: Path, mode: str) -> str:
    path = frameworks_root / f"{mode}_style_guide.md"
    return path.read_text() if path.exists() else ""


def _customize_framework(framework: dict[str, Any], request: ReportRequest) -> dict[str, Any]:
    fw = copy.deepcopy(framework)
    sections = fw.get("sections", [])
    if request.enabled_sections:
        wanted = set(request.enabled_sections)
        sections = [s for s in sections if s.get("id") in wanted]
    for custom in request.custom_sections:
        sections.append(dict(custom))
    fw["sections"] = sections
    fw["length_preference"] = request.length
    return fw


def _section_titles(framework: dict[str, Any]) -> list[str]:
    return [
        s.get("title", s.get("id", "Section"))
        for s in framework.get("sections", [])
    ]


class ReportRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        tools: ToolDispatcher,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
        frameworks_root: Path | None = None,
        report_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._prompts = prompts
        self._tools = tools
        self._resolve = resolve
        self._registry = registry
        self._provider_factory = provider_factory
        self._frameworks_root = (
            frameworks_root if frameworks_root is not None else _default_frameworks_root()
        )
        self._report_id_factory = report_id_factory or (
            lambda: f"r_{uuid.uuid4().hex[:12]}"
        )

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
        cancel_token: CancellationToken | None = None,
    ) -> AsyncIterator[SseEvent]:
        report_id = self._report_id_factory()

        framework_raw = _load_framework(self._frameworks_root, request.mode)
        framework = _customize_framework(framework_raw, request)
        style_guide = _load_style_guide(self._frameworks_root, request.mode)

        yield ReportStart(
            report_id=report_id,
            department=department_id,
            mode=request.mode,
            section_titles=_section_titles(framework),
        )

        try:
            resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
            )
        except LLMProviderError as exc:
            yield ReportError(
                report_id=report_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        provider = self._provider_factory(resolved)

        system = self._prompts.render(
            department_id, "report.system", style_guide=style_guide
        )
        user = self._prompts.render(
            department_id,
            f"report.{request.mode}.user",
            user_input=request.user_input,
            framework=framework,
            length=request.length,
            enabled_sections=request.enabled_sections,
            custom_sections=request.custom_sections,
        )

        conversation = [Message(role="user", content=user)]
        tools = await self._tools.build(department_id, has_web_search=True)

        yield ReportPhase(report_id=report_id, phase="fetching_data")

        for _ in range(10):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            try:
                response = await provider.generate(
                    LLMRequest(
                        messages=conversation,
                        system=system,
                        tools=tools or None,
                        max_tokens=2048,
                    )
                )
            except LLMProviderError as exc:
                yield ReportError(
                    report_id=report_id,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return
            if not response.tool_calls:
                break
            results = await self._tools.dispatch_many(
                department_id=department_id, calls=response.tool_calls
            )
            for r in results:
                yield ReportToolCall(
                    report_id=report_id,
                    tool_name=_tool_name_for_result(response, r.call_id),
                    summary=r.summary,
                )
                conversation.append(
                    Message(role="tool", content=json.dumps(r.payload))
                )
            tools = await self._tools.build(department_id, has_web_search=True)

        yield ReportPhase(report_id=report_id, phase="writing")
        if cancel_token is not None and cancel_token.is_cancelled:
            return

        try:
            final = await provider.generate(
                LLMRequest(
                    messages=conversation,
                    system=system,
                    response_format=ResponseFormat(
                        kind="json_schema", json_schema=framework
                    ),
                    max_tokens=4096,
                )
            )
        except LLMProviderError as exc:
            yield ReportError(
                report_id=report_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        yield ReportPhase(report_id=report_id, phase="finalizing")
        if cancel_token is not None and cancel_token.is_cancelled:
            return

        try:
            schema_payload = json.loads(final.text) if final.text else {}
        except json.JSONDecodeError as exc:
            yield ReportError(
                report_id=report_id,
                error_class="RuntimeError",
                message=f"LLM returned non-JSON response: {exc!s}",
            )
            return

        yield ReportComplete(report_id=report_id, schema=schema_payload)


def _tool_name_for_result(response, call_id: str) -> str:
    for call in response.tool_calls:
        if call.id == call_id:
            return call.name
    return "unknown"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report.py -v`
Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/report.py
uv run ruff format packages/core/src/openlia/llm/runtime/report.py \
                   packages/core/tests/test_llm/test_runtime/test_report.py
git add packages/core/src/openlia/llm/runtime/report.py \
        packages/core/tests/test_llm/test_runtime/test_report.py
git commit -m "phase-5(runtime): ReportRunner (framework/style-guide injection + phase events + structured-output)"
```

---

## Task 11: `batch.py` — BatchRunner

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/batch.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_batch.py`

BatchRunner is non-streaming: given a department + task name + items + pydantic schema, it calls the LLM in parallel bounded by `asyncio.Semaphore(concurrency)`. Per-item failures become `BatchResult(ok=False, error=...)` — one bad item never sinks the batch. No tool calling. Prompts come from `batch.<task>.system` / `batch.<task>.user` slots.

- [ ] **Step 1: Write the failing BatchRunner tests**

Create `packages/core/tests/test_llm/test_runtime/test_batch.py`:

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from textwrap import dedent
from typing import Any, Literal

import pytest
from pydantic import BaseModel

from openlia.llm.exceptions import ContextLengthError, TierNotConfiguredError
from openlia.llm.runtime.batch import BatchRunner
from openlia.llm.runtime.messages import BatchItem
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.types import (
    Capabilities,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
)

from _fakes import FakeProvider, FakeProviderScript

pytestmark = pytest.mark.asyncio


class SentimentResult(BaseModel):
    sentiment: Literal["bullish", "bearish", "neutral"]
    confidence: float


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    shared = root / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("return json.\n")
    (root / "retail_sentiment.yaml").write_text(
        dedent(
            """\
            batch:
              classify_sentiment:
                system: classify.
                user: |
                  Ticker: {{ ticker }}
                  Text: {{ text }}
            """
        )
    )
    return root


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        tier=ModelTier.QUICK,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=False, structured_output=True),
        overrides={},
    )


class _Registry:
    def get_department_tier_override(self, department_id: str): return None
    def get_user_preference(self, user_id, tier): return None
    def get_tier_default(self, tier): return None
    def get_any_in_tier(self, tier): return None


def _always(resolved):
    def _r(*, department_id, user_id, registry, tier_override=None):
        return resolved
    return _r


def _raises(exc):
    def _r(*, department_id, user_id, registry, tier_override=None):
        raise exc
    return _r


async def test_batch_runs_all_items_ok(prompts_root: Path) -> None:
    # Need one turn per item since each item is a fresh generate().
    def provider_factory(resolved):
        return FakeProvider(
            script=FakeProviderScript(
                turns=[
                    ("final_json", json.dumps({"sentiment": "bullish", "confidence": 0.9})),
                    ("final_json", json.dumps({"sentiment": "bearish", "confidence": 0.8})),
                    ("final_json", json.dumps({"sentiment": "neutral", "confidence": 0.5})),
                ]
            )
        )
    # Provider factory is called once; the single provider serves all items sequentially.
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=provider_factory,
    )
    items = [
        BatchItem(id=f"p{i}", context={"ticker": "AAPL", "text": t})
        for i, t in enumerate(["to the moon", "drop the bag", "meh"])
    ]
    results = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=2,
    )
    assert [r.id for r in results] == ["p0", "p1", "p2"]
    assert all(r.ok for r in results)
    assert results[0].data["sentiment"] == "bullish"
    assert results[1].data["sentiment"] == "bearish"


async def test_batch_surfaces_per_item_failure_without_sinking_batch(
    prompts_root: Path,
) -> None:
    class _PartiallyFailingProvider(FakeProvider):
        def __init__(self):
            super().__init__(
                script=FakeProviderScript(
                    turns=[
                        ("final_json", json.dumps({"sentiment": "bullish", "confidence": 0.9})),
                        ("final_json", json.dumps({"sentiment": "neutral", "confidence": 0.5})),
                    ]
                )
            )
            self._calls = 0

        async def generate(self, request):
            self._calls += 1
            if self._calls == 2:
                raise ContextLengthError("too long", limit=1000)
            return await super().generate(request)

    provider = _PartiallyFailingProvider()
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
    )
    items = [
        BatchItem(id="ok", context={"ticker": "AAPL", "text": "a"}),
        BatchItem(id="bad", context={"ticker": "AAPL", "text": "b"}),
        BatchItem(id="ok2", context={"ticker": "AAPL", "text": "c"}),
    ]
    results = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=1,
    )
    by_id = {r.id: r for r in results}
    assert by_id["ok"].ok is True
    assert by_id["bad"].ok is False
    assert "ContextLengthError" in by_id["bad"].error
    assert by_id["ok2"].ok is True


async def test_batch_tier_not_configured_fails_every_item(prompts_root: Path) -> None:
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_raises(TierNotConfiguredError("quick")),
        registry=_Registry(),
        provider_factory=lambda r: FakeProvider(),
    )
    items = [
        BatchItem(id="p0", context={"ticker": "AAPL", "text": "a"}),
        BatchItem(id="p1", context={"ticker": "AAPL", "text": "b"}),
    ]
    results = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=2,
    )
    assert all(r.ok is False for r in results)
    assert all("TierNotConfiguredError" in r.error for r in results)


async def test_batch_concurrency_is_bounded(prompts_root: Path) -> None:
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    class _Counting(FakeProvider):
        def __init__(self):
            super().__init__(
                script=FakeProviderScript(
                    turns=[("final_json", json.dumps({"sentiment": "neutral", "confidence": 0.1}))] * 10
                )
            )

        async def generate(self, request):
            nonlocal in_flight, peak
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            try:
                await asyncio.sleep(0.02)
                return await super().generate(request)
            finally:
                async with lock:
                    in_flight -= 1

    provider = _Counting()
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
    )
    items = [
        BatchItem(id=f"p{i}", context={"ticker": "AAPL", "text": f"t{i}"})
        for i in range(10)
    ]
    await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=3,
    )
    assert peak <= 3


async def test_batch_rejects_invalid_json_as_per_item_error(prompts_root: Path) -> None:
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final_json", "not json at all")])
    )
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
    )
    items = [BatchItem(id="p0", context={"ticker": "AAPL", "text": "a"})]
    results = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=1,
    )
    assert results[0].ok is False
    assert "JSON" in results[0].error or "validation" in results[0].error.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_batch.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement BatchRunner**

Create `packages/core/src/openlia/llm/runtime/batch.py`:

```python
"""BatchRunner — bounded-concurrency structured classification.

Non-streaming. No tool calls. One LLM call per item. `asyncio.Semaphore`
bounds in-flight calls. Per-item exceptions are captured and surfaced
as BatchResult(ok=False, error=...) — the batch always completes.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.messages import BatchItem, BatchResult
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ResponseFormat,
)

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


class BatchRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
    ) -> None:
        self._prompts = prompts
        self._resolve = resolve
        self._registry = registry
        self._provider_factory = provider_factory

    async def run(
        self,
        *,
        department_id: str,
        task: str,
        items: list[BatchItem],
        schema: type[BaseModel],
        concurrency: int = 8,
        user_id: str | None = None,
    ) -> list[BatchResult]:
        # Resolve once. If the tier isn't configured, every item reports it.
        try:
            resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
            )
        except LLMProviderError as exc:
            msg = f"{type(exc).__name__}: {exc!s}"
            return [BatchResult(id=it.id, ok=False, data=None, error=msg) for it in items]

        provider = self._provider_factory(resolved)
        system_slot = f"batch.{task}.system"
        user_slot = f"batch.{task}.user"
        system = self._prompts.render(department_id, system_slot)

        sema = asyncio.Semaphore(concurrency)
        response_format = ResponseFormat(
            kind="json_schema", json_schema=schema.model_json_schema()
        )

        async def _one(item: BatchItem) -> BatchResult:
            async with sema:
                user = self._prompts.render(department_id, user_slot, **item.context)
                try:
                    response = await provider.generate(
                        LLMRequest(
                            messages=[Message(role="user", content=user)],
                            system=system,
                            response_format=response_format,
                            max_tokens=1024,
                        )
                    )
                except LLMProviderError as exc:
                    return BatchResult(
                        id=item.id,
                        ok=False,
                        data=None,
                        error=f"{type(exc).__name__}: {exc!s}",
                    )
                try:
                    raw = json.loads(response.text or "{}")
                except json.JSONDecodeError as exc:
                    return BatchResult(
                        id=item.id, ok=False, data=None, error=f"JSON parse: {exc!s}"
                    )
                try:
                    validated = schema.model_validate(raw).model_dump()
                except ValidationError as exc:
                    return BatchResult(
                        id=item.id,
                        ok=False,
                        data=None,
                        error=f"schema validation: {exc!s}",
                    )
                return BatchResult(id=item.id, ok=True, data=validated, error=None)

        return await asyncio.gather(*(_one(item) for item in items))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_batch.py -v`
Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/batch.py
uv run ruff format packages/core/src/openlia/llm/runtime/batch.py \
                   packages/core/tests/test_llm/test_runtime/test_batch.py
git add packages/core/src/openlia/llm/runtime/batch.py \
        packages/core/tests/test_llm/test_runtime/test_batch.py
git commit -m "phase-5(runtime): BatchRunner (bounded concurrency + per-item failure isolation + pydantic validation)"
```

---

## Task 12: Public exports, README update, acceptance sweep

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/__init__.py`
- Modify: `planning/implementation-plans/README.md` (status column for Plan 5)

- [ ] **Step 1: Populate runtime public exports**

Replace `packages/core/src/openlia/llm/runtime/__init__.py`:

```python
"""LLM runtime — public exports.

Server routes depend on these names. Do not rename without coordinated
changes in `openlia_server.routes.*` and the department-plan tests.
"""
from __future__ import annotations

from openlia.llm.runtime.batch import BatchRunner
from openlia.llm.runtime.cancellation import CancellationToken, await_with_grace
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatReportThumbnail,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    ReportToolCall,
    SseEvent,
    to_wire,
)
from openlia.llm.runtime.messages import (
    Attachment,
    BatchItem,
    BatchResult,
    ChatMessage,
    ReportRequest,
)
from openlia.llm.runtime.prompts import PromptLoader, PromptSlotNotFound
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import (
    DataProviderDispatcher,
    ToolCallResult,
    ToolDispatcher,
)
from openlia.llm.runtime.web_search import (
    WebSearchAdapter,
    WebSearchResolution,
    WebSearchResult,
    resolve_web_search,
)

__all__ = [
    "Attachment",
    "BatchItem",
    "BatchResult",
    "BatchRunner",
    "CancellationToken",
    "ChatDone",
    "ChatError",
    "ChatMessage",
    "ChatReportThumbnail",
    "ChatRunner",
    "ChatStart",
    "ChatToken",
    "ChatToolCallResult",
    "ChatToolCallStart",
    "DataProviderDispatcher",
    "PromptLoader",
    "PromptSlotNotFound",
    "ReportComplete",
    "ReportError",
    "ReportPhase",
    "ReportRequest",
    "ReportRunner",
    "ReportStart",
    "ReportToolCall",
    "SseEvent",
    "ToolCallResult",
    "ToolDispatcher",
    "WebSearchAdapter",
    "WebSearchResolution",
    "WebSearchResult",
    "await_with_grace",
    "resolve_web_search",
    "to_wire",
]
```

- [ ] **Step 2: Run the full core test suite**

Run: `uv run pytest packages/core/tests/ -v`
Expected: every test in `test_llm/test_runtime/*`, `test_llm/test_*` (from Plan 4), and any other core test already in the repo passes. If a Plan 4 fixture exports (`resolve`, `ResolvedModel`, etc.) shifted meaning after Plan 4 was executed, update imports rather than working around them.

- [ ] **Step 3: Ruff sweep**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime packages/core/src/openlia/prompts
uv run ruff format --check packages/core/src/openlia/llm/runtime packages/core/src/openlia/prompts
```

Expected: no lint or format drift.

- [ ] **Step 4: Fresh-import smoke check**

Run:

```bash
uv run python -c "
from openlia.llm.runtime import (
    BatchRunner, ChatRunner, ReportRunner,
    ChatMessage, ReportRequest, BatchItem,
    PromptLoader, ToolDispatcher, CancellationToken,
    resolve_web_search,
)
print('runtime import ok')
"
```

Expected output: `runtime import ok`. This confirms the core wheel layout still works without any server-package import.

- [ ] **Step 5: Core-vs-server boundary check**

Run:

```bash
uv run python -c "
import sys
import openlia.llm.runtime  # noqa: F401
assert 'fastapi' not in sys.modules, 'core runtime must not pull in FastAPI'
assert 'sqlalchemy' not in sys.modules, 'core runtime must not pull in SQLAlchemy'
assert 'openlia_server' not in sys.modules, 'core runtime must not import the server package'
print('boundary ok')
"
```

Expected output: `boundary ok`. If this fails, walk the import chain from `openlia.llm.runtime.*` until you find the offending import and relocate it.

- [ ] **Step 6: Update the implementation-plans README**

Edit `planning/implementation-plans/README.md`, replacing the Plan 5 row:

```markdown
| 5 | 2 | LLM runtime (runners, prompt loader, SSE) | Draft | `2026-04-17-phase-5-llm-runtime.md` |
```

- [ ] **Step 7: Commit the exports + README update**

```bash
git add packages/core/src/openlia/llm/runtime/__init__.py \
        planning/implementation-plans/README.md
git commit -m "phase-5(runtime): public exports + mark plan draft in roadmap"
```

- [ ] **Step 8: Self-review checklist**

Re-read `planning/specs/systems/llm-runtime-design.md` one more time. For each in-scope bullet, confirm a task delivers it:

- [x] Three runners under `llm/runtime/` — Tasks 9, 10, 11.
- [x] `ChatRunner`, `ReportRunner`, `BatchRunner` interfaces — Tasks 9, 10, 11.
- [x] Per-department YAML prompts with Jinja2 — Tasks 5, 6.
- [x] Framework + style-guide injection into ReportRunner — Task 10.
- [x] Tool schema construction (requirement tools + `find_more_data` + `web_search`) — Task 8.
- [x] `chat.*` / `report.*` SSE taxonomy — Task 3.
- [x] Native-first / configured-fallback web search — Task 7.
- [x] Cancellation driven by client disconnect + 2s grace — Task 4, wired in Tasks 9/10.
- [x] `TierNotConfiguredError` → terminal `*.error` event — Tasks 9, 10, 11.
- [x] Framework + style-guide physical move — Task 1.
- [x] Parallel tool calls (asyncio.gather) — Task 8, exercised in Tasks 9/10.
- [x] Response normalization (drop nulls, cap arrays) — Task 8.
- [x] No streaming of structured report output — Task 10 (single generate() call after writing phase).
- [x] Tool-dispatch failure stays in-stream (ok=false, not terminal) — Task 8.
- [x] BatchRunner never builds a tool list — Task 11.
- [x] Prompt slot typo validation at startup — Task 5 (`validate_department_slots`) + Task 6 test enforces every declared slot.

If any bullet is missing, add a follow-up task before moving this plan out of Draft.

---

## Notes for the executor

- **Plan 3 dependency surface.** `ToolDispatcher` speaks to Plan 3's `DataProviderDispatcher` Protocol (`list_requirement_tools`, `dispatch_requirement`, `find_more_data`). If Plan 3 ships a different name for any of these, **update the Protocol in `tools.py` to match** — do not invent a shim. This plan locks the *shape* (three methods, dict payloads, per-department scoping); Plan 3 locks the *implementation*.
- **Plan 4 import names.** This plan assumes `openlia.llm.resolver.resolve`, `openlia.llm.resolver.ModelRegistry`, and `openlia.llm.exceptions.*` match Plan 4 exactly. If Plan 4 renamed any of these during execution, stop and update this plan's imports (and the executing task), don't paper over the mismatch.
- **Prompt YAML authoring.** The v1 YAMLs (Task 6) are intentionally sparse. Each department plan (13–16, 19, 20) will tune its own prompt — the contract is that **the slots in `EXPECTED`** (Task 6 test) continue to resolve. Add new slots there first if you add new YAML keys.
- **Parallel tool calls and ordering.** Providers that don't emit multi-tool turns work unchanged (the list just has one entry). If an adapter later needs strict serial ordering for a tool, add a per-tool `serialize: True` flag rather than flipping a global.
- **Cancellation has no terminal event.** Do not emit `chat.done(stop_reason="cancelled")` on cancellation — the spec explicitly forbids it (connection is already gone). The server writes a `stopped_at` marker into the chat-session DB outside runtime scope.
- **Native web search semantics.** When `resolve_web_search` returns `variant="native"`, the dispatcher's `web_search` path should never fire because the adapter layer (Plan 4) recognizes the `web_search` tool schema name and swaps in the provider-native tool. Keep the existing safety branch (`_dispatch_web_search` returning ok=False when variant != "configured") — it is a defensive shim only.
- **Pydantic schemas in BatchRunner.** `schema.model_json_schema()` emits a JSON-schema dict; each Plan 4 adapter must accept arbitrary JSON-schema shapes in `ResponseFormat.json_schema` when `kind="json_schema"`. If an adapter instead requires a simplified subset (e.g., OpenAI strict-mode structured output), the workaround belongs in Plan 4, not here.
- **Framework packaging.** After Task 1, the framework files ship inside the core wheel. If you later need to hot-edit a framework mid-development, edit the file under `packages/core/src/openlia/reports/frameworks/` and reinstall with `uv sync` — do not create a filesystem override path.

---

## Out-of-scope deferrals (explicit)

These are explicitly **not** added to this plan even though a reviewer might expect them:

- **Streaming partial report JSON** — spec rejects this; single-pass only.
- **Custom user tools beyond the three sources** — v2 feature; this plan's ToolDispatcher has no extension hook.
- **Chat-session persistence** — server's job. Runtime is stateless.
- **Rendering the `ReportSchema` to Markdown** — Plan 13 owns this; `report.complete` just carries the schema dict.
- **Rate limiting per tool** — Plan 3's adapter layer; not here.
- **Prompt-injection defense** — prompt authors' responsibility at YAML level.
- **Automatic prompt A/B testing** — out of v1.

---

## Total tasks: 12

Tasks: 1 (scaffold + framework move), 2 (messages), 3 (events), 4 (cancellation), 5 (prompts loader), 6 (prompt YAMLs), 7 (web search), 8 (tool dispatcher), 9 (ChatRunner), 10 (ReportRunner), 11 (BatchRunner), 12 (exports + acceptance).

