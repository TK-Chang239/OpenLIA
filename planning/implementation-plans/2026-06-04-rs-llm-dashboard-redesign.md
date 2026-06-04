# Retail Sentiment LLM-Dashboard Redesign (`report_dash_rs`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Retail Sentiment as `report_dash_rs` — the `report_dash_mr` sibling engine (web-search backbone, LLM tool loop → one typed payload), ship the single-ticker sentiment overview end-to-end, and delete the inert per-post pipeline.

**Architecture:** Core engine mirrors `report_dash_mr`, re-importing its department-agnostic submodules and adding only RS-specific files (payload, quant, prompts, registry, runner). Server gets a run service + cache table + MR-shaped routes; the existing `RS_SNAPSHOT` executor is repointed. Frontend reshapes to the polled single-ticker view. The old per-post stack (RsRunner, batch classifier, 12-metric engine, `rs_snapshots`/`rs_classification_log`) is removed.

**Tech Stack:** Python 3.12 + Pydantic + SQLAlchemy/Alembic (core/server), React/TS/Vite + Vitest (frontend), `uv` + `ruff` + `pytest`.

**Spec:** `planning/specs/systems/retail-sentiment-llm-dashboard-redesign.md` (read it first). MR template: `packages/core/src/openlia/llm/runtime/report_dash_mr/`, `services/mr_dash_run_service.py`, `routes/departments/macro_research.py`, `frontend/src/pages/departments/MacroResearch.tsx`.

**Branch:** `feat/rs-llm-dashboard-redesign` (already created; spec already committed).

**Conventions for every task:** `uv run ruff check --fix . && uv run ruff format .` before each commit. No emojis. Modern strict type hints. Commit at the end of each task.

---

## Phase 1 — Core engine (`report_dash_rs`)

New package dir: `packages/core/src/openlia/llm/runtime/report_dash_rs/`. The guiding rule: **import from `report_dash_mr` anything department-agnostic; create a new file only where RS content differs.** Files to CREATE new: `__init__.py`, `schemas.py`, `quant.py`, `prompts.py`, `runner.py`, `tools/__init__.py`, `tools/dashboard_tools.py`, `tools/registry.py`. Files to REUSE by import (do NOT copy): `session`, `ledger`, `events`, `workspace`, `transports`, `tools/web_search`, `tools/dispatcher_tools`.

### Task 1: Payload schema

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_dash_rs/__init__.py`
- Create: `packages/core/src/openlia/llm/runtime/report_dash_rs/schemas.py`
- Test: `packages/core/tests/test_llm/test_runtime/report_dash_rs/test_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# test_schemas.py
from openlia.llm.runtime.report_dash_rs.schemas import (
    EvidenceItem,
    RetailSentimentData,
    Signal,
)


def test_retail_sentiment_data_minimal_valid():
    data = RetailSentimentData(
        subject="AAPL",
        sentiment_score=0.42,
        direction="bullish",
        buzz_level="elevated",
        buzz_note="Active discussion on earnings beat.",
        bull_pct=70.0,
        bear_pct=20.0,
        narratives=["earnings beat", "guidance raise"],
        signals=[Signal(name="FOMO / crowding", severity="caution", note="High buzz + bullish tone.")],
        evidence=[EvidenceItem(title="AAPL pops", url="https://x", source="reddit", classification="bullish")],
        narrative="Retail tone is bullish into the print.",
    )
    assert data.subject == "AAPL"
    assert data.momentum is None  # optional, history-derived
    assert data.aggregated_sentiment is None  # optional connector cross-check


def test_sentiment_score_out_of_range_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RetailSentimentData(
            subject="AAPL", sentiment_score=2.0, direction="bullish",
            buzz_level="low", buzz_note="", bull_pct=1, bear_pct=0,
            narratives=[], signals=[], evidence=[], narrative="",
        )
```

- [ ] **Step 2: Run it, expect ImportError/fail**

Run: `cd packages/core && uv run pytest tests/test_llm/test_runtime/report_dash_rs/test_schemas.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `__init__.py` + `schemas.py`**

`schemas.py` — re-export the department-agnostic run types from MR, define RS payload models:

```python
"""Typed contracts for the report_dash_rs engine.

Run-level types (RunRequest/RunResult/EnabledConnectors/...) are shared with
report_dash_mr and re-exported here so the engine's relative imports resolve.
Only the RS dashboard payload is RS-specific.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Shared, department-agnostic run types — single source of truth in report_dash_mr.
from ..report_dash_mr.schemas import (  # noqa: F401
    ChartDataPoint,
    ChartSpec,
    ChartType,
    CitationLogEntry,
    EnabledConnectors,
    RunRequest,
    RunResult,
    RunStatus,
)


class Signal(BaseModel):
    name: str
    severity: Literal["info", "caution", "alert"]
    note: str


class EvidenceItem(BaseModel):
    title: str
    url: str
    source: str
    classification: Literal["bullish", "bearish", "neutral"]
    published_at: str | None = None


class RetailSentimentData(BaseModel):
    """Single-ticker retail-sentiment dashboard payload."""

    subject: str  # ticker
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    direction: Literal["bullish", "bearish", "neutral"]
    momentum: float | None = None  # history-derived; null until >= 2 snapshots
    trend_label: str | None = None
    buzz_level: Literal["low", "elevated", "high"]
    buzz_note: str
    bull_pct: float = Field(ge=0.0, le=100.0)
    bear_pct: float = Field(ge=0.0, le=100.0)
    narratives: list[str]
    signals: list[Signal]
    evidence: list[EvidenceItem]
    narrative: str
    # Optional connector cross-checks — null/hidden when unavailable.
    aggregated_sentiment: float | None = None
    analyst_gap: float | None = None
    captured_at: str | None = None
```

