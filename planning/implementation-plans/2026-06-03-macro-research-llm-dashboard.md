# Macro Research LLM-Dashboard — Implementation Plan (Phase 1: debt_cycle vertical slice)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Macro Research `debt_cycle` dashboard fully live end-to-end — a scheduled LLM tool-use agent (`report_dash_mr`) gathers cited data, runs deterministic classification, emits the typed `DebtCycleData` payload to a DB cache, and the existing React view renders it from cache instead of the hardcoded fallback.

**Architecture:** Fork the Morning Briefing engine (`report_mb`) into `report_dash_mr`. Unlike MB (which emits free-form sections/charts), this engine emits one validated typed dashboard payload via an `emit_dashboard` output tool, and calls deterministic quant tools for any computed numbers. A scheduler job runs it per dashboard and writes the payload to `mr_dashboard_cache`; the route reads cache. This plan delivers ONE dashboard (`debt_cycle`) plus all reusable scaffolding; the other four dashboards, heavy quant (Markov/VAR/Monte-Carlo), curated reference data, and removal of the old need-id layer are follow-on plans (see Roadmap).

**Tech Stack:** Python 3.12 (core: pure, no web deps), Pydantic v2, SQLAlchemy + Alembic, FastAPI, APScheduler, pytest; React/TypeScript/Vite (frontend). Package manager: `uv`. Lint/format: `ruff`.

**Spec:** `planning/specs/systems/macro-research-llm-dashboard-redesign.md`

---

## File Structure (Phase 1)

**Create (core):**
- `packages/core/src/openlia/macro_research/quant/__init__.py` — quant package exports
- `packages/core/src/openlia/macro_research/quant/classification.py` — debt-cycle RAG/phase classifier (pure)
- `packages/core/src/openlia/macro_research/payloads.py` — Pydantic payload models mirroring `dalio_copy/types.ts`
- `packages/core/src/openlia/llm/runtime/report_dash_mr/` — forked engine (see Task 5)
- `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py` — `emit_dashboard` + quant tools

**Create (server):**
- `packages/server/src/openlia_server/db/models/mr_dashboard_cache.py` — cache ORM model
- `packages/server/src/openlia_server/db/migrations/versions/2026-06-03_0001_mr_dashboard_cache.py` — migration
- `packages/server/src/openlia_server/services/mr_dash_run_service.py` — run-to-cache service
- `packages/server/src/openlia_server/scheduler/executors/mr_dash.py` — scheduler executor

**Modify:**
- `packages/server/src/openlia_server/scheduler/registry.py` — add `JobType.MR_DASH`
- `packages/server/src/openlia_server/scheduler/wiring.py` — register `MrDashExecutor`
- `packages/server/src/openlia_server/db/models/register_all.py` — register the cache model
- `packages/server/src/openlia_server/routes/departments/macro_research.py` — `GET /dashboards/{slug}` reads cache; `POST /dashboards/{slug}/refresh`
- `packages/server/src/openlia_server/app.py` — wire run service + executor
- `frontend/src/pages/departments/macro_research/DebtCycleView.tsx` — render from live cache
- `frontend/src/api/macro_research.ts` — `getDashboard` returns typed payload

**Tests:**
- `packages/core/tests/macro_research/test_classification.py`
- `packages/core/tests/macro_research/test_payloads.py`
- `packages/core/tests/macro_research/runtime/test_report_dash_mr_debt_cycle.py`
- `packages/server/tests/test_macro_research/test_mr_dash_cache.py`
- `packages/server/tests/test_macro_research/test_mr_dash_route.py`
- `frontend/src/pages/departments/macro_research/__tests__/DebtCycleView.test.tsx`

---

## Phase 1A — Deterministic foundation (pure Python, no engine, no server)

### Task 1: Debt-cycle classification module

Port the sound classification logic from `packages/core/src/openlia/macro_research/dashboards/debt_cycle.py` (`T3_compute`) into a standalone pure function. Drop the stubbed T2 formulas — this function takes already-fetched numeric inputs.

**Files:**
- Create: `packages/core/src/openlia/macro_research/quant/classification.py`
- Create: `packages/core/src/openlia/macro_research/quant/__init__.py`
- Test: `packages/core/tests/macro_research/test_classification.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/macro_research/test_classification.py
from openlia.macro_research.quant.classification import (
    DebtCycleInputs,
    DebtCycleClassification,
    classify_debt_cycle,
)


def test_two_red_indicators_yields_deleveraging():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=125.2, interest_revenue=20.1, tips_real_yield=1.94, dxy=104.0)
    )
    assert isinstance(out, DebtCycleClassification)
    assert out.indicator_statuses["debt_gdp"] == "red"
    assert out.indicator_statuses["interest_revenue"] == "red"
    assert out.phase == "Deleveraging"
    assert out.severity == "red"


def test_all_green_yields_expansion():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=80.0, interest_revenue=8.0, tips_real_yield=2.0, dxy=105.0)
    )
    assert out.phase == "Expansion"
    assert out.severity == "green"


def test_low_tips_yield_flags_amber():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=80.0, interest_revenue=8.0, tips_real_yield=0.2, dxy=105.0)
    )
    assert out.indicator_statuses["tips_yield"] == "amber"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_classification.py -v`
