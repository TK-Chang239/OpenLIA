# Morning Briefing Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy Morning Briefing engine with an EU-v2-style, connector-gated, tool-use briefing engine that runs on the existing cron scheduler, with per-schedule template/instructions/connector/model binding.

**Architecture:** Fork `report_eu` → `report_mb` (single-model tool-use loop, no revision, no batch, connector-gated catalog). Mirror the `report_eu` DB family and `eu_v2_*` services as `report_mb*` / `mb_v2_*`. Keep the existing APScheduler cron mechanism but rewire the executor to the new engine. Rewrite the route and frontend in the EU page shape. Clean replacement — no feature gate.

**Tech Stack:** Python 3 (core: pure, no web deps), FastAPI + SQLAlchemy + Alembic (server), React/TypeScript/Vite (frontend), `uv` + `ruff` + `pytest`, `vitest` + `tsc`.

**Reference spec:** `docs/superpowers/specs/2026-06-02-morning-briefing-rework-design.md`

**Reference implementation to mirror (READ THESE FIRST for each layer):**
- Engine: `packages/core/src/openlia/llm/runtime/report_eu/`
- DB models: `packages/server/src/openlia_server/db/models/report_eu.py`
- Services: `packages/server/src/openlia_server/services/eu_v2_*.py`
- Route: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py`
- Frontend: `frontend/src/pages/departments/EarningsUpdate.tsx`, `frontend/src/components/` (EU components), `frontend/src/api/earnings-update.ts`

**Conventions (from CLAUDE.md):**
- `uv run` for all Python; `npm` in `frontend/`.
- `uv run ruff check --fix . && uv run ruff format .` before each commit.
- Modern strict type hints; fail fast with specific exceptions; no emojis; positive LLM prompt phrasing.
- Core (`packages/core/`) must never import FastAPI/HTTP. Verify: `from openlia import ...` works library-only.
- Server full suite hangs on SSE tests (no pytest-timeout) — run targeted dirs/files, never bare `uv run pytest` on `packages/server/`.
- Bilingual: every new frontend string needs `en` + `zh-TW` i18n keys.

---

## Phase 1 — Core `report_mb` engine

Goal: a working, unit-tested tool-use briefing engine in `packages/core/`, decoupled from the server via injected `MbDataTransports`.

### Task 1.1: Scaffold `report_mb` package by forking `report_eu`

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_mb/` (copy of `report_eu/` then edited in later tasks)
- Test: `packages/core/tests/llm/runtime/report_mb/test_imports.py`

- [ ] **Step 1: Copy the EU engine as the starting point**

```bash
cp -r packages/core/src/openlia/llm/runtime/report_eu packages/core/src/openlia/llm/runtime/report_mb
```

- [ ] **Step 2: Write the failing import test**

Create `packages/core/tests/llm/runtime/report_mb/__init__.py` (empty) and `test_imports.py`:

```python
def test_public_surface_imports():
    from openlia.llm.runtime.report_mb import (
        BriefingContext,
        MbDataTransports,
        RunRequest,
        RunResult,
        Runner,
        TemplateSpec,
    )

    assert Runner is not None
    assert BriefingContext is not None
    assert MbDataTransports is not None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_imports.py -v`
Expected: FAIL — `ImportError: cannot import name 'BriefingContext'` (the copied package still exports `TriggerContext` / `EuDataTransports`).

- [ ] **Step 4: Rename the engine identity (module docstrings + `__init__` exports)**

In `report_mb/__init__.py`: update the module docstring to describe the Morning Briefing engine; in `__all__` and the import lines, replace `TriggerContext` → `BriefingContext` and `EuDataTransports` → `MbDataTransports`. (The symbols are renamed in Tasks 1.2 / 1.3; for now keep the file importable by also renaming in the source modules below as you go — run the test after Task 1.3.)

- [ ] **Step 5: Defer** — this test passes only after Tasks 1.2 and 1.3 rename the symbols. Mark Task 1.1 step 4 done; the green checkpoint is at the end of Task 1.3.

### Task 1.2: `schemas.py` — `BriefingContext`, briefing `RunRequest`

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_mb/schemas.py`
- Test: `packages/core/tests/llm/runtime/report_mb/test_schemas.py`

- [ ] **Step 1: Write failing schema tests**

```python
import pytest
from pydantic import ValidationError

from openlia.llm.runtime.report_mb.schemas import (
    BriefingContext,
    EnabledConnectors,
    RunRequest,
)
from openlia.llm.runtime.report_v2_3.templates.spec import TemplateSpec


def test_briefing_context_minimal():
    ctx = BriefingContext(run_date="2026-06-02")
    assert ctx.run_date == "2026-06-02"
    assert ctx.schedule_label is None


def test_run_request_subject_is_label_not_ticker():
    tpl = TemplateSpec.builtin_default()  # use whatever builtin constructor EU uses
    req = RunRequest(
        subject="Morning Briefing - 2026-06-02",
        template=tpl,
        provider_kind="anthropic",
        model="claude-opus-4-8",
        briefing_context=BriefingContext(run_date="2026-06-02", schedule_label="Pre-market"),
    )
    assert req.subject.startswith("Morning Briefing")
    assert req.briefing_context.schedule_label == "Pre-market"
    assert not hasattr(req, "trigger_context")


def test_run_request_rejects_empty_subject():
    tpl = TemplateSpec.builtin_default()
    with pytest.raises(ValidationError):
        RunRequest(subject="", template=tpl, provider_kind="anthropic", model="x")
```

> NOTE: Confirm the correct builtin `TemplateSpec` constructor by reading how `report_eu` tests build a template (grep `TemplateSpec` in `packages/core/tests/llm/runtime/report_eu/`). Use the same helper.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'BriefingContext'`.

- [ ] **Step 3: Apply schema deltas**

In `report_mb/schemas.py`:
1. Delete the `TriggerContext` class.
2. Add:

```python
class BriefingContext(BaseModel):
    """Recurring-briefing metadata handed to a run.

    For scheduled runs this is populated from the matched ``mb_schedules``
    row (label/time/timezone) plus the run date; for on-demand runs the
    route fills in the run date and any chosen schedule's label. Injected
    into the system prompt so the model knows which briefing it is writing
    before it calls any tool.
    """

    run_date: str = Field(..., min_length=1)
    schedule_label: str | None = None
    time_label: str | None = None
    timezone: str | None = None
```

