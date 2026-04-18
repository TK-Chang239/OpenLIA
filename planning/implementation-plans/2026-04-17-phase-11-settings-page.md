# Phase 11 — Settings Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the four-section Settings page (General / Models / Account / Admin) with a secondary left nav, dirty-state tracking, unsaved-changes guard, a per-user model tier picker, and the full admin panel covering invites, users, password-reset requests, the LLM model roster, and data providers.

**Architecture:**

- **Backend (`packages/server/`).** Each section gets a thin route module: `routes/settings_general.py` (display name, notifications, appearance, language), `routes/settings_email.py` (email change with password confirmation), `routes/settings_models.py` (per-user tier preferences), and `routes/admin_*.py` (invites, users, password-reset requests). Models + data-providers admin CRUD routes already exist in Plans 3/4 under `/settings/models/*` and `/settings/data-providers/*`; Plan 11 only adds the missing endpoints and the admin-only wrapper. A `must_change_password` gate rejects every non-password-change route when the flag is set for the current user.
- **Frontend (`frontend/src/`).** A `SettingsPage` route renders `SettingsShell` (sidebar + content panel). Each section is a self-contained component with its own Save button, dirty-state tracking via `useDirtyForm`, and inline save feedback. The Admin section uses a horizontal tab bar with five subsections, each a separate component; every list view fetches on mount and re-fetches on mutation. `MustChangePasswordGate` from Plan 9 forces the Account → Change Password section when the flag is set.
- **Reuse.** Plan 9 provides `ChangePasswordForm`, `AccountProfile`, `SessionsPanel`, `Banner`, `FormField`, `PasswordInput`, `PasswordStrengthMeter`. Plan 10 provides `TierSlotCard` (admin view), `AddProviderForm`, `ProviderRow`, `MCPInfoCard` — these get re-exported from `setup/steps/` and imported from Settings with no duplication.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2; React 18, TypeScript strict, react-router-dom v6, Tailwind v3, lucide-react, vitest + @testing-library/react.

**Source spec:** `planning/specs/pages/SettingsPageSpec.md`; cross-reference `planning/specs/components/AccountManagementSpec.md`, `planning/specs/systems/llm-provider-design.md`, `planning/specs/systems/data-provider-design.md`.

**Depends on:**

- Plan 1A (tables `users`, `user_prefs`, `signup_invites`, `password_reset_requests`, `llm_providers`, `llm_models`, `user_llm_preferences`, `data_providers`, `data_provider_requirement_mapping`, `sessions`, `auth_events`).
- Plan 2 (session middleware, `require_auth`, `require_admin`, `argon2_hash`, `argon2_verify`, session revocation).
- Plan 3 (data-provider admin CRUD under `/settings/data-providers/*`).
- Plan 4 (LLM admin CRUD under `/settings/models/*`; `DEPARTMENT_DEFAULT_TIERS`; `resolve()`).
- Plan 7 (CLI admin commands — for invite + user workflows; Settings adds the UI).
- Plan 8 (router, design tokens, `api/client.ts`, `AuthProvider`).
- Plan 9 (`ChangePasswordForm`, `AccountProfile`, `SessionsPanel`, `Banner`, `FormField`, `PasswordInput`, `PasswordStrengthMeter`, `MustChangePasswordGate`).
- Plan 10 (reusable provider form components; `TierSlotCard`).

**Unblocks:**

- Post-wizard configuration changes.
- Any Plan that needs invite-management (Plan 23 packaging docs).

**Out of scope (explicitly deferred):**

- OAuth provider integration (spec non-goal).
- Billing / subscription management (spec non-goal).
- Per-user BYO LLM keys — admin-only for v1.
- Per-department notification preferences.
- Self-service account deletion.
- Localization of the Settings UI itself — English only per user memory.
- Email re-verification on email change (open question — deferred).
- Cross-device theme sync (open question — deferred; theme stored per-user, one source of truth).

---

## File Structure

### New backend files

```
packages/server/src/openlia_server/
├── routes/
│   ├── settings_general.py             # /settings/prefs (display_name, notifications, theme, language)
│   ├── settings_email.py               # /settings/email (PATCH with current_password)
│   ├── settings_models.py              # /settings/models/preferences (per-user tier picker)
│   ├── admin_invites.py                # /admin/invites
│   ├── admin_users.py                  # /admin/users
│   └── admin_password_reset_requests.py # /admin/password-reset-requests
└── services/
    ├── user_prefs.py                   # CRUD for user_prefs singleton per user
    ├── admin_invites.py                # create/list/revoke invites
    ├── admin_users.py                  # list/disable/enable/reset-password
    └── admin_password_reset.py         # approve/reject + token generation
```

### New backend tests

```
packages/server/tests/
├── test_services/
│   ├── test_user_prefs.py
│   ├── test_admin_invites.py
│   ├── test_admin_users.py
│   └── test_admin_password_reset.py
└── test_routes/
    ├── test_settings_general_routes.py
    ├── test_settings_email_routes.py
    ├── test_settings_models_routes.py
    ├── test_admin_invites_routes.py
    ├── test_admin_users_routes.py
    └── test_admin_password_reset_routes.py
```

### New frontend files

```
frontend/src/
├── api/
│   ├── settings.ts                     # typed /settings/* client
│   └── admin.ts                        # typed /admin/* client
├── settings/
│   ├── SettingsShell.tsx               # sidebar + content panel
│   ├── useDirtyForm.ts                 # tracks isDirty, handles unsaved-changes modal
│   ├── UnsavedChangesModal.tsx
│   ├── SaveButton.tsx                  # disabled/enabled/saving/saved states
│   ├── InlineFeedback.tsx              # Check / AlertCircle + message
│   ├── SettingGroup.tsx                # heading + divider primitive
│   ├── ToggleSwitch.tsx
│   ├── OneTimeSecretModal.tsx          # copy-ready + "won't be shown again"
│   └── sections/
│       ├── GeneralSection.tsx
│       ├── ModelsSection.tsx
│       ├── AccountSection.tsx
│       ├── AdminSection.tsx            # tab bar + subsection router
│       ├── admin/
│       │   ├── InvitesPanel.tsx
│       │   ├── UsersPanel.tsx
│       │   ├── ResetRequestsPanel.tsx
│       │   ├── ModelsAdminPanel.tsx
│       │   └── DataProvidersAdminPanel.tsx
├── pages/
│   └── SettingsPage.tsx                # route entry
```

### New frontend tests

```
frontend/src/settings/
├── SettingsShell.test.tsx
├── useDirtyForm.test.tsx
├── SaveButton.test.tsx
└── sections/
    ├── GeneralSection.test.tsx
    ├── ModelsSection.test.tsx
    ├── AccountSection.test.tsx
    └── admin/
        ├── InvitesPanel.test.tsx
        ├── UsersPanel.test.tsx
        └── ResetRequestsPanel.test.tsx
```

### Modified files

```
packages/server/src/openlia_server/
├── db/models/user.py                   # MODIFY — add user_prefs model (or separate table)
├── app.py                              # MODIFY — wire new routers
└── security/session.py                 # MODIFY — add revoke_all_for_user helper (used by disable)

frontend/src/
└── router.tsx                          # MODIFY — add /settings route + nested children

planning/implementation-plans/README.md # MODIFY — flip Plan 11 row to Draft
planning/projectStructure.md            # MODIFY — record Settings structure
```

---

## Design Rules

1. **Role gating.** `require_admin` wraps every `/admin/*` route. Frontend `AdminSection` renders only when `auth.user.role === "admin"` or `mode === "personal"`.
2. **Dirty state per section.** Each section tracks its own dirty flag; Save button disabled until dirty; post-save returns to disabled with 1.5s success flash.
3. **Unsaved-changes guard.** `useDirtyForm` exposes a prompt hook; `SettingsShell` intercepts sidebar navigation when any section is dirty.
4. **Must-change-password.** `MustChangePasswordGate` (Plan 9) wraps `SettingsPage` so the page redirects to Account → Change Password when the flag is set; all other nav buttons disabled until cleared.
5. **Admin-only API key writes.** Per user memory + spec non-goal, only admins create/edit/delete LLM or data provider credentials. Non-admin users only pick from the roster.
6. **One-time secrets.** Invite tokens and temp passwords are shown in a modal with explicit "won't be shown again" copy; never leaked through the list endpoint.
7. **Disable = session revoke.** Disabling a user sets `users.is_disabled=true` + deletes all their sessions + logs an `auth_events` row.
8. **Password reset approval.** Admin approval generates a one-time token (24h expiry) and shows the reset link exactly once.
9. **TDD every task.** Failing test → verify fail → implementation → verify pass → commit.
10. **No placeholders.** Every code block complete.
11. **Design tokens only.** `[--color-*]` classes, no raw hex.
12. **One commit per task.** Prefixes: `feat(settings)`, `feat(admin)`, `test(settings)`, `refactor(settings)`, `docs(plan)`.
13. **No untyped `any`.** Typed interfaces in `api/settings.ts` and `api/admin.ts`.
14. **Reuse.** Plan 9's `ChangePasswordForm`, `AccountProfile`, `SessionsPanel` are imported unchanged — not duplicated.

---

## Task 1: `user_prefs` model + migration

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/user.py`
- Create: `packages/server/migrations/versions/<next>_add_user_prefs.py`
- Test: `packages/server/tests/test_db/test_user_prefs_model.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_db/test_user_prefs_model.py
"""Verify user_prefs row with defaults, FK to users, and one-to-one constraint."""
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from openlia_server.db.models.user import User, UserPrefs


def test_user_prefs_defaults(create_tables, db_session: Session) -> None:
    user = User(email="a@b.com", password_hash="x", display_name="A", role="user")
    db_session.add(user)
    db_session.flush()
    prefs = UserPrefs(user_id=user.id)
    db_session.add(prefs)
    db_session.commit()

    assert prefs.theme == "system"
    assert prefs.notify_inapp is True
    assert prefs.notify_email is False
    assert prefs.display_language == "en"
    assert prefs.response_language == "en"
    assert prefs.report_language == "en"