Expected: FAIL — `ModuleNotFoundError: openlia.macro_research.quant`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/core/src/openlia/macro_research/quant/classification.py
"""Debt Cycle deterministic classification. Pure function; no I/O, no LLM.

Ported from the old dashboards/debt_cycle.py T3_compute. Thresholds are
Dalio defaults. Inputs are already-fetched scalars (the engine gathers
them via tools/web_search), so the stubbed T2 formulas are gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Tone = Literal["red", "amber", "green"]

_DEBT_GDP_WARN = 100.0
_DEBT_GDP_CRITICAL = 120.0
_INTEREST_REVENUE_WARN = 15.0
_INTEREST_REVENUE_CRITICAL = 20.0
_TIPS_YIELD_WARN = 0.5
_DXY_WARN = 100.0


@dataclass(frozen=True)
class DebtCycleInputs:
    debt_gdp: float
    interest_revenue: float
    tips_real_yield: float
    dxy: float


@dataclass(frozen=True)
class DebtCycleClassification:
    phase: str
    severity: Tone
    indicator_statuses: dict[str, Tone]
    red_count: int
    amber_count: int
    monetary_space: dict[str, object] = field(default_factory=dict)


def _bucket(value: float, warn: float, crit: float) -> Tone:
    if value >= crit:
        return "red"
    if value >= warn:
        return "amber"
    return "green"


def classify_debt_cycle(inputs: DebtCycleInputs) -> DebtCycleClassification:
    statuses: dict[str, Tone] = {
        "debt_gdp": _bucket(inputs.debt_gdp, _DEBT_GDP_WARN, _DEBT_GDP_CRITICAL),
        "interest_revenue": _bucket(
            inputs.interest_revenue, _INTEREST_REVENUE_WARN, _INTEREST_REVENUE_CRITICAL
        ),
        "tips_yield": "amber" if inputs.tips_real_yield < _TIPS_YIELD_WARN else "green",
        "dxy": "amber" if inputs.dxy < _DXY_WARN else "green",
    }
    red = sum(1 for s in statuses.values() if s == "red")
    amber = sum(1 for s in statuses.values() if s == "amber")

    if red >= 2:
        phase, severity = "Deleveraging", "red"
    elif red == 1 and amber >= 1:
        phase, severity = "Late Plateau", "red"
    elif amber >= 2:
        phase, severity = "Plateau", "amber"
    else:
        phase, severity = "Expansion", "green"

    return DebtCycleClassification(
        phase=phase,
        severity=severity,
        indicator_statuses=statuses,
        red_count=red,
        amber_count=amber,
        monetary_space={
            "rate_cut_headroom": max(0.0, 5.0 - inputs.tips_real_yield),
            "qe_credibility": "amber" if inputs.interest_revenue >= 12 else "green",
            "currency_debasement_risk": (
                "red" if inputs.dxy < 98 else "amber" if inputs.dxy < 102 else "green"
            ),
        },
    )
```

```python
# packages/core/src/openlia/macro_research/quant/__init__.py
from openlia.macro_research.quant.classification import (
    DebtCycleClassification,
    DebtCycleInputs,
    classify_debt_cycle,
)

__all__ = ["DebtCycleInputs", "DebtCycleClassification", "classify_debt_cycle"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_classification.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check --fix packages/core/src/openlia/macro_research/quant/
uv run ruff format packages/core/src/openlia/macro_research/quant/ packages/core/tests/macro_research/test_classification.py
git add packages/core/src/openlia/macro_research/quant/ packages/core/tests/macro_research/test_classification.py
git commit -m "feat(mr): debt-cycle deterministic classification module"
```

### Task 2: Payload models mirroring the frontend contract

The engine emits validated typed payloads whose shape **is** the frontend contract. Before writing, read `frontend/src/lib/macro_research/dalio_copy/types.ts` and mirror `DebtCycleData` exactly (field names, optionality). The models below match the shape used by `DebtCycleView.tsx`; reconcile any drift against `types.ts`.

**Files:**
- Create: `packages/core/src/openlia/macro_research/payloads.py`
- Test: `packages/core/tests/macro_research/test_payloads.py`

- [ ] **Step 1: Read the contract**

Run: `sed -n '1,80p' frontend/src/lib/macro_research/dalio_copy/types.ts` and confirm the `DebtCycleData`, tone, and `Status` field names match the models below. If a name differs, use the `types.ts` name.

- [ ] **Step 2: Write the failing test**

```python
# packages/core/tests/macro_research/test_payloads.py
import pytest
from pydantic import ValidationError

from openlia.macro_research.payloads import (
    DebtCycleData,
    DashHeader,
    ScoreRow,
    Provenance,
)


def test_minimal_debt_cycle_payload_validates():
    data = DebtCycleData(
        header=DashHeader(title="T1", subtitle="April 2026 · Dalio", pills=[]),
        cardSummary="summary",
        scorecard={"rows": [
            ScoreRow(
                name="Govt debt / GDP", sub="Q4 2025", current="125.2%",
                currentTone="red", currentMeta="CEIC", threshold="> 100%",
                status="Critical", statusTone="red", fillPct=93, fillTone="red",
            )
        ]},
        phaseBox={"title": "Late plateau", "body": "...", "tone": "amber"},
        analogPair={"analog": {"title": "1968-80", "body": "..."},
                    "timeToConstraint": {"title": "3-7y", "body": "..."}},
        policySpace={"cards": [{"label": "Rate cut headroom", "value": "~150bps",
                                "valueTone": "amber", "unit": "to ELB", "note": "..."}]},
        assetThesis={"gold": {"title": "Gold", "body": "..."},
                     "longBond": {"title": "Bonds", "body": "..."}},
        watchlist={"rows": [{"tone": "red", "name": "spiral", "body": "..."}]},
        verdict={"title": "synthesis", "body": "...", "tone": "amber"},
        sources="CEIC/BEA",
        provenance=Provenance.LIVE,
        generated_at="2026-06-03T00:00:00Z",
    )
    assert data.scorecard["rows"][0].fillPct == 93
    assert data.provenance == Provenance.LIVE


def test_invalid_tone_rejected():
    with pytest.raises(ValidationError):
        ScoreRow(
            name="x", sub="y", current="1", currentTone="purple", currentMeta="m",
            threshold="t", status="s", statusTone="red", fillPct=1, fillTone="red",
        )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_payloads.py -v`
Expected: FAIL — `ModuleNotFoundError: openlia.macro_research.payloads`

- [ ] **Step 4: Write minimal implementation**

```python
# packages/core/src/openlia/macro_research/payloads.py
"""Typed dashboard payloads. The engine emits one of these per dashboard;
the server returns it verbatim; the React view renders it. Shapes mirror
frontend/src/lib/macro_research/dalio_copy/types.ts. Keep in lockstep.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