`__init__.py` — public API (re-export shared + RS):

```python
"""report_dash_rs: Retail Sentiment dashboard engine (report_dash_mr sibling)."""

from __future__ import annotations

# Shared engine infrastructure (single source of truth in report_dash_mr).
from ..report_dash_mr import (  # noqa: F401
    CancelToken,
    EnabledConnectors,
    EventBroker,
    EventEmitter,
    LLMSession,
    MbDataTransports,
    NullEmitter,
)
from .runner import Runner
from .schemas import EvidenceItem, RetailSentimentData, RunRequest, RunResult, RunStatus, Signal
from .tools.dashboard_tools import (
    PAYLOAD_MODEL_BY_SLUG,
    CLASSIFY_TOOL_BY_SLUG,
    implemented_dashboard_slugs,
)

__all__ = [
    "Runner", "RunRequest", "RunResult", "RunStatus", "EnabledConnectors",
    "LLMSession", "NullEmitter", "CancelToken", "MbDataTransports",
    "EventEmitter", "EventBroker", "RetailSentimentData", "Signal", "EvidenceItem",
    "PAYLOAD_MODEL_BY_SLUG", "CLASSIFY_TOOL_BY_SLUG", "implemented_dashboard_slugs",
]
```

> Note: `__init__.py` imports `runner` and `tools.dashboard_tools`, created in Tasks 3 & 5. Until then this task's test imports only `schemas`, which has no such dependency — so Step 4 passes. Verify the exact re-export names against `report_dash_mr/__init__.py` and `report_dash_mr/schemas.py`; adjust the import lists to match what actually exists there.

- [ ] **Step 4: Run the schema test, expect PASS**

Run: `cd packages/core && uv run pytest tests/test_llm/test_runtime/report_dash_rs/test_schemas.py -q`
Expected: PASS. (Create `tests/test_llm/test_runtime/report_dash_rs/__init__.py` if the test dir needs it.)

- [ ] **Step 5: Commit** — `feat(report-dash-rs): RetailSentimentData payload schema`

### Task 2: Deterministic quant (`quant.py`)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_dash_rs/quant.py`
- Test: `packages/core/tests/test_llm/test_runtime/report_dash_rs/test_quant.py`

- [ ] **Step 1: Write the failing test**

```python
from openlia.llm.runtime.report_dash_rs.quant import (
    RetailSentimentInputs,
    classify_retail_sentiment,
    momentum_from_history,
)


def test_classify_bullish():
    out = classify_retail_sentiment(
        RetailSentimentInputs(bullish=70, bearish=20, neutral=10, buzz_level="elevated")
    )
    assert out.direction == "bullish"
    assert abs(out.sentiment_score - 0.5) < 1e-9  # (70-20)/100
    assert abs(out.bull_pct - 70.0) < 1e-9


def test_classify_zero_volume_is_neutral():
    out = classify_retail_sentiment(
        RetailSentimentInputs(bullish=0, bearish=0, neutral=0, buzz_level="low")
    )
    assert out.direction == "neutral"
    assert out.sentiment_score == 0.0
    assert out.signals == []


def test_panic_signal_high_buzz_negative_tone():
    out = classify_retail_sentiment(
        RetailSentimentInputs(bullish=10, bearish=70, neutral=20, buzz_level="high")
    )
    assert any(s["name"].lower().startswith("panic") for s in out.signals)


def test_momentum_from_history():
    m, label = momentum_from_history([0.1, 0.2, 0.45])
    assert m is not None and m > 0
    assert label == "improving"
    assert momentum_from_history([0.4]) == (None, "building history")
```

- [ ] **Step 2: Run, expect fail.** `cd packages/core && uv run pytest tests/test_llm/test_runtime/report_dash_rs/test_quant.py -q`

- [ ] **Step 3: Implement `quant.py`**

```python
"""Deterministic retail-sentiment scoring + signal flags.

The LLM gathers and classifies the discussion; this module turns the counts
into the headline score, the bull/bear split, and the threshold-based signal
flags, so the numbers are computed rather than invented. Momentum is derived
from cached snapshot history by the run service.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_BULLISH_CUTOFF = 0.15
_BEARISH_CUTOFF = -0.15


@dataclass(frozen=True)
class RetailSentimentInputs:
    bullish: int
    bearish: int
    neutral: int
    buzz_level: str  # "low" | "elevated" | "high"


@dataclass
class RetailSentimentClassification:
    sentiment_score: float
    direction: str
    bull_pct: float
    bear_pct: float
    signals: list[dict] = field(default_factory=list)


def classify_retail_sentiment(inp: RetailSentimentInputs) -> RetailSentimentClassification:
    total = inp.bullish + inp.bearish + inp.neutral
    if total <= 0:
        return RetailSentimentClassification(0.0, "neutral", 0.0, 0.0, [])
    score = round((inp.bullish - inp.bearish) / total, 4)
    if score > _BULLISH_CUTOFF:
        direction = "bullish"
    elif score < _BEARISH_CUTOFF:
        direction = "bearish"
    else:
        direction = "neutral"
    bull_pct = round(inp.bullish / total * 100, 1)
    bear_pct = round(inp.bearish / total * 100, 1)
    signals: list[dict] = []
    if inp.buzz_level == "high" and direction == "bearish":
        signals.append({"name": "Panic", "severity": "alert",
                        "note": "High buzz with negative tone — crowd anxiety."})
    if inp.buzz_level == "high" and direction == "bullish":
        signals.append({"name": "FOMO / crowding", "severity": "caution",
                        "note": "High buzz with bullish tone — possible crowding."})
    if inp.buzz_level == "low" and direction == "bullish":
        signals.append({"name": "Stealth recovery", "severity": "info",
                        "note": "Quiet tape with improving tone."})
    return RetailSentimentClassification(score, direction, bull_pct, bear_pct, signals)


def momentum_from_history(scores: list[float]) -> tuple[float | None, str]:
    """Momentum from sentiment-score history (oldest-first). Needs >= 2 points."""
    if len(scores) < 2:
        return None, "building history"
    delta = round(scores[-1] - scores[-2], 4)
    if delta > 0.05:
        label = "improving"
    elif delta < -0.05:
        label = "deteriorating"
    else:
        label = "flat"
    return delta, label
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(report-dash-rs): deterministic sentiment classifier + momentum`

