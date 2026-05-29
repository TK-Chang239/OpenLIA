# Earnings Update v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a v2 Earnings Update backend on a forked v3-style engine: user-chosen model, DB-backed templates (built-in default + uploads), per-user connector toggles, watchlist, and a weekly EODHD calendar sync that schedules auto-generated reports when watchlisted tickers release earnings.

**Architecture:** A new `report_eu` core runtime is forked from `report_v3` (single tool-use loop, write_section/finalize, citation ledger, SSE-friendly events) with two earnings-specific changes: the mandatory web-search capability gate is removed (no required connectors) and the tool catalog is assembled from per-user connector toggles. New `report_eu_*` / `eu_v2_*` DB tables, services, routes, and two scheduler jobs (weekly calendar sync + hourly dispatcher) sit in the server package. Everything is additive behind `EARNINGS_ENGINE_VERSION=v2`; EU v1 is untouched as rollback.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy + Alembic, Pydantic v2, APScheduler (existing scheduler infra), EODHD SDK/helpers, pytest. Frontend is a separate later phase — out of scope here.

**Spec:** `planning/2026-05-29-earnings-update-v2-design.md`

**Conventions:**
- `uv run pytest ...` for tests, `uv run ruff check --fix . && uv run ruff format .` before each commit.
- Modern strict type hints on every signature. Fail fast, raise specific exceptions. No emojis. Positive prompt phrasing.
- Branch: `feat/earnings-update-v2-backend`. Commit after every green step.

---

## Shared contracts (defined once, referenced throughout)

These types are created in Phase 1 and reused everywhere. Names are fixed — do not rename in later tasks.

- `EnabledConnectors` (core, `report_eu/schemas.py`): `financial: bool`, `earnings_calendar: bool`, `web_search: bool`.
- `TriggerContext` (core, `report_eu/schemas.py`): `ticker: str`, `company_name: str | None`, `fiscal_period: str | None`, `report_date: str | None`, `release_timing: str | None`, `eps_estimate: str | None`, `revenue_estimate: str | None`.
- `RunRequest` (core, `report_eu/schemas.py`): `subject`, `template: TemplateSpec`, `language`, `length`, `provider_kind`, `model`, `reasoning_effort`, `enabled_connectors: EnabledConnectors`, `trigger_context: TriggerContext | None`.
- `EuDataTransports` (core, `report_eu/__init__.py`): dataclass of callables `fundamentals`, `prices`, `news`, `earnings_calendar`.
- Engine module: `packages/core/src/openlia/llm/runtime/report_eu/`.
- Tables: `report_eu`, `report_eu_sections`, `report_eu_charts`, `report_eu_citations`, `report_eu_tool_call_log`, `report_eu_templates`, `eu_v2_watchlist`, `eu_v2_earnings_schedule`, `eu_v2_settings`.
- Routes prefix: `/api/departments/earnings-update/v2`.
- JobTypes: `JobType.EU_V2_SYNC`, `JobType.EU_V2_DISPATCH`.

---

## Phase 0 — Branch + engine gate

### Task 0: Branch and env-gate helper

**Files:**
- Modify: existing git working tree (new branch)
- Create: `packages/server/src/openlia_server/routes/departments/_eu_v2_gate.py`
- Test: `packages/server/tests/test_routes/departments/test_eu_v2_gate.py`

- [ ] **Step 1: Create the branch**

```bash
git checkout -b feat/earnings-update-v2-backend
```

- [ ] **Step 2: Write the failing test**

```python
# packages/server/tests/test_routes/departments/test_eu_v2_gate.py
import os

from openlia_server.routes.departments._eu_v2_gate import eu_v2_enabled


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EARNINGS_ENGINE_VERSION", raising=False)
    assert eu_v2_enabled() is False


def test_enabled_when_v2(monkeypatch):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "v2")
    assert eu_v2_enabled() is True


def test_case_insensitive(monkeypatch):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "V2")
    assert eu_v2_enabled() is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_eu_v2_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: ..._eu_v2_gate`.

- [ ] **Step 4: Implement the gate helper**

```python
# packages/server/src/openlia_server/routes/departments/_eu_v2_gate.py
"""Env gate for the Earnings Update v2 engine.

Mirrors the v3 ``REPORT_ENGINE_VERSION=v3`` gate. EU v2 routes return
503 when disabled so v1 stays the only live Earnings Update surface
until v2 is proven.
"""

from __future__ import annotations

import os


def eu_v2_enabled() -> bool:
    """True when ``EARNINGS_ENGINE_VERSION`` equals ``v2`` (case-insensitive)."""
    return os.environ.get("EARNINGS_ENGINE_VERSION", "").strip().lower() == "v2"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_eu_v2_gate.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/routes/departments/_eu_v2_gate.py packages/server/tests/test_routes/departments/test_eu_v2_gate.py
git commit -m "feat(earnings-update-v2): add EARNINGS_ENGINE_VERSION gate helper"
```

---

## Phase 1 — `report_eu` core engine fork

The engine is forked from `report_v3`. Several files are copied near-verbatim; the connector-gating and prompt files are genuinely new. Copy first, then edit.

### Task 1: Copy the report_v3 package skeleton into report_eu

**Files:**
- Create (copy): the whole `report_eu/` tree from `report_v3/`, then prune.

- [ ] **Step 1: Copy the package**

```bash
cp -r packages/core/src/openlia/llm/runtime/report_v3 packages/core/src/openlia/llm/runtime/report_eu
```

- [ ] **Step 2: Remove files EU v2 does not use (revisions, valuation, discovery, extended)**

EU v2 has no revision flow, no valuation models, and a fixed (non-discoverable) tool set. Remove:

```bash
cd packages/core/src/openlia/llm/runtime/report_eu
rm -f tools/valuation_tools.py tools/extended_tools.py tools/find_tools.py
cd -
```

(If `report_v3` has revision-specific modules, leave the runner copy intact for now; revision wiring is edited out in Task 6.)

- [ ] **Step 3: Verify import still resolves after pruning (expected to FAIL — registry imports removed modules)**

Run: `uv run python -c "import openlia.llm.runtime.report_eu"`
Expected: FAIL — `ModuleNotFoundError` for `valuation_tools` / `extended_tools` / `find_tools` (fixed in Task 4). This confirms the prune targets are real.

- [ ] **Step 4: Commit the raw copy (broken state is fine on a feature branch; next tasks fix imports)**

```bash
git add packages/core/src/openlia/llm/runtime/report_eu
git commit -m "chore(earnings-update-v2): fork report_v3 package into report_eu (pre-edit)"
```

### Task 2: Schemas — add EnabledConnectors, TriggerContext; extend RunRequest

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/schemas.py`
- Test: `packages/core/tests/runtime/report_eu/test_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/runtime/report_eu/test_schemas.py
from openlia.llm.runtime.report_eu.schemas import (
    EnabledConnectors,
    RunRequest,
    TriggerContext,
)
from openlia.llm.runtime.report_v2_3.templates.spec import TemplateSpec


def _template() -> TemplateSpec:
    return TemplateSpec(
        template_id="eu_default",
        name="Earnings Update",
        shape_description="Post-earnings scorecard",
        ticker_anchored=True,
        default_length="normal",
        sections=[],
    )


def test_enabled_connectors_defaults():
    c = EnabledConnectors()
    assert c.financial is True
    assert c.earnings_calendar is True
    assert c.web_search is False


def test_trigger_context_minimal():
    t = TriggerContext(ticker="MSFT.US")
    assert t.ticker == "MSFT.US"
    assert t.eps_estimate is None


def test_run_request_carries_connectors_and_trigger():
    req = RunRequest(
        subject="MSFT.US Q3 FY26 earnings",
        template=_template(),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=EnabledConnectors(web_search=True),
        trigger_context=TriggerContext(ticker="MSFT.US", fiscal_period="Q3 FY26"),
    )
    assert req.enabled_connectors.web_search is True
    assert req.trigger_context.fiscal_period == "Q3 FY26"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'EnabledConnectors'`.

- [ ] **Step 3: Edit schemas.py**

In `report_eu/schemas.py`, add the two new models and rewrite `RunRequest`. Replace the v3 `RunRequest` block (the one with `attachments` / `instructions`) with:

```python
class EnabledConnectors(BaseModel):
    """Which connector tool groups the LLM may call this run.

    Per-user global toggles resolved from ``eu_v2_settings``. None are
    required — all-False yields an output-tools-only catalog and the
    model writes from the prompt and trigger context alone.
    """

    financial: bool = True
    earnings_calendar: bool = True
    web_search: bool = False


class TriggerContext(BaseModel):
    """Earnings event metadata handed to a run.

    For scheduled runs this is populated from the matched
    ``eu_v2_earnings_schedule`` row; for on-demand runs the route fills
    in what it can (ticker always; estimates when the calendar
    connector is enabled). Injected into the system prompt so the model
    knows which release it is covering before it calls any tool.
    """

    ticker: str = Field(..., min_length=1)
    company_name: str | None = None
    fiscal_period: str | None = None
    report_date: str | None = None
    release_timing: str | None = None
    eps_estimate: str | None = None
    revenue_estimate: str | None = None