3. In `RunRequest`: remove `trigger_context: TriggerContext | None`; add
   `briefing_context: BriefingContext | None = None`. Update the class docstring
   to describe a briefing subject (label) rather than a ticker. Remove any
   mention of `ticker_anchored`.
4. Update `__all__`: replace `"TriggerContext"` with `"BriefingContext"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
uv run ruff format packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git add packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git commit -m "feat(report-mb): fork EU engine schemas with BriefingContext"
```

### Task 1.3: `transports.py` — `MbDataTransports`

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_mb/transports.py`
- Test: `packages/core/tests/llm/runtime/report_mb/test_transports.py`

- [ ] **Step 1: Read the EU reference** — `packages/core/src/openlia/llm/runtime/report_eu/transports.py` to see the `EuDataTransports` dataclass shape (callable fields, types).

- [ ] **Step 2: Write failing test**

```python
from openlia.llm.runtime.report_mb.transports import MbDataTransports


def test_transports_holds_market_callables():
    t = MbDataTransports(
        quotes=lambda tickers: [{"ticker": tk, "price": 1.0} for tk in tickers],
        prices=lambda ticker, rng: [{"date": "2026-06-01", "close": 1.0}],
        news=lambda symbol=None: [{"title": "x"}],
        economic_calendar=lambda window: [{"event": "CPI"}],
        macro_indicators=lambda keys: {k: 1.0 for k in keys},
    )
    assert t.quotes(["AAPL.US"])[0]["ticker"] == "AAPL.US"
    assert t.news()[0]["title"] == "x"
    assert t.economic_calendar("7d")[0]["event"] == "CPI"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_transports.py -v`
Expected: FAIL — `ImportError: cannot import name 'MbDataTransports'`.

- [ ] **Step 4: Rewrite `transports.py`**

Replace the `EuDataTransports` dataclass with:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MbDataTransports:
    """Market-data callables the Morning Briefing engine may invoke.

    Server wires these from EODHD (or other connectors) in
    ``mb_v2_wiring``; tests inject fakes. Pure data plumbing — no network
    concern leaks into the engine.
    """

    quotes: Callable[[list[str]], list[dict[str, Any]]]
    prices: Callable[[str, str], list[dict[str, Any]]]
    news: Callable[..., list[dict[str, Any]]]
    economic_calendar: Callable[[str], list[dict[str, Any]]]
    macro_indicators: Callable[[list[str]], dict[str, Any]]
```

Then grep the rest of `report_mb/` for `EuDataTransports` and replace every
reference with `MbDataTransports` (in `runner.py`, `tools/`, `__init__.py`).

- [ ] **Step 5: Run transports + import tests**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/ -v`
Expected: `test_transports.py`, `test_schemas.py`, and `test_imports.py` all PASS (the import test green-lights now that both symbols are renamed).

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
uv run ruff format packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git add packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git commit -m "feat(report-mb): MbDataTransports market-data seam"
```

### Task 1.4: `tools/` — MB tool catalog

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_mb/tools/` (all modules)
- Test: `packages/core/tests/llm/runtime/report_mb/test_tools.py`

- [ ] **Step 1: Read the EU reference** — `report_eu/tools/` (data_tools, dispatcher_tools, output_tools, web_search) and how `runner.py` builds the catalog (`build_catalog`).

- [ ] **Step 2: Write failing catalog test**

```python
from openlia.llm.runtime.report_mb.schemas import EnabledConnectors
from openlia.llm.runtime.report_mb.tools import build_catalog  # adjust to actual export
from openlia.llm.runtime.report_mb.transports import MbDataTransports


def _fake_transports():
    return MbDataTransports(
        quotes=lambda tickers: [],
        prices=lambda ticker, rng: [],
        news=lambda symbol=None: [],
        economic_calendar=lambda window: [],
        macro_indicators=lambda keys: {},
    )


def test_catalog_has_market_tools_no_earnings_calendar():
    catalog = build_catalog(
        enabled=EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=False),
        transports=_fake_transports(),
        dispatcher=None,
    )
    names = set(catalog.by_name().keys())
    assert "get_quotes" in names
    assert "get_historical_prices" in names
    assert "get_news" in names
    assert "get_economic_calendar" in names
    assert "write_section" in names
    assert "set_cover" in names
    assert "get_earnings_calendar" not in names  # EU-only, dropped


def test_web_search_gated_off_when_disabled():
    catalog = build_catalog(
        enabled=EnabledConnectors(provider_ids=frozenset(), web_search=False),
        transports=_fake_transports(),
        dispatcher=None,
    )
    assert "web_search" not in catalog.by_name()
```

> Adjust tool names to match whatever convention EU uses (read `report_eu/tools/data_tools.py` for the exact `name=` strings and the `build_catalog` signature). Keep MB names parallel to EU but market-oriented.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_tools.py -v`
Expected: FAIL — earnings-calendar tool still present / quote tools missing.

- [ ] **Step 4: Edit the tool modules**

In `report_mb/tools/data_tools.py` (forked from EU):
1. Remove the `fundamentals` and `earnings_calendar` curated tools.
2. Add curated EODHD tools backed by `MbDataTransports`:
   - `get_quotes(tickers: list[str])` → `transports.quotes`
   - `get_historical_prices(ticker: str, range: str)` → `transports.prices`
   - `get_news(symbol: str | None = None)` → `transports.news`
   - `get_economic_calendar(window: str)` → `transports.economic_calendar`
   - `get_macro_indicators(keys: list[str])` → `transports.macro_indicators`
   Each appends a `CitationLogEntry` to the ledger exactly as EU's data tools do
   (copy the ledger-append + provenance pattern verbatim).
3. Keep `output_tools.py` (`write_section`, `emit_chart`, `set_cover`, finalize),
   `dispatcher_tools.py`, and `web_search.py` unchanged except for any
   `EuDataTransports` references.
4. Update `build_catalog` so the curated branch builds the MB tools when
   `enabled.eodhd` is set, dispatcher tools for other provider ids, and web
   search when `enabled.web_search`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_tools.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
uv run ruff format packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git add packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git commit -m "feat(report-mb): market-oriented connector-gated tool catalog"
```

### Task 1.5: `prompts.py` — briefing system prompt

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_mb/prompts.py`
- Test: `packages/core/tests/llm/runtime/report_mb/test_prompts.py`

- [ ] **Step 1: Read EU reference** — `report_eu/prompts.py` (how it injects template + trigger_context + instructions).