Tone = Literal["red", "amber", "green", "blue"]


class Provenance(StrEnum):
    LIVE = "live"
    COMPUTED = "computed"
    REFERENCE = "reference"


class Pill(BaseModel):
    tone: Tone
    label: str


class DashHeader(BaseModel):
    title: str
    subtitle: str
    pills: list[Pill] = []


class ScoreRow(BaseModel):
    name: str
    sub: str
    current: str
    currentTone: Tone
    currentMeta: str
    threshold: str
    status: str
    statusTone: Tone
    fillPct: int
    fillTone: Tone


class Prose(BaseModel):
    title: str
    body: str


class TonedProse(Prose):
    tone: Tone


class PolicyCard(BaseModel):
    label: str
    value: str
    valueTone: Tone
    unit: str
    note: str


class WatchRow(BaseModel):
    tone: Tone
    name: str
    body: str


class DebtCycleData(BaseModel):
    header: DashHeader
    cardSummary: str
    scorecard: dict[str, list[ScoreRow]]
    phaseBox: TonedProse
    analogPair: dict[str, Prose]
    policySpace: dict[str, list[PolicyCard]]
    assetThesis: dict[str, Prose]
    watchlist: dict[str, list[WatchRow]]
    verdict: TonedProse
    sources: str
    # Redesign additions (not fabricated as "live"): provenance + freshness.
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_payloads.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check --fix packages/core/src/openlia/macro_research/payloads.py
uv run ruff format packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads.py
git add packages/core/src/openlia/macro_research/payloads.py packages/core/tests/macro_research/test_payloads.py
git commit -m "feat(mr): typed DebtCycleData payload model mirroring frontend contract"
```

### Task 3: MRSnapshot derivation from a cached payload

Morning Briefing consumes `MRSnapshot` via `MacroResearchDepartment.get_current_snapshot`. The redesign re-derives it from cached payloads. Add a pure helper that maps a `DebtCycleData` to the snapshot's `debt_cycle_phase`.

**Files:**
- Create: `packages/core/src/openlia/macro_research/snapshot.py`
- Test: `packages/core/tests/macro_research/test_snapshot.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/macro_research/test_snapshot.py
from datetime import UTC, datetime

from openlia.macro_research.payloads import DebtCycleData
from openlia.macro_research.snapshot import debt_cycle_phase_from_payload


def _payload(phase_title: str) -> DebtCycleData:
    return DebtCycleData(
        header={"title": "T1", "subtitle": "s", "pills": []},
        cardSummary="x",
        scorecard={"rows": []},
        phaseBox={"title": phase_title, "body": "b", "tone": "amber"},
        analogPair={"analog": {"title": "a", "body": "b"},
                    "timeToConstraint": {"title": "t", "body": "b"}},
        policySpace={"cards": []},
        assetThesis={"gold": {"title": "g", "body": "b"},
                     "longBond": {"title": "l", "body": "b"}},
        watchlist={"rows": []},
        verdict={"title": "v", "body": "b", "tone": "amber"},
        sources="s",
        generated_at=datetime.now(UTC),
    )