class RunRequest(BaseModel):
    """Input to an Earnings Update v2 run.

    Forked from report_v3's RunRequest. Differences: no ``attachments``
    / ``instructions`` (out of scope for EU v2), and two added fields —
    ``enabled_connectors`` (which tool groups to build) and
    ``trigger_context`` (the earnings event being covered).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subject: str = Field(..., min_length=1)
    template: TemplateSpec
    language: Language = Language.EN
    length: ReportLength = ReportLength.NORMAL
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    reasoning_effort: ReasoningEffort | None = None
    enabled_connectors: EnabledConnectors = Field(default_factory=EnabledConnectors)
    trigger_context: TriggerContext | None = None
```

Add `"EnabledConnectors"` and `"TriggerContext"` to `__all__`. Remove `PriorSection`, `PriorCitation`, `ReviseContext` (revision-only) from the file and `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_schemas.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/core/src/openlia/llm/runtime/report_eu/schemas.py packages/core/tests/runtime/report_eu/test_schemas.py
git commit -m "feat(earnings-update-v2): report_eu schemas — connectors + trigger context"
```

### Task 3: Session — drop the web-search capability gate

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/session.py`
- Test: `packages/core/tests/runtime/report_eu/test_session.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/runtime/report_eu/test_session.py
from openlia.llm.runtime.report_eu.session import LLMSession


def test_create_allows_model_without_native_web_search():
    # A model lacking web_search_native must NOT raise for EU v2.
    session = LLMSession.create(
        provider_kind="ollama",
        model="llama3.1",
        capability_override={"web_search_native": False, "max_output_tokens": 4096},
    )
    assert session.provider_kind == "ollama"
    assert session.capabilities.web_search_native is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_session.py -v`
Expected: FAIL — `CapabilityError: v3 requires a model with native web search`.

- [ ] **Step 3: Edit session.py — remove the gate**

In `report_eu/session.py`, delete the `if not capabilities.web_search_native: raise CapabilityError(...)` block inside `create()` so it becomes:

```python
        capabilities = capabilities_for(
            provider_kind=provider_kind,
            model=model,
            override=capability_override,
        )
        return cls(
            provider_kind=provider_kind,
            model=model,
            capabilities=capabilities,
        )
```

Keep the `CapabilityError` class defined (other modules may import it) but update its docstring to note EU v2 does not require web search. Update the module docstring's point 2 to: "EU v2 imposes no capability gate — any model the registry knows is allowed; connectors are opt-in."

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_session.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/core/src/openlia/llm/runtime/report_eu/session.py packages/core/tests/runtime/report_eu/test_session.py
git commit -m "feat(earnings-update-v2): drop web-search capability gate in report_eu session"
```

### Task 4: Earnings-calendar data tool

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/tools/data_tools.py`
- Test: `packages/core/tests/runtime/report_eu/test_data_tools.py`

The earnings-calendar tool wraps a transport callable `earnings_calendar(ticker) -> list[dict]`, ledger-annotated like the other data tools.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/runtime/report_eu/test_data_tools.py
from openlia.llm.runtime.report_eu.ledger import CitationLedger
from openlia.llm.runtime.report_eu.tools.data_tools import build_earnings_calendar_tool


def test_earnings_calendar_tool_calls_transport_and_logs():
    ledger = CitationLedger()
    calls: list[str] = []

    def transport(ticker: str) -> list[dict]:
        calls.append(ticker)
        return [{"report_date": "2026-06-15", "estimate": "2.50"}]

    tool = build_earnings_calendar_tool(ledger=ledger, earnings_calendar=transport)
    result = tool.run({"ticker": "MSFT.US"})

    assert calls == ["MSFT.US"]
    assert "2026-06-15" in str(result)
    assert tool.descriptor.name == "get_earnings_calendar"
```

(Adapt the `tool.run(...)` call to match the actual `ResearchTool` invocation contract used by the copied `data_tools.py` — read the existing `build_data_tools` wrapper shape and mirror it exactly.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_data_tools.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_earnings_calendar_tool'`.

- [ ] **Step 3: Implement the tool in data_tools.py**

Add to `report_eu/tools/data_tools.py`, mirroring the existing fundamentals/prices/news wrapper pattern in that file (ledger entry append with `source_id`, structured-error wrapping, `ToolDescriptor` with name `get_earnings_calendar`, one required `ticker` string param). The transport type alias:

```python
from collections.abc import Callable

EarningsCalendarTransport = Callable[[str], list[dict]]
```

Implement `build_earnings_calendar_tool(*, ledger: CitationLedger, earnings_calendar: EarningsCalendarTransport) -> ResearchTool` returning a tool whose body calls `earnings_calendar(ticker)`, appends a ledger entry (`tool_name="get_earnings_calendar"`, `source_id` from the ledger's next eodhd id), and returns the payload. Follow the exact wrapper/error idiom already present for the other three data tools so the runner dispatch contract matches.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_data_tools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/core/src/openlia/llm/runtime/report_eu/tools/data_tools.py packages/core/tests/runtime/report_eu/test_data_tools.py
git commit -m "feat(earnings-update-v2): add get_earnings_calendar data tool"
```

### Task 5: Connector-gated catalog

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/tools/registry.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/__init__.py` (add `EuDataTransports`)
- Test: `packages/core/tests/runtime/report_eu/test_registry.py`

`build_catalog` now takes `enabled_connectors` and an `EuDataTransports` bundle and assembles only the toggled tool groups. Output tools are always present. No `find_tools` / extended discovery (removed in Task 1), so `ToolCatalog` drops the `discovery` / `category_index` fields and `active_*` methods collapse to the core set.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/runtime/report_eu/test_registry.py
from openlia.llm.runtime.report_eu import EuDataTransports
from openlia.llm.runtime.report_eu.ledger import CitationLedger
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors
from openlia.llm.runtime.report_eu.tools.registry import build_catalog
from openlia.llm.runtime.report_eu.workspace import RunWorkspace


def _transports() -> EuDataTransports:
    return EuDataTransports(
        fundamentals=lambda t: {},
        prices=lambda t, f, to: [],
        news=lambda t, limit: [],
        earnings_calendar=lambda t: [],
    )


def _catalog(connectors: EnabledConnectors):
    return build_catalog(
        ledger=CitationLedger(),
        workspace=RunWorkspace(template_section_ids=["quick_take"]),
        transports=_transports(),
        enabled_connectors=connectors,
    )


def test_all_off_yields_output_tools_only():
    cat = _catalog(EnabledConnectors(financial=False, earnings_calendar=False, web_search=False))
    names = set(cat.by_name())
    assert {"write_section", "finalize"} <= names
    assert "get_fundamentals" not in names
    assert "get_earnings_calendar" not in names
    assert cat.native_tools == ()


def test_financial_on_adds_data_tools():
    cat = _catalog(EnabledConnectors(financial=True, earnings_calendar=False, web_search=False))
    names = set(cat.by_name())
    assert {"get_fundamentals", "get_historical_prices", "get_company_news"} <= names
    assert "get_earnings_calendar" not in names


def test_calendar_on_adds_calendar_tool():
    cat = _catalog(EnabledConnectors(financial=False, earnings_calendar=True, web_search=False))
    assert "get_earnings_calendar" in set(cat.by_name())


def test_web_search_on_sets_native_tool():
    cat = _catalog(EnabledConnectors(financial=False, earnings_calendar=False, web_search=True))
    assert cat.native_tools == ("web_search",)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_registry.py -v`
Expected: FAIL — import error (`EuDataTransports`) / `build_catalog` signature mismatch.

- [ ] **Step 3: Add `EuDataTransports` to `report_eu/__init__.py`**

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EuDataTransports:
    """Callables the EU v2 data tools dispatch against.

    Supplied by the server wiring layer so the core package stays free
    of the EODHD SDK. ``earnings_calendar`` returns the upcoming-events
    list for a ticker.
    """

    fundamentals: Callable[[str], dict[str, Any]]
    prices: Callable[[str, str, str], list[dict[str, Any]]]
    news: Callable[[str, int], list[dict[str, Any]]]
    earnings_calendar: Callable[[str], list[dict[str, Any]]]
```

Export it in `__all__`.

- [ ] **Step 4: Rewrite `build_catalog` in registry.py**

Replace the v3 catalog assembly with connector-gated assembly. New `ToolCatalog` drops discovery; `by_name()` and `core_schemas()` remain; remove `active_schemas` / `active_tools_by_name` / `category_index` / `descriptors`-discovery bits. New signature and body:

```python
def build_catalog(
    *,
    ledger: CitationLedger,
    workspace: RunWorkspace,
    transports: EuDataTransports,
    enabled_connectors: EnabledConnectors,
) -> ToolCatalog:
    """Assemble the EU v2 catalog from the user's connector toggles.

    Output tools (write_section, set_cover, emit_chart, finalize) are
    always present. Data tools, the earnings-calendar tool, and native
    web search are each gated by ``enabled_connectors``.
    """
    output = build_output_tools(workspace=workspace)
    core: list[ResearchTool] = [*output]

    if enabled_connectors.financial:
        core.extend(
            build_data_tools(
                ledger=ledger,
                fundamentals=transports.fundamentals,
                prices=transports.prices,
                news=transports.news,
            )
        )
    if enabled_connectors.earnings_calendar:
        core.append(
            build_earnings_calendar_tool(
                ledger=ledger,
                earnings_calendar=transports.earnings_calendar,
            )
        )

    native: tuple[str, ...] = (WEB_SEARCH_TOOL_NAME,) if enabled_connectors.web_search else ()

    descriptors = [tool.descriptor for tool in core]
    if enabled_connectors.web_search:
        descriptors.append(build_web_search_descriptor())

    return ToolCatalog(
        core_tools=core,
        native_tools=native,
        descriptors=descriptors,
    )
```

Update imports (drop valuation/find_tools/extended; add `build_earnings_calendar_tool`, `EuDataTransports`, `EnabledConnectors`). Trim the `ToolCatalog` dataclass to fields `core_tools`, `native_tools`, `descriptors` and keep `by_name()` + `core_schemas()`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_registry.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/core/src/openlia/llm/runtime/report_eu/tools/registry.py packages/core/src/openlia/llm/runtime/report_eu/__init__.py packages/core/tests/runtime/report_eu/test_registry.py
git commit -m "feat(earnings-update-v2): connector-gated tool catalog"
```

### Task 6: Earnings-flavored prompt builder

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/prompts.py`
- Test: `packages/core/tests/runtime/report_eu/test_prompts.py`

`build_system_prompt` gains a trigger-context block and an available-connectors block, and an earnings analyst voice replacing the equity-research voice.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/runtime/report_eu/test_prompts.py
from openlia.llm.runtime.report_eu.prompts import build_system_prompt
from openlia.llm.runtime.report_eu.schemas import (
    EnabledConnectors,
    RunRequest,
    TriggerContext,
)
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec


def _req(connectors: EnabledConnectors, trigger: TriggerContext | None) -> RunRequest:
    return RunRequest(
        subject="MSFT.US Q3 FY26 earnings",
        template=TemplateSpec(
            template_id="eu_default",
            name="Earnings Update",
            shape_description="Post-earnings scorecard",
            ticker_anchored=True,
            default_length="normal",
            sections=[SectionSpec(section_id="quick_take", title="Quick Take", intent="TLDR")],
        ),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=connectors,
        trigger_context=trigger,
    )


def test_prompt_includes_trigger_context():
    prompt = build_system_prompt(
        _req(EnabledConnectors(), TriggerContext(ticker="MSFT.US", fiscal_period="Q3 FY26", eps_estimate="2.50"))
    )
    assert "Q3 FY26" in prompt
    assert "2.50" in prompt


def test_prompt_lists_available_connectors():
    prompt = build_system_prompt(
        _req(EnabledConnectors(financial=True, earnings_calendar=False, web_search=True), None)
    )
    assert "get_fundamentals" in prompt or "financial data" in prompt.lower()
    assert "web search" in prompt.lower()


def test_prompt_states_no_tools_when_all_off():
    prompt = build_system_prompt(_req(EnabledConnectors(financial=False, earnings_calendar=False, web_search=False), None))
    assert "no data tools" in prompt.lower() or "without tools" in prompt.lower()


def test_prompt_lists_template_sections():
    prompt = build_system_prompt(_req(EnabledConnectors(), None))
    assert "quick_take" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_prompts.py -v`
Expected: FAIL — signature mismatch (`build_system_prompt` currently takes `(request, catalog)`).

- [ ] **Step 3: Rewrite prompts.py**

Change `build_system_prompt(request: RunRequest) -> str`. Compose:
1. Earnings analyst identity (post-earnings scorecard analyst; assess the quarter against expectations and the prior thesis; positive directive phrasing).
2. Template shape block: enumerate `request.template.sections` (id, title, intent), or a freeform directive when `sections` is empty.
3. Trigger-context block built from `request.trigger_context` (skip None fields): "You are covering: {ticker} {fiscal_period}, reported {report_date} ({release_timing}). Consensus EPS {eps_estimate}, revenue {revenue_estimate}."
4. Available-connectors block derived from `request.enabled_connectors`: list the enabled tool groups by capability; when all off, state explicitly that no data tools are available and the report must be written from the provided context and the model's own knowledge.
5. Output discipline: call `write_section` for every template section id, optional `set_cover` / `emit_chart`, then `finalize`.

Provide a concrete implementation (real string assembly, no placeholders) following the structure of the copied v3 `build_system_prompt`. Drop the v3 `catalog`/`category_index` argument and any `instructions` handling.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_prompts.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/core/src/openlia/llm/runtime/report_eu/prompts.py packages/core/tests/runtime/report_eu/test_prompts.py
git commit -m "feat(earnings-update-v2): earnings-flavored prompt with trigger + connector blocks"
```

### Task 7: Runner — wire new catalog + prompt, drop revision/discovery paths

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/runner.py`
- Test: `packages/core/tests/runtime/report_eu/test_runner.py`

Edit the forked runner so it calls the new `build_catalog(transports=..., enabled_connectors=...)` and `build_system_prompt(request)`, removes `ReviseContext`/discovery/`find_tools` injection, and removes the v3 web-search-required assumptions. The loop, finalize contract, deadline, and error-wrapped dispatch are unchanged.

- [ ] **Step 1: Write the failing test (fake provider, all connectors off → write+finalize)**

```python
# packages/core/tests/runtime/report_eu/test_runner.py
import pytest

from openlia.llm.runtime.report_eu import EuDataTransports
from openlia.llm.runtime.report_eu.runner import Runner
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors, RunRequest
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec

# Reuse the fake LLM provider / session pattern already used by
# report_v3 runner tests. Import or replicate that fixture here.
from packages.core.tests.runtime.report_v3._fakes import FakeSession  # adjust path


def _req() -> RunRequest:
    return RunRequest(
        subject="MSFT.US Q3 FY26",
        template=TemplateSpec(
            template_id="eu_default", name="EU", shape_description="scorecard",
            ticker_anchored=True, default_length="normal",
            sections=[SectionSpec(section_id="quick_take", title="Quick Take", intent="TLDR")],
        ),
        provider_kind="anthropic", model="claude-sonnet-4-6",
        enabled_connectors=EnabledConnectors(financial=False, earnings_calendar=False, web_search=False),
    )


@pytest.mark.asyncio
async def test_runner_writes_then_finalizes():
    # FakeSession is scripted: turn 1 -> write_section(quick_take), turn 2 -> finalize().
    session = FakeSession.scripted_write_and_finalize(section_id="quick_take")
    transports = EuDataTransports(
        fundamentals=lambda t: {}, prices=lambda t, f, to: [],
        news=lambda t, n: [], earnings_calendar=lambda t: [],
    )
    runner = Runner(request=_req(), session=session, transports=transports)
    result = await runner.run()
    assert result.status == "completed"
    assert any(s["section_id"] == "quick_take" for s in result.sections)
```

(Locate the report_v3 runner-test fakes and reuse them — do not invent a new fake provider. Adjust the import path to the real fixture module. If the report_v3 tests define the fake inline, copy that fake into `packages/core/tests/runtime/report_eu/_fakes.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_runner.py -v`
Expected: FAIL — `Runner.__init__` signature mismatch (`transports` / `enabled_connectors` not threaded) or import error.

- [ ] **Step 3: Edit runner.py**

- Change `Runner` construction to accept `transports: EuDataTransports` (the runner already holds the `RunRequest`; read `enabled_connectors` off it).
- Replace the `build_catalog(...)` call site with `build_catalog(ledger=..., workspace=..., transports=transports, enabled_connectors=request.enabled_connectors)`.
- Replace `build_system_prompt(request, catalog)` with `build_system_prompt(request)`.
- Remove the per-turn discovery injection (the `active_schemas()` / `find_tools` handling) — each turn now uses `catalog.core_schemas()` and `catalog.by_name()` directly.
- Remove `ReviseContext` parameters / prior-section pre-loading.
- Keep web-citation ingestion guarded by `request.enabled_connectors.web_search` (skip when web search is off).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Verify the whole report_eu package imports clean**

Run: `uv run python -c "import openlia.llm.runtime.report_eu; from openlia.llm.runtime.report_eu.runner import Runner; print('ok')"`
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/core/src/openlia/llm/runtime/report_eu packages/core/tests/runtime/report_eu/test_runner.py
git commit -m "feat(earnings-update-v2): runner wired to gated catalog + earnings prompt"
```

---

## Phase 2 — DB models + migration + built-in template seed

### Task 8: ORM models

**Files:**
- Create: `packages/server/src/openlia_server/db/models/report_eu.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py` (export new models)
- Test: `packages/server/tests/db/test_report_eu_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/test_report_eu_models.py
from openlia_server.db.models.report_eu import (
    EuV2EarningsSchedule,
    EuV2Settings,
    EuV2WatchlistEntry,
    ReportEu,
    ReportEuSection,
    ReportEuTemplate,
)


def test_tablenames():
    assert ReportEu.__tablename__ == "report_eu"
    assert ReportEuSection.__tablename__ == "report_eu_sections"
    assert ReportEuTemplate.__tablename__ == "report_eu_templates"
    assert EuV2WatchlistEntry.__tablename__ == "eu_v2_watchlist"
    assert EuV2EarningsSchedule.__tablename__ == "eu_v2_earnings_schedule"
    assert EuV2Settings.__tablename__ == "eu_v2_settings"


def test_settings_connector_defaults_are_columns():
    cols = {c.name for c in EuV2Settings.__table__.columns}
    assert {"financial_enabled", "calendar_enabled", "web_search_enabled"} <= cols


def test_schedule_dedup_unique_constraint():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in EuV2EarningsSchedule.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("user_id", "ticker", "fiscal_date") in uniques
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/db/test_report_eu_models.py -v`
Expected: FAIL — `ModuleNotFoundError: ...db.models.report_eu`.

- [ ] **Step 3: Write the models**

Create `report_eu.py` mirroring `report_v3.py` for the artifact tables (`ReportEu`, `ReportEuSection`, `ReportEuChart`, `ReportEuCitation`, `ReportEuToolCallLog`, `ReportEuTemplate`) with these deltas on `ReportEu`: add `ticker: String(32)`, `trigger_kind: String(16)` (`scheduled`|`on_demand`), `fiscal_date: String(32) nullable`. Drop the revision columns/table (no revisions in EU v2): `ReportEuSection` / `ReportEuChart` keep `version` default 1 but drop `revision_id`. Then add the three control tables:

```python
class EuV2WatchlistEntry(Base):
    """A ticker a user tracks for earnings-triggered reports."""

    __tablename__ = "eu_v2_watchlist"

    id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_eu_v2_watchlist"),
        UniqueConstraint("user_id", "ticker", name="uq_eu_v2_watchlist_user_ticker"),
        Index("ix_eu_v2_watchlist_user_id", "user_id"),
    )


class EuV2EarningsSchedule(Base):
    """Forward earnings calendar built by the weekly sync.

    One row per (user, ticker, fiscal_date). ``status`` walks
    pending -> reported (run fired) or skipped (gave up after retries).
    ``scheduled_run_at`` is when the dispatcher should fire the run.
    """

    __tablename__ = "eu_v2_earnings_schedule"

    id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    fiscal_date: Mapped[str] = mapped_column(String(32), nullable=False)
    release_timing: Mapped[str | None] = mapped_column(String(16), nullable=True)
    eps_estimate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revenue_estimate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scheduled_run_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_eu_v2_earnings_schedule"),
        UniqueConstraint(
            "user_id", "ticker", "fiscal_date",
            name="uq_eu_v2_earnings_schedule_user_ticker_fiscal",
        ),
        Index("ix_eu_v2_earnings_schedule_status_run_at", "status", "scheduled_run_at"),
        Index("ix_eu_v2_earnings_schedule_user_id", "user_id"),
    )


class EuV2Settings(Base):
    """Per-user EU v2 defaults + connector toggles."""

    __tablename__ = "eu_v2_settings"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    length: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    reasoning_effort: Mapped[str | None] = mapped_column(String(16), nullable=True)
    financial_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    calendar_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    web_search_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (PrimaryKeyConstraint("user_id", name="pk_eu_v2_settings"),)
```

Mirror the `report_v3.py` imports (`Boolean, ForeignKey, Index, Integer, LargeBinary, PrimaryKeyConstraint, String, Text, UniqueConstraint`, `JSON`, `Mapped`, `mapped_column`, `Base`, `UTCDateTime`). Add all new classes to `db/models/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/db/test_report_eu_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/db/models/report_eu.py packages/server/src/openlia_server/db/models/__init__.py packages/server/tests/db/test_report_eu_models.py
git commit -m "feat(earnings-update-v2): ORM models for report_eu + eu_v2 control tables"
```

### Task 9: Alembic migration + built-in default template seed

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-05-29_XXXX_earnings_update_v2.py` (use the repo's migration filename convention; generate the revision id with `uv run alembic revision -m "earnings update v2"` then move the body in)
- Create: `packages/core/src/openlia/llm/runtime/report_eu/default_template.py` (builds the `TemplateSpec` from the v1 prompt sections)
- Test: `packages/server/tests/db/test_report_eu_migration.py`

- [ ] **Step 1: Write the default-template builder + its test**

```python
# packages/core/tests/runtime/report_eu/test_default_template.py
from openlia.llm.runtime.report_eu.default_template import build_default_template


def test_default_template_has_eight_sections():
    spec = build_default_template()
    ids = [s.section_id for s in spec.sections]
    assert ids == [
        "quick_take", "market_reaction", "key_financials",
        "operational_highlights", "forward_guidance", "earnings_call",
        "risk_assessment", "thesis_check",
    ]
    assert spec.template_id == "eu_default"
    assert spec.ticker_anchored is True
```

```python
# packages/core/src/openlia/llm/runtime/report_eu/default_template.py
"""Built-in default Earnings Update template.

