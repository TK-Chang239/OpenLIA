# EU v2 Report Download + Save-to-Repo (v3 parity) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Earnings Update v2 reports the same Download (PDF/Word), standalone HTML, and Save-to-Repo as equity-research v3.

**Architecture:** Approach A — fork the thin v3 server wrappers into `eu_v2_*` (the heavy core renderer `report_eu/rendering/assemble_html` is already shared + generic), and extend the already-polymorphic `RepoItem` with a 4th target column for save-to-repo. No changes to working v3 code.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic, Playwright (PDF), python-docx (Word), React/TS/Vite, Vitest, pytest.

**Base branch:** `feat/eu-report-export-and-repo` (off `main`).

**Spec:** `docs/superpowers/specs/2026-06-01-eu-report-export-and-repo-design.md`

**Conventions:**
- Python tests: `uv run pytest <path>` (if `uv` hits a sandbox cache error, the controller re-runs unsandboxed). Frontend: from `frontend/`, `npx vitest run <path>`, `npx tsc --noEmit`, `npm run build`. Lint: `uv run ruff check <paths>`.
- This plan has **two independently-shippable phases**: **Phase 1 (Export)** Tasks 1–6, **Phase 2 (Save-to-Repo)** Tasks 7–11, then Task 12 (integration). Each phase compiles + tests green on its own.
- Reference the v3 implementations when forking: `v3_render_service.py`, `v3_docx.py`, `v3_filename.py`, `repo.py` (`save_v3_report_to_repo`), `repo.py` routes (`/v3-runs`), and the v3 frontend (`reports.ts` engine `v3`, `repo.ts` `saveV3RunToRepo`, `SaveToRepoButton` v3 branch, the Repo page's v3 open). Mirror them exactly, swapping v3 identifiers/paths for EU.

---

## File Structure

| File | Responsibility | Action |
| --- | --- | --- |
| `packages/server/src/openlia_server/services/eu_v2_run_service.py` | Add `get_run` / `get_report_row` / `ReportNotFoundError` loaders. | Modify |
| `packages/server/src/openlia_server/services/eu_v2_filename.py` | `Ticker_Template_Date.ext` filename (fork of v3). | Create |
| `packages/server/src/openlia_server/services/eu_v2_docx.py` | `report_eu` → .docx bytes (fork of v3_docx). | Create |
| `packages/server/src/openlia_server/services/eu_v2_render_service.py` | html/pdf/docx render (reuses core `assemble_html`). | Create |
| `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py` | Add html/pdf/docx endpoints; drop stale comment. | Modify |
| `packages/server/src/openlia_server/db/models/content.py` | `RepoItem.eu_v2_report_id` + unique + 4-way CHECK. | Modify |
| `packages/server/src/openlia_server/db/migrations/versions/<new>.py` | Migration for the column/constraints. | Create |
| `packages/server/src/openlia_server/services/repo.py` | EU save/unsave/is-saved + list metadata for EU. | Modify |
| `packages/server/src/openlia_server/routes/repo.py` | `POST/DELETE/GET /eu-runs`. | Modify |
| `frontend/src/api/reports.ts` | `"eu"` engine + EU pdf/docx/html URLs. | Modify |
| `frontend/src/api/repo.ts` | `"eu"` engine + save/unsave/list EU. | Modify |
| `frontend/src/components/chat/SaveToRepoButton.tsx` | `"eu"` engine. | Modify |
| `frontend/src/components/viewer/ViewerHeader.tsx` | EU branch: download + save + standalone. | Modify |
| `frontend/src/pages/departments/EarningsUpdate.tsx` | Pass reportId + `eu` save-engine on open. | Modify |
| Repo page (open handler) | Saved EU item → `eu_v2_report` viewer source. | Modify |

---

# PHASE 1 — EXPORT (Download PDF/Word + standalone HTML)

## Task 1: EU run loaders in `eu_v2_run_service`

The render service + endpoints need a typed loader (mirror v3's `svc.get_run` / `svc.get_report_row` / `ReportNotFoundError`). Today the EU route loads rows inline (`_load_owned_run` + selects); centralize it.

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_run_service.py`
- Test: `packages/server/tests/test_services/test_eu_v2_run_service.py`

- [ ] **Step 1: Failing test**

Append to `test_eu_v2_run_service.py` (it already has `db_session_with_seed`, `update_settings`, `_fake_session`, `db_session_factory`, and seeds the `eu_default` template; reuse the existing `test_start_run_async_completes_and_persists` pattern to create a completed run, then load it):

```python
def test_get_run_loads_row_with_children(db_session_with_seed):
    # Insert a minimal completed report_eu row + one section directly.
    from openlia_server.db.models.report_eu import ReportEu, ReportEuSection
    from datetime import UTC, datetime

    rid = "rid-load-1"
    db_session_with_seed.add(
        ReportEu(
            id=rid, user_id="u-1", subject="AAPL earnings", ticker="AAPL",
            trigger_kind="on_demand", fiscal_date=None, template_id="eu_default",
            language="en", length="normal", provider_kind="anthropic",
            model="claude-sonnet-4-6", status="completed", error_message=None,
            created_at=datetime.now(UTC), completed_at=datetime.now(UTC),
            cover_json=None, reasoning_effort=None,
        )
    )
    db_session_with_seed.add(
        ReportEuSection(
            report_id=rid, section_id="quick_take", section_index=0,
            title="Quick Take", markdown="Body.", version=1,
        )
    )
    db_session_with_seed.flush()

    row, sections, charts, citations = svc.get_run(
        db=db_session_with_seed, user_id="u-1", report_id=rid
    )
    assert row.id == rid
    assert [s.section_id for s in sections] == ["quick_take"]
    assert charts == []
    assert citations == []


def test_get_run_missing_raises(db_session_with_seed):
    import pytest as _pytest
    with _pytest.raises(svc.ReportNotFoundError):
        svc.get_run(db=db_session_with_seed, user_id="u-1", report_id="nope")
```

(If `ReportEuSection`'s exact column names differ, match `packages/server/src/openlia_server/db/models/report_eu.py`.)

- [ ] **Step 2: Run → FAIL** (`svc.get_run` / `svc.ReportNotFoundError` don't exist).

Run: `uv run pytest packages/server/tests/test_services/test_eu_v2_run_service.py -k "get_run" -q`

- [ ] **Step 3: Implement** in `eu_v2_run_service.py`. Add near the top-level helpers:

```python
class ReportNotFoundError(LookupError):
    """The requested report_eu row doesn't exist or isn't owned by the user."""


def get_report_row(*, db: DBSession, user_id: str, report_id: str) -> ReportEu:
    row = db.get(ReportEu, report_id)
    if row is None or row.user_id != user_id:
        raise ReportNotFoundError(f"EU report {report_id} not found")
    return row


def get_run(
    *, db: DBSession, user_id: str, report_id: str
) -> tuple[ReportEu, list[ReportEuSection], list[ReportEuChart], list[ReportEuCitation]]:
    """Load a report_eu row + its ordered sections/charts/citations."""
    from sqlalchemy import select as _select

    row = get_report_row(db=db, user_id=user_id, report_id=report_id)
    sections = list(
        db.execute(
            _select(ReportEuSection)
            .where(ReportEuSection.report_id == report_id)
            .order_by(ReportEuSection.section_index.asc())
        ).scalars()
    )
    charts = list(
        db.execute(
            _select(ReportEuChart).where(ReportEuChart.report_id == report_id)
        ).scalars()
    )
    citations = list(
        db.execute(
            _select(ReportEuCitation)
            .where(ReportEuCitation.report_id == report_id)
            .order_by(ReportEuCitation.display_index.asc())
        ).scalars()
    )
    return row, sections, charts, citations
```

`ReportEu`, `ReportEuSection`, `ReportEuChart`, `ReportEuCitation` are already imported in this module.

- [ ] **Step 4: Run → PASS.** Also run the full file: `uv run pytest packages/server/tests/test_services/test_eu_v2_run_service.py -q`.

- [ ] **Step 5: Commit**
```bash
git add packages/server/src/openlia_server/services/eu_v2_run_service.py packages/server/tests/test_services/test_eu_v2_run_service.py
git commit -m "feat(eu): get_run/get_report_row loaders for the render service"
```

---

## Task 2: `eu_v2_filename`

Fork of `v3_filename.py` with EU template labels and `ReportEu` typing.

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_filename.py`
- Test: `packages/server/tests/test_services/test_eu_v2_filename.py`

- [ ] **Step 1: Failing test** — create `test_eu_v2_filename.py`:

```python
from datetime import UTC, datetime

from openlia_server.db.models.report_eu import ReportEu
from openlia_server.services.eu_v2_filename import build_download_filename


def _row() -> ReportEu:
    return ReportEu(
        id="r1", user_id="u1", subject="AAPL", ticker="AAPL",
        trigger_kind="on_demand", fiscal_date=None, template_id="eu_default",
        language="en", length="normal", provider_kind="anthropic", model="m",
        status="completed", error_message=None,
        created_at=datetime(2026, 4, 9, tzinfo=UTC),
        completed_at=datetime(2026, 4, 9, tzinfo=UTC),
        cover_json=None, reasoning_effort=None,
    )


def test_filename_shape():
    assert build_download_filename(row=_row(), ext="pdf") == "AAPL_Earnings-Update_2026-04-09.pdf"
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — copy `v3_filename.py` to `eu_v2_filename.py`, then change: import `ReportEu` instead of `ReportV3`; type `build_download_filename(*, row: ReportEu, ext: str)`; replace `_TEMPLATE_LABEL` with `{"eu_default": "Earnings-Update"}`. Keep `slugify_filename_component` + `template_label` + the `Subject_Template_Date.ext` body verbatim.
- [ ] **Step 4: Run → PASS.** `uv run ruff check packages/server/src/openlia_server/services/eu_v2_filename.py` clean.
- [ ] **Step 5: Commit**
```bash
git add packages/server/src/openlia_server/services/eu_v2_filename.py packages/server/tests/test_services/test_eu_v2_filename.py
git commit -m "feat(eu): download filename helper"
```

---

## Task 3: `eu_v2_docx`

Fork of `v3_docx.py` with `ReportEu*` types.

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_docx.py`
- Test: `packages/server/tests/test_services/test_eu_v2_docx.py`

- [ ] **Step 1: Read** `packages/server/src/openlia_server/services/v3_docx.py` fully.
- [ ] **Step 2: Failing test** — create `test_eu_v2_docx.py`:

```python
from openlia_server.db.models.report_eu import ReportEu, ReportEuSection
from openlia_server.services.eu_v2_docx import render_docx
from datetime import UTC, datetime


def test_render_docx_returns_zip_bytes():
    row = ReportEu(
        id="r1", user_id="u1", subject="AAPL", ticker="AAPL", trigger_kind="on_demand",
        fiscal_date=None, template_id="eu_default", language="en", length="normal",
        provider_kind="anthropic", model="m", status="completed", error_message=None,
        created_at=datetime.now(UTC), completed_at=datetime.now(UTC),
        cover_json=None, reasoning_effort=None,
    )
    sections = [ReportEuSection(report_id="r1", section_id="quick_take", section_index=0,
                                title="Quick Take", markdown="Body text.", version=1)]
    out = render_docx(report=row, sections=sections, charts=[], citations=[])
    assert isinstance(out, (bytes, bytearray)) and out[:2] == b"PK"  # .docx is a zip
```

- [ ] **Step 3: Run → FAIL.**
- [ ] **Step 4: Implement** — copy `v3_docx.py` → `eu_v2_docx.py`. Replace every `ReportV3` → `ReportEu`, `ReportV3Section` → `ReportEuSection`, `ReportV3Chart` → `ReportEuChart`, `ReportV3Citation` → `ReportEuCitation` (imports + signatures + type hints). Swap the chart renderer import from `report_v3.rendering` → `report_eu.rendering` (it has the same `chart_renderer`). Keep all docx-building logic identical.
- [ ] **Step 5: Run → PASS.** ruff clean.
- [ ] **Step 6: Commit**
```bash
git add packages/server/src/openlia_server/services/eu_v2_docx.py packages/server/tests/test_services/test_eu_v2_docx.py
git commit -m "feat(eu): docx renderer"
```

---

## Task 4: `eu_v2_render_service`

Fork of `v3_render_service.py`, wired to the EU loaders + EU docx + core `report_eu` assembler.

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_render_service.py`
- Test: `packages/server/tests/test_services/test_eu_v2_render_service.py`

- [ ] **Step 1: Failing test** — create `test_eu_v2_render_service.py` (mirror the seeding from Task 1):

```python
from datetime import UTC, datetime

from openlia_server.db.models.report_eu import ReportEu, ReportEuSection
from openlia_server.services import eu_v2_render_service as render_svc


def _seed_completed(db) -> str:
    rid = "rr-1"
    db.add(ReportEu(
        id=rid, user_id="u-1", subject="AAPL earnings", ticker="AAPL",
        trigger_kind="on_demand", fiscal_date=None, template_id="eu_default",
        language="en", length="normal", provider_kind="anthropic", model="m",
        status="completed", error_message=None,
        created_at=datetime.now(UTC), completed_at=datetime.now(UTC),
        cover_json=None, reasoning_effort=None,
    ))
    db.add(ReportEuSection(report_id=rid, section_id="quick_take", section_index=0,
                           title="Quick Take", markdown="Body text.", version=1))
    db.flush()
    return rid


def test_render_html_contains_section(db_session_with_seed):
    rid = _seed_completed(db_session_with_seed)
    out = render_svc.render_html(db=db_session_with_seed, user_id="u-1", report_id=rid)
    assert "Quick Take" in out.html


def test_render_docx_returns_bytes(db_session_with_seed):
    rid = _seed_completed(db_session_with_seed)
    out = render_svc.render_docx(db=db_session_with_seed, user_id="u-1", report_id=rid)
    assert isinstance(out, (bytes, bytearray)) and out[:2] == b"PK"
```

(Reuse the `db_session_with_seed` fixture — import it via the test module's existing conftest path; if this new test file can't see it, add `from .test_eu_v2_run_service import db_session_with_seed` or move the fixture to a conftest. Match how the other `test_services` files obtain it.)

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — copy `v3_render_service.py` → `eu_v2_render_service.py` and change:
  - import `assemble_html`, `AssembledReport` from `openlia.llm.runtime.report_eu.rendering` (not report_v3),
  - `from openlia_server.services import eu_v2_run_service as svc`,
  - `from openlia_server.services.eu_v2_docx import render_docx as _build_docx`,
  - `svc.get_run(...)` (the Task 1 loader returns the same 4-tuple),
  - keep `render_html` / `render_docx` / `render_pdf` / `_persist_rendered_urls` bodies identical (they're attribute-based).
- [ ] **Step 4: Run → PASS** (html + docx; pdf path is exercised by the endpoint test with a launcher, or skipped without Playwright). ruff clean.
- [ ] **Step 5: Commit**
```bash
git add packages/server/src/openlia_server/services/eu_v2_render_service.py packages/server/tests/test_services/test_eu_v2_render_service.py
git commit -m "feat(eu): render service (html/pdf/docx) reusing the core assembler"
```

---

## Task 5: EU export endpoints

Add `GET /runs/{id}/html|pdf|docx` to the EU router, mirroring v3 (`equity_research_v3.py` get_html/get_pdf/get_docx). Remove the stale "intentionally NOT implemented" comment (lines ~20-23 of the route module docstring).

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py`
- Test: `packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py`

- [ ] **Step 1: Failing test** — add a test that posts/creates a completed run (reuse the existing route-test harness for EU; mirror how the v3 route tests hit `/html`), then `GET /runs/{id}/html` returns 200 with `Content-Disposition` containing `.html` and the body contains a section title; `GET /runs/{id}/docx` returns 200 with the docx content-type; a missing id returns 404. (Read the existing `test_earnings_update_v2_routes.py` for its client/auth/seed fixtures and the v3 route tests `test_equity_research_v3*` for the html/docx assertions; mirror them with EU paths.) PDF: assert 503 when no launcher is wired in the test app, OR skip if the test app has one — match the v3 pdf route test.
- [ ] **Step 2: Run → FAIL** (endpoints 404 — not yet added).
- [ ] **Step 3: Implement** — add inside `build_earnings_update_v2_router` (near the other `/runs/{report_id}/...` handlers), importing `HTMLResponse`/`Response` and `render_svc = eu_v2_render_service`, `build_download_filename` from `eu_v2_filename`:

```python
    @router.get("/runs/{report_id}/html", response_class=HTMLResponse)
    def get_html(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> HTMLResponse:
        if not eu_v2_enabled():
            raise _engine_disabled()
        try:
            row = run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            rendered = eu_v2_render_service.render_html(db=db, user_id=user.id, report_id=report_id)
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = build_download_filename(row=row, ext="html")
        return HTMLResponse(
            content=rendered.html,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    @router.get("/runs/{report_id}/pdf")
    async def get_pdf(
        report_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        if not eu_v2_enabled():
            raise _engine_disabled()
        launcher = getattr(request.app.state, "browser_launcher", None)
        if launcher is None:
            raise HTTPException(
                status_code=503,
                detail="PDF rendering requires the BrowserLauncher on app.state. Use GET /html instead.",
            )
        try:
            row = run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            pdf_bytes = await eu_v2_render_service.render_pdf(
                db=db, user_id=user.id, report_id=report_id, browser_launcher=launcher
            )
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = build_download_filename(row=row, ext="pdf")
        return Response(
            content=pdf_bytes, media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    @router.get("/runs/{report_id}/docx")
    def get_docx(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        if not eu_v2_enabled():
            raise _engine_disabled()
        try:
            row = run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            docx_bytes = eu_v2_render_service.render_docx(db=db, user_id=user.id, report_id=report_id)
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = build_download_filename(row=row, ext="docx")
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
```

Add the imports at the top of the module: `from fastapi.responses import HTMLResponse` (if not present), `from fastapi import Response`, `from openlia_server.services import eu_v2_render_service`, `from openlia_server.services.eu_v2_filename import build_download_filename`. `run_svc` is the existing alias for `eu_v2_run_service`. Confirm the actual run-service alias name in this file and use it. Delete the stale "Render endpoints (html/pdf/docx) are intentionally NOT implemented" comment block.

- [ ] **Step 4: Run → PASS.** ruff clean.
- [ ] **Step 5: Commit**
```bash
git add packages/server/src/openlia_server/routes/departments/earnings_update_v2.py packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py
git commit -m "feat(eu): html/pdf/docx export endpoints"
```

---

## Task 6: Frontend download + standalone HTML

Wire `engine="eu"` downloads and re-add the download + standalone affordances to `ViewerHeader` for `eu_v2_report` (replacing the current "no button" stopgap).

**Files:**
- Modify: `frontend/src/api/reports.ts`
- Modify: `frontend/src/components/viewer/ViewerHeader.tsx`
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx` (pass an `eu` save-engine hint when opening — needed in Phase 2; here ensure the FileViewer open carries `reportId`)
- Test: `frontend/src/api/__tests__/reports.test.ts` (or co-located), `frontend/src/components/viewer/__tests__/ViewerHeader.test.tsx`

- [ ] **Step 1: Failing tests**
  - `reports.test.ts`: `downloadReportBlob` URL builder for `engine="eu"` hits `/api/departments/earnings-update/v2/runs/{id}/pdf` and `/docx`. (Mirror the existing v3 URL test; read `reports.ts` lines ~400-443 for how v3 is asserted.)
  - `ViewerHeader.test.tsx`: extend the existing file — for an `eu_v2_report` source, a download control AND a standalone-HTML link render (and Save-to-Repo when `reportId`/`saveEngine="eu"` provided). Mock `ReportDownloadButton`/`SaveToRepoButton`/`FileDownloadButton` as the existing test does.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**
  - `reports.ts`: add `"eu"` to `ReportEngine`; in `downloadReportBlob`, add `else if (engine === "eu")` building `/api/departments/earnings-update/v2/runs/${reportId}/pdf` and `/docx` (mirror the v3 branch). Export an `euHtmlUrl(reportId)` → `/api/departments/earnings-update/v2/runs/${reportId}/html`.
  - `ViewerHeader.tsx`: replace the `source.kind === "eu_v2_report" ? null` branch (added in the prior fix) with:
    ```tsx
    ) : source.kind === "eu_v2_report" ? (
      <>
        <ReportDownloadButton reportId={source.reportId} engine="eu" />
        <a
          href={euHtmlUrl(source.reportId)}
          target="_blank"
          rel="noopener noreferrer"
          className="..."  // mirror v3's "Standalone" link styling
        >
          Standalone
        </a>
      </>
    ) : (
    ```
    Import `euHtmlUrl` from `../../api/reports`. (Save-to-Repo for EU is added in Phase 2 Task 10.)
- [ ] **Step 4: Run → PASS.** `npx tsc --noEmit` clean.
- [ ] **Step 5: Commit**
```bash
git add frontend/src/api/reports.ts frontend/src/components/viewer/ViewerHeader.tsx frontend/src/api/__tests__/reports.test.ts frontend/src/components/viewer/__tests__/ViewerHeader.test.tsx
git commit -m "feat(eu): wire PDF/Word download + standalone HTML into the report viewer"
```

**Phase 1 gate:** `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py packages/server/tests/test_services -q` green; `npx vitest run src/components/viewer src/api` green; downloads work in the live app.

---

# PHASE 2 — SAVE-TO-REPO

## Task 7: `RepoItem.eu_v2_report_id` + migration

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/content.py`
- Create: `packages/server/src/openlia_server/db/migrations/versions/<rev>_repo_items_eu_target.py`
- Test: `packages/server/tests/test_db/test_migrations.py` (already covers EXPECTED_TABLES — same table, no new entry), and the migration-hygiene tests.

- [ ] **Step 1: Model change** — in `content.py`, `RepoItem`:
  - add column `eu_v2_report_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("report_eu.id", ondelete="CASCADE"), nullable=True)`;
  - add `UniqueConstraint("user_id", "eu_v2_report_id", name="uq_repo_items_user_eu_report")`;
  - replace the CHECK with the 4-way version:
    ```python
    CheckConstraint(
        "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
        "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
        "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END) + "
        "(CASE WHEN eu_v2_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
        name="ck_repo_items_exactly_one_target",
    ),
    ```
    Update the class docstring to list the 4th target.

- [ ] **Step 2: Generate the migration** — from `packages/server`: `uv run alembic -c alembic.ini revision -m "repo_items eu_v2 target"`. Then hand-edit the generated file so `upgrade()` uses a **batch** alter (SQLite rebuilds the table to change the CHECK):
    ```python
    def upgrade() -> None:
        with op.batch_alter_table("repo_items", schema=None) as batch_op:
            batch_op.add_column(sa.Column("eu_v2_report_id", sa.String(length=36), nullable=True))
            batch_op.create_foreign_key(
                "fk_repo_items_eu_v2_report_id", "report_eu", ["eu_v2_report_id"], ["id"],
                ondelete="CASCADE",
            )
            batch_op.create_unique_constraint(
                "uq_repo_items_user_eu_report", ["user_id", "eu_v2_report_id"]
            )
            batch_op.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
            batch_op.create_check_constraint(
                "ck_repo_items_exactly_one_target",
                "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
                "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
                "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END) + "
                "(CASE WHEN eu_v2_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
            )
    def downgrade() -> None:
        with op.batch_alter_table("repo_items", schema=None) as batch_op:
            batch_op.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
            batch_op.drop_constraint("uq_repo_items_user_eu_report", type_="unique")
            batch_op.drop_constraint("fk_repo_items_eu_v2_report_id", type_="foreignkey")
            batch_op.drop_column("eu_v2_report_id")
            batch_op.create_check_constraint(
                "ck_repo_items_exactly_one_target",
                "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
                "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
                "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
            )
    ```
  Double-quote the revision identifiers (the home-grown head parser in `test_app_migration_on_start.py` matches double-quoted ids only). Use `from __future__ import annotations` and only the imports actually used.

- [ ] **Step 3: Run the migration-suite gate**
    ```
    uv run pytest \
      packages/server/tests/test_db/test_alembic_hygiene.py::test_alembic_autogenerate_is_clean \
      packages/server/tests/test_db/test_migrations.py::test_baseline_upgrade_creates_all_tables \
      packages/server/tests/test_app_migration_on_start.py::test_bootstrap_runs_alembic_upgrade_to_head -q
    ```
  Expected: PASS. If autogenerate is dirty, align the model's column/constraint definitions with the migration until clean (server_default, FK name, etc.). `EXPECTED_TABLES` needs no change (same table).

- [ ] **Step 4: Commit**
```bash
git add packages/server/src/openlia_server/db/models/content.py packages/server/src/openlia_server/db/migrations/versions/
git commit -m "feat(eu): add eu_v2_report_id repo target (model + migration)"
```

---

## Task 8: repo service — EU save/unsave/is-saved + listing

Mirror `save_v3_report_to_repo` / `unsave_v3_report_from_repo` / `is_v3_report_saved` and the v3 list fanout for EU.

**Files:**
- Modify: `packages/server/src/openlia_server/services/repo.py`
- Test: `packages/server/tests/test_services/test_repo.py` (mirror the existing v3 repo-service tests)

- [ ] **Step 1: Failing tests** — mirror the v3 repo-service tests in `test_repo.py`: save an EU report (idempotent), `is_eu_report_saved` true after, unsave removes it, and a saved EU report appears in the repo listing the Repo page consumes. (Read the existing v3 repo tests + `list_items_filtered` to match the exact listing assertion.)
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add after the v3 block in `repo.py` (mirror exactly, swapping `v3_report_id`→`eu_v2_report_id`, `ReportV3`→`ReportEu`):

```python
def save_eu_report_to_repo(db: Session, *, user_id: str, eu_report_id: str) -> RepoItem:
    existing = db.execute(
        select(RepoItem).where(
            RepoItem.user_id == user_id, RepoItem.eu_v2_report_id == eu_report_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    report = db.get(ReportEu, eu_report_id)
    if report is None or report.user_id != user_id:
        raise LookupError(f"EU report {eu_report_id} not found")
    item = RepoItem(
        id=str(uuid.uuid4()), user_id=user_id,
        report_id=None, pipeline_run_id=None, v3_report_id=None,
        eu_v2_report_id=eu_report_id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.execute(
            select(RepoItem).where(
                RepoItem.user_id == user_id, RepoItem.eu_v2_report_id == eu_report_id
            )
        ).scalar_one()
    db.refresh(item)
    return item


def unsave_eu_report_from_repo(db: Session, *, user_id: str, eu_report_id: str) -> None:
    db.query(RepoItem).filter(
        RepoItem.user_id == user_id, RepoItem.eu_v2_report_id == eu_report_id
    ).delete()
    db.commit()


def is_eu_report_saved(db: Session, *, user_id: str, eu_report_id: str) -> bool:
    return db.execute(
        select(RepoItem.id).where(
            RepoItem.user_id == user_id, RepoItem.eu_v2_report_id == eu_report_id
        )
    ).first() is not None
```

Import `ReportEu` at the top of `repo.py`. Then extend the **listing** that the Repo page consumes (`list_items_filtered` or its fanout) to include EU rows: read how v3 rows are turned into list items (subject, date, department, an open target carrying `engine`/source kind + report id) and add an EU branch (`_list_eu_rows`) that emits items tagged so the frontend opens them as `eu_v2_report`. Use `eu_v2_filename.build_download_filename` for the displayed name; department label `"earnings_update"`.

- [ ] **Step 4: Run → PASS.** ruff clean.
- [ ] **Step 5: Commit**
```bash
git add packages/server/src/openlia_server/services/repo.py packages/server/tests/test_services/test_repo.py
git commit -m "feat(eu): repo save/unsave/list support"
```

---

## Task 9: repo routes — `/eu-runs`

Mirror the `/v3-runs` routes.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/repo.py`
- Test: `packages/server/tests/test_routes/test_repo_routes.py` (mirror the v3 route tests)

- [ ] **Step 1: Failing test** — `POST /api/repo/eu-runs {eu_v2_report_id}` → 201; `GET /api/repo/eu-runs` lists it; `DELETE /api/repo/eu-runs?eu_v2_report_id=...` → 204; 404 for an unknown report. (Read the v3 route tests + the `RepoSaveV3In`/`RepoV3SavedListOut` payload models and mirror them as `RepoSaveEuIn`/`RepoEuSavedListOut`.)
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add a `RepoSaveEuIn(BaseModel): eu_v2_report_id: str` payload + `RepoEuSavedListOut(BaseModel): saved_run_ids: list[str]`, and three endpoints mirroring `save_v3_ep`/`unsave_v3_ep`/`list_v3_saved_ep`, calling the Task 8 service functions, with the `LookupError → 404 {code:"eu_report_not_found"}` mapping. `GET /eu-runs` returns the ids from `list_items` where `eu_v2_report_id is not None`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit**
```bash
git add packages/server/src/openlia_server/routes/repo.py packages/server/tests/test_routes/test_repo_routes.py
git commit -m "feat(eu): repo save/unsave/list endpoints (/eu-runs)"
```

---

## Task 10: Frontend save-to-repo

**Files:**
- Modify: `frontend/src/api/repo.ts`, `frontend/src/components/chat/SaveToRepoButton.tsx`, `frontend/src/components/viewer/ViewerHeader.tsx`, `frontend/src/pages/departments/EarningsUpdate.tsx`
- Test: `frontend/src/components/chat/__tests__/SaveToRepoButton.test.tsx`, `ViewerHeader.test.tsx`

- [ ] **Step 1: Failing tests** — `SaveToRepoButton` with `engine="eu"` calls `saveEuRunToRepo(reportId)` (POST `/api/repo/eu-runs`); `ViewerHeader` for an `eu_v2_report` source with `reportId` + `saveEngine="eu"` renders the Save-to-Repo button. (Mirror the existing v3 SaveToRepoButton test.)
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**
  - `api/repo.ts`: add `"eu"` to the engine type; `saveEuRunToRepo(reportId)` → `POST /api/repo/eu-runs {eu_v2_report_id}`; `unsaveEuRunFromRepo`; `listSavedEuRuns` → `GET /api/repo/eu-runs` (mirror the v3 functions).
  - `SaveToRepoButton.tsx`: add `"eu"` to `SaveToRepoEngine`; in the save/unsave handlers, branch `engine === "eu"` to the new repo functions (mirror the v3 branch incl. the `initialSaved`/saved-state handling).
  - `ViewerHeader.tsx`: widen `saveEngine` prop type to include `"eu"`; the `eu_v2_report` branch (from Task 6) now also relies on the shared Save-to-Repo block at the top — ensure the EU open path passes `reportId` + `saveEngine="eu"` so it renders.
  - `EarningsUpdate.tsx` `openReport`: pass the FileViewer `reportId` + a `saveEngine: "eu"` hint (match how the viewer derives `saveEngine` from the source; if it's derived from `source.kind`, map `eu_v2_report → "eu"` in the viewer rather than the page).
- [ ] **Step 4: Run → PASS.** tsc clean.
- [ ] **Step 5: Commit**
```bash
git add frontend/src/api/repo.ts frontend/src/components/chat/SaveToRepoButton.tsx frontend/src/components/viewer/ViewerHeader.tsx frontend/src/pages/departments/EarningsUpdate.tsx frontend/src/components/chat/__tests__/SaveToRepoButton.test.tsx frontend/src/components/viewer/__tests__/ViewerHeader.test.tsx
git commit -m "feat(eu): Save-to-Repo button on EU reports"
```

---

## Task 11: Repo page — open a saved EU report

**Files:**
- Modify: the Repo page open handler + its API (find via `grep -rn "v3_report" frontend/src/pages` and the repo list rendering)
- Test: the Repo page test (mirror its v3 open test)

- [ ] **Step 1: Read** how the Repo page lists saved items and opens a v3 one (it sets a FileViewer source `{ kind: "v3_report", reportId }`). Find the list item's engine/kind field.
- [ ] **Step 2: Failing test** — clicking a saved EU item opens the FileViewer with `{ kind: "eu_v2_report", reportId }` (mirror the v3 open test).
- [ ] **Step 3: Run → FAIL.**
- [ ] **Step 4: Implement** — in the repo list → open mapping, add an EU branch: when the item is an EU report (engine/source tag from Task 8's listing), open `{ kind: "eu_v2_report", reportId }`. Ensure the repo list fetch includes EU items (the Task 8 listing already merges them).
- [ ] **Step 5: Run → PASS.** tsc clean.
- [ ] **Step 6: Commit**
```bash
git add frontend/src/pages frontend/src/api
git commit -m "feat(eu): open saved EU reports from the Repository page"
```

---

## Task 12: Integration verification

**Files:** none.

- [ ] **Step 1: Full backend suite** — `uv run pytest packages/core packages/server -q`. Expected: no new failures (the pre-existing date-dependent `test_portfolio_value_series_route` failure is unrelated — confirm the count isn't higher).
- [ ] **Step 2: Full frontend suite** — from `frontend/`, `npx vitest run`. Expected: no new failures (the pre-existing `SettingsShellBlocker` AbortSignal flakiness is unrelated).
- [ ] **Step 3: Build + lint** — `npm run build` succeeds; `uv run ruff check packages/server/src/openlia_server` clean.
- [ ] **Step 4: Live smoke** — with the server on `EARNINGS_ENGINE_VERSION=v2` + a completed EU report: `GET /api/departments/earnings-update/v2/runs/{id}/pdf` returns a non-empty `%PDF`; `/docx` returns a `PK` zip; `/html` returns HTML; `POST /api/repo/eu-runs` then the Repo page shows + opens the report. In the UI: open a report → Download (PDF/Word), Standalone, and Save-to-Repo all work; the saved report opens from the Repository page.
- [ ] **Step 5: Final commit** if manual-pass fixes were needed.

---

## Self-Review Notes

- **Spec coverage:** export render service → Tasks 1–4; endpoints → Task 5; frontend download + standalone → Task 6; RepoItem migration → Task 7; repo service → Task 8; repo routes → Task 9; frontend save → Task 10; repo open routing → Task 11; tests/verification throughout + Task 12.
- **Fork fidelity:** Tasks 2/3/4 are verbatim forks of `v3_filename`/`v3_docx`/`v3_render_service` with `ReportV3*`→`ReportEu*` + `report_v3.rendering`→`report_eu.rendering` substitutions and the EU run-service loader — the source files are named explicitly for the implementer to copy.
- **Type consistency:** `run_svc.get_run` returns `(row, sections, charts, citations)` (Task 1) consumed identically by Task 4; `eu_v2_report_id` column (Task 7) is the key used by Tasks 8/9; frontend `engine="eu"` (Task 6) and the `eu_v2_report` source kind thread through Tasks 6/10/11.
- **Migration risk:** Task 7 uses batch-alter for the SQLite CHECK rewrite and gates on the three migration-suite tests (the same ones that broke during the EU-redesign merge — kept green here).
- **Phasing:** Phase 1 (1–6) ships download independently of Phase 2 (7–11) save-to-repo.
- **Pieces requiring the implementer to read a v3 source before mirroring** (named in each task): `v3_docx.py`, the repo list fanout in `repo.py`, the v3 repo route payload models, the frontend `reports.ts`/`repo.ts`/`SaveToRepoButton` v3 branches, and the Repo page's v3 open handler. Each task specifies the exact EU endpoints/types/names to produce.