- [ ] **Step 2: Write failing prompt test**

```python
from openlia.llm.runtime.report_mb.prompts import build_system_prompt
from openlia.llm.runtime.report_mb.schemas import BriefingContext, RunRequest
from openlia.llm.runtime.report_v2_3.templates.spec import TemplateSpec


def test_prompt_mentions_briefing_date_and_label():
    req = RunRequest(
        subject="Morning Briefing - 2026-06-02",
        template=TemplateSpec.builtin_default(),
        provider_kind="anthropic",
        model="claude-opus-4-8",
        briefing_context=BriefingContext(
            run_date="2026-06-02", schedule_label="Pre-market briefing"
        ),
        instructions="Lead with US index futures.",
    )
    prompt = build_system_prompt(req, connector_prompt_info={})
    assert "2026-06-02" in prompt
    assert "Pre-market briefing" in prompt
    assert "US index futures" in prompt
    assert "earnings" not in prompt.lower()  # no earnings framing
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_prompts.py -v`
Expected: FAIL (earnings framing present / briefing context not injected).

- [ ] **Step 4: Rewrite the system-prompt body**

Reframe `build_system_prompt` to describe a recurring market-briefing analyst:
inject `briefing_context.run_date`, `schedule_label`, `time_label`/`timezone` when
present; inject the template skeleton and free-form `instructions`; keep the
citation discipline (Markdown footnotes against the ledger). Use positive phrasing
("write a clear, current briefing for {run_date}...") not prohibitions. Replace the
`trigger_context` block with the `briefing_context` block. Remove earnings/ticker
language.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_prompts.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
uv run ruff format packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git add packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git commit -m "feat(report-mb): briefing system prompt"
```

### Task 1.6: `runner.py` end-to-end loop test with fakes

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_mb/runner.py` (remove EU-only `trigger_context` wiring; pass `briefing_context`)
- Test: `packages/core/tests/llm/runtime/report_mb/test_runner.py`

- [ ] **Step 1: Read EU reference** — `report_eu/runner.py` and `report_eu` runner tests (`packages/core/tests/llm/runtime/report_eu/`) for the fake-session pattern (a stub LLM session that emits scripted tool calls then finalizes).

- [ ] **Step 2: Write failing runner test** — mirror the EU runner test that scripts: one data-tool call → one `write_section` → finalize, asserting `RunResult.status == "completed"` and one section present. Construct the `RunRequest` with `briefing_context` (no `trigger_context`). Inject `MbDataTransports` fakes.

```python
# Mirror packages/core/tests/llm/runtime/report_eu/test_runner.py exactly,
# swapping: RunRequest(subject="Morning Briefing - 2026-06-02", ...,
# briefing_context=BriefingContext(run_date="2026-06-02")) and MbDataTransports
# fakes. Assert RunResult.status == "completed" and len(result.sections) >= 1.
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/test_runner.py -v`
Expected: FAIL — `runner.py` still references `trigger_context`.

- [ ] **Step 4: Fix `runner.py`**

In `report_mb/runner.py`: replace every `trigger_context` reference with
`briefing_context`; ensure the runner passes `briefing_context` to
`build_system_prompt`; drop any earnings-calendar tool registration; keep the turn
loop, ledger, workspace, and event emission unchanged.

- [ ] **Step 5: Run full `report_mb` core suite**

Run: `uv run pytest packages/core/tests/llm/runtime/report_mb/ -v`
Expected: PASS (all of 1.1–1.6).

- [ ] **Step 6: Verify core stays library-only**

Run: `uv run python -c "from openlia.llm.runtime.report_mb import Runner, BriefingContext, MbDataTransports; print('ok')"`
Expected: prints `ok` (no FastAPI import error).

- [ ] **Step 7: Commit**

```bash
uv run ruff check --fix packages/core
uv run ruff format packages/core/src/openlia/llm/runtime/report_mb packages/core/tests/llm/runtime/report_mb
git add packages/core
git commit -m "feat(report-mb): end-to-end tool-use loop with fakes"
```

---

## Phase 2 — Data model & migrations

Goal: `report_mb*` tables, templates/instructions tables, `mb_schedules` config
columns, `repo_items.mb_v2_report_id`, seeded `mb_default` template, `mb_user_configs`
dropped. SQLAlchemy models + Alembic migration, both tested.

### Task 2.1: `report_mb` ORM models

**Files:**
- Create: `packages/server/src/openlia_server/db/models/report_mb.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py` (export new models)
- Test: `packages/server/tests/test_db/test_report_mb_models.py`

- [ ] **Step 1: Read EU reference** — `db/models/report_eu.py` (all 7 classes: `ReportEu`, `ReportEuSection`, `ReportEuChart`, `ReportEuCitation`, `ReportEuTemplate`, `ReportEuInstructions`, `ReportEuToolCallLog`).

- [ ] **Step 2: Write failing model test**

```python
from openlia_server.db.models.report_mb import (
    ReportMb,
    ReportMbInstructions,
    ReportMbTemplate,
)


def test_report_mb_columns():
    cols = ReportMb.__table__.columns.keys()
    assert {"id", "user_id", "subject", "trigger_kind", "schedule_id",
            "template_id", "instructions_id", "status", "created_at"} <= set(cols)
    assert "ticker" not in cols
    assert "fiscal_date" not in cols


def test_template_table_name():
    assert ReportMbTemplate.__tablename__ == "report_mb_templates"
    assert ReportMbInstructions.__tablename__ == "report_mb_instructions"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_db/test_report_mb_models.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 4: Create `report_mb.py` models**

Fork `report_eu.py`. Class/table renames: `ReportEu`→`ReportMb`/`report_mb`, and
the four children + two config tables analogously (`report_mb_sections`,
`report_mb_charts`, `report_mb_citations`, `report_mb_tool_call_log`,
`report_mb_templates`, `report_mb_instructions`). Column deltas on `ReportMb`:
remove `ticker`, `fiscal_date`; add `trigger_kind` (`scheduled`|`on_demand`),
`schedule_id` (`String(36)`, FK→`mb_schedules.id` `ondelete="SET NULL"`, nullable),
`instructions_id` (nullable). Keep `template_id`, `language`, `length`,
`provider_kind`, `model`, `reasoning_effort`, `status`, `error_message`,
`cover_json`, `created_at`, `completed_at`, and the `(user_id, created_at)` /
`(user_id, status)` indexes. Children and template/instructions tables are
structurally identical to EU (just renamed). Export all from `db/models/__init__.py`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_db/test_report_mb_models.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/db packages/server/tests/test_db
uv run ruff format packages/server/src/openlia_server/db packages/server/tests/test_db
git add packages/server/src/openlia_server/db packages/server/tests/test_db
git commit -m "feat(report-mb): ORM models mirroring report_eu"
```