Codifies the section set the v1 ``earnings_update.yaml`` report produced
as a ``TemplateSpec`` so EU v2 ships a working report shape out of the
box. The migration seeds a ``report_eu_templates`` row from this.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec

_SECTIONS = [
    ("quick_take", "Quick Take", "One-paragraph verdict: beat/miss vs expectations and what it means."),
    ("market_reaction", "Market Reaction", "Price move on the print and why."),
    ("key_financials", "Key Financials", "Revenue, EPS, margins vs consensus and prior year."),
    ("operational_highlights", "Operational Highlights", "Segment and KPI movements that drove the quarter."),
    ("forward_guidance", "Forward Guidance", "Management guidance vs prior guidance and consensus."),
    ("earnings_call", "Earnings Call", "Notable management commentary and analyst Q&A signal."),
    ("risk_assessment", "Risk Assessment", "New or changed risks surfaced by the quarter."),
    ("thesis_check", "Thesis Check", "Does the quarter confirm or challenge the investment thesis."),
]


def build_default_template() -> TemplateSpec:
    return TemplateSpec(
        template_id="eu_default",
        name="Earnings Update (Default)",
        shape_description="Post-earnings scorecard assessing the quarter against expectations and the prior thesis.",
        ticker_anchored=True,
        default_length="normal",
        sections=[SectionSpec(section_id=sid, title=title, intent=intent) for sid, title, intent in _SECTIONS],
    )
