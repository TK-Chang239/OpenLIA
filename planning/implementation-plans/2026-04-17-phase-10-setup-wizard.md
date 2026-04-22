# Phase 10 — Setup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **2026-04-21 rewrite (REM-P0-004 / REM-P1-006 — read first):**
> - **Task 1 is already shipped.** The `wizard_state` reshape (`current_step` String, `completed_steps` JSON array, `active_session_token` String(64) nullable) landed as migration `5d41c9a7e812` on the current branch, together with the model change and the `openlia wizard reset` CLI rewrite. Executors must **not** author another migration — verify, run the test suite, and proceed to Task 2.
> - **No `get_db_session` / `get_db` helper exists.** Every snippet below that shows `from openlia_server.db.session import get_db_session` or `db: Session = Depends(get_db_session)` is stale. Replace with the factory pattern: inside `build_setup_router(...)`, bind `session_dep = make_session_dependency(db_session_factory)` (from `openlia_server.db.deps`) and use `db: Session = Depends(session_dep)` on each route handler. The middleware-style `require_wizard_active` / `require_wizard_session` dependencies accept the same `session_dep` from the factory's closure; do not import a bare helper at module scope.
> - **Routers are factory functions.** `build_setup_router(*, db_session_factory, mode, is_loopback_request)` — not a zero-arg function. `db_session_factory: Callable[[], Session]`, `mode: Literal["personal", "company"]`, `is_loopback_request: Callable[[Request], bool]` (used by the personal-mode loopback gate — Design Rule 3). Mount from `app.py` with `app.include_router(build_setup_router(db_session_factory=factory, mode=mode, is_loopback_request=is_loopback))`. See `routes/notifications.py` / `routes/jobs.py` for the canonical template.
> - **Password hashing.** Import from `openlia_server.services.auth.passwords` (`hash_password`). There is no `openlia_server.security.passwords` module and no `argon2_hash` symbol. `create_user` already hashes internally — call `create_user(db, email=..., password=..., display_name=..., is_admin=...)` rather than hashing manually.
> - **Loopback gate (Design Rule 3).** Personal-mode non-loopback clients get `403`. The gate runs as a FastAPI dependency on every `/setup/*` write route (not `GET /setup/status`). The factory builds `require_loopback_if_personal(request: Request)` from the closure's `mode` and `is_loopback_request(request)`; on mismatch raise `HTTPException(403, detail={"code": "loopback_only", ...})`.
> - **Wizard is pre-auth, unaffected by must-change-password.** Setup routes never wire `build_require_auth` / `build_require_admin`. The Plan 11 must-change-password gate must explicitly exempt `/setup/*`.
> - **UUID string IDs.** `User.id`, `SignupInvite.id`, `review_id`, etc. are `String(36)`. Every DTO and path param is `str`; every comparison / insert uses `uuid.uuid4().hex`.
>
> **Audit 2026-04-20 normalizations (apply before executing this plan):**
> - Follow the README "Current backend contract" block for every import. Specifically: `User` is in `openlia_server.db.models.auth` (not `.user`/`.users`); `LLMModel` is in `openlia_server.db.models.config` (not `.llm`); password hashing is `openlia_server.services.auth.passwords.hash_password` (not `argon2_hash` and not `openlia_server.security.passwords`); there is no `get_db_session`/`get_db`/`current_user`/`require_user` — use the router-factory `build_require_auth(...)` pattern and accept `db_session_factory` in the router factory.
> - All IDs are UUID strings (`String(36)`). Wizard DTOs, path params, and review IDs must be `str`.
> - `services/llm_providers.py` does **not** export `test_provider`, `clear_all_providers`, `add_model`, or `list_data_provider_rows`. Rewrite every call site against the shipped surface: `create_provider`, `get_provider`, `list_providers`, `update_provider`, `delete_provider`, `create_model`, `list_models_for_provider`, `set_user_preference`. If wizard flow genuinely needs a helper that doesn't exist, add it as a typed service helper in the Task that first uses it — do not assume it's already there.
> - `wizard_state` shape (Task 1): `current_step: String` (named step id like `"mode"`, `"account"`, `"models"`, `"data_providers"`, `"policy"`, `"review"`, `"done"`), `completed_steps: JSON[]`, `active_session_token: String(64) nullable`. Add a Task to also patch `openlia wizard reset` in `cli.py` to write this shape.
> - `config_store["wizard.completed"]` is seeded by bootstrap as a Python `bool`. Readers must type-guard: `isinstance(v, bool) ? v : (v or "").lower() == "true"`. Never call `.lower()` on the raw value directly.
> - `must_change_password` is enforced by Plan 11 on non-password routes; the wizard runs pre-auth and is unaffected — document this explicitly so the gate isn't accidentally applied to `/setup/*`.

**Goal:** Ship the first-run Setup Wizard — the resumable, DB-backed, mode-aware flow (5 steps personal / 6 steps company) that collects deployment mode, identity/admin account, three LLM tiers, data providers, access-control policy, and a Quick-tier AI review mapping providers to department requirements — before routing the user into `/` (personal) or `/login` (company).

**Architecture:**

- **Backend (`packages/server/`).** Fifteen `/setup/*` endpoints layered on existing services: Plan 2's `create_user` / `argon2_hash`, Plan 3's data-provider service, Plan 4's LLM provider service + `resolve()` + `DEPARTMENT_DEFAULT_TIERS`, and Plan 5's LLM adapters for the AI review call. A single `wizard_state` row (from Plan 1A) carries `current_step`, `completed_steps`, and opaque `step_data` JSON; a `config_store` row (`wizard.completed`) is the terminal flag. A `require_wizard_active` dependency returns `410 Gone` after completion. A wizard-session cookie (`openlia_wizard_session`, opaque 32-byte token) enforces "only one wizard session at a time" via a `wizard_state.active_session_token` column.
- **AI review.** Run as a background task (`asyncio.create_task`) keyed by `review_id` (UUID) with an in-memory dict state. The review calls the resolved Quick-tier LLM with a structured prompt enumerating each department's basic + advanced requirements and asking for a confidence-scored provider-to-requirement mapping. Output is persisted as `data_provider_requirement_mapping` rows (from Plan 3).
- **Frontend (`frontend/src/`).** A `/setup/*` route group gated by `GET /setup/status`; a `WizardContext` that mirrors server state and drives step transitions; a `WizardShell` chrome (card, header, progress bar, footer); six step components that call typed `api/setup.ts` methods. Reuses Plan 8's design tokens + primitives and Plan 9's `Banner` / `FormField` / `PasswordInput` / `PasswordStrengthMeter`. The wizard bypasses `AuthContext` entirely — it runs pre-auth in both modes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2, httpx (async), APScheduler (review task), asyncio; React 18, TypeScript strict, react-router-dom v6, Tailwind v3, lucide-react, vitest + @testing-library/react.

**Source specs:** `planning/specs/pages/SetupWizardSpec.md`; cross-reference `planning/specs/systems/llm-provider-design.md`, `planning/specs/systems/data-provider-design.md`, `planning/specs/systems/database-design.md`.

**Depends on:**

- Plan 1A (tables `wizard_state`, `config_store`, `signup_policy`, `users`, `llm_providers`, `llm_models`, `data_providers`, `data_provider_requirement_mapping`, `web_search_providers`).
- Plan 2 (`services.auth.passwords.hash_password`, `services.auth.users.create_user`, session helpers — wizard creates first admin user).
- Plan 3 (data-provider service + EODHD adapter + `auto_map` routine).
- Plan 4 (LLM provider service + `resolve()` + `DEPARTMENT_DEFAULT_TIERS` + `SHIPPED_TIER_DEFAULTS`).
- Plan 5 (LLM runtime — adapter `generate()` used by AI review).
- Plan 8 (frontend shell, design tokens, router, `api/client.ts`).
- Plan 9 (`Banner`, `FormField`, `PasswordInput`, `PasswordStrengthMeter`, `AuthLayout` shell).

**Unblocks:**

- Plan 11 (Settings page — reuses the same provider/model forms post-setup).
- First-run end-to-end boot in both personal and company modes.

**Out of scope (explicitly deferred):**

- Provider discovery from a remote registry (spec non-goal).
- Wizard-authored `.env` file generation (spec non-goal).
- OAuth for MCP providers (spec non-goal).
- Localization (English only; see memory).
- Multi-admin invite flow inside wizard — Settings-only per spec.
- Password reset / forgot password during wizard — Plan 9 handles post-completion.
- Provider discovery / catalog updates from remote — shipped catalog only.
- Estimated cost display on Step 3 (open question in spec — deferred).
- Switching modes post-completion (documented in ops docs, not wizard).

---

## File Structure

### New backend files

```
packages/server/src/openlia_server/
├── services/
│   └── wizard.py                       # WizardService — status, token, mode, identity, access_control, finish
├── routes/
│   └── setup.py                        # 15 /setup/* endpoints
├── ai_review/
│   ├── __init__.py
│   ├── runner.py                       # run_review(review_id, db, llm_factory) — orchestrates the Quick-tier call
│   ├── prompt.py                       # build_review_prompt(departments, providers) -> str
│   ├── schema.py                       # ReviewResult, DepartmentReadiness, ReadinessState (enum)
│   └── store.py                        # in-memory review-state dict (keyed by review_id)
└── middleware/
    └── wizard_gate.py                  # require_wizard_active / reject_after_completion
```

### New backend tests

```
packages/server/tests/
├── test_services/
│   ├── test_wizard.py
│   └── test_ai_review.py
└── test_routes/
    └── test_setup_routes.py
```

### New frontend files

```
frontend/src/
├── api/
│   └── setup.ts                        # typed /setup/* client
├── setup/
│   ├── WizardContext.tsx               # provider + useWizard hook
│   ├── WizardShell.tsx                 # chrome + step slot
│   ├── WizardFooter.tsx                # Back / Next buttons + loading
│   ├── WizardProgress.tsx              # progress bar
│   ├── ReadOnlyBadge.tsx               # "from environment" badge component
│   └── steps/
│       ├── ModeStep.tsx                # Step 1
│       ├── IdentityStep.tsx            # Step 2a (personal)
│       ├── AdminAccountStep.tsx        # Step 2b (company)
│       ├── ModelsStep.tsx              # Step 3
│       ├── TierSlotCard.tsx            # sub-component used by ModelsStep
│       ├── ProvidersStep.tsx           # Step 4 (tabs + list + add form)
│       ├── ProviderRow.tsx             # list row
│       ├── AddProviderForm.tsx         # 3-mode takeover form
│       ├── MCPInfoCard.tsx             # info card for MCP mode
│       ├── AccessControlStep.tsx       # Step 5 (company only)
│       └── ReviewStep.tsx              # Step 6
├── pages/
│   └── SetupPage.tsx                   # route entry — picks step from status
└── index.css                           # (modified to add `--color-surface-info` token)
```

### New frontend tests

```
frontend/src/setup/
├── WizardContext.test.tsx
├── WizardShell.test.tsx
└── steps/
    ├── ModeStep.test.tsx
    ├── IdentityStep.test.tsx
    ├── AdminAccountStep.test.tsx
    ├── ModelsStep.test.tsx
    ├── ProvidersStep.test.tsx
    ├── AccessControlStep.test.tsx
    └── ReviewStep.test.tsx
```

### Modified files

```
packages/server/src/openlia_server/
├── app.py                              # MODIFY — wire setup router + wizard_gate middleware
└── db/models/infrastructure.py         # MODIFY — add `active_session_token` col to wizard_state (migration)

frontend/src/
├── router.tsx                          # MODIFY — add /setup/* route group + SetupRedirect gate
└── App.tsx                             # MODIFY — render SetupRedirect before AuthProvider when wizard incomplete

planning/implementation-plans/README.md # MODIFY — flip Plan 10 row to Draft
planning/projectStructure.md            # MODIFY — reflect setup/ directories
```

---

## Design Rules

1. **DB is canonical.** Env vars override at read time; the wizard never writes `.env`. `env_overrides` field on `/setup/status` lists which slots are env-bound.
2. **Single active wizard session.** `wizard_state.active_session_token` gates all writes; `POST /setup/takeover` replaces it. All non-`status` routes require the cookie to match.
3. **Wizard is pre-auth.** No `require_auth` on `/setup/*`. In personal mode, a non-loopback client IP is rejected with `403`.
4. **`410 Gone` after completion.** A `wizard_gate` middleware short-circuits any `/setup/*` path when `config_store['wizard.completed'] == true`, except `GET /setup/status` (which must always respond).
5. **Required-tier gate.** `POST /setup/models` computes the union of `DEPARTMENT_DEFAULT_TIERS` across the shipped department list, and rejects with `422` if any required tier has zero green models.
6. **Provider save = test first.** `POST /setup/providers` runs the category's `test()` via the adapter before inserting. On failure the row is not created.
7. **AI review is background.** `POST /setup/review/run` returns a `review_id` immediately; the background task updates an in-memory dict. `GET /setup/review/{id}` polls.
8. **Finish is atomic.** `POST /setup/finish` writes `wizard.completed = true` + clears `wizard_state` in one transaction. Returns redirect target based on resolved mode.
9. **Step transitions are server-validated.** Each step save updates `current_step` + `completed_steps`; client cannot skip ahead.
10. **TDD every task.** Failing test → verify fail → implementation → verify pass → commit. No batching.
11. **No placeholders.** Every code block is complete and runnable.
12. **Design tokens only.** Tailwind classes use `[--color-*]` tokens from Plan 8; no literal hex/named Tailwind colors.
13. **One commit per task.** Conventional prefixes: `feat(wizard)`, `feat(setup)`, `test(wizard)`, `refactor(wizard)`, `docs(plan)`.
14. **No untyped `any` on frontend.** Responses flow through typed interfaces in `api/setup.ts`.
15. **Wizard bypasses AuthContext.** Frontend setup routes render outside the `AuthProvider` so no `/auth/session` probe runs during wizard.

---

## Task 1: Reshape `wizard_state` — **already shipped (REM-P1-006)**

**Status:** Shipped on this branch. Do not re-run.

**What shipped:**
- Model update in `packages/server/src/openlia_server/db/models/infrastructure.py`: `current_step: Mapped[str] = mapped_column(String(32), nullable=False, default="mode")`, `completed_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)`, `active_session_token: Mapped[str | None] = mapped_column(String(64), nullable=True)`.
- Migration `packages/server/src/openlia_server/db/migrations/versions/2026-04-21-0001_reshape_wizard_state.py` (revision `5d41c9a7e812`, down_revision `3c8e1a2b4d9f`). Migrates int→string via a helper column; maps legacy int `1..8` to named steps; preserves existing row data.
- `openlia wizard reset` CLI (`packages/server/src/openlia_server/cli.py`) now writes `current_step="mode"`, `completed_steps=[]`, `active_session_token=None`, `mode=None`, `step_data={}`.
- Test updates: `packages/server/tests/test_db/test_models_infrastructure.py` (`test_wizard_state_defaults` asserts the new defaults; new `test_wizard_state_accepts_named_step_and_session_token`). `packages/server/tests/test_cli/test_cli_wizard.py` fixture rows use the new shape; reset assertions check `current_step == "mode"`, `completed_steps == []`, `active_session_token is None`.

**Executor action (verify-only):**

- [ ] **Step 1: Confirm revision chain is linear**
  Run: `uv run alembic heads`
  Expected: `5d41c9a7e812 (head)` — exactly one head.
- [ ] **Step 2: Confirm the reshape tests pass**
  Run: `uv run pytest packages/server/tests/test_db/test_models_infrastructure.py packages/server/tests/test_cli/test_cli_wizard.py -q`
  Expected: all pass.
- [ ] **Step 3: Confirm aggregate server suite still green**
  Run: `uv run pytest packages/server/tests/ -q`
  Expected: all pass.

If any step fails, do not re-author Task 1 — fix the shipped code in place and re-run.

<details><summary>Historical (pre-REM-P1-006) snippet — do not execute.</summary>

The original Task 1 below was authored before the shape landed; it is retained only for auditability.

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_db/test_wizard_state_shape.py
"""Verify wizard_state shape after the reshape migration: current_step is a string,
completed_steps is a JSON array, and active_session_token is nullable text."""
from sqlalchemy.orm import Session

from openlia_server.db.models.infrastructure import WizardState


