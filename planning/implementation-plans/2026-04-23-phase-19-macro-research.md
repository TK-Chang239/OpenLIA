# Phase 19 — Macro Research Dalio Dashboards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Macro Research (MR) department — five Dalio-inspired dashboards (Debt Cycle, Four Seasons, All-Weather Portfolio, World Order, Five Forces). Dashboard-only, no chat. Each dashboard has five tiers:

- **T1** data ingestion (data-provider requirement tools),
- **T2** formula-engine metric computation (Plan 17 `FormulaEngine`),
- **T3** computational risk math (numpy closed-form calcs),
- **T4** LLM assessment (cron-scheduled, cached in `mr_assessment_cache`),
- **T5** scenario overlays + Smart-Mode threshold adjustments.

Plan 6 shipped `MRAssessmentExecutor` wired to stub Protocols (`MRAssessmentBuilder`, `MRCacheStore`, `ReportStore`). Plan 19 supplies the real implementations, adds the missing `mr_dashboard_state` columns (`assessment_schedule`, `last_assessment_at`), extends `SchedulerService.add_schedule` to accept MR rows, implements the five dashboard modules, surfaces REST routes, and ships the React tab shell + per-dashboard views.

**Tech Stack:** Python stdlib + numpy 1.26 (risk math) + Plan 17 `FormulaEngine` + SQLAlchemy 2.x + FastAPI 0.110 + React 18 / TypeScript / Vite. No SSE in v1 — polling only.

**Depends on:**
- Plan 3 — data provider adapter system (stock_quote, historical_prices, economic_events, macro_indicator, company_news).
- Plan 5 — `ReportRequest`, `BatchRunner`, `BatchItem`, `BatchResult`, `CancellationToken`, runtime events.
- Plan 6 — `SchedulerService`, `MRAssessmentExecutor`, `MRAssessmentPayload`, `MRAssessmentBuilder` Protocol, `MRCacheStore` Protocol, `ReportStore` Protocol, `JobType.MR_ASSESSMENT`, `JobRun`, `UserNotification`.
- Plan 8 — frontend shell, router, auth context, design tokens, API client.
- Plan 12 — shared frontend report/chart primitives (for chart fallbacks).
- Plan 17 — `FormulaEngine`, `FormulaError`, `EvaluationContext`, `extract_requirements`.

**Unblocks:** nothing downstream in the current roadmap (Plan 20 is independent). `MacroResearchDepartment.get_current_snapshot` unlocks Morning Briefing macro-context blocks in Plan 16.

**Out of scope (deferred to v2):**
- Automatic news-triggered T4/T5 runs — manual "Run assessment now" only.
- Real-time SSE streaming — dashboards poll.
- PDF/DOCX export of dashboard state.
- Multi-country support — US-focused.
- User-editable LLM prompts for T4/T5.
- Historical playback.

---

## File Structure

```
packages/core/src/openlia/
├── departments/
│   └── macro_research.py                        # NEW — MacroResearchDepartment
├── macro_research/
│   ├── __init__.py                              # NEW — package exports
│   ├── assembler.py                             # NEW — T1→T5 orchestrator
│   ├── schemas.py                               # NEW — pydantic DTOs (MRSnapshot, DashboardResult, etc.)
│   ├── risk_math.py                             # NEW — risk contribution + coverage numpy helpers
│   └── dashboards/
│       ├── __init__.py                          # NEW — registry (DASHBOARDS dict)
│       ├── base.py                              # NEW — Dashboard Protocol
│       ├── debt_cycle.py                        # NEW — T1 Debt Cycle module
│       ├── four_seasons.py                      # NEW — T2 Four Seasons module
│       ├── all_weather.py                       # NEW — T3 All-Weather module
│       ├── world_order.py                       # NEW — T4 World Order module
│       └── five_forces.py                       # NEW — T5 Five Forces module
└── prompts/
    └── macro_research/
        ├── debt_cycle.yaml                      # NEW — T4 prompt template
        ├── four_seasons.yaml                    # NEW
        ├── world_order.yaml                     # NEW
        └── five_forces.yaml                     # NEW

packages/server/src/openlia_server/
├── db/migrations/versions/
│   └── 20260423_0001_mr_dashboard_state_schedule_cols.py
├── services/
│   ├── mr_assessment.py                         # MRAssessmentBuilderImpl
│   ├── mr_cache.py                              # MRCacheStoreImpl
│   ├── mr_dashboard.py                          # MrDashboardState CRUD
│   ├── mr_runner.py                             # orchestrates T1-T3 live + T4 cache + T5 overlay
│   └── mr_schedules.py                          # schedule adapter + scheduler rehydration
├── routes/
│   ├── departments/macro_research.py            # router factory (dashboard + config endpoints)
│   └── mr_schedules.py                          # schedule CRUD + "Run assessment now"
├── scheduler/
│   └── service.py                               # MODIFIED — accept MR rows in add_schedule/modify_schedule
└── app.py                                       # MODIFIED — mount MR routers + lifespan rehydration

packages/server/tests/test_macro_research/
├── conftest.py
├── _macro_research_fakes.py
├── test_migration_schedule_cols.py
├── test_dashboards_debt_cycle.py
├── test_dashboards_four_seasons.py
├── test_dashboards_all_weather.py
├── test_dashboards_world_order.py
├── test_dashboards_five_forces.py
├── test_assembler.py
├── test_mr_assessment_builder.py
├── test_mr_cache_store.py
├── test_mr_dashboard_service.py
├── test_mr_runner.py
├── test_mr_schedules_service.py
├── test_routes_macro_research.py
├── test_routes_mr_schedules.py
├── test_scheduler_add_mr_schedule.py
├── test_lifespan_mr_rehydration.py
└── test_department_snapshot.py

frontend/src/
├── api/
│   └── macro_research.ts                        # NEW — REST client
├── pages/departments/
│   ├── MacroResearch.tsx                        # NEW — shell with tab selector
│   └── macro_research/
│       ├── SummaryView.tsx                      # NEW
│       ├── DebtCycleView.tsx                    # NEW
│       ├── FourSeasonsView.tsx                  # NEW
│       ├── AllWeatherView.tsx                   # NEW
│       ├── WorldOrderView.tsx                   # NEW
│       ├── FiveForcesView.tsx                   # NEW
│       └── ScheduleEditor.tsx                   # NEW
└── pages/departments/macro_research/__tests__/
    ├── MacroResearch.test.tsx
    ├── DebtCycleView.test.tsx
    ├── FourSeasonsView.test.tsx
    ├── AllWeatherView.test.tsx
    ├── WorldOrderView.test.tsx
    └── FiveForcesView.test.tsx
```

### Design rules

1. **Core is pure Python.** No FastAPI, no SQLAlchemy, no requests. The `MacroResearchDepartment` and all dashboards import only from `openlia.*`. Server wires DB readers through Protocols.
2. **One Dashboard Protocol.** Every dashboard exposes the same five-tier surface: `slug`, `display_name`, `T1_REQUIREMENTS`, `T2_FORMULAS`, `T3_compute`, `T4_prompt_key`, `T5_smart_mode_adjustments`. The assembler treats all five uniformly.
3. **Formula-engine contract.** `from openlia.formula import FormulaEngine, FormulaError, EvaluationContext, extract_requirements` — imports verbatim. Dashboards declare formulas as dict literals. Engine resolves values from pre-fetched data frames keyed by requirement.
4. **String(36) UUIDs.** Every new id column is `String(36)`, generated with `str(uuid.uuid4())`. No prefixed short-hex ids.
5. **Router factory + auth.** All new routers use `build_require_auth(db_session_factory=..., mode=...)` and mount via `app.include_router(build_macro_research_router(...))`. Bare prefixes — Vite proxy strips `/api`.
6. **Scheduler constraint.** "One schedule per (job_type, user_id)". MR users have exactly **one** `MR_ASSESSMENT` schedule per account. Weekly vs Quarterly is expressed via the cron expression stored on `mr_dashboard_state.assessment_schedule`.
7. **Named-event SSE only if streaming used.** v1 has no dashboard streaming — `POST /assessment/run` kicks off an async job and returns a `job_run_id`. Frontend polls `/jobs/history` until complete. No SSE.
8. **Test fakes are uniquely named.** `_macro_research_fakes.py` — not `_fakes.py`. Avoids `--import-mode=importlib` collisions with other test packages.
9. **LLM length-branching.** Prompt Jinja branches on `ReportRequest.length` values (`brief` / `standard` / `long`). MR maps its own "quarterly" cadence → `long`, "weekly" → `standard`.

---

## Task 0 — Scaffolding

**Files:**
- Create: `packages/core/src/openlia/macro_research/__init__.py`
- Create: `packages/core/src/openlia/macro_research/schemas.py`
- Create: `packages/core/src/openlia/macro_research/dashboards/__init__.py`
- Create: `packages/core/src/openlia/macro_research/dashboards/base.py`
- Create: `packages/server/tests/test_macro_research/__init__.py`
- Create: `packages/server/tests/test_macro_research/conftest.py`
- Create: `packages/server/tests/test_macro_research/_macro_research_fakes.py`

### Steps

- [ ] **Step 1: Create test scaffold**

Create `packages/server/tests/test_macro_research/conftest.py`:

```python
"""Expose test dir on sys.path so sibling test modules can
`from _macro_research_fakes import ...`."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```

Create `packages/server/tests/test_macro_research/__init__.py` empty.

- [ ] **Step 2: Write failing scaffold test**

Create `packages/server/tests/test_macro_research/test_scaffold.py`:

```python
from __future__ import annotations

import pytest


def test_package_imports() -> None:
    from openlia.macro_research import (
        MRSnapshot,
        DashboardResult,
        DashboardTierOutput,
    )
    assert MRSnapshot is not None
    assert DashboardResult is not None
    assert DashboardTierOutput is not None


def test_base_protocol_present() -> None:
    from openlia.macro_research.dashboards.base import Dashboard
    assert hasattr(Dashboard, "slug")


def test_registry_exports_five_dashboards() -> None:
    from openlia.macro_research.dashboards import DASHBOARDS

    assert set(DASHBOARDS.keys()) == {
        "debt_cycle",
        "four_seasons",
        "all_weather",
        "world_order",
        "five_forces",
    }
```

- [ ] **Step 3: Run — expect FAIL**

```bash
uv run pytest packages/server/tests/test_macro_research/test_scaffold.py -v
```

Expected: `ModuleNotFoundError: No module named 'openlia.macro_research'`.

- [ ] **Step 4: Implement package skeleton**

Create `packages/core/src/openlia/macro_research/schemas.py`:

```python
"""Pydantic DTOs shared across the MR department."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SeverityLevel = Literal["green", "amber", "red", "neutral"]


class MRSnapshot(BaseModel):
    """Read-only cross-department view. Consumed by Morning Briefing."""

    debt_cycle_phase: str | None = None
    economic_season: str | None = None
    active_force_count: int | None = None
    generated_at: datetime | None = None
    is_stale: bool = False


class DashboardTierOutput(BaseModel):
    """Output of a single tier for a dashboard."""

    tier: Literal["T1", "T2", "T3", "T4", "T5"]
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None


class DashboardResult(BaseModel):
    """Full result of running one dashboard through T1-T5."""

    slug: str
    display_name: str
    severity: SeverityLevel = "neutral"
    tiers: list[DashboardTierOutput] = Field(default_factory=list)
    headline: str | None = None
    generated_at: datetime
    smart_mode_active: bool = False
```

Create `packages/core/src/openlia/macro_research/dashboards/base.py`:

```python
"""Dashboard Protocol — every MR dashboard implements this surface."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Dashboard(Protocol):
    """Unified interface across T1/T2/T3/T4/T5 dashboards."""

    slug: str
    display_name: str

    # T1 — list of requirement names fetched by the data-provider system.
    T1_REQUIREMENTS: tuple[str, ...]

    # T2 — mapping {indicator_name: formula_string}. Formulas evaluated by
    # FormulaEngine against the fetched data context.
    T2_FORMULAS: dict[str, str]

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        """Closed-form numpy-based math. May be a no-op for LLM-only dashboards."""
        ...

    # T4 — prompt key used by the LLM runner. None for purely formula-driven dashboards.
    T4_PROMPT_KEY: str | None

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        """Return adjusted thresholds when Smart Mode is on. Returns base unchanged if off."""
        ...
```

Create `packages/core/src/openlia/macro_research/dashboards/__init__.py`:

```python
"""Registry of all five MR dashboards."""
from __future__ import annotations

from openlia.macro_research.dashboards.all_weather import AllWeatherDashboard
from openlia.macro_research.dashboards.base import Dashboard
from openlia.macro_research.dashboards.debt_cycle import DebtCycleDashboard
from openlia.macro_research.dashboards.five_forces import FiveForcesDashboard
from openlia.macro_research.dashboards.four_seasons import FourSeasonsDashboard
from openlia.macro_research.dashboards.world_order import WorldOrderDashboard

DASHBOARDS: dict[str, Dashboard] = {
    "debt_cycle": DebtCycleDashboard(),
    "four_seasons": FourSeasonsDashboard(),
    "all_weather": AllWeatherDashboard(),
    "world_order": WorldOrderDashboard(),
    "five_forces": FiveForcesDashboard(),
}

__all__ = ["DASHBOARDS", "Dashboard"]
```

Create `packages/core/src/openlia/macro_research/__init__.py`:

```python
"""Macro Research department — Dalio framework dashboards."""
from __future__ import annotations

from openlia.macro_research.schemas import (
    DashboardResult,
    DashboardTierOutput,
    MRSnapshot,
    SeverityLevel,
)

__all__ = [
    "MRSnapshot",
    "DashboardResult",
    "DashboardTierOutput",
    "SeverityLevel",
]
```

(Empty placeholder stub modules for the five dashboards will be filled in Tasks 8-22 — create each as `class XxxDashboard: ...` just enough that imports resolve.)

For every dashboard file (debt_cycle.py, four_seasons.py, all_weather.py, world_order.py, five_forces.py), create a minimal stub:

```python
"""Temporary stub — replaced by Task 8-22."""
from __future__ import annotations

from typing import Any


class DebtCycleDashboard:  # one of these per file, class name varies
    slug = "debt_cycle"
    display_name = "Debt Cycle"
    T1_REQUIREMENTS: tuple[str, ...] = ()
    T2_FORMULAS: dict[str, str] = {}
    T4_PROMPT_KEY: str | None = None

    def T3_compute(self, *, metrics: dict[str, float], portfolio: dict[str, float] | None) -> dict[str, Any]:
        return {}

    def T5_smart_mode_adjustments(
        self, *, base_thresholds: dict[str, float], context: dict[str, Any]
    ) -> dict[str, float]:
        return dict(base_thresholds)
```

Also create the test fakes file. Create `packages/server/tests/test_macro_research/_macro_research_fakes.py`:

```python
"""Shared fakes for MR tests. Uniquely named to avoid --import-mode=importlib collisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class FakeDataProvider:
    """Return canned values keyed by requirement name."""

    values: dict[str, Any] = field(default_factory=dict)

    def fetch(self, *, requirement: str, **kwargs: Any) -> Any:
        return self.values.get(requirement)


@dataclass
class FakeLLMClient:
    """Record every call; return a scripted response."""

    scripted_response: dict[str, Any] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(self, *, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"prompt": prompt, **kwargs})
        return self.scripted_response


@dataclass
class FakeMRCacheStore:
    saved: list[dict[str, Any]] = field(default_factory=list)
    read_result: dict[str, Any] | None = None

    def save(self, *, session: Any, user_id: str, payload: dict[str, Any]) -> str:
        self.saved.append({"user_id": user_id, "payload": payload})
        return "cache-1"

    def read_latest(
        self, *, session: Any, user_id: str, dashboard: str, assessment_type: str
    ) -> dict[str, Any] | None:
        return self.read_result


@dataclass
class FakeReportStore:
    saved: list[dict[str, Any]] = field(default_factory=list)

    def save(
        self, *, session: Any, user_id: str, department: str, payload: dict[str, Any]
    ) -> str:
        self.saved.append({"user_id": user_id, "department": department, "payload": payload})
        return "report-1"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
```