def test_phase_extracted_from_phasebox_title():
    assert debt_cycle_phase_from_payload(_payload("Phase: late plateau")) == "Phase: late plateau"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: openlia.macro_research.snapshot`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/core/src/openlia/macro_research/snapshot.py
"""Derive the cross-department MRSnapshot fields from cached dashboard
payloads. Preserves the contract Morning Briefing reads."""

from __future__ import annotations

from openlia.macro_research.payloads import DebtCycleData


def debt_cycle_phase_from_payload(payload: DebtCycleData) -> str:
    return payload.phaseBox.title
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_snapshot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
uv run ruff format packages/core/src/openlia/macro_research/snapshot.py packages/core/tests/macro_research/test_snapshot.py
git add packages/core/src/openlia/macro_research/snapshot.py packages/core/tests/macro_research/test_snapshot.py
git commit -m "feat(mr): derive MRSnapshot debt_cycle_phase from cached payload"
```

---

## Phase 1B — Engine (`report_dash_mr`)

> **REVISION (2026-06-03, during execution) — supersedes the Task 5/6 code below.**
> Recon of the real forked engine showed the speculative code below was wrong in three ways, so Tasks 5 and 6 are consolidated and corrected:
> 1. **Real tool API** (`report_v2_3.research`): `ToolDescriptor(name, description, parameters=<JSON-Schema dict>)`; `ResearchTool(descriptor, execute)`; `execute(args) -> ToolResult(payload=<dict>, provenance=ComputedSource(method=..., derived_from=[...]), summary=...)`; raise `ToolExecutionError(msg)` on bad input. (NOT `ToolResult(ok=, data=)` / `input_schema=`.)
> 2. **`RunRequest` has no `dashboard_slug`** and `template` is required; **`RunResult` has no `payload`**; the workspace is built around `write_section`/`finalize`. So the engine needs: `RunRequest += dashboard_slug: str`, `template` made optional; `RunResult += payload: dict|None`; `RunWorkspace += payload + set_payload()` (sets `finalized=True`, so the existing loop exit fires) and `to_result(... payload=self.payload.model_dump(mode="json"))`; tolerate `template=None`.
> 3. **`build_catalog` swaps output tools**: replace `build_output_tools(...)` with `[emit_dashboard, classify_debt_cycle]`, keep the eodhd/dispatcher/web_search blocks, and take `dashboard_slug`. The runner passes `request.dashboard_slug`, uses a dashboard-specific initial user turn + system prompt (gather → classify_debt_cycle → emit_dashboard; NOT "write sections/finalize"). Template becomes vestigial (intentional Phase-1 tech-debt; a later phase can strip section/chart/cover machinery).
> Engine test models `packages/core/tests/runtime/report_mb/_fakes.py` + `test_runner.py` (fake adapter via `LLMSession.attach_adapter`, scripting turn1=classify_debt_cycle call, turn2=emit_dashboard call). The authoritative brief for this is the dispatched Task 5 implementer prompt.

### Task 4: Fork the engine package skeleton

Copy the `report_mb` engine as the base. The only structural difference is the **output contract**: instead of `write_section`/`emit_chart`/`finalize` producing free-form sections, this engine has a single `emit_dashboard` tool that accepts a validated typed payload and finalizes the run. The turn loop, session, ledger, events, and transports are reused as-is.

**Files:**
- Create (copy): `packages/core/src/openlia/llm/runtime/report_dash_mr/` from `report_mb/`

- [ ] **Step 1: Copy the package**

```bash
cp -r packages/core/src/openlia/llm/runtime/report_mb \
      packages/core/src/openlia/llm/runtime/report_dash_mr
rm -rf packages/core/src/openlia/llm/runtime/report_dash_mr/__pycache__
```

- [ ] **Step 2: Rename the department + module identity**

In `report_dash_mr/runner.py`, change the `in_department("morning_briefing")` string to `in_department("macro_research")`. In `report_dash_mr/__init__.py`, update the docstring to describe the dashboard engine. Leave `events.py`, `ledger.py`, `session.py`, `workspace.py`, `transports.py` unchanged.

- [ ] **Step 3: Verify it imports**

Run: `uv run python -c "from openlia.llm.runtime.report_dash_mr import Runner; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_dash_mr/
git commit -m "chore(mr): fork report_mb -> report_dash_mr engine skeleton"
```

### Task 5: `emit_dashboard` + quant output tools

Replace the MB output tools with an `emit_dashboard` tool (validates against `DebtCycleData`, stores it on the workspace, marks finalized) and a `classify_debt_cycle` quant tool (wraps Task 1). The data-gathering tools (quotes/news via dispatcher + native `web_search`) stay from the fork.

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/registry.py` (swap output tools)
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/workspace.py` (hold the typed payload)
- Test: `packages/core/tests/macro_research/runtime/test_report_dash_mr_debt_cycle.py`

- [ ] **Step 1: Write the failing test (fake tool surface + golden payload)**

```python
# packages/core/tests/macro_research/runtime/test_report_dash_mr_debt_cycle.py
import pytest

from openlia.llm.runtime.report_dash_mr import Runner
from openlia.llm.runtime.report_dash_mr.schemas import RunRequest, RunStatus
from openlia.macro_research.payloads import DebtCycleData


@pytest.mark.asyncio
async def test_debt_cycle_run_emits_typed_payload(fake_session_emitting_debt_cycle):
    # fake_session_emitting_debt_cycle: an LLMSession stub whose scripted
    # turns call classify_debt_cycle then emit_dashboard with a full payload.
    runner = Runner(
        request=RunRequest(dashboard_slug="debt_cycle", model="stub", provider_kind="stub"),
        transports=None,
        dispatcher=None,
    )
    result = await runner.run(session=fake_session_emitting_debt_cycle)
    assert result.status == RunStatus.COMPLETED
    assert isinstance(result.payload, DebtCycleData)
    assert result.payload.phaseBox.tone in ("red", "amber", "green")
```