### Task 2.2: Extend `MbSchedule` model with config binding

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/scheduler.py` (`MbSchedule`)
- Test: `packages/server/tests/test_db/test_mb_schedule_binding.py`

- [ ] **Step 1: Read** — current `MbSchedule` in `db/models/scheduler.py`.

- [ ] **Step 2: Write failing test**

```python
from openlia_server.db.models.scheduler import MbSchedule


def test_mb_schedule_has_config_binding_columns():
    cols = set(MbSchedule.__table__.columns.keys())
    assert {"template_id", "instructions_id", "enabled_connectors",
            "provider_kind", "model", "language", "length",
            "reasoning_effort", "web_search"} <= cols
    # existing scheduling columns retained
    assert {"time", "timezone", "days_of_week", "is_enabled", "last_run_at"} <= cols
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_db/test_mb_schedule_binding.py -v`
Expected: FAIL — new columns absent.

- [ ] **Step 4: Add the columns to `MbSchedule`**

```python
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    instructions_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    enabled_connectors: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provider_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    length: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    reasoning_effort: Mapped[str | None] = mapped_column(String(16), nullable=True)
    web_search: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

(Match existing import style in the file for `JSON`, `Boolean`, `String`, `Mapped`,
`mapped_column`. `enabled_connectors` JSON holds `{"provider_ids": [...],
"web_search": bool}` — `web_search` column is a denormalized convenience mirror;
keep both or drop the column and read from JSON. Prefer the explicit columns above
for queryability.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_db/test_mb_schedule_binding.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/db packages/server/tests/test_db
uv run ruff format packages/server/src/openlia_server/db packages/server/tests/test_db
git add packages/server/src/openlia_server/db packages/server/tests/test_db
git commit -m "feat(report-mb): per-schedule config binding columns"
```

### Task 2.3: `repo_items.mb_v2_report_id` pointer

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/content.py` (`RepoItem`)
- Test: `packages/server/tests/test_db/test_repo_item_mb.py`

- [ ] **Step 1: Write failing test**

```python
from openlia_server.db.models.content import RepoItem


def test_repo_item_has_mb_pointer():
    assert "mb_v2_report_id" in RepoItem.__table__.columns.keys()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_db/test_repo_item_mb.py -v`
Expected: FAIL.

- [ ] **Step 3: Add the column + update CHECK**

In `RepoItem`, after `eu_v2_report_id`:

```python
    mb_v2_report_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("report_mb.id", ondelete="CASCADE"),
        nullable=True,
    )
```

Update the polymorphic CHECK constraint (the "exactly one target set" rule) to
include `mb_v2_report_id` as a fifth allowed target, and update the docstring.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_db/test_repo_item_mb.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/db packages/server/tests/test_db
uv run ruff format packages/server/src/openlia_server/db packages/server/tests/test_db
git add packages/server/src/openlia_server/db packages/server/tests/test_db
git commit -m "feat(report-mb): repo_items.mb_v2_report_id pointer"
```

### Task 2.4: Alembic migration

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-06-02-XXXX_morning_briefing_v2.py`
- Test: `packages/server/tests/test_db/test_mb_migration.py`

- [ ] **Step 1: Read** — an EU migration that created `report_eu*` tables and one that altered a table, for the exact op style. Find the current head: `uv run alembic -c packages/server/alembic.ini heads` (or however the project invokes alembic — check `pyproject.toml`/CI). Identify `down_revision`.

- [ ] **Step 2: Write failing migration round-trip test**

```python
# Mirror an existing migration test in packages/server/tests/test_db/.
# Apply upgrade to a fresh SQLite/Postgres test DB, assert the tables exist:
#   report_mb, report_mb_sections, report_mb_charts, report_mb_citations,
#   report_mb_tool_call_log, report_mb_templates, report_mb_instructions
# assert mb_schedules has template_id column; assert repo_items has
# mb_v2_report_id; assert mb_user_configs is dropped; assert a builtin
# 'mb_default' row exists in report_mb_templates.
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_db/test_mb_migration.py -v`
Expected: FAIL — migration file absent.

- [ ] **Step 4: Author the migration**

`upgrade()`:
1. `create_table` for the seven `report_mb*` tables (copy column defs from the EU
   migration, applying the `ReportMb` deltas: drop ticker/fiscal_date, add
   trigger_kind/schedule_id/instructions_id).
2. `add_column` the nine config-binding columns on `mb_schedules`.
3. `add_column` `mb_v2_report_id` on `repo_items`; recreate the CHECK constraint
   to include it (drop + add, or batch op for SQLite).
4. `op.bulk_insert` one builtin `report_mb_templates` row (`id="mb_default"`,
   `is_builtin=True`, `user_id=None`, a general-briefing `template_spec_json`).
   Build the spec JSON from the same shape EU's builtin uses (read the EU builtin
   template seed); sections: Market Wrap, Macro & Economic Calendar, Headlines,
   Themes to Watch, Outlook.
5. `drop_table("mb_user_configs")`.

`downgrade()`: reverse in order (recreate `mb_user_configs`, drop the column/CHECK
additions, drop the seven tables).

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_db/test_mb_migration.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/db packages/server/tests/test_db
uv run ruff format packages/server/src/openlia_server/db packages/server/tests/test_db
git add packages/server/src/openlia_server/db packages/server/tests/test_db
git commit -m "feat(report-mb): alembic migration for MB v2 schema"
```

---

## Phase 3 — Server services & scheduler rewire

Goal: `mb_v2_*` services + executor rewired to the new engine, repo fan-out, all
tested with fakes.

### Task 3.1: `mb_v2_template_service` + `mb_v2_instructions_service`

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_v2_template_service.py`
- Create: `packages/server/src/openlia_server/services/mb_v2_instructions_service.py`
- Test: `packages/server/tests/test_services/test_mb_v2_templates.py`
- Test: `packages/server/tests/test_services/test_mb_v2_instructions.py`

- [ ] **Step 1: Read EU reference** — `eu_v2_template_service.py`, `eu_v2_instructions_service.py`.