def test_wizard_state_accepts_named_step_and_completed_list(create_tables, db_session: Session) -> None:
    row = WizardState(
        id=1,
        current_step="mode",
        completed_steps=[],
        step_data={},
        active_session_token="abc",
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.get(WizardState, 1)
    assert fetched is not None
    assert fetched.current_step == "mode"
    assert fetched.completed_steps == []
    assert fetched.active_session_token == "abc"


def test_wizard_state_active_session_token_nullable(create_tables, db_session: Session) -> None:
    row = WizardState(id=1, current_step="mode", completed_steps=[], step_data={})
    db_session.add(row)
    db_session.commit()

    fetched = db_session.get(WizardState, 1)
    assert fetched is not None
    assert fetched.active_session_token is None


def test_wizard_state_completed_steps_round_trips_entries(create_tables, db_session: Session) -> None:
    row = WizardState(
        id=1,
        current_step="providers",
        completed_steps=["mode", "admin"],
        step_data={},
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.get(WizardState, 1)
    assert fetched is not None
    assert fetched.completed_steps == ["mode", "admin"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/server/tests/test_db/test_wizard_state_shape.py -v`
Expected: FAIL — `current_step` is int-typed, `completed_steps` + `active_session_token` do not exist on the model.

- [ ] **Step 3: Update the model**

In `packages/server/src/openlia_server/db/models/infrastructure.py`, change the `WizardState` class so that:

```python
class WizardState(Base):
    __tablename__ = "wizard_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Plan 1A shipped current_step as Integer default 1. Plan 10 keeps a string
    # step identifier instead ("mode", "admin", "providers", "data-providers",
    # "portfolio", "review"). Default is the first step.
    current_step: Mapped[str] = mapped_column(String(32), nullable=False, default="mode")
    completed_steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    step_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active_session_token: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
    )
```

Adjust imports as needed (`JSON`, `CheckConstraint`).

- [ ] **Step 4: Create the Alembic migration**

Run: `uv run alembic -c packages/server/alembic.ini revision -m "reshape_wizard_state"`

Then edit the generated file under `packages/server/migrations/versions/` to:

```python
"""reshape_wizard_state — current_step -> String, add completed_steps + active_session_token

Revision ID: <generated>
Revises: <prior>
Create Date: <generated>
"""
from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "<prior>"
branch_labels = None
depends_on = None


_STEP_ORDER = ["mode", "admin", "providers", "data-providers", "portfolio", "review"]


def upgrade() -> None:
    # SQLite requires batch mode for most ALTERs. Rewrite current_step from
    # Integer -> String, defaulting existing rows to the first named step.
    with op.batch_alter_table("wizard_state") as batch_op:
        batch_op.add_column(sa.Column("completed_steps", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("active_session_token", sa.String(length=64), nullable=True))
        batch_op.alter_column(
            "current_step",
            existing_type=sa.Integer(),
            type_=sa.String(length=32),
            existing_nullable=False,
            server_default="mode",
            postgresql_using="'mode'",
        )
    # Data fix-up: any prior int values become "mode".
    op.execute("UPDATE wizard_state SET current_step = 'mode' WHERE current_step NOT IN ("
               + ",".join(f"'{s}'" for s in _STEP_ORDER) + ")")


def downgrade() -> None:
    with op.batch_alter_table("wizard_state") as batch_op:
        batch_op.alter_column(
            "current_step",
            existing_type=sa.String(length=32),
            type_=sa.Integer(),
            existing_nullable=False,
            server_default="1",
            postgresql_using="1",
        )
        batch_op.drop_column("active_session_token")
        batch_op.drop_column("completed_steps")
    op.execute("UPDATE wizard_state SET current_step = 1")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest packages/server/tests/test_db/test_wizard_state_shape.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full DB test suite to catch regressions**

Run: `uv run pytest packages/server/tests/test_db/ -v`
Expected: all pass (Plan 1A's existing `test_wizard_state_defaults` may need updating to assert `current_step == "mode"` instead of `== 1` — update it in this task if so).

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/db/models/infrastructure.py \
        packages/server/migrations/versions/*reshape_wizard_state* \
        packages/server/tests/test_db/test_wizard_state_shape.py \
        packages/server/tests/test_db/test_wizard_state_model.py  # if updated
git commit -m "feat(db): reshape wizard_state — string current_step + completed_steps + active_session_token"
```

</details>

---

## Task 2: `WizardStatus` DTO + env-overrides resolver

**Files:**
- Create: `packages/server/src/openlia_server/services/wizard.py`
- Test: `packages/server/tests/test_services/test_wizard.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_services/test_wizard.py
"""Tests for WizardService.get_status and env-override resolution."""
import pytest
from sqlalchemy.orm import Session

from openlia_server.services import wizard as svc


def test_get_status_fresh_install_returns_personal_step_mode(create_tables, db_session: Session) -> None:
    status = svc.get_status(db_session, env={})
    assert status.mode == "personal"
    assert status.wizard_completed is False
    assert status.current_step == "mode"
    assert status.completed_steps == []
    assert status.env_overrides == {}


def test_get_status_reflects_env_mode_override(create_tables, db_session: Session) -> None:
    status = svc.get_status(db_session, env={"OPENLIA_MODE": "company"})
    assert status.mode == "company"
    assert "mode" in status.env_overrides


def test_get_status_reflects_wizard_completed_flag(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.completed", value="true"))
    db_session.add(ConfigStore(key="wizard.mode", value="company"))
    db_session.commit()

    status = svc.get_status(db_session, env={})
    assert status.wizard_completed is True
    assert status.mode == "company"


def test_get_status_env_mode_shadows_db_mode(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.mode", value="personal"))
    db_session.commit()

    status = svc.get_status(db_session, env={"OPENLIA_MODE": "company"})
    assert status.mode == "company"
    assert "mode" in status.env_overrides
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/server/tests/test_services/test_wizard.py -v`
Expected: FAIL — `openlia_server.services.wizard` import error.

- [ ] **Step 3: Create the service**

Create `packages/server/src/openlia_server/services/wizard.py`:

```python
"""Setup Wizard service — status resolution, step state, session token."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.infrastructure import ConfigStore, WizardState

Mode = Literal["personal", "company"]

ENV_KEYS: dict[str, str] = {
    "mode": "OPENLIA_MODE",
    "bind_host": "OPENLIA_BIND_HOST",
    "bind_port": "OPENLIA_BIND_PORT",
    "db_url": "OPENLIA_DB_URL",
    "auth_enabled": "OPENLIA_AUTH_ENABLED",
    "cookie_secure": "OPENLIA_COOKIE_SECURE",
    "trust_proxy_headers": "OPENLIA_TRUST_PROXY_HEADERS",
    "signup_policy": "OPENLIA_SIGNUP_POLICY",
    "signup_allowed_domains": "OPENLIA_SIGNUP_ALLOWED_DOMAINS",
}


@dataclass(slots=True)
class WizardStatus:
    mode: Mode
    wizard_completed: bool
    current_step: str
    completed_steps: list[str]
    env_overrides: dict[str, str] = field(default_factory=dict)


def _load_config(db: Session, key: str) -> str | None:
    return db.scalar(select(ConfigStore.value).where(ConfigStore.key == key))


def _env_overrides(env: dict[str, str]) -> dict[str, str]:
    return {slot: env_key for slot, env_key in ENV_KEYS.items() if env.get(env_key)}


def _resolve_mode(db: Session, env: dict[str, str]) -> Mode:
    if env.get("OPENLIA_MODE") in ("personal", "company"):
        return env["OPENLIA_MODE"]  # type: ignore[return-value]
    db_mode = _load_config(db, "wizard.mode")
    if db_mode in ("personal", "company"):
        return db_mode  # type: ignore[return-value]
    return "personal"


def _load_or_create_state(db: Session) -> WizardState:
    state = db.get(WizardState, 1)
    if state is None:
        state = WizardState(id=1, current_step="mode", completed_steps=[], step_data={})
        db.add(state)
        db.flush()
    return state


def get_status(db: Session, env: dict[str, str]) -> WizardStatus:
    completed = (_load_config(db, "wizard.completed") or "").lower() == "true"
    mode = _resolve_mode(db, env)
    state = _load_or_create_state(db)
    return WizardStatus(
        mode=mode,
        wizard_completed=completed,
        current_step=state.current_step,
        completed_steps=list(state.completed_steps or []),
        env_overrides=_env_overrides(env),
    )


def rotate_session_token(db: Session) -> str:
    state = _load_or_create_state(db)
    token = secrets.token_urlsafe(32)
    state.active_session_token = token
    db.flush()
    return token


def verify_session_token(db: Session, token: str | None) -> bool:
    if not token:
        return False
    state = db.get(WizardState, 1)
    return state is not None and state.active_session_token == token
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/server/tests/test_services/test_wizard.py -v`
Expected: all 4 pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/wizard.py \
        packages/server/tests/test_services/test_wizard.py
git commit -m "feat(wizard): add WizardService.get_status with env-override resolution"
```

---

## Task 3: Wizard-active middleware / dependency

**Files:**
- Create: `packages/server/src/openlia_server/middleware/wizard_gate.py`
- Test: `packages/server/tests/test_middleware/test_wizard_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_middleware/test_wizard_gate.py
"""Tests for wizard_gate dependency — 410 Gone after completion."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.middleware.wizard_gate import build_require_wizard_active


@pytest.fixture
def app_with_gate(db_session_factory):
    app = FastAPI()
    session_dep = make_session_dependency(db_session_factory)
    require_wizard_active = build_require_wizard_active(session_dep)

    @app.get("/setup/mode", dependencies=[require_wizard_active])
    def setup_mode():
        return {"ok": True}

    return TestClient(app)


def test_wizard_active_allows_request(app_with_gate) -> None:
    resp = app_with_gate.get("/setup/mode")
    assert resp.status_code == 200


def test_wizard_completed_returns_410(app_with_gate, db_session) -> None:
    db_session.add(ConfigStore(key="wizard.completed", value=True))
    db_session.commit()

    resp = app_with_gate.get("/setup/mode")
    assert resp.status_code == 410
    assert resp.json()["detail"]["code"] == "wizard_completed"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/server/tests/test_middleware/test_wizard_gate.py -v`
Expected: FAIL — `openlia_server.middleware.wizard_gate` import error.

- [ ] **Step 3: Create the dependency factories**

Create `packages/server/src/openlia_server/middleware/wizard_gate.py`:

```python
"""Dependencies guarding /setup/* routes.

- `build_require_wizard_active(session_dep)` — returns 410 Gone after wizard
  completion (Design Rule 4). Attach to every `/setup/*` path except
  `GET /setup/status` (spec requires status to always respond).
- `build_require_wizard_session(session_dep)` — enforces the single-session
  cookie (Design Rule 2). Attach to every write route except
  `POST /setup/mode` (issues the token) and `POST /setup/takeover`
  (rotates the token).
- `build_require_loopback_if_personal(mode, is_loopback_request)` — Design
  Rule 3. Attach to every `/setup/*` write route.

All three are factories so they close over the router's `session_dep` and
`is_loopback_request`. No module-level `get_db_session` import — there is no
such helper in source; use `make_session_dependency(db_session_factory)` from
`openlia_server.db.deps`.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Literal

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.services import wizard as wizard_svc


def _is_completed(db: DBSession) -> bool:
    value = db.scalar(select(ConfigStore.value).where(ConfigStore.key == "wizard.completed"))
    # Bootstrap seeds a Python bool; older rows may hold "true"/"false" strings.
    if isinstance(value, bool):
        return value
    return (value or "").lower() == "true"


def build_require_wizard_active(session_dep: Callable[[], Iterator[DBSession]]):
    def require_wizard_active(db: DBSession = Depends(session_dep)) -> None:
        if _is_completed(db):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"code": "wizard_completed", "message": "Setup has already been completed."},
            )

    return Depends(require_wizard_active)


def build_require_wizard_session(session_dep: Callable[[], Iterator[DBSession]]):
    def require_wizard_session(
        openlia_wizard_session: str | None = Cookie(default=None),
        db: DBSession = Depends(session_dep),
    ) -> None:
        if not wizard_svc.verify_session_token(db, openlia_wizard_session):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "wizard_session_active",
                    "message": "Another setup session is active. Take over to continue here.",
                },
            )

    return Depends(require_wizard_session)


def build_require_loopback_if_personal(
    *,
    mode: Literal["personal", "company"],
    is_loopback_request: Callable[[Request], bool],
):
    def require_loopback_if_personal(request: Request) -> None:
        if mode == "personal" and not is_loopback_request(request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "loopback_only",
                    "message": "Personal-mode setup writes are only accepted from 127.0.0.1/::1.",
                },
            )

    return Depends(require_loopback_if_personal)
```

The test file (`packages/server/tests/test_middleware/test_wizard_gate.py`) must build a mini-app via the same factory pattern — construct a `db_session_factory`, pass it to a local `APIRouter`, and attach `build_require_wizard_active(make_session_dependency(db_session_factory))` to a test route.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/server/tests/test_middleware/test_wizard_gate.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/middleware/wizard_gate.py \
        packages/server/tests/test_middleware/test_wizard_gate.py
git commit -m "feat(wizard): add require_wizard_active dependency returning 410 after completion"
```

---

## Task 4: `GET /setup/status` route

**Files:**
- Create: `packages/server/src/openlia_server/routes/setup.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py`
- Modify: `packages/server/src/openlia_server/app.py` (mount router)

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_routes/test_setup_routes.py
"""Tests for /setup/* routes."""
import pytest
from fastapi.testclient import TestClient


def test_status_fresh_install(personal_client: TestClient) -> None:
    resp = personal_client.get("/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "personal"
    assert body["wizard_completed"] is False
    assert body["current_step"] == "mode"
    assert body["completed_steps"] == []
    assert body["env_overrides"] == {}


def test_status_after_completion_still_returns_200(personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.completed", value="true"))
    db_session.add(ConfigStore(key="wizard.mode", value="personal"))
    db_session.commit()

    resp = personal_client.get("/setup/status")
    assert resp.status_code == 200
    assert resp.json()["wizard_completed"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: FAIL — `/setup/status` returns 404.

- [ ] **Step 3: Create the route module**

Create `packages/server/src/openlia_server/routes/setup.py`:

```python
"""Setup Wizard routes under /setup/*."""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.services import wizard as wizard_svc


class StatusOut(BaseModel):
    mode: str
    wizard_completed: bool
    current_step: str
    completed_steps: list[str]
    env_overrides: dict[str, str]


def build_setup_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
    is_loopback_request: Callable[[Request], bool],
) -> APIRouter:
    """Factory for /setup/*.

    `mode` and `is_loopback_request` are captured for the personal-mode
    loopback gate (Design Rule 3). Subsequent tasks attach the gate, the
    wizard-session cookie dep, and the 410-Gone gate via `build_require_*`
    factories from `middleware/wizard_gate.py`.
    """
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/setup", tags=["setup"])

    @router.get("/status", response_model=StatusOut)
    def get_status(db: DBSession = Depends(session_dep)) -> StatusOut:
        # GET /setup/status must always respond — no gates attached.
        result = wizard_svc.get_status(db, env=dict(os.environ))
        return StatusOut(
            mode=result.mode,
            wizard_completed=result.wizard_completed,
            current_step=result.current_step,
            completed_steps=result.completed_steps,
            env_overrides=result.env_overrides,
        )

    return router
```

- [ ] **Step 4: Wire the router into `app.py`**

In `packages/server/src/openlia_server/app.py`, inside `create_app(...)`, after existing router mounts:

```python
from fastapi import Request

from openlia_server.routes.setup import build_setup_router


def _is_loopback_request(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    return host in {"127.0.0.1", "::1", "localhost"}


app.include_router(
    build_setup_router(
        db_session_factory=factory,
        mode=mode,
        is_loopback_request=_is_loopback_request,
    )
)
```

`factory` (resolved from `db_session_factory or _default_session_factory`) and `mode` are the same values already passed to `build_auth_router`, `build_notifications_router`, etc. — they live in `create_app`'s scope. Use `factory`, not the raw `db_session_factory` parameter (which may be `None`).

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): add GET /setup/status route with env-override reporting"
```

---

## Task 5: `POST /setup/mode` route + session-token issuance

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Modify: `packages/server/src/openlia_server/services/wizard.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `packages/server/tests/test_routes/test_setup_routes.py`:

```python
def test_post_mode_persists_and_issues_cookie(personal_client: TestClient) -> None:
    resp = personal_client.post("/setup/mode", json={"mode": "company"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "company"
    assert "openlia_wizard_session" in resp.cookies

    status = personal_client.get("/setup/status").json()
    assert status["mode"] == "company"
    assert "mode" in status["completed_steps"]


def test_post_mode_rejected_when_env_override_set(personal_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    resp = personal_client.post("/setup/mode", json={"mode": "company"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "env_locked"


def test_post_mode_rejects_invalid_value(personal_client: TestClient) -> None:
    resp = personal_client.post("/setup/mode", json={"mode": "banana"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k post_mode`
Expected: FAIL — 404 on `POST /setup/mode`.

- [ ] **Step 3: Extend `wizard.py` with `set_mode` + `advance_step`**

Append to `packages/server/src/openlia_server/services/wizard.py`:

```python
def set_mode(db: Session, mode: Mode) -> None:
    row = db.scalar(select(ConfigStore).where(ConfigStore.key == "wizard.mode"))
    if row is None:
        db.add(ConfigStore(key="wizard.mode", value=mode))
    else:
        row.value = mode
    db.flush()


STEP_ORDER_PERSONAL = ["mode", "identity", "models", "providers", "review"]
STEP_ORDER_COMPANY = ["mode", "admin", "models", "providers", "access_control", "review"]


def advance_step(db: Session, completed: str, mode: Mode) -> None:
    state = _load_or_create_state(db)
    order = STEP_ORDER_COMPANY if mode == "company" else STEP_ORDER_PERSONAL
    if completed not in order:
        return
    done = list(state.completed_steps or [])
    if completed not in done:
        done.append(completed)
    idx = order.index(completed)
    state.current_step = order[idx + 1] if idx + 1 < len(order) else order[-1]
    state.completed_steps = done
    db.flush()
```

- [ ] **Step 4: Add the route + env guard + cookie**

Append inside `build_setup_router()` in `packages/server/src/openlia_server/routes/setup.py`:

```python
from fastapi import HTTPException, Response, status
from pydantic import Field

class ModeIn(BaseModel):
    mode: str = Field(pattern="^(personal|company)$")


@router.post("/mode")
def post_mode(
    payload: ModeIn,
    response: Response,
    db: DBSession = Depends(session_dep),
) -> dict[str, str]:
    if os.environ.get("OPENLIA_MODE"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "env_locked", "message": "Mode is locked by OPENLIA_MODE env var."},
        )
    wizard_svc.set_mode(db, payload.mode)  # type: ignore[arg-type]
    wizard_svc.advance_step(db, "mode", payload.mode)  # type: ignore[arg-type]
    token = wizard_svc.rotate_session_token(db)
    response.set_cookie(
        "openlia_wizard_session",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/setup",
    )
    return {"mode": payload.mode}
```

Also add the import for `require_wizard_active` at top and attach to the route signature once Task 6 lands.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass (3 new + 2 original).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/src/openlia_server/services/wizard.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): add POST /setup/mode with env lock + session cookie + step advance"
```

---

## Task 6: Wizard session-cookie dependency + takeover endpoint

**Files:**
- Modify: `packages/server/src/openlia_server/middleware/wizard_gate.py`
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `test_setup_routes.py`:

```python
def test_second_browser_without_takeover_rejected(personal_client: TestClient) -> None:
    personal_client.post("/setup/mode", json={"mode": "personal"})
    cookie = personal_client.cookies.get("openlia_wizard_session")
    assert cookie

    personal_client.cookies.clear()
    resp = personal_client.post("/setup/identity", json={"display_name": "Hacker"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "wizard_session_active"


def test_takeover_rotates_token(personal_client: TestClient) -> None:
    personal_client.post("/setup/mode", json={"mode": "personal"})
    first = personal_client.cookies.get("openlia_wizard_session")

    personal_client.cookies.clear()
    resp = personal_client.post("/setup/takeover")
    assert resp.status_code == 200
    second = personal_client.cookies.get("openlia_wizard_session")
    assert second and second != first
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k session`
Expected: FAIL.

- [ ] **Step 3: `build_require_wizard_session` already shipped in Task 3**

`build_require_wizard_session(session_dep)` was authored alongside `build_require_wizard_active` in Task 3 (single module, three factories). Verify the factory exists; do not re-author. The wizard-session cookie check closes over the same `session_dep` that the router factory binds.

- [ ] **Step 4: Add the takeover endpoint inside `build_setup_router(...)`**

Inside the router factory (same block that holds `GET /setup/status`), build the session and 410-gate dependencies from the closure, then add the takeover endpoint. Attach `require_wizard_active` and `require_loopback_if_personal` — takeover is a write and must respect Design Rules 3 and 4 — but **do not** attach `require_wizard_session`, since takeover's purpose is to rotate the token for a client that lacks one:

```python
from openlia_server.middleware.wizard_gate import (
    build_require_loopback_if_personal,
    build_require_wizard_active,
    build_require_wizard_session,
)

require_wizard_active = build_require_wizard_active(session_dep)
require_wizard_session = build_require_wizard_session(session_dep)
require_loopback = build_require_loopback_if_personal(
    mode=mode, is_loopback_request=is_loopback_request
)

@router.post(
    "/takeover",
    dependencies=[require_wizard_active, require_loopback],
)
def post_takeover(response: Response, db: DBSession = Depends(session_dep)) -> dict[str, bool]:
    token = wizard_svc.rotate_session_token(db)
    response.set_cookie(
        "openlia_wizard_session",
        token,
        httponly=True,
        samesite="lax",
        secure=(mode == "company"),
        path="/setup",
    )
    return {"ok": True}
```

(`secure=(mode == "company")` mirrors the main auth-cookie default from REM-P1-002.)

- [ ] **Step 5: Attach `require_wizard_session` to a placeholder `POST /setup/identity`**

Add a stub `POST /setup/identity` now so the "rejected without cookie" test has something to hit. It must carry all three gates (active, session, loopback):

```python
class IdentityIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)


@router.post(
    "/identity",
    dependencies=[require_wizard_active, require_wizard_session, require_loopback],
)
def post_identity(
    payload: IdentityIn,
    db: DBSession = Depends(session_dep),
) -> dict[str, str]:
    # Real impl lands in Task 7.
    return {"display_name": payload.display_name}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/middleware/wizard_gate.py \
        packages/server/src/openlia_server/routes/setup.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): add wizard session cookie guard + POST /setup/takeover"
```

---

## Task 7: `POST /setup/identity` (personal) — real impl

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Modify: `packages/server/src/openlia_server/services/wizard.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_post_identity_updates_local_user(personal_client: TestClient, db_session) -> None:
    from openlia_server.db.bootstrap import LOCAL_USER_ID
    from openlia_server.db.models.auth import User

    # Bootstrap has already seeded the local user with id="local".
    personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = personal_client.post("/setup/identity", json={"display_name": "TK"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "TK"

    user = db_session.get(User, LOCAL_USER_ID)
    assert user is not None
    assert user.display_name == "TK"
    assert user.is_admin is False


def test_post_identity_is_idempotent_on_display_name(personal_client: TestClient, db_session) -> None:
    from openlia_server.db.bootstrap import LOCAL_USER_ID
    from openlia_server.db.models.auth import User

    personal_client.post("/setup/mode", json={"mode": "personal"})
    personal_client.post("/setup/identity", json={"display_name": "A"})
    personal_client.post("/setup/identity", json={"display_name": "B"})

    rows = db_session.query(User).filter_by(id=LOCAL_USER_ID).all()
    assert len(rows) == 1
    assert rows[0].display_name == "B"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k identity`
Expected: FAIL — no User row created, placeholder returns payload only.

- [ ] **Step 3: Extend `wizard.py` with `upsert_local_user`**

Append to `services/wizard.py`:

```python
from openlia_server.db.bootstrap import LOCAL_USER_ID
from openlia_server.db.models.auth import User


def upsert_local_user(db: Session, display_name: str) -> User:
    """Bootstrap already seeded the id='local' row; this only updates the display name.

    User.id is String(36); do not create a second row by email filter — the
    singleton local user is keyed by id, not email.
    """
    user = db.get(User, LOCAL_USER_ID)
    if user is None:
        raise RuntimeError(
            "local user missing; bootstrap did not run. See db/bootstrap.py."
        )
    user.display_name = display_name
    db.flush()
    return user
```

- [ ] **Step 4: Replace the placeholder identity route**

In `routes/setup.py` replace the placeholder `post_identity` body with:

```python
@router.post("/identity")
def post_identity(
    payload: IdentityIn,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, str]:
    wizard_svc.upsert_local_user(db, payload.display_name)
    wizard_svc.advance_step(db, "identity", "personal")
    return {"display_name": payload.display_name}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/src/openlia_server/services/wizard.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): implement POST /setup/identity with upsert of local user"
```

---

## Task 8: `POST /setup/admin` (company) — first admin creation

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Modify: `packages/server/src/openlia_server/services/wizard.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_post_admin_creates_first_admin(company_client: TestClient, db_session) -> None:
    from openlia_server.db.models.auth import User

    company_client.post("/setup/mode", json={"mode": "company"})
    resp = company_client.post(
        "/setup/admin",
        json={"email": "boss@example.com", "password": "CorrectHorseBattery9!", "display_name": "Boss"},
    )
    assert resp.status_code == 200

    user = db_session.query(User).filter_by(email="boss@example.com").one()
    assert user.is_admin is True
    assert user.password_hash.startswith("$argon2")


def test_post_admin_rejects_second_admin(company_client: TestClient, db_session) -> None:
    company_client.post("/setup/mode", json={"mode": "company"})
    company_client.post(
        "/setup/admin",
        json={"email": "first@example.com", "password": "CorrectHorseBattery9!", "display_name": "A"},
    )
    resp = company_client.post(
        "/setup/admin",
        json={"email": "second@example.com", "password": "CorrectHorseBattery9!", "display_name": "B"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "admin_exists"


def test_post_admin_rejects_weak_password(company_client: TestClient) -> None:
    company_client.post("/setup/mode", json={"mode": "company"})
    resp = company_client.post(
        "/setup/admin",
        json={"email": "weak@example.com", "password": "short", "display_name": "W"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k admin`
Expected: FAIL.

- [ ] **Step 3: Extend service**

Append to `services/wizard.py`:

```python
from openlia_server.db.models.auth import User
from openlia_server.services.auth import users as user_service


class AdminExistsError(Exception):
    pass


def create_first_admin(db: Session, email: str, password: str, display_name: str) -> User:
    # User.id is String(36); user_service.create_user generates a uuid4 hex and
    # hashes the password via services.auth.passwords internally. No is_admin
    # column on Plan 1A — the canonical shipped User has `is_admin: bool`.
    if db.query(User).filter_by(is_admin=True).first() is not None:
        raise AdminExistsError()
    return user_service.create_user(
        db,
        email=email,
        password=password,
        display_name=display_name,
        is_admin=True,
    )
```

If `services.auth.users.create_user` has not yet landed with this signature (check source before executing), fall back to the shipped primitive `openlia_server.services.auth.passwords.hash_password(password)` and build the row manually with `User(id=uuid.uuid4().hex, email=..., password_hash=..., display_name=..., is_admin=True)`.

- [ ] **Step 4: Add the route**

In `routes/setup.py`:

```python
class AdminIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=60)


@router.post("/admin")
def post_admin(
    payload: AdminIn,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, str]:
    try:
        wizard_svc.create_first_admin(db, payload.email, payload.password, payload.display_name)
    except wizard_svc.AdminExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "admin_exists", "message": "An administrator is already configured."},
        ) from exc
    wizard_svc.advance_step(db, "admin", "company")
    return {"email": payload.email}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/src/openlia_server/services/wizard.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): implement POST /setup/admin with first-admin check + argon2 hash"
```

---

## Task 9: `POST /setup/models` + `/setup/models/test` (thin wrappers + required-tier gate)

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_models_test_route_pings_provider(personal_client: TestClient, respx_mock) -> None:
    from respx import MockRouter

    personal_client.post("/setup/mode", json={"mode": "personal"})
    respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
        200, json={"choices": [{"message": {"content": "ok"}}]}
    )
    resp = personal_client.post(
        "/setup/models/test",
        json={"provider": "openai", "model": "gpt-5.4", "api_key": "sk-test"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_models_save_rejects_when_required_tier_empty(
    personal_client: TestClient,
) -> None:
    personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = personal_client.post(
        "/setup/models",
        json={
            "thinking": [],  # required by equity_research + macro_research
            "everyday": [
                {
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "api_key": "sk-test",
                    "is_tier_default": True,
                }
            ],
            "quick": [
                {
                    "provider": "openai",
                    "model": "gpt-5.4-mini",
                    "api_key": "sk-test",
                    "is_tier_default": True,
                }
            ],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "required_tier_empty"
    assert "thinking" in resp.json()["detail"]["metadata"]["tiers"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k models`
Expected: FAIL — routes don't exist.

- [ ] **Step 3: Add the routes wrapping Plan 4 services**

In `routes/setup.py`:

```python
from openlia.llm.department_defaults import DEPARTMENT_DEFAULT_TIERS
from openlia.llm.types import ModelTier
from openlia_server.services import llm_providers as llm_svc


class TierEntryIn(BaseModel):
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    capabilities: dict[str, bool] | None = None
    is_tier_default: bool = False


class ModelsIn(BaseModel):
    thinking: list[TierEntryIn] = Field(default_factory=list)
    everyday: list[TierEntryIn] = Field(default_factory=list)
    quick: list[TierEntryIn] = Field(default_factory=list)


class ModelsTestIn(BaseModel):
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None


def _required_tiers(enabled_depts: list[str]) -> set[ModelTier]:
    return {DEPARTMENT_DEFAULT_TIERS[d] for d in enabled_depts if d in DEPARTMENT_DEFAULT_TIERS}


ENABLED_DEPARTMENTS_V1 = list(DEPARTMENT_DEFAULT_TIERS.keys())


@router.post("/models/test")
async def post_models_test(
    payload: ModelsTestIn,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, object]:
    result = await llm_svc.test_provider(
        provider=payload.provider,
        model=payload.model,
        api_key=payload.api_key,
        base_url=payload.base_url,
    )
    return {"ok": result.ok, "latency_ms": result.latency_ms, "error": result.error}


@router.post("/models")
async def post_models(
    payload: ModelsIn,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, bool]:
    tier_payloads = {"thinking": payload.thinking, "everyday": payload.everyday, "quick": payload.quick}

    required = _required_tiers(ENABLED_DEPARTMENTS_V1)
    missing = [tier.value for tier in required if not tier_payloads[tier.value]]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "required_tier_empty",
                "message": "One or more required tiers have no models.",
                "metadata": {"tiers": missing},
            },
        )

    llm_svc.clear_all_providers(db)
    for tier_name, entries in tier_payloads.items():
        for entry in entries:
            provider = llm_svc.create_provider(
                db,
                provider=entry.provider,
                api_key=entry.api_key,
                base_url=entry.base_url,
                capabilities=entry.capabilities,
            )
            llm_svc.add_model(
                db,
                provider_id=provider.id,
                model=entry.model,
                tier=ModelTier(tier_name),
                is_tier_default=entry.is_tier_default,
            )

    mode = wizard_svc.get_status(db, env=dict(os.environ)).mode
    wizard_svc.advance_step(db, "models", mode)
    return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): add /setup/models + /setup/models/test with required-tier gate"
```

---

## Task 10: `POST/GET/PATCH/DELETE /setup/providers` + `/test`

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_providers_crud_lifecycle(personal_client: TestClient, respx_mock) -> None:
    personal_client.post("/setup/mode", json={"mode": "personal"})
    respx_mock.get("https://eodhd.com/api/exchanges-list/").respond(200, json=[{"Code": "US"}])

    resp = personal_client.post(
        "/setup/providers",
        json={
            "category": "financial",
            "entry": {
                "mode": "builtin",
                "provider": "eodhd",
                "api_key": "demo",
            },
        },
    )
    assert resp.status_code == 200
    pid = resp.json()["entry_id"]

    listed = personal_client.get("/setup/providers").json()
    assert any(p["id"] == pid for p in listed["providers"])

    patched = personal_client.patch(f"/setup/providers/{pid}", json={"priority": 0})
    assert patched.status_code == 200

    deleted = personal_client.delete(f"/setup/providers/{pid}")
    assert deleted.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k providers`
Expected: FAIL.

- [ ] **Step 3: Add the routes as wrappers around Plan 3's service**

In `routes/setup.py`:

```python
from openlia_server.services import data_providers as dp_svc


class ProviderEntryIn(BaseModel):
    mode: str = Field(pattern="^(builtin|mcp|openapi)$")
    provider: str | None = None
    api_key: str | None = None
    mcp_url: str | None = None
    mcp_auth_header: str | None = None
    openapi_spec_url: str | None = None


class ProviderIn(BaseModel):
    category: str = Field(pattern="^(financial|news|social|web_search)$")
    entry: ProviderEntryIn


class ProviderPatchIn(BaseModel):
    priority: int | None = None
    api_key: str | None = None


def _provider_out(row) -> dict[str, object]:
    return {
        "id": row.id,
        "category": row.category,
        "mode": row.mode,
        "provider": row.provider,
        "priority": row.priority,
        "status": row.status,
    }


@router.get("/providers")
def get_providers(
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, list[dict[str, object]]]:
    rows = dp_svc.list_all(db)
    return {"providers": [_provider_out(r) for r in rows]}


@router.post("/providers")
async def post_provider(
    payload: ProviderIn,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, object]:
    result = await dp_svc.create_and_test(db, category=payload.category, entry=payload.entry.model_dump())
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "provider_test_failed", "message": result.error or "Test failed."},
        )
    return {"ok": True, "entry_id": result.provider_id}


@router.patch("/providers/{entry_id}")
def patch_provider(
    entry_id: str,
    payload: ProviderPatchIn,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, bool]:
    if payload.priority is not None:
        dp_svc.reorder(db, entry_id, payload.priority)
    if payload.api_key is not None:
        dp_svc.update_api_key(db, entry_id, payload.api_key)
    return {"ok": True}


@router.delete("/providers/{entry_id}")
def delete_provider(
    entry_id: str,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, bool]:
    dp_svc.delete(db, entry_id)
    return {"ok": True}


@router.post("/providers/{entry_id}/test")
async def retest_provider(
    entry_id: str,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, object]:
    result = await dp_svc.retest(db, entry_id)
    return {"ok": result.ok, "latency_ms": result.latency_ms, "error": result.error}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): add /setup/providers CRUD + /test thin over data_providers service"
```

---

## Task 11: `POST /setup/access_control` (company only)

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Modify: `packages/server/src/openlia_server/services/wizard.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_access_control_writes_policy_and_bind_config(company_client: TestClient, db_session) -> None:
    from openlia_server.db.models.auth import SignupPolicy
    from openlia_server.db.models.infrastructure import ConfigStore

    company_client.post("/setup/mode", json={"mode": "company"})
    resp = company_client.post(
        "/setup/access_control",
        json={
            "signup_policy": "invite_only",
            "allowed_domains": "example.com,acme.com",
            "bind_host": "0.0.0.0",
            "bind_port": 8000,
        },
    )
    assert resp.status_code == 200

    policy = db_session.query(SignupPolicy).one()
    assert policy.policy == "invite_only"
    assert policy.allowed_domains == "example.com,acme.com"

    host = db_session.query(ConfigStore).filter_by(key="server.bind_host").one()
    port = db_session.query(ConfigStore).filter_by(key="server.bind_port").one()
    assert host.value == "0.0.0.0"
    assert port.value == "8000"


def test_access_control_rejects_personal_mode(personal_client: TestClient) -> None:
    personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = personal_client.post(
        "/setup/access_control",
        json={"signup_policy": "invite_only", "bind_host": "127.0.0.1", "bind_port": 8000},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "wrong_mode"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k access_control`
Expected: FAIL.

- [ ] **Step 3: Extend service**

Append to `services/wizard.py`:

```python
from typing import Any

from openlia_server.db.models.auth import SignupPolicy


def set_signup_policy(
    db: Session, *, policy: str, allowed_domains: str | None
) -> None:
    row = db.query(SignupPolicy).one_or_none()
    if row is None:
        row = SignupPolicy(id=1, policy=policy, allowed_domains=allowed_domains)
        db.add(row)
    else:
        row.policy = policy
        row.allowed_domains = allowed_domains
    db.flush()


def set_config(db: Session, key: str, value: Any) -> None:
    # ConfigStore.value is typed JSON (see db/models/infrastructure.py) — pass
    # native Python types (bool / str / int). Bootstrap seeds `wizard.completed`
    # as a Python bool, so don't coerce to "true"/"false" strings here.
    row = db.query(ConfigStore).filter_by(key=key).one_or_none()
    if row is None:
        db.add(ConfigStore(key=key, value=value))
    else:
        row.value = value
    db.flush()
```

- [ ] **Step 4: Add the route**

In `routes/setup.py`:

```python
class AccessControlIn(BaseModel):
    signup_policy: str = Field(pattern="^(invite_only|closed)$")
    allowed_domains: str | None = None
    bind_host: str = Field(min_length=1, max_length=253)
    bind_port: int = Field(ge=1, le=65535)


@router.post("/access_control")
def post_access_control(
    payload: AccessControlIn,
    db: DBSession = Depends(session_dep),
    _: None = Depends(require_wizard_session),
) -> dict[str, bool]:
    mode = wizard_svc.get_status(db, env=dict(os.environ)).mode
    if mode != "company":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "wrong_mode", "message": "Access control is company-mode only."},
        )
    wizard_svc.set_signup_policy(
        db, policy=payload.signup_policy, allowed_domains=payload.allowed_domains
    )
    wizard_svc.set_config(db, "server.bind_host", payload.bind_host)
    wizard_svc.set_config(db, "server.bind_port", str(payload.bind_port))
    wizard_svc.advance_step(db, "access_control", "company")
    return {"ok": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/src/openlia_server/services/wizard.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): implement POST /setup/access_control writing signup_policy + bind config"
```

---

## Task 12: AI review — schema + prompt builder

**Files:**
- Create: `packages/server/src/openlia_server/ai_review/__init__.py` (empty)
- Create: `packages/server/src/openlia_server/ai_review/schema.py`
- Create: `packages/server/src/openlia_server/ai_review/prompt.py`
- Test: `packages/server/tests/test_services/test_ai_review.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_services/test_ai_review.py
"""Tests for the AI review schema + prompt builder."""
from openlia_server.ai_review.schema import DepartmentReadiness, ReadinessState, ReviewResult
from openlia_server.ai_review.prompt import build_review_prompt


def test_readiness_state_values() -> None:
    assert set(s.value for s in ReadinessState) == {"ready", "gaps", "disabled", "blocked"}


def test_review_result_serializes() -> None:
    result = ReviewResult(
        summary="6 of 7 ready.",
        departments=[
            DepartmentReadiness(
                id="secretary",
                state=ReadinessState.READY,
                note=None,
                basic=[{"type": "stock_quote", "provider": "eodhd", "confidence": 0.95}],
                advanced=[],
                unmet=[],
            )
        ],
    )
    dumped = result.model_dump()
    assert dumped["departments"][0]["state"] == "ready"


def test_build_review_prompt_lists_departments_and_providers() -> None:
    prompt = build_review_prompt(
        departments=[("secretary", ["stock_quote"])],
        providers=[{"id": "p1", "category": "financial", "provider": "eodhd"}],
    )
    assert "secretary" in prompt
    assert "stock_quote" in prompt
    assert "eodhd" in prompt
    assert "confidence" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_ai_review.py -v`
Expected: FAIL — `openlia_server.ai_review` import errors.

- [ ] **Step 3: Write the schema**

Create `packages/server/src/openlia_server/ai_review/__init__.py` (empty file).

Create `packages/server/src/openlia_server/ai_review/schema.py`:

```python
"""Pydantic schema for AI review output."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ReadinessState(str, Enum):
    READY = "ready"
    GAPS = "gaps"
    DISABLED = "disabled"
    BLOCKED = "blocked"


class RequirementMapping(BaseModel):
    type: str
    provider: str | None
    confidence: float


class DepartmentReadiness(BaseModel):
    id: str
    state: ReadinessState
    note: str | None = None
    basic: list[RequirementMapping]
    advanced: list[RequirementMapping]
    unmet: list[str]


class ReviewResult(BaseModel):
    summary: str
    departments: list[DepartmentReadiness]
```

Create `packages/server/src/openlia_server/ai_review/prompt.py`:

```python
"""Prompt builder for the wizard AI review step."""
from __future__ import annotations

import json

PROMPT_HEADER = """You are reviewing a self-hosted AI investor assistant's data provider setup.
Given a list of departments (each with required data-requirement types) and a list of
configured data providers, return a JSON object mapping each department to a readiness
state. Use "ready" when every basic requirement has a confidence>=0.7 match, "gaps"
when basic requirements are all met but one or more advanced requirements are unmapped,
"disabled" when the department depends on a capability nothing ships, and "blocked"
when any basic requirement is unmet.

Respond ONLY with JSON matching the schema:
{
  "summary": str,
  "departments": [
    {
      "id": str,
      "state": "ready" | "gaps" | "disabled" | "blocked",
      "note": str | null,
      "basic": [{"type": str, "provider": str | null, "confidence": float}],
      "advanced": [{"type": str, "provider": str | null, "confidence": float}],
      "unmet": [str]
    }
  ]
}
"""


def build_review_prompt(
    departments: list[tuple[str, list[str]]],
    providers: list[dict[str, object]],
) -> str:
    body = {
        "departments": [{"id": d, "basic_requirements": reqs} for d, reqs in departments],
        "providers": providers,
    }
    return f"{PROMPT_HEADER}\nINPUT:\n{json.dumps(body, indent=2)}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_ai_review.py -v`
Expected: all 3 pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/ai_review/ \
        packages/server/tests/test_services/test_ai_review.py
git commit -m "feat(setup): add ai_review schema + prompt builder for wizard review step"
```

---

## Task 13: AI review — runner + in-memory store

**Files:**
- Create: `packages/server/src/openlia_server/ai_review/store.py`
- Create: `packages/server/src/openlia_server/ai_review/runner.py`
- Test: `packages/server/tests/test_services/test_ai_review.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `test_ai_review.py`:

```python
import pytest
from unittest.mock import AsyncMock

from openlia.llm.types import LLMResponse

from openlia_server.ai_review.store import ReviewStore
from openlia_server.ai_review.runner import run_review


def _fake_response(text: str) -> LLMResponse:
    return LLMResponse(text=text, finish_reason="stop", input_tokens=0, output_tokens=0)


@pytest.mark.asyncio
async def test_run_review_populates_store_on_success(db_session) -> None:
    store = ReviewStore()
    review_id = store.create()

    fake_llm = AsyncMock()
    fake_llm.generate.return_value = _fake_response(
        '{"summary": "1 of 1 ready.", "departments": ['
        '{"id": "secretary", "state": "ready", "note": null, '
        '"basic": [{"type": "stock_quote", "provider": "eodhd", "confidence": 0.9}], '
        '"advanced": [], "unmet": []}]}'
    )

    await run_review(
        review_id=review_id,
        db=db_session,
        llm=fake_llm,
        departments=[("secretary", ["stock_quote"])],
        providers=[{"id": "p1", "category": "financial", "provider": "eodhd"}],
        store=store,
    )
    entry = store.get(review_id)
    assert entry is not None
    assert entry["state"] == "complete"
    assert entry["result"]["departments"][0]["state"] == "ready"


@pytest.mark.asyncio
async def test_run_review_marks_failure_on_bad_json() -> None:
    store = ReviewStore()
    review_id = store.create()

    fake_llm = AsyncMock()
    fake_llm.generate.return_value = _fake_response("not json")

    await run_review(
        review_id=review_id,
        db=None,
        llm=fake_llm,
        departments=[("secretary", ["stock_quote"])],
        providers=[],
        store=store,
    )
    entry = store.get(review_id)
    assert entry["state"] == "failed"
    assert "parse" in entry["error"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_ai_review.py -v -k run_review`
Expected: FAIL — import errors.

- [ ] **Step 3: Create the store**

Create `packages/server/src/openlia_server/ai_review/store.py`:

```python
"""In-memory store for in-flight AI review tasks."""
from __future__ import annotations

import uuid
from threading import Lock
from typing import Any


class ReviewStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: dict[str, dict[str, Any]] = {}

    def create(self) -> str:
        review_id = str(uuid.uuid4())
        with self._lock:
            self._entries[review_id] = {"state": "running", "progress": 0, "result": None, "error": None}
        return review_id

    def update(self, review_id: str, **fields: Any) -> None:
        with self._lock:
            if review_id in self._entries:
                self._entries[review_id].update(fields)

    def get(self, review_id: str) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._entries[review_id]) if review_id in self._entries else None


DEFAULT_STORE = ReviewStore()
```

- [ ] **Step 4: Create the runner**

Create `packages/server/src/openlia_server/ai_review/runner.py`:

```python
"""AI review orchestrator — calls Quick-tier LLM + parses JSON response."""
from __future__ import annotations

import json
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message

from openlia_server.ai_review.prompt import build_review_prompt
from openlia_server.ai_review.schema import ReviewResult
from openlia_server.ai_review.store import ReviewStore


async def run_review(
    *,
    review_id: str,
    db: Any,
    llm: LLMProvider,
    departments: list[tuple[str, list[str]]],
    providers: list[dict[str, object]],
    store: ReviewStore,
) -> None:
    try:
        prompt = build_review_prompt(departments, providers)
        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            max_tokens=4096,
            temperature=0.2,
        )
        response = await llm.generate(request)
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            store.update(review_id, state="failed", error=f"parse error: {exc}")
            return
        result = ReviewResult.model_validate(payload)
        store.update(review_id, state="complete", progress=100, result=result.model_dump())
    except Exception as exc:  # noqa: BLE001 — surface any failure to polling client
        store.update(review_id, state="failed", error=str(exc))
```

Note: `LLMProvider.generate` takes an `LLMRequest` dataclass (see `openlia/llm/base.py` + `openlia/llm/types.py`), not `prompt=` / `max_tokens=` kwargs. The `LLMRequest` constructor requires a `messages` list of `Message(role, content)`. If you need the JSON-only contract enforced by the adapter, also set `response_format=ResponseFormat(kind="json_object")` on supported providers — Gemini / OpenAI / Anthropic will honor it; OpenRouter is pass-through.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_ai_review.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/ai_review/store.py \
        packages/server/src/openlia_server/ai_review/runner.py \
        packages/server/tests/test_services/test_ai_review.py
git commit -m "feat(setup): add AI review runner + in-memory store"
```

---

## Task 14: `/setup/review/run` + `/setup/review/{id}` routes

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_review_run_kicks_off_task_and_poll_returns_running(
    personal_client: TestClient, monkeypatch
) -> None:
    from openlia_server.ai_review import store as store_mod
    fresh_store = store_mod.ReviewStore()
    monkeypatch.setattr(store_mod, "DEFAULT_STORE", fresh_store)

    personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = personal_client.post("/setup/review/run")
    assert resp.status_code == 200
    review_id = resp.json()["review_id"]

    poll = personal_client.get(f"/setup/review/{review_id}")
    assert poll.status_code == 200
    assert poll.json()["state"] in ("running", "complete", "failed")


def test_review_poll_unknown_id_returns_404(personal_client: TestClient) -> None:
    personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = personal_client.get("/setup/review/nope")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k review`
Expected: FAIL.

- [ ] **Step 3: Add the routes**

In `routes/setup.py`:

```python
import asyncio

from openlia.llm.adapters import build_adapter
from openlia.llm.resolver import resolve as resolve_llm  # sync — returns ResolvedModel
from openlia_server.ai_review import store as review_store_mod
from openlia_server.ai_review.runner import run_review as _run_review
from openlia_server.services import data_providers as dp_svc
from openlia_server.services.llm_registry import SQLModelRegistry


ENABLED_DEPARTMENTS_REQS: dict[str, list[str]] = {
    "secretary": [],
    "equity_research": ["stock_quote", "company_profile", "financial_statements"],
    "earnings_update": ["earnings_data", "stock_quote"],
    "morning_briefing": ["market_news", "stock_quote"],
    "retail_sentiment": ["social_posts"],
    "macro_research": ["macro_indicators", "stock_quote"],
    "panic_thermometer": ["market_news", "stock_quote"],
}


@router.post(
    "/review/run",
    dependencies=[require_wizard_active, require_wizard_session, require_loopback],
)
async def post_review_run(
    db: DBSession = Depends(session_dep),
) -> dict[str, str]:
    store = review_store_mod.DEFAULT_STORE
    review_id = store.create()

    # resolve() is sync; it returns a ResolvedModel (provider_kind + credentials
    # + model + capabilities). Build the adapter in the request path — we must
    # not reuse the request-scoped db session inside the background task.
    resolved = resolve_llm(
        department_id="panic_thermometer",  # guarantees Quick tier per DEPARTMENT_DEFAULT_TIERS
        user_id=None,
        registry=SQLModelRegistry(db),
    )
    llm = build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=resolved.capabilities,
    )

    departments = list(ENABLED_DEPARTMENTS_REQS.items())
    # list_providers returns DataProvider rows; IDs are String(36); only include
    # enabled providers in the review input.
    providers = [
        {"id": row.id, "category": row.category, "provider": row.provider_kind}
        for row in dp_svc.list_providers(db)
        if row.is_enabled
    ]

    asyncio.create_task(
        _run_review(
            review_id=review_id,
            db=None,  # runner must open its own SessionLocal() if persistence is added later
            llm=llm,
            departments=departments,
            providers=providers,
            store=store,
        )
    )
    return {"review_id": review_id}


@router.get("/review/{review_id}")
def get_review(
    review_id: str,
) -> dict[str, object]:
    entry = review_store_mod.DEFAULT_STORE.get(review_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "review_not_found", "message": "Unknown review id."},
        )
    return entry
```

Notes: the `get_review` route intentionally does **not** carry `require_wizard_session` — any client with a valid review_id can poll (ids are uuid4 hex, unguessable). The 410-gate is also omitted because the review is a terminal-step read that the UI continues polling after the wizard's in-memory `finish` step; if you want the gate, attach `require_wizard_active` to this route and move the last poll before `POST /setup/finish`.

Notes for the runner (`ai_review/runner.py`): do **not** pass the request-scoped `db` into the background task — the route's `session_dep` closes the session on response. The runner must open a fresh `SessionLocal()` inside `run_review(...)` to persist mapping rows, and accept the `ResolvedModel` (not the open session) as its LLM handle.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): add /setup/review/run + /setup/review/{id} polling routes"
```

---

## Task 15: `POST /setup/finish` — atomic completion

**Files:**
- Modify: `packages/server/src/openlia_server/routes/setup.py`
- Modify: `packages/server/src/openlia_server/services/wizard.py`
- Test: `packages/server/tests/test_routes/test_setup_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_finish_writes_completed_and_returns_redirect(
    personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore, WizardState

    personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = personal_client.post("/setup/finish")
    assert resp.status_code == 200
    assert resp.json()["redirect"] == "/"

    completed = db_session.query(ConfigStore).filter_by(key="wizard.completed").one()
    # bootstrap seeds config_store.value as a Python bool; readers must tolerate
    # both bool and legacy "true"/"false" strings (see README contract locks).
    assert completed.value in (True, "true")
    state = db_session.get(WizardState, 1)
    assert state.active_session_token is None


def test_finish_returns_410_once_done(personal_client: TestClient) -> None:
    personal_client.post("/setup/mode", json={"mode": "personal"})
    personal_client.post("/setup/finish")
    resp = personal_client.post("/setup/finish")
    assert resp.status_code == 410


def test_finish_company_mode_redirects_to_login(company_client: TestClient) -> None:
    company_client.post("/setup/mode", json={"mode": "company"})
    resp = company_client.post("/setup/finish")
    assert resp.json()["redirect"] == "/login"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v -k finish`
Expected: FAIL.

- [ ] **Step 3: Extend service**

Append to `services/wizard.py`:

```python
def finalize(db: Session, mode: Mode) -> None:
    # wizard.completed is stored as a Python bool (JSON column); wizard.mode is
    # a short string. See Cross-plan contract lock 2026-04-20.
    set_config(db, "wizard.completed", True)
    set_config(db, "wizard.mode", mode)
    state = _load_or_create_state(db)
    state.active_session_token = None
    state.completed_steps = []
    state.current_step = "done"
    state.step_data = {}
    db.flush()
```

- [ ] **Step 4: Add `require_wizard_active` to the router + the finish route**

In `routes/setup.py`, inside `build_setup_router(...)` where gate factories are bound (see Task 3 / Task 4 rewrites), the local names `require_wizard_active`, `require_wizard_session`, and `require_loopback` are already in scope. Add the finish route alongside the others:

```python
@router.post("/finish", dependencies=[require_wizard_active, require_wizard_session])
def post_finish(
    db: DBSession = Depends(session_dep),
) -> dict[str, str]:
    mode = wizard_svc.get_status(db, env=dict(os.environ)).mode
    wizard_svc.finalize(db, mode)
    redirect = "/" if mode == "personal" else "/login"
    return {"redirect": redirect, "mode": mode}
```

Attach `require_wizard_active` to every step route added in Tasks 5, 7, 8, 9, 10, 11, 14 using `dependencies=[require_wizard_active, ...]` on the `@router.<verb>` decorator so they return 410 after completion. The gate dependencies are bound objects (already wrapped with `Depends(...)` inside the factory), not names to re-wrap.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_setup_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/setup.py \
        packages/server/src/openlia_server/services/wizard.py \
        packages/server/tests/test_routes/test_setup_routes.py
git commit -m "feat(setup): add POST /setup/finish with atomic completion + 410 guard on step routes"
```

---

## Task 16: Frontend — `api/setup.ts` typed client

**Files:**
- Create: `frontend/src/api/setup.ts`
- Test: `frontend/src/api/setup.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/api/setup.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import * as setup from "./setup";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("api/setup", () => {
  it("getStatus returns parsed body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          mode: "personal",
          wizard_completed: false,
          current_step: "mode",
          completed_steps: [],
          env_overrides: {},
        }),
        { status: 200 },
      ),
    );
    const status = await setup.getStatus();
    expect(status.mode).toBe("personal");
    expect(status.wizard_completed).toBe(false);
  });

  it("setMode posts to /api/setup/mode", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ mode: "company" }), { status: 200 }));
    await setup.setMode("company");
    expect(spy).toHaveBeenCalledWith(
      "/api/setup/mode",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("finish returns redirect target", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ redirect: "/login", mode: "company" }), { status: 200 }),
    );
    const result = await setup.finish();
    expect(result.redirect).toBe("/login");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- setup.test.ts`
Expected: FAIL — module `./setup` does not exist.

- [ ] **Step 3: Implement the client**

Create `frontend/src/api/setup.ts`:

```typescript
import { fetchJson } from "./client";

export type Mode = "personal" | "company";

export interface WizardStatus {
  mode: Mode;
  wizard_completed: boolean;
  current_step: string;
  completed_steps: string[];
  env_overrides: Record<string, string>;
}

export interface TestResult {
  ok: boolean;
  latency_ms: number | null;
  error: string | null;
}

export interface TierEntry {
  provider: string;
  model: string;
  api_key?: string;
  base_url?: string;
  capabilities?: Record<string, boolean>;
  is_tier_default?: boolean;
}

export interface ModelsPayload {
  thinking: TierEntry[];
  everyday: TierEntry[];
  quick: TierEntry[];
}

export interface ProviderEntry {
  mode: "builtin" | "mcp" | "openapi";
  provider?: string;
  api_key?: string;
  mcp_url?: string;
  mcp_auth_header?: string;
  openapi_spec_url?: string;
}

export interface ProviderRow {
  id: string;
  category: string;
  mode: string;
  provider: string | null;
  priority: number;
  status: string;
}

export interface ReviewPoll {
  state: "running" | "complete" | "failed";
  progress: number;
  result: unknown | null;
  error: string | null;
}

export interface AccessControlPayload {
  signup_policy: "invite_only" | "closed";
  allowed_domains?: string;
  bind_host: string;
  bind_port: number;
}

export const getStatus = () => fetchJson<WizardStatus>("/api/setup/status");

export const setMode = (mode: Mode) =>
  fetchJson<{ mode: Mode }>("/api/setup/mode", { method: "POST", body: { mode } });

export const takeover = () => fetchJson<{ ok: boolean }>("/api/setup/takeover", { method: "POST" });

export const setIdentity = (displayName: string) =>
  fetchJson<{ display_name: string }>("/api/setup/identity", {
    method: "POST",
    body: { display_name: displayName },
  });

export const setAdmin = (payload: { email: string; password: string; display_name: string }) =>
  fetchJson<{ email: string }>("/api/setup/admin", { method: "POST", body: payload });

export const testModel = (payload: {
  provider: string;
  model: string;
  api_key?: string;
  base_url?: string;
}) => fetchJson<TestResult>("/api/setup/models/test", { method: "POST", body: payload });

export const saveModels = (payload: ModelsPayload) =>
  fetchJson<{ ok: boolean }>("/api/setup/models", { method: "POST", body: payload });

export const listProviders = () =>
  fetchJson<{ providers: ProviderRow[] }>("/api/setup/providers");

export const addProvider = (payload: { category: string; entry: ProviderEntry }) =>
  fetchJson<{ ok: boolean; entry_id: string }>("/api/setup/providers", {
    method: "POST",
    body: payload,
  });

export const patchProvider = (id: string, patch: { priority?: number; api_key?: string }) =>
  fetchJson<{ ok: boolean }>(`/api/setup/providers/${id}`, { method: "PATCH", body: patch });

export const deleteProvider = (id: string) =>
  fetchJson<{ ok: boolean }>(`/api/setup/providers/${id}`, { method: "DELETE" });

export const retestProvider = (id: string) =>
  fetchJson<TestResult>(`/api/setup/providers/${id}/test`, { method: "POST" });

export const setAccessControl = (payload: AccessControlPayload) =>
  fetchJson<{ ok: boolean }>("/api/setup/access_control", { method: "POST", body: payload });

export const runReview = () =>
  fetchJson<{ review_id: string }>("/api/setup/review/run", { method: "POST" });

export const pollReview = (id: string) =>
  fetchJson<ReviewPoll>(`/api/setup/review/${id}`);

export const finish = () =>
  fetchJson<{ redirect: string; mode: Mode }>("/api/setup/finish", { method: "POST" });
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- setup.test.ts`
Expected: all 3 pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/setup.ts frontend/src/api/setup.test.ts
git commit -m "feat(frontend): add typed /api/setup client"
```

---

## Task 17: Frontend — `WizardContext` provider + `useWizard`

**Files:**
- Create: `frontend/src/setup/WizardContext.tsx`
- Test: `frontend/src/setup/WizardContext.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/setup/WizardContext.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { WizardProvider, useWizard } from "./WizardContext";

beforeEach(() => {
  vi.restoreAllMocks();
});

function Probe() {
  const wizard = useWizard();
  if (wizard.state === "loading") return <div>loading</div>;
  return (
    <div>
      mode:{wizard.status.mode} step:{wizard.status.current_step}
    </div>
  );
}

describe("WizardContext", () => {
  it("fetches status on mount", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          mode: "company",
          wizard_completed: false,
          current_step: "admin",
          completed_steps: ["mode"],
          env_overrides: {},
        }),
        { status: 200 },
      ),
    );

    render(
      <WizardProvider>
        <Probe />
      </WizardProvider>,
    );
    await waitFor(() => expect(screen.getByText(/mode:company/)).toBeInTheDocument());
    expect(screen.getByText(/step:admin/)).toBeInTheDocument();
  });

  it("exposes refresh() that re-fetches status", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          mode: "personal",
          wizard_completed: false,
          current_step: "mode",
          completed_steps: [],
          env_overrides: {},
        }),
        { status: 200 },
      ),
    );

    function Refresher() {
      const wizard = useWizard();
      if (wizard.state === "loading") return <div>loading</div>;
      return <button onClick={wizard.refresh}>refresh</button>;
    }

    render(
      <WizardProvider>
        <Refresher />
      </WizardProvider>,
    );
    await waitFor(() => screen.getByText("refresh"));
    screen.getByText("refresh").click();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- WizardContext.test.tsx`
Expected: FAIL — module `./WizardContext` does not exist.

- [ ] **Step 3: Implement the context**

Create `frontend/src/setup/WizardContext.tsx`:

```tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getStatus } from "../api/setup";
import type { WizardStatus } from "../api/setup";

export type WizardState =
  | { state: "loading" }
  | { state: "ready"; status: WizardStatus; refresh: () => Promise<void> }
  | { state: "error"; message: string; refresh: () => Promise<void> };

const WizardCtx = createContext<WizardState | null>(null);

export function WizardProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<WizardState>({ state: "loading" });

  const refresh = useCallback(async () => {
    try {
      const status = await getStatus();
      setValue({ state: "ready", status, refresh });
    } catch (err) {
      setValue({
        state: "error",
        message: err instanceof Error ? err.message : "Failed to load setup status",
        refresh,
      });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const memo = useMemo(() => value, [value]);
  return <WizardCtx.Provider value={memo}>{children}</WizardCtx.Provider>;
}

export function useWizard(): Extract<WizardState, { state: "ready" }> | Extract<WizardState, { state: "loading" }> | Extract<WizardState, { state: "error" }> {
  const ctx = useContext(WizardCtx);
  if (\!ctx) throw new Error("useWizard must be used inside WizardProvider");
  return ctx;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- WizardContext.test.tsx`
Expected: all 2 pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/WizardContext.tsx frontend/src/setup/WizardContext.test.tsx
git commit -m "feat(frontend): add WizardContext provider that fetches /setup/status"
```

---

## Task 18: Frontend — `WizardShell` (card + header + progress + footer)

**Files:**
- Create: `frontend/src/setup/WizardShell.tsx`
- Create: `frontend/src/setup/WizardFooter.tsx`
- Create: `frontend/src/setup/WizardProgress.tsx`
- Test: `frontend/src/setup/WizardShell.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/setup/WizardShell.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WizardShell } from "./WizardShell";

describe("WizardShell", () => {
  it("renders title + step indicator + children", () => {
    render(
      <WizardShell title="Welcome" stepIndex={0} totalSteps={5}>
        <p>step body</p>
      </WizardShell>,
    );
    expect(screen.getByRole("dialog", { name: "Welcome" })).toBeInTheDocument();
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
    expect(screen.getByText("step body")).toBeInTheDocument();
  });

  it("progress bar reflects stepIndex/totalSteps", () => {
    render(
      <WizardShell title="Models" stepIndex={2} totalSteps={5}>
        <p>body</p>
      </WizardShell>,
    );
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuemax", "5");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- WizardShell.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the shell + subcomponents**

Create `frontend/src/setup/WizardProgress.tsx`:

```tsx
export function WizardProgress({ value, max }: { value: number; max: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemax={max}
      aria-valuemin={0}
      className="h-0.5 bg-[--color-border-subtle]"
    >
      <div
        className="h-full bg-[--color-accent-primary] transition-[width] duration-200 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
```

Create `frontend/src/setup/WizardFooter.tsx`:

```tsx
import type { ReactNode } from "react";

export function WizardFooter({
  onBack,
  onNext,
  nextLabel = "Next",
  nextDisabled,
  loading,
  rightSlot,
}: {
  onBack?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  loading?: boolean;
  rightSlot?: ReactNode;
}) {
  return (
    <div className="h-16 flex items-center justify-between px-6 border-t border-[--color-border-subtle]">
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          className="h-10 px-4 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          Back
        </button>
      ) : (
        <span />
      )}
      <div className="flex items-center gap-3">
        {rightSlot}
        {onNext ? (
          <button
            type="button"
            onClick={onNext}
            disabled={nextDisabled || loading}
            className={
              nextDisabled || loading
                ? "h-10 px-5 rounded-[--radius-md] text-sm font-medium bg-[--color-surface-active] text-[--color-text-tertiary] cursor-not-allowed"
                : "h-10 px-5 rounded-[--radius-md] text-sm font-medium bg-[--color-accent-primary] text-white hover:bg-[--color-accent-hover]"
            }
          >
            {loading ? "Saving…" : nextLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}
```

Create `frontend/src/setup/WizardShell.tsx`:

```tsx
import type { ReactNode } from "react";
import { WizardProgress } from "./WizardProgress";

interface Props {
  title: string;
  stepIndex: number;
  totalSteps: number;
  children: ReactNode;
  footer?: ReactNode;
}

export function WizardShell({ title, stepIndex, totalSteps, children, footer }: Props) {
  const titleId = "wizard-title";
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-label={title}
      className="fixed inset-0 bg-[--color-bg-base] overflow-auto"
    >
      <div className="max-w-[880px] w-[90%] mx-auto my-10 bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-md border border-[--color-border-subtle]">
        <header className="h-14 flex items-center justify-between px-6 border-b border-[--color-border-subtle]">
          <h1 id={titleId} className="text-lg font-semibold text-[--color-text-primary]">
            {title}
          </h1>
          <span className="text-xs text-[--color-text-secondary]">
            Step {stepIndex + 1} of {totalSteps}
          </span>
        </header>
        <WizardProgress value={stepIndex} max={totalSteps} />
        <div className="px-8 py-6">
          <div className="max-w-[640px] mx-auto">{children}</div>
        </div>
        {footer}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- WizardShell.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/WizardShell.tsx frontend/src/setup/WizardFooter.tsx \
        frontend/src/setup/WizardProgress.tsx frontend/src/setup/WizardShell.test.tsx
git commit -m "feat(frontend): add WizardShell + WizardFooter + WizardProgress primitives"
```

---

## Task 19: Frontend — Step 1: `ModeStep`

**Files:**
- Create: `frontend/src/setup/steps/ModeStep.tsx`
- Test: `frontend/src/setup/steps/ModeStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/setup/steps/ModeStep.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModeStep } from "./ModeStep";

describe("ModeStep", () => {
  it("disables Next until a card is selected", () => {
    render(<ModeStep envLocked={false} initialMode={null} onSaved={vi.fn()} />);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("saves and advances on Next when Personal is picked", async () => {
    const onSaved = vi.fn();
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ mode: "personal" }), { status: 200 }));

    render(<ModeStep envLocked={false} initialMode={null} onSaved={onSaved} />);
    await userEvent.click(screen.getByRole("button", { name: /^personal$/i }));
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith("personal"));
    expect(fetchSpy).toHaveBeenCalled();
  });

  it("shows from-environment badge when envLocked", () => {
    render(<ModeStep envLocked={true} initialMode="company" onSaved={vi.fn()} />);
    expect(screen.getByText(/from environment/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- ModeStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the step**

Create `frontend/src/setup/steps/ModeStep.tsx`:

```tsx
import { useState } from "react";
import { User, Users } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { setMode } from "../../api/setup";
import type { Mode } from "../../api/setup";

interface Props {
  envLocked: boolean;
  initialMode: Mode | null;
  onSaved: (mode: Mode) => void;
}

function ModeCard({
  title,
  description,
  icon: Icon,
  selected,
  disabled,
  onClick,
  envBadge,
}: {
  title: string;
  description: string;
  icon: typeof User;
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
  envBadge?: boolean;
}) {
  const base =
    "flex-1 p-6 border rounded-[--radius-lg] bg-[--color-bg-elevated] cursor-pointer text-left transition-colors";
  const selectedCls = "border-[--color-accent-primary] ring-2 ring-[--focus-ring-color]";
  const unselectedCls = "border-[--color-border-subtle] hover:border-[--color-border-secondary]";
  const disabledCls = "opacity-50 cursor-not-allowed";

  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      className={`${base} ${selected ? selectedCls : unselectedCls} ${disabled ? disabledCls : ""}`}
    >
      <div className="flex items-start justify-between">
        <Icon size={32} className="text-[--color-accent-primary]" />
        {envBadge ? (
          <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded-[--radius-sm] bg-[--color-surface-active] text-[--color-text-tertiary]">
            from environment
          </span>
        ) : null}
      </div>
      <div className="text-lg font-semibold text-[--color-text-primary] mt-3 mb-1">{title}</div>
      <div className="text-sm text-[--color-text-secondary] leading-relaxed">{description}</div>
    </button>
  );
}

export function ModeStep({ envLocked, initialMode, onSaved }: Props) {
  const [selected, setSelected] = useState<Mode | null>(initialMode);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onNext = async () => {
    if (\!selected) return;
    setLoading(true);
    setError(null);
    try {
      await setMode(selected);
      onSaved(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save mode.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Welcome"
      stepIndex={0}
      totalSteps={5}
      footer={
        <WizardFooter onNext={onNext} nextDisabled={\!selected} loading={loading} />
      }
    >
      <p className="text-sm text-[--color-text-secondary] mb-6">
        Pick how you'll run OpenLIA. You can change this later by resetting the wizard.
      </p>
      <div className="flex gap-4">
        <ModeCard
          title="Personal"
          description="Single user on localhost. No auth. Fastest path to trying OpenLIA."
          icon={User}
          selected={selected === "personal"}
          disabled={envLocked && initialMode \!== "personal"}
          envBadge={envLocked && initialMode === "personal"}
          onClick={() => \!envLocked && setSelected("personal")}
        />
        <ModeCard
          title="Company"
          description="Multi-user deployment with logins and invite-gated signup. Binds to 0.0.0.0 by default."
          icon={Users}
          selected={selected === "company"}
          disabled={envLocked && initialMode \!== "company"}
          envBadge={envLocked && initialMode === "company"}
          onClick={() => \!envLocked && setSelected("company")}
        />
      </div>
      {error ? <p className="text-sm text-[--color-feedback-error] mt-4">{error}</p> : null}
      <p className="text-xs text-[--color-text-tertiary] mt-8">
        Trying to use a company deployment someone else set up? Close this and open the URL your
        admin gave you — no install needed.
      </p>
    </WizardShell>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- ModeStep.test.tsx`
Expected: all 3 pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/ModeStep.tsx frontend/src/setup/steps/ModeStep.test.tsx
git commit -m "feat(frontend): add Step 1 ModeStep with env-lock handling"
```

---

## Task 20: Frontend — Step 2a: `IdentityStep` (personal)

**Files:**
- Create: `frontend/src/setup/steps/IdentityStep.tsx`
- Test: `frontend/src/setup/steps/IdentityStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IdentityStep } from "./IdentityStep";

describe("IdentityStep", () => {
  it("disables Next when display name is empty", () => {
    render(<IdentityStep onBack={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("posts display name and calls onSaved", async () => {
    const onSaved = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ display_name: "TK" }), { status: 200 }),
    );

    render(<IdentityStep onBack={vi.fn()} onSaved={onSaved} />);
    await userEvent.type(screen.getByLabelText(/display name/i), "TK");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- IdentityStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the step**

Create `frontend/src/setup/steps/IdentityStep.tsx`:

```tsx
import { useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { FormField } from "../../auth/FormField";
import { setIdentity } from "../../api/setup";

export function IdentityStep({
  onBack,
  onSaved,
}: {
  onBack: () => void;
  onSaved: () => void;
}) {
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await setIdentity(displayName.trim());
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save identity.");
    } finally {
      setLoading(false);
    }
  };

  const valid = displayName.trim().length >= 1 && displayName.trim().length <= 60;

  return (
    <WizardShell
      title="Your name"
      stepIndex={1}
      totalSteps={5}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onNext}
          nextDisabled={\!valid}
          loading={loading}
        />
      }
    >
      <p className="text-sm text-[--color-text-secondary] mb-6">
        This is the name LIA departments will use when addressing you.
      </p>
      <FormField
        id="display_name"
        label="Display name"
        value={displayName}
        onChange={setDisplayName}
        error={error}
        required
        maxLength={60}
      />
    </WizardShell>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- IdentityStep.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/IdentityStep.tsx frontend/src/setup/steps/IdentityStep.test.tsx
git commit -m "feat(frontend): add Step 2a IdentityStep for personal mode"
```

---

## Task 21: Frontend — Step 2b: `AdminAccountStep` (company)

**Files:**
- Create: `frontend/src/setup/steps/AdminAccountStep.tsx`
- Test: `frontend/src/setup/steps/AdminAccountStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminAccountStep } from "./AdminAccountStep";

describe("AdminAccountStep", () => {
  it("disables Next until all fields valid and passwords match", async () => {
    render(<AdminAccountStep onBack={vi.fn()} onSaved={vi.fn()} />);
    const next = screen.getByRole("button", { name: /next/i });
    expect(next).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/email/i), "boss@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "CorrectHorseBattery9\!");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "CorrectHorseBattery9\!");
    await userEvent.type(screen.getByLabelText(/display name/i), "Boss");
    expect(next).toBeEnabled();
  });

  it("shows mismatch error when passwords differ", async () => {
    render(<AdminAccountStep onBack={vi.fn()} onSaved={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/^password$/i), "CorrectHorseBattery9\!");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "different");
    expect(screen.getByText(/passwords don't match/i)).toBeInTheDocument();
  });

  it("posts payload and calls onSaved", async () => {
    const onSaved = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ email: "boss@example.com" }), { status: 200 }),
    );

    render(<AdminAccountStep onBack={vi.fn()} onSaved={onSaved} />);
    await userEvent.type(screen.getByLabelText(/email/i), "boss@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "CorrectHorseBattery9\!");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "CorrectHorseBattery9\!");
    await userEvent.type(screen.getByLabelText(/display name/i), "Boss");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- AdminAccountStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the step**

Create `frontend/src/setup/steps/AdminAccountStep.tsx`:

```tsx
import { useMemo, useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { FormField } from "../../auth/FormField";
import { PasswordInput } from "../../auth/PasswordInput";
import { PasswordStrengthMeter } from "../../auth/PasswordStrengthMeter";
import { passwordStrength } from "../../auth/passwordStrength";
import { setAdmin } from "../../api/setup";

export function AdminAccountStep({
  onBack,
  onSaved,
}: {
  onBack: () => void;
  onSaved: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  const passwordValid = password.length >= 12;
  const passwordsMatch = password === confirm;
  const nameValid = displayName.trim().length >= 1;
  const canSubmit = emailValid && passwordValid && passwordsMatch && nameValid;
  const strength = useMemo(() => passwordStrength(password), [password]);

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await setAdmin({ email, password, display_name: displayName.trim() });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create admin.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Admin account"
      stepIndex={1}
      totalSteps={6}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onNext}
          nextDisabled={\!canSubmit}
          loading={loading}
        />
      }
    >
      <p className="text-sm text-[--color-text-secondary] mb-6">
        You are creating the first administrator for this deployment. Additional users sign up on
        the login page per the policy you'll choose later.
      </p>
      <div className="flex flex-col gap-5">
        <FormField
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          error={email && \!emailValid ? "Enter a valid email." : null}
          required
        />
        <div>
          <PasswordInput
            id="password"
            label="Password"
            value={password}
            onChange={setPassword}
            error={password && \!passwordValid ? "Must be at least 12 characters." : null}
          />
          <PasswordStrengthMeter score={strength} />
        </div>
        <PasswordInput
          id="confirm_password"
          label="Confirm password"
          value={confirm}
          onChange={setConfirm}
          error={confirm && \!passwordsMatch ? "Passwords don't match." : null}
        />
        <FormField
          id="display_name"
          label="Display name"
          value={displayName}
          onChange={setDisplayName}
          required
          maxLength={60}
        />
      </div>
      {error ? <p className="text-sm text-[--color-feedback-error] mt-4">{error}</p> : null}
    </WizardShell>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- AdminAccountStep.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/AdminAccountStep.tsx frontend/src/setup/steps/AdminAccountStep.test.tsx
git commit -m "feat(frontend): add Step 2b AdminAccountStep with validation and strength meter"
```

---

## Task 22: Frontend — Step 3: `ModelsStep` + `TierSlotCard`

**Files:**
- Create: `frontend/src/setup/steps/TierSlotCard.tsx`
- Create: `frontend/src/setup/steps/ModelsStep.tsx`
- Test: `frontend/src/setup/steps/ModelsStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelsStep } from "./ModelsStep";

describe("ModelsStep", () => {
  it("disables Next when any required tier has no entries", () => {
    render(
      <ModelsStep
        totalSteps={5}
        requiredTiers={["thinking", "everyday", "quick"]}
        onBack={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("enables Next after adding a model in each required tier", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true, latency_ms: 42, error: null }), { status: 200 }),
    );

    render(
      <ModelsStep
        totalSteps={5}
        requiredTiers={["thinking", "everyday", "quick"]}
        onBack={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    for (const tier of ["thinking", "everyday", "quick"]) {
      const section = screen.getByTestId(`tier-${tier}`);
      await userEvent.click(section.querySelector("button[data-test=add]")\!);
      await userEvent.type(section.querySelector("input[name=model]")\!, "gpt-5.4");
      await userEvent.type(section.querySelector("input[name=api_key]")\!, "sk-test");
      await userEvent.click(section.querySelector("button[data-test=test]")\!);
    }
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeEnabled(),
    );
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- ModelsStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `TierSlotCard`**

Create `frontend/src/setup/steps/TierSlotCard.tsx`:

```tsx
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { TierEntry } from "../../api/setup";
import { testModel } from "../../api/setup";

const PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Google Gemini" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "openai_compat", label: "OpenAI-compatible" },
  { value: "ollama", label: "Ollama (local)" },
];

export interface TierEntryWithStatus extends TierEntry {
  ui_id: string;
  status: "untested" | "testing" | "ok" | "error";
  error?: string | null;
}

export function TierSlotCard({
  tierLabel,
  tierValue,
  entries,
  onChange,
}: {
  tierLabel: string;
  tierValue: "thinking" | "everyday" | "quick";
  entries: TierEntryWithStatus[];
  onChange: (entries: TierEntryWithStatus[]) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<TierEntry>({ provider: "openai", model: "", api_key: "" });

  const runTest = async (entry: TierEntryWithStatus) => {
    onChange(
      entries.map((e) => (e.ui_id === entry.ui_id ? { ...e, status: "testing", error: null } : e)),
    );
    try {
      const result = await testModel({
        provider: entry.provider,
        model: entry.model,
        api_key: entry.api_key,
        base_url: entry.base_url,
      });
      onChange(
        entries.map((e) =>
          e.ui_id === entry.ui_id
            ? { ...e, status: result.ok ? "ok" : "error", error: result.error }
            : e,
        ),
      );
    } catch (err) {
      onChange(
        entries.map((e) =>
          e.ui_id === entry.ui_id
            ? { ...e, status: "error", error: err instanceof Error ? err.message : "test failed" }
            : e,
        ),
      );
    }
  };

  const addEntry = () => {
    const ui_id = crypto.randomUUID();
    onChange([...entries, { ...draft, ui_id, status: "untested" }]);
    setAdding(false);
    setDraft({ provider: "openai", model: "", api_key: "" });
  };

  const removeEntry = (ui_id: string) => {
    onChange(entries.filter((e) => e.ui_id \!== ui_id));
  };

  return (
    <section
      data-testid={`tier-${tierValue}`}
      className="border border-[--color-border-subtle] rounded-[--radius-md] p-4 mb-4"
    >
      <h3 className="text-sm font-semibold text-[--color-text-primary] mb-3">{tierLabel}</h3>
      <ul className="flex flex-col gap-2 mb-3">
        {entries.map((entry) => (
          <li
            key={entry.ui_id}
            className="flex items-center justify-between px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base]"
          >
            <div className="flex items-center gap-3">
              <span className="text-xs text-[--color-text-tertiary]">{entry.provider}</span>
              <span className="text-sm text-[--color-text-primary]">{entry.model}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  entry.status === "ok"
                    ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
                    : entry.status === "error"
                      ? "bg-[--color-feedback-error]/15 text-[--color-feedback-error]"
                      : "bg-[--color-surface-active] text-[--color-text-tertiary]"
                }`}
              >
                {entry.status}
              </span>
            </div>
            <button
              type="button"
              aria-label="Remove model"
              onClick={() => removeEntry(entry.ui_id)}
              className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
            >
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
      {adding ? (
        <div className="flex flex-col gap-2 border border-[--color-border-subtle] rounded-[--radius-md] p-3 bg-[--color-bg-base]">
          <select
            value={draft.provider}
            onChange={(e) => setDraft({ ...draft, provider: e.target.value })}
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          >
            {PROVIDER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <input
            name="model"
            value={draft.model}
            onChange={(e) => setDraft({ ...draft, model: e.target.value })}
            placeholder="Model ID"
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
          <input
            name="api_key"
            type="password"
            value={draft.api_key ?? ""}
            onChange={(e) => setDraft({ ...draft, api_key: e.target.value })}
            placeholder="API key"
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              data-test="cancel"
              className="h-8 px-3 rounded-[--radius-md] text-sm text-[--color-text-secondary]"
              onClick={() => setAdding(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              data-test="test"
              onClick={async () => {
                const ui_id = crypto.randomUUID();
                const newEntry: TierEntryWithStatus = {
                  ...draft,
                  ui_id,
                  status: "testing",
                };
                const next = [...entries, newEntry];
                onChange(next);
                setAdding(false);
                setDraft({ provider: "openai", model: "", api_key: "" });
                await runTest(newEntry);
              }}
              className="h-8 px-3 rounded-[--radius-md] text-sm border border-[--color-border-secondary]"
            >
              Test & Save
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          data-test="add"
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-2 h-8 px-3 rounded-[--radius-md] border border-dashed border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          <Plus size={14} />
          Add model
        </button>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Implement `ModelsStep`**

Create `frontend/src/setup/steps/ModelsStep.tsx`:

```tsx
import { useMemo, useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { TierSlotCard } from "./TierSlotCard";
import type { TierEntryWithStatus } from "./TierSlotCard";
import { saveModels } from "../../api/setup";

type TierName = "thinking" | "everyday" | "quick";

export function ModelsStep({
  totalSteps,
  requiredTiers,
  onBack,
  onSaved,
}: {
  totalSteps: number;
  requiredTiers: TierName[];
  onBack: () => void;
  onSaved: () => void;
}) {
  const [thinking, setThinking] = useState<TierEntryWithStatus[]>([]);
  const [everyday, setEveryday] = useState<TierEntryWithStatus[]>([]);
  const [quick, setQuick] = useState<TierEntryWithStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tierHasGreen = (entries: TierEntryWithStatus[]) =>
    entries.some((e) => e.status === "ok");

  const canSubmit = useMemo(
    () =>
      requiredTiers.every((tier) => {
        if (tier === "thinking") return tierHasGreen(thinking);
        if (tier === "everyday") return tierHasGreen(everyday);
        return tierHasGreen(quick);
      }),
    [requiredTiers, thinking, everyday, quick],
  );

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await saveModels({
        thinking: thinking.filter((e) => e.status === "ok").map(stripUi),
        everyday: everyday.filter((e) => e.status === "ok").map(stripUi),
        quick: quick.filter((e) => e.status === "ok").map(stripUi),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save models.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="AI Models"
      stepIndex={2}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onNext}
          nextDisabled={\!canSubmit}
          loading={loading}
        />
      }
    >
      <p className="text-sm text-[--color-text-secondary] mb-4">
        OpenLIA uses a top-tier Thinking model for deep analysis, an Everyday model for general
        chat, and a Quick model for classification and lightweight jobs.
      </p>
      <p className="text-xs text-[--color-text-tertiary] mb-6">
        Required by your enabled departments:{" "}
        <strong>{requiredTiers.join(", ")}</strong>.
      </p>
      <TierSlotCard tierLabel="Thinking" tierValue="thinking" entries={thinking} onChange={setThinking} />
      <TierSlotCard tierLabel="Everyday" tierValue="everyday" entries={everyday} onChange={setEveryday} />
      <TierSlotCard tierLabel="Quick" tierValue="quick" entries={quick} onChange={setQuick} />
      {error ? <p className="text-sm text-[--color-feedback-error] mt-4">{error}</p> : null}
    </WizardShell>
  );
}

function stripUi(e: TierEntryWithStatus) {
  const { ui_id, status, error, ...rest } = e;
  return rest;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- ModelsStep.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/setup/steps/ModelsStep.tsx \
        frontend/src/setup/steps/TierSlotCard.tsx \
        frontend/src/setup/steps/ModelsStep.test.tsx
git commit -m "feat(frontend): add Step 3 ModelsStep with per-tier add/test flow"
```

---

## Task 23: Frontend — Step 4: `ProvidersStep` + `AddProviderForm` + `MCPInfoCard`

**Files:**
- Create: `frontend/src/setup/steps/MCPInfoCard.tsx`
- Create: `frontend/src/setup/steps/AddProviderForm.tsx`
- Create: `frontend/src/setup/steps/ProviderRow.tsx`
- Create: `frontend/src/setup/steps/ProvidersStep.tsx`
- Test: `frontend/src/setup/steps/ProvidersStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProvidersStep } from "./ProvidersStep";

describe("ProvidersStep", () => {
  it("renders 4 category tabs and list of providers", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ providers: [] }), { status: 200 }),
    );

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole("tablist")).toBeInTheDocument());
    expect(screen.getByRole("tab", { name: /financial/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /news/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /social/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /web search/i })).toBeInTheDocument();
  });

  it("gate: Next disabled until ≥1 financial AND ≥1 news provider green", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          providers: [
            { id: "p1", category: "financial", mode: "builtin", provider: "eodhd", priority: 0, status: "ok" },
          ],
        }),
        { status: 200 },
      ),
    );

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => screen.getByRole("tablist"));
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- ProvidersStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `MCPInfoCard`**

Create `frontend/src/setup/steps/MCPInfoCard.tsx`:

```tsx
import { Info } from "lucide-react";

export function MCPInfoCard() {
  return (
    <div className="bg-[--color-surface-info]/10 border border-[--color-surface-info]/30 rounded-[--radius-md] p-3 mb-4 flex gap-3">
      <Info size={16} className="text-[--color-surface-info] mt-0.5 flex-shrink-0" />
      <div>
        <p className="text-sm font-semibold text-[--color-text-primary] mb-1">
          MCP authentication
        </p>
        <p className="text-sm text-[--color-text-secondary] leading-relaxed">
          OpenLIA doesn't support OAuth for MCP providers. If your endpoint requires
          authentication, include your API key directly in the URL as a query parameter:
        </p>
        <code className="text-xs font-mono bg-[--color-surface-active] px-2 py-1 rounded-[--radius-sm] inline-block mt-1 break-all">
          https://mcp.example.com/sse?api_key=sk_live_xxxxxxxxxxxxxxxx
        </code>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement `AddProviderForm`**

Create `frontend/src/setup/steps/AddProviderForm.tsx`:

```tsx
import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { MCPInfoCard } from "./MCPInfoCard";
import { addProvider } from "../../api/setup";
import type { ProviderEntry } from "../../api/setup";

type Mode = "builtin" | "mcp" | "openapi";
type Category = "financial" | "news" | "social" | "web_search";

const BUILTIN_CATALOG: Record<Category, { value: string; label: string }[]> = {
  financial: [
    { value: "eodhd", label: "EODHD" },
    { value: "fmp", label: "Financial Modeling Prep" },
    { value: "finnhub", label: "Finnhub" },
  ],
  news: [
    { value: "newsapi_ai", label: "News API AI" },
    { value: "mediastack", label: "Mediastack" },
  ],
  social: [
    { value: "reddit", label: "Reddit" },
    { value: "x", label: "X / Twitter" },
  ],
  web_search: [
    { value: "brave", label: "Brave Search" },
    { value: "tavily", label: "Tavily" },
    { value: "serper", label: "Serper" },
  ],
};

export function AddProviderForm({
  category,
  onCancel,
  onSaved,
}: {
  category: Category;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const allowMcp = category \!== "web_search";
  const [mode, setMode] = useState<Mode>("builtin");
  const [builtinProvider, setBuiltinProvider] = useState<string>(
    BUILTIN_CATALOG[category][0]?.value ?? "",
  );
  const [apiKey, setApiKey] = useState("");
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpAuth, setMcpAuth] = useState("");
  const [openapiUrl, setOpenapiUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSave = async () => {
    setLoading(true);
    setError(null);
    const entry: ProviderEntry =
      mode === "builtin"
        ? { mode: "builtin", provider: builtinProvider, api_key: apiKey }
        : mode === "mcp"
          ? { mode: "mcp", mcp_url: mcpUrl, mcp_auth_header: mcpAuth || undefined }
          : { mode: "openapi", openapi_spec_url: openapiUrl, api_key: apiKey };
    try {
      await addProvider({ category, entry });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add provider.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={onCancel}
        className="inline-flex items-center gap-1 text-sm text-[--color-text-secondary] mb-3"
      >
        <ChevronLeft size={14} />
        Back to list
      </button>
      <h3 className="text-lg font-semibold text-[--color-text-primary] mb-4">
        Add {category} provider
      </h3>
      <div className="flex p-1 bg-[--color-surface-hover] rounded-[--radius-md] w-fit mb-5">
        {(["builtin", "mcp", "openapi"] as Mode[]).map((m) => {
          const disabled = m === "mcp" && \!allowMcp;
          return (
            <button
              key={m}
              type="button"
              disabled={disabled}
              onClick={() => \!disabled && setMode(m)}
              className={`px-3 py-1.5 rounded-[--radius-sm] text-sm capitalize ${
                mode === m ? "bg-[--color-bg-elevated] shadow-sm font-medium" : ""
              } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              {m === "mcp" ? "MCP URL" : m === "openapi" ? "OpenAPI" : "Built-in"}
            </button>
          );
        })}
      </div>

      {mode === "builtin" ? (
        <>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">Provider</span>
            <select
              value={builtinProvider}
              onChange={(e) => setBuiltinProvider(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            >
              {BUILTIN_CATALOG[category].map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
        </>
      ) : mode === "mcp" ? (
        <>
          <MCPInfoCard />
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">MCP URL</span>
            <input
              value={mcpUrl}
              onChange={(e) => setMcpUrl(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <details className="mb-5">
            <summary className="text-sm text-[--color-text-secondary] cursor-pointer">Advanced</summary>
            <label className="flex flex-col gap-1.5 mt-3">
              <span className="text-sm font-medium text-[--color-text-primary]">Auth header</span>
              <input
                value={mcpAuth}
                onChange={(e) => setMcpAuth(e.target.value)}
                placeholder="Bearer sk_…"
                className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
              />
            </label>
          </details>
        </>
      ) : (
        <>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">OpenAPI spec URL</span>
            <input
              value={openapiUrl}
              onChange={(e) => setOpenapiUrl(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
        </>
      )}

      {error ? <p className="text-sm text-[--color-feedback-error] mb-3">{error}</p> : null}
      <div className="flex justify-end gap-2 mt-6">
        <button
          type="button"
          onClick={onCancel}
          className="h-9 px-3 rounded-[--radius-md] text-sm text-[--color-text-secondary]"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={loading}
          className="h-9 px-3 rounded-[--radius-md] text-sm bg-[--color-accent-primary] text-white"
        >
          {loading ? "Testing…" : "Test & Save"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implement `ProviderRow`**

Create `frontend/src/setup/steps/ProviderRow.tsx`:

```tsx
import { Trash2, GripVertical } from "lucide-react";
import type { ProviderRow as Row } from "../../api/setup";

export function ProviderRow({
  row,
  priorityIndex,
  onRemove,
}: {
  row: Row;
  priorityIndex: number;
  onRemove: () => void;
}) {
  const pillCls =
    row.status === "ok"
      ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
      : "bg-[--color-feedback-error]/15 text-[--color-feedback-error]";

  return (
    <li className="flex items-center justify-between px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base] mb-2">
      <div className="flex items-center gap-3">
        <GripVertical size={14} className="text-[--color-text-tertiary] cursor-grab" />
        <span className="text-xs text-[--color-text-tertiary] w-4">{priorityIndex}</span>
        <span className="text-sm text-[--color-text-primary] font-medium">
          {row.provider ?? row.mode}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${pillCls}`}>{row.status}</span>
      </div>
      <button
        type="button"
        aria-label="Remove provider"
        onClick={onRemove}
        className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
      >
        <Trash2 size={14} />
      </button>
    </li>
  );
}
```

- [ ] **Step 6: Implement `ProvidersStep`**

Create `frontend/src/setup/steps/ProvidersStep.tsx`:

```tsx
import { useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { ProviderRow } from "./ProviderRow";
import { AddProviderForm } from "./AddProviderForm";
import { deleteProvider, listProviders } from "../../api/setup";
import type { ProviderRow as Row } from "../../api/setup";

type Category = "financial" | "news" | "social" | "web_search";
const CATEGORIES: { value: Category; label: string; required?: boolean }[] = [
  { value: "financial", label: "Financial", required: true },
  { value: "news", label: "News", required: true },
  { value: "social", label: "Social" },
  { value: "web_search", label: "Web Search" },
];

export function ProvidersStep({
  totalSteps,
  onBack,
  onSaved,
}: {
  totalSteps: number;
  onBack: () => void;
  onSaved: () => void;
}) {
  const [active, setActive] = useState<Category>("financial");
  const [rows, setRows] = useState<Row[]>([]);
  const [adding, setAdding] = useState(false);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    const resp = await listProviders();
    setRows(resp.providers);
  };

  useEffect(() => {
    void refresh();
  }, []);

  const byCategory = useMemo(() => {
    const out: Record<Category, Row[]> = { financial: [], news: [], social: [], web_search: [] };
    for (const r of rows) out[r.category as Category]?.push(r);
    return out;
  }, [rows]);

  const canAdvance =
    byCategory.financial.some((r) => r.status === "ok") &&
    byCategory.news.some((r) => r.status === "ok");

  const onNext = async () => {
    setLoading(true);
    try {
      onSaved();
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Data Providers"
      stepIndex={3}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onNext}
          nextDisabled={\!canAdvance}
          loading={loading}
        />
      }
    >
      <div className="flex gap-6">
        <nav role="tablist" aria-label="Provider categories" className="w-44 flex-shrink-0">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              role="tab"
              aria-selected={active === cat.value}
              onClick={() => {
                setActive(cat.value);
                setAdding(false);
              }}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-[--radius-md] text-sm cursor-pointer ${
                active === cat.value
                  ? "bg-[--color-surface-active] text-[--color-text-primary] font-medium"
                  : "text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
              }`}
            >
              <span>
                {cat.label}
                {cat.required ? " *" : ""}
              </span>
              <span className="text-[10px] px-1.5 py-0.5 bg-[--color-surface-hover] rounded-full text-[--color-text-tertiary]">
                {byCategory[cat.value].length}
              </span>
            </button>
          ))}
        </nav>
        <section role="tabpanel" aria-label={active} className="flex-1 min-w-0">
          {adding ? (
            <AddProviderForm
              category={active}
              onCancel={() => setAdding(false)}
              onSaved={async () => {
                setAdding(false);
                await refresh();
              }}
            />
          ) : (
            <>
              <ul className="flex flex-col">
                {byCategory[active].map((r, i) => (
                  <ProviderRow
                    key={r.id}
                    row={r}
                    priorityIndex={i}
                    onRemove={async () => {
                      await deleteProvider(r.id);
                      await refresh();
                    }}
                  />
                ))}
              </ul>
              <button
                type="button"
                onClick={() => setAdding(true)}
                className="inline-flex items-center gap-2 h-8 px-3 rounded-[--radius-md] border border-dashed border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
              >
                <Plus size={14} />
                Add {active.replace("_", " ")} provider
              </button>
            </>
          )}
        </section>
      </div>
    </WizardShell>
  );
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd frontend && npm test -- ProvidersStep.test.tsx`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/setup/steps/MCPInfoCard.tsx \
        frontend/src/setup/steps/AddProviderForm.tsx \
        frontend/src/setup/steps/ProviderRow.tsx \
        frontend/src/setup/steps/ProvidersStep.tsx \
        frontend/src/setup/steps/ProvidersStep.test.tsx
git commit -m "feat(frontend): add Step 4 ProvidersStep with sidebar tabs, add-form, and gate"
```

---

## Task 24: Frontend — Step 5: `AccessControlStep` (company)

**Files:**
- Create: `frontend/src/setup/steps/AccessControlStep.tsx`
- Test: `frontend/src/setup/steps/AccessControlStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccessControlStep } from "./AccessControlStep";

describe("AccessControlStep", () => {
  it("posts policy + bind host/port", async () => {
    const onSaved = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    render(<AccessControlStep onBack={vi.fn()} onSaved={onSaved} />);
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("disables the 'open signup' option (v2 only)", () => {
    render(<AccessControlStep onBack={vi.fn()} onSaved={vi.fn()} />);
    const open = screen.getByRole("radio", { name: /open signup/i });
    expect(open).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- AccessControlStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the step**

Create `frontend/src/setup/steps/AccessControlStep.tsx`:

```tsx
import { useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { setAccessControl } from "../../api/setup";

type Policy = "invite_only" | "closed";

export function AccessControlStep({
  onBack,
  onSaved,
}: {
  onBack: () => void;
  onSaved: () => void;
}) {
  const [policy, setPolicy] = useState<Policy>("invite_only");
  const [domains, setDomains] = useState("");
  const [host, setHost] = useState("0.0.0.0");
  const [port, setPort] = useState(8000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await setAccessControl({
        signup_policy: policy,
        allowed_domains: domains.trim() || undefined,
        bind_host: host,
        bind_port: port,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save access control.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Access Control"
      stepIndex={4}
      totalSteps={6}
      footer={<WizardFooter onBack={onBack} onNext={onNext} loading={loading} />}
    >
      <fieldset className="mb-6">
        <legend className="text-sm font-medium text-[--color-text-primary] mb-2">
          Signup policy
        </legend>
        <label className="flex items-start gap-3 mb-2 cursor-pointer">
          <input
            type="radio"
            name="policy"
            checked={policy === "invite_only"}
            onChange={() => setPolicy("invite_only")}
          />
          <span>
            <strong className="text-sm">Invite-only</strong>
            <p className="text-xs text-[--color-text-secondary]">
              Create invite links in Settings after setup. Share them with your team.
            </p>
          </span>
        </label>
        <label className="flex items-start gap-3 mb-2 cursor-pointer">
          <input
            type="radio"
            name="policy"
            checked={policy === "closed"}
            onChange={() => setPolicy("closed")}
          />
          <span>
            <strong className="text-sm">Closed</strong>
            <p className="text-xs text-[--color-text-secondary]">
              No public registration; admin creates accounts manually via CLI.
            </p>
          </span>
        </label>
        <label className="flex items-start gap-3 mb-2 cursor-not-allowed opacity-60">
          <input type="radio" name="policy" disabled />
          <span>
            <strong className="text-sm">Open signup</strong>
            <p className="text-xs text-[--color-text-secondary]">Coming soon.</p>
          </span>
        </label>
      </fieldset>
      <label className="flex flex-col gap-1.5 mb-5">
        <span className="text-sm font-medium text-[--color-text-primary]">
          Allowed email domains (optional)
        </span>
        <input
          value={domains}
          onChange={(e) => setDomains(e.target.value)}
          placeholder="example.com, acme.com"
          className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
        />
      </label>
      <div className="grid grid-cols-2 gap-4 mb-5">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-[--color-text-primary]">Bind host</span>
          <input
            value={host}
            onChange={(e) => setHost(e.target.value)}
            className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-[--color-text-primary]">Bind port</span>
          <input
            type="number"
            min={1}
            max={65535}
            value={port}
            onChange={(e) => setPort(Number(e.target.value))}
            className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
        </label>
      </div>
      <p className="text-xs text-[--color-text-tertiary] mb-4">
        Changes to bind address and port take effect after you restart the server.
      </p>
      {error ? <p className="text-sm text-[--color-feedback-error]">{error}</p> : null}
    </WizardShell>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- AccessControlStep.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/AccessControlStep.tsx \
        frontend/src/setup/steps/AccessControlStep.test.tsx
git commit -m "feat(frontend): add Step 5 AccessControlStep for company mode"
```

---

## Task 25: Frontend — Step 6: `ReviewStep`

**Files:**
- Create: `frontend/src/setup/steps/ReviewStep.tsx`
- Test: `frontend/src/setup/steps/ReviewStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewStep } from "./ReviewStep";

describe("ReviewStep", () => {
  it("polls /setup/review/{id} and renders readiness cards", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ review_id: "rev-1" }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            state: "complete",
            progress: 100,
            result: {
              summary: "1 of 1 ready.",
              departments: [
                {
                  id: "secretary",
                  state: "ready",
                  note: null,
                  basic: [{ type: "stock_quote", provider: "eodhd", confidence: 0.9 }],
                  advanced: [],
                  unmet: [],
                },
              ],
            },
            error: null,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ redirect: "/", mode: "personal" }), { status: 200 }),
      );

    render(<ReviewStep totalSteps={5} mode="personal" onBack={vi.fn()} />);
    await waitFor(() => screen.getByText(/1 of 1 ready/i));
    expect(screen.getByText(/secretary/i)).toBeInTheDocument();
  });

  it("Finish disabled when a department is blocked", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ review_id: "rev-1" }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            state: "complete",
            progress: 100,
            result: {
              summary: "0 of 1 ready.",
              departments: [
                {
                  id: "equity_research",
                  state: "blocked",
                  note: null,
                  basic: [],
                  advanced: [],
                  unmet: ["stock_quote"],
                },
              ],
            },
            error: null,
          }),
          { status: 200 },
        ),
      );

    render(<ReviewStep totalSteps={5} mode="personal" onBack={vi.fn()} />);
    await waitFor(() => screen.getByText(/0 of 1 ready/i));
    expect(screen.getByRole("button", { name: /finish/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- ReviewStep.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the step**

Create `frontend/src/setup/steps/ReviewStep.tsx`:

```tsx
import { useEffect, useMemo, useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { finish, pollReview, runReview } from "../../api/setup";
import type { Mode, ReviewPoll } from "../../api/setup";

interface ReviewResult {
  summary: string;
  departments: {
    id: string;
    state: "ready" | "gaps" | "disabled" | "blocked";
    note: string | null;
    basic: { type: string; provider: string | null; confidence: number }[];
    advanced: { type: string; provider: string | null; confidence: number }[];
    unmet: string[];
  }[];
}

export function ReviewStep({
  totalSteps,
  mode,
  onBack,
}: {
  totalSteps: number;
  mode: Mode;
  onBack: () => void;
}) {
  const [state, setState] = useState<"starting" | "running" | "complete" | "failed">("starting");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    (async () => {
      try {
        setState("running");
        const { review_id } = await runReview();
        const loop = async () => {
          if (cancelled) return;
          const poll: ReviewPoll = await pollReview(review_id);
          if (poll.state === "complete") {
            setResult(poll.result as ReviewResult);
            setState("complete");
          } else if (poll.state === "failed") {
            setError(poll.error ?? "Review failed.");
            setState("failed");
          } else {
            timer = setTimeout(loop, 1500);
          }
        };
        await loop();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start review.");
        setState("failed");
      }
    })();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const blocked = useMemo(
    () => result?.departments.some((d) => d.state === "blocked") ?? false,
    [result],
  );

  const onFinish = async () => {
    setFinishing(true);
    try {
      const { redirect } = await finish();
      window.location.href = redirect;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finish.");
    } finally {
      setFinishing(false);
    }
  };

  return (
    <WizardShell
      title="Review"
      stepIndex={totalSteps - 1}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onFinish}
          nextLabel="Finish"
          nextDisabled={state \!== "complete" || blocked}
          loading={finishing}
        />
      }
    >
      {state === "running" ? (
        <p className="text-sm text-[--color-text-secondary]">
          Mapping providers to department requirements…
        </p>
      ) : null}
      {state === "failed" ? (
        <p className="text-sm text-[--color-feedback-error]">{error}</p>
      ) : null}
      {state === "complete" && result ? (
        <>
          <p className="text-sm text-[--color-text-primary] font-medium mb-4">{result.summary}</p>
          <div className="grid grid-cols-2 gap-3">
            {result.departments.map((d) => (
              <article
                key={d.id}
                className="border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-elevated] p-4 flex justify-between gap-3"
                style={{
                  borderLeftWidth: 3,
                  borderLeftColor:
                    d.state === "ready"
                      ? "var(--color-feedback-success)"
                      : d.state === "gaps"
                        ? "var(--color-feedback-warning)"
                        : d.state === "blocked"
                          ? "var(--color-feedback-error)"
                          : "var(--color-border-subtle)",
                }}
              >
                <div>
                  <h4 className="text-sm font-semibold text-[--color-text-primary] capitalize">
                    {d.id.replace("_", " ")}
                  </h4>
                  {d.unmet.length > 0 ? (
                    <p className="text-xs text-[--color-text-secondary] mt-1 leading-relaxed">
                      Unmet: {d.unmet.join(", ")}
                    </p>
                  ) : null}
                </div>
                <span
                  aria-label={`${d.id} ${d.state}`}
                  className={`text-xs px-2 py-0.5 rounded-full h-fit ${
                    d.state === "ready"
                      ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
                      : d.state === "gaps"
                        ? "bg-[--color-feedback-warning]/15 text-[--color-feedback-warning]"
                        : d.state === "blocked"
                          ? "bg-[--color-feedback-error]/15 text-[--color-feedback-error]"
                          : "bg-[--color-surface-active] text-[--color-text-tertiary]"
                  }`}
                >
                  {d.state}
                </span>
              </article>
            ))}
          </div>
          {blocked ? (
            <p className="text-sm text-[--color-feedback-error] mt-4">
              Go back to Data Providers to cover the unmet requirements.
            </p>
          ) : null}
        </>
      ) : null}
    </WizardShell>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- ReviewStep.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/ReviewStep.tsx frontend/src/setup/steps/ReviewStep.test.tsx
git commit -m "feat(frontend): add Step 6 ReviewStep with polling + readiness cards + finish"
```

---

## Task 26: Frontend — `SetupPage` + route wiring + entry gate

**Files:**
- Create: `frontend/src/pages/SetupPage.tsx`
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css` (add `--color-surface-info` token)

- [ ] **Step 1: Add `--color-surface-info` token**

In `frontend/src/index.css`, inside `:root`, add:

```css
  --color-surface-info: #3d82f6;
```

And the dark-mode counterpart under `:root.dark` (or equivalent block):

```css
  --color-surface-info: #5a9bff;
```

- [ ] **Step 2: Create `SetupPage`**

Create `frontend/src/pages/SetupPage.tsx`:

```tsx
import { useWizard, WizardProvider } from "../setup/WizardContext";
import { ModeStep } from "../setup/steps/ModeStep";
import { IdentityStep } from "../setup/steps/IdentityStep";
import { AdminAccountStep } from "../setup/steps/AdminAccountStep";
import { ModelsStep } from "../setup/steps/ModelsStep";
import { ProvidersStep } from "../setup/steps/ProvidersStep";
import { AccessControlStep } from "../setup/steps/AccessControlStep";
import { ReviewStep } from "../setup/steps/ReviewStep";

function Inner() {
  const wizard = useWizard();
  if (wizard.state === "loading") {
    return <div className="p-8 text-sm text-[--color-text-secondary]">Loading…</div>;
  }
  if (wizard.state === "error") {
    return (
      <div className="p-8">
        <p className="text-sm text-[--color-feedback-error]">{wizard.message}</p>
        <button
          type="button"
          onClick={wizard.refresh}
          className="mt-3 h-9 px-3 rounded-[--radius-md] text-sm border border-[--color-border-secondary]"
        >
          Retry
        </button>
      </div>
    );
  }

  const { status, refresh } = wizard;
  const total = status.mode === "company" ? 6 : 5;
  const step = status.current_step;
  const envLocked = \!\!status.env_overrides.mode;

  if (step === "mode")
    return <ModeStep envLocked={envLocked} initialMode={envLocked ? status.mode : null} onSaved={refresh} />;
  if (step === "identity") return <IdentityStep onBack={refresh} onSaved={refresh} />;
  if (step === "admin") return <AdminAccountStep onBack={refresh} onSaved={refresh} />;
  if (step === "models")
    return (
      <ModelsStep
        totalSteps={total}
        requiredTiers={["thinking", "everyday", "quick"]}
        onBack={refresh}
        onSaved={refresh}
      />
    );
  if (step === "providers") return <ProvidersStep totalSteps={total} onBack={refresh} onSaved={refresh} />;
  if (step === "access_control") return <AccessControlStep onBack={refresh} onSaved={refresh} />;
  if (step === "review") return <ReviewStep totalSteps={total} mode={status.mode} onBack={refresh} />;
  return <div className="p-8">Unknown step: {step}</div>;
}

export function SetupPage() {
  return (
    <WizardProvider>
      <Inner />
    </WizardProvider>
  );
}
```

- [ ] **Step 3: Add `/setup` route to `router.tsx`**

In `frontend/src/router.tsx`, add to the `createBrowserRouter` tree (before the protected routes):

```typescript
import { SetupPage } from "./pages/SetupPage";

// inside createBrowserRouter children:
  { path: "/setup", element: <SetupPage /> },
```

- [ ] **Step 4: Add a `SetupRedirect` gate at app root**

In `frontend/src/App.tsx` (or wherever the router is rendered), before rendering the `AuthProvider`:

```tsx
import { useEffect, useState } from "react";
import { getStatus } from "./api/setup";

function SetupGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"loading" | "needs_setup" | "done">("loading");

  useEffect(() => {
    void (async () => {
      try {
        const status = await getStatus();
        setState(status.wizard_completed ? "done" : "needs_setup");
      } catch {
        setState("done"); // backend may be unreachable; let AuthProvider handle it
      }
    })();
  }, []);

  if (state === "loading") return null;
  if (state === "needs_setup" && window.location.pathname \!== "/setup") {
    window.location.replace("/setup");
    return null;
  }
  return <>{children}</>;
}
```

Wrap `<App>` content with `<SetupGate>`.

- [ ] **Step 5: Build and smoke-test**

Run: `cd frontend && npm run build`
Expected: exit 0.

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SetupPage.tsx frontend/src/router.tsx frontend/src/App.tsx \
        frontend/src/index.css
git commit -m "feat(frontend): wire /setup route + SetupGate redirect for incomplete wizard"
```

---

## Task 27: Manual smoke test

- [ ] **Step 1: Reset DB state**

Run: `rm -f ~/.openlia/openlia.db`

- [ ] **Step 2: Start the server**

Run: `uv run openlia serve` (in one terminal)

- [ ] **Step 3: Start the frontend**

Run: `cd frontend && npm run dev` (in another terminal)

- [ ] **Step 4: Walk through the wizard in Personal mode**

1. Visit `http://localhost:5173/` → redirect to `/setup`.
2. Step 1 (Welcome): pick **Personal**, click Next.
3. Step 2a (Identity): type display name, click Next.
4. Step 3 (AI Models): add one model per required tier with a valid API key. Click Test & Save for each, wait for green pill. Click Next.
5. Step 4 (Providers): on Financial tab, add **EODHD** with `demo` key; on News tab add any configured built-in. Click Next.
6. Step 5 (Review): watch the progress bar, then inspect readiness cards. Click Finish.
7. Browser navigates to `/`.

- [ ] **Step 5: Walk through in Company mode**

Reset DB + restart server. Visit `/setup`, pick **Company**, create admin, then repeat steps 3–5 (access control step appears). Finish should redirect to `/login`. Log in with the admin account.

- [ ] **Step 6: Verify `410 Gone` on completed**

Run: `curl -i http://localhost:8000/setup/mode -X POST -d '{"mode":"personal"}' -H 'Content-Type: application/json'`
Expected: `HTTP/1.1 410 Gone`.

- [ ] **Step 7: Commit smoke-test notes (optional)**

No code change. If any divergence from the plan was found and fixed inline, stage those fixes and commit:

```bash
git commit -m "fix(wizard): smoke-test corrections"
```

---

## Task 28: Update planning docs

- [ ] **Step 1: Update `planning/implementation-plans/README.md`**

Edit the Plan 10 row:

```markdown
| 10 | 4 | Setup Wizard | Draft | `2026-04-17-phase-10-setup-wizard.md` |
```

- [ ] **Step 2: Update `planning/projectStructure.md`**

Append under the frontend section:

```
frontend/src/setup/              # Setup Wizard (WizardShell, steps, WizardContext)
```

Append under the server section:

```
packages/server/src/openlia_server/ai_review/   # AI review runner + prompt builder (wizard Step 6)
packages/server/src/openlia_server/middleware/wizard_gate.py
packages/server/src/openlia_server/routes/setup.py
packages/server/src/openlia_server/services/wizard.py
```

- [ ] **Step 3: Commit**

```bash
git add planning/implementation-plans/README.md planning/projectStructure.md
git commit -m "docs(plan): mark Phase 10 as Draft + record wizard paths in projectStructure"
```

---

## Self-Review Checklist

Before handing this plan off:

1. **Spec coverage** — every numbered entry in `SetupWizardSpec.md` maps to a task here:
   - Entry conditions + status → Task 2 + Task 4
   - Mode detection order + env override → Tasks 2, 4, 5
   - Resume (single-session) → Task 6
   - Storage + env precedence → Task 2, Task 11 (access control config writes)
   - Step 1 (Welcome/Mode) → Tasks 5 + 19
   - Step 2a (Identity) → Tasks 7 + 20
   - Step 2b (Admin) → Tasks 8 + 21
   - Step 3 (AI Models) → Tasks 9 + 22
   - Step 4 (Data Providers) → Tasks 10 + 23
   - Step 5 (Access Control) → Tasks 11 + 24
   - Step 6 (Review) → Tasks 12 + 13 + 14 + 25
   - `POST /setup/finish` → Task 15
   - UI chrome tokens + animations → Task 18 (WizardShell) + Task 26 (token addition)
   - 410 Gone post-completion → Tasks 3 + 15
   - Error handling scenarios → covered in step-specific error states
2. **Placeholder scan** — no "TBD", no "similar to Task N", no "add error handling".
3. **Type consistency** — `Mode`, `TierEntry`, `ProviderEntry`, `ProviderRow`, `ReviewPoll`, `WizardStatus` defined once in `api/setup.ts` and consumed unchanged.
4. **Commit discipline** — one commit per task; prefixes match the repo's convention.
5. **Dependency chain** — every Plan 10 task only references symbols from Plan 1A/2/3/4/5/8/9 or tasks earlier in this plan.

---

## Out-of-Scope Confirmations

- **Open signup policy** — disabled in UI (Task 24) per spec v1 default.
- **Provider catalog updates from remote** — not added; shipped catalog is the static list in `AddProviderForm.tsx`.
- **OAuth MCP** — explicitly documented in `MCPInfoCard`; no implementation.
- **Cost display on Step 3** — deferred (spec open question).
- **Localization** — English only per user memory `feedback_english_only.md`.