### Task 3: Tool registry + classify/emit tools

**Files:**
- Create: `tools/__init__.py`, `tools/dashboard_tools.py`, `tools/registry.py` under `report_dash_rs/`
- Test: `packages/core/tests/test_llm/test_runtime/report_dash_rs/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
from openlia.llm.runtime.report_dash_rs.tools.dashboard_tools import (
    CLASSIFY_TOOL_BY_SLUG,
    PAYLOAD_MODEL_BY_SLUG,
    implemented_dashboard_slugs,
)


def test_registry_has_retail_sentiment_slug():
    assert implemented_dashboard_slugs() == frozenset({"retail_sentiment"})
    assert "retail_sentiment" in PAYLOAD_MODEL_BY_SLUG
    assert "retail_sentiment" in CLASSIFY_TOOL_BY_SLUG


def test_classify_tool_executes():
    builder = CLASSIFY_TOOL_BY_SLUG["retail_sentiment"][0]
    tool = builder()
    res = tool.execute({"bullish": 70, "bearish": 20, "neutral": 10, "buzz_level": "elevated"})
    assert res.payload["direction"] == "bullish"
    assert res.payload["bull_pct"] == 70.0
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement the tools**

`tools/dashboard_tools.py` — mirror `report_dash_mr/tools/dashboard_tools.py` but RS-specific. Reuse MR's generic `build_emit_dashboard_tool` by importing it; add the RS classify tool:

```python
"""Output + quant tools for report_dash_rs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

# Reuse the generic emit_dashboard tool (validates payload vs the model).
from ...report_dash_mr.tools.dashboard_tools import build_emit_dashboard_tool  # noqa: F401
from ...report_v2_3.research import ResearchTool, ToolDescriptor, ToolExecutionError, ToolResult
from ...report_v2_3.schemas import ComputedSource
from ..quant import RetailSentimentInputs, classify_retail_sentiment
from ..schemas import RetailSentimentData

PAYLOAD_MODEL_BY_SLUG: dict[str, type[BaseModel]] = {"retail_sentiment": RetailSentimentData}


def implemented_dashboard_slugs() -> frozenset[str]:
    return frozenset(PAYLOAD_MODEL_BY_SLUG)


def build_classify_retail_sentiment_tool() -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            out = classify_retail_sentiment(
                RetailSentimentInputs(
                    bullish=int(args["bullish"]),
                    bearish=int(args["bearish"]),
                    neutral=int(args["neutral"]),
                    buzz_level=str(args["buzz_level"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolExecutionError(
                "classify_retail_sentiment requires integer bullish, bearish, neutral "
                f"and a buzz_level of low|elevated|high. {exc}"
            ) from exc
        return ToolResult(
            payload={
                "sentiment_score": out.sentiment_score,
                "direction": out.direction,
                "bull_pct": out.bull_pct,
                "bear_pct": out.bear_pct,
                "signals": out.signals,
            },
            provenance=ComputedSource(method="classify_retail_sentiment", derived_from=["(counts)"]),
            summary=f"score={out.sentiment_score} direction={out.direction}",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="classify_retail_sentiment",
            description=(
                "Deterministic retail-sentiment score + signal flags from the counts of "
                "bullish / bearish / neutral items you gathered, plus your qualitative "
                "buzz_level (low|elevated|high). Use the returned sentiment_score, direction, "
                "bull_pct, bear_pct, and signals verbatim in the payload."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "bullish": {"type": "integer", "minimum": 0},
                    "bearish": {"type": "integer", "minimum": 0},
                    "neutral": {"type": "integer", "minimum": 0},
                    "buzz_level": {"type": "string", "enum": ["low", "elevated", "high"]},
                },
                "required": ["bullish", "bearish", "neutral", "buzz_level"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


CLASSIFY_TOOL_BY_SLUG: dict[str, list[Callable[[], ResearchTool]]] = {
    "retail_sentiment": [build_classify_retail_sentiment_tool],
}
```

`tools/registry.py` — copy `report_dash_mr/tools/registry.py`'s `build_catalog`, but **drop the curated-EODHD `data_tools` branch** (RS has no curated data tools; its optional connector data arrives via `dispatcher_tools`). Keep: emit_dashboard + per-slug classify tools + dispatcher tools (when providers present) + web search (when enabled). Import `build_dispatcher_tools` and web-search helpers from `report_dash_mr.tools` rather than copying them. Pull `PAYLOAD_MODEL_BY_SLUG`/`CLASSIFY_TOOL_BY_SLUG` from `.dashboard_tools`.

`tools/__init__.py` — re-export `build_catalog` and the web-search descriptor (import the descriptor/`WEB_SEARCH_TOOL_NAME` from `report_dash_mr.tools`).

> Read `report_dash_mr/tools/registry.py` and `tools/__init__.py` first and mirror their exact signatures; the only intentional divergences are (a) RS registry, (b) no `data_tools` branch.

- [ ] **Step 4: Run the registry test, expect PASS.**
- [ ] **Step 5: Commit** — `feat(report-dash-rs): tool registry + classify/emit tools`

### Task 4: Prompt spec

**Files:**
- Create: `report_dash_rs/prompts.py`
- Test: `packages/core/tests/test_llm/test_runtime/report_dash_rs/test_prompts.py`

- [ ] **Step 1: Failing test**

```python
from openlia.llm.runtime.report_dash_rs.prompts import (
    DASHBOARD_PROMPT_SPECS,
    build_system_prompt,
)
from openlia.llm.runtime.report_dash_rs.schemas import EnabledConnectors, RunRequest


def test_retail_sentiment_prompt_spec_present():
    spec = DASHBOARD_PROMPT_SPECS["retail_sentiment"]
    assert spec.workflow and spec.payload_shape


def test_build_system_prompt_mentions_web_search_and_ticker():
    req = RunRequest(
        dashboard_slug="retail_sentiment", subject="AAPL",
        enabled_connectors=EnabledConnectors(provider_ids=frozenset(), web_search=True),
    )
    text = build_system_prompt(req)
    assert "AAPL" in text
    assert "web" in text.lower()
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement `prompts.py`** — copy `report_dash_mr/prompts.py`'s structure (`DashboardPromptSpec` dataclass, `build_system_prompt`, the master template with `{workflow}`/`{payload_shape}`/`{connectors_block}`/`{data_context_block}`/`{instructions_block}` slots). Replace `DASHBOARD_PROMPT_SPECS` with a single `"retail_sentiment"` entry:
  - `workflow`: the gather→classify→narrate→emit instructions — "Use web_search to read current retail discussion (Reddit, StockTwits, X, forums) and recent news for {subject}. Count bullish/bearish/neutral items and judge buzz_level. Call classify_retail_sentiment with those counts. Optionally call connector tools for an aggregated-sentiment cross-check and analyst consensus. Cite concrete threads/articles as evidence. Call emit_dashboard once, last."
  - `payload_shape`: a JSON sketch of `RetailSentimentData`.
  - `indicator_hint`: brief notes on honest degradation (momentum is history-derived; optional tiles may be null).
  - If `DashboardPromptSpec` is defined in `report_dash_mr/prompts.py`, import it; otherwise redefine identically.
  - Reuse `report_dash_mr`'s `build_system_prompt` body; only `DASHBOARD_PROMPT_SPECS` differs. If MR's `build_system_prompt` reads its own module-level `DASHBOARD_PROMPT_SPECS`, copy the function into RS so it reads RS's specs.

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(report-dash-rs): system prompt + dashboard prompt spec`

### Task 5: Runner + end-to-end engine test

**Files:**
- Create: `report_dash_rs/runner.py`
- Test: `packages/core/tests/test_llm/test_runtime/report_dash_rs/test_runner.py`

- [ ] **Step 1: Failing test** — model the fake-session pattern on `report_dash_mr`'s runner test (find it: `grep -rl "report_dash_mr" packages/core/tests`). The fake LLM session returns, in order: (1) a `web_search` call, (2) a `classify_retail_sentiment` call, (3) an `emit_dashboard` call with a complete `RetailSentimentData` payload. Assert `RunResult.status == "completed"` and `result.payload["subject"] == "AAPL"`.

```python
# Skeleton — fill the fake session to match report_dash_mr's runner test harness.
import pytest
from openlia.llm.runtime.report_dash_rs import EnabledConnectors, Runner, RunRequest


@pytest.mark.asyncio
async def test_engine_runs_to_completed(fake_rs_session, rs_transports):
    req = RunRequest(
        dashboard_slug="retail_sentiment", subject="AAPL",
        enabled_connectors=EnabledConnectors(provider_ids=frozenset(), web_search=True),
    )
    result = await Runner(req, transports=rs_transports).run(session=fake_rs_session)
    assert result.status == "completed"
    assert result.payload["subject"] == "AAPL"
    assert result.payload["direction"] in {"bullish", "bearish", "neutral"}
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement `runner.py`** — copy `report_dash_mr/runner.py` verbatim, then change only:
  - the department string in `dispatcher.in_department("macro_research")` → `"retail_sentiment"`;
  - remove any MR-only logic (portfolio weights live in the run service, not the runner — confirm none remain);
  - relative imports (`from .prompts import build_system_prompt`, `from .tools import build_catalog`, `from .schemas import ...`) already resolve to RS's modules because they are relative.
  Confirm `build_catalog`'s call signature matches Task 3's `registry.py`.

- [ ] **Step 4: Run the runner test, expect PASS.** Then full engine suite:
Run: `cd packages/core && uv run pytest tests/test_llm/test_runtime/report_dash_rs/ -q`
Expected: all PASS. Then `uv run ruff check report_dash_rs` clean.

- [ ] **Step 5: Commit** — `feat(report-dash-rs): runner + end-to-end engine test`

---

## Phase 2 — Department relaxation + health + artifacts

### Task 6: Relax RS department to web-search dashboard (mirror MR #251)

**Files:**
- Modify: `packages/core/src/openlia/departments/retail_sentiment.py`
- Modify: `packages/core/src/openlia/departments/retail_sentiment.needs.yaml` (header only)
- Modify: `packages/core/src/openlia/departments/retail_sentiment.routing_context.md`
- Modify: `packages/core/tests/departments/test_health.py`
- Modify: `packages/core/tests/departments/test_department_artifacts.py`
- Modify (if referenced): `packages/core/src/openlia/llm/department_requirements.py`

- [ ] **Step 1: Update the failing tests first.** In `test_health.py`, mirror the MR tests from #251 for RS: `test_retail_sentiment_requires_only_web_search`, `..._active_with_web_search_only`, `..._disabled_without_web_search_connector`. In `test_department_artifacts.py`, extend the `test_needs_yaml_present_when_runner_required` `elif` chain with a `retail_sentiment` branch identical in spirit to the `macro_research` branch (retain needs.yaml under `requires_runner=False`, assert it exists + declares needs). Check whether the existing `_runner_need_ids_for("retail_sentiment")` hardcodes `{"social_posts"}` — keep that (the need stays declared), but since `requires_runner=False`, the dept won't be in the runner-required path.

- [ ] **Step 2: Run, expect fail.** `cd packages/core && uv run pytest tests/departments/test_health.py tests/departments/test_department_artifacts.py -q`

- [ ] **Step 3: Implement the dept change**

```python
required_categories: ClassVar[tuple[Category, ...]] = (Category.WEB_SEARCH,)
optional_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL, Category.NEWS)
required_any_of: ClassVar[tuple[tuple[Category, ...], ...]] = ()
requires_runner: ClassVar[bool] = False
is_dashboard: bool = True
```
Keep `department_type = "dashboard"`, `prompt_name`. Update `needs.yaml` header comment to mirror MR's (note `requires_runner=False`, declarations are connector-resolution metadata; the EODHD `social_posts` runner_spec depends on them). Update `routing_context.md` to describe the web-search-backbone dashboard and drop per-post-classification language (keep the required H2 sections so `test_department_artifacts` passes). If `department_requirements.py` enumerates RS required categories, update it to match.

- [ ] **Step 4: Run, expect PASS.** Then full dept suite: `cd packages/core && uv run pytest tests/departments/ -q`.

- [ ] **Step 5: Commit** — `feat(retail-sentiment): relax connectors to web-search dashboard (requires_runner=False)`

---

## Phase 3 — Server cache + run service

### Task 7: `rs_dashboard_cache` table (add-only)

> **Sequencing (revised during execution):** Task 7 only ADDS `RsDashboardCache` + a create-table migration. The OLD models (`RsSnapshot`, `RsClassificationLog`) and their tables are NOT touched here — their services (`rs_snapshot.py`, `rs_classification_log.py`) and the current routes still import them until Tasks 9/12. Deleting them now would break server imports mid-stream. The model deletion + drop-table migration moved to **Task 12** (after their importers are gone).

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/dashboard.py`
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-06-04-XXXX_rs_dashboard_cache.py`
- Test: `packages/server/tests/test_db/test_rs_dashboard_cache.py`

- [ ] **Step 1: Failing test** — assert a `RsDashboardCache` row can be written and read back, unique on `(user_id, ticker)`:

```python
from datetime import UTC, datetime
from openlia_server.db.models.dashboard import RsDashboardCache


def test_rs_dashboard_cache_roundtrip(db_session):
    row = RsDashboardCache(user_id="u1", ticker="AAPL", payload_json="{}",
                           provenance="live", model_ref="m", generated_at=datetime.now(UTC))
    db_session.add(row); db_session.commit()
    got = db_session.query(RsDashboardCache).filter_by(user_id="u1", ticker="AAPL").one()
    assert got.payload_json == "{}"
```
(Use the existing server test DB fixture; check `test_rs_classification_log.py` for the fixture name before writing.)

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Add the model** in `dashboard.py` mirroring `MrDashboardCache`, with `ticker: Mapped[str] = mapped_column(String(16))` replacing `dashboard`, unique `(user_id, ticker)` named `uq_rs_dashboard_cache_user_ticker`, index `ix_rs_dashboard_cache_user_ticker`. **Do NOT delete** `RsSnapshot`/`RsClassificationLog` (still imported by their services/routes until Tasks 9/12). Keep `RsUserConfig` (repurposed as dashboard state; columns unchanged — `metric_settings` JSON now holds threshold overrides, `refresh_interval_minutes` stays).

- [ ] **Step 4: Write the migration.** First find the head: `cd packages/server && uv run alembic heads`. Set `down_revision` to that head. The migration `upgrade()`: `create_table("rs_dashboard_cache", ...)` mirroring the `mr_dashboard_cache` migration (ticker String(16) instead of dashboard) + its index. `downgrade()`: drop the index and `drop_table("rs_dashboard_cache")`. (No drops of legacy tables here — that is Task 12.)

- [ ] **Step 5: Run** `cd packages/server && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` to verify up/down/up, then the model test. Expected: clean + PASS.

- [ ] **Step 6: Commit** — `feat(retail-sentiment): add rs_dashboard_cache table`

### Task 8: `rs_dash_run_service`

**Files:**
- Create: `packages/server/src/openlia_server/services/rs_dash_run_service.py`
- Test: `packages/server/tests/test_services/test_rs_dash_run_service.py`

- [ ] **Step 1: Failing test** — with a stubbed `Runner` (monkeypatch `report_dash_rs.Runner` or inject) returning a `RunResult` with a `RetailSentimentData` payload, assert `run_to_cache(session, user_id, "AAPL")` upserts one `RsDashboardCache` row and merges `momentum` from prior cache history. Model the stubbing on `test` for `mr_dash_run_service` (find it: `grep -rl mr_dash_run_service packages/server/tests`).

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement** mirroring `mr_dash_run_service.run_to_cache`:

```python
def run_to_cache(session: DBSession, user_id: str, ticker: str,
                 cancel_token: CancelToken | None = None) -> str:
    # 1. resolve EnabledConnectors via build_mb_dispatcher / resolve_eodhd_api_key (reused).
    # 2. build RunRequest(dashboard_slug="retail_sentiment", subject=ticker, ...).
    # 3. prior_scores = [json payload sentiment_score from recent RsDashboardCache history for (user_id, ticker)]
    # 4. result = Runner(request, transports, dispatcher=...).run()
    # 5. momentum, trend_label = momentum_from_history(prior_scores + [result score])
    #    merge into payload dict.
    # 6. upsert RsDashboardCache(user_id, ticker, payload_json=json.dumps(payload), provenance, model_ref, generated_at=now).
    return ticker
```
Reuse `build_mb_dispatcher`, `build_mb_transports`, `resolve_eodhd_api_key` exactly as `mr_dash_run_service` does (no fork). Import `Runner`/`RunRequest`/`EnabledConnectors`/`momentum_from_history` from `openlia.llm.runtime.report_dash_rs` (+ `.quant`). The dispatcher department context is set inside the runner ("retail_sentiment").

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(retail-sentiment): rs_dash_run_service (engine run -> cache, momentum merge)`

---

## Phase 4 — Routes + executor + app wiring (the swap)

### Task 9: Rewrite RS routes to MR shape

**Files:**
- Modify (full rewrite): `packages/server/src/openlia_server/routes/departments/retail_sentiment.py`
- Modify (rewrite): `packages/server/tests/test_routes/departments/test_retail_sentiment.py`
- Keep: `packages/server/tests/test_routes/departments/test_retail_sentiment_schedule.py` (adjust only if endpoint paths changed; `/schedule` is unchanged)

- [ ] **Step 1: Rewrite the route tests first** (TDD). Assert:
  - `POST /departments/retail_sentiment/dashboard/AAPL/refresh` → 202 and enqueues (mock the scheduler/jobs service like the MR route test does).
  - returns 409 when `active_run_for_schedule` reports a run in progress.
  - returns 409 when the dept is disabled (no WEB_SEARCH connector) via `gate_dept_or_409`.
  - `GET /dashboard/AAPL` → `{payload, generated_at, is_stale, provenance}`; `{payload: null,...}` when no cache.
  - `GET /dashboard/AAPL/history?days=7` returns the snapshot series.
  - `GET/PUT /config` round-trips dashboard state.
  Model the harness on `test` for the MR dashboard route (`grep -rl gate_dept_or_409 packages/server/tests`).

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Rewrite the router.** Remove imports of `openlia.retail_sentiment.quotes`, `.schemas`, `.spike_detector`, `services.rs_runner`, `services.rs_snapshot`. New imports: `implemented_dashboard_slugs` from `openlia.llm.runtime.report_dash_rs`, `gate_dept_or_409`, `RsDashboardCache`, `RsConfigService` (repurposed), `rs_schedules`. Endpoints per spec §7.3:

| Method | Path | Behaviour |
|---|---|---|
| GET | `/dashboard/{ticker}` | read latest `RsDashboardCache` for `(user, ticker)`; `is_stale` via 24h TTL |
| GET | `/dashboard/{ticker}/history?days=N` | recent cache rows for the ticker, newest-first |
| GET | `/config` | `RsConfigService.get_or_create(user)` → state |
| PUT | `/config` | update state |
| POST | `/dashboard/{ticker}/refresh` (202) | `gate_dept_or_409(request, "retail_sentiment")`; 409 if `active_run_for_schedule` running; enqueue `RS_SNAPSHOT` for `ticker` |
| GET/PUT | `/schedule` | unchanged — reuse `rs_schedules` service |

Remove `/spikes`, `/stocks/{ticker}`, `/classifier/audit`, the old `/run` (replaced by per-ticker `/refresh`), `/dashboard` (list). Drop the `_snapshot_out(MetricSnapshot)` helper; serialize from the cached JSON instead.

- [ ] **Step 4: Run** `cd packages/server && uv run pytest tests/test_routes/departments/test_retail_sentiment.py tests/test_routes/departments/test_retail_sentiment_schedule.py -q`. Expected: PASS.

- [ ] **Step 5: Commit** — `feat(retail-sentiment): MR-shaped dashboard routes; drop per-post endpoints`

### Task 10: Repoint the RS_SNAPSHOT executor

**Files:**
- Modify: `packages/server/src/openlia_server/scheduler/executors/rs.py`
- Modify (rewrite): `packages/server/tests/test_scheduler/test_rs_executor.py`
- Check: `packages/server/src/openlia_server/scheduler/payloads.py` (the `RSSnapshotRunner` payload type — may be removed/simplified)

- [ ] **Step 1: Rewrite the executor test** — assert `_do_work` iterates the user's `EuWatchlistEntry` tickers and calls `rs_dash_run_service.run_to_cache(user_id, ticker)` per ticker, returns a `JobOutcome` counting tickers, and emits one `assessment_ready` notification. Mock `run_to_cache`.

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Rewrite `_do_work`** to call `rs_dash_run_service.run_to_cache` per watchlist ticker (replacing `rs_runner.run_many`). Drop the `rs_runner`/`RSSnapshotRunner` constructor dependency; the executor opens a session and calls the run service directly (mirror `MrDashExecutor._do_work`). Update `scheduler/wiring.py` if the `RSSnapshotExecutor(...)` constructor args change (it currently takes `rs_runner=...`). Keep `JobType.RS_SNAPSHOT` and the `JobType.RS_SNAPSHOT: "retail_sentiment"` registry mapping.

- [ ] **Step 4: Run** `cd packages/server && uv run pytest tests/test_scheduler/test_rs_executor.py -q`. Expected: PASS.

- [ ] **Step 5: Commit** — `feat(retail-sentiment): repoint RS_SNAPSHOT executor to report_dash_rs`

### Task 11: Remove RsRunner wiring from `app.py`

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`

- [ ] **Step 1: Remove** the `rs_data_provider` / `RefreshingSyncLlmClassifier` / `RsRunner` block (around lines 870–884) and any `app.state.rs_runner` / `app.state.rs_classifier` assignments. Update the `build_retail_sentiment_router(...)` include to the new router's signature (Task 9). Update the `scheduler/wiring.py` `RSSnapshotExecutor` construction (Task 10) so app startup no longer passes `rs_runner`.

- [ ] **Step 2: Verify the app boots / imports clean.** Run the existing app/smoke tests: `cd packages/server && uv run pytest tests/test_app* tests/test_routes/departments/test_retail_sentiment.py -q` (adjust glob to whatever app-construction test exists; `grep -rl "create_app\|build_app" packages/server/tests | head`). Expected: PASS, no import errors.

- [ ] **Step 3: Commit** — `refactor(retail-sentiment): drop RsRunner/classifier app wiring`

---

## Phase 5 — Delete the inert per-post pipeline

### Task 12: Delete old core + server modules and their tests

**Files (DELETE):**
- Core package: the entire `packages/core/src/openlia/retail_sentiment/` directory (`classifier.py`, `metrics.py`, `reliability.py`, `spike_detector.py`, `quotes.py`, `insights.py`, `schemas.py`, `__init__.py`).
- Prompts: `packages/core/src/openlia/prompts/retail_sentiment.yaml`, `packages/core/src/openlia/prompts/retail_sentiment_insights.yaml`.
- Server services: `services/rs_runner.py`, `services/rs_sync_classifier.py`, `services/rs_classification_log.py`.
- DB models (now unreferenced — their services/routes are gone): the `RsSnapshot` and `RsClassificationLog` classes in `db/models/dashboard.py`.
- Core tests: all of `packages/core/tests/retail_sentiment/`.
- Server tests: `test_services/test_rs_runner.py`, `test_rs_runner_insights.py`, `test_rs_sync_classifier.py`; `test_db/test_rs_classification_log.py`; `test_routes/departments/test_retail_sentiment_classifier_audit.py`.

**Files (CREATE):**
- Migration `packages/server/src/openlia_server/db/migrations/versions/2026-06-04-YYYY_drop_legacy_rs_tables.py` (chained after Task 7's migration head): `upgrade()` drops indexes + `drop_table("rs_snapshots")` + `drop_table("rs_classification_log")`; `downgrade()` recreates both (copy their `create_table` from `2026-04-24-0100_rs_classification_log.py` and the baseline migration for `rs_snapshots`).

- [ ] **Step 1: Grep for stragglers before deleting.** `grep -rn "openlia.retail_sentiment\|rs_runner\|rs_sync_classifier\|rs_classification_log\|RsRunner\|RsSnapshotService\|RsSnapshot\b\|RsClassificationLog\|NeutralClassifier\|LlmClassifier" packages/ --include=*.py | grep -v __pycache__`. Every hit outside the delete list must already be removed by Tasks 9–11 — if any remain, fix the referencing file. Also check `prompts/__init__.py` for a registry reference to the deleted YAMLs, and `services/smoke_service.py` (the inventory flagged a retail_sentiment reference) and `routes/chat_sessions.py`. Confirm nothing still imports `RsSnapshot`/`RsClassificationLog` before deleting those model classes.

- [ ] **Step 2: Delete** the files/dirs + the two model classes above (`git rm -r` for files; edit `dashboard.py` to remove the two classes).

- [ ] **Step 3: Write + run the drop-tables migration** (above). Verify up/down/up: `cd packages/server && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`.

- [ ] **Step 4: Verify import-clean.** Run the full core suite and the server collection:
`cd packages/core && uv run pytest -q` then `cd packages/server && uv run pytest tests/test_routes/departments/ tests/test_services/ tests/test_scheduler/ tests/test_db/ -q`.
Expected: green (no import errors, no orphaned references). Fix any remaining import.

- [ ] **Step 5: Commit** — `refactor(retail-sentiment): delete inert per-post pipeline + drop legacy rs tables`

---

## Phase 6 — Frontend reshape

### Task 13: Polled single-ticker view + API client + coverage hint

**Files:**
- Modify (rewrite): `frontend/src/api/retail-sentiment.ts`
- Modify (rewrite): `frontend/src/pages/departments/RetailSentiment.tsx`
- Create: `frontend/src/pages/departments/retail_sentiment/RsOverviewView.tsx` (the typed payload renderer) + `RsSettingsPanel.tsx` (coverage hint)
- Modify: `frontend/src/api/departments.ts` (`RUNNER_BEARING_DEPARTMENTS` → `[]`)
- Modify: `frontend/src/i18n/locales/en.json`, `zh-TW.json`
- DELETE: `components/retail-sentiment/{EvidenceTab,MetricsDeepDiveTab,OverviewAllView,InsightsTab,ReliabilityBadge}.tsx`, `lib/retail-sentiment/metric-catalog.ts`, and the hooks `hooks/useRsSpikes.ts`, `useRsQuotes.ts`, plus any `useRs*` hooks tied to deleted endpoints; their `__tests__`.
- KEEP/reuse: `SentimentGauge`, `MomentumGauge`, `SignalAlert`, `TrendChart`, `MetricCard`, `charts.tsx`, `TickerSelector`, `SettingsDrawer`, `ScheduleEditor`.
- Test: `frontend/src/pages/departments/__tests__/RetailSentiment.test.tsx` (rewrite), `retail_sentiment/__tests__/RsSettingsPanel.test.tsx` (new, coverage hint).

- [ ] **Step 1: Rewrite `api/retail-sentiment.ts`** mirroring `api/macro_research.ts`: `RetailSentimentPayload` interface matching `RetailSentimentData`; `getDashboard(ticker)` → `GET /api/departments/retail_sentiment/dashboard/{ticker}` returning `DashboardResponse<RetailSentimentPayload>`; `getHistory(ticker, days)`; `getConfig()/putConfig()`; `refreshDashboard(ticker)` → `POST .../dashboard/{ticker}/refresh`; schedule calls unchanged.

- [ ] **Step 2: Write the failing view tests.** RetailSentiment.test.tsx: mounts the page, mocks the dashboard fetch + `dept-health`, asserts the single-ticker overview renders the sentiment score/direction/buzz/narratives/signals/evidence from a fixture payload, "Generate now" calls `refreshDashboard` and shows a polling skeleton (mirror `DebtCycleView.test`/`MacroResearch.test` patterns). RsSettingsPanel.test.tsx: asserts `data-testid="rs-coverage"` renders web_search "active"/"required" and financial/news "active"/"not configured" from a mocked `dept-health` response (mirror `MRSettingsPanel`'s `mr-coverage` test).

- [ ] **Step 3: Run, expect fail.** `cd frontend && npm run test -- RetailSentiment RsSettingsPanel`

- [ ] **Step 4: Implement.** Rewrite `RetailSentiment.tsx` to the MR page pattern: ticker selector + a single `RsOverviewView` polling `getDashboard(ticker)` (respect `is_stale`/`generated_at`), "Generate now" → `refreshDashboard` then poll until `generated_at` advances (reuse the DebtCycleView polling-skeleton fix), refresh spinner, stale badge. Drop the `overview/metrics/evidence/insights` tab model — single overview view (others are roadmap). `RsSettingsPanel.tsx`: copy `MRSettingsPanel`'s coverage-hint section, `RS_COVERAGE` constant (web_search required; financial → aggregated-sentiment cross-check; news → headline evidence), `fetchDeptHealth("retail_sentiment")` effect, `data-testid="rs-coverage"`. Set `RUNNER_BEARING_DEPARTMENTS = []` in `departments.ts`. Prune deleted i18n keys (`tab_metrics/evidence/insights`, metric-catalog strings) and add coverage-hint strings in `en.json` + `zh-TW.json`.

- [ ] **Step 5: Run** `cd frontend && npm run test -- RetailSentiment RsSettingsPanel` (PASS), then `npx tsc --noEmit` (clean), then `npm run test` (full suite green — watch for the known pre-existing SettingsShellBlocker AbortSignal exit-1 noise documented in memory; the RS files themselves must pass).

- [ ] **Step 6: Commit** — `feat(retail-sentiment): polled single-ticker dashboard view + coverage hint`

---

## Phase 7 — Final verification + review

### Task 14: Whole-branch verification

- [ ] **Step 1: Backend** — `cd packages/core && uv run pytest -q` (full core green); `cd packages/server && uv run pytest tests/test_routes/ tests/test_services/ tests/test_scheduler/ tests/test_db/ tests/test_app* -q` (targeted dirs — the full server suite hangs on SSE tests per memory, so run by dir). `uv run ruff check . && uv run ruff format --check .` from repo root.
- [ ] **Step 2: Frontend** — `cd frontend && npx tsc --noEmit && npm run test`.
- [ ] **Step 3: Migration sanity** — `cd packages/server && uv run alembic upgrade head` on a fresh DB; confirm `rs_dashboard_cache` exists and `rs_snapshots`/`rs_classification_log` are gone.
- [ ] **Step 4: Grep for orphans** — `grep -rn "retail_sentiment" --include=*.py packages | grep -iE "runner|classifier|metric_snapshot|spike|social_posts" | grep -v __pycache__ | grep -v needs.yaml` — every remaining hit should be the retained `needs.yaml`/connector-resolution metadata, nothing live.
- [ ] **Step 5: Final code review** — dispatch `feature-dev:code-reviewer` over the whole branch diff (`git diff main...HEAD`). Address findings.

---

## Self-Review (plan author)

- **Spec coverage:** §4 engine → Tasks 1–5; §8 department/coverage → Tasks 6 & 13; §7.1 run service → Task 8; §7.2 executor → Task 10; §7.3 routes → Task 9; §7.4 DB → Task 7; §7.5 app.py → Task 11; §9 frontend → Task 13; §10 deletion → Task 12; §12 testing → woven into each task + Task 14. Roadmap (§11) intentionally deferred.
- **Hazard coverage:** the `needs.yaml` retention (R3) is enforced in Task 6 + verified in Task 14 Step 4; deletion-import hazards are sequenced so importers (routes/executor/app) are rewritten (Tasks 9–11) before the imported modules are deleted (Task 12), with a straggler grep gate.
- **Type consistency:** `RetailSentimentData`/`Signal`/`EvidenceItem` (Task 1) are the same names used by the registry (Task 3), run service (Task 8), routes (Task 9), and frontend interface (Task 13). `classify_retail_sentiment`/`RetailSentimentInputs`/`momentum_from_history` (Task 2) match their callers (Tasks 3, 8). `run_to_cache(session, user_id, ticker)` (Task 8) matches its callers (Tasks 9, 10).
- **Destructive step:** Task 7 drops `rs_snapshots` + `rs_classification_log` (user-approved; rows are zero-post/worthless) with a recreating `downgrade()`.

## Execution Handoff

Two options: **(1) Subagent-Driven** (recommended) — fresh subagent per task, spec-then-quality review between tasks, continuous execution; **(2) Inline**. Which approach?