- [ ] **Step 2: Write failing tests** — mirror the EU service tests: create a
  template from markdown → `list_templates` returns builtin + the new one;
  `resolve_template("mb_default")` returns a `TemplateSpec`; soft-delete hides it;
  same for instructions (`create_instructions_from_upload` → `resolve_instructions`
  returns body text). Use a test DB session fixture (reuse the EU test fixture
  pattern).

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_templates.py packages/server/tests/test_services/test_mb_v2_instructions.py -v`
Expected: FAIL — modules absent.

- [ ] **Step 4: Fork the EU services**

Copy `eu_v2_template_service.py` → `mb_v2_template_service.py`, swap
`ReportEuTemplate` → `ReportMbTemplate` and the builtin id (`eu_default` →
`mb_default`). Same for instructions (`ReportEuInstructions` → `ReportMbInstructions`).
Keep the parsing/compile/soft-delete logic identical (it is department-agnostic).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_templates.py packages/server/tests/test_services/test_mb_v2_instructions.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services packages/server/tests/test_services
uv run ruff format packages/server/src/openlia_server/services packages/server/tests/test_services
git add packages/server/src/openlia_server/services packages/server/tests/test_services
git commit -m "feat(report-mb): template + instructions services"
```

### Task 3.2: `mb_v2_wiring` (EODHD market transports) + `mb_v2_data_sources`

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_v2_wiring.py`
- Create: `packages/server/src/openlia_server/services/mb_v2_data_sources.py`
- Test: `packages/server/tests/test_services/test_mb_v2_wiring.py`
- Test: `packages/server/tests/test_services/test_mb_v2_data_sources.py`

- [ ] **Step 1: Read EU reference** — `eu_v2_wiring.py` (`build_eu_v2_transports`, `resolve_eodhd_api_key`), `eu_v2_data_sources.py`.

- [ ] **Step 2: Write failing tests** — `build_mb_transports(api_key=...)` returns an
  `MbDataTransports` whose `quotes`/`prices`/`news`/`economic_calendar` callables
  invoke the EODHD client adapter; `compute_data_sources(enabled)` returns the
  available/enabled/routing list (curated for eodhd, model_native for web search).
  Mirror EU's wiring test with fakes/mocks for the EODHD client.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_wiring.py packages/server/tests/test_services/test_mb_v2_data_sources.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement**

`mb_v2_wiring.build_mb_transports`: reuse `resolve_eodhd_api_key` from
`eu_v2_wiring` (import it — do not duplicate); build `MbDataTransports` callables
that map to the EODHD endpoints for multi-ticker quotes, historical prices, news,
economic calendar, macro indicators (reuse `eodhd_payload.py` /
`connector_financial_adapter.py` helpers where they exist; read those files to
find the right call). `mb_v2_data_sources.compute_data_sources`: fork EU's logic
(it is engine-agnostic — only the provider set differs).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_wiring.py packages/server/tests/test_services/test_mb_v2_data_sources.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services packages/server/tests/test_services
uv run ruff format packages/server/src/openlia_server/services packages/server/tests/test_services
git add packages/server/src/openlia_server/services packages/server/tests/test_services
git commit -m "feat(report-mb): EODHD market transports + data sources"
```

### Task 3.3: `mb_v2_run_service` (build request, run, persist)

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_v2_run_service.py`
- Test: `packages/server/tests/test_services/test_mb_v2_run_service.py`

- [ ] **Step 1: Read EU reference** — `eu_v2_run_service.py` (`build_run_request`, `insert_report_row`, `start_run_async`, `persist_result`).

- [ ] **Step 2: Write failing tests** — (a) `build_run_request` from a schedule's
  bound config + resolved template/instructions yields a `report_mb.RunRequest`
  with the right `subject`, `briefing_context`, `enabled_connectors`, `model`;
  (b) `persist_result` writes `ReportMb` + sections/charts/citations and flips
  status to `completed`; (c) `insert_report_row` creates a `running` row and does
  NOT create a `repo_items` pointer (briefings list from `report_mb` directly;
  the pointer is created only on explicit save — see Task 3.7, mirroring EU). Use
  a fake engine `Runner` that yields a scripted `RunResult` (inject it, mirroring
  how EU tests stub the runner).

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_run_service.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement** — fork `eu_v2_run_service.py`. Swap: `report_eu` engine
  imports → `report_mb`; `ReportEu*` models → `ReportMb*`; `TriggerContext` build →
  `BriefingContext` build (from schedule label/time/tz + run date). Do NOT create a
  `repo_items` pointer here (EU's run service does not touch repo_items either).
  `build_run_request` accepts either a schedule row or an ad-hoc on-demand config
  dict. Resolve template via `mb_v2_template_service`, instructions via
  `mb_v2_instructions_service`, transports via `mb_v2_wiring`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_run_service.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services packages/server/tests/test_services
uv run ruff format packages/server/src/openlia_server/services packages/server/tests/test_services
git add packages/server/src/openlia_server/services packages/server/tests/test_services
git commit -m "feat(report-mb): run service (build/run/persist)"
```

### Task 3.4: `mb_v2_render_service` (html/docx/pdf)

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_v2_render_service.py`
- Test: `packages/server/tests/test_services/test_mb_v2_render.py`

- [ ] **Step 1: Read EU reference** — `eu_v2_render_service.py`, `eu_v2_docx.py`, `eu_v2_filename.py`. Identify what is earnings-specific (cover fields, filename subject) vs generic.

- [ ] **Step 2: Write failing test** — `render_html(report_id)` on a persisted
  `ReportMb` returns HTML containing the subject and section titles;
  `build_download_filename` returns `Subject_Template_Date.html`. Mirror EU's render
  test.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_render.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement** — fork `eu_v2_render_service.py` + `eu_v2_docx.py` +
  `eu_v2_filename.py`, swapping `ReportEu*` → `ReportMb*`. The HTML/markdown/chart
  assembly is generic — reuse the core engine's `rendering/` assembler (already
  forked into `report_mb/rendering/`). Filename subject uses the briefing label.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_render.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services packages/server/tests/test_services
uv run ruff format packages/server/src/openlia_server/services packages/server/tests/test_services
git add packages/server/src/openlia_server/services packages/server/tests/test_services
git commit -m "feat(report-mb): render service (html/docx/pdf)"
```

