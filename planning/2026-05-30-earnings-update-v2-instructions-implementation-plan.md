# Earnings Update v2 — Instruction Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an Earnings Update v2 user save/upload free-form methodology "instruction profiles" and select one per run; the chosen profile's text is injected verbatim into the EU system prompt as authoritative analyst guidance (including which tools/endpoints to favor).

**Architecture:** Mirror the Equity Research v3 instructions feature, but as an **EU-owned fork** — a new `report_eu_instructions` table + `eu_v2_instructions_service` (near-verbatim copy of `v3_instructions_service`), consistent with how EU already forked its own `report_eu_templates` table. Flow: upload → `report_eu_instructions.body_text` → `eu_v2_instructions_service.resolve_instructions` → `RunRequest.instructions` → `_render_instructions_block()` → system prompt. Instructions are **optional** (no freeform-required guard — EU runs are always ticker-anchored).

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy + Alembic (server), Pydantic schemas + single-model engine (core), React/TypeScript/Vite (frontend), pytest, ruff, i18next (en + zh-TW).

**Key decision (locked):** Fork an EU-scoped instructions store rather than reuse `report_v3_instructions`. Rationale: EU already forked templates (`report_eu_templates`); reusing v3's table would make a profile uploaded in one engine appear in the other's list. If cross-engine sharing is ever wanted, collapse to a shared table later.

---

## File Structure

**Core (`packages/core`):**
- Modify `src/openlia/llm/runtime/report_eu/schemas.py` — add `instructions` to `RunRequest`.
- Modify `src/openlia/llm/runtime/report_eu/prompts.py` — add `_render_instructions_block` + inject.

**Server (`packages/server`):**
- Modify `src/openlia_server/db/models/report_eu.py` — add `ReportEuInstructions` model + `instructions_id` column on `EuV2Settings`.
- Create `src/openlia_server/db/migrations/versions/2026-05-31_xxxx_eu_v2_instructions.py` — new table + settings column.
- Create `src/openlia_server/services/eu_v2_instructions_service.py` — resolver/list/upload/delete (copy of v3 service).
- Modify `src/openlia_server/services/eu_v2_settings.py` — thread `instructions_id`.
- Modify `src/openlia_server/services/eu_v2_run_service.py` — resolve instructions, pass to `RunRequest`.
- Modify `src/openlia_server/routes/departments/earnings_update_v2.py` — DTOs + 3 routes + settings field.

**Frontend (`frontend`):**
- Modify `src/api/earnings-update.ts` — `instructions_id` on settings + 3 api functions.
- Modify `src/components/earnings-update/ReportSettingsModal.tsx` — instructions picker.
- Create `src/components/earnings-update/EuInstructionsUploadModal.tsx` — clone of v3 upload modal.
- Modify `src/i18n/locales/en.json` + `zh-TW.json` — new keys.

---

## Task 1: `ReportEuInstructions` ORM model + `instructions_id` settings column

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/report_eu.py`
- Test: `packages/server/tests/db/test_report_eu_models.py` (create if absent; otherwise add to the existing EU model test file)

Source to mirror: `packages/server/src/openlia_server/db/models/report_v3.py:300-349` (`ReportV3Instructions`).

- [ ] **Step 1: Write the failing test**

```python
# test_report_eu_models.py
from openlia_server.db.models.report_eu import EuV2Settings, ReportEuInstructions


def test_report_eu_instructions_columns():
    cols = ReportEuInstructions.__table__.columns
    assert "id" in cols and "user_id" in cols
    assert "name" in cols and "is_builtin" in cols
    assert "body_text" in cols
    assert "source_doc_blob" in cols and "source_doc_mime" in cols
    assert "created_at" in cols and "updated_at" in cols and "deleted_at" in cols
    assert ReportEuInstructions.__tablename__ == "report_eu_instructions"