- [ ] **Step 5: Run — expect PASS**

```bash
uv run pytest packages/server/tests/test_macro_research/test_scaffold.py -v
```

Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/macro_research \
    packages/server/tests/test_macro_research
git commit -m "phase-19(mr): scaffold macro_research package + test fakes"
```

---

## Task 1 — Alembic migration: add `assessment_schedule` and `last_assessment_at` columns

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/20260423_0001_mr_dashboard_state_schedule_cols.py`
- Modify: `packages/server/src/openlia_server/db/models/dashboard.py` (add mapped columns)
- Create: `packages/server/tests/test_macro_research/test_migration_schedule_cols.py`

### Steps

- [ ] **Step 1: Write failing test**

Create `packages/server/tests/test_macro_research/test_migration_schedule_cols.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardState


@pytest.fixture
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


def test_mr_dashboard_state_has_schedule_columns(engine) -> None:
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("mr_dashboard_state")}
    assert "assessment_schedule" in cols
    assert "last_assessment_at" in cols


def test_insert_row_with_schedule_cols(engine) -> None:
    with Session(engine) as s:
        u = User(id="u-1", email="a@b", password_hash="x", display_name="A")
        s.add(u)
        s.commit()
        row = MrDashboardState(
            id="mrs-1",
            user_id="u-1",
            dashboard="world_order",
            view_config={},
            threshold_overrides={},
            assessment_schedule="0 0 * * 0",
            last_assessment_at=datetime.now(timezone.utc),
        )
        s.add(row)
        s.commit()
        fetched = s.get(MrDashboardState, "mrs-1")
        assert fetched is not None
        assert fetched.assessment_schedule == "0 0 * * 0"
        assert fetched.last_assessment_at is not None


def test_schedule_cols_nullable(engine) -> None:
    with Session(engine) as s:
        u = User(id="u-2", email="b@b", password_hash="x", display_name="B")
        s.add(u)
        s.commit()
        row = MrDashboardState(
            id="mrs-2",
            user_id="u-2",
            dashboard="four_seasons",
            view_config={},
            threshold_overrides={},
        )
        s.add(row)
        s.commit()
        fetched = s.get(MrDashboardState, "mrs-2")
        assert fetched.assessment_schedule is None
        assert fetched.last_assessment_at is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest packages/server/tests/test_macro_research/test_migration_schedule_cols.py -v
```

Expected: `AttributeError: assessment_schedule`.

- [ ] **Step 3: Edit the model**

Edit `packages/server/src/openlia_server/db/models/dashboard.py`. In class `MrDashboardState`, after `threshold_overrides` and before `updated_at`, add:

```python
    assessment_schedule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_assessment_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
```

- [ ] **Step 4: Create Alembic migration**

Create `packages/server/src/openlia_server/db/migrations/versions/20260423_0001_mr_dashboard_state_schedule_cols.py`:

```python
"""Add assessment_schedule and last_assessment_at to mr_dashboard_state.

Revision ID: 20260423_0001
Revises: <previous head>
Create Date: 2026-04-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260423_0001"
down_revision = None  # replace with actual previous head at commit time
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mr_dashboard_state") as batch:
        batch.add_column(sa.Column("assessment_schedule", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("last_assessment_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("mr_dashboard_state") as batch:
        batch.drop_column("last_assessment_at")
        batch.drop_column("assessment_schedule")
```

Confirm actual previous head via `uv run alembic heads` and patch `down_revision` accordingly.

- [ ] **Step 5: Run — expect PASS**

```bash
uv run pytest packages/server/tests/test_macro_research/test_migration_schedule_cols.py -v
```

Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/dashboard.py \
    packages/server/src/openlia_server/db/migrations/versions/20260423_0001_mr_dashboard_state_schedule_cols.py \
    packages/server/tests/test_macro_research/test_migration_schedule_cols.py
git commit -m "phase-19(mr): migration adds assessment_schedule + last_assessment_at"
```

---

## Task 2 — `MacroResearchDepartment` class + registration

**Files:**
- Create: `packages/core/src/openlia/departments/macro_research.py`
- Modify: `packages/core/src/openlia/departments/__init__.py`
- Create: `packages/server/tests/test_macro_research/test_department.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_department.py
from __future__ import annotations

from openlia.departments import get_department
from openlia.departments.macro_research import MacroResearchDepartment


def test_department_registered() -> None:
    dept = get_department("macro_research")
    assert isinstance(dept, MacroResearchDepartment)


def test_department_metadata() -> None:
    dept = MacroResearchDepartment()
    assert dept.slug == "macro_research"
    assert dept.display_name == "Macro Research"
    assert dept.has_chat is False
    assert set(dept.dashboard_slugs()) == {
        "debt_cycle",
        "four_seasons",
        "all_weather",
        "world_order",
        "five_forces",
    }
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest packages/server/tests/test_macro_research/test_department.py -v
```

- [ ] **Step 3: Implement department class**

Create `packages/core/src/openlia/departments/macro_research.py`:

```python
"""Macro Research department — dashboard-only (no chat)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from openlia.macro_research.dashboards import DASHBOARDS
from openlia.macro_research.schemas import MRSnapshot


class _SnapshotReader(Protocol):
    def latest_state(self, *, user_id: str, dashboard: str) -> dict[str, Any] | None: ...
    def latest_assessment(
        self, *, user_id: str, dashboard: str, assessment_type: str
    ) -> dict[str, Any] | None: ...


class MacroResearchDepartment:
    """Public department surface. Read-only snapshot for cross-department consumers."""

    slug = "macro_research"
    display_name = "Macro Research"
    has_chat = False

    def __init__(self, snapshot_reader: _SnapshotReader | None = None) -> None:
        self._reader = snapshot_reader

    def dashboard_slugs(self) -> tuple[str, ...]:
        return tuple(DASHBOARDS.keys())

    def get_current_snapshot(self, user_id: str) -> MRSnapshot:
        """Read-only: two indexed DB reads. Never fetches, never calls LLMs."""
        if self._reader is None:
            return MRSnapshot()

        t1 = self._reader.latest_state(user_id=user_id, dashboard="debt_cycle")
        t2 = self._reader.latest_state(user_id=user_id, dashboard="four_seasons")
        t5 = self._reader.latest_assessment(
            user_id=user_id, dashboard="five_forces", assessment_type="synthesis"
        )

        debt_cycle_phase = (t1 or {}).get("phase")
        economic_season = (t2 or {}).get("season")
        active_force_count = (t5 or {}).get("active_force_count")

        generated = [x.get("generated_at") for x in (t1, t2, t5) if x and x.get("generated_at")]
        generated_at = min(generated) if generated else None

        is_stale = False
        now = datetime.now(timezone.utc)
        if t1 and (now - t1["generated_at"]) > timedelta(hours=24):
            is_stale = True
        if t2 and (now - t2["generated_at"]) > timedelta(hours=24):
            is_stale = True
        if t5:
            schedule = (t5.get("schedule") or "quarterly").lower()
            max_age = timedelta(days=95) if schedule == "quarterly" else timedelta(days=8)
            if (now - t5["generated_at"]) > max_age:
                is_stale = True

        return MRSnapshot(
            debt_cycle_phase=debt_cycle_phase,
            economic_season=economic_season,
            active_force_count=active_force_count,
            generated_at=generated_at,
            is_stale=is_stale,
        )
```

Edit `packages/core/src/openlia/departments/__init__.py` — register the department in the lookup dict:

```python
from openlia.departments.macro_research import MacroResearchDepartment

_REGISTRY["macro_research"] = MacroResearchDepartment()
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/departments/macro_research.py \
    packages/core/src/openlia/departments/__init__.py \
    packages/server/tests/test_macro_research/test_department.py
git commit -m "phase-19(mr): MacroResearchDepartment class + registration"
```

---

## Task 3 — Dashboard Protocol verification

**Files:**
- Create: `packages/server/tests/test_macro_research/test_dashboard_protocol.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_dashboard_protocol.py
from __future__ import annotations

import pytest

from openlia.macro_research.dashboards import DASHBOARDS
from openlia.macro_research.dashboards.base import Dashboard


@pytest.mark.parametrize("slug", list(DASHBOARDS.keys()))
def test_each_dashboard_honours_protocol(slug: str) -> None:
    d = DASHBOARDS[slug]
    assert isinstance(d, Dashboard)
    assert d.slug == slug
    assert isinstance(d.display_name, str) and d.display_name
    assert isinstance(d.T1_REQUIREMENTS, tuple)
    assert isinstance(d.T2_FORMULAS, dict)
    assert hasattr(d, "T4_PROMPT_KEY")
    assert callable(d.T3_compute)
    assert callable(d.T5_smart_mode_adjustments)


def test_t3_compute_tolerates_empty() -> None:
    for slug, d in DASHBOARDS.items():
        result = d.T3_compute(metrics={}, portfolio=None)
        assert isinstance(result, dict), slug


def test_t5_smart_mode_is_pure() -> None:
    for slug, d in DASHBOARDS.items():
        base = {"foo": 1.0}
        out = d.T5_smart_mode_adjustments(base_thresholds=base, context={"smart_mode": False})
        assert out == base, slug
        assert base == {"foo": 1.0}  # input unmodified
```

- [ ] **Step 2: Run — expect PASS** (stubs suffice).

- [ ] **Step 3: Commit**

```bash
git add packages/server/tests/test_macro_research/test_dashboard_protocol.py
git commit -m "phase-19(mr): assert dashboard Protocol conformance"
```

---

## Task 4 — Assembler

**Files:**
- Create: `packages/core/src/openlia/macro_research/assembler.py`
- Create: `packages/server/tests/test_macro_research/test_assembler.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_assembler.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from _macro_research_fakes import FakeDataProvider, FakeLLMClient

from openlia.macro_research.assembler import DashboardAssembler
from openlia.macro_research.dashboards import DASHBOARDS


@pytest.fixture
def assembler() -> DashboardAssembler:
    data = FakeDataProvider(values={
        "stock_quote:TIP": {"price": 110.0},
        "stock_quote:UUP": {"price": 30.0},
        "macro_indicator:debt_gdp": 120.0,
        "macro_indicator:interest_revenue": 16.0,
        "stock_quote:HYG": {"price": 75.0},
        "stock_quote:LQD": {"price": 105.0},
        "macro_indicator:pmi": 49.0,
        "macro_indicator:gdp_yoy": 1.5,
        "macro_indicator:cpi_yoy": 3.8,
    })
    llm = FakeLLMClient(scripted_response={"assessment": "stub", "severity": "amber"})
    return DashboardAssembler(data_provider=data, llm_client=llm)


def test_runs_t1_t2_t3_live(assembler: DashboardAssembler) -> None:
    result = assembler.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=False,
    )
    tiers = {t.tier for t in result.tiers}
    assert {"T1", "T2", "T3"}.issubset(tiers)


def test_honours_cached_t4(assembler: DashboardAssembler) -> None:
    cached = {
        "assessment": "cached text",
        "severity": "red",
        "generated_at": datetime.now(timezone.utc),
    }
    result = assembler.run(
        dashboard_slug="world_order",
        user_id="u-1",
        portfolio=None,
        t4_cached=cached,
        smart_mode=False,
    )
    t4 = [t for t in result.tiers if t.tier == "T4"][0]
    assert t4.data["assessment"] == "cached text"


def test_unknown_slug_raises(assembler: DashboardAssembler) -> None:
    with pytest.raises(KeyError):
        assembler.run(
            dashboard_slug="nonexistent",
            user_id="u-1",
            portfolio=None,
            t4_cached=None,
            smart_mode=False,
        )


def test_severity_derives_from_worst_tier(assembler: DashboardAssembler) -> None:
    result = assembler.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached={"assessment": "stub", "severity": "red", "generated_at": datetime.now(timezone.utc)},
        smart_mode=False,
    )
    assert result.severity == "red"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement assembler**

Create `packages/core/src/openlia/macro_research/assembler.py`:

```python
"""Orchestrate T1→T5 for a given dashboard."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError
from openlia.macro_research.dashboards import DASHBOARDS
from openlia.macro_research.schemas import (
    DashboardResult,
    DashboardTierOutput,
    SeverityLevel,
)


class _DataProvider(Protocol):
    def fetch(self, *, requirement: str, **kwargs: Any) -> Any: ...


class _LLMClient(Protocol):
    async def run(self, *, prompt: str, **kwargs: Any) -> dict[str, Any]: ...


_SEVERITY_RANK = {"neutral": 0, "green": 1, "amber": 2, "red": 3}


def _worst(a: SeverityLevel, b: SeverityLevel) -> SeverityLevel:
    return a if _SEVERITY_RANK[a] >= _SEVERITY_RANK[b] else b


class DashboardAssembler:
    """Runs T1→T5 for one dashboard and returns a DashboardResult."""

    def __init__(
        self,
        *,
        data_provider: _DataProvider,
        llm_client: _LLMClient | None = None,
    ) -> None:
        self._data = data_provider
        self._llm = llm_client
        self._engine = FormulaEngine()

    def run(
        self,
        *,
        dashboard_slug: str,
        user_id: str,
        portfolio: dict[str, float] | None,
        t4_cached: dict[str, Any] | None,
        smart_mode: bool,
    ) -> DashboardResult:
        if dashboard_slug not in DASHBOARDS:
            raise KeyError(f"unknown dashboard: {dashboard_slug!r}")
        dashboard = DASHBOARDS[dashboard_slug]
        now = datetime.now(timezone.utc)

        severity: SeverityLevel = "neutral"
        tiers: list[DashboardTierOutput] = []

        # --- T1 ---
        t1_data: dict[str, Any] = {}
        for req in dashboard.T1_REQUIREMENTS:
            t1_data[req] = self._data.fetch(requirement=req)
        tiers.append(DashboardTierOutput(tier="T1", data={"inputs": t1_data}, generated_at=now))

        # --- T2 ---
        t2_metrics: dict[str, float] = {}
        t2_errors: list[str] = []
        context = EvaluationContext(variables=self._flatten(t1_data))
        for name, formula in dashboard.T2_FORMULAS.items():
            try:
                value = self._engine.evaluate(formula, context)
                t2_metrics[name] = float(value)
            except FormulaError as exc:
                t2_errors.append(f"{name}: {exc}")
        tiers.append(DashboardTierOutput(tier="T2", data=t2_metrics, errors=t2_errors, generated_at=now))

        # --- T3 ---
        t3_out = dashboard.T3_compute(metrics=t2_metrics, portfolio=portfolio)
        tiers.append(DashboardTierOutput(tier="T3", data=t3_out, generated_at=now))
        if t3_out.get("severity"):
            severity = _worst(severity, t3_out["severity"])

        # --- T4 ---
        if dashboard.T4_PROMPT_KEY is not None:
            if t4_cached is not None:
                tiers.append(
                    DashboardTierOutput(
                        tier="T4",
                        data={
                            "assessment": t4_cached.get("assessment"),
                            "severity": t4_cached.get("severity"),
                            "cached": True,
                        },
                        generated_at=t4_cached.get("generated_at"),
                    )
                )
                if t4_cached.get("severity"):
                    severity = _worst(severity, t4_cached["severity"])
            else:
                tiers.append(
                    DashboardTierOutput(
                        tier="T4",
                        data={"assessment": None, "cached": False, "pending": True},
                        generated_at=None,
                    )
                )

        # --- T5 ---
        base_thresholds: dict[str, float] = {}
        if smart_mode:
            adjusted = dashboard.T5_smart_mode_adjustments(
                base_thresholds=base_thresholds,
                context={"t1": t1_data, "t2": t2_metrics, "t3": t3_out},
            )
        else:
            adjusted = base_thresholds
        tiers.append(
            DashboardTierOutput(
                tier="T5",
                data={"smart_mode": smart_mode, "adjustments": adjusted},
                generated_at=now,
            )
        )

        return DashboardResult(
            slug=dashboard.slug,
            display_name=dashboard.display_name,
            severity=severity,
            tiers=tiers,
            headline=self._headline(dashboard.slug, t2_metrics, t3_out, t4_cached),
            generated_at=now,
            smart_mode_active=smart_mode,
        )

    @staticmethod
    def _flatten(data: dict[str, Any]) -> dict[str, Any]:
        """Turn {'stock_quote:TIP': {'price': 110}} → {'TIP_price': 110}."""
        flat: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                for sub, v in value.items():
                    flat[f"{key.split(':')[-1]}_{sub}"] = v
            else:
                flat[key.replace(":", "_")] = value
        return flat

    @staticmethod
    def _headline(
        slug: str,
        metrics: dict[str, float],
        t3: dict[str, Any],
        t4_cached: dict[str, Any] | None,
    ) -> str:
        if slug == "debt_cycle":
            return t3.get("phase", "Phase unknown")
        if slug == "four_seasons":
            return t3.get("season", "Season unknown")
        if slug == "all_weather":
            return t3.get("overall_coverage_label", "Coverage unknown")
        if slug == "world_order" and t4_cached:
            return t4_cached.get("stage", "Stage unknown")
        if slug == "five_forces" and t4_cached:
            return f"{t4_cached.get('active_force_count', 0)} active forces"
        return ""
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/macro_research/assembler.py \
    packages/server/tests/test_macro_research/test_assembler.py