### Task 3.5: `mb_v2_schedules` service (CRUD + hot-reload)

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_v2_schedules.py`
- Test: `packages/server/tests/test_services/test_mb_v2_schedules.py`

- [ ] **Step 1: Read** — the existing `mb_schedules.py` (CRUD + `SchedulerControl`
  hot-reload protocol). This service is being extended to carry config bindings;
  create `mb_v2_schedules.py` as its replacement (or extend in place — prefer a new
  file and delete the old in Phase 6).

- [ ] **Step 2: Write failing test** — `create_schedule` with template/instructions/
  connectors/model/time/days persists all binding fields and calls
  `scheduler.add_schedule`; `update_schedule` re-binds and calls `modify_schedule`;
  `list_schedules` returns DTOs including binding fields; `delete_schedule` calls
  `remove_schedule`. Use a fake `SchedulerControl`.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_schedules.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement** — fork `mb_schedules.py`; extend the DTO and create/update
  signatures with the binding fields; validate `time`/`timezone`/`days_of_week` as
  before; validate `template_id`/`instructions_id` exist (resolvable) and
  `enabled_connectors` shape. Keep the `SchedulerControl` calls.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_services/test_mb_v2_schedules.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services packages/server/tests/test_services
uv run ruff format packages/server/src/openlia_server/services packages/server/tests/test_services
git add packages/server/src/openlia_server/services packages/server/tests/test_services
git commit -m "feat(report-mb): schedule service with config binding"
```

### Task 3.6: Rewire `MBBriefingExecutor` + scheduler wiring

**Files:**
- Modify: `packages/server/src/openlia_server/scheduler/executors/mb.py`
- Modify: `packages/server/src/openlia_server/scheduler/wiring.py`
- Modify: `packages/server/src/openlia_server/scheduler/payloads.py` (drop `MBRequestBuilder`/`ReportStore` protocols if now unused by MB)
- Test: `packages/server/tests/test_scheduler/test_mb_executor.py`

- [ ] **Step 1: Read** — current `executors/mb.py` (already in context), `wiring.py`, `scheduler/payloads.py`, and `scheduler/executors/base.py` (`BaseExecutor`, `JobOutcome`, `NotificationSpec`).

- [ ] **Step 2: Write failing test** — a fake `mb_v2_run_service` whose
  `run_scheduled(session, schedule_id, user_id, ...)` returns a `report_id`;
  assert the executor calls it for the due schedule, sets `last_run_at`, and emits a
  `REPORT_READY` notification with the schedule label. (Mirror existing executor
  tests in `packages/server/tests/test_scheduler/`.)

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_scheduler/test_mb_executor.py -v`
Expected: FAIL.

- [ ] **Step 4: Rewrite `_do_work`** — replace the `mb_builder`/`report_runner`/
  `report_store` pipeline with a single call into `mb_v2_run_service` that builds the
  request from the schedule's bound config, runs the `report_mb` engine, persists to
  `report_mb`, inserts the `repo_items` pointer, and returns `report_id`. Keep
  `JobType.MB_BRIEFING`, `last_run_at`, and the `REPORT_READY` notification. Update
  the constructor deps. Update `wiring.py` to inject the new service. Remove the now
  unused `MBRequestBuilder`/`ReportStore` injection for MB (leave them if other
  departments use them — grep first).

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_scheduler/test_mb_executor.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/scheduler packages/server/tests/test_scheduler
uv run ruff format packages/server/src/openlia_server/scheduler packages/server/tests/test_scheduler
git add packages/server/src/openlia_server/scheduler packages/server/tests/test_scheduler
git commit -m "feat(report-mb): rewire cron executor to report_mb engine"
```

### Task 3.7: Repo save/unsave/list integration for MB

Mirror EU end-to-end: the run service never creates a `repo_items` pointer; the
pointer is created on explicit save. So MB needs the same three repo seams EU has —
`save_mb_report_to_repo`, `unsave_mb_report_from_repo`, and the listing join — plus
the `routes/repo.py` wiring.

**Files:**
- Modify: `packages/server/src/openlia_server/services/repo.py`
- Modify: `packages/server/src/openlia_server/routes/repo.py`
- Test: `packages/server/tests/test_services/test_repo_mb_listing.py`

- [ ] **Step 1: Read** — `services/repo.py` (the EU functions `save_eu_report_to_repo`,
  `unsave_eu_report_from_repo`, and the `eu_v2_report_id` listing join at the
  `select(...).join(ReportEu, RepoItem.eu_v2_report_id == ReportEu.id)` sites) and
  `routes/repo.py` (the EU save/unsave/list endpoints).

- [ ] **Step 2: Write failing tests** — (a) `save_mb_report_to_repo(db, user_id, mb_report_id)`
  creates exactly one `repo_items` row with `mb_v2_report_id` set; calling it twice is
  idempotent (no duplicate); (b) with a saved `ReportMb`, `list_items_filtered(user_id=...)`
  includes the MB report in the merged result with department `"morning_briefing"` and the
  right title; (c) `unsave_mb_report_from_repo` removes the pointer.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_repo_mb_listing.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement** — add `save_mb_report_to_repo` / `unsave_mb_report_from_repo`
  (mirror the EU functions, swapping `eu_v2_report_id` → `mb_v2_report_id`, `ReportEu` →
  `ReportMb`), and add the MB branch to the listing fan-out (join `report_mb`, map to the
  common `RepoRow` shape, department `"morning_briefing"`). Wire the matching
  save/unsave/list endpoints into `routes/repo.py` mirroring the EU ones.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_services/test_repo_mb_listing.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services packages/server/tests/test_services
uv run ruff format packages/server/src/openlia_server/services packages/server/tests/test_services
git add packages/server/src/openlia_server/services packages/server/tests/test_services
git commit -m "feat(report-mb): repo listing fan-out"
```

---

## Phase 4 — Route rewrite

Goal: rewrite `routes/departments/morning_briefing.py` in the EU v2 shape, tested.

### Task 4.1: Schedules + templates + instructions + data-sources endpoints

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/morning_briefing.py`
- Test: `packages/server/tests/test_routes/departments/test_morning_briefing_config.py`

- [ ] **Step 1: Read EU reference** — `routes/departments/earnings_update_v2.py` (router factory, Pydantic In/Out models, dependency injection, upload handling).