def test_eu_v2_settings_has_instructions_id():
    assert "instructions_id" in EuV2Settings.__table__.columns
    assert EuV2Settings.__table__.columns["instructions_id"].nullable is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/server/tests/db/test_report_eu_models.py -v`
Expected: FAIL (ImportError / missing column).

- [ ] **Step 3: Add the model + column**

In `report_eu.py`, mirror `ReportV3Instructions` exactly but rename table/class:

```python
class ReportEuInstructions(Base):
    """User-uploaded free-form methodology profile for EU v2 runs.

    EU-owned fork of ``ReportV3Instructions`` (same shape, separate
    table) so EU and equity-research instruction lists stay independent.
    """

    __tablename__ = "report_eu_instructions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_doc_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_doc_mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (Index("ix_report_eu_instructions_user_id", "user_id"),)
```

Add to `EuV2Settings` (after `web_search_enabled`):

```python
    instructions_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Ensure `LargeBinary`, `Index`, `Text` are imported in `report_eu.py` (check existing imports; add if missing).

- [ ] **Step 4: Register the model**

EU models register via `register_all.py`, NOT `db/models/__init__.py` (guarded by `test_models_init_surface`). Add `ReportEuInstructions` to whatever EU registration list `report_eu.py` participates in (follow how `ReportEuTemplate` is registered).

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest packages/server/tests/db/test_report_eu_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/report_eu.py packages/server/tests/db/test_report_eu_models.py
git commit -m "feat(eu-v2): ReportEuInstructions model + settings.instructions_id"
```

---

## Task 2: Alembic migration (new table + settings column)

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-05-31_0900_eu_v2_instructions.py`

Mirror style: `versions/2026-05-29-2355_earnings_update_v2_tables.py` and `versions/2026-05-29_1200_report_v3_instructions.py`.

- [ ] **Step 1: Write the migration**

`down_revision` = current head (`eae15acd2745` — confirm with `uv run --directory packages/server alembic heads`). Upgrade creates `report_eu_instructions` (columns per Task 1) + its index, and adds the nullable `instructions_id` column to `eu_v2_settings`. Downgrade drops the column then the table.

```python
"""earnings update v2 instruction profiles

Revision ID: <generate>
Revises: eae15acd2745
"""
from alembic import op
import sqlalchemy as sa

revision = "<generate>"
down_revision = "eae15acd2745"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_eu_instructions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("source_doc_blob", sa.LargeBinary(), nullable=True),
        sa.Column("source_doc_mime", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_report_eu_instructions_user_id", "report_eu_instructions", ["user_id"])
    with op.batch_alter_table("eu_v2_settings") as batch:
        batch.add_column(sa.Column("instructions_id", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("eu_v2_settings") as batch:
        batch.drop_column("instructions_id")
    op.drop_index("ix_report_eu_instructions_user_id", table_name="report_eu_instructions")
    op.drop_table("report_eu_instructions")
```

- [ ] **Step 2: Apply against a scratch DB and verify**

Run:
```bash
TESTDB="$TMPDIR/eu_instr_$(date +%s).db"
OPENLIA_DB_URL="sqlite:///$TESTDB" uv run --directory packages/server alembic upgrade head
```
Expected: ends on the new head, no error. Verify the table + column exist (sqlite introspection).

- [ ] **Step 3: Run the migration-hygiene tests**

Run: `uv run pytest packages/server/tests -k "migration or alembic" -q`
Expected: no NEW failures beyond the 6 pre-existing SQLite batch-downgrade failures already failing on `main`.

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-05-31_0900_eu_v2_instructions.py
git commit -m "feat(eu-v2): migration for report_eu_instructions + settings.instructions_id"
```

---

## Task 3: `eu_v2_instructions_service`

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_instructions_service.py`
- Test: `packages/server/tests/services/test_eu_v2_instructions_service.py`

Source to copy near-verbatim: `packages/server/src/openlia_server/services/v3_instructions_service.py` (full). Change the import `ReportV3Instructions` → `ReportEuInstructions`, error message strings `"v3 instructions"` → `"eu instructions"`, and docstrings.

- [ ] **Step 1: Write failing tests** (mirror the v3 service tests; seed a `local` User inline — conftest only seeds u-1/u-2)