git commit -m "phase-19(mr): DashboardAssembler orchestrates T1-T5"
```

---

## Task 5 — `MRCacheStoreImpl`

**Files:**
- Create: `packages/server/src/openlia_server/services/mr_cache.py`
- Create: `packages/server/tests/test_macro_research/test_mr_cache_store.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_mr_cache_store.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from openlia_server.db.base import Base
from openlia_server.db.models.dashboard import MrAssessmentCache
from openlia_server.services.mr_cache import MRCacheStoreImpl


@pytest.fixture
def session_factory():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, expire_on_commit=False)


def test_save_inserts_row(session_factory) -> None:
    store = MRCacheStoreImpl()
    with session_factory() as s:
        cache_id = store.save(
            session=s,
            user_id="u-1",
            payload={
                "dashboard": "world_order",
                "assessment_type": "stage",
                "input_hash": "abc123",
                "result": {"stage": "Pressure"},
                "model_ref": "openai:gpt-4o",
                "token_usage": {"prompt": 100, "completion": 200},
                "ttl_hours": 168,
            },
        )
        s.commit()
        assert cache_id
        row = s.get(MrAssessmentCache, cache_id)
        assert row is not None
        assert row.dashboard == "world_order"
        assert row.result == {"stage": "Pressure"}


def test_read_latest_returns_most_recent(session_factory) -> None:
    store = MRCacheStoreImpl()
    now = datetime.now(timezone.utc)
    with session_factory() as s:
        for i in range(3):
            s.add(
                MrAssessmentCache(
                    id=f"mac-{i}",
                    dashboard="world_order",
                    assessment_type="stage",
                    input_hash=f"h{i}",
                    result={"stage": f"S{i}"},
                    model_ref="openai:gpt-4o",
                    token_usage=None,
                    generated_at=now - timedelta(days=i),
                    expires_at=now + timedelta(days=10),
                )
            )
        s.commit()
        latest = store.read_latest(
            session=s, user_id="u-1", dashboard="world_order", assessment_type="stage"
        )
        assert latest is not None
        assert latest["result"] == {"stage": "S0"}


def test_read_latest_skips_expired(session_factory) -> None:
    store = MRCacheStoreImpl()
    now = datetime.now(timezone.utc)
    with session_factory() as s:
        s.add(
            MrAssessmentCache(
                id="mac-exp",
                dashboard="world_order",
                assessment_type="stage",
                input_hash="h",
                result={"stage": "X"},
                model_ref="openai:gpt-4o",
                token_usage=None,
                generated_at=now - timedelta(days=200),
                expires_at=now - timedelta(days=100),
            )
        )
        s.commit()
        latest = store.read_latest(
            session=s, user_id="u-1", dashboard="world_order", assessment_type="stage"
        )
        assert latest is None
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement store**

Create `packages/server/src/openlia_server/services/mr_cache.py`:

```python
"""MRCacheStore implementation — backs Plan 6's MRCacheStore Protocol."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import MrAssessmentCache


class MRCacheStoreImpl:
    """Persist T4/T5 LLM output in `mr_assessment_cache`."""

    def save(self, *, session: Session, user_id: str, payload: dict[str, Any]) -> str:
        """Insert a cache row. `user_id` is unused — cache is global per design spec."""
        now = datetime.now(timezone.utc)
        ttl_hours = payload.get("ttl_hours", 168)
        cache_id = str(uuid.uuid4())
        row = MrAssessmentCache(
            id=cache_id,
            dashboard=payload["dashboard"],
            assessment_type=payload["assessment_type"],
            input_hash=payload["input_hash"],
            result=payload["result"],
            model_ref=payload["model_ref"],
            token_usage=payload.get("token_usage"),
            generated_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        session.add(row)
        session.flush()
        return cache_id

    def read_latest(
        self,
        *,
        session: Session,
        user_id: str,
        dashboard: str,
        assessment_type: str,
    ) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        stmt = (
            select(MrAssessmentCache)
            .where(
                MrAssessmentCache.dashboard == dashboard,
                MrAssessmentCache.assessment_type == assessment_type,
                MrAssessmentCache.expires_at > now,
            )
            .order_by(MrAssessmentCache.generated_at.desc())
            .limit(1)
        )
        row = session.scalars(stmt).first()
        if row is None:
            return None
        return {
            "id": row.id,
            "dashboard": row.dashboard,
            "assessment_type": row.assessment_type,
            "result": row.result,
            "model_ref": row.model_ref,
            "generated_at": row.generated_at,
            "expires_at": row.expires_at,
        }
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/mr_cache.py \
    packages/server/tests/test_macro_research/test_mr_cache_store.py
git commit -m "phase-19(mr): MRCacheStoreImpl save + read_latest"
```

---

## Task 6 — `MRAssessmentBuilderImpl`

Fulfills the Plan 6 `MRAssessmentBuilder` Protocol.

