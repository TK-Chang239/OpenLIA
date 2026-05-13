# Settings → Models Remake (Tier Removal + Slot Defaults) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every code task uses TDD: write failing test → run it red → minimal implementation → run it green → commit.

**Goal:** Rip the three-tier (`thinking`/`everyday`/`quick`) LLM resolution system out of OpenLIA and replace it with explicit per-department and per-system-role model assignments managed on a redesigned `/settings/models` page.

**Architecture:** A new `llm_slot_defaults(slot_kind, slot_id, model_id)` table holds the admin-assigned default model for each user-facing department and each internal system role. The resolver chain collapses from four levels to three: `session.model_id` → `user_department_model_prefs[user, dept]` → `llm_slot_defaults['department', dept]` → hard error. System roles use a single lookup with no user override. The `/settings/models` page becomes a three-section surface (user overrides → catalog with admin CRUD → system roles, admin-only) and the Setup Wizard's `ModelsStep` gains a third screen for explicit default assignment. Tier columns, the `user_llm_preferences` table, and the `model_defaults`/`department_defaults` curated tier maps are deleted with no backfill — this project is pre-production.

**Tech Stack:** Python 3.12 (FastAPI, SQLAlchemy 2.x typed mappings, Alembic), React 18 + TypeScript + Vite + Tailwind, pytest + Vitest, ruff for lint/format.

---

## Locked Design Decisions (from /grill-me)

| # | Decision |
|---|---|
| Q1 | Mixed audience on `/settings/models`: non-admin sees catalog (read-only) + per-department overrides; admin additionally sees CRUD + dept-default chips + system-role assignment. |
| Q2 | Primary catalog grouping: **by Provider**, with a "Defaults for" chip column. |
| Q3 | **Tiers are removed everywhere** (frontend, backend, core resolver, migrations, wizard, prompts, comments). |
| Q4 | Full rip: drop `llm_models.tier`, `llm_models.is_tier_default`, drop `user_llm_preferences` table; introduce `llm_slot_defaults`. No backfill. |
| Q5 | Per-department default lives on the model row as a multi-select chip set; backed by `llm_slot_defaults` rows with `slot_kind='department'`. |
| Q6 | Department defaults are user-overridable (`user_department_model_prefs`). System roles are global, no user override. |
| Q7 | All three sections on `/settings/models`. `/settings/admin` becomes connectors-only. |
| Q8 | Non-admin view: read-only catalog + "Your defaults per department" panel listing every department × dropdown. |
| Q9 | Page order: User overrides → Catalog → System roles. |
| Q10 | Wizard: 3 screens — keys → register models → assign defaults (departments + system roles). |
| Q11 | System roles: `ai_review`, `connector_agentic_resolver`, `graph_extraction`, `graph_summarization`. |
| Q12 | Migration: drop tier columns + drop `user_llm_preferences` + create empty `llm_slot_defaults`. No data backfill. |
| Q13 | Department resolver chain: `session.model_id` → `user_department_model_prefs[user, dept]` → `llm_slot_defaults['department', dept]` → hard error. |
| Q14 | `ModelPicker` dropdown: all enabled models, grouped by provider. No tier filter. |

---

## File Structure

### Files to create

```
packages/server/src/openlia_server/db/migrations/versions/2026-05-13_0000_remove_tiers_add_slot_defaults.py
packages/server/src/openlia_server/services/slot_defaults.py
packages/server/src/openlia_server/routes/settings_llm_slots.py
packages/core/src/openlia/llm/system_roles.py
frontend/src/api/llm_slots.ts
frontend/src/components/settings/sections/ModelsSection.test.tsx (rewrite from scratch)
frontend/src/components/settings/models/UserOverridesPanel.tsx
frontend/src/components/settings/models/ProviderCatalog.tsx
frontend/src/components/settings/models/SystemRolesPanel.tsx
frontend/src/components/settings/models/DepartmentChips.tsx
frontend/src/setup/steps/RegisterModelsScreen.tsx
frontend/src/setup/steps/AssignDefaultsScreen.tsx
packages/server/tests/server/test_slot_defaults_service.py
packages/server/tests/server/routes/test_settings_llm_slots.py
packages/core/tests/test_resolver_slot_chain.py
frontend/src/components/settings/models/__tests__/UserOverridesPanel.test.tsx
frontend/src/components/settings/models/__tests__/ProviderCatalog.test.tsx
frontend/src/components/settings/models/__tests__/SystemRolesPanel.test.tsx
frontend/src/setup/steps/__tests__/RegisterModelsScreen.test.tsx
frontend/src/setup/steps/__tests__/AssignDefaultsScreen.test.tsx
```

### Files to delete

```
packages/core/src/openlia/llm/model_defaults.py            (SHIPPED_TIER_DEFAULTS — tier-keyed)
packages/core/src/openlia/llm/department_defaults.py       (DEPARTMENT_DEFAULT_TIERS — dept→tier map)
packages/server/src/openlia_server/routes/settings_llm_user.py  (per-user tier-pref endpoints)
frontend/src/setup/steps/TiersScreen.tsx
frontend/src/setup/steps/TiersScreen.test.tsx (if present)
frontend/src/components/settings/admin/ModelsAdminPanel.tsx
frontend/src/components/settings/admin/__tests__/ModelsAdminPanel.test.tsx
```

### Files to modify

```
packages/server/src/openlia_server/db/models/config.py            (drop tier cols, drop UserLLMPreference class, add LLMSlotDefault)
packages/server/src/openlia_server/db/models/__init__.py          (exports)
packages/server/src/openlia_server/services/llm_providers.py      (drop tier helpers)
packages/server/src/openlia_server/services/llm_registry.py       (drop tier-keyed methods, add slot lookup)
packages/server/src/openlia_server/services/adapter_llm_client.py (resolve via system_role slot)
packages/server/src/openlia_server/services/runtime.py            (drop tier param)
packages/server/src/openlia_server/services/rs_runner.py          (drop tier resolution)
packages/server/src/openlia_server/services/wizard_models.py      (rewrite)
packages/server/src/openlia_server/services/graph_summarization.py
packages/server/src/openlia_server/scheduler/executors/graph_extraction.py
packages/server/src/openlia_server/ai_review/runner.py
packages/server/src/openlia_server/routes/settings.py             (admin LLM CRUD: drop tier fields)
packages/server/src/openlia_server/routes/setup.py                (drop get_enabled_default_tiers usage)
packages/server/src/openlia_server/routes/department_model_pref.py (unchanged behaviour, but drop tier fallback)
packages/server/src/openlia_server/routes/admin_graph.py
packages/server/src/openlia_server/routes/chat_sessions.py
packages/server/src/openlia_server/app.py                          (drop tier provider registry init paths)
packages/core/src/openlia/llm/types.py                             (remove ModelTier enum, drop tier from ResolvedModel)
packages/core/src/openlia/llm/__init__.py                          (drop tier exports)
packages/core/src/openlia/llm/exceptions.py                        (drop TierNotConfiguredError, add ModelNotConfiguredError)
packages/core/src/openlia/llm/resolver.py                          (rewrite — slot-based chain)
packages/core/src/openlia/llm/runtime/chat.py                      (drop tier=)
packages/core/src/openlia/llm/runtime/report.py                    (drop tier=)
packages/core/src/openlia/llm/runtime/router.py                    (drop tier=)
packages/core/src/openlia/departments/base.py                       (drop default_tier class var)
packages/core/src/openlia/departments/secretary.py                 (drop default_tier)
packages/core/src/openlia/departments/equity_research.py
packages/core/src/openlia/departments/earnings_update.py
packages/core/src/openlia/departments/morning_briefing.py
packages/core/src/openlia/departments/retail_sentiment.py
packages/core/src/openlia/departments/panic_thermometer.py
packages/core/src/openlia/departments/macro_research.py
packages/core/src/openlia/departments/__init__.py                  (drop get_enabled_default_tiers; add get_registered_system_role_ids if needed)
frontend/src/api/settings.ts                                       (drop tier types/calls; add slot list/get/put)
frontend/src/api/llm_admin.ts                                      (drop tier from AdminModel)
frontend/src/api/department-model-pref.ts                          (unchanged)
frontend/src/components/settings/sections/ModelsSection.tsx        (full rewrite)
frontend/src/components/settings/SettingsShell.tsx                  (no nav change — `/settings/models` still listed)
frontend/src/components/settings/sections/AdminSection.tsx          (drop ModelsAdminPanel import)
frontend/src/components/chat/ModelPicker.tsx                       (drop tier filter)
frontend/src/components/morning-briefing/ModelPicker.tsx            (drop tier filter)
frontend/src/components/earnings-update/ReportSettingsModal.tsx     (drop tier prop if used)
frontend/src/setup/steps/ModelsStep.tsx                              (rewrite screen state machine)
frontend/src/setup/steps/KeysScreen.tsx                              (export-only changes)
frontend/src/setup/steps/inferProvider.ts                            (unchanged)
frontend/src/api/setup.ts                                            (payload shape changes)
```

---

## Phase 0 — Branch hygiene

### Task 0.1: Confirm branch and clean state

- [ ] **Step 1: Verify branch and clean tree**

```bash
git status
git rev-parse --abbrev-ref HEAD
```

Expected: `On branch feat/settings-models-remake` and `nothing to commit, working tree clean`.

- [ ] **Step 2: Confirm baseline test suite is green before touching anything**

```bash
uv run pytest -q
cd frontend && npm test -- --run && cd ..
```

Expected: all currently-passing tests still pass. Record the count.

---

## Phase 1 — System roles registry (pure-Python, no DB yet)

### Task 1.1: Create `system_roles.py` registry in core

**Files:**
- Create: `packages/core/src/openlia/llm/system_roles.py`
- Create test: `packages/core/tests/test_system_roles.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_system_roles.py
from openlia.llm.system_roles import (
    SystemRole,
    SYSTEM_ROLE_IDS,
    get_system_role_label,
)


def test_system_role_ids_contains_locked_set():
    assert SYSTEM_ROLE_IDS == (
        "ai_review",
        "connector_agentic_resolver",
        "graph_extraction",
        "graph_summarization",
    )


def test_system_role_enum_matches_ids():
    assert {r.value for r in SystemRole} == set(SYSTEM_ROLE_IDS)


def test_get_system_role_label_returns_human_string():
    assert get_system_role_label("ai_review") == "Wizard AI review"


def test_get_system_role_label_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_system_role_label("not_a_role")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_system_roles.py -v
```

Expected: ModuleNotFoundError or ImportError on `openlia.llm.system_roles`.

- [ ] **Step 3: Write minimal implementation**