```python
import pytest
from openlia_server.services import eu_v2_instructions_service as svc


def _seed_user(db):
    from openlia_server.db.models.auth import User
    if db.get(User, "local") is None:
        db.add(User(id="local", email="local@openlia.local", display_name="Local"))
        db.flush()


def test_create_resolve_and_list(db_session):
    _seed_user(db_session)
    row = svc.create_instructions_from_upload(
        db=db_session, user_id="local", name="My Method", body_text="Favor FCF over EBITDA."
    )
    db_session.commit()
    assert svc.resolve_instructions(db=db_session, user_id="local", instructions_id=row.id) == "Favor FCF over EBITDA."
    names = [s.name for s in svc.list_instructions(db=db_session, user_id="local")]
    assert "My Method" in names


def test_empty_text_rejected(db_session):
    _seed_user(db_session)
    with pytest.raises(svc.InstructionsValidationError):
        svc.create_instructions_from_upload(db=db_session, user_id="local", name="x", body_text="   ")


def test_resolve_unknown_raises(db_session):
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(db=db_session, user_id="local", instructions_id="nope")


def test_soft_delete_then_resolve_raises(db_session):
    _seed_user(db_session)
    row = svc.create_instructions_from_upload(db=db_session, user_id="local", name="d", body_text="text")
    db_session.commit()
    svc.soft_delete_instructions(db=db_session, user_id="local", instructions_id=row.id)
    db_session.commit()
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(db=db_session, user_id="local", instructions_id=row.id)


def test_owner_scoping(db_session):
    _seed_user(db_session)
    row = svc.create_instructions_from_upload(db=db_session, user_id="local", name="p", body_text="t")
    db_session.commit()
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(db=db_session, user_id="u-2", instructions_id=row.id)
```

- [ ] **Step 2: Run to verify fail** — `uv run pytest packages/server/tests/services/test_eu_v2_instructions_service.py -v` → FAIL (ImportError).

- [ ] **Step 3: Create the service** — copy `v3_instructions_service.py` verbatim into `eu_v2_instructions_service.py`; swap the model import to `ReportEuInstructions`, rename the two exception classes' messages, and adjust the module docstring to say EU. Keep all four functions and `InstructionsSummary` identical in shape.

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/eu_v2_instructions_service.py packages/server/tests/services/test_eu_v2_instructions_service.py
git commit -m "feat(eu-v2): eu_v2_instructions_service (forked from v3)"
```

---

## Task 4: `RunRequest.instructions` (core schema)

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/schemas.py`
- Test: `packages/core/tests/runtime/report_eu/test_schemas.py` (create if absent)

- [ ] **Step 1: Write the failing test**

```python
from openlia.llm.runtime.report_eu.schemas import RunRequest, TemplateSpec


def test_run_request_accepts_instructions():
    req = RunRequest(
        subject="SNOW earnings",
        template=TemplateSpec(template_id="eu_default", name="d", shape_description="s", sections=[]),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        instructions="Favor FCF. Skip web search.",
    )
    assert req.instructions == "Favor FCF. Skip web search."


def test_run_request_instructions_defaults_none():
    req = RunRequest(
        subject="x",
        template=TemplateSpec(template_id="eu_default", name="d", shape_description="s", sections=[]),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )
    assert req.instructions is None
```

- [ ] **Step 2: Run to verify fail** — `uv run pytest packages/core/tests/runtime/report_eu/test_schemas.py -v` → FAIL.

- [ ] **Step 3: Add the field** — in `RunRequest`, add after `trigger_context`:

```python
    # Free-form analyst methodology selected for this run, injected
    # verbatim into the system prompt as authoritative guidance. ``None``
    # = no profile chosen (the common case). Re-added vs. the original EU
    # fork, which dropped it.
    instructions: str | None = None
```