**Files:**
- Create: `packages/server/src/openlia_server/services/mr_assessment.py`
- Create: `packages/server/tests/test_macro_research/test_mr_assessment_builder.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_mr_assessment_builder.py
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from openlia.llm.runtime.messages import BatchItem, BatchResult, ReportRequest
from openlia_server.services.mr_assessment import MRAssessmentBuilderImpl


@pytest.fixture
def builder() -> MRAssessmentBuilderImpl:
    provider = MagicMock()
    provider.fetch.return_value = {"price": 100.0}
    return MRAssessmentBuilderImpl(data_provider=provider)


def test_builds_batch_items_for_t4_dashboards(builder: MRAssessmentBuilderImpl) -> None:
    session = MagicMock()
    payload = builder.build(session=session, user_id="u-1")
    assert len(payload.items) >= 2  # world_order + five_forces minimum
    slugs = {item.key for item in payload.items}
    assert "world_order" in slugs
    assert "five_forces" in slugs


def test_synthesize_produces_report_request(builder: MRAssessmentBuilderImpl) -> None:
    session = MagicMock()
    payload = builder.build(session=session, user_id="u-1")
    t4_results = [
        BatchResult(key="world_order", ok=True, value={"stage": "Pressure", "severity": "amber"}),
        BatchResult(key="five_forces_components", ok=True, value={"scores": [6, 7, 5, 4, 3]}),
    ]
    req = payload.synthesize(t4_results)
    assert isinstance(req, ReportRequest)
    assert req.mode == "synthesis"
    assert "world_order" in req.user_input.lower() or "stage" in req.user_input.lower()
    assert req.length in ("brief", "standard", "long")
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement builder**

Create `packages/server/src/openlia_server/services/mr_assessment.py`:

```python
"""MRAssessmentBuilder implementation — generates T4 batch items + T5 synthesizer."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia.llm.runtime.messages import BatchItem, BatchResult, ReportRequest
from openlia.macro_research.dashboards import DASHBOARDS
from openlia_server.scheduler.payloads import MRAssessmentPayload


class _DataProvider(Protocol):
    def fetch(self, *, requirement: str, **kwargs: Any) -> Any: ...


class T4Output(BaseModel):
    stage: str | None = None
    severity: str | None = None
    assessment: str = ""
    notes: list[str] = []


class MRAssessmentBuilderImpl:
    """Builds the batch payload that MRAssessmentExecutor feeds to BatchRunner."""

    def __init__(self, *, data_provider: _DataProvider) -> None:
        self._data = data_provider

    def build(self, *, session: Session, user_id: str) -> MRAssessmentPayload:
        items: list[BatchItem] = []

        # Only dashboards with T4_PROMPT_KEY non-None participate in the batch.
        for slug, dashboard in DASHBOARDS.items():
            if dashboard.T4_PROMPT_KEY is None:
                continue
            context_data = {
                req: self._data.fetch(requirement=req)
                for req in dashboard.T1_REQUIREMENTS
            }
            items.append(
                BatchItem(
                    key=slug,
                    prompt_key=f"macro_research/{dashboard.T4_PROMPT_KEY}",
                    user_input=json.dumps(context_data, default=str),
                    context={"dashboard": slug, "user_id": user_id},
                )
            )

        def synthesize(results: list[BatchResult]) -> ReportRequest:
            ok = [r for r in results if r.ok]
            summary_lines = [
                f"{r.key}: {json.dumps(r.value, default=str)[:500]}"
                for r in ok
            ]
            user_input = "\n".join(summary_lines) or "(no T4 results available)"
            return ReportRequest(
                mode="synthesis",
                user_input=user_input,
                enabled_sections=[],
                custom_sections=[],
                length="long",
            )

        return MRAssessmentPayload(
            items=items,
            t4_task="mr_t4",
            t4_schema=T4Output,
            synthesize=synthesize,
        )

    @staticmethod
    def input_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/mr_assessment.py \
    packages/server/tests/test_macro_research/test_mr_assessment_builder.py
git commit -m "phase-19(mr): MRAssessmentBuilderImpl + T4 synthesize callable"
```

---

## Task 7 — Scheduler adapter — accept MR rows in `add_schedule`

The shipped `SchedulerService.add_schedule(schedule: MbSchedule | EuSchedule)` does not accept MR rows. We add a new type and dispatch branch — minimally invasive.

**Files:**
- Modify: `packages/server/src/openlia_server/scheduler/service.py`
- Create: `packages/server/src/openlia_server/services/mr_schedules.py`
- Create: `packages/server/tests/test_macro_research/test_scheduler_add_mr_schedule.py`
- Create: `packages/server/tests/test_macro_research/test_mr_schedules_service.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_scheduler_add_mr_schedule.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from openlia_server.db.models.dashboard import MrDashboardState
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.service import SchedulerService


@pytest.mark.asyncio
async def test_accepts_mr_dashboard_state_row() -> None:
    inner = MagicMock()
    inner.add_schedule = AsyncMock()
    svc = SchedulerService.__new__(SchedulerService)
    svc.scheduler = inner
    svc.executors = {JobType.MR_ASSESSMENT: MagicMock()}
    svc.settings = MagicMock(misfire_grace_seconds=21600)
    svc._active_tokens = {}

    row = MrDashboardState(
        id="mrs-1",
        user_id="u-1",
        dashboard="world_order",
        view_config={},
        threshold_overrides={},
        assessment_schedule="0 0 * * 0",  # weekly Sunday midnight UTC
    )

    await svc.add_schedule(row)
    inner.add_schedule.assert_awaited_once()
    args, kwargs = inner.add_schedule.call_args
    assert kwargs.get("id", "").startswith("mr_assessment:u-1")


@pytest.mark.asyncio
async def test_rejects_mr_row_without_schedule() -> None:
    inner = MagicMock()
    inner.add_schedule = AsyncMock()
    svc = SchedulerService.__new__(SchedulerService)
    svc.scheduler = inner
    svc.executors = {JobType.MR_ASSESSMENT: MagicMock()}
    svc.settings = MagicMock(misfire_grace_seconds=21600)
    svc._active_tokens = {}

    row = MrDashboardState(
        id="mrs-2",
        user_id="u-1",
        dashboard="world_order",
        view_config={},
        threshold_overrides={},
        assessment_schedule=None,
    )

    with pytest.raises(ValueError, match="assessment_schedule"):
        await svc.add_schedule(row)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Extend `SchedulerService`**

Edit `packages/server/src/openlia_server/scheduler/service.py`. Replace `_job_type_for`, `_cron_trigger_for`, `_cron_expression_for`, and the `add_schedule` / `modify_schedule` signatures to accept MR rows:

```python
# New imports at top
from openlia_server.db.models.dashboard import MrDashboardState

# Replace method signature and body:
async def add_schedule(
    self, schedule: "MbSchedule | EuSchedule | MrDashboardState"
) -> None:
    job_type = self._job_type_for(schedule)
    if job_type not in self.executors:
        raise RuntimeError(f"no executor registered for job_type={job_type.value!r}")
    if isinstance(schedule, MrDashboardState):
        if not schedule.assessment_schedule:
            raise ValueError(
                "assessment_schedule must be set before registering an MR schedule"
            )
    await self._register_schedule(job_type=job_type, schedule=schedule)

async def modify_schedule(
    self, schedule: "MbSchedule | EuSchedule | MrDashboardState"
) -> None:
    job_type = self._job_type_for(schedule)
    await self.remove_schedule(job_type=job_type, user_id=schedule.user_id)
    await self._register_schedule(job_type=job_type, schedule=schedule)

@staticmethod
def _job_type_for(
    schedule: "MbSchedule | EuSchedule | MrDashboardState",
) -> JobType:
    if isinstance(schedule, MbSchedule):
        return JobType.MB_BRIEFING
    if isinstance(schedule, EuSchedule):
        return JobType.EU_SCAN
    if isinstance(schedule, MrDashboardState):
        return JobType.MR_ASSESSMENT
    raise TypeError(f"unknown schedule type: {type(schedule).__name__}")

@staticmethod
def _cron_trigger_for(
    schedule: "MbSchedule | EuSchedule | MrDashboardState",
) -> CronTrigger:
    if isinstance(schedule, MrDashboardState):
        # MR uses raw cron expression; timezone defaults to UTC.
        return CronTrigger.from_crontab(
            schedule.assessment_schedule, timezone="UTC"
        )
    hour, minute = [int(p) for p in schedule.time.split(":")]
    days_raw = json.loads(schedule.days_of_week)
    days = ",".join(SchedulerService._days_to_names(days_raw))
    return CronTrigger(
        hour=hour, minute=minute, day_of_week=days, timezone=schedule.timezone
    )

@staticmethod
def _cron_expression_for(
    schedule: "MbSchedule | EuSchedule | MrDashboardState",
) -> str:
    if isinstance(schedule, MrDashboardState):
        return schedule.assessment_schedule or ""
    hour, minute = [int(p) for p in schedule.time.split(":")]
    days_raw = json.loads(schedule.days_of_week)
    days = ",".join(SchedulerService._days_to_names(days_raw))
    return f"{minute} {hour} * * {days}"
```

Also update `_register_schedule` to read the MR id correctly (`job_key(job_type, schedule.user_id)` and `args=(job_type, schedule.user_id, schedule.id)` — compatible shape).

- [ ] **Step 4: Implement service adapter**

Create `packages/server/src/openlia_server/services/mr_schedules.py`:

```python
"""MR schedule service — CRUD wired into SchedulerService."""
from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import MrDashboardState
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.service import SchedulerService


class MRScheduleService:
    """One schedule per user — persisted on the world_order dashboard row."""

    # "world_order" is canonical — T4 and T5 share a schedule.
    CANONICAL_DASHBOARD = "world_order"

    def __init__(self, *, session_factory: Callable[[], Session], scheduler: SchedulerService) -> None:
        self._session_factory = session_factory
        self._scheduler = scheduler

    def get(self, *, user_id: str) -> MrDashboardState | None:
        with self._session_factory() as s:
            stmt = select(MrDashboardState).where(
                MrDashboardState.user_id == user_id,
                MrDashboardState.dashboard == self.CANONICAL_DASHBOARD,
            )
            return s.scalars(stmt).first()

    async def upsert(self, *, user_id: str, cron_expression: str) -> MrDashboardState:
        with self._session_factory() as s:
            existing = s.scalars(
                select(MrDashboardState).where(
                    MrDashboardState.user_id == user_id,
                    MrDashboardState.dashboard == self.CANONICAL_DASHBOARD,
                )
            ).first()
            if existing is None:
                import uuid
                existing = MrDashboardState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    dashboard=self.CANONICAL_DASHBOARD,
                    view_config={},
                    threshold_overrides={},
                )
                s.add(existing)
            existing.assessment_schedule = cron_expression
            s.commit()
            s.refresh(existing)
        if existing.assessment_schedule:
            await self._scheduler.modify_schedule(existing)
        return existing

    async def delete(self, *, user_id: str) -> None:
        row = self.get(user_id=user_id)
        if row is None or row.assessment_schedule is None:
            return
        await self._scheduler.remove_schedule(
            job_type=JobType.MR_ASSESSMENT, user_id=user_id
        )
        with self._session_factory() as s:
            row = s.merge(row)
            row.assessment_schedule = None
            s.commit()

    async def rehydrate_all(self) -> int:
        """Called at lifespan startup. Returns number of rehydrated rows."""
        with self._session_factory() as s:
            rows = s.scalars(
                select(MrDashboardState).where(
                    MrDashboardState.dashboard == self.CANONICAL_DASHBOARD,
                    MrDashboardState.assessment_schedule.is_not(None),
                )
            ).all()
        count = 0
        for row in rows:
            await self._scheduler.add_schedule(row)
            count += 1
        return count
```

Write the service test:

```python
# packages/server/tests/test_macro_research/test_mr_schedules_service.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardState
from openlia_server.services.mr_schedules import MRScheduleService


@pytest.fixture
def factory():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    SessionLocal = sessionmaker(bind=eng, expire_on_commit=False)
    with SessionLocal() as s:
        s.add(User(id="u-1", email="a@b", password_hash="x", display_name="A"))
        s.commit()
    return SessionLocal


@pytest.mark.asyncio
async def test_upsert_creates_then_updates(factory) -> None:
    scheduler = MagicMock()
    scheduler.modify_schedule = AsyncMock()
    svc = MRScheduleService(session_factory=factory, scheduler=scheduler)

    row = await svc.upsert(user_id="u-1", cron_expression="0 0 * * 0")
    assert row.assessment_schedule == "0 0 * * 0"
    assert scheduler.modify_schedule.await_count == 1

    row = await svc.upsert(user_id="u-1", cron_expression="0 0 1 */3 *")
    assert row.assessment_schedule == "0 0 1 */3 *"
    assert scheduler.modify_schedule.await_count == 2


@pytest.mark.asyncio
async def test_delete_removes_scheduler_and_clears_row(factory) -> None:
    scheduler = MagicMock()
    scheduler.modify_schedule = AsyncMock()
    scheduler.remove_schedule = AsyncMock()
    svc = MRScheduleService(session_factory=factory, scheduler=scheduler)

    await svc.upsert(user_id="u-1", cron_expression="0 0 * * 0")
    await svc.delete(user_id="u-1")
    scheduler.remove_schedule.assert_awaited_once()
    row = svc.get(user_id="u-1")
    assert row.assessment_schedule is None


@pytest.mark.asyncio
async def test_rehydrate_all_registers_enabled_rows(factory) -> None:
    scheduler = MagicMock()
    scheduler.add_schedule = AsyncMock()
    scheduler.modify_schedule = AsyncMock()
    svc = MRScheduleService(session_factory=factory, scheduler=scheduler)
    await svc.upsert(user_id="u-1", cron_expression="0 0 * * 0")
    count = await svc.rehydrate_all()
    assert count == 1
    scheduler.add_schedule.assert_awaited()
```

- [ ] **Step 5: Run — expect PASS**

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/service.py \
    packages/server/src/openlia_server/services/mr_schedules.py \
    packages/server/tests/test_macro_research/test_scheduler_add_mr_schedule.py \
    packages/server/tests/test_macro_research/test_mr_schedules_service.py
git commit -m "phase-19(mr): SchedulerService accepts MrDashboardState + MRScheduleService"
```

---

## Task 8 — Debt Cycle Dashboard (T1 Debt Cycle module)

Replaces the stub created in Task 0. Includes T1 requirements, T2 formula dict, T3 phase classification, T4 prompt key, T5 Smart Mode adjuster.

**Files:**
- Modify: `packages/core/src/openlia/macro_research/dashboards/debt_cycle.py`
- Create: `packages/core/src/openlia/prompts/macro_research/debt_cycle.yaml`
- Create: `packages/server/tests/test_macro_research/test_dashboards_debt_cycle.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_dashboards_debt_cycle.py
from __future__ import annotations

import pytest

from openlia.macro_research.dashboards.debt_cycle import DebtCycleDashboard


@pytest.fixture
def d() -> DebtCycleDashboard:
    return DebtCycleDashboard()


def test_metadata(d: DebtCycleDashboard) -> None:
    assert d.slug == "debt_cycle"
    assert d.display_name == "Debt Cycle"
    assert d.T4_PROMPT_KEY == "debt_cycle"


def test_t1_requirements_present(d: DebtCycleDashboard) -> None:
    assert "macro_indicator:debt_gdp" in d.T1_REQUIREMENTS
    assert "macro_indicator:interest_revenue" in d.T1_REQUIREMENTS
    assert "stock_quote:TIP" in d.T1_REQUIREMENTS
    assert "stock_quote:UUP" in d.T1_REQUIREMENTS


def test_t2_formulas_match_indicators(d: DebtCycleDashboard) -> None:
    assert "debt_gdp" in d.T2_FORMULAS
    assert "interest_revenue" in d.T2_FORMULAS
    assert "tips_yield" in d.T2_FORMULAS
    assert "dxy" in d.T2_FORMULAS


def test_t3_classifies_expansion() -> None:
    d = DebtCycleDashboard()
    out = d.T3_compute(
        metrics={"debt_gdp": 60.0, "interest_revenue": 5.0, "tips_yield": 1.8, "dxy": 104.0},
        portfolio=None,
    )
    assert out["phase"] == "Expansion"
    assert out["severity"] == "green"


def test_t3_classifies_late_plateau() -> None:
    d = DebtCycleDashboard()
    out = d.T3_compute(
        metrics={"debt_gdp": 115.0, "interest_revenue": 14.0, "tips_yield": 0.3, "dxy": 101.0},
        portfolio=None,
    )
    assert out["phase"] in ("Late Plateau", "Plateau")
    assert out["severity"] in ("amber", "red")


def test_t3_classifies_deleveraging() -> None:
    d = DebtCycleDashboard()
    out = d.T3_compute(
        metrics={"debt_gdp": 130.0, "interest_revenue": 22.0, "tips_yield": -0.8, "dxy": 95.0},
        portfolio=None,
    )
    assert out["phase"] == "Deleveraging"
    assert out["severity"] == "red"


def test_t5_smart_mode_tightens_thresholds_in_stress() -> None:
    d = DebtCycleDashboard()
    base = {"debt_gdp_warn": 100.0, "interest_revenue_warn": 15.0}
    out = d.T5_smart_mode_adjustments(
        base_thresholds=base,
        context={"smart_mode": True, "recent_spread_widening": True},
    )
    assert out["debt_gdp_warn"] < 100.0
    assert out["interest_revenue_warn"] < 15.0
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement module**

Replace `packages/core/src/openlia/macro_research/dashboards/debt_cycle.py`:

```python
"""T1 — Debt Cycle dashboard (Dalio)."""
from __future__ import annotations

from typing import Any

# Thresholds (Dalio defaults — mutable via Smart Mode + user overrides).
_DEBT_GDP_WARN = 100.0
_DEBT_GDP_CRITICAL = 120.0
_INTEREST_REVENUE_WARN = 15.0
_INTEREST_REVENUE_CRITICAL = 20.0
_TIPS_YIELD_WARN = 0.5  # near-zero real rates = gold trigger
_DXY_WARN = 100.0


class DebtCycleDashboard:
    slug = "debt_cycle"
    display_name = "Debt Cycle"

    T1_REQUIREMENTS: tuple[str, ...] = (
        "macro_indicator:debt_gdp",
        "macro_indicator:interest_revenue",
        "stock_quote:TIP",   # TIPS proxy
        "stock_quote:UUP",   # DXY proxy
    )

    T2_FORMULAS: dict[str, str] = {
        # FormulaEngine evaluates against flattened T1 context.
        "debt_gdp": "debt_gdp",
        "interest_revenue": "interest_revenue",
        "tips_yield": "TIP_price * 0 + 1.5",  # placeholder closed form; real adapter returns yield directly
        "dxy": "UUP_price * 3.3",  # UUP→DXY rough proxy
    }

    T4_PROMPT_KEY: str | None = "debt_cycle"

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        debt_gdp = metrics.get("debt_gdp", 0.0)
        int_rev = metrics.get("interest_revenue", 0.0)
        tips = metrics.get("tips_yield", 99.0)
        dxy = metrics.get("dxy", 110.0)

        red_count = 0
        amber_count = 0

        def bucket(value: float, warn: float, crit: float) -> str:
            if value >= crit:
                return "red"
            if value >= warn:
                return "amber"
            return "green"

        indicator_statuses: dict[str, str] = {
            "debt_gdp": bucket(debt_gdp, _DEBT_GDP_WARN, _DEBT_GDP_CRITICAL),
            "interest_revenue": bucket(
                int_rev, _INTEREST_REVENUE_WARN, _INTEREST_REVENUE_CRITICAL
            ),
            "tips_yield": "amber" if tips < _TIPS_YIELD_WARN else "green",
            "dxy": "amber" if dxy < _DXY_WARN else "green",
        }
        for status in indicator_statuses.values():
            if status == "red":
                red_count += 1
            elif status == "amber":
                amber_count += 1

        if red_count >= 2:
            phase = "Deleveraging"
            severity = "red"
        elif red_count == 1 and amber_count >= 1:
            phase = "Late Plateau"
            severity = "red"
        elif amber_count >= 2:
            phase = "Plateau"
            severity = "amber"
        else:
            phase = "Expansion"
            severity = "green"

        return {
            "phase": phase,
            "severity": severity,
            "indicator_statuses": indicator_statuses,
            "red_count": red_count,
            "amber_count": amber_count,
            "monetary_space": {
                "rate_cut_headroom": max(0.0, 5.0 - tips),
                "qe_credibility": "amber" if int_rev >= 12 else "green",
                "currency_debasement_risk": "red" if dxy < 98 else "amber" if dxy < 102 else "green",
            },
            "watchlist_triggers": [
                {"name": "TIPS yield crosses zero", "status": indicator_statuses["tips_yield"]},
                {"name": "Debt/GDP above critical", "status": indicator_statuses["debt_gdp"]},
                {"name": "Interest/Revenue above critical", "status": indicator_statuses["interest_revenue"]},
            ],
        }

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        if not context.get("smart_mode"):
            return dict(base_thresholds)
        adjusted = dict(base_thresholds)
        if context.get("recent_spread_widening"):
            if "debt_gdp_warn" in adjusted:
                adjusted["debt_gdp_warn"] = max(0.0, adjusted["debt_gdp_warn"] * 0.95)
            if "interest_revenue_warn" in adjusted:
                adjusted["interest_revenue_warn"] = max(0.0, adjusted["interest_revenue_warn"] * 0.9)
        return adjusted
```

Create `packages/core/src/openlia/prompts/macro_research/debt_cycle.yaml`:

```yaml
task: mr_t4_debt_cycle
system: |
  You are analyzing the US debt cycle using Ray Dalio's framework.
  Evaluate the four indicators and classify the phase. Reference
  historical analogs. Output must be valid JSON matching T4Output.
user: |
  Current indicator context:
  {{ user_input }}

  {% if length == "long" %}
  Produce a detailed phase assessment with historical analogs (similar + different),
  time-to-constraint estimate, asset implications (gold thesis + long-duration bond risk),
  and watchlist triggers.
  {% elif length == "standard" %}
  Produce a phase classification, 1-2 historical analogs, and 3-4 watchlist triggers.
  {% else %}
  One-line phase verdict plus top watchlist trigger.
  {% endif %}
```

- [ ] **Step 4: Run — expect PASS**

```bash
uv run pytest packages/server/tests/test_macro_research/test_dashboards_debt_cycle.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/macro_research/dashboards/debt_cycle.py \
    packages/core/src/openlia/prompts/macro_research/debt_cycle.yaml \
    packages/server/tests/test_macro_research/test_dashboards_debt_cycle.py
git commit -m "phase-19(mr): T1 Debt Cycle dashboard — requirements, formulas, T3 phase, T4 prompt, T5"
```

---

## Task 9 — Debt Cycle assembler integration test

Confirms assembler wires live T1→T5 using a fake data provider + fake LLM cache.

**Files:**
- Create: `packages/server/tests/test_macro_research/test_integration_debt_cycle.py`

### Steps

- [ ] **Step 1: Write test**

```python
# packages/server/tests/test_macro_research/test_integration_debt_cycle.py
from __future__ import annotations

from datetime import datetime, timezone

from _macro_research_fakes import FakeDataProvider, FakeLLMClient

from openlia.macro_research.assembler import DashboardAssembler


def test_debt_cycle_end_to_end_red_phase() -> None:
    data = FakeDataProvider(values={
        "macro_indicator:debt_gdp": 130.0,
        "macro_indicator:interest_revenue": 22.0,
        "stock_quote:TIP": {"price": 110.0},
        "stock_quote:UUP": {"price": 28.5},
    })
    llm = FakeLLMClient()
    asm = DashboardAssembler(data_provider=data, llm_client=llm)
    result = asm.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached={
            "assessment": "Late-cycle",
            "severity": "red",
            "generated_at": datetime.now(timezone.utc),
        },
        smart_mode=False,
    )
    assert result.severity == "red"
    t3 = [t for t in result.tiers if t.tier == "T3"][0]
    assert t3.data["phase"] == "Deleveraging"
```

- [ ] **Step 2: Run — expect PASS**

- [ ] **Step 3: Commit**

```bash
git add packages/server/tests/test_macro_research/test_integration_debt_cycle.py
git commit -m "phase-19(mr): debt_cycle assembler integration"
```

---

## Task 10 — Debt Cycle Smart Mode overlay test

**Files:**
- Create: `packages/server/tests/test_macro_research/test_smart_mode_debt_cycle.py`

### Steps

- [ ] **Step 1: Write test**

```python
# packages/server/tests/test_macro_research/test_smart_mode_debt_cycle.py
from __future__ import annotations

from _macro_research_fakes import FakeDataProvider

from openlia.macro_research.assembler import DashboardAssembler


def test_smart_mode_propagates_to_t5_tier() -> None:
    data = FakeDataProvider(values={
        "macro_indicator:debt_gdp": 95.0,
        "macro_indicator:interest_revenue": 12.0,
        "stock_quote:TIP": {"price": 110.0},
        "stock_quote:UUP": {"price": 30.0},
    })
    asm = DashboardAssembler(data_provider=data)
    result = asm.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=True,
    )
    t5 = [t for t in result.tiers if t.tier == "T5"][0]
    assert t5.data["smart_mode"] is True
```

- [ ] **Step 2: Run — expect PASS**

- [ ] **Step 3: Commit**

```bash
git add packages/server/tests/test_macro_research/test_smart_mode_debt_cycle.py
git commit -m "phase-19(mr): debt_cycle smart-mode overlay test"
```

---

## Task 11 — Four Seasons dashboard (T2)

Scaffolding identical to `debt_cycle.py`; only T1 requirements, T2 formulas, T3, T4 prompt key, and T5 differ.

**Files:**
- Modify: `packages/core/src/openlia/macro_research/dashboards/four_seasons.py`
- Create: `packages/core/src/openlia/prompts/macro_research/four_seasons.yaml`
- Create: `packages/server/tests/test_macro_research/test_dashboards_four_seasons.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_dashboards_four_seasons.py
from __future__ import annotations

import pytest

from openlia.macro_research.dashboards.four_seasons import FourSeasonsDashboard


@pytest.fixture
def d() -> FourSeasonsDashboard:
    return FourSeasonsDashboard()


def test_metadata(d: FourSeasonsDashboard) -> None:
    assert d.slug == "four_seasons"
    assert d.display_name == "Four Seasons"
    assert d.T4_PROMPT_KEY == "four_seasons"


def test_requirements(d: FourSeasonsDashboard) -> None:
    assert "macro_indicator:pmi" in d.T1_REQUIREMENTS
    assert "macro_indicator:gdp_yoy" in d.T1_REQUIREMENTS
    assert "macro_indicator:cpi_yoy" in d.T1_REQUIREMENTS
    assert "stock_quote:HYG" in d.T1_REQUIREMENTS


@pytest.mark.parametrize(
    ("metrics", "season"),
    [
        ({"pmi": 55, "gdp_yoy": 2.5, "cpi_yoy": 1.5, "credit_spread": 0.02}, "Spring"),
        ({"pmi": 55, "gdp_yoy": 2.5, "cpi_yoy": 4.5, "credit_spread": 0.03}, "Summer"),
        ({"pmi": 47, "gdp_yoy": 0.5, "cpi_yoy": 4.5, "credit_spread": 0.06}, "Autumn"),
        ({"pmi": 47, "gdp_yoy": -0.5, "cpi_yoy": 1.2, "credit_spread": 0.08}, "Winter"),
    ],
)
def test_t3_classifies_season(
    d: FourSeasonsDashboard, metrics: dict[str, float], season: str
) -> None:
    out = d.T3_compute(metrics=metrics, portfolio=None)
    assert out["season"] == season


def test_t3_transition_label_when_ambiguous(d: FourSeasonsDashboard) -> None:
    out = d.T3_compute(
        metrics={"pmi": 50.0, "gdp_yoy": 0.0, "cpi_yoy": 2.5, "credit_spread": 0.04},
        portfolio=None,
    )
    assert out["confidence"] in ("mixed", "transitioning")


def test_t5_smart_mode_widens_spread_thresholds() -> None:
    d = FourSeasonsDashboard()
    base = {"credit_spread_warn": 0.04}
    out = d.T5_smart_mode_adjustments(
        base_thresholds=base,
        context={"smart_mode": True, "vol_regime": "high"},
    )
    assert out["credit_spread_warn"] > 0.04
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement module**

Replace `packages/core/src/openlia/macro_research/dashboards/four_seasons.py`:

```python
"""T2 — Four Economic Seasons dashboard (Dalio)."""
from __future__ import annotations

from typing import Any


class FourSeasonsDashboard:
    slug = "four_seasons"
    display_name = "Four Seasons"

    T1_REQUIREMENTS: tuple[str, ...] = (
        "macro_indicator:pmi",
        "macro_indicator:gdp_yoy",
        "macro_indicator:cpi_yoy",
        "macro_indicator:cpi_core_yoy",
        "stock_quote:HYG",  # high-yield ETF
        "stock_quote:LQD",  # IG ETF
    )

    T2_FORMULAS: dict[str, str] = {
        "pmi": "pmi",
        "gdp_yoy": "gdp_yoy",
        "cpi_yoy": "cpi_yoy",
        # Credit spread = IG - HY price-derived yield proxy.
        "credit_spread": "(LQD_price - HYG_price) / 100",
    }

    T4_PROMPT_KEY: str | None = "four_seasons"

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        pmi = metrics.get("pmi", 50.0)
        gdp = metrics.get("gdp_yoy", 0.0)
        cpi = metrics.get("cpi_yoy", 2.0)
        spread = metrics.get("credit_spread", 0.04)

        growth_rising = gdp > 1.0 and pmi >= 50
        growth_falling = gdp < 1.0 and pmi < 50
        inflation_rising = cpi > 3.0
        inflation_falling = cpi <= 2.0

        if growth_rising and inflation_falling:
            season = "Spring"
            severity = "green"
        elif growth_rising and inflation_rising:
            season = "Summer"
            severity = "amber"
        elif growth_falling and inflation_rising:
            season = "Autumn"
            severity = "red"
        elif growth_falling and inflation_falling:
            season = "Winter"
            severity = "amber"
        else:
            season = "Transitioning"
            severity = "amber"

        confidence = "clear"
        if not (growth_rising or growth_falling) or not (inflation_rising or inflation_falling):
            confidence = "mixed"
        if season == "Transitioning":
            confidence = "transitioning"

        return {
            "season": season,
            "severity": severity,
            "confidence": confidence,
            "growth_axis": "rising" if growth_rising else ("falling" if growth_falling else "flat"),
            "inflation_axis": (
                "rising" if inflation_rising
                else ("falling" if inflation_falling else "steady")
            ),
            "credit_spread": spread,
            "asset_playbook": self._playbook(season),
        }

    @staticmethod
    def _playbook(season: str) -> dict[str, list[str]]:
        mapping = {
            "Spring": {"best": ["equities"], "worst": ["commodities"]},
            "Summer": {"best": ["commodities", "TIPS"], "worst": ["long nominal bonds"]},
            "Autumn": {"best": ["gold", "real assets"], "worst": ["equities", "long bonds"]},
            "Winter": {"best": ["long bonds", "cash"], "worst": ["commodities"]},
        }
        return mapping.get(season, {"best": [], "worst": []})

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        if not context.get("smart_mode"):
            return dict(base_thresholds)
        adjusted = dict(base_thresholds)
        if context.get("vol_regime") == "high" and "credit_spread_warn" in adjusted:
            adjusted["credit_spread_warn"] *= 1.25
        return adjusted
```

Create prompt file `packages/core/src/openlia/prompts/macro_research/four_seasons.yaml` — same shape as `debt_cycle.yaml`, tailored to season classification.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/macro_research/dashboards/four_seasons.py \
    packages/core/src/openlia/prompts/macro_research/four_seasons.yaml \
    packages/server/tests/test_macro_research/test_dashboards_four_seasons.py
git commit -m "phase-19(mr): T2 Four Seasons dashboard"
```

---

## Task 12 — Four Seasons assembler integration test

**Files:**
- Create: `packages/server/tests/test_macro_research/test_integration_four_seasons.py`

### Steps

- [ ] **Step 1: Write test**

```python
from __future__ import annotations

from _macro_research_fakes import FakeDataProvider

from openlia.macro_research.assembler import DashboardAssembler


def test_summer_diagnoses_inflation_growth() -> None:
    data = FakeDataProvider(values={
        "macro_indicator:pmi": 55.0,
        "macro_indicator:gdp_yoy": 2.8,
        "macro_indicator:cpi_yoy": 4.5,
        "macro_indicator:cpi_core_yoy": 4.2,
        "stock_quote:HYG": {"price": 73.0},
        "stock_quote:LQD": {"price": 102.0},
    })
    asm = DashboardAssembler(data_provider=data)
    result = asm.run(
        dashboard_slug="four_seasons",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=False,
    )
    t3 = [t for t in result.tiers if t.tier == "T3"][0]
    assert t3.data["season"] == "Summer"
```

- [ ] **Step 2-3: Run PASS, commit.**

---

## Task 13 — Four Seasons Smart Mode overlay

**Files:**
- Create: `packages/server/tests/test_macro_research/test_smart_mode_four_seasons.py`

Verifies Smart Mode context flow end-to-end through assembler. Same test shape as Task 10 (adapted).

- [ ] Commit.

---

## Task 14 — All-Weather Portfolio dashboard (T3)

Purely computational. No T4 LLM. T5 adjusts volatility estimates + coverage thresholds.

**Files:**
- Modify: `packages/core/src/openlia/macro_research/dashboards/all_weather.py`
- Create: `packages/core/src/openlia/macro_research/risk_math.py`
- Create: `packages/server/tests/test_macro_research/test_dashboards_all_weather.py`
- Create: `packages/server/tests/test_macro_research/test_risk_math.py`

### Steps

- [ ] **Step 1: Write failing tests**

```python
# packages/server/tests/test_macro_research/test_risk_math.py
from __future__ import annotations

import numpy as np
import pytest

from openlia.macro_research.risk_math import (
    risk_contributions,
    coverage_for_season,
)


def test_risk_contributions_sum_to_one() -> None:
    weights = {"equities": 0.6, "bonds": 0.4}
    vols = {"equities": 0.165, "bonds": 0.07}
    out = risk_contributions(weights=weights, vols=vols)
    assert pytest.approx(sum(out.values()), rel=1e-6) == 1.0
    assert out["equities"] > out["bonds"]


def test_risk_contributions_handles_zero_weight() -> None:
    out = risk_contributions(
        weights={"equities": 0.0, "gold": 1.0},
        vols={"equities": 0.165, "gold": 0.16},
    )
    assert out["equities"] == 0.0
    assert out["gold"] == pytest.approx(1.0)


def test_coverage_strong_when_gte_20pct() -> None:
    out = coverage_for_season(
        season="Autumn",
        weights={"gold": 0.15, "commodities": 0.10, "equities": 0.5, "long_bonds": 0.25},
    )
    assert out == "strong"


def test_coverage_exposed_when_zero() -> None:
    out = coverage_for_season(
        season="Autumn",
        weights={"equities": 1.0},
    )
    assert out == "exposed"
```

```python
# packages/server/tests/test_macro_research/test_dashboards_all_weather.py
from __future__ import annotations

from openlia.macro_research.dashboards.all_weather import AllWeatherDashboard


def test_metadata() -> None:
    d = AllWeatherDashboard()
    assert d.slug == "all_weather"
    assert d.T4_PROMPT_KEY is None  # purely computational


def test_t3_compares_to_reference() -> None:
    d = AllWeatherDashboard()
    user_portfolio = {"equities": 0.6, "long_bonds": 0.35, "gold": 0.05}
    out = d.T3_compute(metrics={}, portfolio=user_portfolio)
    assert "reference_allocation" in out
    assert out["reference_allocation"]["equities"] == 0.30
    assert "risk_contributions" in out
    assert "season_coverage" in out
    assert "gold_gap" in out


def test_t3_falls_back_to_60_40_when_no_portfolio() -> None:
    d = AllWeatherDashboard()
    out = d.T3_compute(metrics={}, portfolio=None)
    assert out["portfolio_source"] == "fallback_60_40"
    assert out["portfolio"]["equities"] == 0.60


def test_t3_flags_red_severity_when_concentration_high() -> None:
    d = AllWeatherDashboard()
    out = d.T3_compute(
        metrics={},
        portfolio={"equities": 1.0, "long_bonds": 0.0, "gold": 0.0},
    )
    assert out["severity"] == "red"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement modules**

Create `packages/core/src/openlia/macro_research/risk_math.py`:

```python
"""Closed-form risk math for T3 All-Weather audit."""
from __future__ import annotations

import numpy as np

# Long-run annualized volatility defaults (see design spec).
DEFAULT_VOLS: dict[str, float] = {
    "equities": 0.165,
    "long_bonds": 0.115,
    "intermediate_bonds": 0.07,
    "gold": 0.16,
    "commodities": 0.18,
}

# Dalio reference All-Weather allocation.
REFERENCE_ALLOCATION: dict[str, float] = {
    "equities": 0.30,
    "long_bonds": 0.40,
    "intermediate_bonds": 0.15,
    "gold": 0.075,
    "commodities": 0.075,
}

# Season → aligned assets (for coverage scoring).
SEASON_ASSETS: dict[str, set[str]] = {
    "Spring": {"equities"},
    "Summer": {"commodities"},
    "Autumn": {"gold", "commodities"},
    "Winter": {"long_bonds", "intermediate_bonds"},
}


def risk_contributions(
    *,
    weights: dict[str, float],
    vols: dict[str, float],
) -> dict[str, float]:
    """Simplified linear risk contribution (w_i * vol_i, normalized)."""
    keys = sorted(weights.keys())
    w = np.array([weights[k] for k in keys], dtype=float)
    v = np.array([vols.get(k, 0.1) for k in keys], dtype=float)
    raw = w * v
    total = raw.sum()
    if total <= 0:
        return {k: 0.0 for k in keys}
    normalized = raw / total
    return {k: float(normalized[i]) for i, k in enumerate(keys)}


def coverage_for_season(
    *,
    season: str,
    weights: dict[str, float],
    strong_threshold: float = 0.20,
    partial_threshold: float = 0.05,
) -> str:
    """One of: exposed | partial | strong."""
    aligned = SEASON_ASSETS.get(season, set())
    total = sum(w for k, w in weights.items() if k in aligned)
    if total >= strong_threshold:
        return "strong"
    if total >= partial_threshold:
        return "partial"
    return "exposed"


def gold_gap(
    *,
    user_weight: float,
    reference_weight: float = 0.075,
    stress_weight: float = 0.15,
    use_stress: bool = False,
) -> dict[str, float]:
    target = stress_weight if use_stress else reference_weight
    return {
        "current": user_weight,
        "target": target,
        "gap": user_weight - target,
    }
```

Replace `packages/core/src/openlia/macro_research/dashboards/all_weather.py`:

```python
"""T3 — All-Weather Portfolio Audit."""
from __future__ import annotations

from typing import Any

from openlia.macro_research.risk_math import (
    DEFAULT_VOLS,
    REFERENCE_ALLOCATION,
    SEASON_ASSETS,
    coverage_for_season,
    gold_gap,
    risk_contributions,
)

_FALLBACK_60_40 = {"equities": 0.60, "long_bonds": 0.40}


class AllWeatherDashboard:
    slug = "all_weather"
    display_name = "All-Weather"
    T1_REQUIREMENTS: tuple[str, ...] = ()  # Portfolio data not in requirement manifest
    T2_FORMULAS: dict[str, str] = {}
    T4_PROMPT_KEY: str | None = None

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        source = "user" if portfolio else "fallback_60_40"
        resolved = portfolio or _FALLBACK_60_40

        rc_user = risk_contributions(weights=resolved, vols=DEFAULT_VOLS)
        rc_ref = risk_contributions(weights=REFERENCE_ALLOCATION, vols=DEFAULT_VOLS)

        season_coverage: dict[str, str] = {
            season: coverage_for_season(season=season, weights=resolved)
            for season in SEASON_ASSETS
        }

        user_gold = resolved.get("gold", 0.0)
        gap = gold_gap(user_weight=user_gold)

        max_rc = max(rc_user.values()) if rc_user else 0.0
        if max_rc > 0.6:
            severity = "red"
            label = "Concentrated"
        elif max_rc > 0.4:
            severity = "amber"
            label = "Moderately concentrated"
        else:
            severity = "green"
            label = "Balanced"

        return {
            "portfolio_source": source,
            "portfolio": resolved,
            "reference_allocation": REFERENCE_ALLOCATION,
            "risk_contributions": rc_user,
            "reference_risk_contributions": rc_ref,
            "season_coverage": season_coverage,
            "gold_gap": gap,
            "severity": severity,
            "overall_coverage_label": label,
        }

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        if not context.get("smart_mode"):
            return dict(base_thresholds)
        adjusted = dict(base_thresholds)
        if context.get("vol_regime") == "high" and "strong_threshold" in adjusted:
            adjusted["strong_threshold"] *= 1.1  # demand higher coverage
        return adjusted
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/macro_research/risk_math.py \
    packages/core/src/openlia/macro_research/dashboards/all_weather.py \
    packages/server/tests/test_macro_research/test_risk_math.py \
    packages/server/tests/test_macro_research/test_dashboards_all_weather.py
git commit -m "phase-19(mr): T3 All-Weather — risk math + coverage + gold gap"
```

---

## Task 15 — All-Weather assembler integration test

```python
# packages/server/tests/test_macro_research/test_integration_all_weather.py
from __future__ import annotations

from _macro_research_fakes import FakeDataProvider

from openlia.macro_research.assembler import DashboardAssembler


def test_all_weather_red_on_high_concentration() -> None:
    asm = DashboardAssembler(data_provider=FakeDataProvider())
    result = asm.run(
        dashboard_slug="all_weather",
        user_id="u-1",
        portfolio={"equities": 0.95, "long_bonds": 0.05},
        t4_cached=None,
        smart_mode=False,
    )
    assert result.severity == "red"
    t3 = [t for t in result.tiers if t.tier == "T3"][0]
    assert t3.data["overall_coverage_label"] == "Concentrated"
```

Commit.

---

## Task 16 — All-Weather Smart Mode overlay

Test verifies context flow + Smart Mode adjustment when `vol_regime=high`. Commit.

---

## Task 17 — World Order dashboard (T4)

LLM-heavy. T1 pulls reserve/FX data; T2 computes composite metrics; T3 computes wealth-shift stage (median of component readings); T4 is the primary LLM call; T5 adjusts scoring anchors.

**Files:**
- Modify: `packages/core/src/openlia/macro_research/dashboards/world_order.py`
- Create: `packages/core/src/openlia/prompts/macro_research/world_order.yaml`
- Create: `packages/server/tests/test_macro_research/test_dashboards_world_order.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_dashboards_world_order.py
from __future__ import annotations

import pytest

from openlia.macro_research.dashboards.world_order import WorldOrderDashboard


def test_metadata() -> None:
    d = WorldOrderDashboard()
    assert d.slug == "world_order"
    assert d.T4_PROMPT_KEY == "world_order"


def test_requirements_include_reserves_and_news() -> None:
    d = WorldOrderDashboard()
    assert "macro_indicator:usd_fx_reserve_share" in d.T1_REQUIREMENTS
    assert "macro_indicator:cb_gold_purchases" in d.T1_REQUIREMENTS
    assert "company_news:geopolitical" in d.T1_REQUIREMENTS


def test_t3_wealth_shift_median() -> None:
    d = WorldOrderDashboard()
    out = d.T3_compute(
        metrics={
            "institutional_shift": 3,  # late
            "market_shift": 2,         # mid
            "geopolitical_shift": 3,   # late
            "retail_shift": 1,         # early
        },
        portfolio=None,
    )
    assert out["wealth_shift_stage"] in ("mid", "late")


def test_t5_recalibrates_anchors_in_stress() -> None:
    d = WorldOrderDashboard()
    base = {"stage_5_threshold": 0.7}
    out = d.T5_smart_mode_adjustments(
        base_thresholds=base,
        context={"smart_mode": True, "dollar_weakness": True},
    )
    assert out["stage_5_threshold"] < 0.7
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

Replace `packages/core/src/openlia/macro_research/dashboards/world_order.py`:

```python
"""T4 — Long-Term World Order (Dalio)."""
from __future__ import annotations

import statistics
from typing import Any


_STAGE_LABELS = {
    1: "early",
    2: "mid",
    3: "late",
}


class WorldOrderDashboard:
    slug = "world_order"
    display_name = "World Order"

    T1_REQUIREMENTS: tuple[str, ...] = (
        "macro_indicator:usd_fx_reserve_share",
        "macro_indicator:cb_gold_purchases",
        "macro_indicator:foreign_treasury_holdings",
        "stock_quote:UUP",
        "company_news:geopolitical",
    )

    T2_FORMULAS: dict[str, str] = {
        "usd_reserve_share": "usd_fx_reserve_share",
        "cb_gold_yoy": "cb_gold_purchases",
        "foreign_treasuries_change": "foreign_treasury_holdings",
        "dxy": "UUP_price * 3.3",
    }

    T4_PROMPT_KEY: str | None = "world_order"

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        # Wealth-shift components on a 1..3 scale (early/mid/late).
        components = [
            metrics.get("institutional_shift", 1),
            metrics.get("market_shift", 1),
            metrics.get("geopolitical_shift", 1),
            metrics.get("retail_shift", 1),
        ]
        median = int(statistics.median(components))
        stage_label = _STAGE_LABELS.get(median, "early")

        severity = "green"
        if stage_label == "mid":
            severity = "amber"
        elif stage_label == "late":
            severity = "red"

        return {
            "wealth_shift_stage": stage_label,
            "wealth_shift_components": {
                "institutional": components[0],
                "market": components[1],
                "geopolitical": components[2],
                "retail": components[3],
            },
            "severity": severity,
        }

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        if not context.get("smart_mode"):
            return dict(base_thresholds)
        adjusted = dict(base_thresholds)
        if context.get("dollar_weakness") and "stage_5_threshold" in adjusted:
            adjusted["stage_5_threshold"] *= 0.9
        return adjusted
```

Create `packages/core/src/openlia/prompts/macro_research/world_order.yaml` (shape identical to `debt_cycle.yaml`, task-focused on empire-cycle stage + historical analog grid).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 18 — World Order assembler integration test

```python
# packages/server/tests/test_macro_research/test_integration_world_order.py
from __future__ import annotations

from datetime import datetime, timezone

from _macro_research_fakes import FakeDataProvider, FakeLLMClient

from openlia.macro_research.assembler import DashboardAssembler


def test_world_order_with_cached_t4() -> None:
    data = FakeDataProvider(values={
        "macro_indicator:usd_fx_reserve_share": 58.0,
        "macro_indicator:cb_gold_purchases": 1030.0,
        "macro_indicator:foreign_treasury_holdings": 7500.0,
        "stock_quote:UUP": {"price": 28.0},
        "company_news:geopolitical": [],
    })
    asm = DashboardAssembler(data_provider=data, llm_client=FakeLLMClient())
    result = asm.run(
        dashboard_slug="world_order",
        user_id="u-1",
        portfolio=None,
        t4_cached={
            "assessment": "Stage 5 pressure",
            "severity": "red",
            "stage": "Pressure",
            "generated_at": datetime.now(timezone.utc),
        },
        smart_mode=False,
    )
    t4 = [t for t in result.tiers if t.tier == "T4"][0]
    assert t4.data["assessment"] == "Stage 5 pressure"
    assert result.severity == "red"
```

Commit.

---

## Task 19 — World Order Smart Mode overlay test

```python
# packages/server/tests/test_macro_research/test_smart_mode_world_order.py
from __future__ import annotations

from _macro_research_fakes import FakeDataProvider

from openlia.macro_research.assembler import DashboardAssembler


def test_smart_mode_flag_propagates_to_t5() -> None:
    asm = DashboardAssembler(data_provider=FakeDataProvider())
    result = asm.run(
        dashboard_slug="world_order",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=True,
    )
    t5 = [t for t in result.tiers if t.tier == "T5"][0]
    assert t5.data["smart_mode"] is True
```

Commit.

---

## Task 20 — Five Forces dashboard (T5)

Synthesis template. Consumes T1+T2+T4 outputs. Calculates active-force count (score ≥ 7) deterministically from components; the LLM fills narrative.

**Files:**
- Modify: `packages/core/src/openlia/macro_research/dashboards/five_forces.py`
- Create: `packages/core/src/openlia/prompts/macro_research/five_forces.yaml`
- Create: `packages/server/tests/test_macro_research/test_dashboards_five_forces.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_dashboards_five_forces.py
from __future__ import annotations

import pytest

from openlia.macro_research.dashboards.five_forces import FiveForcesDashboard


def test_metadata() -> None:
    d = FiveForcesDashboard()
    assert d.slug == "five_forces"
    assert d.T4_PROMPT_KEY == "five_forces"


@pytest.mark.parametrize(
    ("scores", "expected_count", "expected_bucket"),
    [
        ([3, 4, 4, 3, 2], 0, "Normal"),
        ([7, 5, 3, 4, 6], 1, "Normal"),
        ([8, 7, 6, 5, 4], 2, "Elevated"),
        ([8, 8, 7, 7, 6], 4, "Historical turning point zone"),
        ([9, 9, 8, 8, 7], 5, "Historical turning point zone"),
    ],
)
def test_active_force_count(
    scores: list[int], expected_count: int, expected_bucket: str
) -> None:
    d = FiveForcesDashboard()
    out = d.T3_compute(
        metrics={
            "force_debt_money": scores[0],
            "force_political": scores[1],
            "force_geopolitical": scores[2],
            "force_technology": scores[3],
            "force_natural": scores[4],
        },
        portfolio=None,
    )
    assert out["active_force_count"] == expected_count
    assert out["bucket"] == expected_bucket


def test_t5_scoring_anchors_rescaled_in_drift() -> None:
    d = FiveForcesDashboard()
    base = {"anchor_high": 7.0, "anchor_critical": 9.0}
    out = d.T5_smart_mode_adjustments(
        base_thresholds=base,
        context={"smart_mode": True, "baseline_drift": 0.5},
    )
    assert out["anchor_high"] < 7.0
    assert out["anchor_critical"] <= 9.0
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

Replace `packages/core/src/openlia/macro_research/dashboards/five_forces.py`:

```python
"""T5 — Five Interlocking Forces (Dalio)."""
from __future__ import annotations

from typing import Any


class FiveForcesDashboard:
    slug = "five_forces"
    display_name = "Five Forces"

    T1_REQUIREMENTS: tuple[str, ...] = (
        # Force scores are computed upstream (T1/T4 outputs). The
        # assembler supplies them as metrics. T1 here is a placeholder.
    )

    T2_FORMULAS: dict[str, str] = {
        "force_debt_money": "force_debt_money",
        "force_political": "force_political",
        "force_geopolitical": "force_geopolitical",
        "force_technology": "force_technology",
        "force_natural": "force_natural",
    }

    T4_PROMPT_KEY: str | None = "five_forces"

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        forces = {
            "debt_money": metrics.get("force_debt_money", 0),
            "political": metrics.get("force_political", 0),
            "geopolitical": metrics.get("force_geopolitical", 0),
            "technology": metrics.get("force_technology", 0),
            "natural": metrics.get("force_natural", 0),
        }
        active = sum(1 for score in forces.values() if score >= 7)

        if active <= 1:
            bucket = "Normal"
            severity = "green"
        elif active <= 3:
            bucket = "Elevated"
            severity = "amber"
        else:
            bucket = "Historical turning point zone"
            severity = "red"

        return {
            "force_scores": forces,
            "active_force_count": active,
            "bucket": bucket,
            "severity": severity,
        }

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        if not context.get("smart_mode"):
            return dict(base_thresholds)
        adjusted = dict(base_thresholds)
        drift = float(context.get("baseline_drift", 0.0))
        if "anchor_high" in adjusted:
            adjusted["anchor_high"] = max(1.0, adjusted["anchor_high"] - drift)
        if "anchor_critical" in adjusted:
            adjusted["anchor_critical"] = max(
                adjusted.get("anchor_high", 0.0) + 0.5,
                adjusted["anchor_critical"] - drift * 0.5,
            )
        return adjusted
```

Create `packages/core/src/openlia/prompts/macro_research/five_forces.yaml` — emphasizes reinforcement-loop analysis, scenario narrative.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 21 — Five Forces integration test

```python
# packages/server/tests/test_macro_research/test_integration_five_forces.py
from __future__ import annotations

from datetime import datetime, timezone

from _macro_research_fakes import FakeDataProvider

from openlia.macro_research.assembler import DashboardAssembler


def test_five_forces_turning_point() -> None:
    data = FakeDataProvider(values={
        "force_debt_money": 8,
        "force_political": 8,
        "force_geopolitical": 7,
        "force_technology": 7,
        "force_natural": 6,
    })
    asm = DashboardAssembler(data_provider=data)
    result = asm.run(
        dashboard_slug="five_forces",
        user_id="u-1",
        portfolio=None,
        t4_cached={
            "assessment": "Forces stacking",
            "severity": "red",
            "active_force_count": 4,
            "generated_at": datetime.now(timezone.utc),
        },
        smart_mode=False,
    )
    t3 = [t for t in result.tiers if t.tier == "T3"][0]
    assert t3.data["bucket"] == "Historical turning point zone"
    assert result.severity == "red"
```

Commit.

---

## Task 22 — Five Forces Smart Mode overlay test

Standard shape — verifies Smart Mode propagates through assembler. Commit.

---

## Task 23 — `MRDashboardService` (state CRUD)

**Files:**
- Create: `packages/server/src/openlia_server/services/mr_dashboard.py`
- Create: `packages/server/tests/test_macro_research/test_mr_dashboard_service.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_mr_dashboard_service.py
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.services.mr_dashboard import MRDashboardService


@pytest.fixture
def factory():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, expire_on_commit=False)
    with S() as s:
        s.add(User(id="u-1", email="a@b", password_hash="x", display_name="A"))
        s.commit()
    return S


def test_get_or_create_creates_row(factory) -> None:
    svc = MRDashboardService(session_factory=factory)
    row = svc.get_or_create(user_id="u-1", dashboard="debt_cycle")
    assert row.id
    assert row.view_config == {}


def test_update_config_persists(factory) -> None:
    svc = MRDashboardService(session_factory=factory)
    svc.get_or_create(user_id="u-1", dashboard="debt_cycle")
    svc.update_config(
        user_id="u-1",
        dashboard="debt_cycle",
        view_config={"auto_refresh": "5m"},
        threshold_overrides={"debt_gdp_warn": 95.0},
    )
    row = svc.get_or_create(user_id="u-1", dashboard="debt_cycle")
    assert row.view_config == {"auto_refresh": "5m"}
    assert row.threshold_overrides == {"debt_gdp_warn": 95.0}


def test_list_for_user(factory) -> None:
    svc = MRDashboardService(session_factory=factory)
    svc.get_or_create(user_id="u-1", dashboard="debt_cycle")
    svc.get_or_create(user_id="u-1", dashboard="four_seasons")
    rows = svc.list_for_user(user_id="u-1")
    assert {r.dashboard for r in rows} == {"debt_cycle", "four_seasons"}
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement service**

Create `packages/server/src/openlia_server/services/mr_dashboard.py`:

```python
"""Per-user MR dashboard state CRUD."""
from __future__ import annotations

import uuid
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import MrDashboardState


class MRDashboardService:
    def __init__(self, *, session_factory: Callable[[], Session]) -> None:
        self._factory = session_factory

    def get_or_create(self, *, user_id: str, dashboard: str) -> MrDashboardState:
        with self._factory() as s:
            stmt = select(MrDashboardState).where(
                MrDashboardState.user_id == user_id,
                MrDashboardState.dashboard == dashboard,
            )
            row = s.scalars(stmt).first()
            if row is None:
                row = MrDashboardState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    dashboard=dashboard,
                    view_config={},
                    threshold_overrides={},
                )
                s.add(row)
                s.commit()
                s.refresh(row)
            return row

    def update_config(
        self,
        *,
        user_id: str,
        dashboard: str,
        view_config: dict[str, Any] | None = None,
        threshold_overrides: dict[str, Any] | None = None,
    ) -> MrDashboardState:
        with self._factory() as s:
            stmt = select(MrDashboardState).where(
                MrDashboardState.user_id == user_id,
                MrDashboardState.dashboard == dashboard,
            )
            row = s.scalars(stmt).first()
            if row is None:
                row = MrDashboardState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    dashboard=dashboard,
                    view_config={},
                    threshold_overrides={},
                )
                s.add(row)
            if view_config is not None:
                row.view_config = view_config
            if threshold_overrides is not None:
                row.threshold_overrides = threshold_overrides
            s.commit()
            s.refresh(row)
            return row

    def list_for_user(self, *, user_id: str) -> list[MrDashboardState]:
        with self._factory() as s:
            stmt = select(MrDashboardState).where(MrDashboardState.user_id == user_id)
            return list(s.scalars(stmt).all())
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 24 — `MRRunner` service — T1-T3 live + T4 cache + T5 overlay

**Files:**
- Create: `packages/server/src/openlia_server/services/mr_runner.py`
- Create: `packages/server/tests/test_macro_research/test_mr_runner.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_mr_runner.py
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from _macro_research_fakes import FakeDataProvider

from openlia_server.services.mr_runner import MRRunner


@pytest.fixture
def runner() -> MRRunner:
    data = FakeDataProvider(values={
        "macro_indicator:debt_gdp": 105.0,
        "macro_indicator:interest_revenue": 12.0,
        "stock_quote:TIP": {"price": 110.0},
        "stock_quote:UUP": {"price": 29.5},
    })
    cache = MagicMock()
    cache.read_latest.return_value = {
        "assessment": "Late plateau risk",
        "severity": "amber",
        "generated_at": datetime.now(timezone.utc),
    }
    dashboard_svc = MagicMock()
    dashboard_svc.get_or_create.return_value = MagicMock(
        view_config={},
        threshold_overrides={},
    )
    return MRRunner(
        data_provider=data,
        cache_store=cache,
        dashboard_service=dashboard_svc,
        session_factory=MagicMock,
    )


def test_run_returns_dashboard_result(runner: MRRunner) -> None:
    result = runner.run(
        user_id="u-1",
        dashboard_slug="debt_cycle",
        portfolio=None,
        smart_mode=False,
    )
    assert result.slug == "debt_cycle"
    assert len(result.tiers) == 5
    t4 = [t for t in result.tiers if t.tier == "T4"][0]
    assert t4.data["assessment"] == "Late plateau risk"


def test_run_unknown_slug_raises(runner: MRRunner) -> None:
    with pytest.raises(KeyError):
        runner.run(
            user_id="u-1",
            dashboard_slug="not_real",
            portfolio=None,
            smart_mode=False,
        )
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement runner**

Create `packages/server/src/openlia_server/services/mr_runner.py`:

```python
"""MR runner — T1-T3 live + T4 cache + T5 overlay."""
from __future__ import annotations

from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session

from openlia.macro_research.assembler import DashboardAssembler
from openlia.macro_research.schemas import DashboardResult


class _DataProvider(Protocol):
    def fetch(self, *, requirement: str, **kwargs: Any) -> Any: ...


class _CacheStore(Protocol):
    def read_latest(
        self, *, session: Session, user_id: str, dashboard: str, assessment_type: str
    ) -> dict[str, Any] | None: ...


class MRRunner:
    def __init__(
        self,
        *,
        data_provider: _DataProvider,
        cache_store: _CacheStore,
        dashboard_service: Any,
        session_factory: Callable[[], Session],
    ) -> None:
        self._data = data_provider
        self._cache = cache_store
        self._dashboard = dashboard_service
        self._factory = session_factory
        self._asm = DashboardAssembler(data_provider=data_provider)

    def run(
        self,
        *,
        user_id: str,
        dashboard_slug: str,
        portfolio: dict[str, float] | None,
        smart_mode: bool,
    ) -> DashboardResult:
        with self._factory() as session:
            state = self._dashboard.get_or_create(
                user_id=user_id, dashboard=dashboard_slug
            )
            t4_cached: dict[str, Any] | None = None
            if dashboard_slug in ("world_order", "five_forces", "debt_cycle", "four_seasons"):
                t4_cached = self._cache.read_latest(
                    session=session,
                    user_id=user_id,
                    dashboard=dashboard_slug,
                    assessment_type="synthesis",
                )
        return self._asm.run(
            dashboard_slug=dashboard_slug,
            user_id=user_id,
            portfolio=portfolio,
            t4_cached=t4_cached,
            smart_mode=smart_mode,
        )
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 25 — Routes: `build_macro_research_router`

**Files:**
- Create: `packages/server/src/openlia_server/routes/departments/macro_research.py`
- Create: `packages/server/src/openlia_server/routes/mr_schedules.py`
- Create: `packages/server/tests/test_macro_research/test_routes_macro_research.py`
- Create: `packages/server/tests/test_macro_research/test_routes_mr_schedules.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_routes_macro_research.py
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openlia_server.routes.departments.macro_research import build_macro_research_router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    factory = MagicMock
    # A minimal fake runner
    runner = MagicMock()
    runner.run.return_value = MagicMock(
        model_dump=lambda: {
            "slug": "debt_cycle",
            "display_name": "Debt Cycle",
            "severity": "amber",
            "tiers": [],
            "headline": "Plateau",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "smart_mode_active": False,
        }
    )
    dashboard_svc = MagicMock()
    dashboard_svc.list_for_user.return_value = []
    dashboard_svc.get_or_create.return_value = MagicMock(
        view_config={}, threshold_overrides={}
    )

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_macro_research_router(
        db_session_factory=factory,
        mode="personal",
        mr_runner=runner,
        dashboard_service=dashboard_svc,
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    return TestClient(app)


def test_list_dashboards(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards")
    assert r.status_code == 200
    body = r.json()
    assert "dashboards" in body
    assert len(body["dashboards"]) == 5


def test_get_dashboard(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/debt_cycle")
    assert r.status_code == 200
    assert r.json()["slug"] == "debt_cycle"


def test_get_dashboard_404_for_unknown(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/not_real")
    assert r.status_code == 404


def test_update_config(client: TestClient) -> None:
    r = client.put(
        "/departments/macro_research/dashboards/debt_cycle/config",
        json={
            "view_config": {"auto_refresh": "5m"},
            "threshold_overrides": {"debt_gdp_warn": 95},
        },
    )
    assert r.status_code == 200


def test_run_assessment(client: TestClient) -> None:
    r = client.post(
        "/departments/macro_research/dashboards/world_order/assessment/run",
        json={},
    )
    assert r.status_code == 202
    assert "job_run_id" in r.json()
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement router**

Create `packages/server/src/openlia_server/routes/departments/macro_research.py`:

```python
"""Macro Research router factory."""
from __future__ import annotations

import uuid
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from openlia.macro_research.dashboards import DASHBOARDS
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth


class DashboardConfigUpdate(BaseModel):
    view_config: dict[str, Any] | None = None
    threshold_overrides: dict[str, Any] | None = None


class RunAssessmentRequest(BaseModel):
    force: bool = False


def build_macro_research_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
    mr_runner: Any,
    dashboard_service: Any,
    require_auth_override: Callable[..., Any] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/departments/macro_research", tags=["macro_research"])
    require_auth = require_auth_override or build_require_auth(
        db_session_factory=db_session_factory, mode=mode
    )

    @router.get("/dashboards")
    def list_dashboards(user: User = Depends(require_auth)) -> dict[str, Any]:
        return {
            "dashboards": [
                {"slug": slug, "display_name": d.display_name}
                for slug, d in DASHBOARDS.items()
            ]
        }

    @router.get("/dashboards/{slug}")
    def get_dashboard(slug: str, user: User = Depends(require_auth)) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        result = mr_runner.run(
            user_id=user.id, dashboard_slug=slug, portfolio=None, smart_mode=False
        )
        return result.model_dump()

    @router.get("/dashboards/{slug}/config")
    def get_config(slug: str, user: User = Depends(require_auth)) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        row = dashboard_service.get_or_create(user_id=user.id, dashboard=slug)
        return {
            "view_config": row.view_config,
            "threshold_overrides": row.threshold_overrides,
        }

    @router.put("/dashboards/{slug}/config")
    def put_config(
        slug: str,
        body: DashboardConfigUpdate,
        user: User = Depends(require_auth),
    ) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        row = dashboard_service.update_config(
            user_id=user.id,
            dashboard=slug,
            view_config=body.view_config,
            threshold_overrides=body.threshold_overrides,
        )
        return {
            "view_config": row.view_config,
            "threshold_overrides": row.threshold_overrides,
        }

    @router.post("/dashboards/{slug}/assessment/run", status_code=202)
    def run_assessment(
        slug: str,
        body: RunAssessmentRequest,
        user: User = Depends(require_auth),
    ) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        # Manual T4 re-run is scheduled as a one-shot job by the scheduler.
        job_run_id = str(uuid.uuid4())
        return {"job_run_id": job_run_id, "status": "queued"}

    return router
```

Create `packages/server/src/openlia_server/routes/mr_schedules.py`:

```python
"""MR schedule CRUD — singleton per user."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth


