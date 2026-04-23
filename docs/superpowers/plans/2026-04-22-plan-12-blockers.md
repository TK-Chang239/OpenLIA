# Plan 12 Blockers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three Plan 12 remediation blockers (REM-P1-007 repo_items consolidation, REM-P1-009 report store + GET endpoint, REM-P1-008 Secretary chat SSE route) on branch `feat/plan-12-blockers` off `main`.

**Architecture:** Three backend-only deliverables land as four commits on a single branch. Deliverable 1 consolidates saved-report persistence on a new `repo_items` table and drops the stale `Report.is_starred` and `Report.tags` columns. Deliverable 2 adds a report store service (validate-then-persist) and a user-scoped `GET /reports/{id}` route. Deliverable 3 adds the first real runtime-backed SSE route, `POST /departments/secretary/chat`, that streams `ChatRunner` events serialized via `to_wire(event)` and cancels on client disconnect. All route factories follow the existing `build_require_active_user(...)` + `make_session_dependency(factory)` pattern. No frontend work in this plan.

**Tech Stack:** Python 3.12+, FastAPI, Starlette StreamingResponse, SQLAlchemy 2.x, Alembic, Pydantic v2, pytest, httpx.AsyncClient (for SSE cancellation test). Runtime primitives come from `openlia.llm.runtime.*` (core package).

**Spec:** `docs/superpowers/specs/2026-04-22-plan-12-blockers-design.md`.

**Prior constraints (from the spec):**
- Cross-plan contract already designates `repo_items` canonical.
- Route factories accept `db_session_factory` and `mode`; auth via `build_require_active_user`.
- SSE events serialized with `to_wire(event)` from `openlia.llm.runtime.events`.
- Runtime imports always `openlia.llm.runtime.*`, never `openlia.runtime.*`.
- Frontend hits `/api/...`; backend mounts bare prefixes.
- `make_session_dependency(factory)` (in `openlia_server.db.deps`) is the canonical way to inject a per-request `Session`.

---

## File Structure

### Backend source

- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-22-2200_repo_items_and_drop_legacy_report_cols.py` — migration adding `repo_items`, dropping `reports.is_starred`/`reports.tags`. Down-revision `b3d8f5a0e192`.
- Modify: `packages/server/src/openlia_server/db/models/content.py` — add `RepoItem` class; remove `is_starred` and `tags` from `Report`.
- Create: `packages/server/src/openlia_server/services/reports.py` — `InvalidReportSchemaError`, `validate_report_schema`, `save_report`, `get_report_for_user`.
- Create: `packages/server/src/openlia_server/routes/reports.py` — `build_reports_router(...)` exposing `GET /reports/{report_id}`, `ReportResponse` DTO.
- Create: `packages/server/src/openlia_server/services/runtime.py` — `build_chat_runner(...)` wiring `PromptLoader`, `SQLModelRegistry`, `ToolDispatcher`, `resolve`, `build_adapter`.
- Create: `packages/server/src/openlia_server/routes/chat_stream.py` — `build_chat_stream_router(...)` exposing `POST /departments/secretary/chat` (SSE).
- Modify: `packages/server/src/openlia_server/app.py` — mount the two new routers; construct `chat_runner_factory` once at startup; extend `_API_PREFIXES` with `"reports"` and `"departments"`.

### Backend tests

- Modify: `packages/server/tests/test_db/test_migrations.py` — add `"repo_items"` to `EXPECTED_TABLES`.
- Create: `packages/server/tests/test_db/test_repo_items_model.py` — model registration + cascade + unique constraint.
- Create: `packages/server/tests/test_services/test_reports.py` — `validate_report_schema`, `save_report`, `get_report_for_user`.
- Create: `packages/server/tests/test_routes/test_reports_routes.py` — owner 200, non-owner 404, missing 404, unauthenticated 401.
- Create: `packages/server/tests/test_routes/test_chat_stream.py` — happy path via stub runner.
- Create: `packages/server/tests/test_routes/test_chat_stream_cancellation.py` — httpx.AsyncClient disconnect flips cancel token.
- Create: `packages/server/tests/test_routes/test_chat_stream_error.py` — stub runner raises, terminal `chat.error` frame.

### Docs

- Modify: `planning/audits/2026-04-21-remediation-checklist.md` — flip REM-P1-007, REM-P1-008, REM-P1-009 status + summary block.
- Modify: `planning/implementation-plans/2026-04-17-phase-12-shared-chat-components.md` — annotate Task 0 header.

### Commit sequence

1. `feat(db): consolidate saved-report persistence on repo_items` — Tasks 1–3.
2. `feat(reports): add report store service and GET /reports/{id}` — Tasks 4–5.
3. `feat(chat): add Secretary chat SSE route backed by ChatRunner` — Tasks 6–7.
4. `docs(audit): mark Plan 12 blockers complete` — Task 8.

---

## Task 0: Prep branch

**Files:** none; branch-only.

- [ ] **Step 1: Create and switch to the implementation branch from main**

```bash
git fetch origin
git checkout -B feat/plan-12-blockers origin/main
```

- [ ] **Step 2: Verify baseline test suite is green before touching anything**

```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -q
```

Expected: PASS. If it fails on `main`, stop and investigate before proceeding.

---

# Deliverable 1 — REM-P1-007: repo_items consolidation (Commit 1)

## Task 1: Update migration round-trip test expectations

**Files:**
- Modify: `packages/server/tests/test_db/test_migrations.py`

- [ ] **Step 1: Add `repo_items` to `EXPECTED_TABLES`**

Edit `packages/server/tests/test_db/test_migrations.py`. Locate the `EXPECTED_TABLES` set (after the `# --- Plan 11 additions ---` comment) and add a new trailing section:

