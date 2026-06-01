# Earnings Update v2 — Report Download + Save-to-Repo (v3 parity)

**Date:** 2026-06-01
**Status:** Approved design, pre-implementation
**Base branch:** `feat/eu-report-export-and-repo` (off `main`).
**Scope:** Backend (render services + export endpoints + repo save) + a DB migration + frontend wiring. Mirrors equity-research v3.

## Problem

Equity-research v3 reports offer Download (PDF/Word), a standalone HTML view, and
Save-to-Repo. Earnings Update v2 reports offer none of these — the EU v2 route
shipped with render endpoints "intentionally NOT implemented" and no repo-save
path. (A prior fix removed the non-functional download buttons that pointed at the
wrong v1 endpoint.) Users want EU reports to behave exactly like equity-research
reports: download PDF/Word, open standalone HTML, and save to the repository.

The core document renderer (`report_eu/rendering/assemble_html`) already exists —
forked from v3 and engine-agnostic (it consumes ORM rows by attribute). Only the
server-side *wrappers* (render service, docx builder, filename builder) and the
endpoints/repo plumbing are missing. The route comment claiming the renderer
"cannot be reused" is outdated.

## Goals

- EU v2 reports: Download **PDF** and **Word**, open **standalone HTML**, and
  **Save-to-Repo** — full v3 parity.
- Saved EU reports appear in the Repo page and **open into the EU report viewer**.
- Reuse the existing generic core renderer; do not refactor working v3 code.
- Keep the migration suite green (model↔migration squared, autogenerate clean).

## Non-goals

- No change to the v3 render/docx/repo services (approach A = fork, not generalize).
- No new report content/fields; render the existing `report_eu` sections/charts/citations.
- No bulk/zip export, no scheduled-email delivery.

## Decisions (from brainstorming)

| Topic | Decision |
| --- | --- |
| Approach | **A** — fork the v3 service wrappers into `eu_v2_*`; extend the polymorphic `RepoItem` for save-to-repo. |
| Formats | Full parity: PDF + Word download, standalone HTML, Save-to-Repo. |
| Repo open routing | In scope — saved EU items list in the Repo page and open into `EUV2ReportRenderer`. |

## Architecture

The core renderer is shared and generic; everything new is a thin EU wrapper that
mirrors the v3 equivalent, plus one polymorphic extension to `RepoItem`.

### 1. Backend — export (PDF / Word / HTML)

- **Reuse** `openlia.llm.runtime.report_eu.rendering.assemble_html(report, sections,
  charts, citations)` (already present, attribute-based, engine-agnostic).
- **New `services/eu_v2_render_service.py`** (mirror `v3_render_service.py`):
  - `render_html(db, user_id, report_id) -> str` — load the `ReportEu` row +
    `ReportEuSection`/`ReportEuChart`/`ReportEuCitation`, call `assemble_html`, return HTML.
  - `render_pdf(db, user_id, report_id) -> bytes` — render HTML, Playwright `page.pdf()`
    (same mechanism as v3).
  - `render_docx(db, user_id, report_id) -> bytes` — delegate to `eu_v2_docx`.
  - Loads via the existing EU run-detail accessor (the same query `GET /runs/{id}` uses).
- **New `services/eu_v2_docx.py`** — fork of `v3_docx.py` with `ReportEu*` types
  (identical logic: sections + embedded charts + bibliography → python-docx bytes).
- **New `services/eu_v2_filename.py`** — fork of `v3_filename.py`; pattern
  `Ticker_Template_Date.ext` (slugified subject/ticker + template label + completed/created date).
- **New endpoints on `routes/departments/earnings_update_v2.py`** (mirror v3 lines for html/pdf/docx):
  - `GET /runs/{report_id}/html` → `HTMLResponse` + `Content-Disposition`.
  - `GET /runs/{report_id}/pdf` → `application/pdf` + filename header.
  - `GET /runs/{report_id}/docx` → docx mime + filename header.
  - All: require auth, 404 if the report isn't found / not owned, gated by `eu_v2_enabled()`.
  - Remove the stale "Render endpoints … intentionally NOT implemented" comment.

### 2. Backend — save-to-repo

- **`RepoItem` model** (`db/models/content.py`): add nullable `eu_v2_report_id`
  FK → `report_eu.id` (ondelete CASCADE), a unique constraint
  `uq_repo_items_user_eu_report (user_id, eu_v2_report_id)`, and update the
  polymorphic CHECK so **exactly one** of `report_id` / `pipeline_run_id` /
  `v3_report_id` / `eu_v2_report_id` is set.
- **Alembic migration**: add the column + constraints; chain off the current head;
  keep the model and migration aligned so `test_alembic_autogenerate_is_clean`,
  `test_baseline_upgrade_creates_all_tables`, and `test_bootstrap_runs_alembic_upgrade_to_head`
  stay green (`EXPECTED_TABLES` unchanged — same table).
- **`services/repo.py`**: `save_eu_report_to_repo(db, user_id, eu_report_id)` (idempotent;
  validates ownership of the `ReportEu` row), `unsave_eu_report_from_repo`,
  `is_eu_report_saved`; add an EU fanout (`_list_eu_rows`) to `list_items_filtered`
  so saved EU items appear in the repo listing with enough metadata to open them.