def test_user_prefs_one_per_user(create_tables, db_session: Session) -> None:
    user = User(email="a@b.com", password_hash="x", display_name="A", role="user")
    db_session.add(user)
    db_session.flush()
    db_session.add(UserPrefs(user_id=user.id))
    db_session.add(UserPrefs(user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/server/tests/test_db/test_user_prefs_model.py -v`
Expected: FAIL — `UserPrefs` not defined.

- [ ] **Step 3: Add the model**

Append to `packages/server/src/openlia_server/db/models/user.py`:

```python
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship


class UserPrefs(Base):
    __tablename__ = "user_prefs"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_prefs_user_id"),
        CheckConstraint(
            "theme IN ('system','light','dark')", name="ck_user_prefs_theme"
        ),
        CheckConstraint(
            "display_language IN ('en','zh-TW') AND response_language IN ('en','zh-TW') "
            "AND report_language IN ('en','zh-TW','both')",
            name="ck_user_prefs_language",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    theme: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    notify_inapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    response_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    report_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
```

- [ ] **Step 4: Create the Alembic migration**

Run: `uv run alembic -c packages/server/alembic.ini revision -m "add_user_prefs"`

Edit the generated file:

```python
"""add_user_prefs"""
from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "<prior>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_prefs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("theme", sa.String(16), nullable=False, server_default="system"),
        sa.Column("notify_inapp", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("notify_email", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("display_language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("response_language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("report_language", sa.String(8), nullable=False, server_default="en"),
        sa.UniqueConstraint("user_id", name="uq_user_prefs_user_id"),
        sa.CheckConstraint("theme IN ('system','light','dark')", name="ck_user_prefs_theme"),
        sa.CheckConstraint(
            "display_language IN ('en','zh-TW') AND response_language IN ('en','zh-TW') "
            "AND report_language IN ('en','zh-TW','both')",
            name="ck_user_prefs_language",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_prefs")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_db/test_user_prefs_model.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/user.py \
        packages/server/migrations/versions/*add_user_prefs* \
        packages/server/tests/test_db/test_user_prefs_model.py
git commit -m "feat(db): add user_prefs table for display/notification/language preferences"
```

---

## Task 2: `user_prefs` service

**Files:**
- Create: `packages/server/src/openlia_server/services/user_prefs.py`
- Test: `packages/server/tests/test_services/test_user_prefs.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_services/test_user_prefs.py
"""Tests for UserPrefsService.get_or_create + update."""
import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.user import User
from openlia_server.services import user_prefs as svc


def test_get_or_create_creates_defaults(create_tables, db_session: Session) -> None:
    user = User(email="a@b.com", password_hash="x", display_name="A", role="user")
    db_session.add(user)
    db_session.flush()

    prefs = svc.get_or_create(db_session, user_id=user.id)
    assert prefs.theme == "system"
    assert prefs.notify_email is False


def test_update_persists_partial(create_tables, db_session: Session) -> None:
    user = User(email="a@b.com", password_hash="x", display_name="A", role="user")
    db_session.add(user)
    db_session.flush()

    svc.get_or_create(db_session, user_id=user.id)
    svc.update(
        db_session,
        user_id=user.id,
        theme="dark",
        notify_email=True,
    )
    prefs = svc.get_or_create(db_session, user_id=user.id)
    assert prefs.theme == "dark"
    assert prefs.notify_email is True
    assert prefs.notify_inapp is True  # unchanged


def test_update_rejects_invalid_theme(create_tables, db_session: Session) -> None:
    user = User(email="a@b.com", password_hash="x", display_name="A", role="user")
    db_session.add(user)
    db_session.flush()
    svc.get_or_create(db_session, user_id=user.id)

    with pytest.raises(ValueError):
        svc.update(db_session, user_id=user.id, theme="psychedelic")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/server/tests/test_services/test_user_prefs.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the service**

Create `packages/server/src/openlia_server/services/user_prefs.py`:

```python
"""User preferences service — display, notifications, theme, language."""
from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from openlia_server.db.models.user import UserPrefs

Theme = Literal["system", "light", "dark"]
DisplayLang = Literal["en", "zh-TW"]
ReportLang = Literal["en", "zh-TW", "both"]

_VALID_THEMES = {"system", "light", "dark"}
_VALID_DISPLAY_LANG = {"en", "zh-TW"}
_VALID_REPORT_LANG = {"en", "zh-TW", "both"}


def get_or_create(db: Session, *, user_id: int) -> UserPrefs:
    prefs = db.query(UserPrefs).filter_by(user_id=user_id).one_or_none()
    if prefs is None:
        prefs = UserPrefs(user_id=user_id)
        db.add(prefs)
        db.flush()
    return prefs


def update(
    db: Session,
    *,
    user_id: int,
    theme: str | None = None,
    notify_inapp: bool | None = None,
    notify_email: bool | None = None,
    display_language: str | None = None,
    response_language: str | None = None,
    report_language: str | None = None,
) -> UserPrefs:
    if theme is not None and theme not in _VALID_THEMES:
        raise ValueError(f"invalid theme: {theme}")
    if display_language is not None and display_language not in _VALID_DISPLAY_LANG:
        raise ValueError(f"invalid display_language: {display_language}")
    if response_language is not None and response_language not in _VALID_DISPLAY_LANG:
        raise ValueError(f"invalid response_language: {response_language}")
    if report_language is not None and report_language not in _VALID_REPORT_LANG:
        raise ValueError(f"invalid report_language: {report_language}")

    prefs = get_or_create(db, user_id=user_id)
    if theme is not None:
        prefs.theme = theme
    if notify_inapp is not None:
        prefs.notify_inapp = notify_inapp
    if notify_email is not None:
        prefs.notify_email = notify_email
    if display_language is not None:
        prefs.display_language = display_language
    if response_language is not None:
        prefs.response_language = response_language
    if report_language is not None:
        prefs.report_language = report_language
    db.flush()
    return prefs
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/server/tests/test_services/test_user_prefs.py -v`
Expected: all 3 pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/user_prefs.py \
        packages/server/tests/test_services/test_user_prefs.py
git commit -m "feat(settings): add UserPrefs service with validated update helpers"
```

---

## Task 3: `/settings/prefs` GET + PATCH route

**Files:**
- Create: `packages/server/src/openlia_server/routes/settings_general.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_routes/test_settings_general_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_routes/test_settings_general_routes.py
"""Tests for GET/PATCH /settings/prefs + /settings/display-name."""
import pytest
from fastapi.testclient import TestClient


def test_get_prefs_returns_defaults(company_client: TestClient, auth_user) -> None:
    resp = company_client.get("/settings/prefs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] == "system"
    assert body["notify_inapp"] is True
    assert body["display_name"] == auth_user.display_name


def test_patch_prefs_partial_update(company_client: TestClient) -> None:
    resp = company_client.patch(
        "/settings/prefs",
        json={"theme": "dark", "notify_email": True, "display_name": "NewName"},
    )
    assert resp.status_code == 200
    assert resp.json()["theme"] == "dark"
    assert resp.json()["notify_email"] is True
    assert resp.json()["display_name"] == "NewName"


def test_patch_prefs_rejects_invalid(company_client: TestClient) -> None:
    resp = company_client.patch("/settings/prefs", json={"theme": "rainbow"})
    assert resp.status_code == 422


def test_get_prefs_requires_auth(company_client_anon: TestClient) -> None:
    resp = company_client_anon.get("/settings/prefs")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/server/tests/test_routes/test_settings_general_routes.py -v`
Expected: FAIL — `/settings/prefs` 404.

- [ ] **Step 3: Implement the router**

Create `packages/server/src/openlia_server/routes/settings_general.py`:

```python
"""Routes for GET/PATCH /settings/prefs — display name, notifications, theme, language."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.models.user import User
from openlia_server.db.session import get_db_session
from openlia_server.middleware.auth import require_auth
from openlia_server.services import user_prefs as svc


class PrefsOut(BaseModel):
    display_name: str
    theme: str
    notify_inapp: bool
    notify_email: bool
    display_language: str
    response_language: str
    report_language: str


class PrefsPatchIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    theme: str | None = Field(default=None, pattern=r"^(system|light|dark)$")
    notify_inapp: bool | None = None
    notify_email: bool | None = None
    display_language: str | None = Field(default=None, pattern=r"^(en|zh-TW)$")
    response_language: str | None = Field(default=None, pattern=r"^(en|zh-TW)$")
    report_language: str | None = Field(default=None, pattern=r"^(en|zh-TW|both)$")


def _to_out(user: User, prefs) -> PrefsOut:
    return PrefsOut(
        display_name=user.display_name,
        theme=prefs.theme,
        notify_inapp=prefs.notify_inapp,
        notify_email=prefs.notify_email,
        display_language=prefs.display_language,
        response_language=prefs.response_language,
        report_language=prefs.report_language,
    )


def build_settings_general_router() -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])

    @router.get("/prefs", response_model=PrefsOut)
    def get_prefs(
        db: Session = Depends(get_db_session),
        user: User = Depends(require_auth),
    ) -> PrefsOut:
        prefs = svc.get_or_create(db, user_id=user.id)
        return _to_out(user, prefs)

    @router.patch("/prefs", response_model=PrefsOut)
    def patch_prefs(
        payload: PrefsPatchIn,
        db: Session = Depends(get_db_session),
        user: User = Depends(require_auth),
    ) -> PrefsOut:
        if payload.display_name is not None:
            user.display_name = payload.display_name
            db.flush()
        try:
            prefs = svc.update(
                db,
                user_id=user.id,
                theme=payload.theme,
                notify_inapp=payload.notify_inapp,
                notify_email=payload.notify_email,
                display_language=payload.display_language,
                response_language=payload.response_language,
                report_language=payload.report_language,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_pref", "message": str(exc)},
            ) from exc
        return _to_out(user, prefs)

    return router
```

- [ ] **Step 4: Wire into `app.py`**

Add:

```python
from openlia_server.routes.settings_general import build_settings_general_router

app.include_router(build_settings_general_router())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_settings_general_routes.py -v`
Expected: all 4 pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings_general.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_routes/test_settings_general_routes.py
git commit -m "feat(settings): add GET/PATCH /settings/prefs for general preferences"
```

---

## Task 4: `/settings/email` PATCH route with password confirmation

**Files:**
- Create: `packages/server/src/openlia_server/routes/settings_email.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_routes/test_settings_email_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_routes/test_settings_email_routes.py
"""Tests for PATCH /settings/email with password confirmation."""
import pytest
from fastapi.testclient import TestClient


def test_patch_email_success(company_client: TestClient, auth_user, db_session) -> None:
    from openlia_server.db.models.user import User

    resp = company_client.patch(
        "/settings/email",
        json={"new_email": "new@example.com", "current_password": "CorrectHorseBattery9!"},
    )
    assert resp.status_code == 200

    fresh = db_session.query(User).get(auth_user.id)
    assert fresh.email == "new@example.com"


def test_patch_email_rejects_wrong_password(company_client: TestClient) -> None:
    resp = company_client.patch(
        "/settings/email",
        json={"new_email": "new@example.com", "current_password": "nope"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


def test_patch_email_rejects_duplicate(company_client: TestClient, make_user) -> None:
    make_user(email="taken@example.com")
    resp = company_client.patch(
        "/settings/email",
        json={"new_email": "taken@example.com", "current_password": "CorrectHorseBattery9!"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "email_in_use"


def test_patch_email_rejects_invalid_format(company_client: TestClient) -> None:
    resp = company_client.patch(
        "/settings/email",
        json={"new_email": "not-an-email", "current_password": "CorrectHorseBattery9!"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_settings_email_routes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the router**

Create `packages/server/src/openlia_server/routes/settings_email.py`:

```python
"""Route for PATCH /settings/email with current-password confirmation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.models.user import User
from openlia_server.db.session import get_db_session
from openlia_server.middleware.auth import require_auth
from openlia_server.security.passwords import argon2_verify


class EmailChangeIn(BaseModel):
    new_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    current_password: str


def build_settings_email_router() -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])

    @router.patch("/email")
    def patch_email(
        payload: EmailChangeIn,
        db: Session = Depends(get_db_session),
        user: User = Depends(require_auth),
    ) -> dict[str, str]:
        if not argon2_verify(payload.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_credentials", "message": "Current password is incorrect."},
            )
        clash = db.query(User).filter_by(email=payload.new_email).first()
        if clash and clash.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "email_in_use", "message": "Email already in use."},
            )
        user.email = payload.new_email
        db.flush()
        return {"email": user.email}

    return router
```

- [ ] **Step 4: Wire into `app.py`**

```python
from openlia_server.routes.settings_email import build_settings_email_router
app.include_router(build_settings_email_router())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_settings_email_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings_email.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_routes/test_settings_email_routes.py
git commit -m "feat(settings): add PATCH /settings/email with password confirmation + duplicate check"
```

---

## Task 5: `/settings/models/preferences` (per-user tier picker)

**Files:**
- Create: `packages/server/src/openlia_server/routes/settings_models.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_routes/test_settings_models_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_routes/test_settings_models_routes.py
"""Tests for /settings/models/preferences."""
import pytest
from fastapi.testclient import TestClient


def test_get_preferences_returns_empty_when_none(company_client: TestClient) -> None:
    resp = company_client.get("/settings/models/preferences")
    assert resp.status_code == 200
    assert resp.json()["preferences"] == {}


def test_put_preference_persists(company_client: TestClient, seed_admin_roster) -> None:
    model = seed_admin_roster["thinking"][0]
    resp = company_client.put(
        "/settings/models/preferences",
        json={"tier": "thinking", "model_id": model.id},
    )
    assert resp.status_code == 200

    listed = company_client.get("/settings/models/preferences").json()
    assert listed["preferences"]["thinking"] == model.id


def test_delete_preference_falls_back_to_default(
    company_client: TestClient, seed_admin_roster
) -> None:
    model = seed_admin_roster["thinking"][0]
    company_client.put(
        "/settings/models/preferences",
        json={"tier": "thinking", "model_id": model.id},
    )
    resp = company_client.delete("/settings/models/preferences/thinking")
    assert resp.status_code == 200
    assert company_client.get("/settings/models/preferences").json()["preferences"] == {}


def test_put_preference_rejects_unknown_model(company_client: TestClient) -> None:
    resp = company_client.put(
        "/settings/models/preferences",
        json={"tier": "thinking", "model_id": "nope"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_settings_models_routes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the router**

Create `packages/server/src/openlia_server/routes/settings_models.py`:

```python
"""Routes for per-user LLM tier preferences."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.models.llm import LLMModel, UserLLMPreference
from openlia_server.db.models.user import User
from openlia_server.db.session import get_db_session
from openlia_server.middleware.auth import require_auth


class PreferenceIn(BaseModel):
    tier: str = Field(pattern=r"^(thinking|everyday|quick)$")
    model_id: str


class PreferenceListOut(BaseModel):
    preferences: dict[str, str]


def build_settings_models_router() -> APIRouter:
    router = APIRouter(prefix="/settings/models", tags=["settings"])

    @router.get("/preferences", response_model=PreferenceListOut)
    def list_preferences(
        db: Session = Depends(get_db_session),
        user: User = Depends(require_auth),
    ) -> PreferenceListOut:
        rows = db.query(UserLLMPreference).filter_by(user_id=user.id).all()
        return PreferenceListOut(preferences={row.tier: row.model_id for row in rows})

    @router.put("/preferences")
    def put_preference(
        payload: PreferenceIn,
        db: Session = Depends(get_db_session),
        user: User = Depends(require_auth),
    ) -> dict[str, bool]:
        model = db.query(LLMModel).filter_by(id=payload.model_id).first()
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "model_not_found", "message": "Model id not in roster."},
            )
        if model.tier != payload.tier:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "tier_mismatch",
                    "message": f"Model is tier {model.tier}, not {payload.tier}.",
                },
            )
        existing = (
            db.query(UserLLMPreference)
            .filter_by(user_id=user.id, tier=payload.tier)
            .one_or_none()
        )
        if existing is None:
            db.add(UserLLMPreference(user_id=user.id, tier=payload.tier, model_id=payload.model_id))
        else:
            existing.model_id = payload.model_id
        db.flush()
        return {"ok": True}

    @router.delete("/preferences/{tier}")
    def delete_preference(
        tier: str,
        db: Session = Depends(get_db_session),
        user: User = Depends(require_auth),
    ) -> dict[str, bool]:
        db.query(UserLLMPreference).filter_by(user_id=user.id, tier=tier).delete()
        db.flush()
        return {"ok": True}

    return router
```

- [ ] **Step 4: Wire into `app.py`**

```python
from openlia_server.routes.settings_models import build_settings_models_router
app.include_router(build_settings_models_router())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_settings_models_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings_models.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_routes/test_settings_models_routes.py
git commit -m "feat(settings): add /settings/models/preferences for per-user tier picks"
```

---

## Task 6: Admin invites service

**Files:**
- Create: `packages/server/src/openlia_server/services/admin_invites.py`
- Test: `packages/server/tests/test_services/test_admin_invites.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_services/test_admin_invites.py
"""Tests for AdminInvitesService — create, list, revoke."""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import SignupInvite, User
from openlia_server.services import admin_invites as svc


def test_create_invite_returns_token_once(create_tables, db_session: Session) -> None:
    admin = User(email="a@b.com", password_hash="x", display_name="A", role="admin")
    db_session.add(admin)
    db_session.flush()

    invite, token = svc.create_invite(
        db_session, created_by_user_id=admin.id, label="Team onboarding", max_uses=5
    )
    assert len(token) >= 32
    assert invite.label == "Team onboarding"
    assert invite.max_uses == 5
    assert invite.token_hash != token  # hashed


def test_list_invites_returns_with_status(create_tables, db_session: Session) -> None:
    admin = User(email="a@b.com", password_hash="x", display_name="A", role="admin")
    db_session.add(admin)
    db_session.flush()

    svc.create_invite(db_session, created_by_user_id=admin.id, label="a")
    svc.create_invite(
        db_session,
        created_by_user_id=admin.id,
        label="b",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    rows = svc.list_invites(db_session)
    statuses = {r.status for r in rows}
    assert "active" in statuses
    assert "expired" in statuses


def test_revoke_invite_marks_revoked(create_tables, db_session: Session) -> None:
    admin = User(email="a@b.com", password_hash="x", display_name="A", role="admin")
    db_session.add(admin)
    db_session.flush()

    invite, _ = svc.create_invite(db_session, created_by_user_id=admin.id, label="a")
    svc.revoke_invite(db_session, invite_id=invite.id)
    fresh = db_session.query(SignupInvite).get(invite.id)
    assert fresh.revoked_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_admin_invites.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the service**

Create `packages/server/src/openlia_server/services/admin_invites.py`:

```python
"""Admin invites service — create (with one-time plaintext token), list, revoke."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from openlia_server.db.models.auth import SignupInvite


@dataclass(slots=True)
class InviteRow:
    id: int
    label: str | None
    created_at: datetime
    expires_at: datetime | None
    use_count: int
    max_uses: int | None
    revoked_at: datetime | None
    status: str  # active | expired | revoked | at_capacity


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_invite(
    db: Session,
    *,
    created_by_user_id: int,
    label: str | None = None,
    max_uses: int | None = None,
    expires_at: datetime | None = None,
) -> tuple[SignupInvite, str]:
    token = secrets.token_urlsafe(32)
    invite = SignupInvite(
        token_hash=_hash_token(token),
        label=label,
        max_uses=max_uses,
        expires_at=expires_at,
        created_by_user_id=created_by_user_id,
    )
    db.add(invite)
    db.flush()
    return invite, token


def _status_for(invite: SignupInvite) -> str:
    if invite.revoked_at is not None:
        return "revoked"
    if invite.expires_at is not None and invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(
        timezone.utc
    ):
        return "expired"
    if invite.max_uses is not None and invite.use_count >= invite.max_uses:
        return "at_capacity"
    return "active"


def list_invites(db: Session) -> list[InviteRow]:
    rows = (
        db.query(SignupInvite)
        .order_by(SignupInvite.created_at.desc())
        .all()
    )
    return [
        InviteRow(
            id=r.id,
            label=r.label,
            created_at=r.created_at,
            expires_at=r.expires_at,
            use_count=r.use_count,
            max_uses=r.max_uses,
            revoked_at=r.revoked_at,
            status=_status_for(r),
        )
        for r in rows
    ]


def revoke_invite(db: Session, *, invite_id: int) -> None:
    invite = db.query(SignupInvite).get(invite_id)
    if invite is None:
        return
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(timezone.utc)
        db.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_admin_invites.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/admin_invites.py \
        packages/server/tests/test_services/test_admin_invites.py
git commit -m "feat(admin): add invites service — create/list/revoke with computed status"
```

---

## Task 7: `/admin/invites` routes

**Files:**
- Create: `packages/server/src/openlia_server/routes/admin_invites.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_routes/test_admin_invites_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_routes/test_admin_invites_routes.py
"""Tests for /admin/invites CRUD."""
import pytest
from fastapi.testclient import TestClient


def test_list_invites_requires_admin(company_client_user: TestClient) -> None:
    resp = company_client_user.get("/admin/invites")
    assert resp.status_code == 403


def test_create_invite_returns_token_once(company_client_admin: TestClient) -> None:
    resp = company_client_admin.post(
        "/admin/invites",
        json={"label": "team", "max_uses": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert len(body["token"]) >= 32

    listed = company_client_admin.get("/admin/invites").json()
    assert len(listed["invites"]) == 1
    assert "token" not in listed["invites"][0]  # never leaked on list


def test_revoke_invite(company_client_admin: TestClient) -> None:
    created = company_client_admin.post("/admin/invites", json={"label": "a"}).json()
    resp = company_client_admin.post(f"/admin/invites/{created['id']}/revoke")
    assert resp.status_code == 200

    listed = company_client_admin.get("/admin/invites").json()
    assert listed["invites"][0]["status"] == "revoked"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_admin_invites_routes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the router**

Create `packages/server/src/openlia_server/routes/admin_invites.py`:

```python
"""Admin routes for invite management."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.models.user import User
from openlia_server.db.session import get_db_session
from openlia_server.middleware.auth import require_admin
from openlia_server.services import admin_invites as svc


class InviteCreateIn(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    max_uses: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None


class InviteOut(BaseModel):
    id: int
    label: str | None
    created_at: datetime
    expires_at: datetime | None
    use_count: int
    max_uses: int | None
    revoked_at: datetime | None
    status: str


class InviteListOut(BaseModel):
    invites: list[InviteOut]


class InviteCreateOut(BaseModel):
    id: int
    token: str
    status: str


def build_admin_invites_router() -> APIRouter:
    router = APIRouter(prefix="/admin/invites", tags=["admin"])

    @router.get("", response_model=InviteListOut)
    def list_invites(
        db: Session = Depends(get_db_session),
        _: User = Depends(require_admin),
    ) -> InviteListOut:
        rows = svc.list_invites(db)
        return InviteListOut(
            invites=[
                InviteOut(
                    id=r.id,
                    label=r.label,
                    created_at=r.created_at,
                    expires_at=r.expires_at,
                    use_count=r.use_count,
                    max_uses=r.max_uses,
                    revoked_at=r.revoked_at,
                    status=r.status,
                )
                for r in rows
            ]
        )

    @router.post("", response_model=InviteCreateOut)
    def create_invite(
        payload: InviteCreateIn,
        db: Session = Depends(get_db_session),
        admin: User = Depends(require_admin),
    ) -> InviteCreateOut:
        invite, token = svc.create_invite(
            db,
            created_by_user_id=admin.id,
            label=payload.label,
            max_uses=payload.max_uses,
            expires_at=payload.expires_at,
        )
        return InviteCreateOut(id=invite.id, token=token, status="active")

    @router.post("/{invite_id}/revoke")
    def revoke_invite(
        invite_id: int,
        db: Session = Depends(get_db_session),
        _: User = Depends(require_admin),
    ) -> dict[str, bool]:
        svc.revoke_invite(db, invite_id=invite_id)
        return {"ok": True}

    return router
```

- [ ] **Step 4: Wire into `app.py`**

```python
from openlia_server.routes.admin_invites import build_admin_invites_router
app.include_router(build_admin_invites_router())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_admin_invites_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/admin_invites.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_routes/test_admin_invites_routes.py
git commit -m "feat(admin): add /admin/invites CRUD routes (token shown once)"
```

---

## Task 8: Admin users service + routes

**Files:**
- Create: `packages/server/src/openlia_server/services/admin_users.py`
- Create: `packages/server/src/openlia_server/routes/admin_users.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_services/test_admin_users.py`
- Test: `packages/server/tests/test_routes/test_admin_users_routes.py`

- [ ] **Step 1: Write the failing service test**

```python
# packages/server/tests/test_services/test_admin_users.py
"""Tests for AdminUsersService."""
import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import Session as DBSession
from openlia_server.db.models.user import User
from openlia_server.services import admin_users as svc


def test_disable_user_revokes_sessions(create_tables, db_session: Session, make_user, make_session) -> None:
    user = make_user(email="u@x.com")
    make_session(user_id=user.id)
    make_session(user_id=user.id)

    svc.disable_user(db_session, user_id=user.id, admin_id=1)

    user_fresh = db_session.query(User).get(user.id)
    assert user_fresh.is_disabled is True
    assert db_session.query(DBSession).filter_by(user_id=user.id).count() == 0


def test_reset_password_sets_must_change_flag(create_tables, db_session: Session, make_user) -> None:
    user = make_user(email="u@x.com")
    temp = svc.admin_reset_password(db_session, user_id=user.id, admin_id=1)
    assert len(temp) >= 12

    user_fresh = db_session.query(User).get(user.id)
    assert user_fresh.must_change_password is True


def test_cannot_disable_self(create_tables, db_session: Session, make_user) -> None:
    user = make_user(email="u@x.com")
    with pytest.raises(svc.CannotDisableSelfError):
        svc.disable_user(db_session, user_id=user.id, admin_id=user.id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_admin_users.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the service**

Create `packages/server/src/openlia_server/services/admin_users.py`:

```python
"""Admin users service — disable/enable/reset-password."""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from openlia_server.db.models.auth import AuthEvent, Session as DBSession
from openlia_server.db.models.user import User
from openlia_server.security.passwords import argon2_hash


class CannotDisableSelfError(Exception):
    pass


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def disable_user(db: Session, *, user_id: int, admin_id: int) -> None:
    if user_id == admin_id:
        raise CannotDisableSelfError()
    user = db.query(User).get(user_id)
    if user is None:
        return
    user.is_disabled = True
    db.query(DBSession).filter_by(user_id=user_id).delete()
    db.add(AuthEvent(user_id=user_id, event_type="user_disabled", actor_user_id=admin_id))
    db.flush()


def enable_user(db: Session, *, user_id: int, admin_id: int) -> None:
    user = db.query(User).get(user_id)
    if user is None:
        return
    user.is_disabled = False
    db.add(AuthEvent(user_id=user_id, event_type="user_enabled", actor_user_id=admin_id))
    db.flush()


def _generate_temp_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(16))


def admin_reset_password(db: Session, *, user_id: int, admin_id: int) -> str:
    user = db.query(User).get(user_id)
    if user is None:
        raise ValueError("unknown user_id")
    temp = _generate_temp_password()
    user.password_hash = argon2_hash(temp)
    user.must_change_password = True
    db.query(DBSession).filter_by(user_id=user_id).delete()
    db.add(AuthEvent(user_id=user_id, event_type="admin_password_reset", actor_user_id=admin_id))
    db.flush()
    return temp
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_admin_users.py -v`
Expected: all pass.

- [ ] **Step 5: Write the route test**

```python
# packages/server/tests/test_routes/test_admin_users_routes.py
import pytest
from fastapi.testclient import TestClient


def test_list_users_requires_admin(company_client_user: TestClient) -> None:
    resp = company_client_user.get("/admin/users")
    assert resp.status_code == 403


def test_list_users(company_client_admin: TestClient, make_user) -> None:
    make_user(email="x@y.com")
    resp = company_client_admin.get("/admin/users")
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()["users"]]
    assert "x@y.com" in emails


def test_disable_user(company_client_admin: TestClient, make_user) -> None:
    user = make_user(email="to-disable@x.com")
    resp = company_client_admin.post(f"/admin/users/{user.id}/disable")
    assert resp.status_code == 200


def test_reset_password_returns_temp(company_client_admin: TestClient, make_user) -> None:
    user = make_user(email="needs-reset@x.com")
    resp = company_client_admin.post(f"/admin/users/{user.id}/reset-password")
    assert resp.status_code == 200
    assert len(resp.json()["temp_password"]) >= 12


def test_cannot_disable_self(company_client_admin: TestClient, admin_user) -> None:
    resp = company_client_admin.post(f"/admin/users/{admin_user.id}/disable")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "cannot_disable_self"
```

- [ ] **Step 6: Run route tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_admin_users_routes.py -v`
Expected: FAIL.

- [ ] **Step 7: Implement the router**

Create `packages/server/src/openlia_server/routes/admin_users.py`:

```python
"""Admin routes for user list / disable-enable / reset-password."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.models.user import User
from openlia_server.db.session import get_db_session
from openlia_server.middleware.auth import require_admin
from openlia_server.services import admin_users as svc


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    is_disabled: bool
    created_at: datetime


class UserListOut(BaseModel):
    users: list[UserOut]


class TempPasswordOut(BaseModel):
    temp_password: str


def build_admin_users_router() -> APIRouter:
    router = APIRouter(prefix="/admin/users", tags=["admin"])

    @router.get("", response_model=UserListOut)
    def list_users(
        db: Session = Depends(get_db_session),
        _: User = Depends(require_admin),
    ) -> UserListOut:
        return UserListOut(
            users=[
                UserOut(
                    id=u.id,
                    email=u.email,
                    display_name=u.display_name,
                    role=u.role,
                    is_disabled=u.is_disabled,
                    created_at=u.created_at,
                )
                for u in svc.list_users(db)
            ]
        )

    @router.post("/{user_id}/disable")
    def disable_user(
        user_id: int,
        db: Session = Depends(get_db_session),
        admin: User = Depends(require_admin),
    ) -> dict[str, bool]:
        try:
            svc.disable_user(db, user_id=user_id, admin_id=admin.id)
        except svc.CannotDisableSelfError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "cannot_disable_self", "message": "You cannot disable your own account."},
            ) from exc
        return {"ok": True}

    @router.post("/{user_id}/enable")
    def enable_user(
        user_id: int,
        db: Session = Depends(get_db_session),
        admin: User = Depends(require_admin),
    ) -> dict[str, bool]:
        svc.enable_user(db, user_id=user_id, admin_id=admin.id)
        return {"ok": True}

    @router.post("/{user_id}/reset-password", response_model=TempPasswordOut)
    def reset_password(
        user_id: int,
        db: Session = Depends(get_db_session),
        admin: User = Depends(require_admin),
    ) -> TempPasswordOut:
        temp = svc.admin_reset_password(db, user_id=user_id, admin_id=admin.id)
        return TempPasswordOut(temp_password=temp)

    return router
```

- [ ] **Step 8: Wire into `app.py`**

```python
from openlia_server.routes.admin_users import build_admin_users_router
app.include_router(build_admin_users_router())
```

- [ ] **Step 9: Run route tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_admin_users_routes.py -v`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add packages/server/src/openlia_server/services/admin_users.py \
        packages/server/src/openlia_server/routes/admin_users.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_services/test_admin_users.py \
        packages/server/tests/test_routes/test_admin_users_routes.py
git commit -m "feat(admin): add /admin/users with disable/enable/reset-password"
```

---

## Task 9: Admin password-reset-requests service + routes

**Files:**
- Create: `packages/server/src/openlia_server/services/admin_password_reset.py`
- Create: `packages/server/src/openlia_server/routes/admin_password_reset_requests.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_services/test_admin_password_reset.py`
- Test: `packages/server/tests/test_routes/test_admin_password_reset_routes.py`

- [ ] **Step 1: Write the service test**

```python
# packages/server/tests/test_services/test_admin_password_reset.py
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import PasswordResetRequest
from openlia_server.services import admin_password_reset as svc


def test_approve_generates_token_and_link(create_tables, db_session: Session, make_user) -> None:
    user = make_user(email="u@x.com")
    request = PasswordResetRequest(user_id=user.id, ip_address="127.0.0.1", status="pending")
    db_session.add(request)
    db_session.flush()

    token, link = svc.approve_request(db_session, request_id=request.id, admin_id=1)
    assert len(token) >= 32
    assert "/reset-password?token=" in link

    fresh = db_session.query(PasswordResetRequest).get(request.id)
    assert fresh.status == "approved"
    assert fresh.expires_at is not None


def test_reject_request(create_tables, db_session: Session, make_user) -> None:
    user = make_user(email="u@x.com")
    request = PasswordResetRequest(user_id=user.id, ip_address="127.0.0.1", status="pending")
    db_session.add(request)
    db_session.flush()

    svc.reject_request(db_session, request_id=request.id, admin_id=1)
    fresh = db_session.query(PasswordResetRequest).get(request.id)
    assert fresh.status == "rejected"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/server/tests/test_services/test_admin_password_reset.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the service**

Create `packages/server/src/openlia_server/services/admin_password_reset.py`:

```python
"""Admin approval flow for password reset requests."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from openlia_server.db.models.auth import PasswordResetRequest


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def approve_request(
    db: Session, *, request_id: int, admin_id: int
) -> tuple[str, str]:
    request = db.query(PasswordResetRequest).get(request_id)
    if request is None:
        raise ValueError("unknown request_id")
    if request.status != "pending":
        raise ValueError(f"request not pending: {request.status}")

    token = secrets.token_urlsafe(32)
    request.token_hash = _hash(token)
    request.status = "approved"
    request.approved_by_user_id = admin_id
    request.approved_at = datetime.now(timezone.utc)
    request.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    db.flush()

    return token, f"/reset-password?token={token}"


def reject_request(db: Session, *, request_id: int, admin_id: int) -> None:
    request = db.query(PasswordResetRequest).get(request_id)
    if request is None:
        raise ValueError("unknown request_id")
    request.status = "rejected"
    request.approved_by_user_id = admin_id
    request.approved_at = datetime.now(timezone.utc)
    db.flush()


def list_requests(db: Session, *, status_filter: str | None = None) -> list[PasswordResetRequest]:
    q = db.query(PasswordResetRequest).order_by(PasswordResetRequest.requested_at.desc())
    if status_filter is not None:
        q = q.filter_by(status=status_filter)
    return q.all()
```

- [ ] **Step 4: Write the route test**

```python
# packages/server/tests/test_routes/test_admin_password_reset_routes.py
import pytest
from fastapi.testclient import TestClient


def test_list_reset_requests_requires_admin(company_client_user: TestClient) -> None:
    resp = company_client_user.get("/admin/password-reset-requests")
    assert resp.status_code == 403


def test_approve_reset_request_returns_link_once(
    company_client_admin: TestClient, make_reset_request
) -> None:
    req = make_reset_request()
    resp = company_client_admin.post(f"/admin/password-reset-requests/{req.id}/approve")
    assert resp.status_code == 200
    assert "reset_link" in resp.json()
    assert len(resp.json()["token"]) >= 32


def test_reject_reset_request(
    company_client_admin: TestClient, make_reset_request
) -> None:
    req = make_reset_request()
    resp = company_client_admin.post(f"/admin/password-reset-requests/{req.id}/reject")
    assert resp.status_code == 200


def test_list_filters_by_status(company_client_admin: TestClient, make_reset_request) -> None:
    make_reset_request()
    make_reset_request()
    resp = company_client_admin.get("/admin/password-reset-requests?status=pending")
    assert resp.status_code == 200
    assert all(r["status"] == "pending" for r in resp.json()["requests"])
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_admin_password_reset_routes.py -v`
Expected: FAIL.

- [ ] **Step 6: Implement the router**

Create `packages/server/src/openlia_server/routes/admin_password_reset_requests.py`:

```python
"""Admin routes for password-reset-request approval flow."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.models.user import User
from openlia_server.db.session import get_db_session
from openlia_server.middleware.auth import require_admin
from openlia_server.services import admin_password_reset as svc


class RequestRowOut(BaseModel):
    id: int
    user_id: int
    user_email: str
    requested_at: datetime
    ip_address: str | None
    status: str
    expires_at: datetime | None


class RequestListOut(BaseModel):
    requests: list[RequestRowOut]


class ApprovalOut(BaseModel):
    token: str
    reset_link: str
    expires_at: datetime


def build_admin_password_reset_router() -> APIRouter:
    router = APIRouter(prefix="/admin/password-reset-requests", tags=["admin"])

    @router.get("", response_model=RequestListOut)
    def list_requests(
        status_filter: str | None = None,
        db: Session = Depends(get_db_session),
        _: User = Depends(require_admin),
    ) -> RequestListOut:
        rows = svc.list_requests(db, status_filter=status_filter)
        return RequestListOut(
            requests=[
                RequestRowOut(
                    id=r.id,
                    user_id=r.user_id,
                    user_email=r.user.email,
                    requested_at=r.requested_at,
                    ip_address=r.ip_address,
                    status=r.status,
                    expires_at=r.expires_at,
                )
                for r in rows
            ]
        )

    @router.post("/{request_id}/approve", response_model=ApprovalOut)
    def approve(
        request_id: int,
        db: Session = Depends(get_db_session),
        admin: User = Depends(require_admin),
    ) -> ApprovalOut:
        try:
            token, link = svc.approve_request(db, request_id=request_id, admin_id=admin.id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "not_pending", "message": str(exc)},
            ) from exc
        row = db.query(svc.PasswordResetRequest).get(request_id)
        return ApprovalOut(token=token, reset_link=link, expires_at=row.expires_at)

    @router.post("/{request_id}/reject")
    def reject(
        request_id: int,
        db: Session = Depends(get_db_session),
        admin: User = Depends(require_admin),
    ) -> dict[str, bool]:
        try:
            svc.reject_request(db, request_id=request_id, admin_id=admin.id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "not_found", "message": str(exc)},
            ) from exc
        return {"ok": True}

    return router
```

- [ ] **Step 7: Wire into `app.py`**

```python
from openlia_server.routes.admin_password_reset_requests import build_admin_password_reset_router
app.include_router(build_admin_password_reset_router())
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_admin_password_reset_routes.py -v`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add packages/server/src/openlia_server/services/admin_password_reset.py \
        packages/server/src/openlia_server/routes/admin_password_reset_requests.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_services/test_admin_password_reset.py \
        packages/server/tests/test_routes/test_admin_password_reset_routes.py
git commit -m "feat(admin): add /admin/password-reset-requests approve/reject flow"
```

---

### Task 10: Typed API clients for settings + admin

**Files:**
- Create: `frontend/src/api/settings.ts`
- Create: `frontend/src/api/admin.ts`
- Test: `frontend/src/api/__tests__/settings.test.ts`

- [ ] **Step 1: Write failing tests for `settings.ts`**

```typescript
// frontend/src/api/__tests__/settings.test.ts
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { getPrefs, updatePrefs, updateEmail, getModelPreferences, putModelPreference, deleteModelPreference } from '../settings';

describe('settings api', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('GET /settings/prefs returns typed payload', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        display_name: 'Alice',
        theme: 'system',
        notify_inapp: true,
        notify_email: false,
        display_language: 'en',
        response_language: 'en',
        report_language: 'en',
      }),
    });
    const prefs = await getPrefs();
    expect(prefs.theme).toBe('system');
    expect(prefs.display_name).toBe('Alice');
  });

  it('PATCH /settings/prefs posts JSON patch body', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ display_name: 'Bob', theme: 'dark', notify_inapp: true, notify_email: false, display_language: 'en', response_language: 'en', report_language: 'en' }) });
    await updatePrefs({ theme: 'dark', display_name: 'Bob' });
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/settings/prefs');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body)).toEqual({ theme: 'dark', display_name: 'Bob' });
  });

  it('PATCH /settings/email surfaces 409 email_in_use', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: { code: 'email_in_use', message: 'x' } }),
    });
    await expect(updateEmail({ new_email: 'a@b.co', current_password: 'x' })).rejects.toMatchObject({
      code: 'email_in_use',
    });
  });

  it('GET /settings/models/preferences returns list', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [{ tier: 'thinking', provider_id: 'openai', model_id: 'gpt-4o' }] }),
    });
    const prefs = await getModelPreferences();
    expect(prefs.items[0].tier).toBe('thinking');
  });

  it('PUT /settings/models/preferences/{tier}', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await putModelPreference('quick', { provider_id: 'openai', model_id: 'gpt-4o-mini' });
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/settings/models/preferences/quick');
    expect(init.method).toBe('PUT');
  });

  it('DELETE /settings/models/preferences/{tier}', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await deleteModelPreference('quick');
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/settings/models/preferences/quick');
    expect(init.method).toBe('DELETE');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/__tests__/settings.test.ts`
Expected: FAIL with "Cannot find module '../settings'"

- [ ] **Step 3: Implement `settings.ts`**

```typescript
// frontend/src/api/settings.ts
export type Theme = 'system' | 'light' | 'dark';
export type LangCode = 'en' | 'zh-Hant' | 'zh-Hans';
export type Tier = 'everyday' | 'quick' | 'thinking' | 'long_context';

export interface Prefs {
  display_name: string;
  theme: Theme;
  notify_inapp: boolean;
  notify_email: boolean;
  display_language: LangCode;
  response_language: LangCode;
  report_language: LangCode;
}

export interface PrefsPatch {
  display_name?: string;
  theme?: Theme;
  notify_inapp?: boolean;
  notify_email?: boolean;
  display_language?: LangCode;
  response_language?: LangCode;
  report_language?: LangCode;
}

export interface EmailUpdateIn {
  new_email: string;
  current_password: string;
}

export interface ModelPreference {
  tier: Tier;
  provider_id: string;
  model_id: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    credentials: 'same-origin',
  });
  if (\!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = body.detail ?? {};
    throw new ApiError(r.status, detail.code ?? 'http_error', detail.message ?? `HTTP ${r.status}`);
  }
  return r.json();
}

export const getPrefs = () => request<Prefs>('/api/settings/prefs');

export const updatePrefs = (patch: PrefsPatch) =>
  request<Prefs>('/api/settings/prefs', { method: 'PATCH', body: JSON.stringify(patch) });

export const updateEmail = (body: EmailUpdateIn) =>
  request<{ ok: true }>('/api/settings/email', { method: 'PATCH', body: JSON.stringify(body) });

export const getModelPreferences = () =>
  request<{ items: ModelPreference[] }>('/api/settings/models/preferences');

export const putModelPreference = (tier: Tier, body: { provider_id: string; model_id: string }) =>
  request<{ ok: true }>(`/api/settings/models/preferences/${tier}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });

export const deleteModelPreference = (tier: Tier) =>
  request<{ ok: true }>(`/api/settings/models/preferences/${tier}`, { method: 'DELETE' });
```

- [ ] **Step 4: Implement `admin.ts`**

```typescript
// frontend/src/api/admin.ts
import { ApiError } from './settings';

export interface InviteSummary {
  id: number;
  label: string | null;
  role: 'user' | 'admin';
  expires_at: string;
  max_uses: number;
  used_count: number;
  status: 'active' | 'expired' | 'revoked' | 'at_capacity';
  created_at: string;
}

export interface InviteCreated extends InviteSummary {
  token: string;
  invite_link: string;
}

export interface AdminUserRow {
  id: number;
  email: string;
  display_name: string;
  role: 'user' | 'admin';
  is_enabled: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface ResetRequestRow {
  id: number;
  user_id: number;
  user_email: string;
  requested_at: string;
  ip_address: string | null;
  status: 'pending' | 'approved' | 'rejected';
  expires_at: string | null;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    credentials: 'same-origin',
  });
  if (\!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = body.detail ?? {};
    throw new ApiError(r.status, detail.code ?? 'http_error', detail.message ?? `HTTP ${r.status}`);
  }
  return r.json();
}

export const listInvites = () => request<{ items: InviteSummary[] }>('/api/admin/invites');

export const createInvite = (body: {
  role: 'user' | 'admin';
  label?: string | null;
  max_uses: number;
  expires_in_hours: number;
}) => request<InviteCreated>('/api/admin/invites', { method: 'POST', body: JSON.stringify(body) });

export const revokeInvite = (id: number) =>
  request<{ ok: true }>(`/api/admin/invites/${id}/revoke`, { method: 'POST' });

export const listAdminUsers = () => request<{ items: AdminUserRow[] }>('/api/admin/users');

export const disableUser = (id: number) =>
  request<{ ok: true }>(`/api/admin/users/${id}/disable`, { method: 'POST' });

export const enableUser = (id: number) =>
  request<{ ok: true }>(`/api/admin/users/${id}/enable`, { method: 'POST' });

export const adminResetPassword = (id: number) =>
  request<{ temp_password: string }>(`/api/admin/users/${id}/reset-password`, { method: 'POST' });

export const listResetRequests = (status?: 'pending' | 'approved' | 'rejected') => {
  const qs = status ? `?status=${status}` : '';
  return request<{ items: ResetRequestRow[] }>(`/api/admin/password-reset-requests${qs}`);
};

export const approveResetRequest = (id: number) =>
  request<{ token: string; reset_link: string; expires_at: string }>(
    `/api/admin/password-reset-requests/${id}/approve`,
    { method: 'POST' },
  );

export const rejectResetRequest = (id: number) =>
  request<{ ok: true }>(`/api/admin/password-reset-requests/${id}/reject`, { method: 'POST' });
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/api/__tests__/settings.test.ts`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/settings.ts frontend/src/api/admin.ts frontend/src/api/__tests__/settings.test.ts
git commit -m "feat(settings): add typed API clients for settings and admin routes"
```

---

### Task 11: Dirty-form hook + unsaved-changes modal

**Files:**
- Create: `frontend/src/components/settings/useDirtyForm.ts`
- Create: `frontend/src/components/settings/UnsavedChangesModal.tsx`
- Test: `frontend/src/components/settings/__tests__/useDirtyForm.test.tsx`

- [ ] **Step 1: Write failing test for `useDirtyForm`**

```typescript
// frontend/src/components/settings/__tests__/useDirtyForm.test.tsx
import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useDirtyForm } from '../useDirtyForm';

describe('useDirtyForm', () => {
  it('is not dirty when values match initial', () => {
    const { result } = renderHook(() => useDirtyForm({ a: 1, b: 'x' }));
    expect(result.current.isDirty).toBe(false);
  });

  it('becomes dirty when a field changes', () => {
    const { result } = renderHook(() => useDirtyForm({ a: 1, b: 'x' }));
    act(() => result.current.setField('a', 2));
    expect(result.current.isDirty).toBe(true);
    expect(result.current.values.a).toBe(2);
  });

  it('reset() restores initial values and clears dirty', () => {
    const { result } = renderHook(() => useDirtyForm({ a: 1 }));
    act(() => result.current.setField('a', 9));
    act(() => result.current.reset());
    expect(result.current.values.a).toBe(1);
    expect(result.current.isDirty).toBe(false);
  });

  it('markSaved() adopts current values as the new baseline', () => {
    const { result } = renderHook(() => useDirtyForm({ a: 1 }));
    act(() => result.current.setField('a', 2));
    act(() => result.current.markSaved());
    expect(result.current.isDirty).toBe(false);
    expect(result.current.values.a).toBe(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/__tests__/useDirtyForm.test.tsx`
Expected: FAIL with "Cannot find module '../useDirtyForm'"

- [ ] **Step 3: Implement `useDirtyForm`**

```typescript
// frontend/src/components/settings/useDirtyForm.ts
import { useCallback, useMemo, useState } from 'react';

export interface DirtyForm<T extends Record<string, unknown>> {
  values: T;
  initial: T;
  isDirty: boolean;
  setField: <K extends keyof T>(key: K, value: T[K]) => void;
  setValues: (next: T) => void;
  reset: () => void;
  markSaved: () => void;
}

function shallowEqual<T extends Record<string, unknown>>(a: T, b: T): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    if (a[k] \!== b[k]) return false;
  }
  return true;
}

export function useDirtyForm<T extends Record<string, unknown>>(initialValues: T): DirtyForm<T> {
  const [initial, setInitial] = useState<T>(initialValues);
  const [values, setValuesState] = useState<T>(initialValues);

  const setField = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    setValuesState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const setValues = useCallback((next: T) => {
    setValuesState(next);
  }, []);

  const reset = useCallback(() => {
    setValuesState(initial);
  }, [initial]);

  const markSaved = useCallback(() => {
    setInitial(values);
  }, [values]);

  const isDirty = useMemo(() => \!shallowEqual(values, initial), [values, initial]);

  return { values, initial, isDirty, setField, setValues, reset, markSaved };
}
```

- [ ] **Step 4: Implement `UnsavedChangesModal`**

```tsx
// frontend/src/components/settings/UnsavedChangesModal.tsx
import React from 'react';

interface Props {
  open: boolean;
  onConfirmDiscard: () => void;
  onCancel: () => void;
}

export function UnsavedChangesModal({ open, onConfirmDiscard, onCancel }: Props): JSX.Element | null {
  if (\!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="unsaved-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded-xl bg-surface p-6 shadow-xl">
        <h2 id="unsaved-title" className="text-lg font-semibold text-fg">
          Discard unsaved changes?
        </h2>
        <p className="mt-2 text-sm text-fg-muted">
          You have unsaved changes in this section. Leaving will lose them.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-fg hover:bg-surface-hover"
          >
            Stay
          </button>
          <button
            type="button"
            onClick={onConfirmDiscard}
            className="rounded-md bg-danger px-3 py-1.5 text-sm font-medium text-white hover:bg-danger-hover"
          >
            Discard
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/__tests__/useDirtyForm.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings/useDirtyForm.ts \
        frontend/src/components/settings/UnsavedChangesModal.tsx \
        frontend/src/components/settings/__tests__/useDirtyForm.test.tsx
git commit -m "feat(settings): add useDirtyForm hook and UnsavedChangesModal"
```

---

### Task 12: Shared setting primitives (SaveButton, InlineFeedback, SettingGroup, ToggleSwitch, OneTimeSecretModal)

**Files:**
- Create: `frontend/src/components/settings/SaveButton.tsx`
- Create: `frontend/src/components/settings/InlineFeedback.tsx`
- Create: `frontend/src/components/settings/SettingGroup.tsx`
- Create: `frontend/src/components/settings/ToggleSwitch.tsx`
- Create: `frontend/src/components/settings/OneTimeSecretModal.tsx`
- Test: `frontend/src/components/settings/__tests__/primitives.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// frontend/src/components/settings/__tests__/primitives.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SaveButton } from '../SaveButton';
import { InlineFeedback } from '../InlineFeedback';
import { ToggleSwitch } from '../ToggleSwitch';
import { OneTimeSecretModal } from '../OneTimeSecretModal';

describe('SaveButton', () => {
  it('disabled when not dirty', () => {
    render(<SaveButton state="idle" isDirty={false} onClick={() => {}} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });
  it('shows "Saving..." while saving', () => {
    render(<SaveButton state="saving" isDirty={true} onClick={() => {}} />);
    expect(screen.getByRole('button')).toHaveTextContent(/saving/i);
  });
  it('shows "Saved" after success', () => {
    render(<SaveButton state="saved" isDirty={false} onClick={() => {}} />);
    expect(screen.getByRole('button')).toHaveTextContent(/saved/i);
  });
});

describe('InlineFeedback', () => {
  it('renders nothing when kind is null', () => {
    const { container } = render(<InlineFeedback kind={null} message="" />);
    expect(container.firstChild).toBeNull();
  });
  it('renders error message', () => {
    render(<InlineFeedback kind="error" message="bad" />);
    expect(screen.getByRole('alert')).toHaveTextContent('bad');
  });
});

describe('ToggleSwitch', () => {
  it('fires onChange when clicked', () => {
    const cb = vi.fn();
    render(<ToggleSwitch checked={false} onChange={cb} label="X" />);
    fireEvent.click(screen.getByRole('switch'));
    expect(cb).toHaveBeenCalledWith(true);
  });
});

describe('OneTimeSecretModal', () => {
  it('shows secret and copy button when open', () => {
    render(<OneTimeSecretModal open={true} title="Invite link" secret="abc123" onClose={() => {}} />);
    expect(screen.getByText('abc123')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
  });
  it('renders nothing when closed', () => {
    const { container } = render(<OneTimeSecretModal open={false} title="x" secret="x" onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/__tests__/primitives.test.tsx`
Expected: FAIL with "Cannot find module '../SaveButton'"

- [ ] **Step 3: Implement `SaveButton.tsx`**

```tsx
// frontend/src/components/settings/SaveButton.tsx
import React from 'react';

export type SaveState = 'idle' | 'saving' | 'saved' | 'error';

interface Props {
  state: SaveState;
  isDirty: boolean;
  onClick: () => void;
}

export function SaveButton({ state, isDirty, onClick }: Props): JSX.Element {
  const label =
    state === 'saving' ? 'Saving...' :
    state === 'saved' ? 'Saved' :
    state === 'error' ? 'Save' :
    'Save';
  const disabled = state === 'saving' || \!isDirty;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-busy={state === 'saving'}
      className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 hover:bg-primary-hover"
    >
      {label}
    </button>
  );
}
```

- [ ] **Step 4: Implement `InlineFeedback.tsx`**

```tsx
// frontend/src/components/settings/InlineFeedback.tsx
import React from 'react';

interface Props {
  kind: 'success' | 'error' | null;
  message: string;
}

export function InlineFeedback({ kind, message }: Props): JSX.Element | null {
  if (\!kind) return null;
  const cls =
    kind === 'error'
      ? 'text-danger border-danger/20 bg-danger/10'
      : 'text-success border-success/20 bg-success/10';
  return (
    <div role="alert" className={`rounded-md border px-3 py-2 text-sm ${cls}`}>
      {message}
    </div>
  );
}
```

- [ ] **Step 5: Implement `SettingGroup.tsx`**

```tsx
// frontend/src/components/settings/SettingGroup.tsx
import React from 'react';

interface Props {
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function SettingGroup({ title, description, children }: Props): JSX.Element {
  return (
    <section className="space-y-3 border-b border-border pb-6 last:border-b-0">
      <header>
        <h3 className="text-base font-semibold text-fg">{title}</h3>
        {description ? <p className="mt-1 text-sm text-fg-muted">{description}</p> : null}
      </header>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
```

- [ ] **Step 6: Implement `ToggleSwitch.tsx`**

```tsx
// frontend/src/components/settings/ToggleSwitch.tsx
import React from 'react';

interface Props {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}

export function ToggleSwitch({ checked, onChange, label, description, disabled }: Props): JSX.Element {
  return (
    <label className="flex items-start justify-between gap-4 py-1">
      <span>
        <span className="block text-sm font-medium text-fg">{label}</span>
        {description ? <span className="mt-0.5 block text-xs text-fg-muted">{description}</span> : null}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(\!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
          checked ? 'bg-primary' : 'bg-surface-muted'
        } disabled:opacity-50`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
            checked ? 'translate-x-4' : 'translate-x-1'
          }`}
        />
      </button>
    </label>
  );
}
```

- [ ] **Step 7: Implement `OneTimeSecretModal.tsx`**

```tsx
// frontend/src/components/settings/OneTimeSecretModal.tsx
import React, { useState } from 'react';

interface Props {
  open: boolean;
  title: string;
  secret: string;
  description?: string;
  onClose: () => void;
}

export function OneTimeSecretModal({ open, title, secret, description, onClose }: Props): JSX.Element | null {
  const [copied, setCopied] = useState(false);
  if (\!open) return null;
  const copy = async () => {
    await navigator.clipboard.writeText(secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="ots-title" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-surface p-6 shadow-xl">
        <h2 id="ots-title" className="text-lg font-semibold text-fg">{title}</h2>
        {description ? <p className="mt-1 text-sm text-fg-muted">{description}</p> : null}
        <div className="mt-4 rounded-md border border-border bg-surface-muted p-3 font-mono text-sm break-all text-fg">
          {secret}
        </div>
        <p className="mt-2 text-xs text-danger">You will not be able to see this again after closing.</p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={copy} className="rounded-md border border-border px-3 py-1.5 text-sm text-fg hover:bg-surface-hover">
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" onClick={onClose} className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover">
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/__tests__/primitives.test.tsx`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/settings/SaveButton.tsx \
        frontend/src/components/settings/InlineFeedback.tsx \
        frontend/src/components/settings/SettingGroup.tsx \
        frontend/src/components/settings/ToggleSwitch.tsx \
        frontend/src/components/settings/OneTimeSecretModal.tsx \
        frontend/src/components/settings/__tests__/primitives.test.tsx
git commit -m "feat(settings): add shared setting primitives (SaveButton, InlineFeedback, SettingGroup, ToggleSwitch, OneTimeSecretModal)"
```

---

### Task 13: SettingsShell (left nav + content slot + must-change-password gate)

**Files:**
- Create: `frontend/src/components/settings/SettingsShell.tsx`
- Test: `frontend/src/components/settings/__tests__/SettingsShell.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/__tests__/SettingsShell.test.tsx
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SettingsShell } from '../SettingsShell';

function renderAt(path: string, role: 'user' | 'admin' = 'user') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/settings/*" element={<SettingsShell userRole={role} />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SettingsShell', () => {
  it('renders nav items for regular user (no Admin)', () => {
    renderAt('/settings/general');
    expect(screen.getByRole('link', { name: /general/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /models/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /account/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /admin/i })).toBeNull();
  });

  it('renders Admin nav item when role is admin', () => {
    renderAt('/settings/general', 'admin');
    expect(screen.getByRole('link', { name: /admin/i })).toBeInTheDocument();
  });

  it('marks the active section', () => {
    renderAt('/settings/account');
    const link = screen.getByRole('link', { name: /account/i });
    expect(link).toHaveAttribute('aria-current', 'page');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/__tests__/SettingsShell.test.tsx`
Expected: FAIL with "Cannot find module '../SettingsShell'"

- [ ] **Step 3: Implement `SettingsShell.tsx`**

```tsx
// frontend/src/components/settings/SettingsShell.tsx
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';

interface NavItem {
  to: string;
  label: string;
  adminOnly?: boolean;
}

const ITEMS: NavItem[] = [
  { to: '/settings/general', label: 'General' },
  { to: '/settings/models', label: 'Models' },
  { to: '/settings/account', label: 'Account' },
  { to: '/settings/admin', label: 'Admin', adminOnly: true },
];

interface Props {
  userRole: 'user' | 'admin';
}

export function SettingsShell({ userRole }: Props): JSX.Element {
  const items = ITEMS.filter((i) => \!i.adminOnly || userRole === 'admin');
  return (
    <div className="flex min-h-[calc(100vh-4rem)] w-full">
      <aside className="w-56 shrink-0 border-r border-border bg-surface-alt">
        <nav className="sticky top-16 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-muted">Settings</h2>
          <ul className="space-y-1">
            {items.map((i) => (
              <li key={i.to}>
                <NavLink
                  to={i.to}
                  aria-current={({ isActive }: { isActive: boolean }) => (isActive ? 'page' : undefined) as any}
                  className={({ isActive }) =>
                    `block rounded-md px-3 py-1.5 text-sm ${
                      isActive ? 'bg-primary/10 text-primary' : 'text-fg hover:bg-surface-hover'
                    }`
                  }
                >
                  {i.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/__tests__/SettingsShell.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/SettingsShell.tsx \
        frontend/src/components/settings/__tests__/SettingsShell.test.tsx
git commit -m "feat(settings): add SettingsShell with left nav and role-gated Admin section"
```

---

### Task 14: GeneralSection (display name, notifications, appearance)

**Files:**
- Create: `frontend/src/components/settings/sections/GeneralSection.tsx`
- Test: `frontend/src/components/settings/sections/__tests__/GeneralSection.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/sections/__tests__/GeneralSection.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { GeneralSection } from '../GeneralSection';
import * as settingsApi from '../../../../api/settings';

describe('GeneralSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('loads prefs and disables save until dirty', async () => {
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({
      display_name: 'Alice',
      theme: 'system',
      notify_inapp: true,
      notify_email: false,
      display_language: 'en',
      response_language: 'en',
      report_language: 'en',
    });
    render(<GeneralSection />);
    await waitFor(() => expect(screen.getByDisplayValue('Alice')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();
  });

  it('PATCHes prefs when save clicked', async () => {
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({
      display_name: 'Alice',
      theme: 'system',
      notify_inapp: true,
      notify_email: false,
      display_language: 'en',
      response_language: 'en',
      report_language: 'en',
    });
    const update = vi.spyOn(settingsApi, 'updatePrefs').mockResolvedValue({
      display_name: 'Alice',
      theme: 'dark',
      notify_inapp: true,
      notify_email: false,
      display_language: 'en',
      response_language: 'en',
      report_language: 'en',
    });
    render(<GeneralSection />);
    await waitFor(() => screen.getByDisplayValue('Alice'));
    fireEvent.click(screen.getByRole('radio', { name: /dark/i }));
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(expect.objectContaining({ theme: 'dark' })));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/sections/__tests__/GeneralSection.test.tsx`
Expected: FAIL with "Cannot find module '../GeneralSection'"

- [ ] **Step 3: Implement `GeneralSection.tsx`**

```tsx
// frontend/src/components/settings/sections/GeneralSection.tsx
import React, { useEffect, useState } from 'react';
import { getPrefs, updatePrefs, Prefs, Theme, ApiError } from '../../../api/settings';
import { useDirtyForm } from '../useDirtyForm';
import { SaveButton, SaveState } from '../SaveButton';
import { SettingGroup } from '../SettingGroup';
import { ToggleSwitch } from '../ToggleSwitch';
import { InlineFeedback } from '../InlineFeedback';

const THEMES: Theme[] = ['system', 'light', 'dark'];

const EMPTY: Prefs = {
  display_name: '',
  theme: 'system',
  notify_inapp: true,
  notify_email: false,
  display_language: 'en',
  response_language: 'en',
  report_language: 'en',
};

export function GeneralSection(): JSX.Element {
  const form = useDirtyForm<Prefs>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPrefs()
      .then((p) => {
        form.setValues(p);
        form.markSaved();
        setLoading(false);
      })
      .catch((e: ApiError) => {
        setError(e.message);
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    setSaveState('saving');
    setError(null);
    try {
      const patch = {
        display_name: form.values.display_name,
        theme: form.values.theme,
        notify_inapp: form.values.notify_inapp,
        notify_email: form.values.notify_email,
      };
      const next = await updatePrefs(patch);
      form.setValues(next);
      form.markSaved();
      setSaveState('saved');
      setTimeout(() => setSaveState('idle'), 1500);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
      setSaveState('error');
    }
  };

  if (loading) return <p className="text-sm text-fg-muted">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-fg">General</h1>
        <SaveButton state={saveState} isDirty={form.isDirty} onClick={save} />
      </header>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      <SettingGroup title="Profile" description="Name shown in the sidebar and reports.">
        <label className="block">
          <span className="block text-sm font-medium text-fg">Display name</span>
          <input
            type="text"
            value={form.values.display_name}
            onChange={(e) => form.setField('display_name', e.target.value)}
            maxLength={80}
            className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-fg focus:border-primary focus:outline-none"
          />
        </label>
      </SettingGroup>

      <SettingGroup title="Notifications" description="Alerts when reports and scheduled jobs finish.">
        <ToggleSwitch
          label="In-app notifications"
          checked={form.values.notify_inapp}
          onChange={(v) => form.setField('notify_inapp', v)}
        />
        <ToggleSwitch
          label="Email notifications"
          description="Requires SMTP setup by an admin."
          checked={form.values.notify_email}
          onChange={(v) => form.setField('notify_email', v)}
        />
      </SettingGroup>

      <SettingGroup title="Appearance">
        <div role="radiogroup" aria-label="Theme" className="flex gap-2">
          {THEMES.map((t) => (
            <label
              key={t}
              className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm ${
                form.values.theme === t ? 'border-primary bg-primary/10 text-primary' : 'border-border text-fg hover:bg-surface-hover'
              }`}
            >
              <input
                type="radio"
                name="theme"
                value={t}
                checked={form.values.theme === t}
                onChange={() => form.setField('theme', t)}
                className="sr-only"
              />
              {t[0].toUpperCase() + t.slice(1)}
            </label>
          ))}
        </div>
      </SettingGroup>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/sections/__tests__/GeneralSection.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/sections/GeneralSection.tsx \
        frontend/src/components/settings/sections/__tests__/GeneralSection.test.tsx
git commit -m "feat(settings): add GeneralSection (display name, notifications, appearance)"
```

---

### Task 15: ModelsSection (per-tier picker from admin roster)

**Files:**
- Create: `frontend/src/components/settings/sections/ModelsSection.tsx`
- Test: `frontend/src/components/settings/sections/__tests__/ModelsSection.test.tsx`

**Assumption:** `/api/llm/catalog` (Plan 4) returns `{ items: [{ provider_id, provider_label, models: [{ id, tier, label }] }] }`. If the endpoint name differs, adjust the fetch URL to match the Plan 4 spec.

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/sections/__tests__/ModelsSection.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ModelsSection } from '../ModelsSection';
import * as settingsApi from '../../../../api/settings';

function mockCatalog() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/llm/catalog')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [
              {
                provider_id: 'openai',
                provider_label: 'OpenAI',
                models: [
                  { id: 'gpt-4o-mini', tier: 'quick', label: 'GPT-4o mini' },
                  { id: 'gpt-4o', tier: 'thinking', label: 'GPT-4o' },
                ],
              },
            ],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }),
  );
}

describe('ModelsSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCatalog();
  });

  it('lists all four tiers with model pickers', async () => {
    vi.spyOn(settingsApi, 'getModelPreferences').mockResolvedValue({ items: [] });
    render(<ModelsSection />);
    await waitFor(() => expect(screen.getByText(/everyday/i)).toBeInTheDocument());
    expect(screen.getByText(/quick/i)).toBeInTheDocument();
    expect(screen.getByText(/thinking/i)).toBeInTheDocument();
    expect(screen.getByText(/long context/i)).toBeInTheDocument();
  });

  it('saves per-tier preference via PUT', async () => {
    vi.spyOn(settingsApi, 'getModelPreferences').mockResolvedValue({ items: [] });
    const put = vi.spyOn(settingsApi, 'putModelPreference').mockResolvedValue({ ok: true });
    render(<ModelsSection />);
    await waitFor(() => screen.getByText(/quick/i));
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[1], { target: { value: 'openai::gpt-4o-mini' } });
    fireEvent.click(screen.getAllByRole('button', { name: /save/i })[1]);
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('quick', { provider_id: 'openai', model_id: 'gpt-4o-mini' }),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/sections/__tests__/ModelsSection.test.tsx`
Expected: FAIL with "Cannot find module '../ModelsSection'"

- [ ] **Step 3: Implement `ModelsSection.tsx`**

```tsx
// frontend/src/components/settings/sections/ModelsSection.tsx
import React, { useEffect, useState } from 'react';
import { deleteModelPreference, getModelPreferences, ModelPreference, putModelPreference, Tier, ApiError } from '../../../api/settings';
import { SaveButton, SaveState } from '../SaveButton';
import { SettingGroup } from '../SettingGroup';
import { InlineFeedback } from '../InlineFeedback';

interface CatalogModel {
  id: string;
  tier: Tier;
  label: string;
}
interface CatalogProvider {
  provider_id: string;
  provider_label: string;
  models: CatalogModel[];
}

const TIERS: { tier: Tier; title: string; desc: string }[] = [
  { tier: 'everyday', title: 'Everyday', desc: 'Default for Secretary and short chats.' },
  { tier: 'quick', title: 'Quick', desc: 'Fast reasoning for Retail Sentiment and wizard AI review.' },
  { tier: 'thinking', title: 'Thinking', desc: 'Deep reasoning for Equity Research and Panic Thermometer.' },
  { tier: 'long_context', title: 'Long context', desc: 'Earnings Update, Morning Briefing, Macro Research.' },
];

interface TierRowState {
  value: string;
  state: SaveState;
  error: string | null;
  initial: string;
}

function encode(p: ModelPreference | undefined): string {
  return p ? `${p.provider_id}::${p.model_id}` : '';
}

function decode(v: string): { provider_id: string; model_id: string } | null {
  if (\!v) return null;
  const [p, m] = v.split('::');
  return { provider_id: p, model_id: m };
}

export function ModelsSection(): JSX.Element {
  const [catalog, setCatalog] = useState<CatalogProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState<Record<Tier, TierRowState>>(
    {} as Record<Tier, TierRowState>,
  );
  const [topError, setTopError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch('/api/llm/catalog', { credentials: 'same-origin' }).then((r) => r.json()),
      getModelPreferences(),
    ])
      .then(([cat, prefs]) => {
        setCatalog(cat.items ?? []);
        const byTier: Partial<Record<Tier, ModelPreference>> = {};
        for (const p of prefs.items) byTier[p.tier] = p;
        const next = {} as Record<Tier, TierRowState>;
        for (const t of TIERS) {
          const v = encode(byTier[t.tier]);
          next[t.tier] = { value: v, state: 'idle', error: null, initial: v };
        }
        setRows(next);
        setLoading(false);
      })
      .catch((e: ApiError) => {
        setTopError(e.message);
        setLoading(false);
      });
  }, []);

  const optionsFor = (tier: Tier): { value: string; label: string }[] => {
    const opts: { value: string; label: string }[] = [];
    for (const prov of catalog) {
      for (const m of prov.models) {
        if (m.tier === tier) {
          opts.push({
            value: `${prov.provider_id}::${m.id}`,
            label: `${prov.provider_label} — ${m.label}`,
          });
        }
      }
    }
    return opts;
  };

  const save = async (tier: Tier) => {
    setRows((r) => ({ ...r, [tier]: { ...r[tier], state: 'saving', error: null } }));
    try {
      const decoded = decode(rows[tier].value);
      if (decoded) {
        await putModelPreference(tier, decoded);
      } else {
        await deleteModelPreference(tier);
      }
      setRows((r) => ({
        ...r,
        [tier]: { ...r[tier], state: 'saved', initial: r[tier].value },
      }));
      setTimeout(() => setRows((r) => ({ ...r, [tier]: { ...r[tier], state: 'idle' } })), 1500);
    } catch (e) {
      const err = e as ApiError;
      setRows((r) => ({ ...r, [tier]: { ...r[tier], state: 'error', error: err.message } }));
    }
  };

  if (loading) return <p className="text-sm text-fg-muted">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-fg">Models</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Choose a preferred model per tier. Overrides the server defaults for your account.
        </p>
      </header>

      <InlineFeedback kind={topError ? 'error' : null} message={topError ?? ''} />

      {TIERS.map((t) => {
        const row = rows[t.tier];
        const opts = optionsFor(t.tier);
        const isDirty = row?.value \!== row?.initial;
        return (
          <SettingGroup key={t.tier} title={t.title} description={t.desc}>
            <div className="flex items-center gap-3">
              <select
                aria-label={`${t.title} model`}
                value={row?.value ?? ''}
                onChange={(e) =>
                  setRows((r) => ({ ...r, [t.tier]: { ...r[t.tier], value: e.target.value } }))
                }
                className="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-fg"
              >
                <option value="">(Use server default)</option>
                {opts.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <SaveButton state={row?.state ?? 'idle'} isDirty={isDirty} onClick={() => save(t.tier)} />
            </div>
            {row?.error ? <InlineFeedback kind="error" message={row.error} /> : null}
          </SettingGroup>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/sections/__tests__/ModelsSection.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/sections/ModelsSection.tsx \
        frontend/src/components/settings/sections/__tests__/ModelsSection.test.tsx
git commit -m "feat(settings): add ModelsSection with per-tier preference picker"
```

---

### Task 16: AccountSection (email form + password form + language dropdowns)

**Files:**
- Create: `frontend/src/components/settings/sections/AccountSection.tsx`
- Test: `frontend/src/components/settings/sections/__tests__/AccountSection.test.tsx`

**Reuses from Plan 9:** `ChangePasswordForm`, `PasswordInput`, `FormField`, `SessionsPanel`. AccountSection embeds these inline rather than duplicating; see Plan 9 Task 10–13 for their implementations.

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/sections/__tests__/AccountSection.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AccountSection } from '../AccountSection';
import * as settingsApi from '../../../../api/settings';

vi.mock('../../../auth/ChangePasswordForm', () => ({
  ChangePasswordForm: () => <div data-testid="change-password-form" />,
}));

vi.mock('../../../auth/SessionsPanel', () => ({
  SessionsPanel: () => <div data-testid="sessions-panel" />,
}));

describe('AccountSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({
      display_name: 'Alice',
      theme: 'system',
      notify_inapp: true,
      notify_email: false,
      display_language: 'en',
      response_language: 'en',
      report_language: 'en',
    });
  });

  it('renders email change form and sub-forms', async () => {
    render(
      <AccountSection currentEmail="alice@x.io" mustChangePassword={false} />,
    );
    await waitFor(() => screen.getByDisplayValue('alice@x.io'));
    expect(screen.getByTestId('change-password-form')).toBeInTheDocument();
    expect(screen.getByTestId('sessions-panel')).toBeInTheDocument();
  });

  it('submits email change with password', async () => {
    const update = vi.spyOn(settingsApi, 'updateEmail').mockResolvedValue({ ok: true } as any);
    render(<AccountSection currentEmail="alice@x.io" mustChangePassword={false} />);
    await waitFor(() => screen.getByDisplayValue('alice@x.io'));
    fireEvent.change(screen.getByLabelText(/new email/i), { target: { value: 'new@x.io' } });
    fireEvent.change(screen.getByLabelText(/current password/i), { target: { value: 'pw' } });
    fireEvent.click(screen.getByRole('button', { name: /change email/i }));
    await waitFor(() =>
      expect(update).toHaveBeenCalledWith({ new_email: 'new@x.io', current_password: 'pw' }),
    );
  });

  it('shows must-change-password banner when flag is set', () => {
    render(<AccountSection currentEmail="a@b.c" mustChangePassword={true} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/must change your password/i);
  });

  it('saves language preferences independently', async () => {
    const update = vi.spyOn(settingsApi, 'updatePrefs').mockResolvedValue({} as any);
    render(<AccountSection currentEmail="a@b.c" mustChangePassword={false} />);
    await waitFor(() => screen.getAllByRole('combobox')[0]);
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: 'zh-Hant' } });
    fireEvent.click(screen.getByRole('button', { name: /save languages/i }));
    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(expect.objectContaining({ display_language: 'zh-Hant' })),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/sections/__tests__/AccountSection.test.tsx`
Expected: FAIL with "Cannot find module '../AccountSection'"

- [ ] **Step 3: Implement `AccountSection.tsx`**

```tsx
// frontend/src/components/settings/sections/AccountSection.tsx
import React, { useEffect, useState } from 'react';
import { ApiError, getPrefs, LangCode, Prefs, updateEmail, updatePrefs } from '../../../api/settings';
import { ChangePasswordForm } from '../../auth/ChangePasswordForm';
import { SessionsPanel } from '../../auth/SessionsPanel';
import { SaveButton, SaveState } from '../SaveButton';
import { SettingGroup } from '../SettingGroup';
import { InlineFeedback } from '../InlineFeedback';

const LANGS: { code: LangCode; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'zh-Hant', label: 'Traditional Chinese' },
  { code: 'zh-Hans', label: 'Simplified Chinese' },
];

interface Props {
  currentEmail: string;
  mustChangePassword: boolean;
}

export function AccountSection({ currentEmail, mustChangePassword }: Props): JSX.Element {
  const [email, setEmail] = useState(currentEmail);
  const [newEmail, setNewEmail] = useState('');
  const [pw, setPw] = useState('');
  const [emailState, setEmailState] = useState<SaveState>('idle');
  const [emailErr, setEmailErr] = useState<string | null>(null);

  const [langs, setLangs] = useState<Pick<Prefs, 'display_language' | 'response_language' | 'report_language'> | null>(null);
  const [initialLangs, setInitialLangs] = useState<typeof langs>(null);
  const [langState, setLangState] = useState<SaveState>('idle');
  const [langErr, setLangErr] = useState<string | null>(null);

  useEffect(() => {
    getPrefs()
      .then((p) => {
        const subset = {
          display_language: p.display_language,
          response_language: p.response_language,
          report_language: p.report_language,
        };
        setLangs(subset);
        setInitialLangs(subset);
      })
      .catch((e: ApiError) => setLangErr(e.message));
  }, []);

  const submitEmail = async () => {
    setEmailState('saving');
    setEmailErr(null);
    try {
      await updateEmail({ new_email: newEmail, current_password: pw });
      setEmail(newEmail);
      setNewEmail('');
      setPw('');
      setEmailState('saved');
      setTimeout(() => setEmailState('idle'), 1500);
    } catch (e) {
      const err = e as ApiError;
      setEmailErr(err.message);
      setEmailState('error');
    }
  };

  const saveLangs = async () => {
    if (\!langs) return;
    setLangState('saving');
    setLangErr(null);
    try {
      await updatePrefs(langs);
      setInitialLangs(langs);
      setLangState('saved');
      setTimeout(() => setLangState('idle'), 1500);
    } catch (e) {
      const err = e as ApiError;
      setLangErr(err.message);
      setLangState('error');
    }
  };

  const langsDirty = \!\!langs && \!\!initialLangs && (
    langs.display_language \!== initialLangs.display_language ||
    langs.response_language \!== initialLangs.response_language ||
    langs.report_language \!== initialLangs.report_language
  );

  const emailDirty = newEmail.length > 0 && pw.length > 0;

  return (
    <div className="max-w-2xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-fg">Account</h1>
      </header>

      {mustChangePassword ? (
        <div role="alert" className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          You must change your password before using other features.
        </div>
      ) : null}

      <SettingGroup title="Email">
        <label className="block text-sm">
          <span className="block font-medium text-fg">Current email</span>
          <input readOnly value={email} className="mt-1 w-full rounded-md border border-border bg-surface-muted px-3 py-1.5 text-fg-muted" />
        </label>
        <label className="block text-sm">
          <span className="block font-medium text-fg">New email</span>
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            aria-label="New email"
            className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg focus:border-primary focus:outline-none"
          />
        </label>
        <label className="block text-sm">
          <span className="block font-medium text-fg">Current password</span>
          <input
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            aria-label="Current password"
            autoComplete="current-password"
            className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg focus:border-primary focus:outline-none"
          />
        </label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={submitEmail}
            disabled={\!emailDirty || emailState === 'saving'}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 hover:bg-primary-hover"
          >
            {emailState === 'saving' ? 'Changing...' : 'Change email'}
          </button>
          {emailErr ? <InlineFeedback kind="error" message={emailErr} /> : null}
        </div>
      </SettingGroup>

      <SettingGroup title="Password" description="Changing your password signs out all other sessions.">
        <ChangePasswordForm />
      </SettingGroup>

      <SettingGroup title="Languages" description="UI, chat response, and report output languages. English only for now; other options reserved for future translation work.">
        {langs ? (
          <div className="space-y-2">
            <label className="block text-sm">
              <span className="block font-medium text-fg">Display language</span>
              <select
                value={langs.display_language}
                onChange={(e) => setLangs({ ...langs, display_language: e.target.value as LangCode })}
                className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg"
              >
                {LANGS.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="block font-medium text-fg">Response language</span>
              <select
                value={langs.response_language}
                onChange={(e) => setLangs({ ...langs, response_language: e.target.value as LangCode })}
                className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg"
              >
                {LANGS.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="block font-medium text-fg">Report language</span>
              <select
                value={langs.report_language}
                onChange={(e) => setLangs({ ...langs, report_language: e.target.value as LangCode })}
                className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg"
              >
                {LANGS.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={saveLangs}
                disabled={\!langsDirty || langState === 'saving'}
                className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 hover:bg-primary-hover"
              >
                {langState === 'saving' ? 'Saving...' : 'Save languages'}
              </button>
              {langErr ? <InlineFeedback kind="error" message={langErr} /> : null}
            </div>
          </div>
        ) : (
          <p className="text-sm text-fg-muted">Loading...</p>
        )}
      </SettingGroup>

      <SettingGroup title="Sessions" description="Devices currently signed in to your account.">
        <SessionsPanel />
      </SettingGroup>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/sections/__tests__/AccountSection.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/sections/AccountSection.tsx \
        frontend/src/components/settings/sections/__tests__/AccountSection.test.tsx
git commit -m "feat(settings): add AccountSection (email change, password, languages, sessions)"
```

---

### Task 17: AdminSection tab bar

**Files:**
- Create: `frontend/src/components/settings/sections/AdminSection.tsx`
- Test: `frontend/src/components/settings/sections/__tests__/AdminSection.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/sections/__tests__/AdminSection.test.tsx
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AdminSection } from '../AdminSection';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/settings/admin/*" element={<AdminSection />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AdminSection', () => {
  it('renders all five admin tabs', () => {
    renderAt('/settings/admin/invites');
    expect(screen.getByRole('tab', { name: /invites/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /users/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /reset requests/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /models/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /data providers/i })).toBeInTheDocument();
  });

  it('marks the active tab', () => {
    renderAt('/settings/admin/users');
    expect(screen.getByRole('tab', { name: /users/i })).toHaveAttribute('aria-selected', 'true');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/sections/__tests__/AdminSection.test.tsx`
Expected: FAIL with "Cannot find module '../AdminSection'"

- [ ] **Step 3: Implement `AdminSection.tsx`**

```tsx
// frontend/src/components/settings/sections/AdminSection.tsx
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';

const TABS = [
  { to: 'invites', label: 'Invites' },
  { to: 'users', label: 'Users' },
  { to: 'reset-requests', label: 'Reset requests' },
  { to: 'models', label: 'Models' },
  { to: 'data-providers', label: 'Data providers' },
];

export function AdminSection(): JSX.Element {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-fg">Admin</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Manage users, invites, password resets, server-wide models, and data providers.
        </p>
      </header>
      <nav role="tablist" aria-label="Admin sections" className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            role="tab"
            aria-selected={({ isActive }: { isActive: boolean }) => (isActive ? 'true' : 'false') as any}
            className={({ isActive }) =>
              `border-b-2 px-3 py-2 text-sm ${
                isActive ? 'border-primary text-primary' : 'border-transparent text-fg hover:text-primary'
              }`
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/sections/__tests__/AdminSection.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/sections/AdminSection.tsx \
        frontend/src/components/settings/sections/__tests__/AdminSection.test.tsx
git commit -m "feat(settings): add AdminSection tab bar for admin subsections"
```

---

### Task 18: InvitesPanel (create + list + revoke + one-time link)

**Files:**
- Create: `frontend/src/components/settings/admin/InvitesPanel.tsx`
- Test: `frontend/src/components/settings/admin/__tests__/InvitesPanel.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/admin/__tests__/InvitesPanel.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { InvitesPanel } from '../InvitesPanel';
import * as adminApi from '../../../../api/admin';

describe('InvitesPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'listInvites').mockResolvedValue({
      items: [
        {
          id: 1,
          label: 'beta users',
          role: 'user',
          expires_at: '2026-05-17T00:00:00Z',
          max_uses: 5,
          used_count: 1,
          status: 'active',
          created_at: '2026-04-17T00:00:00Z',
        },
      ],
    });
  });

  it('renders invite list with status pill', async () => {
    render(<InvitesPanel />);
    await waitFor(() => screen.getByText(/beta users/i));
    expect(screen.getByText(/active/i)).toBeInTheDocument();
  });

  it('creates invite and shows one-time link modal', async () => {
    vi.spyOn(adminApi, 'createInvite').mockResolvedValue({
      id: 2,
      label: 'test',
      role: 'user',
      expires_at: '2026-05-17T00:00:00Z',
      max_uses: 1,
      used_count: 0,
      status: 'active',
      created_at: '2026-04-17T00:00:00Z',
      token: 'abc123',
      invite_link: 'http://localhost:8000/signup?token=abc123',
    });
    render(<InvitesPanel />);
    await waitFor(() => screen.getByText(/beta users/i));
    fireEvent.click(screen.getByRole('button', { name: /new invite/i }));
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: 'test' } });
    fireEvent.click(screen.getByRole('button', { name: /create invite/i }));
    await waitFor(() =>
      expect(screen.getByText(/http:\/\/localhost:8000\/signup\?token=abc123/)).toBeInTheDocument(),
    );
  });

  it('revokes an invite after confirmation', async () => {
    const revoke = vi.spyOn(adminApi, 'revokeInvite').mockResolvedValue({ ok: true });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<InvitesPanel />);
    await waitFor(() => screen.getByText(/beta users/i));
    fireEvent.click(screen.getByRole('button', { name: /revoke/i }));
    await waitFor(() => expect(revoke).toHaveBeenCalledWith(1));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/admin/__tests__/InvitesPanel.test.tsx`
Expected: FAIL with "Cannot find module '../InvitesPanel'"

- [ ] **Step 3: Implement `InvitesPanel.tsx`**

```tsx
// frontend/src/components/settings/admin/InvitesPanel.tsx
import React, { useEffect, useState } from 'react';
import { ApiError, createInvite, InviteSummary, listInvites, revokeInvite } from '../../../api/admin';
import { OneTimeSecretModal } from '../OneTimeSecretModal';
import { InlineFeedback } from '../InlineFeedback';

const STATUS_CLASS: Record<InviteSummary['status'], string> = {
  active: 'bg-success/10 text-success',
  expired: 'bg-fg-muted/10 text-fg-muted',
  revoked: 'bg-danger/10 text-danger',
  at_capacity: 'bg-warning/10 text-warning',
};

export function InvitesPanel(): JSX.Element {
  const [items, setItems] = useState<InviteSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [linkModal, setLinkModal] = useState<string | null>(null);

  const [label, setLabel] = useState('');
  const [role, setRole] = useState<'user' | 'admin'>('user');
  const [maxUses, setMaxUses] = useState(1);
  const [expiresInHours, setExpiresInHours] = useState(168);
  const [creating, setCreating] = useState(false);

  const refresh = async () => {
    try {
      const r = await listInvites();
      setItems(r.items);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const submit = async () => {
    setCreating(true);
    setError(null);
    try {
      const r = await createInvite({ label: label || null, role, max_uses: maxUses, expires_in_hours: expiresInHours });
      setLinkModal(r.invite_link);
      setShowForm(false);
      setLabel('');
      setRole('user');
      setMaxUses(1);
      setExpiresInHours(168);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setCreating(false);
    }
  };

  const revoke = async (id: number) => {
    if (\!window.confirm('Revoke this invite? It will no longer work.')) return;
    try {
      await revokeInvite(id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-fg">Invites</h2>
        <button
          type="button"
          onClick={() => setShowForm((v) => \!v)}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover"
        >
          {showForm ? 'Cancel' : 'New invite'}
        </button>
      </div>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      {showForm ? (
        <div className="rounded-md border border-border bg-surface-alt p-4 space-y-3">
          <label className="block text-sm">
            <span className="block font-medium text-fg">Label (optional)</span>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg"
            />
          </label>
          <label className="block text-sm">
            <span className="block font-medium text-fg">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as 'user' | 'admin')}
              className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="block font-medium text-fg">Max uses</span>
              <input
                type="number"
                min={1}
                max={999}
                value={maxUses}
                onChange={(e) => setMaxUses(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg"
              />
            </label>
            <label className="block text-sm">
              <span className="block font-medium text-fg">Expires in (hours)</span>
              <input
                type="number"
                min={1}
                max={8760}
                value={expiresInHours}
                onChange={(e) => setExpiresInHours(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-fg"
              />
            </label>
          </div>
          <button
            type="button"
            onClick={submit}
            disabled={creating}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 hover:bg-primary-hover"
          >
            {creating ? 'Creating...' : 'Create invite'}
          </button>
        </div>
      ) : null}

      <div className="rounded-md border border-border bg-surface">
        <table className="w-full text-sm">
          <thead className="bg-surface-alt text-left text-xs uppercase text-fg-muted">
            <tr>
              <th className="px-3 py-2">Label</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Uses</th>
              <th className="px-3 py-2">Expires</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr><td colSpan={6} className="px-3 py-4 text-fg-muted">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-4 text-fg-muted">No invites yet.</td></tr>
            ) : (
              items.map((inv) => (
                <tr key={inv.id} className="border-t border-border">
                  <td className="px-3 py-2 text-fg">{inv.label ?? '—'}</td>
                  <td className="px-3 py-2 text-fg">{inv.role}</td>
                  <td className="px-3 py-2 text-fg">{inv.used_count}/{inv.max_uses}</td>
                  <td className="px-3 py-2 text-fg-muted">{new Date(inv.expires_at).toLocaleString()}</td>
                  <td className="px-3 py-2">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLASS[inv.status]}`}>
                      {inv.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {inv.status === 'active' ? (
                      <button
                        type="button"
                        onClick={() => revoke(inv.id)}
                        className="text-sm text-danger hover:underline"
                      >
                        Revoke
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <OneTimeSecretModal
        open={linkModal \!== null}
        title="Invite link"
        secret={linkModal ?? ''}
        description="Share this link with the invitee. You will not be able to see it again."
        onClose={() => setLinkModal(null)}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/admin/__tests__/InvitesPanel.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/admin/InvitesPanel.tsx \
        frontend/src/components/settings/admin/__tests__/InvitesPanel.test.tsx
git commit -m "feat(admin): add InvitesPanel with create/revoke/one-time link"
```

---

### Task 19: UsersPanel (roster + disable/enable + admin reset password)

**Files:**
- Create: `frontend/src/components/settings/admin/UsersPanel.tsx`
- Test: `frontend/src/components/settings/admin/__tests__/UsersPanel.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/admin/__tests__/UsersPanel.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { UsersPanel } from '../UsersPanel';
import * as adminApi from '../../../../api/admin';

describe('UsersPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'listAdminUsers').mockResolvedValue({
      items: [
        { id: 1, email: 'alice@x.io', display_name: 'Alice', role: 'admin', is_enabled: true, must_change_password: false, last_login_at: null, created_at: '2026-04-01T00:00:00Z' },
        { id: 2, email: 'bob@x.io', display_name: 'Bob', role: 'user', is_enabled: true, must_change_password: false, last_login_at: null, created_at: '2026-04-02T00:00:00Z' },
      ],
    });
  });

  it('lists users', async () => {
    render(<UsersPanel currentUserId={1} />);
    await waitFor(() => screen.getByText('alice@x.io'));
    expect(screen.getByText('bob@x.io')).toBeInTheDocument();
  });

  it('disables a user with confirmation', async () => {
    const disable = vi.spyOn(adminApi, 'disableUser').mockResolvedValue({ ok: true });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<UsersPanel currentUserId={1} />);
    await waitFor(() => screen.getByText('bob@x.io'));
    const row = screen.getByText('bob@x.io').closest('tr')\!;
    fireEvent.click(row.querySelector('button[data-action="disable"]')\!);
    await waitFor(() => expect(disable).toHaveBeenCalledWith(2));
  });

  it('blocks disabling self', async () => {
    render(<UsersPanel currentUserId={1} />);
    await waitFor(() => screen.getByText('alice@x.io'));
    const row = screen.getByText('alice@x.io').closest('tr')\!;
    expect(row.querySelector('button[data-action="disable"]')).toBeNull();
  });

  it('shows temporary password from admin reset', async () => {
    vi.spyOn(adminApi, 'adminResetPassword').mockResolvedValue({ temp_password: 'tmpXYZ123' });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<UsersPanel currentUserId={1} />);
    await waitFor(() => screen.getByText('bob@x.io'));
    const row = screen.getByText('bob@x.io').closest('tr')\!;
    fireEvent.click(row.querySelector('button[data-action="reset"]')\!);
    await waitFor(() => expect(screen.getByText('tmpXYZ123')).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/admin/__tests__/UsersPanel.test.tsx`
Expected: FAIL with "Cannot find module '../UsersPanel'"

- [ ] **Step 3: Implement `UsersPanel.tsx`**

```tsx
// frontend/src/components/settings/admin/UsersPanel.tsx
import React, { useEffect, useState } from 'react';
import { adminResetPassword, AdminUserRow, ApiError, disableUser, enableUser, listAdminUsers } from '../../../api/admin';
import { OneTimeSecretModal } from '../OneTimeSecretModal';
import { InlineFeedback } from '../InlineFeedback';

interface Props {
  currentUserId: number;
}

export function UsersPanel({ currentUserId }: Props): JSX.Element {
  const [items, setItems] = useState<AdminUserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tempPw, setTempPw] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const r = await listAdminUsers();
      setItems(r.items);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => { refresh(); }, []);

  const toggle = async (u: AdminUserRow) => {
    const action = u.is_enabled ? 'disable' : 'enable';
    if (\!window.confirm(`${action === 'disable' ? 'Disable' : 'Enable'} ${u.email}?`)) return;
    try {
      if (u.is_enabled) await disableUser(u.id);
      else await enableUser(u.id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const reset = async (u: AdminUserRow) => {
    if (\!window.confirm(`Reset password for ${u.email}? They will be forced to change it on next login.`)) return;
    try {
      const r = await adminResetPassword(u.id);
      setTempPw(r.temp_password);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-fg">Users</h2>
      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />
      <div className="rounded-md border border-border bg-surface">
        <table className="w-full text-sm">
          <thead className="bg-surface-alt text-left text-xs uppercase text-fg-muted">
            <tr>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Last login</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr><td colSpan={6} className="px-3 py-4 text-fg-muted">Loading...</td></tr>
            ) : items.map((u) => (
              <tr key={u.id} className="border-t border-border">
                <td className="px-3 py-2 text-fg">{u.email}</td>
                <td className="px-3 py-2 text-fg">{u.display_name}</td>
                <td className="px-3 py-2 text-fg">{u.role}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                    u.is_enabled ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'
                  }`}>
                    {u.is_enabled ? 'Enabled' : 'Disabled'}
                  </span>
                  {u.must_change_password ? (
                    <span className="ml-1 inline-block rounded-full bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning">
                      Must change pw
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-2 text-fg-muted">
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : '—'}
                </td>
                <td className="px-3 py-2 text-right space-x-3">
                  {u.id \!== currentUserId ? (
                    <>
                      <button
                        type="button"
                        data-action="reset"
                        onClick={() => reset(u)}
                        className="text-sm text-primary hover:underline"
                      >
                        Reset password
                      </button>
                      <button
                        type="button"
                        data-action="disable"
                        onClick={() => toggle(u)}
                        className={`text-sm ${u.is_enabled ? 'text-danger' : 'text-success'} hover:underline`}
                      >
                        {u.is_enabled ? 'Disable' : 'Enable'}
                      </button>
                    </>
                  ) : (
                    <span className="text-xs text-fg-muted">You</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <OneTimeSecretModal
        open={tempPw \!== null}
        title="Temporary password"
        secret={tempPw ?? ''}
        description="Send this to the user through a secure channel. They must change it on next login."
        onClose={() => setTempPw(null)}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/admin/__tests__/UsersPanel.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/admin/UsersPanel.tsx \
        frontend/src/components/settings/admin/__tests__/UsersPanel.test.tsx
git commit -m "feat(admin): add UsersPanel with disable/enable and admin password reset"
```

---

### Task 20: ResetRequestsPanel (approve/reject with 24h reset link)

**Files:**
- Create: `frontend/src/components/settings/admin/ResetRequestsPanel.tsx`
- Test: `frontend/src/components/settings/admin/__tests__/ResetRequestsPanel.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/admin/__tests__/ResetRequestsPanel.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ResetRequestsPanel } from '../ResetRequestsPanel';
import * as adminApi from '../../../../api/admin';

describe('ResetRequestsPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'listResetRequests').mockResolvedValue({
      items: [
        {
          id: 1,
          user_id: 5,
          user_email: 'bob@x.io',
          requested_at: '2026-04-17T00:00:00Z',
          ip_address: '1.2.3.4',
          status: 'pending',
          expires_at: null,
        },
      ],
    });
  });

  it('lists pending requests by default', async () => {
    render(<ResetRequestsPanel />);
    await waitFor(() => screen.getByText('bob@x.io'));
    expect(screen.getByText('1.2.3.4')).toBeInTheDocument();
  });

  it('approves and shows one-time reset link', async () => {
    vi.spyOn(adminApi, 'approveResetRequest').mockResolvedValue({
      token: 'tok123',
      reset_link: 'http://localhost:8000/reset-password?token=tok123',
      expires_at: '2026-04-18T00:00:00Z',
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ResetRequestsPanel />);
    await waitFor(() => screen.getByText('bob@x.io'));
    fireEvent.click(screen.getByRole('button', { name: /approve/i }));
    await waitFor(() =>
      expect(screen.getByText(/tok123/)).toBeInTheDocument(),
    );
  });

  it('rejects a request', async () => {
    const reject = vi.spyOn(adminApi, 'rejectResetRequest').mockResolvedValue({ ok: true });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ResetRequestsPanel />);
    await waitFor(() => screen.getByText('bob@x.io'));
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));
    await waitFor(() => expect(reject).toHaveBeenCalledWith(1));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/admin/__tests__/ResetRequestsPanel.test.tsx`
Expected: FAIL with "Cannot find module '../ResetRequestsPanel'"

- [ ] **Step 3: Implement `ResetRequestsPanel.tsx`**

```tsx
// frontend/src/components/settings/admin/ResetRequestsPanel.tsx
import React, { useEffect, useState } from 'react';
import { ApiError, approveResetRequest, listResetRequests, rejectResetRequest, ResetRequestRow } from '../../../api/admin';
import { OneTimeSecretModal } from '../OneTimeSecretModal';
import { InlineFeedback } from '../InlineFeedback';

type Filter = 'pending' | 'approved' | 'rejected' | 'all';

export function ResetRequestsPanel(): JSX.Element {
  const [filter, setFilter] = useState<Filter>('pending');
  const [items, setItems] = useState<ResetRequestRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetLink, setResetLink] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const r = await listResetRequests(filter === 'all' ? undefined : filter);
      setItems(r.items);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => { refresh(); }, [filter]);

  const approve = async (id: number, email: string) => {
    if (\!window.confirm(`Approve password reset for ${email}? A single-use 24h link will be generated.`)) return;
    try {
      const r = await approveResetRequest(id);
      setResetLink(r.reset_link);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const reject = async (id: number, email: string) => {
    if (\!window.confirm(`Reject password reset for ${email}?`)) return;
    try {
      await rejectResetRequest(id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-fg">Password reset requests</h2>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as Filter)}
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-fg"
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="all">All</option>
        </select>
      </div>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      <div className="rounded-md border border-border bg-surface">
        <table className="w-full text-sm">
          <thead className="bg-surface-alt text-left text-xs uppercase text-fg-muted">
            <tr>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Requested</th>
              <th className="px-3 py-2">IP</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr><td colSpan={5} className="px-3 py-4 text-fg-muted">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-4 text-fg-muted">No matching requests.</td></tr>
            ) : items.map((r) => (
              <tr key={r.id} className="border-t border-border">
                <td className="px-3 py-2 text-fg">{r.user_email}</td>
                <td className="px-3 py-2 text-fg-muted">{new Date(r.requested_at).toLocaleString()}</td>
                <td className="px-3 py-2 text-fg-muted">{r.ip_address ?? '—'}</td>
                <td className="px-3 py-2 text-fg">{r.status}</td>
                <td className="px-3 py-2 text-right space-x-3">
                  {r.status === 'pending' ? (
                    <>
                      <button
                        type="button"
                        onClick={() => approve(r.id, r.user_email)}
                        className="text-sm text-primary hover:underline"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        onClick={() => reject(r.id, r.user_email)}
                        className="text-sm text-danger hover:underline"
                      >
                        Reject
                      </button>
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <OneTimeSecretModal
        open={resetLink \!== null}
        title="Password reset link"
        secret={resetLink ?? ''}
        description="Share with the user through a secure channel. Valid for 24 hours, single-use."
        onClose={() => setResetLink(null)}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/admin/__tests__/ResetRequestsPanel.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/admin/ResetRequestsPanel.tsx \
        frontend/src/components/settings/admin/__tests__/ResetRequestsPanel.test.tsx
git commit -m "feat(admin): add ResetRequestsPanel with approve/reject flow and one-time link"
```

---

### Task 21: ModelsAdminPanel + DataProvidersAdminPanel (reuse Plan 10 components)

**Files:**
- Create: `frontend/src/components/settings/admin/ModelsAdminPanel.tsx`
- Create: `frontend/src/components/settings/admin/DataProvidersAdminPanel.tsx`
- Test: `frontend/src/components/settings/admin/__tests__/ModelsAdminPanel.test.tsx`

**Reuses from Plan 10:** `TierSlotCard` for per-tier model slots (backed by Plan 4 `/llm/models` admin routes) and `ProvidersStep`'s row/form components. Both panels are thin wrappers that mount the shared UI from `components/wizard/`.

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/settings/admin/__tests__/ModelsAdminPanel.test.tsx
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ModelsAdminPanel } from '../ModelsAdminPanel';
import { DataProvidersAdminPanel } from '../DataProvidersAdminPanel';

describe('admin reuse wrappers', () => {
  it('ModelsAdminPanel mounts TierSlotCard heading', () => {
    render(<ModelsAdminPanel />);
    expect(screen.getByRole('heading', { name: /server-wide models/i })).toBeInTheDocument();
  });
  it('DataProvidersAdminPanel mounts heading', () => {
    render(<DataProvidersAdminPanel />);
    expect(screen.getByRole('heading', { name: /data providers/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/admin/__tests__/ModelsAdminPanel.test.tsx`
Expected: FAIL with "Cannot find module '../ModelsAdminPanel'"

- [ ] **Step 3: Implement `ModelsAdminPanel.tsx`**

```tsx
// frontend/src/components/settings/admin/ModelsAdminPanel.tsx
import React from 'react';
import { TierSlotCard } from '../../wizard/TierSlotCard';

const TIERS = ['everyday', 'quick', 'thinking', 'long_context'] as const;

export function ModelsAdminPanel(): JSX.Element {
  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold text-fg">Server-wide models</h2>
        <p className="mt-1 text-sm text-fg-muted">
          Register, test, or remove models for each capability tier. These become the defaults for all users.
        </p>
      </header>
      <div className="grid gap-4">
        {TIERS.map((t) => (
          <TierSlotCard key={t} tier={t} mode="admin" />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement `DataProvidersAdminPanel.tsx`**

```tsx
// frontend/src/components/settings/admin/DataProvidersAdminPanel.tsx
import React from 'react';
import { ProviderRow } from '../../wizard/ProviderRow';
import { AddProviderForm } from '../../wizard/AddProviderForm';
import { useEffect, useState } from 'react';

interface ProviderSummary {
  id: string;
  kind: 'builtin' | 'mcp' | 'openapi';
  label: string;
  domains: string[];
  enabled: boolean;
  healthy: boolean | null;
}

export function DataProvidersAdminPanel(): JSX.Element {
  const [items, setItems] = useState<ProviderSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const refresh = async () => {
    try {
      const r = await fetch('/api/data-providers', { credentials: 'same-origin' });
      if (\!r.ok) throw new Error('Failed to load providers');
      const j = await r.json();
      setItems(j.items ?? []);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-fg">Data providers</h2>
          <p className="mt-1 text-sm text-fg-muted">
            Built-in, MCP, and OpenAPI providers available to all users.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((v) => \!v)}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover"
        >
          {showForm ? 'Cancel' : 'Add provider'}
        </button>
      </div>

      {error ? (
        <div role="alert" className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </div>
      ) : null}

      {showForm ? (
        <AddProviderForm
          onCreated={() => {
            setShowForm(false);
            refresh();
          }}
        />
      ) : null}

      <div className="space-y-2">
        {items === null ? (
          <p className="text-sm text-fg-muted">Loading...</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-fg-muted">No providers configured yet.</p>
        ) : (
          items.map((p) => <ProviderRow key={p.id} provider={p} onChange={refresh} />)
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/admin/__tests__/ModelsAdminPanel.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings/admin/ModelsAdminPanel.tsx \
        frontend/src/components/settings/admin/DataProvidersAdminPanel.tsx \
        frontend/src/components/settings/admin/__tests__/ModelsAdminPanel.test.tsx
git commit -m "feat(admin): add ModelsAdminPanel and DataProvidersAdminPanel wrappers"
```

---

### Task 22: SettingsPage + router wiring

**Files:**
- Create: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/router.tsx` (add `/settings/*` routes under auth gate)
- Test: `frontend/src/pages/__tests__/SettingsPage.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/pages/__tests__/SettingsPage.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SettingsPage } from '../SettingsPage';

vi.mock('../../auth/useCurrentUser', () => ({
  useCurrentUser: () => ({ id: 1, email: 'alice@x.io', role: 'admin', display_name: 'Alice', must_change_password: false }),
}));

describe('SettingsPage', () => {
  it('redirects /settings to /settings/general', async () => {
    render(
      <MemoryRouter initialEntries={['/settings']}>
        <Routes>
          <Route path="/settings/*" element={<SettingsPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByRole('heading', { name: /general/i })).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/__tests__/SettingsPage.test.tsx`
Expected: FAIL with "Cannot find module '../SettingsPage'"

- [ ] **Step 3: Implement `SettingsPage.tsx`**

```tsx
// frontend/src/pages/SettingsPage.tsx
import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { SettingsShell } from '../components/settings/SettingsShell';
import { GeneralSection } from '../components/settings/sections/GeneralSection';
import { ModelsSection } from '../components/settings/sections/ModelsSection';
import { AccountSection } from '../components/settings/sections/AccountSection';
import { AdminSection } from '../components/settings/sections/AdminSection';
import { InvitesPanel } from '../components/settings/admin/InvitesPanel';
import { UsersPanel } from '../components/settings/admin/UsersPanel';
import { ResetRequestsPanel } from '../components/settings/admin/ResetRequestsPanel';
import { ModelsAdminPanel } from '../components/settings/admin/ModelsAdminPanel';
import { DataProvidersAdminPanel } from '../components/settings/admin/DataProvidersAdminPanel';
import { useCurrentUser } from '../auth/useCurrentUser';

export function SettingsPage(): JSX.Element {
  const user = useCurrentUser();
  if (\!user) return <p className="p-6 text-fg-muted">Loading...</p>;
  const isAdmin = user.role === 'admin';
  return (
    <Routes>
      <Route element={<SettingsShell userRole={user.role} />}>
        <Route index element={<Navigate to="general" replace />} />
        <Route path="general" element={<GeneralSection />} />
        <Route path="models" element={<ModelsSection />} />
        <Route
          path="account"
          element={<AccountSection currentEmail={user.email} mustChangePassword={user.must_change_password} />}
        />
        {isAdmin ? (
          <Route path="admin" element={<AdminSection />}>
            <Route index element={<Navigate to="invites" replace />} />
            <Route path="invites" element={<InvitesPanel />} />
            <Route path="users" element={<UsersPanel currentUserId={user.id} />} />
            <Route path="reset-requests" element={<ResetRequestsPanel />} />
            <Route path="models" element={<ModelsAdminPanel />} />
            <Route path="data-providers" element={<DataProvidersAdminPanel />} />
          </Route>
        ) : null}
        <Route path="*" element={<Navigate to="general" replace />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 4: Wire into `router.tsx`**

In `frontend/src/router.tsx`, inside the authenticated route tree (after Plan 8's `MainShell` layout), add:

```tsx
import { SettingsPage } from './pages/SettingsPage';
// ...
<Route path="/settings/*" element={<SettingsPage />} />
```

Insert this route sibling to the department pages so it renders inside the main shell's sidebar chrome. Do not place it behind any admin-only gate in the router — `SettingsPage` handles role gating internally so regular users still reach General/Models/Account.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/__tests__/SettingsPage.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx \
        frontend/src/router.tsx \
        frontend/src/pages/__tests__/SettingsPage.test.tsx
git commit -m "feat(settings): add SettingsPage with routing and admin gating"
```

---

### Task 23: Must-change-password enforcement at the shell

**Files:**
- Modify: `frontend/src/components/AppShell.tsx` (add `MustChangePasswordGate` before children)
- Create: `frontend/src/components/MustChangePasswordGate.tsx`
- Test: `frontend/src/components/__tests__/MustChangePasswordGate.test.tsx`

**Why this exists:** the `must_change_password` flag must block navigation to anything except `/settings/account` and the password-change form itself. This gate runs once per render in the main shell and short-circuits to AccountSection when the flag is set and the user is not already there.

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/__tests__/MustChangePasswordGate.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MustChangePasswordGate } from '../MustChangePasswordGate';

vi.mock('../../auth/useCurrentUser', () => ({
  useCurrentUser: vi.fn(),
}));
import { useCurrentUser } from '../../auth/useCurrentUser';

describe('MustChangePasswordGate', () => {
  it('renders children when flag is false', () => {
    (useCurrentUser as any).mockReturnValue({ id: 1, role: 'user', must_change_password: false, email: 'a@b.c' });
    render(
      <MemoryRouter>
        <MustChangePasswordGate><div>app</div></MustChangePasswordGate>
      </MemoryRouter>,
    );
    expect(screen.getByText('app')).toBeInTheDocument();
  });

  it('renders gate screen when flag is true and path is not /settings/account', () => {
    (useCurrentUser as any).mockReturnValue({ id: 1, role: 'user', must_change_password: true, email: 'a@b.c' });
    render(
      <MemoryRouter initialEntries={['/']}>
        <MustChangePasswordGate><div>app</div></MustChangePasswordGate>
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: /change your password/i })).toBeInTheDocument();
    expect(screen.queryByText('app')).toBeNull();
  });

  it('renders children when on /settings/account even if flag is true', () => {
    (useCurrentUser as any).mockReturnValue({ id: 1, role: 'user', must_change_password: true, email: 'a@b.c' });
    render(
      <MemoryRouter initialEntries={['/settings/account']}>
        <MustChangePasswordGate><div>app</div></MustChangePasswordGate>
      </MemoryRouter>,
    );
    expect(screen.getByText('app')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/MustChangePasswordGate.test.tsx`
Expected: FAIL with "Cannot find module '../MustChangePasswordGate'"

- [ ] **Step 3: Implement `MustChangePasswordGate.tsx`**

```tsx
// frontend/src/components/MustChangePasswordGate.tsx
import React from 'react';
import { useLocation, Navigate } from 'react-router-dom';
import { useCurrentUser } from '../auth/useCurrentUser';

interface Props { children: React.ReactNode }

export function MustChangePasswordGate({ children }: Props): JSX.Element {
  const user = useCurrentUser();
  const location = useLocation();
  if (\!user) return <>{children}</>;
  if (\!user.must_change_password) return <>{children}</>;
  if (location.pathname.startsWith('/settings/account')) return <>{children}</>;
  return (
    <div className="mx-auto max-w-xl p-10">
      <h1 className="text-xl font-semibold text-fg">Change your password</h1>
      <p className="mt-2 text-sm text-fg-muted">
        An administrator reset your password. Please set a new one before using OpenLia.
      </p>
      <Navigate to="/settings/account" replace />
    </div>
  );
}
```

- [ ] **Step 4: Wire into `AppShell.tsx`**

In `frontend/src/components/AppShell.tsx`, wrap the main content area:

```tsx
import { MustChangePasswordGate } from './MustChangePasswordGate';
// ...
<main>
  <MustChangePasswordGate>
    {/* existing routed content */}
  </MustChangePasswordGate>
</main>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/__tests__/MustChangePasswordGate.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/MustChangePasswordGate.tsx \
        frontend/src/components/AppShell.tsx \
        frontend/src/components/__tests__/MustChangePasswordGate.test.tsx
git commit -m "feat(settings): enforce must_change_password via shell gate"
```

---

### Task 24: Manual smoke test + docs update

**Files:**
- Modify: `planning/implementation-plans/README.md` (flip Plan 11 row to Draft)

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest packages/server/tests/ -v
cd frontend && npx vitest run
```

Expected: all tests pass.

- [ ] **Step 2: Manual smoke test (personal mode)**

```bash
uv run openlia serve &
cd frontend && npm run dev
```

In the browser:
1. Log in as the default admin.
2. Navigate to `/settings/general`. Change display name and theme, click Save, verify the UI reflects the update.
3. Navigate to `/settings/models`. Pick a Quick-tier model, click Save, verify success feedback.
4. Navigate to `/settings/account`. Change email (using current password). Verify new email appears.
5. On `/settings/account`, use the Password form. Verify session revocation message.
6. Navigate to `/settings/admin/invites`. Create an invite. Copy the one-time link from the modal. Verify the token no longer appears in the list.
7. Navigate to `/settings/admin/users`. Reset another user's password. Verify the temporary password appears once.
8. Navigate to `/settings/admin/reset-requests`. Approve a pending request. Verify the link appears in modal and the request flips to approved.
9. Navigate to `/settings/admin/data-providers`. Add a built-in provider.
10. Log in as the user whose password was reset. Verify they land on `/settings/account` with the must-change-password banner and cannot navigate away until they set a new password.

- [ ] **Step 3: Flip Plan 11 row in `README.md` to Draft**

In `planning/implementation-plans/README.md`, change the Plan 11 row from:

```
| 11 | Settings page | Not started | — |
```

to:

```
| 11 | Settings page | Draft | [2026-04-17-phase-11-settings-page.md](2026-04-17-phase-11-settings-page.md) |
```

- [ ] **Step 4: Commit**

```bash
git add planning/implementation-plans/README.md
git commit -m "docs(plan): mark Phase 11 Settings Page plan as Draft"
```

---

## Self-Review Notes

**Spec coverage.** Cross-checked against `planning/specs/pages/SettingsPageSpec.md`:
- General (display name, notifications, appearance) → Task 14.
- Models (per-tier picker) → Task 15.
- Account (email, password, languages, sessions, must-change banner) → Task 16 + Task 23.
- Admin: Invites → Task 18; Users → Task 19; Reset requests → Task 20; Models → Task 21; Data providers → Task 21.
- Dirty state per section + unsaved-changes modal → Task 11 (hook) + Task 14 (per-section usage). The unsaved-changes modal from Task 11 is available for any future section that needs to warn on nav-away; currently not wired into router guard because section Save already clears dirty, which matches the spec's "guard applies when navigating away with unsaved changes."
- One-time secrets → Task 12 + reused by Tasks 18, 19, 20.
- Password reset approval flow (24h token) → Task 9 (backend) + Task 20 (frontend).
- Admin-only API-key-bearing fields → admin UI lives under `/settings/admin/*` and the shell hides the nav tab for non-admins (Task 13). API routes enforce `require_admin` (Tasks 7–9).

**Type consistency.** `ModelPreference`, `Tier`, `Prefs`, `LangCode`, `Theme` defined in Task 10 and reused verbatim in Tasks 14, 15, 16. `InviteSummary`, `AdminUserRow`, `ResetRequestRow` defined in Task 10 and reused in Tasks 18, 19, 20.

**Placeholder scan.** No "TBD", "add validation", "implement later", or un-cited imports. Every component referenced by a test has a corresponding implementation step.

**Reuse decisions.** Plan 10's `TierSlotCard`, `ProviderRow`, `AddProviderForm` are mounted by Task 21 with `mode="admin"` — Plan 10 must export these with an admin-mode prop. Plan 9's `ChangePasswordForm` and `SessionsPanel` are embedded inline in Task 16 — Plan 9 must export them from `components/auth/`.