```python
# packages/core/src/openlia/llm/system_roles.py
"""Registry of internal LLM consumers ("system roles") that need an admin-
assigned model. Each role is a slot in `llm_slot_defaults` with
`slot_kind='system_role'` and `slot_id` equal to the SystemRole value.
"""
from __future__ import annotations

from enum import StrEnum


class SystemRole(StrEnum):
    AI_REVIEW = "ai_review"
    CONNECTOR_AGENTIC_RESOLVER = "connector_agentic_resolver"
    GRAPH_EXTRACTION = "graph_extraction"
    GRAPH_SUMMARIZATION = "graph_summarization"


SYSTEM_ROLE_IDS: tuple[str, ...] = tuple(r.value for r in SystemRole)


_LABELS: dict[str, str] = {
    SystemRole.AI_REVIEW.value: "Wizard AI review",
    SystemRole.CONNECTOR_AGENTIC_RESOLVER.value: "Connector agentic resolver",
    SystemRole.GRAPH_EXTRACTION.value: "Graph memory extraction",
    SystemRole.GRAPH_SUMMARIZATION.value: "Graph memory summarization",
}


def get_system_role_label(role_id: str) -> str:
    return _LABELS[role_id]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_system_roles.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/system_roles.py packages/core/tests/test_system_roles.py
git commit -m "feat(llm): add system_roles registry"
```

---

## Phase 2 — DB schema migration

### Task 2.1: Write Alembic migration that drops tier columns + `user_llm_preferences` and creates `llm_slot_defaults`

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-05-13_0000_remove_tiers_add_slot_defaults.py`
- Modify: `packages/server/tests/server/db/test_migrations.py` (update `EXPECTED_TABLES`)

- [ ] **Step 1: Find the current head revision**

```bash
uv run alembic --config packages/server/alembic.ini current
uv run alembic --config packages/server/alembic.ini heads
```

Record the head ID (e.g. `20260512_0000_er_templates`); this is the `down_revision`.

- [ ] **Step 2: Write the failing test (migrations hygiene)**

Modify `packages/server/tests/server/db/test_migrations.py`:
- Remove `"user_llm_preferences"` from `EXPECTED_TABLES`.
- Add `"llm_slot_defaults"` to `EXPECTED_TABLES`.

Add a new test:

```python
def test_llm_models_has_no_tier_columns(temp_db_url):
    from sqlalchemy import create_engine, inspect
    engine = create_engine(temp_db_url)
    upgrade_to_head(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("llm_models")}
    assert "tier" not in cols
    assert "is_tier_default" not in cols