(The fixture lives in `packages/core/tests/macro_research/runtime/conftest.py`; build it by scripting an `LLMSession`-shaped stub that returns two tool calls then a stop. Model it on the existing EU/MB engine test fakes in `packages/core/tests/` — search `grep -rl "tool_calls" packages/core/tests/llm/runtime/report_mb` for the closest template.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/runtime/test_report_dash_mr_debt_cycle.py -v`
Expected: FAIL — `result.payload` attribute missing / `emit_dashboard` not defined.

- [ ] **Step 3: Add the typed payload slot to the workspace**

In `report_dash_mr/workspace.py`, add to `RunWorkspace`:

```python
    payload: object | None = None  # the emitted typed dashboard payload

    def set_payload(self, payload: object) -> None:
        self.payload = payload
        self.finalized = True
```

- [ ] **Step 4: Write the dashboard tools**

```python
# packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py
"""Output + quant tools for the dashboard engine. `emit_dashboard`
validates the model's payload against the typed contract and finalizes.
Quant tools wrap the deterministic core math so the model never invents
computed numbers."""

from __future__ import annotations

from typing import Any

from openlia.macro_research.payloads import DebtCycleData
from openlia.macro_research.quant.classification import (
    DebtCycleInputs,
    classify_debt_cycle,
)

from .registry import ResearchTool, ToolDescriptor, ToolResult


def build_emit_dashboard_tool(workspace: Any, payload_model: type) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        validated = payload_model.model_validate(args["payload"])
        workspace.set_payload(validated)
        return ToolResult(ok=True, summary=f"emitted {payload_model.__name__}")

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="emit_dashboard",
            description="Emit the final typed dashboard payload. Call once, last.",
            input_schema={"type": "object", "properties": {"payload": {"type": "object"}},
                          "required": ["payload"]},
        ),
        execute=_execute,
    )


def build_classify_debt_cycle_tool() -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        out = classify_debt_cycle(
            DebtCycleInputs(
                debt_gdp=float(args["debt_gdp"]),
                interest_revenue=float(args["interest_revenue"]),
                tips_real_yield=float(args["tips_real_yield"]),
                dxy=float(args["dxy"]),
            )
        )
        return ToolResult(
            ok=True,
            summary=f"phase={out.phase} severity={out.severity}",
            data={
                "phase": out.phase,
                "severity": out.severity,
                "indicator_statuses": out.indicator_statuses,
                "monetary_space": out.monetary_space,
            },
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="classify_debt_cycle",
            description="Deterministic debt-cycle phase/RAG classification from four indicators.",
            input_schema={
                "type": "object",
                "properties": {
                    "debt_gdp": {"type": "number"},
                    "interest_revenue": {"type": "number"},
                    "tips_real_yield": {"type": "number"},
                    "dxy": {"type": "number"},
                },
                "required": ["debt_gdp", "interest_revenue", "tips_real_yield", "dxy"],
            },
        ),
        execute=_execute,
    )
```

(Match `ResearchTool` / `ToolDescriptor` / `ToolResult` to the actual classes used in `report_dash_mr/tools/registry.py` — adapt names if the fork uses different attributes.)

- [ ] **Step 5: Wire the tools into `build_catalog`**

In `report_dash_mr/tools/registry.py`, in `build_catalog`, replace the MB output-tools block (`build_output_tools(...)`) with:

```python
    from .dashboard_tools import build_classify_debt_cycle_tool, build_emit_dashboard_tool
    from openlia.macro_research.payloads import DebtCycleData

    _PAYLOAD_MODEL_BY_SLUG = {"debt_cycle": DebtCycleData}

    core: list[ResearchTool] = [
        build_emit_dashboard_tool(workspace, _PAYLOAD_MODEL_BY_SLUG[dashboard_slug]),
        build_classify_debt_cycle_tool(),
    ]
```

Thread `dashboard_slug` from `RunRequest` into `build_catalog` (add the param; the runner passes `request.dashboard_slug`). Keep `build_data_tools` / `build_dispatcher_tools` / native `web_search` from the fork. Update `RunResult` (`schemas.py`) to carry `payload: object | None` and have the runner set `result.payload = workspace.payload`.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/runtime/test_report_dash_mr_debt_cycle.py -v`
Expected: PASS

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check --fix packages/core/src/openlia/llm/runtime/report_dash_mr/
uv run ruff format packages/core/src/openlia/llm/runtime/report_dash_mr/ packages/core/tests/macro_research/runtime/
git add packages/core/src/openlia/llm/runtime/report_dash_mr/ packages/core/tests/macro_research/runtime/
git commit -m "feat(mr): emit_dashboard + debt-cycle quant tools in report_dash_mr"
```

### Task 6: Engine system prompt for debt_cycle

The prompt tells the model: gather the four indicators (prefer connector tools, fall back to web_search against FRED/IMF/Treasury/CBO), call `classify_debt_cycle`, write each narrative tile from cited data, then `emit_dashboard`. Per project convention, phrase positively (see CLAUDE.md / memory: positive prompts).

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`
- Create: `packages/core/src/openlia/prompts/report_dash_mr/debt_cycle.yaml`
- Test: extend `test_report_dash_mr_debt_cycle.py` to assert the system prompt names the four indicators and the emit-last contract.