- [ ] **Step 2: Write failing route tests** (use the server `TestClient` fixture):
  `POST /departments/morning-briefing/schedules` with a full binding returns 201 and
  echoes the binding; `GET /schedules` lists it; `PATCH` updates; `DELETE` returns
  204; `GET /templates` returns the builtin `mb_default`; `POST /templates` (markdown)
  creates one; `GET /instructions`; `GET /data-sources` returns the connector list.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_morning_briefing_config.py -v`
Expected: FAIL.

- [ ] **Step 4: Rewrite the router** — replace the old config/schedule handlers. Add
  In/Out models for schedules (with binding fields), templates, instructions,
  data-sources. Wire to `mb_v2_schedules`, `mb_v2_template_service`,
  `mb_v2_instructions_service`, `mb_v2_data_sources`. Keep the factory-pattern and
  auth dependencies the EU route uses.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_morning_briefing_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/routes packages/server/tests/test_routes
uv run ruff format packages/server/src/openlia_server/routes packages/server/tests/test_routes
git add packages/server/src/openlia_server/routes packages/server/tests/test_routes
git commit -m "feat(report-mb): config/schedule/template/instructions routes"
```

### Task 4.2: Runs lifecycle + SSE + downloads endpoints

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/morning_briefing.py`
- Test: `packages/server/tests/test_routes/departments/test_morning_briefing_runs.py`

- [ ] **Step 1: Read EU reference** — the runs/events/downloads handlers in `earnings_update_v2.py`.

- [ ] **Step 2: Write failing tests** — `POST /runs/start` with `{schedule_id}`
  returns `{report_id}` and creates a `running` row; `GET /runs` lists summaries;
  `GET /runs/{id}` returns detail (sections/cover); `DELETE /runs/{id}` hard-deletes;
  `GET /runs/{id}/html` returns HTML. (Skip a live SSE assertion — the suite hangs on
  streaming; assert the events endpoint is registered via `app.routes` instead.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_morning_briefing_runs.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement** the runs handlers wiring to `mb_v2_run_service`
  (`start_run_async`) and `mb_v2_render_service`. `POST /runs/start` accepts either a
  `schedule_id` (reuse its config) or an ad-hoc config body. Mirror EU's SSE events
  handler and download handlers.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_morning_briefing_runs.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check --fix packages/server/src/openlia_server/routes packages/server/tests/test_routes
uv run ruff format packages/server/src/openlia_server/routes packages/server/tests/test_routes
git add packages/server/src/openlia_server/routes packages/server/tests/test_routes
git commit -m "feat(report-mb): run lifecycle + events + download routes"
```

---

## Phase 5 — Frontend rework

Goal: rewrite the MB page in the EU shape, reusing EU components, tested + tsc-clean +
bilingual.

### Task 5.1: API client + types

**Files:**
- Rewrite: `frontend/src/api/morning-briefing.ts`
- Test: `frontend/src/api/__tests__/morning-briefing.test.ts` (if API tests exist; else cover via page tests)

- [ ] **Step 1: Read EU reference** — `frontend/src/api/earnings-update.ts` (types + fetch wrappers).

- [ ] **Step 2: Write failing test (or type-check target)** — a test importing the new
  types (`MbSchedule`, `MbRunSummary`, `MbTemplate`, `MbInstructions`, `MbDataSource`)
  and asserting `startMbRun`/`getMbRuns`/`createMbSchedule` exist. If the repo has no
  api unit tests, skip the test and rely on `tsc` + page tests; note that here.

- [ ] **Step 3: Run** `cd frontend && npx tsc --noEmit` — Expected: FAIL (missing exports).

- [ ] **Step 4: Implement** — fork `earnings-update.ts`: types + fetchers against
  `/api/departments/morning-briefing/*` (schedules with binding, templates,
  instructions, data-sources, runs start/list/detail/delete/cancel, events URL,
  download URLs).

- [ ] **Step 5: Run** `cd frontend && npx tsc --noEmit` — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && npx prettier --write src/api/morning-briefing.ts && cd ..
git add frontend/src/api/morning-briefing.ts
git commit -m "feat(report-mb): frontend api client"
```

### Task 5.2: Hooks

**Files:**
- Create: `frontend/src/hooks/useMbSchedules.ts`, `useMbRuns.ts`, `useMbRunStream.ts`, `useMbTemplates.ts`, `useMbInstructions.ts`, `useMbDataSources.ts`
- Test: `frontend/src/hooks/__tests__/useMbRuns.test.tsx` (mirror EU hook tests)

- [ ] **Step 1: Read EU reference** — `useEuSchedule`, `useEuRuns`, `useEuRunStream`, `useEuSettings` hooks.

- [ ] **Step 2: Write a failing hook test** — `useMbRuns` fetches + exposes
  `{runs, refresh, loading}` (mock fetch). Mirror the EU hook test.

- [ ] **Step 3: Run** `cd frontend && npx vitest run src/hooks/__tests__/useMbRuns.test.tsx` — Expected: FAIL.

- [ ] **Step 4: Implement** the hooks (fork EU hooks, swap API calls/types).

- [ ] **Step 5: Run** the hook test — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && npx prettier --write src/hooks/useMb*.ts src/hooks/__tests__/useMbRuns.test.tsx && cd ..
git add frontend/src/hooks
git commit -m "feat(report-mb): frontend data hooks"
```

### Task 5.3: Components — feed, generating card, schedule editor, upload modals, cabinet

**Files:**
- Create: `frontend/src/components/morning-briefing/` (feed cards, generating card, schedule editor, template/instructions upload modals, cabinet view) — fork the EU components under `frontend/src/components/equity-research-*`/EU components, reusing generic ones (`ConfirmDialog`, viewer) directly.
- Test: `frontend/src/components/morning-briefing/__tests__/*.test.tsx`

- [ ] **Step 1: Read EU reference** — the EU components: feed (`EuBigCard`, `EuReportRow`, `EuGeneratingCard`, `EuFeedSection`), `ReportSettingsModal`, `EuTemplateUploadModal`, `EuInstructionsUploadModal`, `EUCabinetView`, `CoverageDrawer`. Identify earnings-specific bits (ticker, fiscal date, up-next/calendar) to drop.

- [ ] **Step 2: Write failing component tests** — (a) a briefing feed card renders
  subject + highlights; (b) the generating card shows streaming phase and hides when
  not live; (c) the schedule editor renders the binding controls (template select,
  instructions select, connector toggles, model picker, time/days). Mirror existing
  EU/MB component tests.

- [ ] **Step 3: Run** `cd frontend && npx vitest run src/components/morning-briefing` — Expected: FAIL.