def test_llm_slot_defaults_table_exists_with_correct_shape(temp_db_url):
    from sqlalchemy import create_engine, inspect
    engine = create_engine(temp_db_url)
    upgrade_to_head(engine)
    cols = {c["name"]: c for c in inspect(engine).get_columns("llm_slot_defaults")}
    assert set(cols.keys()) == {"slot_kind", "slot_id", "model_id", "updated_at"}
    pk = inspect(engine).get_pk_constraint("llm_slot_defaults")
    assert set(pk["constrained_columns"]) == {"slot_kind", "slot_id"}
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/server/db/test_migrations.py -v
```

Expected: the new tests fail because the migration doesn't exist yet; the EXPECTED_TABLES test fails because `user_llm_preferences` is still there and `llm_slot_defaults` is not.

- [ ] **Step 4: Write minimal migration**

```python
# packages/server/src/openlia_server/db/migrations/versions/2026-05-13_0000_remove_tiers_add_slot_defaults.py
"""remove tiers, add llm_slot_defaults

Revision ID: 20260513_0000_remove_tiers
Revises: 20260512_0000_er_templates
Create Date: 2026-05-13 00:00:00

Drops the per-tier resolution system. Adds llm_slot_defaults to store the
admin-assigned model for each user-facing department and each internal
system role. No data backfill — this project is pre-production.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260513_0000_remove_tiers"
down_revision = "20260512_0000_er_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("user_llm_preferences")

    with op.batch_alter_table("llm_models") as batch:
        batch.drop_index("ix_llm_models_tier_is_enabled")
        batch.drop_constraint("uq_llm_models_tier_default", type_="unique")
        batch.drop_constraint("tier_enum", type_="check")
        batch.drop_column("is_tier_default")
        batch.drop_column("tier")

    op.create_table(
        "llm_slot_defaults",
        sa.Column("slot_kind", sa.String(16), nullable=False),
        sa.Column("slot_id", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("slot_kind", "slot_id"),
        sa.CheckConstraint("slot_kind IN ('department','system_role')", name="slot_kind_enum"),
    )
    op.create_index("ix_llm_slot_defaults_model_id", "llm_slot_defaults", ["model_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_slot_defaults_model_id", table_name="llm_slot_defaults")
    op.drop_table("llm_slot_defaults")

    with op.batch_alter_table("llm_models") as batch:
        batch.add_column(sa.Column("tier", sa.String(16), nullable=False, server_default="everyday"))
        batch.add_column(sa.Column("is_tier_default", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_check_constraint("tier_enum", "tier IN ('thinking', 'everyday', 'quick')")
        batch.create_unique_constraint("uq_llm_models_tier_default", ["tier"])
        batch.create_index("ix_llm_models_tier_is_enabled", ["tier", "is_enabled"])

    op.create_table(
        "user_llm_preferences",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tier", sa.String(16), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tier IN ('thinking','everyday','quick')", name="tier_enum"),
    )
```

- [ ] **Step 5: Run migration tests**

```bash
uv run pytest packages/server/tests/server/db/test_migrations.py -v
```

Expected: tests now pass. Other tests will still fail because the ORM hasn't been updated yet — that's the next task.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-05-13_0000_remove_tiers_add_slot_defaults.py packages/server/tests/server/db/test_migrations.py
git commit -m "feat(db): drop tier columns + user_llm_preferences, add llm_slot_defaults"
```

### Task 2.2: Update ORM models to match new schema

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/config.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/server/tests/server/db/test_models.py`:

```python
def test_llm_model_has_no_tier_attrs():
    from openlia_server.db.models.config import LLMModel
    assert not hasattr(LLMModel, "tier")
    assert not hasattr(LLMModel, "is_tier_default")


def test_llm_slot_default_model_exists():
    from openlia_server.db.models.config import LLMSlotDefault
    assert LLMSlotDefault.__tablename__ == "llm_slot_defaults"
    cols = {c.name for c in LLMSlotDefault.__table__.columns}
    assert cols == {"slot_kind", "slot_id", "model_id", "updated_at"}


def test_user_llm_preference_removed():
    import openlia_server.db.models.config as cfg
    assert not hasattr(cfg, "UserLLMPreference")
```

- [ ] **Step 2: Run test (expect failure)**

```bash
uv run pytest packages/server/tests/server/db/test_models.py -v
```

Expected: failures because `LLMSlotDefault` is missing and `UserLLMPreference` still exists.

- [ ] **Step 3: Edit `config.py`**

In `packages/server/src/openlia_server/db/models/config.py`:

1. **In class `LLMModel`** — remove the `tier`, `is_tier_default` columns; remove `ix_llm_models_tier_is_enabled` index; remove the unique constraint `uq_llm_models_tier_default`; remove the `tier_enum` CheckConstraint.
2. **Delete the entire `UserLLMPreference` class.**
3. **Append a new class:**

```python
class LLMSlotDefault(Base):
    """Maps a (slot_kind, slot_id) pair to the admin-assigned model_id.

    slot_kind is 'department' (e.g. 'secretary', 'equity_research') or
    'system_role' (e.g. 'ai_review', 'graph_extraction'). Replaces the
    per-tier default model mechanism.
    """

    __tablename__ = "llm_slot_defaults"

    slot_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    slot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "slot_kind IN ('department','system_role')", name="slot_kind_enum"
        ),
        Index("ix_llm_slot_defaults_model_id", "model_id"),
    )
```

4. **In `db/models/__init__.py`**, replace any `UserLLMPreference` export with `LLMSlotDefault`.

- [ ] **Step 4: Run tests**

```bash
uv run pytest packages/server/tests/server/db/test_models.py -v
```

Expected: 3 new tests pass. Many downstream tests will now fail because the resolver, services, and routes still reference `tier`. Those are addressed in later phases.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/models/config.py packages/server/src/openlia_server/db/models/__init__.py packages/server/tests/server/db/test_models.py
git commit -m "feat(db): drop tier columns + UserLLMPreference; add LLMSlotDefault model"
```

---

## Phase 3 — Core resolver rewrite

### Task 3.1: Replace `TierNotConfiguredError` with `ModelNotConfiguredError`

**Files:**
- Modify: `packages/core/src/openlia/llm/exceptions.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_exceptions.py (create or append)
def test_model_not_configured_error_exists_with_slot_id():
    from openlia.llm.exceptions import ModelNotConfiguredError
    e = ModelNotConfiguredError(slot_kind="department", slot_id="secretary")
    assert e.slot_kind == "department"
    assert e.slot_id == "secretary"
    assert "secretary" in str(e)
    assert "Settings" in str(e)


def test_tier_not_configured_error_removed():
    import openlia.llm.exceptions as exc
    assert not hasattr(exc, "TierNotConfiguredError")
```

- [ ] **Step 2: Run (expect failure)**

```bash
uv run pytest packages/core/tests/test_exceptions.py -v
```

- [ ] **Step 3: Edit `packages/core/src/openlia/llm/exceptions.py`**

Delete `class TierNotConfiguredError`. Append:

```python
class ModelNotConfiguredError(Exception):
    """No model has been assigned to a slot in `llm_slot_defaults`.

    Raised by the resolver when no per-user override, no per-department
    user pref, and no admin-assigned slot default exists. The message
    directs the operator to the Settings page.
    """

    def __init__(self, *, slot_kind: str, slot_id: str) -> None:
        self.slot_kind = slot_kind
        self.slot_id = slot_id
        super().__init__(
            f"No model is configured for {slot_kind}={slot_id!r}. "
            f"Assign one in Settings → Models."
        )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest packages/core/tests/test_exceptions.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/exceptions.py packages/core/tests/test_exceptions.py
git commit -m "feat(llm): replace TierNotConfiguredError with ModelNotConfiguredError"
```

### Task 3.2: Rewrite `resolver.py` to a slot-based chain

**Files:**
- Modify: `packages/core/src/openlia/llm/resolver.py`
- Modify: `packages/core/src/openlia/llm/types.py` (drop `tier` from `ResolvedModel` and `ResolvedModelRow`; remove `ModelTier` enum)
- Modify: `packages/core/src/openlia/llm/__init__.py`
- Create: `packages/core/tests/test_resolver_slot_chain.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_resolver_slot_chain.py
from dataclasses import dataclass

import pytest

from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.resolver import ModelRegistry, ResolvedModelRow, resolve
from openlia.llm.types import ProviderCredentials


def _row(model_id: str = "M1") -> ResolvedModelRow:
    return ResolvedModelRow(
        model_id=model_id,
        model_ref="m",
        overrides={},
        provider_id="P1",
        provider_kind="openai",
        credentials=ProviderCredentials(api_key="k", base_url=None, env_var_name=None),
        capability_override=None,
    )


@dataclass
class FakeRegistry:
    by_id: dict[str, ResolvedModelRow]
    dept_user_override: dict[tuple[str, str], ResolvedModelRow]
    dept_slot_default: dict[str, ResolvedModelRow]
    system_role_default: dict[str, ResolvedModelRow]

    def get_by_id(self, mid):
        return self.by_id.get(mid)

    def get_department_user_override(self, user_id, dept):
        return self.dept_user_override.get((user_id, dept))

    def get_department_slot_default(self, dept):
        return self.dept_slot_default.get(dept)

    def get_system_role_default(self, role):
        return self.system_role_default.get(role)


def test_model_id_override_wins():
    row = _row("forced")
    reg = FakeRegistry({"forced": row}, {}, {}, {})
    out = resolve(department_id="secretary", registry=reg, user_id="U", model_id_override="forced")
    assert out.model_id == "forced"


def test_falls_through_to_user_dept_override_when_explicit_pick_missing():
    over = _row("U-dept")
    reg = FakeRegistry({}, {("U", "secretary"): over}, {}, {})
    out = resolve(department_id="secretary", registry=reg, user_id="U", model_id_override="ghost")
    assert out.model_id == "U-dept"


def test_user_dept_override_wins_over_slot_default():
    over = _row("U-dept")
    default = _row("D")
    reg = FakeRegistry({}, {("U", "secretary"): over}, {"secretary": default}, {})
    out = resolve(department_id="secretary", registry=reg, user_id="U")
    assert out.model_id == "U-dept"


def test_slot_default_used_when_no_user_override():
    default = _row("D")
    reg = FakeRegistry({}, {}, {"secretary": default}, {})
    out = resolve(department_id="secretary", registry=reg, user_id="U")
    assert out.model_id == "D"


def test_no_chain_match_raises_model_not_configured():
    reg = FakeRegistry({}, {}, {}, {})
    with pytest.raises(ModelNotConfiguredError) as ei:
        resolve(department_id="secretary", registry=reg, user_id="U")
    assert ei.value.slot_kind == "department"
    assert ei.value.slot_id == "secretary"


def test_resolve_system_role_uses_system_role_default():
    from openlia.llm.resolver import resolve_system_role
    default = _row("R")
    reg = FakeRegistry({}, {}, {}, {"ai_review": default})
    out = resolve_system_role(role_id="ai_review", registry=reg)
    assert out.model_id == "R"


def test_resolve_system_role_missing_raises():
    from openlia.llm.resolver import resolve_system_role
    reg = FakeRegistry({}, {}, {}, {})
    with pytest.raises(ModelNotConfiguredError) as ei:
        resolve_system_role(role_id="ai_review", registry=reg)
    assert ei.value.slot_kind == "system_role"
    assert ei.value.slot_id == "ai_review"
```

- [ ] **Step 2: Run (expect failure)**

```bash
uv run pytest packages/core/tests/test_resolver_slot_chain.py -v
```

- [ ] **Step 3: Edit `packages/core/src/openlia/llm/types.py`**

Delete the `ModelTier` StrEnum entirely. Edit `ResolvedModel` and `ResolvedModelRow` (if defined here) to drop the `tier: ModelTier` field. (`ResolvedModelRow` lives in `resolver.py` — handle it there in the next step.)

- [ ] **Step 4: Rewrite `packages/core/src/openlia/llm/resolver.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openlia.llm.capabilities import capabilities_for
from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.types import ProviderCredentials, ResolvedModel


@dataclass(frozen=True)
class ResolvedModelRow:
    model_id: str
    model_ref: str
    overrides: dict
    provider_id: str
    provider_kind: str
    credentials: ProviderCredentials
    capability_override: dict | None


class ModelRegistry(Protocol):
    def get_by_id(self, model_id: str) -> ResolvedModelRow | None: ...

    def get_department_user_override(
        self, user_id: str, department_id: str
    ) -> ResolvedModelRow | None: ...

    def get_department_slot_default(
        self, department_id: str
    ) -> ResolvedModelRow | None: ...

    def get_system_role_default(self, role_id: str) -> ResolvedModelRow | None: ...


def _to_resolved(row: ResolvedModelRow) -> ResolvedModel:
    caps = capabilities_for(
        provider_kind=row.provider_kind,
        model=row.model_ref,
        override=row.capability_override,
    )
    return ResolvedModel(
        provider_kind=row.provider_kind,
        provider_id=row.provider_id,
        model_id=row.model_id,
        model_ref=row.model_ref,
        credentials=row.credentials,
        capabilities=caps,
        overrides=row.overrides or {},
    )


def resolve(
    *,
    department_id: str,
    registry: ModelRegistry,
    user_id: str | None,
    model_id_override: str | None = None,
) -> ResolvedModel:
    """Department-scoped resolution.

    Chain: explicit model_id_override (e.g. chat session.model_id) →
    per-user-per-department pref → admin slot default for the department.
    Raises `ModelNotConfiguredError` when nothing matches.
    """
    if model_id_override is not None:
        row = registry.get_by_id(model_id_override)
        if row is not None:
            return _to_resolved(row)

    if user_id is not None:
        over = registry.get_department_user_override(user_id, department_id)
        if over is not None:
            return _to_resolved(over)

    slot = registry.get_department_slot_default(department_id)
    if slot is not None:
        return _to_resolved(slot)

    raise ModelNotConfiguredError(slot_kind="department", slot_id=department_id)


def resolve_system_role(
    *, role_id: str, registry: ModelRegistry
) -> ResolvedModel:
    """System-role resolution. No user override. Direct slot lookup."""
    row = registry.get_system_role_default(role_id)
    if row is None:
        raise ModelNotConfiguredError(slot_kind="system_role", slot_id=role_id)
    return _to_resolved(row)
```

- [ ] **Step 5: Update `packages/core/src/openlia/llm/__init__.py`**

Remove exports: `ModelTier`, `TierNotConfiguredError`. Add: `ModelNotConfiguredError`, `resolve_system_role`. Drop any imports of `model_defaults` or `department_defaults` (those files are deleted in Phase 8).

- [ ] **Step 6: Run tests**

```bash
uv run pytest packages/core/tests/test_resolver_slot_chain.py -v
```

Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/llm/resolver.py packages/core/src/openlia/llm/types.py packages/core/src/openlia/llm/__init__.py packages/core/tests/test_resolver_slot_chain.py
git commit -m "feat(llm): rewrite resolver as slot-based chain"
```

### Task 3.3: Drop tier-keyed call sites in core runtime

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/chat.py`
- Modify: `packages/core/src/openlia/llm/runtime/report.py`
- Modify: `packages/core/src/openlia/llm/runtime/router.py`

- [ ] **Step 1: Find every `tier=` or `ModelTier` reference in runtime**

```bash
grep -rn "tier=\|ModelTier" packages/core/src/openlia/llm/runtime/
```

- [ ] **Step 2: Update each call site**

For every `resolve(..., tier_override=...)` call, drop the `tier_override` argument. For every `ResolvedModel.tier` access, remove it. The runtime's `ChatRunner`/`ReportRunner` should not pass a tier — they pass `department_id`, `user_id`, and optionally `model_id_override`.

- [ ] **Step 3: Run core test suite**

```bash
uv run pytest packages/core/tests -v
```

Many existing tests will fail because the resolver protocol changed; fix tests one by one to drop tier args. Each fix is a one-line edit.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/ packages/core/tests/
git commit -m "refactor(llm-runtime): drop tier params from chat/report/router"
```

### Task 3.4: Drop tier class vars from Departments

**Files:**
- Modify: `packages/core/src/openlia/departments/base.py`
- Modify: each `packages/core/src/openlia/departments/*.py` (delete `tier = ModelTier.XXX` lines)
- Modify: `packages/core/src/openlia/departments/__init__.py` (delete `get_enabled_default_tiers`)

- [ ] **Step 1: Write failing test**

```python
# packages/core/tests/test_departments_no_tier.py
import pytest

from openlia.departments import (
    EquityResearchDepartment,
    SecretaryDepartment,
)


def test_department_has_no_tier_attr():
    assert not hasattr(SecretaryDepartment(), "tier")
    assert not hasattr(EquityResearchDepartment(), "tier")


def test_get_enabled_default_tiers_removed():
    import openlia.departments as dpt
    assert not hasattr(dpt, "get_enabled_default_tiers")
```

- [ ] **Step 2: Run (expect failure)**

```bash
uv run pytest packages/core/tests/test_departments_no_tier.py -v
```

- [ ] **Step 3: Remove `tier = ModelTier.XXX` from each Department subclass**

In each file under `packages/core/src/openlia/departments/`, delete the class-level `tier: ModelTier = ModelTier.XXX` attribute and any `from openlia.llm.types import ModelTier` import that becomes unused.

In `packages/core/src/openlia/departments/__init__.py`, delete the `get_enabled_default_tiers` function entirely and its `__all__` entry.

In `base.py`, drop the `tier` class var declaration.

- [ ] **Step 4: Run tests**

```bash
uv run pytest packages/core/tests/test_departments_no_tier.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/departments/
git commit -m "refactor(departments): drop tier class var; remove get_enabled_default_tiers"
```

---

## Phase 4 — Server services: slot defaults + adapter wiring

### Task 4.1: Slot-defaults service

**Files:**
- Create: `packages/server/src/openlia_server/services/slot_defaults.py`
- Create test: `packages/server/tests/server/test_slot_defaults_service.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/server/test_slot_defaults_service.py
import pytest

from openlia_server.db.models.config import LLMSlotDefault
from openlia_server.services.slot_defaults import (
    InvalidSlotError,
    SlotDefaultsService,
    get_slot_default_model_id,
    list_slot_defaults,
    set_slot_default,
    delete_slot_default,
)


def test_set_then_get_department_slot(db_session, llm_model_factory):
    model = llm_model_factory()
    set_slot_default(
        db_session, slot_kind="department", slot_id="secretary", model_id=model.id
    )
    assert get_slot_default_model_id(db_session, "department", "secretary") == model.id


def test_set_then_get_system_role_slot(db_session, llm_model_factory):
    model = llm_model_factory()
    set_slot_default(
        db_session, slot_kind="system_role", slot_id="ai_review", model_id=model.id
    )
    assert (
        get_slot_default_model_id(db_session, "system_role", "ai_review") == model.id
    )


def test_set_overwrites_existing(db_session, llm_model_factory):
    m1 = llm_model_factory()
    m2 = llm_model_factory()
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=m1.id)
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=m2.id)
    assert get_slot_default_model_id(db_session, "department", "secretary") == m2.id


def test_invalid_slot_kind_raises(db_session, llm_model_factory):
    model = llm_model_factory()
    with pytest.raises(InvalidSlotError):
        set_slot_default(db_session, slot_kind="bogus", slot_id="x", model_id=model.id)


def test_invalid_department_slot_id_raises(db_session, llm_model_factory):
    model = llm_model_factory()
    with pytest.raises(InvalidSlotError):
        set_slot_default(
            db_session, slot_kind="department", slot_id="not_a_dept", model_id=model.id
        )


def test_invalid_system_role_slot_id_raises(db_session, llm_model_factory):
    model = llm_model_factory()
    with pytest.raises(InvalidSlotError):
        set_slot_default(
            db_session, slot_kind="system_role", slot_id="ghost", model_id=model.id
        )


def test_delete_removes_row(db_session, llm_model_factory):
    model = llm_model_factory()
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=model.id)
    delete_slot_default(db_session, slot_kind="department", slot_id="secretary")
    assert get_slot_default_model_id(db_session, "department", "secretary") is None


def test_list_returns_all_defaults(db_session, llm_model_factory):
    m1 = llm_model_factory()
    m2 = llm_model_factory()
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=m1.id)
    set_slot_default(db_session, slot_kind="system_role", slot_id="ai_review", model_id=m2.id)
    rows = list_slot_defaults(db_session)
    assert len(rows) == 2
    by_kv = {(r.slot_kind, r.slot_id): r.model_id for r in rows}
    assert by_kv == {
        ("department", "secretary"): m1.id,
        ("system_role", "ai_review"): m2.id,
    }
```

Note: `db_session` and `llm_model_factory` fixtures already exist in the test suite. Inspect `packages/server/tests/server/conftest.py` and reuse them or create `llm_model_factory` if missing (a factory that inserts an `LLMProvider` + `LLMModel`).

- [ ] **Step 2: Run (expect failure)**

```bash
uv run pytest packages/server/tests/server/test_slot_defaults_service.py -v
```

- [ ] **Step 3: Implement service**

```python
# packages/server/src/openlia_server/services/slot_defaults.py
"""CRUD for `llm_slot_defaults`. Replaces the per-tier default mechanism.