- [ ] **Step 1: Write the failing assertion**

```python
def test_debt_cycle_system_prompt_lists_indicators():
    from openlia.llm.runtime.report_dash_mr.prompts import build_system_prompt
    from openlia.llm.runtime.report_dash_mr.schemas import RunRequest
    prompt = build_system_prompt(RunRequest(dashboard_slug="debt_cycle", model="x", provider_kind="x"))
    for token in ["debt/GDP", "interest", "TIPS", "DXY", "emit_dashboard"]:
        assert token in prompt
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/runtime/test_report_dash_mr_debt_cycle.py::test_debt_cycle_system_prompt_lists_indicators -v`
Expected: FAIL

- [ ] **Step 3: Implement the prompt**

Write `prompts/report_dash_mr/debt_cycle.yaml` with a positively-phrased task (gather → classify → narrate → emit), and have `build_system_prompt` load the slug's YAML, enumerate the available tools, and state the citation + emit-last contract. Reuse the shared includes pattern from `prompts/macro_research/debt_cycle.yaml`.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/runtime/test_report_dash_mr_debt_cycle.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py packages/core/src/openlia/prompts/report_dash_mr/
git commit -m "feat(mr): debt_cycle system prompt for report_dash_mr"
```

---

## Phase 1C — Persistence

### Task 7: `mr_dashboard_cache` model + migration

A simple per-(user, slug) cache: latest payload JSON + freshness. Model after `db/models/dashboard.py` and the `report_mb` table conventions.

**Files:**
- Create: `packages/server/src/openlia_server/db/models/mr_dashboard_cache.py`
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-06-03_0001_mr_dashboard_cache.py`
- Modify: `packages/server/src/openlia_server/db/models/register_all.py`
- Test: `packages/server/tests/test_macro_research/test_mr_dash_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_macro_research/test_mr_dash_cache.py
from datetime import UTC, datetime

from openlia_server.db.models.mr_dashboard_cache import MrDashboardCache


def test_cache_row_roundtrip(db_session, make_user):
    user = make_user()
    row = MrDashboardCache(
        user_id=user.id, dashboard="debt_cycle",
        payload_json='{"phaseBox": {"title": "Late plateau"}}',
        provenance="live", model_ref="claude-sonnet-4-6",
        generated_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.flush()
    fetched = db_session.query(MrDashboardCache).filter_by(
        user_id=user.id, dashboard="debt_cycle"
    ).one()
    assert "Late plateau" in fetched.payload_json
```