- [ ] **Step 4: Implement** the components (fork EU, drop ticker/calendar/up-next,
  add the schedule binding editor; reuse `ConfirmDialog` + viewer delete flow shipped
  for EU). Add `en` + `zh-TW` i18n keys for all copy.

- [ ] **Step 5: Run** the component tests — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && npx prettier --write src/components/morning-briefing && cd ..
git add frontend/src/components/morning-briefing frontend/src/i18n
git commit -m "feat(report-mb): feed, generating card, schedule editor, modals"
```

### Task 5.4: Page assembly — rewrite `MorningBriefing.tsx`

**Files:**
- Rewrite: `frontend/src/pages/departments/MorningBriefing.tsx`
- Rewrite: `frontend/src/pages/departments/MorningBriefing.test.tsx`

- [ ] **Step 1: Read EU reference** — `EarningsUpdate.tsx` page composition.

- [ ] **Step 2: Write failing page test** — renders the feed, opens the schedule
  editor, opens "Run now", opens the cabinet (templates/instructions). Mock the
  hooks. Mirror `EarningsUpdate.test.tsx`.

- [ ] **Step 3: Run** `cd frontend && npx vitest run src/pages/departments/MorningBriefing.test.tsx` — Expected: FAIL.

- [ ] **Step 4: Implement** — compose the page from the hooks + components: feed +
  live generating card + viewer (with delete), schedule editor, run-now modal,
  cabinet. Remove the old 4-tab/sections-config UI.

- [ ] **Step 5: Run** the page test + `npx tsc --noEmit` — Expected: PASS, clean.

- [ ] **Step 6: Commit**

```bash
cd frontend && npx prettier --write src/pages/departments/MorningBriefing.tsx src/pages/departments/MorningBriefing.test.tsx && cd ..
git add frontend/src/pages/departments/MorningBriefing.tsx frontend/src/pages/departments/MorningBriefing.test.tsx
git commit -m "feat(report-mb): rewrite Morning Briefing page in EU shape"
```

---

## Phase 6 — Cleanup & final verification

### Task 6.1: Delete old MB code

> **Sequencing note (revised during execution):** Phase 2's migration intentionally does NOT drop `mb_user_configs` — doing so while the `MbUserConfig` model still exists would leave the migration-parity and alembic-hygiene guardrail tests red through Phases 3-5. This task removes the `MbUserConfig` model AND adds a new migration that drops the `mb_user_configs` table, atomically, so metadata and the alembic head stay in sync.

**Files:**
- Delete: `packages/server/src/openlia_server/services/mb_config.py`, `mb_request_builder.py`, old `mb_schedules.py` (if replaced by `mb_v2_schedules.py`)
- Delete: `MbUserConfig` model + its export; add a new alembic migration `<timestamp>_drop_mb_user_configs.py` (down_revision = `morning_briefing_v2` or the latest head) that `drop_table("mb_user_configs")` in upgrade and recreates it in downgrade (original shape — copy from the now-removed recreate block in git history of the `morning_briefing_v2` migration). Update `EXPECTED_TABLES` in `test_migrations.py` to remove `mb_user_configs`.
- Delete: old MB frontend components no longer imported (`frontend/src/components/morning-briefing/` legacy files: `MBArchiveView`, `MBRunNowView`, `MBSettingsView`, `MBScheduleView` if superseded, `MBSettings` sections UI)
- Modify: `packages/core/src/openlia/prompts/morning_briefing.yaml` — remove the report-mode prompt blocks (keep chat mode only if still referenced by Secretary; grep first)
- Modify: any imports referencing deleted modules

- [ ] **Step 1: Grep for references** to each deletion target:

Run: `grep -rn "mb_config\|mb_request_builder\|MBRequestBuilder\|mb_user_configs\|MbUserConfig" packages/ frontend/src`
Resolve each reference before deleting.

- [ ] **Step 2: Delete the files** and fix imports. For `morning_briefing.yaml`,
  confirm whether the `chat:system` mode is still used (grep `morning_briefing` in
  prompt loaders / Secretary); keep that block, remove the `report:*` blocks.

- [ ] **Step 3: Run the targeted suites**

Run:
```
uv run pytest packages/core/tests/llm/runtime/report_mb packages/core/tests/departments -v
uv run pytest packages/server/tests/test_db packages/server/tests/test_services packages/server/tests/test_scheduler packages/server/tests/test_routes/departments -v
cd frontend && npx vitest run && npx tsc --noEmit && cd ..
```
Expected: all PASS, tsc clean.

- [ ] **Step 4: Lint + format whole repo**

Run: `uv run ruff check --fix . && uv run ruff format .`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(report-mb): remove legacy MB engine, config, prompt, UI"
```

### Task 6.2: Department-level smoke + spec reconciliation

- [ ] **Step 1: Verify core import boundary**

Run: `uv run python -c "from openlia.departments.morning_briefing import MorningBriefingDepartment; from openlia.llm.runtime.report_mb import Runner; print('ok')"`
Expected: `ok`.

- [ ] **Step 2: Run the migration forward on a scratch DB** (mirror how CI applies
  migrations) and confirm `report_mb` + builtin `mb_default` exist and
  `mb_user_configs` is gone.

- [ ] **Step 3: Reconcile the spec** — if implementation diverged, update
  `docs/superpowers/specs/2026-06-02-morning-briefing-rework-design.md` (CLAUDE.md
  rule 9).

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "docs(report-mb): reconcile spec with implementation"
```

---

## Self-Review notes (author)

- **Spec coverage:** Engine (P1) ✓, data model incl. mb_schedules binding + repo
  pointer + dropped mb_user_configs (P2) ✓, services incl. run/render/templates/
  instructions/data-sources/wiring/schedules + executor rewire + repo fan-out (P3) ✓,
  route rewrite incl. runs/SSE/downloads (P4) ✓, frontend incl. feed/generating/
  schedule-editor/cabinet/upload (P5) ✓, removal of legacy code (P6) ✓.
- **Known unknowns to resolve at execution time (read the named reference file
  first):** exact `TemplateSpec` builtin constructor, exact EU tool `name=` strings
  and `build_catalog` signature, exact EODHD adapter call surface for market data,
  exact alembic invocation/head, exact EU test fixtures. Each task names the
  reference file to read.
- **Type consistency:** `BriefingContext`, `MbDataTransports`, `ReportMb*`,
  `mb_v2_*`, `mb_v2_report_id` used consistently across phases.
- **Server suite hang:** every server test step targets a specific dir/file; no bare
  `uv run pytest packages/server/`.