Update the class docstring: change "no ``attachments`` / ``instructions``" to "no ``attachments``" (instructions are now supported).

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_eu/schemas.py packages/core/tests/runtime/report_eu/test_schemas.py
git commit -m "feat(eu-v2): add RunRequest.instructions field"
```

---

## Task 5: Inject instructions into the EU system prompt

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/prompts.py`
- Test: `packages/core/tests/runtime/report_eu/test_prompts.py` (create if absent)

Source to copy: `report_v3/prompts.py` `_render_instructions_block` (lines 68-83).

- [ ] **Step 1: Write the failing test**

```python
from openlia.llm.runtime.report_eu.prompts import build_system_prompt
from openlia.llm.runtime.report_eu.schemas import RunRequest, TemplateSpec


def _req(**kw):
    base = dict(
        subject="SNOW earnings",
        template=TemplateSpec(template_id="eu_default", name="d", shape_description="s", sections=[]),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )
    base.update(kw)
    return RunRequest(**base)


def test_instructions_block_present_when_set():
    out = build_system_prompt(_req(instructions="Favor FCF over EBITDA."))
    assert "Analyst instructions" in out
    assert "Favor FCF over EBITDA." in out


def test_instructions_block_absent_when_none():
    out = build_system_prompt(_req())
    assert "Analyst instructions" not in out
```

- [ ] **Step 2: Run to verify fail** — `uv run pytest packages/core/tests/runtime/report_eu/test_prompts.py -v` → FAIL.