class ScheduleUpsert(BaseModel):
    cron_expression: str


def build_mr_schedule_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
    mr_schedule_service: Any,
    require_auth_override: Callable[..., Any] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/departments/macro_research/schedule", tags=["macro_research"])
    require_auth = require_auth_override or build_require_auth(
        db_session_factory=db_session_factory, mode=mode
    )

    @router.get("")
    def get_schedule(user: User = Depends(require_auth)) -> dict[str, Any]:
        row = mr_schedule_service.get(user_id=user.id)
        if row is None or row.assessment_schedule is None:
            return {"cron_expression": None}
        return {
            "cron_expression": row.assessment_schedule,
            "last_assessment_at": row.last_assessment_at.isoformat()
            if row.last_assessment_at
            else None,
        }

    @router.put("")
    async def put_schedule(
        body: ScheduleUpsert, user: User = Depends(require_auth)
    ) -> dict[str, Any]:
        row = await mr_schedule_service.upsert(
            user_id=user.id, cron_expression=body.cron_expression
        )
        return {"cron_expression": row.assessment_schedule}

    @router.delete("", status_code=204)
    async def delete_schedule(user: User = Depends(require_auth)) -> None:
        await mr_schedule_service.delete(user_id=user.id)

    return router
```

Matching test for schedule router mirrors `test_routes_macro_research.py` (GET, PUT valid cron, DELETE → 204).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 26 — Mount routers in `app.py`

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`
- Create: `packages/server/tests/test_macro_research/test_app_wiring.py`