```

Run: `uv run pytest packages/core/tests/runtime/report_eu/test_default_template.py -v` → expect FAIL then PASS after creating the module.

- [ ] **Step 2: Write the migration failing test**

```python
# packages/server/tests/db/test_report_eu_migration.py
from sqlalchemy import create_engine, inspect

from openlia_server.db.base import Base
import openlia_server.db.models.report_eu  # noqa: F401  (register tables)


def test_create_all_builds_eu_v2_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    Base.metadata.create_all(engine)
    names = set(inspect(engine).get_table_names())
    assert {
        "report_eu", "report_eu_sections", "report_eu_charts",
        "report_eu_citations", "report_eu_tool_call_log", "report_eu_templates",
        "eu_v2_watchlist", "eu_v2_earnings_schedule", "eu_v2_settings",
    } <= names
```

Run it: expect PASS already (models exist) — this guards the schema. If any table missing, fix Task 8.

- [ ] **Step 3: Generate and write the Alembic migration**

```bash
cd packages/server && uv run alembic revision -m "earnings update v2 tables" && cd -
```

In the generated file: `op.create_table(...)` for all nine tables matching the ORM columns/constraints from Task 8, and seed the built-in template in `upgrade()`:

```python
import json
from datetime import datetime, timezone

from openlia.llm.runtime.report_eu.default_template import build_default_template