- **`routes/repo.py`**: `POST /eu-runs` (`{eu_v2_report_id}`), `DELETE /eu-runs`,
  `GET /eu-runs` — mirror the `/v3-runs` routes.

### 3. Frontend

- **`api/reports.ts`**: add `"eu"` to `ReportEngine`; `downloadReportBlob` branch →
  `/api/departments/earnings-update/v2/runs/{id}/pdf|docx`. EU HTML url helper
  (`/runs/{id}/html`) for the standalone link.
- **`api/repo.ts`**: add `"eu"` engine; `saveEuRunToRepo` / `unsaveEuRunFromRepo` /
  `listSavedEuRuns` (mirror the v3 repo functions).
- **`SaveToRepoButton`** (`components/chat/SaveToRepoButton.tsx`): add `"eu"` to
  `SaveToRepoEngine`; on `eu`, call the EU repo functions.
- **`ViewerHeader`**: for `source.kind === "eu_v2_report"`, render
  `ReportDownloadButton engine="eu"` + a standalone-HTML link (EU html url), and
  pass `reportId` + `saveEngine="eu"` so the Save-to-Repo button shows — replacing
  the current "no button" stopgap. The `saveEngine` prop type widens to include `"eu"`.
- **EU report open path** (`EarningsUpdate.tsx` `openReport` / FileViewer open): pass
  the `reportId` + an `eu` save-engine hint so `ViewerHeader` renders the affordances.
- **Repo page**: the saved-items list includes EU reports; selecting one opens the
  FileViewer with an `eu_v2_report` source (→ `EUV2ReportRenderer`). The repo list
  item must carry the engine/source kind so the open handler routes correctly.

## Files

| File | Change |
| --- | --- |
| `packages/server/src/openlia_server/services/eu_v2_render_service.py` | New. html/pdf/docx render (reuses core `assemble_html`). |
| `packages/server/src/openlia_server/services/eu_v2_docx.py` | New. Fork of `v3_docx.py` with `ReportEu*` types. |
| `packages/server/src/openlia_server/services/eu_v2_filename.py` | New. Fork of `v3_filename.py`. |
| `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py` | Add html/pdf/docx endpoints; drop the stale comment. |
| `packages/server/src/openlia_server/db/models/content.py` | `RepoItem.eu_v2_report_id` + unique + CHECK update. |
| `packages/server/src/openlia_server/db/migrations/versions/*` | New migration for the column/constraints. |
| `packages/server/src/openlia_server/services/repo.py` | EU save/unsave/is-saved + list fanout. |
| `packages/server/src/openlia_server/routes/repo.py` | `POST/DELETE/GET /eu-runs`. |
| `frontend/src/api/reports.ts` | `"eu"` engine + download URLs + html url. |
| `frontend/src/api/repo.ts` | `"eu"` engine + save/unsave/list functions. |
| `frontend/src/components/chat/SaveToRepoButton.tsx` | `"eu"` engine. |
| `frontend/src/components/viewer/ViewerHeader.tsx` | EU branch: download + save + standalone HTML. |
| `frontend/src/pages/departments/EarningsUpdate.tsx` | Pass reportId + eu save-engine when opening a report. |
| Repo page + viewer open routing | Saved EU item → `eu_v2_report` FileViewer source. |

## Testing

- **Render service** (server): `render_html` returns HTML containing a section title;
  `render_docx` returns non-empty docx bytes (zip magic); `render_pdf` returns
  non-empty `%PDF` bytes (or mock Playwright). Mirror the v3 render-service tests.
- **Endpoints**: each of html/pdf/docx returns 200 + correct content-type +
  `Content-Disposition` filename; 404 for a missing/foreign report; 503 when the
  engine flag is off; auth required.
- **Repo**: `save_eu_report_to_repo` idempotent + ownership-checked; appears in
  `list_items_filtered`; unsave removes it; the `/eu-runs` routes round-trip.
- **Migration**: `test_alembic_autogenerate_is_clean`, `test_baseline_upgrade_creates_all_tables`,
  `test_bootstrap_runs_alembic_upgrade_to_head` all pass with the new column.
- **Frontend**: `downloadReportBlob(id, fmt, "eu")` hits the EU URLs; `SaveToRepoButton`
  with `engine="eu"` calls `saveEuRunToRepo`; `ViewerHeader` renders download + save +
  standalone for an `eu_v2_report` source; the repo open handler routes an EU item to
  an `eu_v2_report` viewer source.

## Risks / open points

- **Playwright PDF**: EU PDF reuses the same Playwright path as v3 — confirm the
  render service shares the v3 browser-launcher/`render_base_url_resolver` on
  `app.state`, and reuse it rather than standing up a second.
- **RepoItem CHECK migration**: the existing CHECK enforces exactly-one of the three
  current columns; the migration must rewrite it to four-way without invalidating
  existing rows. On SQLite this means a batch table rebuild — verify the migration's
  batch-alter recreates the CHECK correctly and the migration tests stay green.
- **Repo list metadata**: opening a saved EU item needs the list row to expose its
  engine/source kind + report id; confirm the existing repo-list item shape can carry
  it (mirror how v3 items are opened from the repo today).