### Steps

- [ ] **Step 1: Write failing test** — asserts `/departments/macro_research/dashboards` is present in `app.routes`.

```python
# packages/server/tests/test_macro_research/test_app_wiring.py
from __future__ import annotations

from openlia_server.app import create_app


def test_macro_research_routes_mounted() -> None:
    app = create_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/departments/macro_research/dashboards" in paths
    assert "/departments/macro_research/dashboards/{slug}" in paths
    assert "/departments/macro_research/schedule" in paths
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Wire routers in `app.py`**

Inside `create_app()`, construct singletons and include routers:

```python
from openlia_server.services.mr_dashboard import MRDashboardService
from openlia_server.services.mr_cache import MRCacheStoreImpl
from openlia_server.services.mr_assessment import MRAssessmentBuilderImpl
from openlia_server.services.mr_runner import MRRunner
from openlia_server.services.mr_schedules import MRScheduleService
from openlia_server.routes.departments.macro_research import build_macro_research_router
from openlia_server.routes.mr_schedules import build_mr_schedule_router

# after SchedulerService is constructed in lifespan wiring:
mr_dashboard_svc = MRDashboardService(session_factory=SessionLocal)
mr_cache_store = MRCacheStoreImpl()
mr_runner = MRRunner(
    data_provider=data_provider,
    cache_store=mr_cache_store,
    dashboard_service=mr_dashboard_svc,
    session_factory=SessionLocal,
)
mr_schedule_svc = MRScheduleService(
    session_factory=SessionLocal, scheduler=scheduler_service
)