# ... after create_table calls ...
spec = build_default_template()
now = datetime.now(timezone.utc)
op.bulk_insert(
    sa.table(
        "report_eu_templates",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("name", sa.String),
        sa.column("is_builtin", sa.Boolean),
        sa.column("template_spec_json", sa.JSON),
        sa.column("source_markdown", sa.Text),
        sa.column("source_doc_blob", sa.LargeBinary),
        sa.column("source_doc_mime", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
        sa.column("deleted_at", sa.DateTime),
    ),
    [{
        "id": "eu_default", "user_id": None, "name": spec.name,
        "is_builtin": True, "template_spec_json": json.loads(spec.model_dump_json()),
        "source_markdown": None, "source_doc_blob": None, "source_doc_mime": None,
        "created_at": now, "updated_at": now, "deleted_at": None,
    }],
)
```

`downgrade()` drops the nine tables in FK-safe order.

- [ ] **Step 4: Apply and verify the migration end-to-end**

Run:
```bash
cd packages/server && uv run alembic upgrade head && cd -
```
Then write/extend a test that runs the migration against a fresh sqlite URL via Alembic config and asserts the `eu_default` row exists in `report_eu_templates`. Expected: PASS, builtin seeded.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/core/src/openlia/llm/runtime/report_eu/default_template.py packages/core/tests/runtime/report_eu/test_default_template.py packages/server/src/openlia_server/db/migrations packages/server/tests/db/test_report_eu_migration.py
git commit -m "feat(earnings-update-v2): migration for eu v2 tables + default template seed"
```

---

## Phase 3 — Services

### Task 10: Settings service

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_settings.py`
- Test: `packages/server/tests/services/test_eu_v2_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_v2_settings.py
from openlia_server.services.eu_v2_settings import get_settings, update_settings


def test_get_returns_defaults_when_no_row(db_session):
    dto = get_settings(db_session, user_id="u1")
    assert dto.financial_enabled is True
    assert dto.calendar_enabled is True
    assert dto.web_search_enabled is False
    assert dto.length == "normal"


def test_update_persists_and_returns(db_session):
    dto = update_settings(
        db_session, user_id="u1",
        provider_kind="anthropic", model="claude-sonnet-4-6",
        template_id="eu_default", language="en", length="elaborative",
        reasoning_effort="medium",
        financial_enabled=False, calendar_enabled=True, web_search_enabled=True,
    )
    assert dto.web_search_enabled is True
    assert dto.length == "elaborative"
    # round-trips
    again = get_settings(db_session, user_id="u1")
    assert again.financial_enabled is False
    assert again.reasoning_effort == "medium"
```

(Use the existing server test DB fixture — find how `test_eu_config.py` obtains `db_session` and reuse that fixture verbatim.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_settings.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the service**

Real code: a frozen `EuSettingsDTO` dataclass with all fields; `get_settings` returns DTO from row or defaults (`provider_kind="anthropic"`, `model="claude-sonnet-4-6"`, `template_id="eu_default"`) when absent; `update_settings` upserts the row (insert if missing, else update, bump `updated_at`) and returns the DTO. Validate `length in {"concise","normal","elaborative"}` and `reasoning_effort in {None,"medium","high"}`, raising `ValueError` otherwise. No emojis, strict types.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/services/eu_v2_settings.py packages/server/tests/services/test_eu_v2_settings.py
git commit -m "feat(earnings-update-v2): per-user settings service (connectors + defaults)"
```

### Task 11: Watchlist service

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_watchlist.py`
- Test: `packages/server/tests/services/test_eu_v2_watchlist.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_v2_watchlist.py
import pytest

from openlia_server.services.eu_v2_watchlist import (
    AlreadyOnWatchlistError,
    WatchlistEntryNotFoundError,
    add_entry, list_entries, remove_entry,
)


def test_add_and_list(db_session):
    e = add_entry(db_session, user_id="u1", ticker="MSFT.US", company_name="Microsoft")
    rows = list_entries(db_session, user_id="u1")
    assert [r.ticker for r in rows] == ["MSFT.US"]
    assert e.id


def test_add_duplicate_raises(db_session):
    add_entry(db_session, user_id="u1", ticker="MSFT.US", company_name=None)
    with pytest.raises(AlreadyOnWatchlistError):
        add_entry(db_session, user_id="u1", ticker="MSFT.US", company_name=None)


def test_remove(db_session):
    e = add_entry(db_session, user_id="u1", ticker="AAPL.US", company_name=None)
    remove_entry(db_session, user_id="u1", entry_id=e.id)
    assert list_entries(db_session, user_id="u1") == []


def test_remove_missing_raises(db_session):
    with pytest.raises(WatchlistEntryNotFoundError):
        remove_entry(db_session, user_id="u1", entry_id="nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_watchlist.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the service**

Real code mirroring v1 `eu_watchlist.py` shape but against `EuV2WatchlistEntry`: `WatchlistEntryDTO` (id, ticker, company_name, created_at); `add_entry` (uuid id, catch unique violation → `AlreadyOnWatchlistError`); `list_entries` (ordered by ticker); `remove_entry` (filter user_id+id, raise `WatchlistEntryNotFoundError` if absent). Ticker normalized upper-case. No EODHD call here — calendar sync (Task 14) is separate.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_watchlist.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/services/eu_v2_watchlist.py packages/server/tests/services/test_eu_v2_watchlist.py
git commit -m "feat(earnings-update-v2): watchlist service"
```

### Task 12: Template service

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_template_service.py`
- Test: `packages/server/tests/services/test_eu_v2_template_service.py`

Mirror `v3_template_service.py` against `ReportEuTemplate`: `resolve_template(db, user_id, template_id) -> TemplateSpec` (builtin or owned, soft-delete filtered), `list_templates(db, user_id)` (builtins + own, builtin first then name), `upload_template(db, user_id, name, source_markdown)` (compile markdown → `TemplateSpec` via the same compiler v3 uses, persist UUID row), `delete_template(db, user_id, template_id)` (soft-delete; refuse builtins).

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_v2_template_service.py
import pytest

from openlia_server.services.eu_v2_template_service import (
    TemplateNotFoundError, list_templates, resolve_template,
)


def test_resolve_builtin_default(db_session_with_seed):
    spec = resolve_template(db_session_with_seed, user_id="u1", template_id="eu_default")
    assert spec.template_id == "eu_default"
    assert len(spec.sections) == 8


def test_list_includes_builtin(db_session_with_seed):
    rows = list_templates(db_session_with_seed, user_id="u1")
    assert any(t.id == "eu_default" and t.is_builtin for t in rows)


def test_resolve_unknown_raises(db_session_with_seed):
    with pytest.raises(TemplateNotFoundError):
        resolve_template(db_session_with_seed, user_id="u1", template_id="ghost")
```

(`db_session_with_seed` = the test DB with the `eu_default` builtin row inserted; add a fixture that inserts it via `build_default_template()` if the migration is not run in unit tests. Mirror how v3 template tests seed.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_template_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement by adapting v3_template_service.py**

Copy `v3_template_service.py` to `eu_v2_template_service.py`, swap `ReportV3Template` → `ReportEuTemplate`, keep the same compile/resolve/list/delete logic and exception type names (`TemplateNotFoundError`). Reuse the v3 markdown→TemplateSpec compiler import unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_template_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/services/eu_v2_template_service.py packages/server/tests/services/test_eu_v2_template_service.py
git commit -m "feat(earnings-update-v2): template service (builtin + upload)"
```

### Task 13: EODHD transports wiring (incl. earnings calendar)

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_wiring.py`
- Test: `packages/server/tests/services/test_eu_v2_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_v2_wiring.py
from openlia_server.services.eu_v2_wiring import build_eu_v2_transports


def test_none_when_no_key(monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    assert build_eu_v2_transports() is None


def test_bundle_when_key_set(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    t = build_eu_v2_transports()
    assert t is not None
    assert callable(t.fundamentals)
    assert callable(t.earnings_calendar)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_wiring.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the wiring**

Adapt `v3_wiring.py`: return an `EuDataTransports` (not `DataTransports`). Reuse the same `fundamentals` / `prices` / `news` closures over the EODHD `APIClient`. Add `earnings_calendar`:

```python
def earnings_calendar(ticker: str) -> list[dict[str, Any]]:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers.eodhd import (
        eodhd_upcoming_earnings,
    )

    payload = eodhd_upcoming_earnings.execute(ticker)
    return list(payload.get("upcoming_earnings", []))
```

Return `EuDataTransports(fundamentals=..., prices=..., news=..., earnings_calendar=earnings_calendar)`. Return `None` when `EODHD_API_KEY` unset.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_wiring.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/services/eu_v2_wiring.py packages/server/tests/services/test_eu_v2_wiring.py
git commit -m "feat(earnings-update-v2): EODHD transports wiring incl. earnings calendar"
```

### Task 14: Calendar-sync service (weekly sync logic)

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_calendar_sync.py`
- Test: `packages/server/tests/services/test_eu_v2_calendar_sync.py`

Pure, testable upsert logic given an injected `earnings_calendar` callable — no scheduler, no network.

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_v2_calendar_sync.py
from datetime import datetime, timezone

from openlia_server.db.models.report_eu import EuV2EarningsSchedule
from openlia_server.services.eu_v2_calendar_sync import sync_user_watchlist


def _cal(rows):
    return lambda ticker: rows.get(ticker, [])


def test_sync_inserts_pending_rows(db_session):
    add_watchlist(db_session, "u1", ["MSFT.US"])  # helper inserts EuV2WatchlistEntry
    cal = _cal({"MSFT.US": [{"report_date": "2026-06-15", "before_after_market": "AfterMarket", "estimate": "2.50"}]})
    n = sync_user_watchlist(db_session, user_id="u1", earnings_calendar=cal, now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert n == 1
    row = db_session.query(EuV2EarningsSchedule).one()
    assert row.ticker == "MSFT.US"
    assert row.fiscal_date == "2026-06-15"
    assert row.status == "pending"
    assert row.release_timing == "post_market"


def test_resync_updates_shifted_date_not_duplicates(db_session):
    add_watchlist(db_session, "u1", ["MSFT.US"])
    cal1 = _cal({"MSFT.US": [{"report_date": "2026-06-15", "before_after_market": "AfterMarket"}]})
    sync_user_watchlist(db_session, user_id="u1", earnings_calendar=cal1, now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    cal2 = _cal({"MSFT.US": [{"report_date": "2026-06-15", "before_after_market": "AfterMarket"}]})
    # same fiscal_date -> dedup, still one row
    sync_user_watchlist(db_session, user_id="u1", earnings_calendar=cal2, now=datetime(2026, 6, 2, tzinfo=timezone.utc))
    assert db_session.query(EuV2EarningsSchedule).count() == 1


def test_already_reported_row_untouched(db_session):
    add_watchlist(db_session, "u1", ["MSFT.US"])
    cal = _cal({"MSFT.US": [{"report_date": "2026-06-15", "before_after_market": "BeforeMarket"}]})
    sync_user_watchlist(db_session, user_id="u1", earnings_calendar=cal, now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    row = db_session.query(EuV2EarningsSchedule).one()
    row.status = "reported"
    db_session.commit()
    sync_user_watchlist(db_session, user_id="u1", earnings_calendar=cal, now=datetime(2026, 6, 2, tzinfo=timezone.utc))
    assert db_session.query(EuV2EarningsSchedule).one().status == "reported"
```

(Define the `add_watchlist` helper inline in the test module using `eu_v2_watchlist.add_entry`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_calendar_sync.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement sync logic**

`sync_user_watchlist(db, *, user_id, earnings_calendar, now) -> int` returns count of pending rows touched:
- Load the user's `EuV2WatchlistEntry` tickers.
- For each ticker, call `earnings_calendar(ticker)` → list of event dicts.
- For each event with a `report_date`: map `before_after_market` ("BeforeMarket"→`pre_market`, "AfterMarket"→`post_market`, else None); compute `scheduled_run_at` via a helper `compute_run_at(report_date, timing)` — pre_market → report_date 14:00 UTC (≈ post US open); post_market → report_date 23:00 UTC; unknown → report_date 23:00 UTC.
- Upsert on `(user_id, ticker, fiscal_date=report_date)`: if no row → insert `status="pending"`; if row exists and `status="pending"` → update `scheduled_run_at`, estimates, `synced_at`; if `status in {"reported","skipped"}` → leave untouched.
- Pull `eps_estimate` / `revenue_estimate` from event keys (`estimate`, `revenue_estimate_avg` when present; store as strings).

Provide full real implementation, strict types, raise nothing on empty calendar (just 0).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_calendar_sync.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/services/eu_v2_calendar_sync.py packages/server/tests/services/test_eu_v2_calendar_sync.py
git commit -m "feat(earnings-update-v2): weekly calendar-sync upsert logic"
```

### Task 15: Run service (async start + persist + stream)

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_run_service.py`
- Test: `packages/server/tests/services/test_eu_v2_run_service.py`

Mirror `v3_run_service.py`: build the `report_eu.RunRequest` from settings + template + trigger context, construct `LLMSession` + `Runner`, run, persist `report_eu` + child rows, emit events to the broker. The on-demand and dispatcher paths both call `start_run_async`.

- [ ] **Step 1: Write the failing test (service-level, fake session + fake transports)**

```python
# packages/server/tests/services/test_eu_v2_run_service.py
import pytest

from openlia_server.services.eu_v2_run_service import build_run_request


def test_build_run_request_uses_settings_and_trigger(db_session_with_seed):
    # settings: web search on, financial off
    from openlia_server.services.eu_v2_settings import update_settings
    update_settings(
        db_session_with_seed, user_id="u1",
        provider_kind="anthropic", model="claude-sonnet-4-6", template_id="eu_default",
        language="en", length="normal", reasoning_effort=None,
        financial_enabled=False, calendar_enabled=True, web_search_enabled=True,
    )
    req = build_run_request(
        db_session_with_seed, user_id="u1", ticker="MSFT.US",
        trigger_kind="scheduled", fiscal_period="Q3 FY26",
        report_date="2026-06-15", release_timing="post_market",
        eps_estimate="2.50", revenue_estimate=None,
    )
    assert req.provider_kind == "anthropic"
    assert req.enabled_connectors.financial is False
    assert req.enabled_connectors.web_search is True
    assert req.trigger_context.fiscal_period == "Q3 FY26"
    assert req.template.template_id == "eu_default"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_run_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement build_run_request + start_run_async + persistence**

- `build_run_request(db, *, user_id, ticker, trigger_kind, fiscal_period, report_date, release_timing, eps_estimate, revenue_estimate) -> RunRequest`: load settings via `eu_v2_settings.get_settings`, resolve template via `eu_v2_template_service.resolve_template`, build `EnabledConnectors(financial=..., earnings_calendar=..., web_search=...)`, build `TriggerContext`, set subject = f"{ticker} {fiscal_period} earnings" (fallback to ticker). Map `length`/`language`/`reasoning_effort` strings to the engine enums.
- `start_run_async(db_factory, *, user_id, request, broker, cancel_registry) -> str`: insert a `report_eu` row (`status="running"`, `trigger_kind`, `ticker`, `fiscal_date`), spawn the runner on a background asyncio task (use the exact pattern from `v3_run_service` incl. `_BACKGROUND_TASKS` set + `add_done_callback` discard so RUF006 stays clean), persist sections/charts/citations on completion, flip status to `completed`/`failed`, push events to the broker. Transports come from `build_eu_v2_transports()`; `None` falls through to a loud null transport bundle (mirror v3's null fallback).
- A `persist_result(db, *, report_id, result)` helper writes child rows.

This is large — follow `v3_run_service.py` structure closely; only the request-building differs.

- [ ] **Step 4: Run test to verify build_run_request passes**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_run_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/services/eu_v2_run_service.py packages/server/tests/services/test_eu_v2_run_service.py
git commit -m "feat(earnings-update-v2): run service (request build + async start + persist)"
```

---

## Phase 4 — Routes + app wiring

### Task 16: Router — watchlist, settings, templates, schedule, runs, SSE

**Files:**
- Create: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py`
- Test: `packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py`

- [ ] **Step 1: Write the failing route tests (TestClient)**

```python
# packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py
import pytest


def test_routes_503_when_disabled(client_eu_v2_disabled):
    r = client_eu_v2_disabled.get("/api/departments/earnings-update/v2/settings")
    assert r.status_code == 503


def test_settings_get_returns_defaults(client_eu_v2):
    r = client_eu_v2.get("/api/departments/earnings-update/v2/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["financial_enabled"] is True
    assert body["web_search_enabled"] is False


def test_watchlist_add_list_delete(client_eu_v2):
    r = client_eu_v2.post("/api/departments/earnings-update/v2/watchlist", json={"ticker": "MSFT.US"})
    assert r.status_code == 201
    entry_id = r.json()["id"]
    r = client_eu_v2.get("/api/departments/earnings-update/v2/watchlist")
    assert [e["ticker"] for e in r.json()["entries"]] == ["MSFT.US"]
    r = client_eu_v2.delete(f"/api/departments/earnings-update/v2/watchlist/{entry_id}")
    assert r.status_code == 204


def test_templates_list_has_builtin(client_eu_v2):
    r = client_eu_v2.get("/api/departments/earnings-update/v2/templates")
    assert r.status_code == 200
    assert any(t["id"] == "eu_default" for t in r.json()["templates"])


def test_run_start_handler_is_async():
    # Guard against the v3 sync-def bug: create_task needs a running loop.
    import inspect
    from openlia_server.routes.departments import earnings_update_v2 as mod
    # the start handler must be a coroutine function
    assert any(
        inspect.iscoroutinefunction(getattr(mod, n, None))
        for n in dir(mod) if "start" in n.lower()
    )
```

(Add `client_eu_v2` / `client_eu_v2_disabled` fixtures: build the app with the router mounted, `EARNINGS_ENGINE_VERSION=v2` set/unset, auth in personal mode. Mirror the v3 route-test fixtures.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py -v`
Expected: FAIL — router module missing.

- [ ] **Step 3: Implement the router**

`build_earnings_update_v2_router(*, db_session_factory, mode)`. Every handler first checks `eu_v2_enabled()` (raise `HTTPException(503)` when off). Use `build_require_auth(mode=mode)` like the v1 EU router. Endpoints (Pydantic in/out models defined in-file):

- `GET /settings` → `eu_v2_settings.get_settings`; `PUT /settings` → `update_settings`.
- `GET /watchlist` → `{entries: [...]}`; `POST /watchlist` (201, body `{ticker}`) → add_entry then trigger a single-ticker calendar sync best-effort (call `eu_v2_calendar_sync.sync_user_watchlist` scoped to that ticker when transports available; ignore failures); `DELETE /watchlist/{id}` (204).
- `POST /watchlist/sync` → run `sync_user_watchlist` for the user, return `{synced: n}`.
- `GET /templates` → `{templates: [...]}`; `POST /templates` (upload); `DELETE /templates/{id}` (204).
- `GET /schedule` → upcoming `eu_v2_earnings_schedule` rows for the user (status pending), ordered by `scheduled_run_at`.
- `POST /runs/start` → **`async def`** handler: build request via `build_run_request(trigger_kind="on_demand", ...)` (ticker from body; estimates pulled from calendar when `calendar_enabled` and transports present), call `eu_v2_run_service.start_run_async`, return `{report_id}`.
- `GET /runs` → list `report_eu` rows; `GET /runs/{id}` → detail (sections/charts/citations/cover); `DELETE /runs/{id}` (204).
- `POST /runs/{id}/cancel` → flip cancel token.
- `GET /runs/{id}/events` → SSE from the broker (reuse the v3 SSE generator pattern; separate broker registry keys).

Add an explicitly-named coroutine handler (e.g. `start_run` defined as `async def`) so the Step-1 guard test passes and the v3 sync-def bug class cannot recur.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/routes/departments/earnings_update_v2.py packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py
git commit -m "feat(earnings-update-v2): HTTP router (watchlist/settings/templates/schedule/runs/SSE)"
```

### Task 17: App wiring — mount router + broker/cancel registry

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_app_eu_v2_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_app_eu_v2_wiring.py
def test_eu_v2_router_mounted(monkeypatch):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "v2")
    from openlia_server.app import create_app
    app = create_app()
    paths = {r.path for r in app.routes}
    assert "/api/departments/earnings-update/v2/settings" in paths
    assert hasattr(app.state, "eu_v2_event_broker")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_app_eu_v2_wiring.py -v`
Expected: FAIL — path/state missing.

- [ ] **Step 3: Wire in app.py**

Next to the v3 wiring: initialize `app.state.eu_v2_event_broker = EventBroker()` and `app.state.eu_v2_cancel_registry = {}` at startup; `app.include_router(build_earnings_update_v2_router(db_session_factory=..., mode=...))`. Mount unconditionally — the router self-gates per-request via `eu_v2_enabled()` (matches v3, which mounts then 503s).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_app_eu_v2_wiring.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/app.py packages/server/tests/test_app_eu_v2_wiring.py
git commit -m "feat(earnings-update-v2): mount router + event broker in app factory"
```

---

## Phase 5 — Trigger pipeline (scheduler)

### Task 18: JobType + payload protocols

**Files:**
- Modify: `packages/server/src/openlia_server/scheduler/registry.py`
- Modify: `packages/server/src/openlia_server/scheduler/payloads.py`
- Test: `packages/server/tests/test_scheduler/test_eu_v2_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_scheduler/test_eu_v2_registry.py
from openlia_server.scheduler.registry import JobType, department_for_job_type


def test_eu_v2_job_types_exist():
    assert JobType.EU_V2_SYNC.value == "eu_v2_sync"
    assert JobType.EU_V2_DISPATCH.value == "eu_v2_dispatch"


def test_department_mapping():
    assert department_for_job_type(JobType.EU_V2_SYNC) == "earnings_update_v2"
    assert department_for_job_type(JobType.EU_V2_DISPATCH) == "earnings_update_v2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_scheduler/test_eu_v2_registry.py -v`
Expected: FAIL — enum members missing.

- [ ] **Step 3: Add enum members + mapping + payload protocols**

In `registry.py` add `EU_V2_SYNC = "eu_v2_sync"` and `EU_V2_DISPATCH = "eu_v2_dispatch"` to `JobType`, and both → `"earnings_update_v2"` in `_DEPARTMENT_BY_JOB`. Both are global (all-users) jobs, so add them to the `job_key` global-key branch (like `PORTFOLIO_PRICE_REFRESH`) with fixed keys `EU_V2_SYNC_KEY = "eu_v2_sync"`, `EU_V2_DISPATCH_KEY = "eu_v2_dispatch"`, and handle them in `parse_job_key`.

In `payloads.py` add protocols:

```python
class EuV2CalendarSyncer(Protocol):
    """Run the weekly EODHD calendar sync across all EU v2 watchlists."""

    def sync_all(self, *, session: Session) -> int: ...


class EuV2Dispatcher(Protocol):
    """Fire due scheduled earnings runs from eu_v2_earnings_schedule."""

    def dispatch_due(self, *, session: Session, now: datetime) -> int: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_scheduler/test_eu_v2_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/scheduler/registry.py packages/server/src/openlia_server/scheduler/payloads.py packages/server/tests/test_scheduler/test_eu_v2_registry.py
git commit -m "feat(earnings-update-v2): EU_V2_SYNC + EU_V2_DISPATCH job types and payloads"
```

### Task 19: Sync-all + dispatch services

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_dispatch.py`
- Modify: `packages/server/src/openlia_server/services/eu_v2_calendar_sync.py` (add `sync_all_watchlists`)
- Test: `packages/server/tests/services/test_eu_v2_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_v2_dispatch.py
from datetime import datetime, timezone

from openlia_server.services.eu_v2_dispatch import select_due_rows, mark_reported, mark_failed


def test_select_due_returns_only_past_pending(db_session):
    seed_schedule(db_session, "u1", "MSFT.US", "2026-06-15",
                  run_at=datetime(2026, 6, 15, 23, tzinfo=timezone.utc), status="pending")
    seed_schedule(db_session, "u1", "AAPL.US", "2026-07-30",
                  run_at=datetime(2026, 7, 30, 23, tzinfo=timezone.utc), status="pending")
    due = select_due_rows(db_session, now=datetime(2026, 6, 16, tzinfo=timezone.utc))
    assert [r.ticker for r in due] == ["MSFT.US"]


def test_mark_reported_sets_status_and_report_id(db_session):
    row = seed_schedule(db_session, "u1", "MSFT.US", "2026-06-15",
                        run_at=datetime(2026, 6, 15, 23, tzinfo=timezone.utc), status="pending")
    mark_reported(db_session, row_id=row.id, report_id="r123")
    db_session.refresh(row)
    assert row.status == "reported"
    assert row.report_id == "r123"


def test_mark_failed_skips_after_max_attempts(db_session):
    row = seed_schedule(db_session, "u1", "MSFT.US", "2026-06-15",
                        run_at=datetime(2026, 6, 15, 23, tzinfo=timezone.utc), status="pending")
    for _ in range(3):
        mark_failed(db_session, row_id=row.id, max_attempts=3)
    db_session.refresh(row)
    assert row.status == "skipped"
    assert row.attempts == 3
```

(`seed_schedule` inserts an `EuV2EarningsSchedule` row; define inline.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_dispatch.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement dispatch helpers + sync_all**

`eu_v2_dispatch.py`:
- `select_due_rows(db, *, now) -> list[EuV2EarningsSchedule]` — `status="pending"` AND `scheduled_run_at <= now`, ordered by `scheduled_run_at`.
- `mark_reported(db, *, row_id, report_id)` — set `status="reported"`, `report_id`, commit.
- `mark_failed(db, *, row_id, max_attempts)` — increment `attempts`; if `attempts >= max_attempts` set `status="skipped"`, else leave `pending`; commit.

In `eu_v2_calendar_sync.py` add `sync_all_watchlists(db, *, earnings_calendar, now) -> int` — iterate distinct `user_id`s in `eu_v2_watchlist`, call `sync_user_watchlist` for each, sum counts.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/services/test_eu_v2_dispatch.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/services/eu_v2_dispatch.py packages/server/src/openlia_server/services/eu_v2_calendar_sync.py packages/server/tests/services/test_eu_v2_dispatch.py
git commit -m "feat(earnings-update-v2): dispatch selection/marking + sync-all"
```

### Task 20: Scheduler executors

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/executors/eu_v2.py`
- Test: `packages/server/tests/test_scheduler/test_eu_v2_executors.py`

Two executors implementing the existing executor base contract: `EuV2SyncExecutor` (calls `sync_all_watchlists` with the wired transports' `earnings_calendar`) and `EuV2DispatchExecutor` (calls `select_due_rows`, fires each via the run service, marks reported/failed).

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_scheduler/test_eu_v2_executors.py
import pytest

from openlia_server.scheduler.executors.eu_v2 import EuV2DispatchExecutor, EuV2SyncExecutor


@pytest.mark.asyncio
async def test_sync_executor_invokes_syncer(fake_session_factory):
    calls = {}

    class Syncer:
        def sync_all(self, *, session):
            calls["ran"] = True
            return 2

    ex = EuV2SyncExecutor(session_factory=fake_session_factory, syncer=Syncer())
    await ex.execute(job_key="eu_v2_sync")
    assert calls["ran"] is True


@pytest.mark.asyncio
async def test_dispatch_executor_fires_due_rows(fake_session_factory):
    fired = []

    class Dispatcher:
        def dispatch_due(self, *, session, now):
            fired.append(now)
            return 1

    ex = EuV2DispatchExecutor(session_factory=fake_session_factory, dispatcher=Dispatcher())
    await ex.execute(job_key="eu_v2_dispatch")
    assert len(fired) == 1
```

(Match the real executor base `execute(...)` signature — read `executors/eu.py` (the v1 `EUScanExecutor`) and mirror its method shape exactly: session-factory usage, async/sync, args.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_scheduler/test_eu_v2_executors.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the executors**

Follow `executors/eu.py` structure (`__init__` stores collaborators; `execute` opens a session via `session_factory`, does work, handles errors per base contract). `EuV2SyncExecutor` wraps an `EuV2CalendarSyncer`; `EuV2DispatchExecutor` wraps an `EuV2Dispatcher`. Keep them thin — logic lives in the services from Tasks 14/19. The concrete `EuV2CalendarSyncer` / `EuV2Dispatcher` implementations (bound to transports + run service) live in the wiring (Task 21).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_scheduler/test_eu_v2_executors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/scheduler/executors/eu_v2.py packages/server/tests/test_scheduler/test_eu_v2_executors.py
git commit -m "feat(earnings-update-v2): sync + dispatch scheduler executors"
```

### Task 21: Scheduler wiring + concrete syncer/dispatcher + default schedules

**Files:**
- Modify: `packages/server/src/openlia_server/scheduler/wiring.py`
- Create: `packages/server/src/openlia_server/services/eu_v2_scheduler_impl.py` (concrete `EuV2CalendarSyncer` + `EuV2Dispatcher`)
- Modify: scheduler default-schedule registration (where `PORTFOLIO_PRICE_REFRESH` / maintenance cadences are registered — find that call site)
- Test: `packages/server/tests/test_scheduler/test_eu_v2_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_scheduler/test_eu_v2_wiring.py
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.wiring import build_scheduler_service


def test_eu_v2_executors_registered(scheduler_wiring_kwargs):
    svc = build_scheduler_service(
        **scheduler_wiring_kwargs,
        eu_v2_syncer=_FakeSyncer(),
        eu_v2_dispatcher=_FakeDispatcher(),
    )
    assert JobType.EU_V2_SYNC in svc.executors
    assert JobType.EU_V2_DISPATCH in svc.executors
```

(`scheduler_wiring_kwargs` = the existing fixture supplying all required `build_scheduler_service` args; reuse it. Define `_FakeSyncer`/`_FakeDispatcher` inline.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_scheduler/test_eu_v2_wiring.py -v`
Expected: FAIL — `build_scheduler_service` rejects the new kwargs / executors absent.

- [ ] **Step 3: Implement concrete syncer/dispatcher + wire**

`eu_v2_scheduler_impl.py`:
- `EuV2CalendarSyncerImpl(transports_factory)` — `sync_all(session)` reads `build_eu_v2_transports()`; if `None`, log and return 0; else call `sync_all_watchlists(session, earnings_calendar=transports.earnings_calendar, now=utcnow())`.
- `EuV2DispatcherImpl(run_service, broker_factory, cancel_registry)` — `dispatch_due(session, now)`: for each `select_due_rows`, `build_run_request(trigger_kind="scheduled", ...)` from the row, `start_run_async(...)`, then `mark_reported`; on exception `mark_failed(max_attempts=3)`. Returns count fired.

In `wiring.py`: add optional `eu_v2_syncer` / `eu_v2_dispatcher` params; when present register `JobType.EU_V2_SYNC: EuV2SyncExecutor(...)` and `JobType.EU_V2_DISPATCH: EuV2DispatchExecutor(...)` (mirror the conditional `rs_runner` / `financial_adapter_provider` blocks).

Register default cadences where other global jobs are scheduled: `EU_V2_SYNC` weekly (e.g. Mondays 06:00 UTC), `EU_V2_DISPATCH` hourly. Follow the existing default-schedule registration idiom.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_scheduler/test_eu_v2_wiring.py -v`
Expected: PASS.

- [ ] **Step 5: Wire the syncer/dispatcher in app.py startup**

Pass `eu_v2_syncer=EuV2CalendarSyncerImpl(...)` and `eu_v2_dispatcher=EuV2DispatcherImpl(...)` into `build_scheduler_service(...)` at the app's scheduler-construction site.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix . && uv run ruff format .
git add packages/server/src/openlia_server/scheduler/wiring.py packages/server/src/openlia_server/services/eu_v2_scheduler_impl.py packages/server/src/openlia_server/app.py packages/server/tests/test_scheduler/test_eu_v2_wiring.py
git commit -m "feat(earnings-update-v2): wire weekly sync + hourly dispatcher into scheduler"
```

---

## Phase 6 — Integration verification

### Task 22: End-to-end backend smoke (gated app, in-memory)

**Files:**
- Test: `packages/server/tests/test_integration/test_eu_v2_end_to_end.py`

- [ ] **Step 1: Write the integration test**

Drive the full backend with a fake LLM session and fake EODHD calendar:
1. `EARNINGS_ENGINE_VERSION=v2`, build app, authenticate.
2. PUT settings (web_search off, financial off, calendar off → output-tools-only so the fake session just writes+finalizes).
3. POST a watchlist ticker.
4. Seed an `eu_v2_earnings_schedule` due row (or run the sync service with a fake calendar producing a past-dated release).
5. Invoke the dispatcher service directly with `now` past the run time.
6. Assert a `report_eu` row exists with `status="completed"`, `trigger_kind="scheduled"`, and ≥1 section.
7. Assert the schedule row flipped to `reported` with the `report_id` set.

```python
# packages/server/tests/test_integration/test_eu_v2_end_to_end.py
# (Compose fixtures from earlier phases: fake LLM session, fake transports,
#  TestClient with auth. Reuse the report_v3 fake-session helper.)
def test_scheduled_run_completes_and_marks_reported(eu_v2_app_ctx):
    ...  # steps 1-7 above, real assertions
```

- [ ] **Step 2: Run it**

Run: `uv run pytest packages/server/tests/test_integration/test_eu_v2_end_to_end.py -v`
Expected: PASS after fixtures assembled. Fix any wiring gaps surfaced here.

- [ ] **Step 3: Full suite + lint**

Run:
```bash
uv run pytest packages/core/tests/runtime/report_eu packages/server/tests -q
uv run ruff check . && uv run ruff format --check .
```
Expected: all green, format clean.

- [ ] **Step 4: Commit**

```bash
git add packages/server/tests/test_integration/test_eu_v2_end_to_end.py
git commit -m "test(earnings-update-v2): end-to-end scheduled-run smoke"
```

### Task 23: Update planning docs + open PR

- [ ] **Step 1: Update `planning/phase-progress.md`** with an EU v2 backend entry (phases/tasks shipped).
- [ ] **Step 2: Note any divergence** from this plan back into `planning/2026-05-29-earnings-update-v2-design.md` (coding-standard rule 9).
- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/earnings-update-v2-backend
gh pr create --title "feat(earnings-update): v2 backend (forked engine, connector toggles, weekly calendar trigger)" --body "Implements planning/2026-05-29-earnings-update-v2-design.md. Backend only; frontend is a follow-up phase. Gated by EARNINGS_ENGINE_VERSION=v2; EU v1 untouched."
```

---

## Self-review notes (coverage map)

- Spec §3 engine fork → Tasks 1-7. §3 charts kept → Task 1 prune leaves `output_tools` (emit_chart).
- Spec §4 connector toggles → Tasks 2 (schema), 5 (catalog), 6 (prompt), 13 (transports), 10 (settings persistence).
- Spec §5 tables → Tasks 8-9 (all nine tables + builtin seed).
- Spec §6 trigger pipeline → Tasks 14 (sync), 18-21 (job types, dispatch, executors, wiring, cadences).
- Spec §7 run service + routes → Tasks 15-17.
- Spec §8 builtin default template → Task 9 (`default_template.py` + migration seed).
- Spec §9 v1 coexistence / env gate → Task 0 + per-request gate in Task 16, mount in Task 17.
- Spec §11 testing → every task is TDD; route-level async-handler guard in Task 16 closes the v3 sync-def bug class.
- Spec §10 frontend → intentionally deferred (out of scope this plan).
- Spec §12 deferred items (notifications) → not implemented; left for a follow-up, consistent with the spec marking them deferred.

Open follow-ups (not blocking this plan): completion notification reuse of `user_notifications`; PDF/DOCX render endpoints (Task 16 lists html/pdf/docx — if the v3 render services are not trivially reusable, ship html only in this plan and defer pdf/docx).