- [ ] **Step 3: Implement** — add the renderer (copy v3's wording) and wire it into the template.

Add function:
```python
def _render_instructions_block(instructions: str | None) -> str:
    """The ``# Analyst instructions`` block, or empty when none given."""
    if not instructions or not instructions.strip():
        return ""
    return (
        "# Analyst instructions\n\n"
        "The user provided the methodology and guidance below. Treat it as "
        "authoritative for how to approach this report — what to research and "
        "emphasize, how to reason, tone, which tools/endpoints to favor, and "
        "(where it specifies one) the report's structure.\n\n"
        f"{instructions.strip()}\n\n"
    )
```

In `build_system_prompt`, add `instructions_block=_render_instructions_block(request.instructions),` to the `.format(...)` call.

In `_PROMPT_TEMPLATE`, insert the slot immediately after `{shape_description}` and before `{trigger_block}` (so guidance precedes the event context and structure):

```
# Template: {template_name}
{shape_description}

{instructions_block}{trigger_block}# Report structure
```

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_eu/prompts.py packages/core/tests/runtime/report_eu/test_prompts.py
git commit -m "feat(eu-v2): inject analyst instructions block into EU prompt"
```

---

## Task 6: Settings DTO/service threads `instructions_id`

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_settings.py`
- Test: `packages/server/tests/services/test_eu_v2_settings.py` (add cases)

- [ ] **Step 1: Write the failing test**

```python
from openlia_server.services import eu_v2_settings as svc


def test_update_and_get_round_trips_instructions_id(db_session):
    # seed local user as in other EU service tests
    from openlia_server.db.models.auth import User
    if db_session.get(User, "local") is None:
        db_session.add(User(id="local", email="l@x", display_name="L")); db_session.flush()
    svc.update_settings(
        db=db_session, user_id="local", provider_kind="anthropic", model="claude-sonnet-4-6",
        template_id="eu_default", language="en", length="normal", reasoning_effort=None,
        financial_enabled=True, calendar_enabled=True, web_search_enabled=False,
        instructions_id="abc123",
    )
    dto = svc.get_settings(db=db_session, user_id="local")
    assert dto.instructions_id == "abc123"


def test_defaults_have_none_instructions_id(db_session):
    dto = svc.get_settings(db=db_session, user_id="u-1")
    assert dto.instructions_id is None
```

- [ ] **Step 2: Run to verify fail** — FAIL (unexpected kwarg / missing attr).

- [ ] **Step 3: Implement** — in `eu_v2_settings.py`:
  - Add `instructions_id: str | None` to `EuSettingsDTO`.
  - `_row_to_dto`: add `instructions_id=row.instructions_id`.
  - `get_settings` defaults branch: add `instructions_id=None`.
  - `update_settings`: add `instructions_id: str | None = None` param; set on both the create branch (`instructions_id=instructions_id`) and the update branch (`row.instructions_id = instructions_id`).

- [ ] **Step 4: Run to verify pass** — PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/eu_v2_settings.py packages/server/tests/services/test_eu_v2_settings.py
git commit -m "feat(eu-v2): thread instructions_id through settings service"
```

---

## Task 7: Resolve instructions at run-start and pass to the engine

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_run_service.py`
- Test: `packages/server/tests/services/test_eu_v2_run_service.py` (add a case)

Reference: `build_run_request` currently reads `settings`, resolves `template`, builds `EnabledConnectors`, returns `RunRequest(...)` (no instructions).

- [ ] **Step 1: Write the failing test** — build settings with an `instructions_id` pointing at a seeded `report_eu_instructions` row, call `build_run_request`, assert `request.instructions` equals the profile body; with `instructions_id=None`, assert `request.instructions is None`.

```python
def test_build_run_request_injects_instructions(db_session):
    # seed local user, an instruction profile, and settings referencing it
    from openlia_server.db.models.auth import User
    from openlia_server.services import eu_v2_instructions_service as instr_svc
    from openlia_server.services import eu_v2_settings as settings_svc
    if db_session.get(User, "local") is None:
        db_session.add(User(id="local", email="l@x", display_name="L")); db_session.flush()
    row = instr_svc.create_instructions_from_upload(
        db=db_session, user_id="local", name="m", body_text="Favor FCF."
    )
    settings_svc.update_settings(
        db=db_session, user_id="local", provider_kind="anthropic", model="claude-sonnet-4-6",
        template_id="eu_default", language="en", length="normal", reasoning_effort=None,
        financial_enabled=True, calendar_enabled=True, web_search_enabled=False,
        instructions_id=row.id,
    )
    from openlia_server.services import eu_v2_run_service as run_svc
    req = run_svc.build_run_request(
        db_session, user_id="local", ticker="SNOW", trigger_kind="on_demand",
        fiscal_period=None, report_date=None, release_timing=None,
        eps_estimate=None, revenue_estimate=None,
    )
    assert req.instructions == "Favor FCF."
```

- [ ] **Step 2: Run to verify fail** — FAIL (`req.instructions is None`).

- [ ] **Step 3: Implement** — in `build_run_request`, after `settings = eu_v2_settings.get_settings(...)`:

```python
    instructions_text: str | None = None
    if settings.instructions_id:
        from openlia_server.services import eu_v2_instructions_service
        try:
            instructions_text = eu_v2_instructions_service.resolve_instructions(
                db=db, user_id=user_id, instructions_id=settings.instructions_id
            )
        except eu_v2_instructions_service.InstructionsNotFoundError:
            # Profile was deleted after selection — degrade to no
            # instructions rather than failing the run.
            instructions_text = None
```

Add `instructions=instructions_text,` to the returned `RunRequest(...)`.

- [ ] **Step 4: Run to verify pass** — PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/eu_v2_run_service.py packages/server/tests/services/test_eu_v2_run_service.py
git commit -m "feat(eu-v2): resolve selected instructions into the run request"
```

---

## Task 8: EU v2 routes — settings field + 3 instruction endpoints

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py`
- Test: `packages/server/tests/routes/test_earnings_update_v2_instructions.py` (create)

Reference patterns: the EU templates routes (`earnings_update_v2.py:610-677`) for list/delete/gate shape; the v3 upload route (`equity_research_v3.py:983-1029`) for multipart + `validate_uploads`/`extract_text`/`FileUpload` (import from the same `openlia_server` attachments utils v3 uses).

- [ ] **Step 1: Write failing route tests** (use the existing EU v2 TestClient fixture; engine gated on `EARNINGS_ENGINE_VERSION=v2`):

```python
def test_instructions_crud_roundtrip(eu_v2_client):
    # POST (multipart)
    r = eu_v2_client.post(
        "/api/departments/earnings-update/v2/instructions",
        data={"name": "My Method"},
        files={"file": ("m.txt", b"Favor FCF over EBITDA.", "text/plain")},
    )
    assert r.status_code == 201
    iid = r.json()["id"]
    # GET list
    lst = eu_v2_client.get("/api/departments/earnings-update/v2/instructions").json()
    assert any(p["id"] == iid for p in lst)
    # PUT settings selects it
    s = eu_v2_client.put(
        "/api/departments/earnings-update/v2/settings",
        json={"provider_kind": "anthropic", "model": "claude-sonnet-4-6",
              "template_id": "eu_default", "language": "en", "length": "normal",
              "reasoning_effort": None, "financial_enabled": True,
              "calendar_enabled": True, "web_search_enabled": False,
              "instructions_id": iid},
    )
    assert s.status_code == 200 and s.json()["instructions_id"] == iid
    # DELETE
    assert eu_v2_client.delete(f"/api/departments/earnings-update/v2/instructions/{iid}").status_code == 204


def test_instructions_gated_when_engine_off(eu_v2_client_disabled):
    assert eu_v2_client_disabled.get("/api/departments/earnings-update/v2/instructions").status_code == 503
```

- [ ] **Step 2: Run to verify fail** — FAIL (404 routes / missing field).

- [ ] **Step 3: Implement**

1. `SettingsOut`: add `instructions_id: str | None`.
2. `SettingsUpdateIn`: add `instructions_id: str | None = None`.
3. The settings GET handler: include `instructions_id=dto.instructions_id`; the PUT handler: pass `instructions_id=payload.instructions_id` into `update_settings(...)`.
4. Add `InstructionsOut(BaseModel)` with `id, name, is_builtin, created_at, updated_at` (copy v3's).
5. Import `eu_v2_instructions_service as instructions_svc`, and the attachments utils (`FileUpload`, `validate_uploads`, `extract_text`) v3 uses.
6. Add 3 routes mirroring v3 (`equity_research_v3.py:964-1048`) but gate with `eu_v2_enabled()`/`_engine_disabled()` and prefix on the EU router:
   - `GET /instructions` → `list_instructions` → `list[InstructionsOut]`
   - `POST /instructions` (async, multipart `name: Form`, `file: UploadFile`) → validate → `create_instructions_from_upload` → 201 `InstructionsOut`; on `InstructionsValidationError` → 400
   - `DELETE /instructions/{instructions_id}` → `soft_delete_instructions` → 204; on `InstructionsNotFoundError` → 404
   - Each route commits via the request `db` (templates routes call `db.commit()` after create/delete).

- [ ] **Step 4: Run to verify pass** — PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/earnings_update_v2.py packages/server/tests/routes/test_earnings_update_v2_instructions.py
git commit -m "feat(eu-v2): instructions routes + settings.instructions_id"
```

---

## Task 9: Frontend API client

**Files:**
- Modify: `frontend/src/api/earnings-update.ts`
- Test: `frontend/src/api/__tests__/earnings-update.test.ts` (add cases if a test harness exists; otherwise rely on `tsc` + manual)

Source to mirror: `frontend/src/api/equity-research-v3.ts:420-464`.

- [ ] **Step 1: Add `instructions_id` to the `EuSettings` interface** (`string | null`), and the settings update payload type.

- [ ] **Step 2: Add types + functions** (point at the EU base path):

```ts
export interface EuInstructionsSummary {
  id: string; name: string; is_builtin: boolean;
  created_at: string; updated_at: string;
}
const INSTR = `${BASE}/instructions`;
export const listEuInstructions = () => fetchJson<EuInstructionsSummary[]>(INSTR);
export const uploadEuInstructions = (name: string, file: File) => {
  const fd = new FormData();
  fd.append("name", name);
  fd.append("file", file);
  return fetchJson<EuInstructionsSummary>(INSTR, { method: "POST", body: fd });
};
export const deleteEuInstructions = (id: string) =>
  fetchJson<void>(`${INSTR}/${id}`, { method: "DELETE" });
```

(Match `BASE` and `fetchJson` conventions already in this file; for multipart, do NOT set a JSON Content-Type — let the browser set the boundary, mirroring v3.)

- [ ] **Step 3: Verify** — `cd frontend && npx tsc --noEmit` → clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/earnings-update.ts
git commit -m "feat(eu-v2-fe): instructions api client + settings.instructions_id"
```

---

## Task 10: Instructions upload modal (frontend)

**Files:**
- Create: `frontend/src/components/earnings-update/EuInstructionsUploadModal.tsx`

Source to clone: `frontend/src/components/equity-research-v3/V3InstructionsUploadModal.tsx`.

- [ ] **Step 1: Clone the v3 modal** — same file-picker (`.pdf,.docx,.md,.txt`), auto-fill name from filename, inline error display, `onSaved(profile)` callback. Swap `uploadV3Instructions` → `uploadEuInstructions` and the type to `EuInstructionsSummary`. Replace any hardcoded strings with i18n keys (Task 12).

- [ ] **Step 2: Verify** — `npx tsc --noEmit` clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/earnings-update/EuInstructionsUploadModal.tsx
git commit -m "feat(eu-v2-fe): instructions upload modal"
```

---

## Task 11: Instructions picker in the settings modal

**Files:**
- Modify: `frontend/src/components/earnings-update/ReportSettingsModal.tsx`

Source to mirror: `V3ReportSettingsModal.tsx:137-350` (fetch on mount, picker dropdown, per-row delete, upload trigger).

- [ ] **Step 1: Add state + fetch** — on mount call `listEuInstructions()`; hold `instructions` list, `instructionsId` (init from `draft.instructions_id`), and an upload-modal-open flag.

- [ ] **Step 2: Render the picker** — a labeled dropdown of profiles (plus a "None" option), a delete button per user profile (calls `deleteEuInstructions`, refetch), and an "Upload instructions" button opening `EuInstructionsUploadModal`; on `onSaved`, refetch and select the new profile.

- [ ] **Step 3: Wire save** — include `instructions_id: instructionsId ?? null` in the settings PUT payload in `handleSave`.

- [ ] **Step 4: Verify** — `npx tsc --noEmit` clean; `cd frontend && npm run build` succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/ReportSettingsModal.tsx
git commit -m "feat(eu-v2-fe): instructions picker in settings modal"
```

---

## Task 12: i18n keys (en + zh-TW)

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Add keys** under `earnings.settings_modal` (mirror the v3 instructions keys): label for the picker, "None", "Upload instructions", upload-modal title/fields/errors, delete confirm. Provide both en and Traditional Chinese values.

- [ ] **Step 2: Verify parity** — a tiny node script (or existing i18n-parity test) confirms the new keys exist in both files with identical key sets.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(eu-v2-fe): i18n for instruction profiles (en + zh-TW)"
```

---

## Final verification (after all tasks)

- [ ] Backend: `uv run pytest packages/core/tests/runtime/report_eu/ packages/server/tests -k "eu_v2 or report_eu" -q` → green (modulo the 6 pre-existing migration failures).
- [ ] `uv run ruff check .` and `uv run ruff format --check .` → clean.
- [ ] Frontend: `cd frontend && npx tsc --noEmit && npm run build` → clean.
- [ ] **Live smoke (verify skill):** boot the server with `EARNINGS_ENGINE_VERSION=v2`, upload an instruction profile that says e.g. "Do not use web search; rely only on EODHD fundamentals," select it, run an on-demand SNOW report, and confirm the system prompt carries the `# Analyst instructions` block and the model honors it (no web_search tool calls in the run).

---

## Non-goals (this plan)

- Per-connector tool exposure / dispatcher wiring (that is Scope A — separate plan).
- A "freeform / no-template requires instructions" guard (EU stays ticker-anchored; instructions optional).
- Built-in seeded instruction profiles (the store supports `is_builtin`, but seeding is out of scope here).
- Editing an existing profile's text in place (upload-new + delete-old, same as v3).