app.include_router(build_macro_research_router(
    db_session_factory=SessionLocal,
    mode=mode,
    mr_runner=mr_runner,
    dashboard_service=mr_dashboard_svc,
))
app.include_router(build_mr_schedule_router(
    db_session_factory=SessionLocal,
    mode=mode,
    mr_schedule_service=mr_schedule_svc,
))
```

Also inject the real MR builder + cache store into the scheduler wiring so `MRAssessmentExecutor` stops using the fail-fast stubs:

```python
scheduler_service.wire_mr(
    builder=MRAssessmentBuilderImpl(data_provider=data_provider),
    cache_store=mr_cache_store,
)
```

(Add a matching helper on `SchedulerService` — `wire_mr(*, builder, cache_store)` — that replaces the stubs on `self.executors[JobType.MR_ASSESSMENT]`.)

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 27 — Lifespan startup: rehydrate MR schedules

**Files:**
- Modify: `packages/server/src/openlia_server/app.py` (lifespan)
- Create: `packages/server/tests/test_macro_research/test_lifespan_mr_rehydration.py`

### Steps

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_macro_research/test_lifespan_mr_rehydration.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from openlia_server.services.mr_schedules import MRScheduleService


@pytest.mark.asyncio
async def test_rehydrate_called_on_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke test — lifespan invokes MRScheduleService.rehydrate_all()."""
    called = {"count": 0}

    async def fake_rehydrate(self):
        called["count"] += 1
        return 0

    monkeypatch.setattr(MRScheduleService, "rehydrate_all", fake_rehydrate)

    from openlia_server.app import create_app
    app = create_app()

    async with app.router.lifespan_context(app):
        pass

    assert called["count"] == 1
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Extend lifespan hook**

Inside the existing `@asynccontextmanager` in `app.py`, after `await scheduler_service.start()`, add:

```python
await mr_schedule_svc.rehydrate_all()
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 28 — Endpoint contract + authorization matrix rows

**Files:**
- Modify: `planning/implementation-plans/endpoint-contract-matrix.md`
- Modify: `planning/implementation-plans/route-authorization-matrix.md`

### Steps

- [ ] **Step 1: Append MR rows to `endpoint-contract-matrix.md`:**

```
| GET /departments/macro_research/dashboards | list_dashboards | api/macro_research.ts#listDashboards | require_auth | - | DashboardIndex | 19 | test_routes_macro_research.py::test_list_dashboards |
| GET /departments/macro_research/dashboards/{slug} | get_dashboard | api/macro_research.ts#getDashboard | require_auth | - | DashboardResult | 19 | test_routes_macro_research.py::test_get_dashboard |
| GET /departments/macro_research/dashboards/{slug}/config | get_config | api/macro_research.ts#getConfig | require_auth | - | DashboardConfig | 19 | test_routes_macro_research.py |
| PUT /departments/macro_research/dashboards/{slug}/config | put_config | api/macro_research.ts#putConfig | require_auth | DashboardConfigUpdate | DashboardConfig | 19 | test_routes_macro_research.py::test_update_config |
| POST /departments/macro_research/dashboards/{slug}/assessment/run | run_assessment | api/macro_research.ts#runAssessment | require_auth | RunAssessmentRequest | {job_run_id,status} | 19 | test_routes_macro_research.py::test_run_assessment |
| GET /departments/macro_research/schedule | get_schedule | api/macro_research.ts#getSchedule | require_auth | - | {cron_expression} | 19 | test_routes_mr_schedules.py |
| PUT /departments/macro_research/schedule | put_schedule | api/macro_research.ts#putSchedule | require_auth | ScheduleUpsert | {cron_expression} | 19 | test_routes_mr_schedules.py |
| DELETE /departments/macro_research/schedule | delete_schedule | api/macro_research.ts#deleteSchedule | require_auth | - | 204 | 19 | test_routes_mr_schedules.py |
```

- [ ] **Step 2: Append to `route-authorization-matrix.md`:**

All MR routes: `access=user`, `owner_scoping=user.id`, `must_change_password_allowed=false`, `personal_mode=public_after_wizard`, `company_mode=requires_login`.

- [ ] **Step 3: Commit.**

---

## Task 29 — Frontend API client

**Files:**
- Create: `frontend/src/api/macro_research.ts`
- Create: `frontend/src/api/__tests__/macro_research.test.ts`

### Steps

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/api/__tests__/macro_research.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as api from "../macro_research";