Validates `slot_kind` against {'department', 'system_role'} and `slot_id`
against the registered departments (from `get_registered_department_ids`)
or system roles (from `SYSTEM_ROLE_IDS`).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from openlia.departments import get_registered_department_ids
from openlia.llm.system_roles import SYSTEM_ROLE_IDS
from openlia_server.db.models.config import LLMSlotDefault


class InvalidSlotError(ValueError):
    pass


_VALID_KINDS = {"department", "system_role"}


def _validate_slot(slot_kind: str, slot_id: str) -> None:
    if slot_kind not in _VALID_KINDS:
        raise InvalidSlotError(f"Unknown slot_kind {slot_kind!r}")
    if slot_kind == "department" and slot_id not in get_registered_department_ids():
        raise InvalidSlotError(f"Unknown department {slot_id!r}")
    if slot_kind == "system_role" and slot_id not in SYSTEM_ROLE_IDS:
        raise InvalidSlotError(f"Unknown system role {slot_id!r}")


def set_slot_default(
    db: Session, *, slot_kind: str, slot_id: str, model_id: str
) -> LLMSlotDefault:
    _validate_slot(slot_kind, slot_id)
    row = db.get(LLMSlotDefault, (slot_kind, slot_id))
    if row is None:
        row = LLMSlotDefault(slot_kind=slot_kind, slot_id=slot_id, model_id=model_id)
        db.add(row)
    else:
        row.model_id = model_id
    db.commit()
    db.refresh(row)
    return row


def get_slot_default_model_id(
    db: Session, slot_kind: str, slot_id: str
) -> str | None:
    row = db.get(LLMSlotDefault, (slot_kind, slot_id))
    return row.model_id if row is not None else None


def delete_slot_default(db: Session, *, slot_kind: str, slot_id: str) -> None:
    row = db.get(LLMSlotDefault, (slot_kind, slot_id))
    if row is not None:
        db.delete(row)
        db.commit()


def list_slot_defaults(db: Session) -> list[LLMSlotDefault]:
    return db.query(LLMSlotDefault).all()