```python
    # --- Plan 11 additions ---
    "user_prefs",
    # --- Plan 12 blockers ---
    "repo_items",
}
```

- [ ] **Step 2: Run the migration test — expect FAIL (table not created yet)**

```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -q
```

Expected: failure on `test_baseline_upgrade_creates_all_tables` with `repo_items` missing from the upgraded schema. This is the failing test that Task 2 will fix.

## Task 2: Add the Alembic migration

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-22-2200_repo_items_and_drop_legacy_report_cols.py`

- [ ] **Step 1: Write the migration file**

```python
"""Consolidate saved-report persistence on repo_items.

Creates `repo_items` (user_id × report_id) and drops the legacy
`Report.is_starred` and `Report.tags` columns. See spec
docs/superpowers/specs/2026-04-22-plan-12-blockers-design.md.

Revision ID: c1f4e2d7a931
Revises: b3d8f5a0e192
Create Date: 2026-04-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1f4e2d7a931"
down_revision: str | Sequence[str] | None = "b3d8f5a0e192"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repo_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "report_id", name="uq_repo_items_user_report"),
    )
    op.create_index(
        "ix_repo_items_user_id_created_at",
        "repo_items",
        ["user_id", "created_at"],
    )

    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.drop_column("is_starred")
        batch_op.drop_column("tags")


def downgrade() -> None:
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_starred", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    op.drop_index("ix_repo_items_user_id_created_at", table_name="repo_items")
    op.drop_table("repo_items")
```

- [ ] **Step 2: Run the migration round-trip test — expect PASS on upgrade**

```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -q
```

Expected: PASS. If it still fails, confirm the revision chain by running:

```bash
cd packages/server && uv run alembic heads
```

Expected: exactly one head — `c1f4e2d7a931`. If more than one head prints, another migration has been added with a conflicting `down_revision`. Resolve by rebasing this revision on top of the true head.

## Task 3: Add `RepoItem` model, drop legacy Report columns

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/content.py`
- Create: `packages/server/tests/test_db/test_repo_items_model.py`

- [ ] **Step 1: Write the failing model test**

Create `packages/server/tests/test_db/test_repo_items_model.py`:

```python
"""RepoItem model registration, FK cascades, and unique constraint."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models  # noqa: F401 — register all models
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_repo_item_registered_on_metadata() -> None:
    import openlia_server.db.models  # noqa: F401
    from openlia_server.db.base import Base

    assert "repo_items" in Base.metadata.tables