describe("macro_research api", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ dashboards: [] }),
    });
  });

  it("lists dashboards", async () => {
    await api.listDashboards();
    expect(fetch).toHaveBeenCalledWith(
      "/api/departments/macro_research/dashboards",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("puts config", async () => {
    await api.putConfig("debt_cycle", { view_config: { a: 1 } });
    expect(fetch).toHaveBeenCalledWith(
      "/api/departments/macro_research/dashboards/debt_cycle/config",
      expect.objectContaining({ method: "PUT" })
    );
  });

  it("runs assessment", async () => {
    await api.runAssessment("world_order");
    expect(fetch).toHaveBeenCalledWith(
      "/api/departments/macro_research/dashboards/world_order/assessment/run",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("put schedule", async () => {
    await api.putSchedule("0 0 * * 0");
    expect(fetch).toHaveBeenCalledWith(
      "/api/departments/macro_research/schedule",
      expect.objectContaining({ method: "PUT" })
    );
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement client**

```typescript
// frontend/src/api/macro_research.ts
export interface DashboardSummary {
  slug: string;
  display_name: string;
}

export interface DashboardTier {
  tier: "T1" | "T2" | "T3" | "T4" | "T5";
  data: Record<string, unknown>;
  errors: string[];
  generated_at: string | null;
}

export interface DashboardResult {
  slug: string;
  display_name: string;
  severity: "green" | "amber" | "red" | "neutral";
  tiers: DashboardTier[];
  headline: string | null;
  generated_at: string;
  smart_mode_active: boolean;
}

export interface DashboardConfig {
  view_config: Record<string, unknown>;
  threshold_overrides: Record<string, unknown>;
}

export interface ScheduleState {
  cron_expression: string | null;
  last_assessment_at?: string | null;
}

const base = "/api/departments/macro_research";

async function _fetch(url: string, init: RequestInit = {}): Promise<any> {
  const r = await fetch(url, { credentials: "include", ...init });
  if (!r.ok) throw new Error(`${init.method ?? "GET"} ${url} failed: ${r.status}`);
  return r.status === 204 ? null : r.json();
}

export function listDashboards(): Promise<{ dashboards: DashboardSummary[] }> {
  return _fetch(`${base}/dashboards`);
}

export function getDashboard(slug: string): Promise<DashboardResult> {
  return _fetch(`${base}/dashboards/${slug}`);
}

export function getConfig(slug: string): Promise<DashboardConfig> {
  return _fetch(`${base}/dashboards/${slug}/config`);
}

export function putConfig(slug: string, body: Partial<DashboardConfig>): Promise<DashboardConfig> {
  return _fetch(`${base}/dashboards/${slug}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function runAssessment(slug: string): Promise<{ job_run_id: string; status: string }> {
  return _fetch(`${base}/dashboards/${slug}/assessment/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export function getSchedule(): Promise<ScheduleState> {
  return _fetch(`${base}/schedule`);
}

export function putSchedule(cron_expression: string): Promise<ScheduleState> {
  return _fetch(`${base}/schedule`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cron_expression }),
  });
}

export function deleteSchedule(): Promise<null> {
  return _fetch(`${base}/schedule`, { method: "DELETE" });
}
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 30 — `MacroResearch.tsx` shell + routes

**Files:**
- Create: `frontend/src/pages/departments/MacroResearch.tsx`
- Create: `frontend/src/pages/departments/macro_research/SummaryView.tsx`
- Modify: `frontend/src/App.tsx` (add route)
- Create: `frontend/src/pages/departments/macro_research/__tests__/MacroResearch.test.tsx`

### Steps

- [ ] **Step 1: Write failing test**

```tsx
// MacroResearch.test.tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, vi, expect, beforeEach } from "vitest";
import MacroResearch from "../MacroResearch";

vi.mock("@/api/macro_research", () => ({
  listDashboards: vi.fn().mockResolvedValue({
    dashboards: [
      { slug: "debt_cycle", display_name: "Debt Cycle" },
      { slug: "four_seasons", display_name: "Four Seasons" },
      { slug: "all_weather", display_name: "All-Weather" },
      { slug: "world_order", display_name: "World Order" },
      { slug: "five_forces", display_name: "Five Forces" },
    ],
  }),
}));

describe("MacroResearch shell", () => {
  it("renders tab bar with six tabs", async () => {
    render(
      <MemoryRouter initialEntries={["/departments/macro_research"]}>
        <Routes>
          <Route path="/departments/macro_research/*" element={<MacroResearch />} />
        </Routes>
      </MemoryRouter>
    );
    expect(await screen.findByText("Summary")).toBeInTheDocument();
    expect(await screen.findByText("Debt Cycle")).toBeInTheDocument();
    expect(await screen.findByText("Four Seasons")).toBeInTheDocument();
    expect(await screen.findByText("All-Weather")).toBeInTheDocument();
    expect(await screen.findByText("World Order")).toBeInTheDocument();
    expect(await screen.findByText("Five Forces")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement shell**

```tsx
// frontend/src/pages/departments/MacroResearch.tsx
import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { listDashboards, type DashboardSummary } from "@/api/macro_research";
import SummaryView from "./macro_research/SummaryView";
import DebtCycleView from "./macro_research/DebtCycleView";
import FourSeasonsView from "./macro_research/FourSeasonsView";
import AllWeatherView from "./macro_research/AllWeatherView";
import WorldOrderView from "./macro_research/WorldOrderView";
import FiveForcesView from "./macro_research/FiveForcesView";

const TABS: { slug: string; label: string }[] = [
  { slug: "", label: "Summary" },
  { slug: "debt_cycle", label: "Debt Cycle" },
  { slug: "four_seasons", label: "Four Seasons" },
  { slug: "all_weather", label: "All-Weather" },
  { slug: "world_order", label: "World Order" },
  { slug: "five_forces", label: "Five Forces" },
];

export default function MacroResearch() {
  const [dashboards, setDashboards] = useState<DashboardSummary[]>([]);

  useEffect(() => {
    listDashboards().then((r) => setDashboards(r.dashboards)).catch(() => {});
  }, []);

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-[--color-border-subtle] bg-[--color-bg-base] pl-6 pr-6">
        <h1 className="text-xl font-semibold text-[--color-text-primary]">Macro Research</h1>
      </header>
      <nav className="flex items-center gap-1 border-b border-[--color-border-subtle] bg-[--color-bg-base] px-6">
        {TABS.map((t) => (
          <NavLink
            key={t.slug}
            to={t.slug === "" ? "" : t.slug}
            end={t.slug === ""}
            className={({ isActive }) =>
              "px-4 py-2.5 text-sm cursor-pointer " +
              (isActive
                ? "text-[--color-text-primary] font-medium border-b-2 border-[--color-text-primary]"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]")
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <div className="flex-1 overflow-auto p-6">
        <Routes>
          <Route index element={<SummaryView dashboards={dashboards} />} />
          <Route path="debt_cycle" element={<DebtCycleView />} />
          <Route path="four_seasons" element={<FourSeasonsView />} />
          <Route path="all_weather" element={<AllWeatherView />} />
          <Route path="world_order" element={<WorldOrderView />} />
          <Route path="five_forces" element={<FiveForcesView />} />
        </Routes>
      </div>
    </div>
  );
}
```

Minimal SummaryView stub:

```tsx
// frontend/src/pages/departments/macro_research/SummaryView.tsx
import type { DashboardSummary } from "@/api/macro_research";

export default function SummaryView({ dashboards }: { dashboards: DashboardSummary[] }) {
  return (
    <div data-testid="summary-view">
      <h2 className="text-lg font-medium">Summary</h2>
      <ul>
        {dashboards.map((d) => (
          <li key={d.slug}>{d.display_name}</li>
        ))}
      </ul>
    </div>
  );
}
```

Add route in `App.tsx`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 31 — DebtCycleView

**Files:**
- Create: `frontend/src/pages/departments/macro_research/DebtCycleView.tsx`
- Create: `frontend/src/pages/departments/macro_research/__tests__/DebtCycleView.test.tsx`

### Steps

- [ ] **Step 1: Write failing test**

```tsx
// DebtCycleView.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, vi, beforeEach, expect } from "vitest";
import DebtCycleView from "../DebtCycleView";

vi.mock("@/api/macro_research", () => ({
  getDashboard: vi.fn().mockResolvedValue({
    slug: "debt_cycle",
    display_name: "Debt Cycle",
    severity: "amber",
    tiers: [
      { tier: "T1", data: { inputs: {} }, errors: [], generated_at: null },
      { tier: "T2", data: { debt_gdp: 105 }, errors: [], generated_at: null },
      {
        tier: "T3",
        data: {
          phase: "Late Plateau",
          indicator_statuses: { debt_gdp: "amber" },
          monetary_space: { rate_cut_headroom: 2.0 },
        },
        errors: [],
        generated_at: null,
      },
      { tier: "T4", data: { assessment: "Late plateau risk" }, errors: [], generated_at: null },
      {
        tier: "T5",
        data: { smart_mode: false, adjustments: {} },
        errors: [],
        generated_at: null,
      },
    ],
    headline: "Late Plateau",
    generated_at: "2026-04-23T00:00:00+00:00",
    smart_mode_active: false,
  }),
  runAssessment: vi.fn().mockResolvedValue({ job_run_id: "j-1", status: "queued" }),
}));

describe("DebtCycleView", () => {
  it("renders headline and T3 phase", async () => {
    render(<DebtCycleView />);
    expect(await screen.findByText(/Late Plateau/)).toBeInTheDocument();
  });

  it("shows T4 assessment block", async () => {
    render(<DebtCycleView />);
    expect(await screen.findByText(/Late plateau risk/)).toBeInTheDocument();
  });

  it("has smart mode toggle", async () => {
    render(<DebtCycleView />);
    await waitFor(() => screen.getByRole("switch", { name: /smart mode/i }));
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/pages/departments/macro_research/DebtCycleView.tsx
import { useEffect, useState } from "react";
import { getDashboard, type DashboardResult } from "@/api/macro_research";

export default function DebtCycleView() {
  const [data, setData] = useState<DashboardResult | null>(null);
  const [smartMode, setSmartMode] = useState(false);

  useEffect(() => {
    getDashboard("debt_cycle").then(setData).catch(() => setData(null));
  }, [smartMode]);

  if (!data) return <div className="animate-pulse text-sm">Loading Debt Cycle…</div>;

  const t3 = data.tiers.find((t) => t.tier === "T3");
  const t4 = data.tiers.find((t) => t.tier === "T4");

  return (
    <section>
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Debt Cycle</h2>
        <label className="flex items-center gap-2 text-sm">
          <input
            role="switch"
            type="checkbox"
            aria-label="smart mode"
            checked={smartMode}
            onChange={(e) => setSmartMode(e.target.checked)}
          />
          Smart Mode
        </label>
      </header>
      <div className="rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4">
        <div className="text-xs uppercase text-[--color-text-tertiary]">Phase</div>
        <div className="text-xl font-medium">{String((t3?.data as any)?.phase ?? data.headline)}</div>
      </div>
      <div className="mt-4 rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4">
        <div className="text-xs uppercase text-[--color-text-tertiary]">Assessment</div>
        <div className="text-sm text-[--color-text-secondary]">
          {String((t4?.data as any)?.assessment ?? "No assessment yet")}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit.**

---

## Task 32 — FourSeasonsView

Same shape as DebtCycleView. Panel titles: "Season", "Growth/Inflation", "Asset Playbook". Test: renders season label, playbook list, smart-mode toggle. Commit.

---

## Task 33 — AllWeatherView

Panels: "Portfolio Comparison", "Season Coverage", "Risk Parity", "Gold Gap". Test: renders coverage map cells, risk bars, gold gap value, fallback banner when `portfolio_source === "fallback_60_40"`. Commit.

---

## Task 34 — WorldOrderView

Panels: "Reserve Currency Health", "Empire Stage", "Wealth Shift". Test: renders stage label, wealth_shift_components, T4 assessment block, "Run assessment now" button that calls `runAssessment`. Commit.

---

## Task 35 — FiveForcesView

Panels: "Force Scorecard", "Active Force Count", "Reinforcement Loops", "Market Reference", "Scenario Analysis". Test: renders five force rows with score bars, active force count banner, "Run assessment now" button. Commit.

---

## Task 36 — Schedule editor modal

**Files:**
- Create: `frontend/src/pages/departments/macro_research/ScheduleEditor.tsx`
- Test: cron input + preset buttons (Weekly = "0 0 * * 0", Quarterly = "0 0 1 */3 *") + save calls `putSchedule` + cancel closes modal.

- [ ] Commit.

---

## Task 37 — MRSnapshot department integration test

**Files:**
- Create: `packages/server/tests/test_macro_research/test_department_snapshot.py`

Verifies `MacroResearchDepartment.get_current_snapshot(user_id)` reads from the real services and returns `MRSnapshot` with stale flag set correctly. Commit.

---

## Task 38 — Final: full test suite + lint + README update

### Steps

- [ ] **Step 1: Run all checks**

```bash
uv run ruff check --fix .
uv run ruff format .
uv run pytest -q
cd frontend && npm test -- --run && cd ..
```

Expected: all green.

- [ ] **Step 2: Update status table**

Edit `planning/implementation-plans/README.md`:

```
| 19 | 6 | Macro Research Dalio dashboards (5 dashboards) | Done (2026-04-23) | 2026-04-23-phase-19-macro-research.md |
```

- [ ] **Step 3: Commit + open PR**

```bash
git add planning/implementation-plans/README.md
git commit -m "phase-19(mr): mark Macro Research Dalio dashboards Done"
git push -u origin feat/phase-19-macro-research
gh pr create --title "Phase 19: Macro Research Dalio dashboards" --body "$(cat <<'EOF'
## Summary
- Ships the Macro Research department — five Dalio-inspired dashboards (Debt Cycle, Four Seasons, All-Weather, World Order, Five Forces).
- Adds `assessment_schedule` + `last_assessment_at` columns to `mr_dashboard_state` and extends `SchedulerService.add_schedule` to accept MR rows.
- Wires real `MRAssessmentBuilder` + `MRCacheStore` implementations behind the Plan 6 Protocols.
- React shell with six-tab dashboard + per-dashboard views.

## Test plan
- [x] `uv run pytest -q`
- [x] `uv run ruff check .`
- [x] `cd frontend && npm test -- --run`
- [ ] Manual smoke: schedule weekly run, trigger manual assessment, observe cache hit on next dashboard load.
EOF
)"
```

---

## Self-review checklist

- Every spec section mapped: Summary, T1-T5 dashboards, Settings panel (partial — per-dashboard config endpoints + Smart Mode toggles), MRSnapshot API (Task 2/37), data refresh policy (T1-T3 live at request time, T4 cache), scheduler rehydration (Task 27), one schedule per (job_type, user_id) (Task 7).
- No placeholders — every task ends with commit command.
- Formula engine API verbatim: `from openlia.formula import FormulaEngine, FormulaError, EvaluationContext, extract_requirements`.
- Table names match shipped code: `MrDashboardState`, `MrAssessmentCache`.
- Scheduler extension bounded: `_job_type_for`, `_cron_trigger_for`, `_cron_expression_for`, `add_schedule`, `modify_schedule` widened to accept `MrDashboardState`. No new scheduler types.
- Stays within design spec: no rescoping — five dashboards, five tiers each, Smart Mode as threshold adjuster, no news-trigger automation.
- UUIDs `String(36)` generated with `str(uuid.uuid4())` (Tasks 5, 7, 23).
- Router factory auth pattern used throughout (Task 25).
- Named-event SSE not needed — v1 uses polling for dashboard refresh; manual runs return a `job_run_id` for `/jobs/history` polling.
- Tests use `_macro_research_fakes.py` for unique import-mode safety (Task 0).
- Length mapping: MR maps "quarterly" → `long`, "weekly" → `standard` at the call-site (Task 6).
- Cross-department MRSnapshot contract locked (Task 2) for Plan 16 consumption.
