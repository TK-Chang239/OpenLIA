# Phase 1B — Database Baseline: Dashboard, Scheduler & Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the remaining 11 tables from `database-design.md` on top of the Plan 1A baseline so every feature after Phase 2 has persistent state. Ships the 7 dashboard tables (Panic Thermometer, Macro Research, Retail Sentiment, formula engine) and the 4 scheduler/notification tables (MB/EU schedules, `job_runs`, `user_notifications`) plus a second Alembic migration that upgrades a Plan 1A database into the full 33-table schema.

**Architecture:** Two new model files grouped by category — `models/dashboard.py` (7 tables) and `models/scheduler.py` (4 tables, combining schedules + notifications because `user_notifications.job_run_id` is a foreign key into `job_runs`). A single second migration `2026-04-17-1200_dashboard_scheduler_notifications.py` adds every new table; it downgrades cleanly back to the 1A baseline. No changes to engine, sessionmaker, bootstrap seed, or CLI wiring — those are already correct after Plan 1A.

**Tech Stack:** SQLAlchemy 2.0+, Alembic 1.13+, sqlite3 (stdlib), Python 3.12. Tests use pytest with `tmp_path` and `monkeypatch` fixtures carried over from Plan 1A.

**Source spec:** `planning/specs/systems/database-design.md` §7 (dashboard + infrastructure rows) and `planning/specs/systems/background-task-scheduling-design.md` (the rows added there: `mb_schedules`, `eu_schedules`, `job_runs`, `user_notifications`).

**Depends on:** Plan 1A (Base, TimestampMixin, engine, Alembic scaffold, baseline migration, `users` table for FK targets, `models/__init__.py`, and the extended `test_migrations.py` fixtures).

**Unblocks:**
- Plan 6 (Background task scheduling) — `mb_schedules`, `eu_schedules`, `job_runs`, `user_notifications`.
- Plan 17 (Formula engine DSL) — `fe_saved_formulas`.
- Plan 18 (Panic Thermometer page) — `pt_user_configs`, `pt_presets`.
- Plan 19 (Macro Research Dalio dashboards) — `mr_dashboard_state`, `mr_assessment_cache`.
- Plan 20 (Retail Sentiment dashboard) — `rs_user_config`, `rs_snapshots`.

**Out of scope (handled elsewhere):**
- Shipped Panic Thermometer presets data — seeded when Plan 18 ships the preset library. This plan creates the empty table.
- `mr_assessment_cache` content — populated by Plan 19's cache population pipeline.
- Scheduler process (APScheduler boot, rehydration, cron firing) — Plan 6.
- Nightly pruning sweep on these new tables — Plan 6/7 adds the `openlia maintenance` command.
- Formula DSL parser, evaluator — Plan 17. This plan stores the expression as `Text`; validation lives in the service layer.
- Admin/user routes that read/write these tables — later plans per department.

---

## File Structure

Files created or modified in this plan:

```
openlia/
├── packages/
│   └── server/
│       └── src/openlia_server/db/
│           ├── models/
│           │   ├── __init__.py                                       # MODIFIED — register dashboard + scheduler
│           │   ├── dashboard.py                                      # NEW — 7 tables (PT / MR / RS / FE)
│           │   └── scheduler.py                                      # NEW — 4 tables (MB / EU schedules + job_runs + notifications)
│           └── migrations/versions/
│               └── 2026-04-17-1200_dashboard_scheduler_notifications.py  # NEW — second migration
└── packages/server/tests/
    ├── test_db/
    │   ├── test_models_dashboard.py                                  # NEW — 7 dashboard-model tests
    │   ├── test_models_scheduler.py                                  # NEW — 4 scheduler-model tests
    │   └── test_migrations.py                                        # MODIFIED — EXPECTED_TABLES grows by 11
    └── (no new integration tests — bootstrap auto-migrate still covers the combined schema)
```

Design rules carried over from Plan 1A:

- **One model file per database-design.md category.** Dashboard rows (PT/MR/RS/FE) live in `dashboard.py`; scheduler + notifications share `scheduler.py` because of the `user_notifications.job_run_id` FK.
- **Naming convention** from Plan 1A's `base.py` is reused; no changes to `Base.metadata.naming_convention`.
- **Timestamps** use the `TimestampMixin` from Plan 1A for tables with `updated_at`; append-only or one-off timestamps declare columns directly.
- **Alembic** generates one migration for all 11 tables. `render_as_batch=True` (already set by Plan 1A's `env.py`) handles any SQLite CHECK / partial-index nuance.
- **Test fixtures** (`db_path`, `db_url`, `engine`, `db_session`, `create_tables`) come from `tests/test_db/conftest.py` in Plan 1A — reused unchanged.
- **Soft-polymorphic FK:** `job_runs.schedule_id` points at either `mb_schedules.id` or `eu_schedules.id` depending on `job_type`. Stored as `String(36)` with no DB-level FK constraint — discipline enforced at the service layer. The spec acknowledges this (§background-task-scheduling-design.md line for `schedule_id`: "FK to the department-specific schedule table row" is narrative, not a FK constraint).
- **Self-referential FK:** `job_runs.retry_of` references `job_runs.id` with `ondelete="SET NULL"`. SQLite supports this with `render_as_batch=True`.

---

## Task 1: Dashboard models — Panic Thermometer + Macro Research + Retail Sentiment + Formula Engine (7 tables)

**Files:**
- Create: `packages/server/src/openlia_server/db/models/dashboard.py`
- Create: `packages/server/tests/test_db/test_models_dashboard.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_models_dashboard.py`:

```python
"""Verifies the 7 dashboard tables in §7 of database-design.md:
  pt_user_configs, pt_presets, mr_dashboard_state, mr_assessment_cache,
  rs_user_config, rs_snapshots, fe_saved_formulas.

Exercised against a tmp SQLite file via Base.metadata.create_all.
Alembic round-trip is tested in Task 4 of this plan.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    from openlia_server.db.base import Base
    import openlia_server.db.models.auth  # noqa: F401 — users table FK target
    import openlia_server.db.models.dashboard  # noqa: F401 — register models

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _make_user(db_session: Session, user_id: str = "u1") -> None:
    from openlia_server.db.models.auth import User

    db_session.add(User(id=user_id, email=f"{user_id}@example.com", display_name=user_id))
    db_session.commit()


# ---------- pt_user_configs ----------

def test_pt_user_configs_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import PtUserConfig

    cols = {c.name: c for c in PtUserConfig.__table__.columns}
    expected = {
        "id", "user_id", "active_preset_id", "panel_config",
        "composite_settings", "created_at", "updated_at",
    }
    assert set(cols.keys()) == expected
    assert cols["user_id"].unique is True
    assert cols["active_preset_id"].nullable is True


def test_pt_user_configs_one_per_user(create_tables, db_session: Session) -> None:
    """UNIQUE(user_id) — one config row per user."""
    from openlia_server.db.models.dashboard import PtUserConfig

    _make_user(db_session)
    db_session.add(PtUserConfig(id="c1", user_id="u1", panel_config=[], composite_settings={}))
    db_session.commit()

    db_session.add(PtUserConfig(id="c2", user_id="u1", panel_config=[], composite_settings={}))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_pt_user_configs_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.dashboard import PtUserConfig

    _make_user(db_session)
    db_session.add(PtUserConfig(id="c1", user_id="u1", panel_config=[], composite_settings={}))
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(PtUserConfig)).scalar_one_or_none() is None


def test_pt_user_configs_active_preset_set_null_on_preset_delete(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.dashboard import PtPreset, PtUserConfig

    _make_user(db_session)
    p = PtPreset(id="p1", user_id="u1", name="My preset", panel_config=[], composite_settings={})
    c = PtUserConfig(
        id="c1", user_id="u1", active_preset_id="p1",
        panel_config=[], composite_settings={},
    )
    db_session.add_all([p, c])
    db_session.commit()

    db_session.delete(p)
    db_session.commit()

    fresh = db_session.get(PtUserConfig, "c1")
    assert fresh.active_preset_id is None


# ---------- pt_presets ----------

def test_pt_presets_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import PtPreset

    cols = {c.name: c for c in PtPreset.__table__.columns}
    expected = {
        "id", "user_id", "name", "description", "is_shipped",
        "panel_config", "composite_settings", "created_at", "updated_at",
    }
    assert set(cols.keys()) == expected
    assert cols["user_id"].nullable is True  # shipped presets have NULL user_id
    assert cols["is_shipped"].default.arg is False


def test_pt_presets_user_name_unique(create_tables, db_session: Session) -> None:
    """UNIQUE(user_id, name) — two presets with same name for same user rejected."""
    from openlia_server.db.models.dashboard import PtPreset

    _make_user(db_session)
    db_session.add(PtPreset(id="p1", user_id="u1", name="dup", panel_config=[], composite_settings={}))
    db_session.commit()

    db_session.add(PtPreset(id="p2", user_id="u1", name="dup", panel_config=[], composite_settings={}))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_pt_presets_shipped_partial_unique(create_tables, db_session: Session) -> None:
    """Partial unique: UNIQUE(name) WHERE user_id IS NULL — shipped preset names
    are globally unique among shipped rows; two user presets with the same name
    (across different users or with a user) must not fail the partial index."""
    from openlia_server.db.models.dashboard import PtPreset

    db_session.add(PtPreset(
        id="s1", user_id=None, name="Crisis", is_shipped=True,
        panel_config=[], composite_settings={},
    ))
    db_session.commit()

    db_session.add(PtPreset(
        id="s2", user_id=None, name="Crisis", is_shipped=True,
        panel_config=[], composite_settings={},
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_pt_presets_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.dashboard import PtPreset

    _make_user(db_session)
    db_session.add(PtPreset(id="p1", user_id="u1", name="mine", panel_config=[], composite_settings={}))
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(PtPreset)).scalar_one_or_none() is None


# ---------- mr_dashboard_state ----------

def test_mr_dashboard_state_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import MrDashboardState

    cols = {c.name: c for c in MrDashboardState.__table__.columns}
    expected = {
        "id", "user_id", "dashboard", "view_config",
        "threshold_overrides", "updated_at",
    }
    assert set(cols.keys()) == expected


def test_mr_dashboard_state_user_dashboard_unique(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.dashboard import MrDashboardState

    _make_user(db_session)
    db_session.add(MrDashboardState(
        id="m1", user_id="u1", dashboard="debt_cycle",
        view_config={}, threshold_overrides={},
    ))
    db_session.commit()

    db_session.add(MrDashboardState(
        id="m2", user_id="u1", dashboard="debt_cycle",
        view_config={}, threshold_overrides={},
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------- mr_assessment_cache ----------

def test_mr_assessment_cache_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import MrAssessmentCache

    cols = {c.name: c for c in MrAssessmentCache.__table__.columns}
    expected = {
        "id", "dashboard", "assessment_type", "input_hash",
        "result", "model_ref", "token_usage", "generated_at", "expires_at",
    }
    assert set(cols.keys()) == expected


def test_mr_assessment_cache_key_unique(create_tables, db_session: Session) -> None:
    """UNIQUE(dashboard, assessment_type, input_hash) — cache hit discriminator."""
    from openlia_server.db.models.dashboard import MrAssessmentCache

    now = datetime.now(timezone.utc)
    row = MrAssessmentCache(
        id="a1", dashboard="debt_cycle", assessment_type="t4",
        input_hash="hash-1", result={}, model_ref="gpt-4",
        generated_at=now, expires_at=now + timedelta(days=7),
    )
    db_session.add(row)
    db_session.commit()

    dup = MrAssessmentCache(
        id="a2", dashboard="debt_cycle", assessment_type="t4",
        input_hash="hash-1", result={}, model_ref="gpt-4",
        generated_at=now, expires_at=now + timedelta(days=7),
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------- rs_user_config ----------

def test_rs_user_config_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import RsUserConfig

    cols = {c.name: c for c in RsUserConfig.__table__.columns}
    expected = {
        "id", "user_id", "active_tab", "metric_settings",
        "filter_presets", "refresh_interval_minutes", "updated_at",
    }
    assert set(cols.keys()) == expected
    assert cols["user_id"].unique is True
    assert cols["refresh_interval_minutes"].default.arg == 60


def test_rs_user_config_one_per_user(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.dashboard import RsUserConfig

    _make_user(db_session)
    db_session.add(RsUserConfig(id="r1", user_id="u1"))
    db_session.commit()

    db_session.add(RsUserConfig(id="r2", user_id="u1"))
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------- rs_snapshots ----------

def test_rs_snapshots_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import RsSnapshot

    cols = {c.name: c for c in RsSnapshot.__table__.columns}
    expected = {
        "id", "ticker", "snapshot_data", "source_breakdown", "captured_at",
    }
    assert set(cols.keys()) == expected


def test_rs_snapshots_has_ticker_captured_index(create_tables) -> None:
    """ix_rs_snapshots_ticker_captured must exist on (ticker, captured_at)."""
    from openlia_server.db.models.dashboard import RsSnapshot

    names = {ix.name for ix in RsSnapshot.__table__.indexes}
    assert "ix_rs_snapshots_ticker_captured" in names


# ---------- fe_saved_formulas ----------

def test_fe_saved_formulas_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import FeSavedFormula

    cols = {c.name: c for c in FeSavedFormula.__table__.columns}
    expected = {
        "id", "user_id", "name", "expression", "description",
        "department_scope", "created_at", "updated_at",
    }
    assert set(cols.keys()) == expected


def test_fe_saved_formulas_user_name_unique(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.dashboard import FeSavedFormula

    _make_user(db_session)
    db_session.add(FeSavedFormula(
        id="f1", user_id="u1", name="dup", expression="x + 1",
    ))
    db_session.commit()

    db_session.add(FeSavedFormula(
        id="f2", user_id="u1", name="dup", expression="x + 2",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_fe_saved_formulas_cascade_on_user_delete(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.dashboard import FeSavedFormula

    _make_user(db_session)
    db_session.add(FeSavedFormula(
        id="f1", user_id="u1", name="mine", expression="x + 1",
    ))
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(FeSavedFormula)).scalar_one_or_none() is None
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_dashboard.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'openlia_server.db.models.dashboard'`.

- [ ] **Step 3: Implement `dashboard.py`**

Create `packages/server/src/openlia_server/db/models/dashboard.py`:

```python
"""Dashboard and formula-engine tables from database-design.md § 7.

Rows:
  pt_user_configs, pt_presets — Panic Thermometer.
  mr_dashboard_state, mr_assessment_cache — Macro Research Dalio dashboards.
  rs_user_config, rs_snapshots — Retail Sentiment.
  fe_saved_formulas — shared formula-engine DSL rows.

Notes:
  - pt_presets.user_id is nullable: NULL rows are shipped library presets.
  - pt_user_configs.active_preset_id uses SET NULL so deleting a preset
    demotes the active config to "custom unsaved."
  - mr_assessment_cache is global (no user_id) — assessments depend on
    market data + thresholds, not user identity.
  - rs_snapshots is also global — one row per ticker per refresh cycle.
  - fe_saved_formulas.expression is stored as Text; Plan 17 (formula engine)
    validates the DSL at the service layer on write.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin


# ---------- Panic Thermometer ----------

class PtUserConfig(Base, TimestampMixin):
    """Per-user PT dashboard configuration. Replaces window.storage."""

    __tablename__ = "pt_user_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    active_preset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("pt_presets.id", ondelete="SET NULL"),
        nullable=True,
    )
    panel_config: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    composite_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class PtPreset(Base, TimestampMixin):
    """Named configuration snapshots. Shipped library presets + user-created."""

    __tablename__ = "pt_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_shipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    panel_config: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    composite_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_pt_presets_user_name"),
        # Partial unique over shipped rows: SQLAlchemy lets us declare this as
        # an Index with `unique=True` + `sqlite_where=` (the migration uses the
        # same trick). Declaring here so create_all() mirrors the migration.
        Index(
            "uq_pt_presets_shipped_name",
            "name",
            unique=True,
            sqlite_where=text("user_id IS NULL"),
        ),
    )


# ---------- Macro Research ----------

class MrDashboardState(Base):
    """Per-user state for Dalio dashboards. One row per user per dashboard."""

    __tablename__ = "mr_dashboard_state"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    dashboard: Mapped[str] = mapped_column(String(32), nullable=False)
    view_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    threshold_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "dashboard", name="uq_mr_dashboard_user_dashboard"
        ),
    )


class MrAssessmentCache(Base):
    """Cached T4/T5 LLM assessment results. Global, not per-user."""

    __tablename__ = "mr_assessment_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dashboard: Mapped[str] = mapped_column(String(32), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(16), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    model_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "dashboard", "assessment_type", "input_hash",
            name="uq_mr_assessment_dash_type_hash",
        ),
    )


# ---------- Retail Sentiment ----------

class RsUserConfig(Base):
    """Per-user Retail Sentiment dashboard configuration."""

    __tablename__ = "rs_user_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    active_tab: Mapped[str] = mapped_column(
        String(32), nullable=False, default="overview"
    )
    metric_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    filter_presets: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    refresh_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class RsSnapshot(Base):
    """Point-in-time sentiment metric snapshots. Global, per ticker per cycle."""

    __tablename__ = "rs_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_breakdown: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_rs_snapshots_ticker_captured", "ticker", "captured_at",
        ),
    )


# ---------- Formula engine ----------

class FeSavedFormula(Base, TimestampMixin):
    """User-created formulas for PT custom panels and MR T1/T2 overrides."""

    __tablename__ = "fe_saved_formulas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_fe_formulas_user_name"),
    )
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_dashboard.py -v
```
Expected: 15 tests pass.

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/db/models/dashboard.py \
                  packages/server/tests/test_db/test_models_dashboard.py
uv run ruff format --check packages/server/src/openlia_server/db/models/dashboard.py \
                           packages/server/tests/test_db/test_models_dashboard.py
```
Expected: clean. Auto-fix with `uv run ruff format` if the format check fails.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/dashboard.py \
        packages/server/tests/test_db/test_models_dashboard.py
git commit -m "feat(db): add 7 dashboard models (pt, mr, rs, fe)"
```

---

## Task 2: Scheduler + notification models (4 tables)

**Files:**
- Create: `packages/server/src/openlia_server/db/models/scheduler.py`
- Create: `packages/server/tests/test_db/test_models_scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_models_scheduler.py`:

```python
"""Verifies the 4 scheduler + notification tables:
  mb_schedules, eu_schedules, job_runs, user_notifications.

Declared in database-design.md § 7 and background-task-scheduling-design.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    from openlia_server.db.base import Base
    import openlia_server.db.models.auth  # noqa: F401 — users FK target
    import openlia_server.db.models.scheduler  # noqa: F401 — register models

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _make_user(db_session: Session, user_id: str = "u1") -> None:
    from openlia_server.db.models.auth import User

    db_session.add(User(id=user_id, email=f"{user_id}@example.com", display_name=user_id))
    db_session.commit()


# ---------- mb_schedules ----------

def test_mb_schedules_columns(create_tables) -> None:
    from openlia_server.db.models.scheduler import MbSchedule

    cols = {c.name: c for c in MbSchedule.__table__.columns}
    expected = {
        "id", "user_id", "time", "timezone", "days_of_week",
        "label", "is_enabled", "created_at", "last_run_at",
    }
    assert set(cols.keys()) == expected
    assert cols["is_enabled"].default.arg is True


def test_mb_schedules_cascade_on_user_delete(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.scheduler import MbSchedule

    _make_user(db_session)
    db_session.add(MbSchedule(
        id="s1", user_id="u1", time="07:30", timezone="America/New_York",
        days_of_week='["Mon","Tue"]',
    ))
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(MbSchedule)).scalar_one_or_none() is None


# ---------- eu_schedules ----------

def test_eu_schedules_columns(create_tables) -> None:
    from openlia_server.db.models.scheduler import EuSchedule

    cols = {c.name: c for c in EuSchedule.__table__.columns}
    expected = {
        "id", "user_id", "time", "timezone", "days_of_week",
        "label", "is_enabled", "created_at", "last_run_at",
    }
    assert set(cols.keys()) == expected


def test_eu_schedules_cascade_on_user_delete(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.scheduler import EuSchedule

    _make_user(db_session)
    db_session.add(EuSchedule(
        id="s1", user_id="u1", time="09:00", timezone="America/New_York",
        days_of_week='["Mon"]',
    ))
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(EuSchedule)).scalar_one_or_none() is None


# ---------- job_runs ----------

def test_job_runs_columns(create_tables) -> None:
    from openlia_server.db.models.scheduler import JobRun

    cols = {c.name: c for c in JobRun.__table__.columns}
    expected = {
        "id", "user_id", "job_type", "schedule_id", "status",
        "started_at", "completed_at", "error_message", "result_summary",
        "retry_of", "attempt",
    }
    assert set(cols.keys()) == expected
    assert cols["user_id"].nullable is True  # NULL for system_maintenance
    assert cols["attempt"].default.arg == 1


def test_job_runs_user_id_cascade_on_user_delete(
    create_tables, db_session: Session
) -> None:
    """Per the spec, user-scoped job_runs cascade on user deletion. System
    maintenance rows (user_id NULL) are unaffected."""
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.scheduler import JobRun

    _make_user(db_session)
    now = datetime.now(timezone.utc)
    db_session.add(JobRun(
        id="j1", user_id="u1", job_type="mb_briefing",
        status="completed", started_at=now,
    ))
    db_session.add(JobRun(
        id="j2", user_id=None, job_type="system_maintenance",
        status="completed", started_at=now,
    ))
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    rows = db_session.execute(select(JobRun)).scalars().all()
    assert {r.id for r in rows} == {"j2"}


def test_job_runs_retry_of_self_reference(create_tables, db_session: Session) -> None:
    """retry_of is a self-FK into job_runs.id with ondelete=SET NULL."""
    from openlia_server.db.models.scheduler import JobRun

    now = datetime.now(timezone.utc)
    original = JobRun(
        id="orig", user_id=None, job_type="system_maintenance",
        status="failed", started_at=now,
    )
    retry = JobRun(
        id="retry", user_id=None, job_type="system_maintenance",
        status="completed", started_at=now, retry_of="orig", attempt=2,
    )
    db_session.add_all([original, retry])
    db_session.commit()

    db_session.delete(original)
    db_session.commit()

    fresh = db_session.get(JobRun, "retry")
    assert fresh is not None
    assert fresh.retry_of is None


# ---------- user_notifications ----------

def test_user_notifications_columns(create_tables) -> None:
    from openlia_server.db.models.scheduler import UserNotification

    cols = {c.name: c for c in UserNotification.__table__.columns}
    expected = {
        "id", "user_id", "type", "department", "message",
        "job_run_id", "created_at", "read_at",
    }
    assert set(cols.keys()) == expected


def test_user_notifications_cascade_on_user_delete(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.scheduler import UserNotification

    _make_user(db_session)
    db_session.add(UserNotification(
        id="n1", user_id="u1", type="report_ready",
        department="morning_briefing", message="Your briefing is ready",
    ))
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(UserNotification)).scalar_one_or_none() is None


def test_user_notifications_job_run_set_null_on_job_delete(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.scheduler import JobRun, UserNotification

    _make_user(db_session)
    now = datetime.now(timezone.utc)
    job = JobRun(
        id="j1", user_id="u1", job_type="mb_briefing",
        status="completed", started_at=now,
    )
    notif = UserNotification(
        id="n1", user_id="u1", type="report_ready",
        department="morning_briefing", message="ok", job_run_id="j1",
    )
    db_session.add_all([job, notif])
    db_session.commit()

    db_session.delete(job)
    db_session.commit()

    fresh = db_session.get(UserNotification, "n1")
    assert fresh.job_run_id is None
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_scheduler.py -v
```
Expected: FAIL — `openlia_server.db.models.scheduler` does not exist.

- [ ] **Step 3: Implement `scheduler.py`**

Create `packages/server/src/openlia_server/db/models/scheduler.py`:

```python
"""Scheduler and notification tables.

Added by background-task-scheduling-design.md (the spec that owns the
runtime semantics); the schema itself is cross-referenced by
database-design.md § 7.

Rows:
  mb_schedules, eu_schedules — per-user cron schedules. Identical shape;
    kept as two tables so department-specific pruning/listing queries
    don't need a `kind` discriminator.
  job_runs — append-only history of every scheduled execution. Carries a
    self-referential `retry_of` pointer for user-triggered reruns, and a
    nullable `schedule_id` that points at either schedules table (no FK
    constraint — polymorphic by job_type).
  user_notifications — lightweight notification queue, polled by the
    frontend for sidebar dots.

FK notes:
  - All user_id FKs cascade on user delete, except `job_runs.user_id`
    which is SET NULL is NOT used — the spec says CASCADE for user-scoped
    job_runs. Maintenance rows (user_id NULL) are unaffected.
  - job_runs.retry_of → job_runs.id, SET NULL (prior failed run may be
    pruned independently).
  - user_notifications.job_run_id → job_runs.id, SET NULL.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base


class MbSchedule(Base):
    """Per-user Morning Briefing cron schedule."""

    __tablename__ = "mb_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    days_of_week: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("ix_mb_schedules_user", "user_id"),)


class EuSchedule(Base):
    """Per-user Earnings Update scan schedule. Identical shape to MbSchedule."""

    __tablename__ = "eu_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    days_of_week: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("ix_eu_schedules_user", "user_id"),)


class JobRun(Base):
    """Append-only execution history for every scheduled background job."""

    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Soft-polymorphic pointer: mb_schedules.id or eu_schedules.id depending
    # on job_type. No FK constraint — service layer enforces the invariant.
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("job_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index(
            "ix_job_runs_user_type_started",
            "user_id", "job_type", "started_at",
        ),
        Index("ix_job_runs_status", "status"),
        Index("ix_job_runs_schedule", "schedule_id", "started_at"),
    )


class UserNotification(Base):
    """Lightweight notification record for background job results."""

    __tablename__ = "user_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    department: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    job_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("job_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "read_at"),)
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_scheduler.py -v
```
Expected: 9 tests pass.

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/db/models/scheduler.py \
                  packages/server/tests/test_db/test_models_scheduler.py
uv run ruff format --check packages/server/src/openlia_server/db/models/scheduler.py \
                           packages/server/tests/test_db/test_models_scheduler.py
```
Expected: clean. Auto-fix with `uv run ruff format` if the format check fails.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/scheduler.py \
        packages/server/tests/test_db/test_models_scheduler.py
git commit -m "feat(db): add 4 scheduler + notification models (mb, eu, job_runs, notifications)"
```

---

## Task 3: Register the new submodules in `models/__init__.py`

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/server/tests/test_db/test_models_dashboard.py`:

```python
def test_dashboard_and_scheduler_registered_via_models_init() -> None:
    """Importing `openlia_server.db.models` alone must register every
    dashboard + scheduler table on Base.metadata. Alembic's env.py relies
    on this — it imports the package, not each submodule."""
    # Flush any half-loaded state from earlier tests
    import importlib
    import openlia_server.db.models as models_pkg

    importlib.reload(models_pkg)

    from openlia_server.db.base import Base

    registered = set(Base.metadata.tables.keys())
    required = {
        # Dashboard
        "pt_user_configs", "pt_presets",
        "mr_dashboard_state", "mr_assessment_cache",
        "rs_user_config", "rs_snapshots",
        "fe_saved_formulas",
        # Scheduler + notifications
        "mb_schedules", "eu_schedules", "job_runs", "user_notifications",
    }
    missing = required - registered
    assert missing == set(), f"Not registered via models/__init__.py: {missing}"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_dashboard.py::test_dashboard_and_scheduler_registered_via_models_init -v
```
Expected: FAIL — the new submodules are not imported by `models/__init__.py`.

- [ ] **Step 3: Update `models/__init__.py`**

Replace the contents of `packages/server/src/openlia_server/db/models/__init__.py` with:

```python
"""SQLAlchemy models, grouped by database-design.md category.

Each submodule below registers its models on Base.metadata. Importers
should `import openlia_server.db.models` — that loads every category so
`Base.metadata.tables` is complete.

Categories:
  auth          — §3 users, sessions, invites, policy, reset requests, events
  config        — §4 LLM + data + web-search provider config
  content       — §6 chat, reports, portfolio, watchlists
  infrastructure— §7 wizard_state, config_store
  dashboard     — §7 PT, MR, RS, FE (added in Plan 1B)
  scheduler     — §7 MB/EU schedules + job_runs + user_notifications (added in Plan 1B)
"""

from openlia_server.db.models import (
    auth,  # noqa: F401
    config,  # noqa: F401
    content,  # noqa: F401
    dashboard,  # noqa: F401
    infrastructure,  # noqa: F401
    scheduler,  # noqa: F401
)

__all__ = [
    "auth",
    "config",
    "content",
    "dashboard",
    "infrastructure",
    "scheduler",
]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_dashboard.py::test_dashboard_and_scheduler_registered_via_models_init -v
```
Expected: PASS.

Also run the full `test_db` suite to confirm nothing regressed:

```bash
uv run pytest packages/server/tests/test_db/ -v
```
Expected: every test still passes (prior Plan 1A tests + Task 1 + Task 2 + the new registration test). The migration test in `test_migrations.py` will fail — that is intentional and handled in Task 4.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/tests/test_db/test_models_dashboard.py
git commit -m "feat(db): register dashboard + scheduler models in models/__init__"
```

---

## Task 4: Follow-up migration — create the 11 new tables

**Files:**
- Modify: `packages/server/tests/test_db/test_migrations.py`
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-17-1200_dashboard_scheduler_notifications.py`

- [ ] **Step 1: Extend `EXPECTED_TABLES` in `test_migrations.py`**

Open `packages/server/tests/test_db/test_migrations.py`. Locate the `EXPECTED_TABLES` set (defined in Plan 1A, Task 10). Extend it so the full post-Plan-1B schema is required after `alembic upgrade head`.

Replace the `EXPECTED_TABLES = { ... }` block with:

```python
EXPECTED_TABLES = {
    # --- Plan 1A baseline (22 tables) ---
    # Auth (6)
    "users", "sessions", "signup_invites", "signup_policy",
    "password_reset_requests", "auth_events",
    # Config (6)
    "llm_providers", "llm_models", "user_llm_preferences",
    "data_providers", "data_provider_requirement_mapping", "web_search_providers",
    # Content (8)
    "chat_sessions", "chat_messages", "chat_attachments",
    "reports", "report_versions",
    "portfolio_holdings", "watchlists", "watchlist_items",
    # Infrastructure (2)
    "wizard_state", "config_store",
    # --- Plan 1B additions (11 tables) ---
    # Dashboard (7)
    "pt_user_configs", "pt_presets",
    "mr_dashboard_state", "mr_assessment_cache",
    "rs_user_config", "rs_snapshots",
    "fe_saved_formulas",
    # Scheduler + notifications (4)
    "mb_schedules", "eu_schedules", "job_runs", "user_notifications",
}
```

No other changes to `test_migrations.py` — the three existing tests (`test_baseline_upgrade_creates_all_tables`, `test_baseline_downgrade_drops_all_tables`, `test_baseline_is_idempotent`) now also assert the 11 new tables.

- [ ] **Step 2: Run the migration test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -v
```
Expected: `test_baseline_upgrade_creates_all_tables` FAILS with `Missing: {'pt_user_configs', 'pt_presets', ...}` listing the 11 new tables. The downgrade/idempotent tests may still pass because they only check behavior, not table counts.

- [ ] **Step 3: Autogenerate the follow-up migration**

From `packages/server/`:
```bash
cd packages/server && uv run alembic revision --autogenerate -m "dashboard_scheduler_notifications"
```

The `file_template` from `alembic.ini` writes a file named `packages/server/src/openlia_server/db/migrations/versions/<YYYY-MM-DD-HHMM>_dashboard_scheduler_notifications.py`. If the filename is not `2026-04-17-1200_dashboard_scheduler_notifications.py`, rename it to that exact path. The revision ID inside the file (first `revision: str = '<hex>'` line) is fine as-is — only the filename is normalized.

- [ ] **Step 4: Review and normalize the generated migration**

Open the newly generated migration file. Alembic autogenerate has known blind spots; walk through this checklist and fix each item before moving on.

**Expected file-level shape:**

```python
"""Dashboard, scheduler, and notification tables — 11 tables added on top of the Plan 1A baseline.

See database-design.md § 7 and background-task-scheduling-design.md for the canonical schemas.

Revision ID: <alembic-generated-hex>
Revises: <plan-1A-baseline-revision-id>
Create Date: 2026-04-17 12:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "<alembic-generated-hex>"
down_revision: str | Sequence[str] | None = "<plan-1A-baseline-revision-id>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ... op.create_table(...) for each of the 11 tables, in FK-safe order.
    ...


def downgrade() -> None:
    # ... op.drop_table(...) in reverse order.
    ...
```

Set `down_revision` to the Plan 1A baseline's revision ID. Find it by opening
`packages/server/src/openlia_server/db/migrations/versions/2026-04-16-1200_baseline.py` and copying the `revision: str = "..."` value.

**Checklist — items Alembic often misses:**

1. **Table creation order** matters because of inline FK constraints. Required order in `upgrade()` (and reverse in `downgrade()`):

   ```
   pt_presets          (FK to users; referenced by pt_user_configs)
   pt_user_configs     (FK to users + pt_presets)
   mr_dashboard_state  (FK to users)
   mr_assessment_cache (no FK)
   rs_user_config      (FK to users)
   rs_snapshots        (no FK)
   fe_saved_formulas   (FK to users)
   mb_schedules        (FK to users)
   eu_schedules        (FK to users)
   job_runs            (FK to users + self-ref to job_runs)
   user_notifications  (FK to users + job_runs)
   ```

   If autogenerate emitted a different order, rearrange the `op.create_table` calls to match. `downgrade()` must drop in exact reverse order.

2. **Partial unique index on `pt_presets`.** The model declares:

   ```python
   Index("uq_pt_presets_shipped_name", "name", unique=True,
         sqlite_where=text("user_id IS NULL"))
   ```

   Autogenerate should render this as:

   ```python
   op.create_index(
       "uq_pt_presets_shipped_name",
       "pt_presets",
       ["name"],
       unique=True,
       sqlite_where=sa.text("user_id IS NULL"),
   )
   ```

   If the `sqlite_where=` kwarg is absent, add it by hand. Without it the
   partial semantics are lost and the shipped-preset namespace test from
   Task 1 would still pass in isolation but real usage breaks.

3. **Self-referential FK on `job_runs.retry_of`.** Because SQLite cannot
   `ALTER TABLE ADD CONSTRAINT`, a self-FK must be declared inline in the
   `CREATE TABLE`. Autogenerate emits:

   ```python
   sa.ForeignKeyConstraint(
       ["retry_of"], ["job_runs.id"], ondelete="SET NULL",
   ),
   ```

   inside the `op.create_table("job_runs", ...)` call. Confirm this line is
   present. If Alembic generated an external `op.create_foreign_key(...)`
   call instead, move the constraint back into the `create_table` argument
   list and delete the external call.

4. **FK targeting `job_runs.id` from `user_notifications`.** Similar to
   point 3 — ensure the FK is inline in the `user_notifications` CREATE
   TABLE, not a post-hoc `op.create_foreign_key`.

5. **Named constraints.** Every `ForeignKeyConstraint`, `UniqueConstraint`,
   and `CheckConstraint` in this migration must carry a `name=` kwarg so
   the downgrade can `drop_constraint` by name. The naming convention from
   `base.py` (`fk_<table>_<col>_<referred>`, `uq_<table>_<cols>`, etc.)
   handles this automatically when the model declares the constraint with
   an explicit `name=`; if you see any anonymous constraint in the
   migration (missing `name=`), add the corresponding canonical name.

6. **Indexes.** Each of the following must appear as an `op.create_index`
   in `upgrade()` and `op.drop_index` in `downgrade()`:

   ```
   ix_rs_snapshots_ticker_captured     on rs_snapshots(ticker, captured_at)
   ix_mb_schedules_user                on mb_schedules(user_id)
   ix_eu_schedules_user                on eu_schedules(user_id)
   ix_job_runs_user_type_started       on job_runs(user_id, job_type, started_at)
   ix_job_runs_status                  on job_runs(status)
   ix_job_runs_schedule                on job_runs(schedule_id, started_at)
   ix_notifications_user_unread        on user_notifications(user_id, read_at)
   uq_pt_presets_shipped_name          on pt_presets(name)  partial
   ```

   (The `UniqueConstraint` rows — `uq_pt_presets_user_name`,
   `uq_mr_dashboard_user_dashboard`, `uq_mr_assessment_dash_type_hash`,
   `uq_fe_formulas_user_name` — are emitted inside `create_table` and do
   not need separate `create_index` calls.)

7. **`downgrade()` must drop indexes before tables.** The skeleton should
   be `drop_index(...)` for each explicit index, then `drop_table(...)`
   in reverse-creation order. Alembic's downgrade autogeneration is
   usually correct here — verify it.

After edits, save the file.

- [ ] **Step 5: Run the migration tests**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -v
```
Expected: all 4 tests pass.

- `test_alembic_env_loads` — always passed; confirms env.py still boots.
- `test_baseline_upgrade_creates_all_tables` — now finds all 33 tables.
- `test_baseline_downgrade_drops_all_tables` — downgrades from head all the
  way back to base (both migrations reversed). Must leave only
  `alembic_version`.
- `test_baseline_is_idempotent` — `upgrade head` twice still no-ops the
  second time.

If `test_baseline_downgrade_drops_all_tables` fails with "remaining: {...}",
the follow-up migration's `downgrade()` is missing a `drop_table`. Add it.

If `test_baseline_upgrade_creates_all_tables` reports extra tables, a
stale model registration is leaking into metadata — clear `__pycache__` and
rerun with `-p no:cacheprovider`.

- [ ] **Step 6: Exercise a step-up partial upgrade to the intermediate revision**

Run:
```bash
cd packages/server && OPENLIA_DB_URL="sqlite:///$(mktemp -u).db" uv run alembic upgrade <plan-1A-baseline-revision-id>
```

(Substitute the Plan 1A baseline revision ID you copied earlier.)

Expected: exit code 0. This confirms the follow-up migration's
`down_revision` correctly targets the baseline so partial upgrades still
work. No assertions here — just a smoke check. If it errors with
"Can't locate revision", fix `down_revision` in the new migration file.

- [ ] **Step 7: Ruff format + lint the migration file**

Run:
```bash
uv run ruff format packages/server/src/openlia_server/db/migrations/versions/
uv run ruff check packages/server/src/openlia_server/db/migrations/versions/
```
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-04-17-1200_dashboard_scheduler_notifications.py \
        packages/server/tests/test_db/test_migrations.py
git commit -m "feat(db): add migration for dashboard + scheduler + notification tables"
```

---

## Task 5: Acceptance — full test suite, ruff sweep, README status update

**Files:**
- Modify: `planning/implementation-plans/README.md`

- [ ] **Step 1: Run the full test suite**

Run:
```bash
uv run pytest
```
Expected: every test in both `packages/core` and `packages/server` passes.
Total test count increases by ~25 from Plan 1A (15 dashboard + 9 scheduler +
1 registration). If any test fails, stop and diagnose before continuing.

- [ ] **Step 2: Ruff sweep the whole server package**

Run:
```bash
uv run ruff check packages/server
uv run ruff format --check packages/server
```
Expected: clean. Fix anything that surfaces.

- [ ] **Step 3: Verify the `openlia serve` boot path still works against a fresh DB**

Remove any local `~/.openlia/openlia.db` (or point at a temp path) and do a
dry-run boot to ensure the combined migration chain auto-applies.

Run:
```bash
OPENLIA_DB_URL="sqlite:///$(mktemp -u).db" uv run openlia serve --help
```

Expected: the `serve` subcommand's help text prints and returns 0. (Plan
1A's bootstrap test already covers full startup against a tmp DB — this
step is a belt-and-suspenders sanity check that the CLI hasn't regressed.)

- [ ] **Step 4: Update the implementation plans README**

Open `planning/implementation-plans/README.md`. In the Status table, change
the Plan 1b row so:

- **Status** column: `Draft` (written but not executed yet).
- **File** column: `2026-04-17-phase-1b-database-dashboard-scheduler-notifications.md`.

The updated row should read:

```markdown
| 1b | 1 | Database baseline — dashboard/scheduler/notifications (11 tables) | Draft | `2026-04-17-phase-1b-database-dashboard-scheduler-notifications.md` |
```

No other changes to the README.

- [ ] **Step 5: Commit the README update**

```bash
git add planning/implementation-plans/README.md
git commit -m "docs(plan): mark Phase 1B (dashboard/scheduler/notifications) as Draft"
```

- [ ] **Step 6: Final verification**

Run once more:
```bash
uv run pytest -q
```
Expected: green.

And:
```bash
git log --oneline -n 10
```
Expected: the last ~6 commits are from this plan, in order —
`feat(db): add 7 dashboard models`,
`feat(db): add 4 scheduler + notification models`,
`feat(db): register dashboard + scheduler models in models/__init__`,
`feat(db): add migration for dashboard + scheduler + notification tables`,
`docs(plan): mark Phase 1B ... as Draft`.

Plan 1B is complete when this acceptance task is green. The database
now contains all 33 tables from the spec and every downstream plan
(Plans 6, 17, 18, 19, 20) can rely on them being present.

---

## Cross-plan notes

**For Plan 6 (Background task scheduling):** the `mb_schedules`,
`eu_schedules`, `job_runs`, and `user_notifications` tables exist; the
scheduler module rebuilds APScheduler jobs from rows in the two
department schedule tables on startup. `job_runs.schedule_id` is
polymorphic (no FK constraint) — the scheduler service must validate
that the referenced row exists in whichever table matches `job_type`.

**For Plan 7 (CLI maintenance):** the nightly prune sweep should target:
- `mr_assessment_cache` where `expires_at < now() - 30 days`.
- `rs_snapshots` where `captured_at < now() - <config_store.rs.snapshot_retention_days or 90 days>`.
- `user_notifications` where `created_at < now() - 30 days`.
- `job_runs` where `status IN ('completed', 'cancelled') AND started_at < now() - 90 days`.

**For Plan 17 (Formula engine DSL):** `fe_saved_formulas.expression` is
stored as `Text`. Parsing / validation happens in the service layer on
write — Plan 17 owns that logic. The unique constraint
`uq_fe_formulas_user_name` prevents two formulas with the same name for
the same user.

**For Plan 18 (Panic Thermometer):** the shipped preset library is
loaded into `pt_presets` with `user_id=NULL, is_shipped=True`. Suggested
approach: a Python constant list defined alongside the PT code, seeded
either via Alembic data migration at Plan 18 time or via an idempotent
"ensure shipped presets" function called during server startup. Do not
seed in Plan 1B — the preset shapes are part of the PT feature design.

**For Plan 19 (Macro Research Dalio dashboards):** `mr_dashboard_state`
is one row per `(user_id, dashboard)`. Dashboards are `debt_cycle`,
`four_seasons`, `all_weather`, `world_order`, `five_forces` — enforce
the enum at the service layer.

**For Plan 20 (Retail Sentiment):** `rs_user_config` is one row per
user; the `metric_settings` JSON follows the shape documented in the
spec (`{"wsb_mention_velocity": {"visible": true, "chart_range": "7d"}}`).
`rs_snapshots` retention lives in `config_store.rs.snapshot_retention_days`
(Plan 7 pruner honors it).

---

## Self-review notes (inline — safe to delete after execution)

- **Spec coverage:** every table and every index/constraint from
  database-design.md § 7 (dashboard, infrastructure not-already-in-Plan-1A)
  and from background-task-scheduling-design.md (schedules, job_runs,
  notifications) is produced by Task 1, Task 2, or Task 4.
- **Placeholder scan:** no TBDs, TODOs, or "similar to Task N" shortcuts.
  Every test body is concrete; every migration expectation is enumerated.
- **Type consistency:** model class names (`PtUserConfig`, `PtPreset`,
  `MrDashboardState`, `MrAssessmentCache`, `RsUserConfig`, `RsSnapshot`,
  `FeSavedFormula`, `MbSchedule`, `EuSchedule`, `JobRun`,
  `UserNotification`) used identically in Tasks 1, 2, 3, and 4's
  `EXPECTED_TABLES` via their `__tablename__`.
- **Open question — none.** The spec explicitly documents
  `job_runs.schedule_id` as a narrative FK without a DB constraint; the
  plan preserves that (no `ForeignKey` on the column). If a reviewer later
  wants a hard constraint, they can promote it to a polymorphic join
  table in a follow-up migration without breaking existing rows.