(Use the existing server test fixtures `db_session` / `make_user` — confirm their names in `packages/server/tests/conftest.py`.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/server/tests/test_macro_research/test_mr_dash_cache.py -v`
Expected: FAIL — model missing.

- [ ] **Step 3: Write the model**

```python
# packages/server/src/openlia_server/db/models/mr_dashboard_cache.py
"""Latest dashboard payload per (user, dashboard). The report_dash_mr
engine writes here on each scheduled/refresh run; the route reads it."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class MrDashboardCache(Base):
    __tablename__ = "mr_dashboard_cache"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dashboard: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(16), nullable=False, default="live")
    model_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_mr_dashboard_cache"),
        UniqueConstraint("user_id", "dashboard", name="uq_mr_dashboard_cache_user_dashboard"),
        Index("ix_mr_dashboard_cache_user_dashboard", "user_id", "dashboard"),
    )
```

Register it in `register_all.py` (add the import next to the other `db.models.*` imports).

- [ ] **Step 4: Generate + edit the migration**

Run: `uv run alembic -c packages/server/alembic.ini revision -m "mr_dashboard_cache"` (confirm the alembic config path; existing migrations live in `db/migrations/versions/`). Edit the generated file to `create_table("mr_dashboard_cache", ...)` matching the model, with the unique constraint and index; `downgrade` drops the table.

- [ ] **Step 5: Apply + run the test**

Run: `uv run alembic -c packages/server/alembic.ini upgrade head`
Run: `uv run pytest packages/server/tests/test_macro_research/test_mr_dash_cache.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/mr_dashboard_cache.py \
        packages/server/src/openlia_server/db/migrations/versions/ \
        packages/server/src/openlia_server/db/models/register_all.py \
        packages/server/tests/test_macro_research/test_mr_dash_cache.py
git commit -m "feat(mr): mr_dashboard_cache model + migration"
```

---

## Phase 1D — Run service, executor, scheduler wiring

### Task 8: `mr_dash_run_service` (run engine -> cache)

Mirror `mb_v2_run_service` but simpler: no sections/charts artifacts — just run the engine and upsert the typed payload into `mr_dashboard_cache`.

**Files:**
- Create: `packages/server/src/openlia_server/services/mr_dash_run_service.py`
- Test: `packages/server/tests/test_macro_research/test_mr_dash_run_service.py`

- [ ] **Step 1: Write the failing test** (run with a stub engine session; assert a cache row is upserted with the payload JSON). Model the stub on `mb_v2_run_service` tests.

- [ ] **Step 2: Run to verify it fails.** Run: `uv run pytest packages/server/tests/test_macro_research/test_mr_dash_run_service.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement.** Provide `build_run_request(db, *, user_id, dashboard_slug, model, provider_kind, enabled_connectors)` and `async run_to_cache(db, *, user_id, dashboard_slug, transports=None, session=None, cancel_token=None) -> str` that: builds the dispatcher (`build_mb_dispatcher`-analog or the macro_research dispatcher factory), constructs `report_dash_mr.Runner`, awaits `runner.run(...)`, then upserts `MrDashboardCache(user_id, dashboard=slug, payload_json=result.payload.model_dump_json(), provenance=result.payload.provenance, model_ref=request.model, generated_at=now)`.

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Commit.** `git commit -m "feat(mr): mr_dash_run_service runs engine to cache"`

### Task 9: `MrDashExecutor` + scheduler registration

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/executors/mr_dash.py`
- Modify: `packages/server/src/openlia_server/scheduler/registry.py` (add `MR_DASH = "mr_dash"`)
- Modify: `packages/server/src/openlia_server/scheduler/wiring.py` (register executor in the executors dict)
- Test: `packages/server/tests/test_macro_research/test_mr_dash_executor.py`

- [ ] **Step 1: Write the failing test** — call `MrDashExecutor._do_work(user_id=..., schedule_id="debt_cycle", run_id="r", cancel_token=None)` with a stubbed `run_service` and assert it returns a `JobOutcome` and invokes `run_to_cache(slug="debt_cycle")`. Mirror `test_*` for `MBBriefingExecutor`.

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** `MrDashExecutor(BaseExecutor)` with `job_type = JobType.MR_DASH`; `_do_work` reads the dashboard slug from `schedule_id` (reuse the existing `MrDashboardState` row keyed by `dashboard`, as `_register_schedule` already does for MR), calls `self._run_service.run_to_cache(session, user_id=user_id, dashboard_slug=slug)`, returns `JobOutcome(result_summary={"dashboard": slug})`. Add `JobType.MR_DASH` and register `MrDashExecutor(session_factory=...)` in `build_scheduler_service` executors dict.

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Commit.** `git commit -m "feat(mr): MrDashExecutor + MR_DASH job type wiring"`

### Task 10: App wiring

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`

- [ ] **Step 1:** In the scheduler lifespan block, import `mr_dash_run_service`, ensure `MrDashExecutor` is wired via `build_scheduler_service` (Task 9 already registers it). Confirm MR schedules (existing `MrDashboardState` rows with `assessment_schedule`) register under `JobType.MR_DASH` instead of the old `MR_ASSESSMENT` — update `_register_schedule`'s MR branch if it still points at the old job type.

- [ ] **Step 2: Smoke-run import.** Run: `uv run python -c "import openlia_server.app"` — Expected: no error.

- [ ] **Step 3: Commit.** `git commit -m "feat(mr): wire report_dash_mr scheduler path in app.py"`

---

## Phase 1E — Route + frontend

### Task 11: Route reads cache + refresh endpoint

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/macro_research.py`
- Test: `packages/server/tests/test_macro_research/test_mr_dash_route.py`

- [ ] **Step 1: Write the failing test** — seed an `mr_dashboard_cache` row for `debt_cycle`; `GET /api/departments/macro_research/dashboards/debt_cycle` returns 200 with the payload JSON + `generated_at` + `is_stale`. `POST .../debt_cycle/refresh` enqueues a job and returns 202.

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** `GET /dashboards/{slug}` to read the latest `MrDashboardCache` for the user+slug, parse `payload_json`, compute `is_stale` from `generated_at` + a per-slug TTL, return `{payload, generated_at, is_stale, provenance}`. If no cache row exists, return 200 with `{payload: null, is_stale: true}` (frontend shows skeleton/"not yet generated"). `POST /dashboards/{slug}/refresh` enqueues a `JobType.MR_DASH` run via the scheduler and returns 202. Remove the old tiered-assessment handler.

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Commit.** `git commit -m "feat(mr): dashboard route reads cache + refresh enqueue"`

### Task 12: Frontend — render debt_cycle from live cache

**Files:**
- Modify: `frontend/src/api/macro_research.ts` (`getDashboard` returns `{payload: DebtCycleData | null, generated_at, is_stale}`)
- Modify: `frontend/src/pages/departments/macro_research/DebtCycleView.tsx`
- Test: `frontend/src/pages/departments/macro_research/__tests__/DebtCycleView.test.tsx`

- [ ] **Step 1: Write the failing test** — mock `getDashboard("debt_cycle")` to resolve a payload; assert the view renders the live phase title and an "as-of" timestamp; mock a null payload and assert a skeleton/empty state (no fabricated numbers).

- [ ] **Step 2: Run to verify it fails.** Run: `cd frontend && npx vitest run src/pages/departments/macro_research/__tests__/DebtCycleView.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement** — replace the discarded-fetch + fallback in `DebtCycleView.tsx`:

```tsx
const [data, setData] = useState<DebtCycleData | null>(null);
const [loading, setLoading] = useState(true);
useEffect(() => {
  getDashboard("debt_cycle")
    .then((r) => setData(r.payload))
    .catch(() => setData(null))
    .finally(() => setLoading(false));
}, []);
if (loading) return <DashSkeleton />;
if (!data) return <DashEmpty slug="debt_cycle" />;  // "not yet generated" + Refresh
```

Remove the `DEBT_CYCLE_FALLBACK` import. Add a small `DashSkeleton` and `DashEmpty` to `_shared/widgets`. Render the real `generated_at` in the verdict meta instead of the hardcoded "April 2026".

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Delete the fallback file** once no view imports it (only `debt_cycle` is migrated this phase; keep the other four fallbacks until their phases). Leave `dalio_copy/debt_cycle.ts` deletion to the phase that removes its last import — for now, the import is gone from the view, so:

```bash
git rm frontend/src/lib/macro_research/dalio_copy/debt_cycle.ts
```

(Confirm no other file imports `DEBT_CYCLE_FALLBACK` first: `grep -rn DEBT_CYCLE_FALLBACK frontend/src`.)

- [ ] **Step 6: Run full frontend MR tests + commit**

Run: `cd frontend && npx vitest run src/pages/departments/macro_research`
Expected: PASS

```bash
git add frontend/src/api/macro_research.ts frontend/src/pages/departments/macro_research/ frontend/src/components/macro_research/
git commit -m "feat(mr): debt_cycle view renders live cache, fallback removed"
```

### Task 13: End-to-end manual verification

- [ ] **Step 1:** Start backend (`uv run openlia serve`, port 8080) and Vite (`cd frontend && npm run dev`, 5173).
- [ ] **Step 2:** Trigger a run: `POST /api/departments/macro_research/dashboards/debt_cycle/refresh`, wait for the job, then load the Debt Cycle tab. Confirm live numbers + an "as-of" timestamp render, and that the values trace to citations (check `report_*` tool-call log or the engine event stream).
- [ ] **Step 3:** Confirm Morning Briefing's `MRSnapshot` still resolves (the snapshot derives `debt_cycle_phase` from the new cache). Run: `uv run pytest packages/server/tests -k morning_briefing_snapshot -v` (targeted; full server suite hangs on SSE tests).

---

## Roadmap (follow-on plans)

Each is its own plan once Phase 1 proves the slice:

1. **Remaining dashboards (T2/T3/T4/T5 + Summary):** repeat Tasks 2/5/6/12 per dashboard — payload model, slug prompt, `emit_dashboard` model mapping, view swap. Extend `_PAYLOAD_MODEL_BY_SLUG`.
2. **Heavy quant:** `quant/markov.py` (12y growth/inflation transition matrix), `quant/montecarlo.py` (scenarios), `quant/var_causality.py` (post-1970 VAR), `quant/risk_parity.py` (port `risk_math.py`). Each pure + fixture-tested, exposed as quant tools.
3. **Curated reference data:** `macro_research/reference/` versioned datasets (1900-2026 composites, regime Sharpe tables, century causality) with `provenance="reference"` + `as_of` labeling.
4. **Provider-agnostic hardening + coverage preflight:** relax department connector requirements (WEB_SEARCH required, FINANCIAL optional); per-tile "source unavailable" degradation; surface the connector coverage map.
5. **Remove the old layer (MR):** delete `macro_research.needs.yaml`, MR adapter-LLM resolution, `assembler.py`, the MR `fetch_mr_t1_data` path, stubbed formulas; add the portfolio direct-quote helper; deprecate `mr_assessment_cache`.
6. **Retail Sentiment:** `report_dash_rs` sibling engine (separate spec; resolve the social-text data-source question first).

---

## Self-Review

- **Spec coverage:** Phase 1 implements the engine (spec §4.1), scheduled+cache execution (§4.2), the three-layer split for debt_cycle (§4.3), the payload contract + provenance (§5), debt_cycle's data/quant plan row (§6), MRSnapshot preservation (§5), and the route/frontend swap (§8). Heavy quant (§4.3 Markov/VAR/MonteCarlo), curated reference (§4.3 layer 3), provider-agnostic hardening (§9), and old-layer removal (§7) are explicitly deferred to the Roadmap — intentional decomposition, not gaps.
- **Placeholder scan:** Tasks 8/9 use prose steps (not full code) for fork-and-modify service/executor work where the exact template lines must be read at implementation time; each names the template file, the methods to mirror, and the test to write first. All pure-new code (quant, payloads, snapshot, model, tools) is given in full.
- **Type consistency:** `DebtCycleData` / `DebtCycleInputs` / `classify_debt_cycle` / `MrDashboardCache` / `run_to_cache` / `JobType.MR_DASH` / `emit_dashboard` names are used consistently across tasks. `RunRequest` gains `dashboard_slug`; `RunResult` gains `payload` — both noted at first use (Task 5).
- **Open item flagged for the engineer:** confirm `ResearchTool`/`ToolDescriptor`/`ToolResult` attribute names in the forked `registry.py` and adapt `dashboard_tools.py` accordingly (Task 5 Step 4 note); confirm server test fixture names and the alembic config path.