def test_repo_item_unique_user_report(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import RepoItem, Report

    u = User(id="u1", email="u1@example.com", display_name="U1")
    r = Report(
        id="r1",
        user_id="u1",
        department="secretary",
        report_type="chat_summary",
        title="t",
        content_markdown="x",
        content_structured={},
        model_ref="gpt-4o",
    )
    db_session.add_all([u, r])
    db_session.flush()

    db_session.add(RepoItem(id="ri1", user_id="u1", report_id="r1"))
    db_session.commit()

    db_session.add(RepoItem(id="ri2", user_id="u1", report_id="r1"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_repo_item_cascade_on_report_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import RepoItem, Report

    u = User(id="u2", email="u2@example.com", display_name="U2")
    r = Report(
        id="r2",
        user_id="u2",
        department="secretary",
        report_type="chat_summary",
        title="t",
        content_markdown="x",
        content_structured={},
        model_ref="gpt-4o",
    )
    db_session.add_all([u, r])
    db_session.add(RepoItem(id="ri3", user_id="u2", report_id="r2"))
    db_session.commit()

    db_session.delete(r)
    db_session.commit()
    assert db_session.execute(select(RepoItem)).scalar_one_or_none() is None


def test_report_no_longer_has_is_starred_or_tags() -> None:
    from openlia_server.db.models.content import Report

    cols = {c.name for c in Report.__table__.columns}
    assert "is_starred" not in cols
    assert "tags" not in cols
```

- [ ] **Step 2: Run the test — expect FAIL (`RepoItem` doesn't exist, `is_starred`/`tags` still on Report)**

```bash
uv run pytest packages/server/tests/test_db/test_repo_items_model.py -q
```

Expected: FAIL with `ImportError: cannot import name 'RepoItem'` and/or the `assert "is_starred" not in cols` assertion.

- [ ] **Step 3: Add `RepoItem` and remove `is_starred`/`tags` from `Report`**

Edit `packages/server/src/openlia_server/db/models/content.py`.

Remove the two lines:

```python
    is_starred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
```

Then append a new `RepoItem` class at the end of the file (after `WatchlistItem`):

```python
class RepoItem(Base):
    __tablename__ = "repo_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "report_id", name="uq_repo_items_user_report"),
        Index("ix_repo_items_user_id_created_at", "user_id", "created_at"),
    )
```

Since `Boolean` is no longer used by `Report`, verify whether it's still referenced by `ChatSession` (it is — `is_pinned`, `is_archived`). Leave the `Boolean` import in place.

- [ ] **Step 4: Run the model test — expect PASS**

```bash
uv run pytest packages/server/tests/test_db/test_repo_items_model.py -q
```

Expected: PASS on all four tests.

- [ ] **Step 5: Run the full existing content model test suite to catch regressions**

```bash
uv run pytest packages/server/tests/test_db/test_models_content.py -q
```

Expected: PASS (no test in that file references `is_starred`/`tags`, confirmed by source inspection).

- [ ] **Step 6: Grep to confirm no lingering `is_starred` / `Report.tags` references**

```bash
git grep -n "is_starred\|Report\.tags" packages/ || echo "clean"
```

Expected: output is `clean`, or only the baseline migration file (`2026-04-18-1609_baseline.py`) which intentionally keeps them for historical upgrade. The baseline migration is acceptable — it creates the columns so this migration can drop them.

- [ ] **Step 7: Commit Deliverable 1**

```bash
git add \
  packages/server/src/openlia_server/db/migrations/versions/2026-04-22-2200_repo_items_and_drop_legacy_report_cols.py \
  packages/server/src/openlia_server/db/models/content.py \
  packages/server/tests/test_db/test_repo_items_model.py \
  packages/server/tests/test_db/test_migrations.py
git commit -m "feat(db): consolidate saved-report persistence on repo_items"
```

---

# Deliverable 2 — REM-P1-009: report store + GET endpoint (Commit 2)

## Task 4: `services/reports.py` — validate, save, owner-scoped read

**Files:**
- Create: `packages/server/src/openlia_server/services/reports.py`
- Create: `packages/server/tests/test_services/test_reports.py`

- [ ] **Step 1: Write the failing service tests**

Create `packages/server/tests/test_services/test_reports.py`:

```python
"""Report store service — validation + persistence + owner-scoped read."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report


def _valid_schema() -> dict:
    return {
        "title": "AAPL Q3 Update",
        "sections": [
            {"heading": "Summary", "content": "Revenue up 10%."},
            {"heading": "Risks", "content": "FX exposure."},
        ],
    }


def _seed_user(db_session: Session, uid: str = "u1") -> User:
    u = User(id=uid, email=f"{uid}@example.com", display_name=uid)
    db_session.add(u)
    db_session.commit()
    return u


def test_validate_report_schema_accepts_canonical_shape(create_tables) -> None:
    from openlia_server.services import reports as svc

    svc.validate_report_schema(_valid_schema())


@pytest.mark.parametrize(
    "schema",
    [
        {},
        {"sections": []},
        {"title": "t"},
        {"title": 5, "sections": []},
        {"title": "t", "sections": "not-a-list"},
        {"title": "t", "sections": [{"heading": "h"}]},
        {"title": "t", "sections": [{"content": "c"}]},
        {"title": "t", "sections": [{"heading": 3, "content": "c"}]},
        {"title": "t", "sections": [{"heading": "h", "content": None}]},
    ],
)
def test_validate_report_schema_rejects_malformed(create_tables, schema) -> None:
    from openlia_server.services import reports as svc

    with pytest.raises(svc.InvalidReportSchemaError):
        svc.validate_report_schema(schema)


def test_save_report_persists_and_round_trips_structured_content(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session)
    schema = _valid_schema()

    report = svc.save_report(
        db_session,
        user_id="u1",
        department="secretary",
        report_type="chat_summary",
        title=schema["title"],
        subject=None,
        content_markdown="# AAPL",
        content_structured=schema,
        model_ref="gpt-4o",
    )
    db_session.commit()

    stored = db_session.execute(select(Report).where(Report.id == report.id)).scalar_one()
    assert stored.content_structured == schema
    assert stored.department == "secretary"
    assert stored.user_id == "u1"


def test_save_report_rejects_invalid_schema_without_writing(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session)
    with pytest.raises(svc.InvalidReportSchemaError):
        svc.save_report(
            db_session,
            user_id="u1",
            department="secretary",
            report_type="chat_summary",
            title="t",
            subject=None,
            content_markdown="x",
            content_structured={"title": "t"},  # missing sections
            model_ref="gpt-4o",
        )
    db_session.rollback()
    assert db_session.execute(select(Report)).scalar_one_or_none() is None


def test_get_report_for_user_returns_owner_row(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session, uid="u1")
    report = svc.save_report(
        db_session,
        user_id="u1",
        department="secretary",
        report_type="chat_summary",
        title="t",
        subject=None,
        content_markdown="x",
        content_structured=_valid_schema(),
        model_ref="gpt-4o",
    )
    db_session.commit()

    got = svc.get_report_for_user(db_session, user_id="u1", report_id=report.id)
    assert got is not None
    assert got.id == report.id


def test_get_report_for_user_returns_none_for_non_owner(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session, uid="u1")
    _seed_user(db_session, uid="u2")
    report = svc.save_report(
        db_session,
        user_id="u1",
        department="secretary",
        report_type="chat_summary",
        title="t",
        subject=None,
        content_markdown="x",
        content_structured=_valid_schema(),
        model_ref="gpt-4o",
    )
    db_session.commit()

    assert svc.get_report_for_user(db_session, user_id="u2", report_id=report.id) is None


def test_get_report_for_user_returns_none_for_missing_id(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session, uid="u1")
    assert svc.get_report_for_user(db_session, user_id="u1", report_id="missing") is None
```

- [ ] **Step 2: Run the test — expect FAIL (module does not exist)**

```bash
uv run pytest packages/server/tests/test_services/test_reports.py -q
```

Expected: `ModuleNotFoundError: No module named 'openlia_server.services.reports'`.

- [ ] **Step 3: Implement the service**

Create `packages/server/src/openlia_server/services/reports.py`:

```python
"""Report store service.

Validates completed report schemas emitted by `ReportRunner` and persists
them into the `reports` table. Transaction ownership stays with the caller
(route session dependency) — nothing here commits.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import Report


class InvalidReportSchemaError(ValueError):
    """Raised when a report schema does not match the runtime contract."""


def validate_report_schema(schema: Any) -> None:
    """Require `title: str` and `sections: list[{heading: str, content: str}]`.

    This mirrors the baseline shape produced by
    `ReportRunner.emit(ReportComplete(schema=...))`. Richer schemas may be
    layered on later; this function only rejects the clear violations.
    """
    if not isinstance(schema, dict):
        raise InvalidReportSchemaError("schema must be a dict")
    title = schema.get("title")
    if not isinstance(title, str) or not title:
        raise InvalidReportSchemaError("schema.title must be a non-empty str")
    sections = schema.get("sections")
    if not isinstance(sections, list):
        raise InvalidReportSchemaError("schema.sections must be a list")
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            raise InvalidReportSchemaError(f"schema.sections[{i}] must be a dict")
        heading = section.get("heading")
        if not isinstance(heading, str):
            raise InvalidReportSchemaError(
                f"schema.sections[{i}].heading must be a str"
            )
        content = section.get("content")
        if not isinstance(content, str):
            raise InvalidReportSchemaError(
                f"schema.sections[{i}].content must be a str"
            )


def save_report(
    db: Session,
    *,
    user_id: str,
    department: str,
    report_type: str,
    title: str,
    subject: str | None,
    content_markdown: str,
    content_structured: dict,
    model_ref: str,
    source_session_id: str | None = None,
    token_usage: dict | None = None,
    generation_duration_ms: int | None = None,
) -> Report:
    """Validate schema, build `Report`, flush, return. Does not commit."""
    validate_report_schema(content_structured)
    report = Report(
        id=str(uuid.uuid4()),
        user_id=user_id,
        department=department,
        report_type=report_type,
        title=title,
        subject=subject,
        content_markdown=content_markdown,
        content_structured=content_structured,
        source_session_id=source_session_id,
        model_ref=model_ref,
        token_usage=token_usage,
        generation_duration_ms=generation_duration_ms,
    )
    db.add(report)
    db.flush()
    return report


def get_report_for_user(
    db: Session, *, user_id: str, report_id: str
) -> Report | None:
    """Return the report iff it exists and `user_id` is the owner."""
    stmt = select(Report).where(Report.id == report_id).where(Report.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()
```

- [ ] **Step 4: Run the test — expect PASS**

```bash
uv run pytest packages/server/tests/test_services/test_reports.py -q
```

Expected: PASS on all parametrized cases and the positive paths.

## Task 5: `routes/reports.py` + app wiring

**Files:**
- Create: `packages/server/src/openlia_server/routes/reports.py`
- Create: `packages/server/tests/test_routes/test_reports_routes.py`
- Modify: `packages/server/src/openlia_server/app.py`

- [ ] **Step 1: Write the failing route tests**

Create `packages/server/tests/test_routes/test_reports_routes.py`:

```python
"""GET /reports/{id} — owner-scoped read."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User


def _seed_user(db_session: Session, uid: str, email: str) -> User:
    u = User(
        id=uid,
        email=email,
        display_name=uid,
        password_hash=None,
        is_admin=False,
        is_disabled=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


def _save_report(db_session: Session, owner_id: str) -> str:
    from openlia_server.services import reports as svc

    schema = {
        "title": "T",
        "sections": [{"heading": "H", "content": "C"}],
    }
    report = svc.save_report(
        db_session,
        user_id=owner_id,
        department="secretary",
        report_type="chat_summary",
        title="T",
        subject=None,
        content_markdown="# T",
        content_structured=schema,
        model_ref="gpt-4o",
    )
    db_session.commit()
    return report.id


def test_get_report_as_owner_returns_dto(personal_client: TestClient, db_session: Session) -> None:
    report_id = _save_report(db_session, owner_id="local")
    r = personal_client.get(f"/reports/{report_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == report_id
    assert body["department"] == "secretary"
    assert body["title"] == "T"
    assert body["content_structured"] == {
        "title": "T",
        "sections": [{"heading": "H", "content": "C"}],
    }
    assert body["model_ref"] == "gpt-4o"
    assert "created_at" in body
    assert "updated_at" in body
    assert "user_id" not in body


def test_get_report_as_non_owner_returns_404(
    company_client: TestClient, auth_user, db_session: Session
) -> None:
    other = _seed_user(db_session, uid="other-user", email="other@example.com")
    report_id = _save_report(db_session, owner_id=other.id)

    r = company_client.get(f"/reports/{report_id}")
    assert r.status_code == 404


def test_get_report_missing_id_returns_404(personal_client: TestClient) -> None:
    r = personal_client.get("/reports/does-not-exist")
    assert r.status_code == 404


def test_get_report_unauthenticated_returns_401(company_client_anon: TestClient) -> None:
    r = company_client_anon.get("/reports/whatever")
    assert r.status_code == 401
```

- [ ] **Step 2: Run the test — expect FAIL (route not registered)**

```bash
uv run pytest packages/server/tests/test_routes/test_reports_routes.py -q
```

Expected: all four tests FAIL with `404` on the 200 path (route not mounted) and wrong shape/status on the others.

- [ ] **Step 3: Implement the route factory**

Create `packages/server/src/openlia_server/routes/reports.py`:

```python
"""GET /reports/{id} — owner-scoped report read."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services.reports import get_report_for_user


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    department: str
    report_type: str
    title: str
    subject: str | None
    content_markdown: str
    content_structured: dict
    model_ref: str
    created_at: datetime
    updated_at: datetime


def build_reports_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    require_auth = build_require_active_user(
        db_session_factory=db_session_factory, mode=mode
    )
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/reports", tags=["reports"])

    @router.get("/{report_id}", response_model=ReportResponse)
    def get_report(
        report_id: str,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> ReportResponse:
        report = get_report_for_user(db, user_id=user.id, report_id=report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return ReportResponse.model_validate(report)

    return router
```

- [ ] **Step 4: Wire the router into `app.py`**

Edit `packages/server/src/openlia_server/app.py`.

Add the import next to the other route imports:

```python
from openlia_server.routes.reports import build_reports_router
```

Inside `create_app`, after `app.include_router(build_notifications_router(...))`, add:

```python
    app.include_router(build_reports_router(db_session_factory=factory, mode=mode))
```

Extend `_API_PREFIXES` at module bottom to include `"reports"`:

```python
_API_PREFIXES = (
    "auth",
    "admin",
    "settings",
    "setup",
    "jobs",
    "notifications",
    "reports",
    "healthz",
    "health",
    "docs",
    "redoc",
    "openapi.json",
)
```

- [ ] **Step 5: Run the route tests — expect PASS**

```bash
uv run pytest packages/server/tests/test_routes/test_reports_routes.py -q
```

Expected: all four tests PASS.

- [ ] **Step 6: Run the full server suite to catch broad regressions**

```bash
uv run pytest packages/server/tests -q
```

Expected: PASS. If a pre-existing test fails unrelated to this plan, note the failure and continue only if it's confirmed to be a flake on `main` (compare with Task 0 baseline).

- [ ] **Step 7: Commit Deliverable 2**

```bash
git add \
  packages/server/src/openlia_server/services/reports.py \
  packages/server/src/openlia_server/routes/reports.py \
  packages/server/src/openlia_server/app.py \
  packages/server/tests/test_services/test_reports.py \
  packages/server/tests/test_routes/test_reports_routes.py
git commit -m "feat(reports): add report store service and GET /reports/{id}"
```

---

# Deliverable 3 — REM-P1-008: Secretary chat SSE route (Commit 3)

## Task 6: `services/runtime.py` — `build_chat_runner`

**Files:**
- Create: `packages/server/src/openlia_server/services/runtime.py`

This builder is only exercised end-to-end by the running app; tests stub the factory. Keep it minimal.

- [ ] **Step 1: Write the runtime builder**

Create `packages/server/src/openlia_server/services/runtime.py`:

```python
"""Build a `ChatRunner` wired to the server's LLM admin settings.

Tests stub this entire factory — the route accepts `chat_runner_factory`
as a parameter so the builder below is only exercised by the running
application. Plan 13 will extend the builder with real tool wiring; for
this blocker the Secretary tool dispatcher returns no tools.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openlia.llm.adapters import build_adapter
from openlia.llm.resolver import resolve
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from sqlalchemy.orm import Session as DBSession

from openlia_server.services.llm_registry import SQLModelRegistry


class _EmptyDataDispatcher:
    """No data-provider tools are wired in this blocker. Plan 13 replaces this."""

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]:
        return []

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise RuntimeError(
            f"no data-provider tools registered (attempted {tool_name!r})"
        )

    async def find_more_data(
        self, *, department_id: str, description: str
    ) -> dict[str, Any] | None:
        return None


def build_chat_runner(
    *,
    db_session_factory: Callable[[], DBSession],
) -> ChatRunner:
    """Construct a `ChatRunner` using the current LLM admin config.

    Holds one DB session open for the registry during run(); the session is
    released when the runner is garbage-collected. Matches the scheduler
    executor pattern of opening short-lived sessions per run.
    """
    db = db_session_factory()
    registry = SQLModelRegistry(db)
    prompts = PromptLoader()
    tools = ToolDispatcher(
        data_dispatcher=_EmptyDataDispatcher(),
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )

    def _provider_factory(resolved):
        return build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )

    return ChatRunner(
        prompts=prompts,
        tools=tools,
        resolve=resolve,
        registry=registry,
        provider_factory=_provider_factory,
    )
```

No test here — the integration path is exercised by running the app; the route tests stub the factory.

## Task 7: `routes/chat_stream.py` — SSE route + tests + wiring

**Files:**
- Create: `packages/server/src/openlia_server/routes/chat_stream.py`
- Create: `packages/server/tests/test_routes/test_chat_stream.py`
- Create: `packages/server/tests/test_routes/test_chat_stream_cancellation.py`
- Create: `packages/server/tests/test_routes/test_chat_stream_error.py`
- Modify: `packages/server/src/openlia_server/app.py`

- [ ] **Step 1: Write the happy-path route test**

Create `packages/server/tests/test_routes/test_chat_stream.py`:

```python
"""POST /departments/secretary/chat — scripted happy-path SSE stream."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken

from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User


class _ScriptedChatRunner:
    """Minimal stub matching `ChatRunner.run(...)` async-iterator contract."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.captured: dict[str, Any] = {}

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages,
        cancel_token=None,
    ):
        self.captured = {
            "department_id": department_id,
            "user_id": user_id,
            "messages": messages,
            "cancel_token": cancel_token,
        }
        for event in self._events:
            yield event


@pytest.fixture
def stream_client(tmp_path, monkeypatch):
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/stream.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/stream.db")
    Base.metadata.create_all(session_mod.get_engine())

    with session_mod.SessionLocal() as s:
        s.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                is_admin=True,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()

    runner = _ScriptedChatRunner(
        events=[
            ChatStart(message_id="m1"),
            ChatToken(message_id="m1", text="hi"),
            ChatToken(message_id="m1", text=" "),
            ChatToken(message_id="m1", text="there"),
            ChatDone(message_id="m1", stop_reason="stop"),
        ]
    )

    app = create_app(db_session_factory=session_mod.SessionLocal)
    # Replace the mounted router's factory by swapping the app's chat runner
    # factory on app.state (set by create_app).
    app.state.chat_runner_factory = lambda: runner

    try:
        yield TestClient(app), runner
    finally:
        session_mod.dispose_engine()


def _parse_sse_frames(body: str) -> list[dict]:
    frames: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            frames.append(json.loads(line[len("data: ") :]))
    return frames


def test_scripted_chat_stream_emits_expected_frames(stream_client) -> None:
    client, runner = stream_client
    r = client.post(
        "/departments/secretary/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse_frames(r.text)
    types = [f["type"] for f in frames]
    assert types[0] == "chat.start"
    assert types[-1] == "chat.done"
    assert types.count("chat.token") == 3

    assert runner.captured["department_id"] == "secretary"
    assert runner.captured["user_id"] == "local"
    assert [m.content for m in runner.captured["messages"]] == ["hello"]
```

- [ ] **Step 2: Write the cancellation test (httpx.AsyncClient disconnect)**

Create `packages/server/tests/test_routes/test_chat_stream_cancellation.py`:

```python
"""Client disconnect mid-stream must flip the cancel token."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ChatStart, ChatToken

from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User


class _BlockingChatRunner:
    def __init__(self) -> None:
        self.captured_token: CancellationToken | None = None
        self.first_yielded = asyncio.Event()
        self.released = asyncio.Event()

    async def run(self, *, department_id, user_id, messages, cancel_token=None):
        self.captured_token = cancel_token
        yield ChatStart(message_id="m1")
        yield ChatToken(message_id="m1", text="hello")
        self.first_yielded.set()
        # Block indefinitely; the route's CancelledError handler is what we test.
        await self.released.wait()


@pytest.mark.asyncio
async def test_client_disconnect_flips_cancel_token(tmp_path, monkeypatch) -> None:
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/c.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/c.db")
    Base.metadata.create_all(session_mod.get_engine())

    with session_mod.SessionLocal() as s:
        s.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                is_admin=True,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()

    runner = _BlockingChatRunner()
    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.chat_runner_factory = lambda: runner

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/departments/secretary/chat",
                json={"messages": [{"role": "user", "content": "hi"}]},
            ) as resp:
                assert resp.status_code == 200
                aiter = resp.aiter_lines()
                # Pull until we see the first chat.token
                saw_token = False
                async for line in aiter:
                    if "chat.token" in line:
                        saw_token = True
                        break
                assert saw_token
            # Context-manager exit closes the connection; Starlette raises
            # CancelledError inside the generator.
        # Give the server side a tick to observe the disconnect.
        for _ in range(10):
            if runner.captured_token is not None and runner.captured_token.is_cancelled:
                break
            await asyncio.sleep(0.05)
    finally:
        runner.released.set()
        session_mod.dispose_engine()

    assert runner.captured_token is not None
    assert runner.captured_token.is_cancelled is True
```

- [ ] **Step 3: Write the error-path test**

Create `packages/server/tests/test_routes/test_chat_stream_error.py`:

```python
"""A stub runner that raises must produce exactly one terminal chat.error frame."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.llm.exceptions import TierNotConfiguredError

from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User


class _RaisingChatRunner:
    async def run(self, *, department_id, user_id, messages, cancel_token=None):
        raise TierNotConfiguredError("everyday")
        yield  # unreachable; makes this an async generator


@pytest.fixture
def stream_client(tmp_path, monkeypatch):
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/e.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/e.db")
    Base.metadata.create_all(session_mod.get_engine())

    with session_mod.SessionLocal() as s:
        s.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                is_admin=True,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.chat_runner_factory = _RaisingChatRunner
    try:
        yield TestClient(app)
    finally:
        session_mod.dispose_engine()


def test_raising_runner_emits_single_terminal_error_frame(stream_client: TestClient) -> None:
    r = stream_client.post(
        "/departments/secretary/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    frames = [
        json.loads(line[len("data: ") :])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(frames) == 1
    assert frames[0]["type"] == "chat.error"
    assert frames[0]["error_class"] == "TierNotConfiguredError"


def test_unauthenticated_chat_stream_returns_401(tmp_path, monkeypatch) -> None:
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/u.db")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/u.db")
    Base.metadata.create_all(session_mod.get_engine())

    from openlia_server.services.auth import signup_policy

    with session_mod.SessionLocal() as s:
        signup_policy.seed_signup_policy(s, mode_flag="company")
        s.commit()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.chat_runner_factory = _RaisingChatRunner
    client = TestClient(app)
    try:
        r = client.post(
            "/departments/secretary/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 401
    finally:
        session_mod.dispose_engine()
```

- [ ] **Step 4: Run all three tests — expect FAIL (route not mounted)**

```bash
uv run pytest packages/server/tests/test_routes/test_chat_stream.py \
               packages/server/tests/test_routes/test_chat_stream_cancellation.py \
               packages/server/tests/test_routes/test_chat_stream_error.py -q
```

Expected: 404 on the happy-path/error tests (route missing); cancellation test fails similarly.

- [ ] **Step 5: Implement the route factory**

Create `packages/server/src/openlia_server/routes/chat_stream.py`:

```python
"""POST /departments/secretary/chat — first runtime-backed SSE route."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import ChatError, to_wire
from openlia.llm.runtime.messages import ChatMessage as RuntimeChatMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user

log = logging.getLogger(__name__)


class SecretaryChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class SecretaryChatRequest(BaseModel):
    messages: list[SecretaryChatMessage]


def build_chat_stream_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    """Mount `/departments/secretary/chat`.

    The chat-runner factory is resolved from `request.app.state.chat_runner_factory`
    at each request so tests can swap it without rebuilding the app.
    """
    require_auth = build_require_active_user(
        db_session_factory=db_session_factory, mode=mode
    )
    router = APIRouter(prefix="/departments/secretary", tags=["chat"])

    @router.post("/chat")
    async def stream_chat(
        payload: SecretaryChatRequest,
        request: Request,
        user: User = require_auth,
    ) -> StreamingResponse:
        factory: Callable[[], ChatRunner] = request.app.state.chat_runner_factory
        return StreamingResponse(
            _event_source(payload, user, factory),
            media_type="text/event-stream",
        )

    return router


async def _event_source(
    payload: SecretaryChatRequest,
    user: User,
    factory: Callable[[], ChatRunner],
) -> AsyncIterator[bytes]:
    token = CancellationToken()
    messages = [
        RuntimeChatMessage(role=m.role, content=m.content) for m in payload.messages
    ]
    runner = factory()

    try:
        async for event in runner.run(
            department_id="secretary",
            user_id=user.id,
            messages=messages,
            cancel_token=token,
        ):
            yield f"data: {json.dumps(to_wire(event))}\n\n".encode()
    except asyncio.CancelledError:
        token.cancel()
        raise
    except Exception as exc:  # noqa: BLE001 — surface any runtime error as one terminal frame
        log.warning("chat stream terminated with error", exc_info=True)
        error_event = ChatError(
            message_id="",
            error_class=type(exc).__name__,
            message=str(exc),
        )
        yield f"data: {json.dumps(to_wire(error_event))}\n\n".encode()
```

- [ ] **Step 6: Wire the router and the default runner factory in `app.py`**

Edit `packages/server/src/openlia_server/app.py`.

Add the imports next to the other route imports:

```python
from openlia_server.routes.chat_stream import build_chat_stream_router
from openlia_server.services.runtime import build_chat_runner
```

Inside `create_app`, after `app.include_router(build_reports_router(...))`, add:

```python
    app.state.chat_runner_factory = lambda: build_chat_runner(db_session_factory=factory)
    app.include_router(build_chat_stream_router(db_session_factory=factory, mode=mode))
```

Extend `_API_PREFIXES` to include `"departments"`:

```python
_API_PREFIXES = (
    "auth",
    "admin",
    "settings",
    "setup",
    "jobs",
    "notifications",
    "reports",
    "departments",
    "healthz",
    "health",
    "docs",
    "redoc",
    "openapi.json",
)
```

- [ ] **Step 7: Sanity-check `pytest-asyncio` is wired (already a dev dep on main)**

```bash
uv run python -c "import pytest_asyncio; print('ok')"
grep -n "asyncio_mode" pyproject.toml
```

Expected: prints `ok`, and `asyncio_mode = "auto"` appears under `[tool.pytest.ini_options]`. If either check fails, add `pytest-asyncio>=1.3.0` to `[dependency-groups] dev` in `pyproject.toml` and `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`, then `uv sync`.

- [ ] **Step 8: Run the three chat-stream tests — expect PASS**

```bash
uv run pytest packages/server/tests/test_routes/test_chat_stream.py \
               packages/server/tests/test_routes/test_chat_stream_cancellation.py \
               packages/server/tests/test_routes/test_chat_stream_error.py -q
```

Expected: PASS on all three files. If the cancellation test flakes, increase the sleep-retry window in the test from `range(10)` to `range(20)` with the same `0.05s` step (up to one second total).

- [ ] **Step 9: Run the full server suite**

```bash
uv run pytest packages/server/tests -q
```

Expected: PASS.

- [ ] **Step 10: Commit Deliverable 3**

```bash
git add \
  packages/server/src/openlia_server/services/runtime.py \
  packages/server/src/openlia_server/routes/chat_stream.py \
  packages/server/src/openlia_server/app.py \
  packages/server/tests/test_routes/test_chat_stream.py \
  packages/server/tests/test_routes/test_chat_stream_cancellation.py \
  packages/server/tests/test_routes/test_chat_stream_error.py
# If pyproject.toml / uv.lock changed for pytest-asyncio, include them:
git commit -m "feat(chat): add Secretary chat SSE route backed by ChatRunner"
```

---

# Deliverable 4 — Doc updates (Commit 4)

## Task 8: Mark blockers complete

**Files:**
- Modify: `planning/audits/2026-04-21-remediation-checklist.md`
- Modify: `planning/implementation-plans/2026-04-17-phase-12-shared-chat-components.md`

- [ ] **Step 1: Flip the three remediation items**

Edit `planning/audits/2026-04-21-remediation-checklist.md`.

For each of the three section headers `### REM-P1-007`, `### REM-P1-008`, `### REM-P1-009`, change `Status: \`[ ]\`` to `Status: \`[x]\``.

Append a line immediately after each flipped status line:

```
Completed: 2026-04-22 via `feat/plan-12-blockers` (see
`docs/superpowers/specs/2026-04-22-plan-12-blockers-design.md`).
```

In the summary block around lines 1133–1135, flip:

```
- `[x]` REM-P1-007
- `[x]` REM-P1-008
- `[x]` REM-P1-009
```

- [ ] **Step 2: Annotate Plan 12 Task 0**

Edit `planning/implementation-plans/2026-04-17-phase-12-shared-chat-components.md`.

Locate the line `### Task 0: \`repo_items\` table + model + migration`. Immediately after that header, insert:

```
> **Landed with REM-P1-007 on 2026-04-22.** The `repo_items` migration and
> `RepoItem` model already exist on `main` (branch `feat/plan-12-blockers`).
> Task 0 is a no-op for this plan; proceed to Task 1.
```

- [ ] **Step 3: Sanity-check: confirm the audit summary is consistent**

```bash
grep -n "REM-P1-00[789]" planning/audits/2026-04-21-remediation-checklist.md
```

Expected: every occurrence of `REM-P1-007`, `REM-P1-008`, `REM-P1-009` in the summary block is prefixed `[x]`; section-header `Status:` lines are `[x]`.

- [ ] **Step 4: Commit Deliverable 4**

```bash
git add \
  planning/audits/2026-04-21-remediation-checklist.md \
  planning/implementation-plans/2026-04-17-phase-12-shared-chat-components.md
git commit -m "docs(audit): mark Plan 12 blockers complete"
```

- [ ] **Step 5: Final check — all four commits present, full suite green**

```bash
git log --oneline main..HEAD
uv run pytest packages/server/tests -q
```

Expected:

```
<sha4> docs(audit): mark Plan 12 blockers complete
<sha3> feat(chat): add Secretary chat SSE route backed by ChatRunner
<sha2> feat(reports): add report store service and GET /reports/{id}
<sha1> feat(db): consolidate saved-report persistence on repo_items
```

and a green pytest run. Branch is ready for PR.