class SlotDefaultsService:
    """Optional thin wrapper, in case route handlers want a class API."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, slot_kind: str, slot_id: str) -> str | None:
        return get_slot_default_model_id(self._db, slot_kind, slot_id)

    def set(self, slot_kind: str, slot_id: str, model_id: str) -> LLMSlotDefault:
        return set_slot_default(
            self._db, slot_kind=slot_kind, slot_id=slot_id, model_id=model_id
        )

    def delete(self, slot_kind: str, slot_id: str) -> None:
        delete_slot_default(self._db, slot_kind=slot_kind, slot_id=slot_id)

    def list_all(self) -> list[LLMSlotDefault]:
        return list_slot_defaults(self._db)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest packages/server/tests/server/test_slot_defaults_service.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/slot_defaults.py packages/server/tests/server/test_slot_defaults_service.py
git commit -m "feat(server): add slot_defaults service"
```

### Task 4.2: Rewrite `llm_registry.py` to implement the new `ModelRegistry` protocol

**Files:**
- Modify: `packages/server/src/openlia_server/services/llm_registry.py`

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/server/test_llm_registry_slot.py
from openlia_server.services.llm_registry import SQLModelRegistry


def test_get_department_slot_default_returns_row(db_session, llm_model_factory):
    from openlia_server.services.slot_defaults import set_slot_default
    m = llm_model_factory()
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=m.id)
    reg = SQLModelRegistry(db_session)
    row = reg.get_department_slot_default("secretary")
    assert row is not None
    assert row.model_id == m.id


def test_get_system_role_default_returns_row(db_session, llm_model_factory):
    from openlia_server.services.slot_defaults import set_slot_default
    m = llm_model_factory()
    set_slot_default(db_session, slot_kind="system_role", slot_id="ai_review", model_id=m.id)
    reg = SQLModelRegistry(db_session)
    row = reg.get_system_role_default("ai_review")
    assert row is not None
    assert row.model_id == m.id


def test_registry_no_longer_exposes_tier_methods(db_session):
    reg = SQLModelRegistry(db_session)
    assert not hasattr(reg, "get_tier_default")
    assert not hasattr(reg, "get_any_in_tier")
    assert not hasattr(reg, "get_user_preference")
    assert not hasattr(reg, "get_department_tier_override")
```

- [ ] **Step 2: Run (expect failure)**

```bash
uv run pytest packages/server/tests/server/test_llm_registry_slot.py -v
```

- [ ] **Step 3: Edit `llm_registry.py`**

Strip every tier-keyed method (`get_tier_default`, `get_any_in_tier`, `get_user_preference`, `get_department_tier_override`). Drop any code that reads `LLMModel.tier` or `LLMModel.is_tier_default`. Add:

```python
def get_department_slot_default(self, department_id: str) -> ResolvedModelRow | None:
    from openlia_server.db.models.config import LLMSlotDefault
    row = self._db.get(LLMSlotDefault, ("department", department_id))
    if row is None:
        return None
    return self.get_by_id(row.model_id)


def get_system_role_default(self, role_id: str) -> ResolvedModelRow | None:
    from openlia_server.db.models.config import LLMSlotDefault
    row = self._db.get(LLMSlotDefault, ("system_role", role_id))
    if row is None:
        return None
    return self.get_by_id(row.model_id)
```

Keep `get_by_id` and `get_department_user_override`. The class's `__init__` and DB shape stay the same; just the method surface changes.

- [ ] **Step 4: Run tests**

```bash
uv run pytest packages/server/tests/server/test_llm_registry_slot.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/llm_registry.py packages/server/tests/server/test_llm_registry_slot.py
git commit -m "refactor(llm-registry): replace tier methods with slot lookups"
```

### Task 4.3: Update `adapter_llm_client._resolve_provider` to take a system role

**Files:**
- Modify: `packages/server/src/openlia_server/services/adapter_llm_client.py`
- Modify: `packages/server/src/openlia_server/routes/admin_graph.py`
- Modify: `packages/server/src/openlia_server/scheduler/executors/graph_extraction.py`

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/server/test_adapter_llm_client_role.py
import pytest

from openlia.llm.exceptions import ModelNotConfiguredError
from openlia_server.services.adapter_llm_client import (
    AdapterLlmNotConfigured,
    _resolve_provider_for_role,
)


def test_resolve_for_role_returns_provider(db_session, llm_model_factory):
    from openlia_server.services.slot_defaults import set_slot_default
    m = llm_model_factory()
    set_slot_default(db_session, slot_kind="system_role", slot_id="graph_extraction", model_id=m.id)
    provider = _resolve_provider_for_role(db_session, "graph_extraction")
    assert provider is not None


def test_resolve_for_role_raises_when_unset(db_session):
    with pytest.raises(AdapterLlmNotConfigured) as ei:
        _resolve_provider_for_role(db_session, "graph_extraction")
    assert "graph_extraction" in str(ei.value)
```

- [ ] **Step 2: Run (expect failure)**

- [ ] **Step 3: Replace `_resolve_provider` body**

```python
def _resolve_provider_for_role(db: DBSession, role_id: str) -> LLMProvider:
    from openlia.llm.resolver import resolve_system_role
    registry = SQLModelRegistry(db)
    try:
        resolved = resolve_system_role(role_id=role_id, registry=registry)
    except ModelNotConfiguredError as exc:
        raise AdapterLlmNotConfigured(
            f"System role {role_id!r} has no model assigned. "
            f"Set one in Settings → Models → System roles."
        ) from exc
    return build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=resolved.capabilities,
    )
```

Replace the old `_resolve_provider(db, tiers=...)` with this new function. Then update the two call sites:

- `scheduler/executors/graph_extraction.py:103`: `return _resolve_provider_for_role(db, "graph_extraction")`
- `routes/admin_graph.py:75`: `provider = _resolve_provider_for_role(db, "graph_extraction")`
- The wizard agentic resolver factory (`make_agentic_resolver_factory`, around line 197): replace `_resolve_provider(db, _AGENTIC_TIERS)` with `_resolve_provider_for_role(db, "connector_agentic_resolver")`.

Delete the `_AGENTIC_TIERS` constant.

- [ ] **Step 4: Run tests**

```bash
uv run pytest packages/server/tests/server/test_adapter_llm_client_role.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/adapter_llm_client.py packages/server/src/openlia_server/scheduler/executors/graph_extraction.py packages/server/src/openlia_server/routes/admin_graph.py packages/server/tests/server/test_adapter_llm_client_role.py
git commit -m "refactor(adapter-llm): resolve internal LLMs by system_role slot"
```

### Task 4.4: Update remaining internal consumers (ai_review, graph_summarization)

**Files:**
- Modify: `packages/server/src/openlia_server/ai_review/runner.py`
- Modify: `packages/server/src/openlia_server/services/graph_summarization.py`

- [ ] **Step 1: Read each caller**

```bash
grep -n -E "tier|Tier" packages/server/src/openlia_server/ai_review/runner.py packages/server/src/openlia_server/services/graph_summarization.py
```

- [ ] **Step 2: For each, replace tier-based resolution with `_resolve_provider_for_role`**

`ai_review/runner.py`: replace tier-based provider lookup with `_resolve_provider_for_role(db, "ai_review")`.

`services/graph_summarization.py`: replace with `_resolve_provider_for_role(db, "graph_summarization")`.

Update the module docstring on `runner.py` (first line currently says "Quick-tier LLM") to say "the model assigned to the `ai_review` system role."

- [ ] **Step 3: Run server tests touching these**

```bash
uv run pytest packages/server/tests -k "ai_review or graph_summarization or graph_extraction" -v
```

Fix any fakes that need updating (tests likely set fake tiers; now they need to seed `llm_slot_defaults`).

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/ai_review/runner.py packages/server/src/openlia_server/services/graph_summarization.py packages/server/tests/
git commit -m "refactor(internal-llm): ai_review + graph_summarization use system_role slots"
```

### Task 4.5: Strip tier from `services/runtime.py`, `rs_runner.py`, `wizard_models.py`

**Files:**
- Modify: `packages/server/src/openlia_server/services/runtime.py`
- Modify: `packages/server/src/openlia_server/services/rs_runner.py`
- Modify: `packages/server/src/openlia_server/services/wizard_models.py`

- [ ] **Step 1: Inspect tier usage**

```bash
grep -n -E "tier|Tier" packages/server/src/openlia_server/services/runtime.py packages/server/src/openlia_server/services/rs_runner.py packages/server/src/openlia_server/services/wizard_models.py
```

- [ ] **Step 2: Rewrite `wizard_models.py`**

The wizard previously persisted models grouped by tier. Rewrite the payload shape to:

```python
class RegisterModelInput(BaseModel):
    provider_kind: str
    api_key: str | None
    base_url: str | None
    model_ref: str
    display_name: str


class WizardModelsPayload(BaseModel):
    models: list[RegisterModelInput]
    department_defaults: dict[str, str]   # dept_id -> model_ref
    system_role_defaults: dict[str, str]  # role_id -> model_ref
```

The service should:
1. For each unique (provider_kind, api_key, base_url), upsert an `LLMProvider`.
2. For each model, upsert an `LLMModel` with the provider linkage.
3. For each `department_defaults` entry, call `set_slot_default(slot_kind='department', slot_id=dept, model_id=<resolved model id>)`.
4. For each `system_role_defaults` entry, call `set_slot_default(slot_kind='system_role', slot_id=role, model_id=<resolved model id>)`.

Add a service-level test:

```python
# packages/server/tests/server/test_wizard_models.py
def test_wizard_models_persists_providers_models_and_slots(db_session):
    from openlia_server.services.wizard_models import save_wizard_models, WizardModelsPayload
    payload = WizardModelsPayload(
        models=[{"provider_kind":"openai","api_key":"k","base_url":None,"model_ref":"gpt-x","display_name":"GPT X"}],
        department_defaults={"secretary": "gpt-x"},
        system_role_defaults={"ai_review": "gpt-x"},
    )
    save_wizard_models(db_session, payload)
    from openlia_server.services.slot_defaults import get_slot_default_model_id
    assert get_slot_default_model_id(db_session, "department", "secretary") is not None
    assert get_slot_default_model_id(db_session, "system_role", "ai_review") is not None
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest packages/server/tests/server/test_wizard_models.py -v
uv run pytest packages/server/tests -k "runtime or rs_runner" -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/services/runtime.py packages/server/src/openlia_server/services/rs_runner.py packages/server/src/openlia_server/services/wizard_models.py packages/server/tests/server/test_wizard_models.py
git commit -m "refactor(services): drop tier from runtime, rs_runner, wizard_models"
```

---

## Phase 5 — Server routes

### Task 5.1: Strip tier fields from `/api/settings/admin/llm/*`

**Files:**
- Modify: `packages/server/src/openlia_server/routes/settings.py`

- [ ] **Step 1: Identify tier-bearing fields**

```bash
grep -n -E "tier|Tier" packages/server/src/openlia_server/routes/settings.py
```

- [ ] **Step 2: Update Pydantic models**

- `AdminModelIn` / `AdminModelOut`: remove `tier` and `is_tier_default` fields.
- `AdminModelUpdateIn`: same.
- `_serialize_model` helper: drop tier keys from the dict it returns.

- [ ] **Step 3: Update tests**

```bash
grep -rn "tier" packages/server/tests/server/routes/test_settings*.py | head -40
```

For every assertion on `tier`/`is_tier_default`, delete the line or replace with a slot-defaults check (Task 5.2 will add slot endpoints).

- [ ] **Step 4: Run**

```bash
uv run pytest packages/server/tests/server/routes/test_settings.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings.py packages/server/tests/server/routes/
git commit -m "refactor(routes/settings): drop tier fields from admin LLM CRUD"
```

### Task 5.2: New slot-defaults endpoints under `/api/settings/admin/llm/slot-defaults`

**Files:**
- Create: `packages/server/src/openlia_server/routes/settings_llm_slots.py`
- Modify: `packages/server/src/openlia_server/app.py` (register router)
- Create test: `packages/server/tests/server/routes/test_settings_llm_slots.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/server/routes/test_settings_llm_slots.py
def test_list_slot_defaults_empty(admin_client):
    r = admin_client.get("/api/settings/admin/llm/slot-defaults")
    assert r.status_code == 200
    assert r.json() == {"defaults": []}


def test_put_dept_slot_default(admin_client, llm_model_factory, db_session):
    m = llm_model_factory()
    r = admin_client.put(
        "/api/settings/admin/llm/slot-defaults/department/secretary",
        json={"model_id": m.id},
    )
    assert r.status_code == 200
    assert r.json()["model_id"] == m.id


def test_put_invalid_dept_400(admin_client, llm_model_factory):
    m = llm_model_factory()
    r = admin_client.put(
        "/api/settings/admin/llm/slot-defaults/department/ghost",
        json={"model_id": m.id},
    )
    assert r.status_code == 400


def test_put_system_role_slot(admin_client, llm_model_factory):
    m = llm_model_factory()
    r = admin_client.put(
        "/api/settings/admin/llm/slot-defaults/system_role/ai_review",
        json={"model_id": m.id},
    )
    assert r.status_code == 200


def test_delete_slot(admin_client, llm_model_factory, db_session):
    m = llm_model_factory()
    admin_client.put(
        "/api/settings/admin/llm/slot-defaults/department/secretary",
        json={"model_id": m.id},
    )
    r = admin_client.delete("/api/settings/admin/llm/slot-defaults/department/secretary")
    assert r.status_code == 204


def test_non_admin_forbidden(user_client, llm_model_factory):
    m = llm_model_factory()
    r = user_client.put(
        "/api/settings/admin/llm/slot-defaults/department/secretary",
        json={"model_id": m.id},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run (expect failure)**

- [ ] **Step 3: Implement router**

```python
# packages/server/src/openlia_server/routes/settings_llm_slots.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.session import get_db
from openlia_server.middleware.auth import require_admin
from openlia_server.services.slot_defaults import (
    InvalidSlotError,
    delete_slot_default,
    list_slot_defaults,
    set_slot_default,
)

router = APIRouter(
    prefix="/api/settings/admin/llm/slot-defaults",
    tags=["settings", "admin", "llm"],
    dependencies=[Depends(require_admin)],
)


class SlotDefaultIn(BaseModel):
    model_id: str


class SlotDefaultOut(BaseModel):
    slot_kind: str
    slot_id: str
    model_id: str


@router.get("")
def list_defaults(db: Session = Depends(get_db)) -> dict:
    rows = list_slot_defaults(db)
    return {
        "defaults": [
            SlotDefaultOut(slot_kind=r.slot_kind, slot_id=r.slot_id, model_id=r.model_id).model_dump()
            for r in rows
        ]
    }


@router.put("/{slot_kind}/{slot_id}")
def upsert_default(
    slot_kind: str, slot_id: str, body: SlotDefaultIn, db: Session = Depends(get_db)
) -> SlotDefaultOut:
    try:
        row = set_slot_default(db, slot_kind=slot_kind, slot_id=slot_id, model_id=body.model_id)
    except InvalidSlotError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return SlotDefaultOut(slot_kind=row.slot_kind, slot_id=row.slot_id, model_id=row.model_id)


@router.delete("/{slot_kind}/{slot_id}", status_code=204)
def remove_default(slot_kind: str, slot_id: str, db: Session = Depends(get_db)) -> None:
    try:
        delete_slot_default(db, slot_kind=slot_kind, slot_id=slot_id)
    except InvalidSlotError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
```

- [ ] **Step 4: Wire into `app.py`**

In `packages/server/src/openlia_server/app.py`, find the section that includes `settings.router` and add:

```python
from openlia_server.routes.settings_llm_slots import router as settings_llm_slots_router
app.include_router(settings_llm_slots_router)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest packages/server/tests/server/routes/test_settings_llm_slots.py -v
```

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings_llm_slots.py packages/server/src/openlia_server/app.py packages/server/tests/server/routes/test_settings_llm_slots.py
git commit -m "feat(routes): slot-defaults CRUD endpoints"
```

### Task 5.3: Delete `settings_llm_user.py` (per-tier user prefs)

- [ ] **Step 1: Check callers**

```bash
grep -rn "settings_llm_user\|UserLLMPreference\|/api/settings/me/llm" packages/server/src/ frontend/src/ | head
```

- [ ] **Step 2: Delete file and unregister router**

```bash
git rm packages/server/src/openlia_server/routes/settings_llm_user.py
```

In `app.py`, delete the `include_router` line for the user-LLM router.

- [ ] **Step 3: Run server tests**

```bash
uv run pytest packages/server/tests -k "llm_user or user_llm" -v
```

Delete any obsolete test files (e.g. `tests/server/routes/test_settings_llm_user.py`).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(routes): drop per-user tier-preference endpoints"
```

### Task 5.4: Drop tier fallback from `routes/department_model_pref.py` and `routes/chat_sessions.py`

- [ ] **Step 1: Find tier references**

```bash
grep -n "tier\|Tier" packages/server/src/openlia_server/routes/department_model_pref.py packages/server/src/openlia_server/routes/chat_sessions.py
```

- [ ] **Step 2: Edit each callsite to use the new resolver**

The resolver call pattern becomes `resolve(department_id=..., registry=..., user_id=..., model_id_override=...)`. No `tier_override` kwarg.

- [ ] **Step 3: Run tests for these routes**

```bash
uv run pytest packages/server/tests -k "department_model_pref or chat_sessions" -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/routes/department_model_pref.py packages/server/src/openlia_server/routes/chat_sessions.py
git commit -m "refactor(routes): drop tier fallback from per-dept pref and chat sessions"
```

### Task 5.5: Update `routes/setup.py` to consume new wizard payload

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`

- [ ] **Step 1: Find tier references**

```bash
grep -n "tier\|Tier\|get_enabled_default_tiers" packages/server/src/openlia_server/routes/setup.py
```

- [ ] **Step 2: Replace tier list shape**

Currently the wizard returns `tiers` via `get_enabled_default_tiers`. Replace the wizard payload contract:

- `/api/setup/state` no longer returns `required_tiers`. It returns `enabled_department_ids: list[str]` and `system_role_ids: list[str]`.
- `/api/setup/models` accepts the new `WizardModelsPayload` shape (from Task 4.5) and calls `save_wizard_models`.

- [ ] **Step 3: Run tests**

```bash
uv run pytest packages/server/tests/server/routes/test_setup.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py packages/server/tests/server/routes/test_setup.py
git commit -m "refactor(routes/setup): wizard returns dept+role ids, accepts slot defaults payload"
```

---

## Phase 6 — Frontend API client + types

### Task 6.1: Update `api/llm_admin.ts`

- [ ] **Step 1: Edit types**

In `frontend/src/api/llm_admin.ts`:

1. Remove the `Tier` type and every reference.
2. From `AdminModel`, remove `tier` and `is_tier_default` fields.
3. From `AdminModelInput`, remove `tier`, `is_tier_default`.
4. Keep all other types.

- [ ] **Step 2: Write a small typecheck-only test**

Frontend doesn't have runtime tests for types, but make sure `npm run tsc` (or `tsc --noEmit`) is clean.

```bash
cd frontend && npx tsc --noEmit
```

Expected: errors in many components that import `Tier` from this file. Each error will be fixed in subsequent tasks.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/llm_admin.ts
git commit -m "refactor(api): drop tier types from llm_admin client"
```

### Task 6.2: New `api/llm_slots.ts`

- [ ] **Step 1: Write the file**

```typescript
// frontend/src/api/llm_slots.ts
import { request } from './_request';

export type SlotKind = 'department' | 'system_role';

export interface SlotDefault {
  slot_kind: SlotKind;
  slot_id: string;
  model_id: string;
}

export const listSlotDefaults = () =>
  request<{ defaults: SlotDefault[] }>('/api/settings/admin/llm/slot-defaults');

export const setSlotDefault = (slot_kind: SlotKind, slot_id: string, model_id: string) =>
  request<SlotDefault>(`/api/settings/admin/llm/slot-defaults/${slot_kind}/${slot_id}`, {
    method: 'PUT',
    body: JSON.stringify({ model_id }),
  });

export const deleteSlotDefault = (slot_kind: SlotKind, slot_id: string) =>
  request<void>(`/api/settings/admin/llm/slot-defaults/${slot_kind}/${slot_id}`, {
    method: 'DELETE',
  });
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/llm_slots.ts
git commit -m "feat(api): llm_slots client for slot-defaults CRUD"
```

### Task 6.3: Strip tier from `api/settings.ts`

- [ ] **Step 1: Find tier usage**

```bash
grep -n "tier\|Tier" frontend/src/api/settings.ts
```

- [ ] **Step 2: Edit**

- Remove `Tier` type alias.
- Remove `getModelPreferences`, `putModelPreference`, `deleteModelPreference` (tier-keyed user prefs are gone).
- Remove `getModelsRoster` if it returns tier-grouped data. Replace with `getEnabledModels()` that returns a flat `RosterEntry[]` grouped by provider.
- Remove `getDepartmentDefaults` (replaced by `listSlotDefaults`).

- [ ] **Step 3: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Many components fail typecheck — that's expected; they're rewritten in Phase 7.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/settings.ts
git commit -m "refactor(api): drop tier-keyed endpoints from settings client"
```

---

## Phase 7 — Settings → Models page rewrite

### Task 7.1: `UserOverridesPanel` component (top section)

**Files:**
- Create: `frontend/src/components/settings/models/UserOverridesPanel.tsx`
- Create test: `frontend/src/components/settings/models/__tests__/UserOverridesPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/settings/models/__tests__/UserOverridesPanel.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { UserOverridesPanel } from '../UserOverridesPanel';

vi.mock('../../../../api/department-model-pref', () => ({
  getDepartmentModelPref: vi.fn().mockResolvedValue({ department_id: 'secretary', model_id: null, effective_model_id: 'M-default' }),
  setDepartmentModelPref: vi.fn().mockResolvedValue({}),
  clearDepartmentModelPref: vi.fn().mockResolvedValue({}),
}));

vi.mock('../../../../api/settings', () => ({
  getEnabledModels: vi.fn().mockResolvedValue([
    { id: 'M1', display_name: 'GPT', provider_id: 'P1', provider_kind: 'openai', is_enabled: true },
  ]),
}));

const DEPTS = ['secretary', 'equity_research'];

describe('UserOverridesPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists every department row', async () => {
    render(<UserOverridesPanel departments={DEPTS} />);
    expect(await screen.findByText(/Secretary/i)).toBeInTheDocument();
    expect(await screen.findByText(/Equity Research/i)).toBeInTheDocument();
  });

  it('changing the dropdown calls setDepartmentModelPref', async () => {
    const { setDepartmentModelPref } = await import('../../../../api/department-model-pref');
    render(<UserOverridesPanel departments={DEPTS} />);
    const select = await screen.findByLabelText(/Secretary model/i);
    fireEvent.change(select, { target: { value: 'M1' } });
    await waitFor(() => expect(setDepartmentModelPref).toHaveBeenCalledWith('secretary', 'M1'));
  });
});
```

- [ ] **Step 2: Run (expect failure)**

```bash
cd frontend && npx vitest run src/components/settings/models/__tests__/UserOverridesPanel.test.tsx
```

- [ ] **Step 3: Implement component**

```tsx
// frontend/src/components/settings/models/UserOverridesPanel.tsx
import { useEffect, useState } from 'react';
import { getEnabledModels, RosterEntry } from '../../../api/settings';
import {
  clearDepartmentModelPref,
  getDepartmentModelPref,
  setDepartmentModelPref,
} from '../../../api/department-model-pref';

interface Props {
  departments: string[];
}

interface Row {
  department_id: string;
  selected: string;
  effective: string | null;
}

function humanize(id: string): string {
  return id.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function UserOverridesPanel({ departments }: Props): JSX.Element {
  const [models, setModels] = useState<RosterEntry[]>([]);
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    Promise.all([
      getEnabledModels(),
      Promise.all(
        departments.map((d) =>
          getDepartmentModelPref(d).then((p) => ({
            department_id: d,
            selected: p.model_id ?? '',
            effective: p.effective_model_id,
          })),
        ),
      ),
    ]).then(([m, r]) => {
      setModels(m);
      setRows(r);
    });
  }, [departments]);

  const onChange = async (idx: number, value: string) => {
    const row = rows[idx];
    if (value) {
      await setDepartmentModelPref(row.department_id, value);
    } else {
      await clearDepartmentModelPref(row.department_id);
    }
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: value } : r)));
  };

  return (
    <section className="space-y-3">
      <header>
        <h2 className="text-lg font-semibold text-text-primary">Your defaults per department</h2>
        <p className="text-sm text-text-secondary">
          Override the model used when you run each department. Falls back to the server default if not set.
        </p>
      </header>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((row, idx) => (
            <tr key={row.department_id} className="border-b border-border-subtle">
              <td className="py-2 pr-2 text-text-primary">{humanize(row.department_id)}</td>
              <td className="py-2">
                <select
                  aria-label={`${humanize(row.department_id)} model`}
                  value={row.selected}
                  onChange={(e) => onChange(idx, e.target.value)}
                  className="w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-text-primary"
                >
                  <option value="">(Use server default)</option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name} ({m.provider_kind})
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run src/components/settings/models/__tests__/UserOverridesPanel.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/models/UserOverridesPanel.tsx frontend/src/components/settings/models/__tests__/UserOverridesPanel.test.tsx
git commit -m "feat(settings/models): UserOverridesPanel component"
```

### Task 7.2: `DepartmentChips` reusable chip multi-select

**Files:**
- Create: `frontend/src/components/settings/models/DepartmentChips.tsx`
- Create test: `frontend/src/components/settings/models/__tests__/DepartmentChips.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DepartmentChips } from '../DepartmentChips';

describe('DepartmentChips', () => {
  it('shows assigned departments as filled chips', () => {
    render(
      <DepartmentChips
        departments={['secretary', 'equity_research']}
        assigned={new Set(['secretary'])}
        onToggle={() => {}}
      />,
    );
    expect(screen.getByRole('button', { name: /Secretary/i })).toHaveAttribute('data-active', 'true');
    expect(screen.getByRole('button', { name: /Equity Research/i })).toHaveAttribute('data-active', 'false');
  });

  it('clicking a chip fires onToggle with the dept id', () => {
    const onToggle = vi.fn();
    render(<DepartmentChips departments={['secretary']} assigned={new Set()} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button', { name: /Secretary/i }));
    expect(onToggle).toHaveBeenCalledWith('secretary');
  });
});
```

- [ ] **Step 2: Implement**

```tsx
// frontend/src/components/settings/models/DepartmentChips.tsx
interface Props {
  departments: string[];
  assigned: Set<string>;
  onToggle: (deptId: string) => void;
  disabled?: boolean;
}

function humanize(id: string): string {
  return id.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function DepartmentChips({ departments, assigned, onToggle, disabled }: Props): JSX.Element {
  return (
    <div className="flex flex-wrap gap-1">
      {departments.map((d) => {
        const active = assigned.has(d);
        return (
          <button
            type="button"
            key={d}
            disabled={disabled}
            data-active={active}
            onClick={() => onToggle(d)}
            aria-label={`${humanize(d)}${active ? ' (default)' : ''}`}
            className={`rounded-full border px-2 py-0.5 text-xs ${
              active
                ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                : 'border-border-subtle text-text-secondary hover:bg-surface-hover'
            }`}
          >
            {humanize(d)}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: Run & commit**

```bash
cd frontend && npx vitest run src/components/settings/models/__tests__/DepartmentChips.test.tsx
git add frontend/src/components/settings/models/DepartmentChips.tsx frontend/src/components/settings/models/__tests__/DepartmentChips.test.tsx
git commit -m "feat(settings/models): DepartmentChips multi-select"
```

### Task 7.3: `ProviderCatalog` (middle section, admin CRUD inline)

**Files:**
- Create: `frontend/src/components/settings/models/ProviderCatalog.tsx`
- Create test: `frontend/src/components/settings/models/__tests__/ProviderCatalog.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ProviderCatalog } from '../ProviderCatalog';

vi.mock('../../../../api/llm_admin', () => ({
  listAdminProviders: vi.fn().mockResolvedValue([
    { id: 'P1', kind: 'openai', label: 'OpenAI', has_api_key: true, env_var_name: null, base_url: null, is_enabled: true },
  ]),
  listAdminModelsForProvider: vi.fn().mockResolvedValue([
    { id: 'M1', provider_id: 'P1', model_ref: 'gpt-x', display_name: 'GPT X', is_enabled: true, overrides: null },
  ]),
  createAdminProvider: vi.fn(),
  createAdminModel: vi.fn(),
  deleteAdminProvider: vi.fn(),
  deleteAdminModel: vi.fn(),
  updateAdminModel: vi.fn(),
  updateAdminProvider: vi.fn(),
  testAdminProviderConfig: vi.fn(),
}));

vi.mock('../../../../api/llm_slots', () => ({
  listSlotDefaults: vi.fn().mockResolvedValue({ defaults: [{ slot_kind: 'department', slot_id: 'secretary', model_id: 'M1' }] }),
  setSlotDefault: vi.fn(),
  deleteSlotDefault: vi.fn(),
}));

const DEPTS = ['secretary', 'equity_research'];

describe('ProviderCatalog', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders providers and models read-only for non-admin', async () => {
    render(<ProviderCatalog departments={DEPTS} isAdmin={false} />);
    expect(await screen.findByText('OpenAI')).toBeInTheDocument();
    expect(await screen.findByText(/GPT X/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Add provider/i })).not.toBeInTheDocument();
  });

  it('admin sees Add provider button and chips reflect slot defaults', async () => {
    render(<ProviderCatalog departments={DEPTS} isAdmin={true} />);
    expect(await screen.findByRole('button', { name: /Add provider/i })).toBeInTheDocument();
    const chip = await screen.findByRole('button', { name: /Secretary \(default\)/i });
    expect(chip).toHaveAttribute('data-active', 'true');
  });

  it('admin clicking a chip toggles the slot default', async () => {
    const { setSlotDefault, deleteSlotDefault } = await import('../../../../api/llm_slots');
    render(<ProviderCatalog departments={DEPTS} isAdmin={true} />);
    const erChip = await screen.findByRole('button', { name: /Equity Research/i });
    fireEvent.click(erChip);
    await waitFor(() =>
      expect(setSlotDefault).toHaveBeenCalledWith('department', 'equity_research', 'M1'),
    );
    const secChip = await screen.findByRole('button', { name: /Secretary \(default\)/i });
    fireEvent.click(secChip);
    await waitFor(() =>
      expect(deleteSlotDefault).toHaveBeenCalledWith('department', 'secretary'),
    );
  });
});
```

- [ ] **Step 2: Run (expect failure)**

- [ ] **Step 3: Implement**

The component is large; treat the existing `ModelsAdminPanel.tsx` (~540 lines) as the starting layout for the admin form, but:

- Group models by provider card (same as before).
- Remove every reference to `tier` and `is_tier_default`.
- For each model row, render a `<DepartmentChips departments={departments} assigned={assignedFor(modelId)} onToggle={(dept) => toggleSlot(modelId, dept)} disabled={!isAdmin} />` instead of the tier column.
- For non-admin, hide the "Add provider" / "Add model" forms and the per-row Edit/Delete buttons; just render the table.
- Maintain a `slotDefaults` state from `listSlotDefaults()` and a `slotsByModelId: Map<string, Set<string>>` derived from it.

Top of file:

```tsx
import { useEffect, useMemo, useState, FormEvent } from 'react';
import {
  AdminModel,
  AdminProvider,
  createAdminProvider,
  deleteAdminProvider,
  listAdminProviders,
  listAdminModelsForProvider,
  /* ... etc ... */
} from '../../../api/llm_admin';
import { listSlotDefaults, setSlotDefault, deleteSlotDefault, SlotDefault } from '../../../api/llm_slots';
import { DepartmentChips } from './DepartmentChips';

interface Props {
  departments: string[];
  isAdmin: boolean;
}

export function ProviderCatalog({ departments, isAdmin }: Props): JSX.Element {
  // load providers + models + slot defaults; derive slotsByModelId
  // render header → optional "Add provider" form → provider cards
  // each model row has DepartmentChips wired to setSlotDefault/deleteSlotDefault
}
```

Implementation specifics (must match what the test expects):

```tsx
const toggleSlot = async (modelId: string, deptId: string) => {
  const current = slotsByModelId.get(modelId) ?? new Set<string>();
  if (current.has(deptId)) {
    await deleteSlotDefault('department', deptId);
  } else {
    await setSlotDefault('department', deptId, modelId);
  }
  // refresh slot defaults
  const { defaults } = await listSlotDefaults();
  setSlotDefaults(defaults);
};
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run src/components/settings/models/__tests__/ProviderCatalog.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/models/ProviderCatalog.tsx frontend/src/components/settings/models/__tests__/ProviderCatalog.test.tsx
git commit -m "feat(settings/models): ProviderCatalog with inline admin CRUD + dept chips"
```

### Task 7.4: `SystemRolesPanel` (bottom section, admin-only)

**Files:**
- Create: `frontend/src/components/settings/models/SystemRolesPanel.tsx`
- Create test: `frontend/src/components/settings/models/__tests__/SystemRolesPanel.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SystemRolesPanel } from '../SystemRolesPanel';

vi.mock('../../../../api/llm_slots', () => ({
  listSlotDefaults: vi.fn().mockResolvedValue({ defaults: [
    { slot_kind: 'system_role', slot_id: 'ai_review', model_id: 'M1' },
  ]}),
  setSlotDefault: vi.fn(),
}));

vi.mock('../../../../api/settings', () => ({
  getEnabledModels: vi.fn().mockResolvedValue([
    { id: 'M1', display_name: 'GPT X', provider_kind: 'openai' },
    { id: 'M2', display_name: 'Claude', provider_kind: 'anthropic' },
  ]),
}));

describe('SystemRolesPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists all four system roles with current assignment preselected', async () => {
    render(<SystemRolesPanel />);
    expect(await screen.findByText(/Wizard AI review/i)).toBeInTheDocument();
    expect(screen.getByText(/Connector agentic resolver/i)).toBeInTheDocument();
    expect(screen.getByText(/Graph memory extraction/i)).toBeInTheDocument();
    expect(screen.getByText(/Graph memory summarization/i)).toBeInTheDocument();
    const sel = await screen.findByLabelText(/Wizard AI review model/i);
    expect((sel as HTMLSelectElement).value).toBe('M1');
  });

  it('changing dropdown calls setSlotDefault with system_role', async () => {
    const { setSlotDefault } = await import('../../../../api/llm_slots');
    render(<SystemRolesPanel />);
    const sel = await screen.findByLabelText(/Graph memory extraction model/i);
    fireEvent.change(sel, { target: { value: 'M2' } });
    await waitFor(() => expect(setSlotDefault).toHaveBeenCalledWith('system_role', 'graph_extraction', 'M2'));
  });
});
```

- [ ] **Step 2: Implement**

```tsx
// frontend/src/components/settings/models/SystemRolesPanel.tsx
import { useEffect, useState } from 'react';
import { getEnabledModels, RosterEntry } from '../../../api/settings';
import { listSlotDefaults, setSlotDefault, SlotDefault } from '../../../api/llm_slots';

const SYSTEM_ROLES: { id: string; label: string }[] = [
  { id: 'ai_review', label: 'Wizard AI review' },
  { id: 'connector_agentic_resolver', label: 'Connector agentic resolver' },
  { id: 'graph_extraction', label: 'Graph memory extraction' },
  { id: 'graph_summarization', label: 'Graph memory summarization' },
];

export function SystemRolesPanel(): JSX.Element {
  const [models, setModels] = useState<RosterEntry[]>([]);
  const [assignments, setAssignments] = useState<Record<string, string>>({});

  useEffect(() => {
    Promise.all([getEnabledModels(), listSlotDefaults()]).then(([m, s]) => {
      setModels(m);
      const out: Record<string, string> = {};
      for (const d of s.defaults) {
        if (d.slot_kind === 'system_role') out[d.slot_id] = d.model_id;
      }
      setAssignments(out);
    });
  }, []);

  const onChange = async (roleId: string, modelId: string) => {
    await setSlotDefault('system_role', roleId, modelId);
    setAssignments((prev) => ({ ...prev, [roleId]: modelId }));
  };

  return (
    <section className="space-y-3">
      <header>
        <h2 className="text-lg font-semibold text-text-primary">System roles</h2>
        <p className="text-sm text-text-secondary">
          Pick a model for each internal job (wizard review, graph memory, etc.). No user override.
        </p>
      </header>
      <table className="w-full text-sm">
        <tbody>
          {SYSTEM_ROLES.map(({ id, label }) => (
            <tr key={id} className="border-b border-border-subtle">
              <td className="py-2 pr-2 text-text-primary">{label}</td>
              <td className="py-2">
                <select
                  aria-label={`${label} model`}
                  value={assignments[id] ?? ''}
                  onChange={(e) => onChange(id, e.target.value)}
                  className="w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-text-primary"
                >
                  <option value="">(Unassigned)</option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name} ({m.provider_kind})
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

- [ ] **Step 3: Run & commit**

```bash
cd frontend && npx vitest run src/components/settings/models/__tests__/SystemRolesPanel.test.tsx
git add frontend/src/components/settings/models/SystemRolesPanel.tsx frontend/src/components/settings/models/__tests__/SystemRolesPanel.test.tsx
git commit -m "feat(settings/models): SystemRolesPanel"
```

### Task 7.5: Rewrite `ModelsSection.tsx` to compose the three panels

**Files:**
- Modify: `frontend/src/components/settings/sections/ModelsSection.tsx`
- Rewrite: `frontend/src/components/settings/sections/ModelsSection.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ModelsSection } from '../ModelsSection';

vi.mock('../../../api/department-model-pref', () => ({
  getDepartmentModelPref: vi.fn().mockResolvedValue({ department_id: '', model_id: null, effective_model_id: null }),
  setDepartmentModelPref: vi.fn(),
  clearDepartmentModelPref: vi.fn(),
}));
vi.mock('../../../api/settings', () => ({
  getEnabledModels: vi.fn().mockResolvedValue([]),
  getRegisteredDepartmentIds: vi.fn().mockResolvedValue(['secretary', 'equity_research']),
}));
vi.mock('../../../api/llm_admin', () => ({
  listAdminProviders: vi.fn().mockResolvedValue([]),
  listAdminModelsForProvider: vi.fn().mockResolvedValue([]),
}));
vi.mock('../../../api/llm_slots', () => ({
  listSlotDefaults: vi.fn().mockResolvedValue({ defaults: [] }),
}));

describe('ModelsSection', () => {
  it('renders user overrides → catalog → system roles in order for admin', async () => {
    render(<ModelsSection userRole="admin" />);
    await waitFor(() => screen.getByText(/Your defaults per department/i));
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/Your defaults per department/i),
        expect.stringMatching(/Providers and models/i),
        expect.stringMatching(/System roles/i),
      ]),
    );
  });

  it('hides system roles for non-admin', async () => {
    render(<ModelsSection userRole="user" />);
    await waitFor(() => screen.getByText(/Your defaults per department/i));
    expect(screen.queryByText(/System roles/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement**

```tsx
// frontend/src/components/settings/sections/ModelsSection.tsx
import { useEffect, useState } from 'react';
import { getRegisteredDepartmentIds } from '../../../api/settings';
import { UserOverridesPanel } from '../models/UserOverridesPanel';
import { ProviderCatalog } from '../models/ProviderCatalog';
import { SystemRolesPanel } from '../models/SystemRolesPanel';

interface Props {
  userRole: 'admin' | 'user';
}

export function ModelsSection({ userRole }: Props): JSX.Element {
  const [departments, setDepartments] = useState<string[]>([]);
  useEffect(() => {
    getRegisteredDepartmentIds().then(setDepartments);
  }, []);

  return (
    <div className="max-w-4xl space-y-8">
      <header>
        <h1 className="text-xl font-semibold text-text-primary">Models</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Manage how each department and internal job picks an LLM.
        </p>
      </header>
      <UserOverridesPanel departments={departments} />
      <section className="space-y-3">
        <header>
          <h2 className="text-lg font-semibold text-text-primary">Providers and models</h2>
          <p className="text-sm text-text-secondary">
            {userRole === 'admin'
              ? 'Register providers, add models, and mark which department each model is default for.'
              : 'View the catalog of available models.'}
          </p>
        </header>
        <ProviderCatalog departments={departments} isAdmin={userRole === 'admin'} />
      </section>
      {userRole === 'admin' ? <SystemRolesPanel /> : null}
    </div>
  );
}
```

You'll need to add `getRegisteredDepartmentIds()` to `frontend/src/api/settings.ts` — it hits a new `/api/settings/departments` endpoint that returns `string[]`. Add the endpoint to a small server route too (in `routes/settings.py`).

- [ ] **Step 3: Run tests**

```bash
cd frontend && npx vitest run src/components/settings/sections/__tests__/ModelsSection.test.tsx
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/settings/sections/ModelsSection.tsx frontend/src/components/settings/sections/__tests__/ModelsSection.test.tsx frontend/src/api/settings.ts packages/server/src/openlia_server/routes/settings.py packages/server/tests/server/routes/test_settings.py
git commit -m "feat(settings/models): compose UserOverrides + ProviderCatalog + SystemRoles"
```

### Task 7.6: Delete `ModelsAdminPanel` from `/settings/admin`

- [ ] **Step 1: Edit AdminSection.tsx**

In `frontend/src/components/settings/sections/AdminSection.tsx`, remove the `ModelsAdminPanel` import and its render block. Keep `ConnectorsAdminPanel` (or whatever else is there).

- [ ] **Step 2: Delete files**

```bash
git rm frontend/src/components/settings/admin/ModelsAdminPanel.tsx
git rm frontend/src/components/settings/admin/__tests__/ModelsAdminPanel.test.tsx
```

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run
```

Fix any imports.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(settings/admin): drop ModelsAdminPanel (moved to /settings/models)"
```

---

## Phase 8 — In-context ModelPickers

### Task 8.1: Drop tier filter from `components/chat/ModelPicker.tsx`

**Files:**
- Modify: `frontend/src/components/chat/ModelPicker.tsx`
- Modify: any test file that mocks tier-grouped roster

- [ ] **Step 1: Inspect**

```bash
grep -n "tier\|Tier" frontend/src/components/chat/ModelPicker.tsx
```

- [ ] **Step 2: Rewrite the dropdown**

Replace the tier-filtered roster fetch with `getEnabledModels()` (returns a flat `RosterEntry[]`). Group `<optgroup>` by `provider_kind` so the dropdown reads naturally. Drop any `tier` prop.

- [ ] **Step 3: Run tests and fix**

```bash
cd frontend && npx vitest run src/components/chat/__tests__/
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chat/
git commit -m "refactor(chat): ModelPicker lists all enabled models grouped by provider"
```

### Task 8.2: Same for `components/morning-briefing/ModelPicker.tsx`

Repeat Task 8.1 pattern; commit separately.

```bash
git add frontend/src/components/morning-briefing/
git commit -m "refactor(morning-briefing): drop tier filter from ModelPicker"
```

### Task 8.3: ReportSettingsModal and any other consumers

```bash
grep -rn "tier\|Tier" frontend/src/components/earnings-update/ frontend/src/components/equity-research/ frontend/src/components/secretary/
```

For each match, drop the prop / filter. Commit each component cluster separately.

---

## Phase 9 — Setup Wizard rewrite

### Task 9.1: `RegisterModelsScreen`

**Files:**
- Create: `frontend/src/setup/steps/RegisterModelsScreen.tsx`
- Create test: `frontend/src/setup/steps/__tests__/RegisterModelsScreen.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RegisterModelsScreen } from '../RegisterModelsScreen';

const KEYS = [
  { id: 'K1', provider_kind: 'openai', api_key: 'k', base_url: null, label: 'OpenAI' },
];

describe('RegisterModelsScreen', () => {
  it('lets the user add a model under a key', () => {
    const onChange = vi.fn();
    render(<RegisterModelsScreen keys={KEYS} entries={[]} onChange={onChange} onBack={() => {}} onNext={() => {}} totalSteps={5} />);
    fireEvent.click(screen.getByRole('button', { name: /Add model/i }));
    fireEvent.change(screen.getByLabelText(/model id/i), { target: { value: 'gpt-x' } });
    fireEvent.change(screen.getByLabelText(/display name/i), { target: { value: 'GPT X' } });
    expect(onChange).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Implement**

A simple list-builder UI: for each `key`, show `[+ Add model]`; each row has inputs for `model_ref` and `display_name`. State is `entries: { key_id, model_ref, display_name }[]`. No tier picker.

- [ ] **Step 3: Run, commit**

```bash
git add frontend/src/setup/steps/RegisterModelsScreen.tsx frontend/src/setup/steps/__tests__/RegisterModelsScreen.test.tsx
git commit -m "feat(wizard): RegisterModelsScreen"
```

### Task 9.2: `AssignDefaultsScreen`

**Files:**
- Create: `frontend/src/setup/steps/AssignDefaultsScreen.tsx`
- Create test: `frontend/src/setup/steps/__tests__/AssignDefaultsScreen.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// AssignDefaultsScreen test:
// - lists every enabled department row + every system role row
// - each row is a <select> over the registered models from the previous screen
// - onSubmit yields a payload { department_defaults, system_role_defaults }
```

- [ ] **Step 2: Implement** with a simple grid: departments on top, system roles below; each row a `<select>` over registered models. On submit, invoke `onNext({ department_defaults, system_role_defaults })`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/setup/steps/AssignDefaultsScreen.tsx frontend/src/setup/steps/__tests__/AssignDefaultsScreen.test.tsx
git commit -m "feat(wizard): AssignDefaultsScreen"
```

### Task 9.3: Rewrite `ModelsStep.tsx` as a 3-screen state machine

**Files:**
- Modify: `frontend/src/setup/steps/ModelsStep.tsx`
- Delete: `frontend/src/setup/steps/TiersScreen.tsx`

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/setup/steps/__tests__/ModelsStep.test.tsx
// it('starts on keys → register-models → assign-defaults', ...)
// it('saves payload { models, department_defaults, system_role_defaults } via saveModels')
```

- [ ] **Step 2: Implement**

```tsx
type Screen = 'keys' | 'register' | 'assign';

interface PersistedState {
  screen: Screen;
  keys: ApiKey[];
  entries: ModelEntry[];
  department_defaults: Record<string, string>;
  system_role_defaults: Record<string, string>;
}
```

Wire: `keys` screen → `register` screen → `assign` screen → on submit call `saveModels({ models, department_defaults, system_role_defaults })`. Delete `TiersScreen.tsx` and its test.

- [ ] **Step 3: Update `api/setup.ts`**

Change the `saveModels` signature to match the new payload shape.

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run src/setup/
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/ frontend/src/api/setup.ts
git rm frontend/src/setup/steps/TiersScreen.tsx
git commit -m "feat(wizard): 3-screen Models step (keys → register → assign defaults)"
```

---

## Phase 10 — Cleanup, lint, full test sweep

### Task 10.1: Delete dead files

```bash
git rm packages/core/src/openlia/llm/model_defaults.py
git rm packages/core/src/openlia/llm/department_defaults.py
```

Then `grep -rn "model_defaults\|department_defaults" packages/ frontend/` and fix any lingering imports.

```bash
uv run pytest -q
git add -A
git commit -m "chore(llm): delete dead tier-default modules"
```

### Task 10.2: Lint everything

```bash
uv run ruff check --fix .
uv run ruff format .
cd frontend && npx tsc --noEmit && npx eslint . --fix
```

Fix any remaining errors.

```bash
git add -A
git commit -m "chore: ruff + tsc + eslint clean"
```

### Task 10.3: Full test sweep

```bash
uv run pytest -q
cd frontend && npm test -- --run
```

Both must be fully green. Fix any straggler.

```bash
git add -A
git commit -m "test: full suite green after tier removal"
```

### Task 10.4: Open PR

```bash
git push -u origin feat/settings-models-remake
gh pr create --title "feat(settings/models): redesign + remove tier system" --body "$(cat <<'EOF'
## Summary
- Remove the 3-tier (thinking/everyday/quick) LLM resolution system.
- New `llm_slot_defaults` table maps (department | system_role) → model.
- Redesigned `/settings/models` page: User overrides → Provider catalog (admin CRUD inline) → System roles (admin-only).
- Wizard ModelsStep rewritten as keys → register models → assign defaults.

## Test plan
- [ ] Run full pytest suite green
- [ ] Run full vitest suite green
- [ ] Browser smoke: complete setup wizard from scratch, register at least one model, assign defaults for every department + system role
- [ ] Browser smoke: admin can add/edit/delete a model from `/settings/models` and toggle department chips
- [ ] Browser smoke: non-admin sees catalog read-only and can change per-department override
- [ ] Browser smoke: run an Equity Research report, a Morning Briefing, and a Secretary chat — each uses the assigned model
- [ ] Browser smoke: graph extraction scheduler runs and uses the `graph_extraction` system role model
EOF
)"
```

---

## Self-review

**Spec coverage check (Q1–Q14):**

- Q1 (Mixed audience): Tasks 7.3 (`ProviderCatalog` isAdmin gating), 7.4 (SystemRoles admin-only), 7.5 (Section composes user-visible vs admin-visible).
- Q2 (By Provider grouping): Task 7.3.
- Q3 (Tiers fully removed): Phases 2–4, 6–9; Task 10.1 (delete dead tier modules).
- Q4 (Schema rip): Task 2.1 (migration), 2.2 (ORM), 5.3 (delete user-LLM router).
- Q5 (Dept default on model row): Task 7.2 (chips), 7.3 (toggleSlot wiring).
- Q6 (Split user-override vs system-role): Tasks 4.1 service, 7.1 vs 7.4.
- Q7 (All on `/settings/models`): Task 7.5 + 7.6.
- Q8 (Non-admin view): Task 7.1 (UserOverridesPanel) + 7.3 (read-only branch).
- Q9 (Vertical order): Task 7.5.
- Q10 (Wizard 3-screen): Tasks 9.1–9.3.
- Q11 (System role list): Task 1.1 (registry).
- Q12 (Migration without backfill): Task 2.1.
- Q13 (Resolver chain): Task 3.2.
- Q14 (Picker shows all enabled): Phase 8.

**Placeholder scan:** None left except for Task 9.2's intentionally lighter test outline — both setup-step tests get fleshed out from the patterns in 9.1.

**Type consistency:** `ResolvedModel` no longer carries `tier`; checked across 3.2 (resolver), 3.3 (runtime), 4.2 (registry). `RosterEntry` in `api/settings.ts` no longer has `tier`; checked across 7.1, 7.4, 8.x. Slot kind discriminator `'department' | 'system_role'` used uniformly across 4.1 service, 5.2 routes, 6.2 client, 7.x components.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-12-settings-models-remake.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — I execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Which approach?
