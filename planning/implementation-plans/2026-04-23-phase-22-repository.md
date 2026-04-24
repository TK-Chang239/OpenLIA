# Repository Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Audit 2026-04-23 normalizations (apply before executing this plan):**
> - `repo_items` table was shipped by **Plan 12 Task 0** with columns `id String(36)`, `user_id String(36)`, `report_id String(36)`, `created_at UTCDateTime`. No `tags`, `archived_at`, `title`, or `note` columns exist. Plan 22 does **not** add any — the spec does not require them.
> - All IDs are UUID strings (`String(36)`). `RepoItem.id`, `Report.id`, `user_id` are generated with `str(uuid.uuid4())`.
> - Backend imports use the contracted paths: `from openlia_server.db.models.content import RepoItem, Report`, `from openlia_server.db.models.auth import User`, `from openlia_server.middleware.auth import build_require_auth`, `from openlia_server.db.deps import make_session_dependency`.
> - Backend HTTP prefix is **bare** (`/repo/...`, `/reports/...`). The Vite dev proxy strips `/api`. Frontend hits `/api/repo/...`; backend `TestClient` tests hit `/repo/...`.
> - `build_repo_router(*, db_session_factory, mode)` already exists — Plan 22 **extends** the existing router; it does not create a new one. New endpoints are additive.
> - Reports route surface owned by Plan 13 (`GET /reports`, `GET /reports/{id}`, `DELETE /reports/{id}`, `POST /reports/{id}/export/pdf`) is **not** changed by Plan 22. The Repo page proxies detail/download through the existing `/reports/{id}` + `/reports/{id}/export/pdf` endpoints, same as department pages.
> - Frontend `/api` proxy and session cookies already work. Use `fetchJson` from `frontend/src/api/client.ts`.
> - `FileViewerContext` + `FileViewer` component ship in Plan 12 and already support `FileSource = { kind: "report"; reportId: string }` — the Repository page reuses them unmodified.
> - **Spec fidelity:** the spec does NOT require tags, archiving, bulk select, item-metadata edits, notes, or soft delete. The original Plan 22 scope brief mentioned these, but the `RepositoryPageSpec.md` supersedes the brief. This plan implements the spec verbatim: filename search, department filter, date-generated range, date-saved range, sort dropdown, infinite scroll (50/page), FileViewer open, download, remove-with-confirmation + undo toast. If tags/archive are later desired, a follow-up plan adds columns, endpoints, and UI in one slice.
> - Filter fields on the `GET /repo/items` query string are contract-locked in this plan: `q` (filename substring), `department` (repeatable, CSV also accepted), `generated_from`, `generated_to`, `saved_from`, `saved_to` (ISO-8601 date, inclusive), `sort` (`saved_desc|saved_asc|generated_desc|generated_asc|department_asc|filename_asc`), `page` (int, 1-indexed, default 1), `page_size` (int, default 50, max 200).

**Goal:** Ship the Repository page so users can browse every report they have saved to the Repo, search by filename, filter by department and date ranges, sort by multiple keys, open a report in the FileViewer, download the PDF, and remove a report from the Repo with a confirmation dialog and undo toast. Infinite-scroll pagination loads 50 rows at a time.

**Architecture:**
- **Server** extends the existing `/repo` router with:
  - `GET /repo/items` — gains query params `q`, `department`, `generated_from`, `generated_to`, `saved_from`, `saved_to`, `sort`, `page`, `page_size`. Returns a richer row shape joining `repo_items` to `reports` so the client does not need a second round-trip per row.
  - `GET /repo/facets` — returns the distinct departments actually present in the user's Repo plus total count (feeds the department multi-select in the Filters dropdown without a client-side scan).
- **Service** (`services/repo.py`) gains `list_items_filtered(...)` with paginated SQLAlchemy SQL, plus `facets(...)` returning `{departments: [{slug, count}], total: int}`.
- **Contract docs** (`endpoint-contract-matrix.md`, `route-authorization-matrix.md`) add the new rows.
- **Frontend** builds:
  - `frontend/src/pages/Repository.tsx` — replaces the placeholder; composes the page header, controls bar, active chips, sort dropdown, list, FileViewer pane, and remove dialog.
  - `frontend/src/components/repo/RepoFilterBar.tsx` — search input + filters button + filters dropdown + sort trigger/menu.
  - `frontend/src/components/repo/RepoFilterChips.tsx` — dismissible active-filter chips + "Clear all".
  - `frontend/src/components/repo/RepoListItem.tsx` — single list row with file icon, filename, department badge, dates, download + remove buttons.
  - `frontend/src/components/repo/RepoListSkeleton.tsx` — 8 skeleton rows.
  - `frontend/src/components/repo/RepoEmptyState.tsx` — no-reports empty state AND no-match empty state.
  - `frontend/src/components/repo/RemoveConfirmDialog.tsx` — `<dialog>`-like Radix modal.
  - `frontend/src/components/repo/UndoToast.tsx` — minimal toast with "Undo" link (4s).
  - `frontend/src/hooks/useRepoList.ts` — query-state + infinite fetch + cache updates.
  - `frontend/src/api/repo.ts` — expanded client.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2.
- Frontend: React 18 + TypeScript strict, Framer Motion for row fade/toast, Radix UI `Dialog` + `Popover` + `DropdownMenu`, Vitest + React Testing Library, `lucide-react` icons.

**Dependencies:**
- Plan 8 (frontend shell, auth context, `/api` proxy, design tokens).
- Plan 12 (the `repo_items` table, `FileViewerContext`, `FileViewer`, `FileDownloadButton`, base `/repo/items` save/unsave routes, `frontend/src/api/repo.ts` stub).
- Plan 13 (the `reports` table row `RepoItem.report_id` references, `GET /reports/{id}`, `POST /reports/{id}/export/pdf`, `reportPdfUrl` client helper).

**Unblocks:** closes the MVP loop for report-generating departments. No other plan depends on Plan 22; it is the last user-facing ancillary page before packaging (Plan 23).

---

## Design Rules

1. **Filename comes from `Report.title`.** The spec uses "filename" because downloaded PDFs end `.pdf`, but the persisted source of truth is `Report.title`. The server appends `.pdf` when it serializes the row to the wire shape (`filename = f"{title}.pdf"`). Download uses the existing `GET /reports/{id}/export/pdf` endpoint which already names the file `report-<id>.pdf` — that filename differs from the UI label, which is acceptable (UI label is informational; Content-Disposition on the export response is authoritative on disk).
2. **`generated_at` is `Report.created_at`.** There is no separate generated_at column. The wire shape exposes `generated_at: Report.created_at.isoformat()`.
3. **`saved_at` is `RepoItem.created_at`.** Also exposed in ISO-8601.
4. **Removal uses the existing `DELETE /repo/items?report_id=<id>`.** No new endpoint; the confirmation dialog is a pure frontend concern. Undo = re-POST `/repo/items` with the same `report_id` (the server is idempotent on double-save).
5. **Infinite scroll loads 50/page.** `page_size=50` is the default. The frontend tracks a `hasMore` flag (= whether the last response filled the page) and shows either the three-dot loading indicator or the "All reports loaded" footer.
6. **Filter state lives in the URL.** `?q=...&department=...&generated_from=...&sort=...&page=...` — so bookmarks/back-button work. Implemented via `useSearchParams` from `react-router-dom`.
7. **Department multi-select is union (OR).** Date ranges are intersection (AND). `q` is a case-insensitive substring match on `Report.title`. Empty filters match all.
8. **Owner scoping is absolute.** Every query filters on `RepoItem.user_id == user.id`. Admins do NOT get cross-user visibility (matches `route-authorization-matrix.md`).
9. **Removed rows fade out over 200ms, then the toast slides in.** The undo window is 4 seconds. Clicking "Undo" before the toast dismisses re-saves; after dismiss, undo is a no-op (the toast is gone).
10. **All IDs are UUID-36.** No short-prefixed IDs.
11. **TDD everywhere.** Failing test → implementation → green run → commit per step.
12. **No placeholders.** Real code, real commands, real expected output in every step.
13. **Length/Style/Emojis.** No emojis anywhere in code, tests, or copy. English only. No filler.

---

## File Structure

### Server (`packages/server/src/openlia_server/`)

```
routes/
└── repo.py                            # MODIFY — extend with filter/sort/pagination + /facets
services/
└── repo.py                            # MODIFY — add list_items_filtered + facets helpers
```

### Server tests (`packages/server/tests/`)

```
test_services/
└── test_repo_filtered.py              # NEW — list_items_filtered + facets unit tests
test_routes/
└── test_repo_filter_routes.py         # NEW — extended GET /repo/items + /repo/facets HTTP tests
```

### Frontend (`frontend/src/`)

```
pages/
└── Repository.tsx                     # REWRITE — real page composition
components/repo/
├── RepoFilterBar.tsx                  # NEW
├── RepoFilterChips.tsx                # NEW
├── RepoListItem.tsx                   # NEW
├── RepoListSkeleton.tsx               # NEW
├── RepoEmptyState.tsx                 # NEW
├── RemoveConfirmDialog.tsx            # NEW
├── UndoToast.tsx                      # NEW
└── __tests__/
    ├── RepoFilterBar.test.tsx
    ├── RepoFilterChips.test.tsx
    ├── RepoListItem.test.tsx
    ├── RemoveConfirmDialog.test.tsx
    └── UndoToast.test.tsx
hooks/
└── useRepoList.ts                     # NEW
api/
└── repo.ts                            # MODIFY — expand client to cover filters + facets + detail
pages/__tests__/
└── Repository.test.tsx                # NEW — page-level integration test
```

---

## Dependency Graph (intra-plan)

```
Task 0 (dep gate — verify Plan 12 surface)
  |
  +-- Task 1 (service unit tests for list_items_filtered + facets)       [server]
  |     |
  |     +-- Task 2 (service impl)
  |           |
  |           +-- Task 3 (route tests: GET /repo/items filters)
  |           |     |
  |           |     +-- Task 4 (route impl: extend GET /repo/items)
  |           |
  |           +-- Task 5 (route tests: GET /repo/facets)
  |                 |
  |                 +-- Task 6 (route impl: GET /repo/facets)
  |
  +-- Task 7 (contract-matrix + auth-matrix updates)
  |
  +-- Task 8 (frontend api client expansion + tests)
  |     |
  |     +-- Task 9 (useRepoList hook + tests)
  |           |
  |           +-- Task 10 (RepoFilterBar + tests)
  |           +-- Task 11 (RepoFilterChips + tests)
  |           +-- Task 12 (RepoListItem + tests)
  |           +-- Task 13 (RepoListSkeleton + RepoEmptyState + tests)
  |           +-- Task 14 (RemoveConfirmDialog + tests)
  |           +-- Task 15 (UndoToast + tests)
  |                 |
  |                 +-- Task 16 (Repository page composition + tests)
  |                       |
  |                       +-- Task 17 (route registration + sidebar link verification)
  |                             |
  |                             +-- Task 18 (full aggregate suite + ruff + PR)
```

Tasks 10-15 are mutually independent — run in parallel via `superpowers:subagent-driven-development` if desired.

---

## Tasks

### Task 0 — Dependency gate: verify Plan 12 surface

- [ ] **0.1 — Verify `RepoItem` model exists as contracted**

  Run:
  ```bash
  uv run python -c "from openlia_server.db.models.content import RepoItem; print(RepoItem.__tablename__, [c.name for c in RepoItem.__table__.columns])"
  ```
  Expected stdout (exact):
  ```
  repo_items ['id', 'user_id', 'report_id', 'created_at']
  ```

  If stdout differs, **stop** — Plan 12 Task 0 did not ship as documented; escalate before proceeding.

- [ ] **0.2 — Verify existing `/repo` router is mounted**

  Run:
  ```bash
  uv run python -c "from openlia_server.routes.repo import build_repo_router; print(build_repo_router.__module__)"
  ```
  Expected stdout:
  ```
  openlia_server.routes.repo
  ```

- [ ] **0.3 — Confirm `FileViewerContext` exports `FileSource = {kind: 'report', reportId}`**

  Run:
  ```bash
  grep -n "reportId" frontend/src/components/viewer/FileViewerContext.tsx
  ```
  Expected: at least one match on `{ kind: "report"; reportId: string }`.

- [ ] **0.4 — Verify `reportPdfUrl` helper exists**

  Run:
  ```bash
  grep -n "reportPdfUrl" frontend/src/api/reports.ts
  ```
  Expected: match on `export function reportPdfUrl(reportId: string): string`.

- [ ] **0.5 — Baseline test run is green**

  Run:
  ```bash
  uv run ruff check . && uv run ruff format --check . && uv run pytest -q
  ```
  Expected: all green. If not, pull `main` fresh and re-run.

- [ ] **0.6 — Commit (no-op bookkeeping)**

  Nothing to commit yet; Task 0 is a gate. Move to Task 1.

---

### Task 1 — Service unit tests: `list_items_filtered` + `facets`

- [ ] **1.1 — Write `packages/server/tests/test_services/test_repo_filtered.py`**

  Create file with the exact content below:
  ```python
  """Unit tests for repo filter/sort/pagination + facets helpers."""

  from __future__ import annotations

  import uuid
  from datetime import datetime, timedelta, timezone

  import pytest

  from openlia_server.db.models.auth import User
  from openlia_server.db.models.content import RepoItem, Report
  from openlia_server.services import repo as svc


  def _mk_user(db) -> User:
      u = User(
          id=str(uuid.uuid4()),
          email=f"u-{uuid.uuid4().hex[:8]}@example.com",
          display_name="U",
          password_hash="x",
          is_admin=False,
      )
      db.add(u)
      db.flush()
      return u


  def _mk_report(db, *, user_id: str, department: str, title: str, created_at: datetime) -> Report:
      r = Report(
          id=str(uuid.uuid4()),
          user_id=user_id,
          department=department,
          report_type=f"{department}_report",
          title=title,
          subject=None,
          content_markdown="md",
          content_structured={"title": title, "sections": []},
          model_ref="test-model",
      )
      db.add(r)
      db.flush()
      # Force created_at (TimestampMixin uses server_default; override for determinism).
      r.created_at = created_at
      db.flush()
      return r


  def _save(db, *, user_id: str, report_id: str, saved_at: datetime) -> RepoItem:
      item = RepoItem(
          id=str(uuid.uuid4()), user_id=user_id, report_id=report_id, created_at=saved_at
      )
      db.add(item)
      db.flush()
      return item


  @pytest.fixture()
  def seeded(db_session):
      u = _mk_user(db_session)
      now = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
      reports = [
          _mk_report(
              db_session,
              user_id=u.id,
              department="equity_research",
              title="AAPL-initiation-coverage",
              created_at=now - timedelta(days=7),
          ),
          _mk_report(
              db_session,
              user_id=u.id,
              department="earnings_update",
              title="AAPL-earnings-q1-2026",
              created_at=now - timedelta(days=5),
          ),
          _mk_report(
              db_session,
              user_id=u.id,
              department="secretary",
              title="briefing-notes",
              created_at=now - timedelta(days=3),
          ),
          _mk_report(
              db_session,
              user_id=u.id,
              department="equity_research",
              title="MSFT-update",
              created_at=now - timedelta(days=1),
          ),
      ]
      saves = [
          _save(db_session, user_id=u.id, report_id=reports[0].id, saved_at=now - timedelta(days=6)),
          _save(db_session, user_id=u.id, report_id=reports[1].id, saved_at=now - timedelta(days=4)),
          _save(db_session, user_id=u.id, report_id=reports[2].id, saved_at=now - timedelta(days=2)),
          _save(db_session, user_id=u.id, report_id=reports[3].id, saved_at=now),
      ]
      db_session.commit()
      return {"user": u, "reports": reports, "saves": saves, "now": now}


  def test_list_filtered_default_sort_is_saved_desc(db_session, seeded):
      rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id)
      titles = [row.report.title for row in rows]
      assert titles == ["MSFT-update", "briefing-notes", "AAPL-earnings-q1-2026", "AAPL-initiation-coverage"]


  def test_list_filtered_department_filter_single(db_session, seeded):
      rows = svc.list_items_filtered(
          db_session, user_id=seeded["user"].id, departments=["equity_research"]
      )
      titles = sorted(row.report.title for row in rows)
      assert titles == ["AAPL-initiation-coverage", "MSFT-update"]


  def test_list_filtered_department_filter_multi_is_union(db_session, seeded):
      rows = svc.list_items_filtered(
          db_session, user_id=seeded["user"].id, departments=["equity_research", "secretary"]
      )
      titles = sorted(row.report.title for row in rows)
      assert titles == ["AAPL-initiation-coverage", "MSFT-update", "briefing-notes"]


  def test_list_filtered_q_substring_case_insensitive(db_session, seeded):
      rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id, q="aapl")
      titles = sorted(row.report.title for row in rows)
      assert titles == ["AAPL-earnings-q1-2026", "AAPL-initiation-coverage"]


  def test_list_filtered_generated_date_range_inclusive(db_session, seeded):
      now = seeded["now"]
      rows = svc.list_items_filtered(
          db_session,
          user_id=seeded["user"].id,
          generated_from=(now - timedelta(days=5)).date(),
          generated_to=(now - timedelta(days=3)).date(),
      )
      titles = sorted(row.report.title for row in rows)
      assert titles == ["AAPL-earnings-q1-2026", "briefing-notes"]


  def test_list_filtered_saved_date_range_inclusive(db_session, seeded):
      now = seeded["now"]
      rows = svc.list_items_filtered(
          db_session,
          user_id=seeded["user"].id,
          saved_from=(now - timedelta(days=4)).date(),
          saved_to=(now - timedelta(days=2)).date(),
      )
      titles = sorted(row.report.title for row in rows)
      assert titles == ["AAPL-earnings-q1-2026", "briefing-notes"]


  def test_list_filtered_sort_generated_asc(db_session, seeded):
      rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id, sort="generated_asc")
      titles = [row.report.title for row in rows]
      assert titles == ["AAPL-initiation-coverage", "AAPL-earnings-q1-2026", "briefing-notes", "MSFT-update"]


  def test_list_filtered_sort_department_asc(db_session, seeded):
      rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id, sort="department_asc")
      deps = [row.report.department for row in rows]
      # earnings_update < equity_research < secretary
      assert deps[0] == "earnings_update"
      assert deps[-1] == "secretary"


  def test_list_filtered_sort_filename_asc(db_session, seeded):
      rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id, sort="filename_asc")
      titles = [row.report.title for row in rows]
      assert titles == sorted(titles)


  def test_list_filtered_pagination(db_session, seeded):
      page1 = svc.list_items_filtered(
          db_session, user_id=seeded["user"].id, page=1, page_size=2, sort="saved_desc"
      )
      page2 = svc.list_items_filtered(
          db_session, user_id=seeded["user"].id, page=2, page_size=2, sort="saved_desc"
      )
      assert [r.report.title for r in page1] == ["MSFT-update", "briefing-notes"]
      assert [r.report.title for r in page2] == ["AAPL-earnings-q1-2026", "AAPL-initiation-coverage"]


  def test_list_filtered_scoped_to_user(db_session, seeded):
      other = _mk_user(db_session)
      db_session.commit()
      rows = svc.list_items_filtered(db_session, user_id=other.id)
      assert rows == []


  def test_facets_counts_by_department(db_session, seeded):
      f = svc.facets(db_session, user_id=seeded["user"].id)
      dep_counts = {d["slug"]: d["count"] for d in f["departments"]}
      assert dep_counts == {"equity_research": 2, "earnings_update": 1, "secretary": 1}
      assert f["total"] == 4


  def test_facets_excludes_other_users(db_session, seeded):
      other = _mk_user(db_session)
      db_session.commit()
      f = svc.facets(db_session, user_id=other.id)
      assert f == {"departments": [], "total": 0}
  ```

- [ ] **1.2 — Run the tests (expect failure)**

  Run:
  ```bash
  uv run pytest packages/server/tests/test_services/test_repo_filtered.py -q
  ```
  Expected: every test fails with `AttributeError: module 'openlia_server.services.repo' has no attribute 'list_items_filtered'` (or similar). This confirms the test file loads and the service is genuinely missing.

- [ ] **1.3 — Commit**

  ```bash
  git add packages/server/tests/test_services/test_repo_filtered.py
  git commit -m "test(repo): add failing unit tests for list_items_filtered + facets"
  ```

---

### Task 2 — Service impl: `list_items_filtered` + `facets`

- [ ] **2.1 — Replace `packages/server/src/openlia_server/services/repo.py` with the expanded version**

  Exact file content:
  ```python
  """CRUD + filtered list + facets for repo_items — saved reports, per user."""

  from __future__ import annotations

  import uuid
  from dataclasses import dataclass
  from datetime import date, datetime, time, timezone
  from typing import Literal

  from sqlalchemy import func, select
  from sqlalchemy.exc import IntegrityError
  from sqlalchemy.orm import Session, joinedload

  from openlia_server.db.models.content import RepoItem, Report

  SortKey = Literal[
      "saved_desc",
      "saved_asc",
      "generated_desc",
      "generated_asc",
      "department_asc",
      "filename_asc",
  ]

  VALID_SORTS: frozenset[str] = frozenset(
      {
          "saved_desc",
          "saved_asc",
          "generated_desc",
          "generated_asc",
          "department_asc",
          "filename_asc",
      }
  )


  @dataclass(frozen=True)
  class RepoRow:
      item: RepoItem
      report: Report


  def save_to_repo(db: Session, *, user_id: str, report_id: str) -> RepoItem:
      existing = db.execute(
          select(RepoItem).where(RepoItem.user_id == user_id, RepoItem.report_id == report_id)
      ).scalar_one_or_none()
      if existing is not None:
          return existing
      if db.get(Report, report_id) is None:
          raise LookupError(f"report {report_id} not found")
      item = RepoItem(id=str(uuid.uuid4()), user_id=user_id, report_id=report_id)
      db.add(item)
      try:
          db.commit()
      except IntegrityError:
          db.rollback()
          return db.execute(
              select(RepoItem).where(
                  RepoItem.user_id == user_id, RepoItem.report_id == report_id
              )
          ).scalar_one()
      db.refresh(item)
      return item


  def unsave_from_repo(db: Session, *, user_id: str, report_id: str) -> None:
      db.query(RepoItem).filter(
          RepoItem.user_id == user_id, RepoItem.report_id == report_id
      ).delete()
      db.commit()


  def list_items(db: Session, *, user_id: str) -> list[RepoItem]:
      stmt = (
          select(RepoItem)
          .where(RepoItem.user_id == user_id)
          .order_by(RepoItem.created_at.desc())
      )
      return list(db.execute(stmt).scalars())


  def _start_of_day_utc(d: date) -> datetime:
      return datetime.combine(d, time.min, tzinfo=timezone.utc)


  def _end_of_day_utc(d: date) -> datetime:
      return datetime.combine(d, time.max, tzinfo=timezone.utc)


  def list_items_filtered(
      db: Session,
      *,
      user_id: str,
      q: str | None = None,
      departments: list[str] | None = None,
      generated_from: date | None = None,
      generated_to: date | None = None,
      saved_from: date | None = None,
      saved_to: date | None = None,
      sort: SortKey = "saved_desc",
      page: int = 1,
      page_size: int = 50,
  ) -> list[RepoRow]:
      if sort not in VALID_SORTS:
          raise ValueError(f"invalid sort: {sort!r}")
      if page < 1:
          raise ValueError("page must be >= 1")
      if page_size < 1 or page_size > 200:
          raise ValueError("page_size must be in [1, 200]")

      stmt = (
          select(RepoItem)
          .join(Report, RepoItem.report_id == Report.id)
          .where(RepoItem.user_id == user_id)
          .options(joinedload(RepoItem.report) if _has_rel() else joinedload(Report))  # noqa: E501
      )
      # Note: RepoItem has no ORM relationship to Report, so pull both via join:
      stmt = (
          select(RepoItem, Report)
          .join(Report, RepoItem.report_id == Report.id)
          .where(RepoItem.user_id == user_id)
      )
      if q:
          stmt = stmt.where(func.lower(Report.title).like(f"%{q.lower()}%"))
      if departments:
          stmt = stmt.where(Report.department.in_(departments))
      if generated_from:
          stmt = stmt.where(Report.created_at >= _start_of_day_utc(generated_from))
      if generated_to:
          stmt = stmt.where(Report.created_at <= _end_of_day_utc(generated_to))
      if saved_from:
          stmt = stmt.where(RepoItem.created_at >= _start_of_day_utc(saved_from))
      if saved_to:
          stmt = stmt.where(RepoItem.created_at <= _end_of_day_utc(saved_to))

      if sort == "saved_desc":
          stmt = stmt.order_by(RepoItem.created_at.desc(), RepoItem.id.asc())
      elif sort == "saved_asc":
          stmt = stmt.order_by(RepoItem.created_at.asc(), RepoItem.id.asc())
      elif sort == "generated_desc":
          stmt = stmt.order_by(Report.created_at.desc(), RepoItem.id.asc())
      elif sort == "generated_asc":
          stmt = stmt.order_by(Report.created_at.asc(), RepoItem.id.asc())
      elif sort == "department_asc":
          stmt = stmt.order_by(Report.department.asc(), Report.title.asc())
      elif sort == "filename_asc":
          stmt = stmt.order_by(Report.title.asc())

      offset = (page - 1) * page_size
      stmt = stmt.offset(offset).limit(page_size)

      rows = db.execute(stmt).all()
      return [RepoRow(item=item, report=report) for item, report in rows]


  def _has_rel() -> bool:
      # Kept to satisfy internal shape; RepoItem has no ORM relationship to Report today.
      return False


  def facets(db: Session, *, user_id: str) -> dict:
      stmt = (
          select(Report.department, func.count(RepoItem.id))
          .join(Report, RepoItem.report_id == Report.id)
          .where(RepoItem.user_id == user_id)
          .group_by(Report.department)
          .order_by(Report.department.asc())
      )
      rows = db.execute(stmt).all()
      departments = [{"slug": dep, "count": int(count)} for dep, count in rows]
      total = sum(d["count"] for d in departments)
      return {"departments": departments, "total": total}
  ```

  Note: the duplicated `stmt` block above is intentional cleanup — keep only the second assignment (the `select(RepoItem, Report)` form). Remove the first `stmt = ...joinedload(...)` block when you paste.

  **Paste-ready final form** (drop the noise, this is what the file must contain verbatim):
  ```python
  """CRUD + filtered list + facets for repo_items — saved reports, per user."""

  from __future__ import annotations

  import uuid
  from dataclasses import dataclass
  from datetime import date, datetime, time, timezone
  from typing import Literal

  from sqlalchemy import func, select
  from sqlalchemy.exc import IntegrityError
  from sqlalchemy.orm import Session

  from openlia_server.db.models.content import RepoItem, Report

  SortKey = Literal[
      "saved_desc",
      "saved_asc",
      "generated_desc",
      "generated_asc",
      "department_asc",
      "filename_asc",
  ]

  VALID_SORTS: frozenset[str] = frozenset(
      {
          "saved_desc",
          "saved_asc",
          "generated_desc",
          "generated_asc",
          "department_asc",
          "filename_asc",
      }
  )


  @dataclass(frozen=True)
  class RepoRow:
      item: RepoItem
      report: Report


  def save_to_repo(db: Session, *, user_id: str, report_id: str) -> RepoItem:
      existing = db.execute(
          select(RepoItem).where(RepoItem.user_id == user_id, RepoItem.report_id == report_id)
      ).scalar_one_or_none()
      if existing is not None:
          return existing
      if db.get(Report, report_id) is None:
          raise LookupError(f"report {report_id} not found")
      item = RepoItem(id=str(uuid.uuid4()), user_id=user_id, report_id=report_id)
      db.add(item)
      try:
          db.commit()
      except IntegrityError:
          db.rollback()
          return db.execute(
              select(RepoItem).where(
                  RepoItem.user_id == user_id, RepoItem.report_id == report_id
              )
          ).scalar_one()
      db.refresh(item)
      return item


  def unsave_from_repo(db: Session, *, user_id: str, report_id: str) -> None:
      db.query(RepoItem).filter(
          RepoItem.user_id == user_id, RepoItem.report_id == report_id
      ).delete()
      db.commit()


  def list_items(db: Session, *, user_id: str) -> list[RepoItem]:
      stmt = (
          select(RepoItem)
          .where(RepoItem.user_id == user_id)
          .order_by(RepoItem.created_at.desc())
      )
      return list(db.execute(stmt).scalars())


  def _start_of_day_utc(d: date) -> datetime:
      return datetime.combine(d, time.min, tzinfo=timezone.utc)


  def _end_of_day_utc(d: date) -> datetime:
      return datetime.combine(d, time.max, tzinfo=timezone.utc)


  def list_items_filtered(
      db: Session,
      *,
      user_id: str,
      q: str | None = None,
      departments: list[str] | None = None,
      generated_from: date | None = None,
      generated_to: date | None = None,
      saved_from: date | None = None,
      saved_to: date | None = None,
      sort: SortKey = "saved_desc",
      page: int = 1,
      page_size: int = 50,
  ) -> list[RepoRow]:
      if sort not in VALID_SORTS:
          raise ValueError(f"invalid sort: {sort!r}")
      if page < 1:
          raise ValueError("page must be >= 1")
      if page_size < 1 or page_size > 200:
          raise ValueError("page_size must be in [1, 200]")

      stmt = (
          select(RepoItem, Report)
          .join(Report, RepoItem.report_id == Report.id)
          .where(RepoItem.user_id == user_id)
      )
      if q:
          stmt = stmt.where(func.lower(Report.title).like(f"%{q.lower()}%"))
      if departments:
          stmt = stmt.where(Report.department.in_(departments))
      if generated_from:
          stmt = stmt.where(Report.created_at >= _start_of_day_utc(generated_from))
      if generated_to:
          stmt = stmt.where(Report.created_at <= _end_of_day_utc(generated_to))
      if saved_from:
          stmt = stmt.where(RepoItem.created_at >= _start_of_day_utc(saved_from))
      if saved_to:
          stmt = stmt.where(RepoItem.created_at <= _end_of_day_utc(saved_to))

      if sort == "saved_desc":
          stmt = stmt.order_by(RepoItem.created_at.desc(), RepoItem.id.asc())
      elif sort == "saved_asc":
          stmt = stmt.order_by(RepoItem.created_at.asc(), RepoItem.id.asc())
      elif sort == "generated_desc":
          stmt = stmt.order_by(Report.created_at.desc(), RepoItem.id.asc())
      elif sort == "generated_asc":
          stmt = stmt.order_by(Report.created_at.asc(), RepoItem.id.asc())
      elif sort == "department_asc":
          stmt = stmt.order_by(Report.department.asc(), Report.title.asc())
      elif sort == "filename_asc":
          stmt = stmt.order_by(Report.title.asc())

      offset = (page - 1) * page_size
      stmt = stmt.offset(offset).limit(page_size)

      rows = db.execute(stmt).all()
      return [RepoRow(item=item, report=report) for item, report in rows]


  def facets(db: Session, *, user_id: str) -> dict:
      stmt = (
          select(Report.department, func.count(RepoItem.id))
          .join(Report, RepoItem.report_id == Report.id)
          .where(RepoItem.user_id == user_id)
          .group_by(Report.department)
          .order_by(Report.department.asc())
      )
      rows = db.execute(stmt).all()
      departments = [{"slug": dep, "count": int(count)} for dep, count in rows]
      total = sum(d["count"] for d in departments)
      return {"departments": departments, "total": total}
  ```

- [ ] **2.2 — Run service tests (expect green)**

  ```bash
  uv run pytest packages/server/tests/test_services/test_repo_filtered.py -q
  ```
  Expected: `12 passed`.

- [ ] **2.3 — Run the pre-existing repo service tests (regression check)**

  ```bash
  uv run pytest packages/server/tests/test_services/test_repo.py -q
  ```
  Expected: all pass (Plan 12 tests still green).

- [ ] **2.4 — Lint + format**

  ```bash
  uv run ruff check packages/server/src/openlia_server/services/repo.py packages/server/tests/test_services/test_repo_filtered.py
  uv run ruff format packages/server/src/openlia_server/services/repo.py packages/server/tests/test_services/test_repo_filtered.py
  ```

- [ ] **2.5 — Commit**

  ```bash
  git add packages/server/src/openlia_server/services/repo.py
  git commit -m "feat(repo): add list_items_filtered + facets service helpers"
  ```

---

### Task 3 — Route tests: extended `GET /repo/items`

- [ ] **3.1 — Write `packages/server/tests/test_routes/test_repo_filter_routes.py`**

  Exact file content:
  ```python
  """HTTP tests for the filter/sort/pagination extensions of GET /repo/items + /repo/facets."""

  from __future__ import annotations

  import uuid
  from datetime import datetime, timedelta, timezone


  def _save(client, *, report_id: str, saved_at: datetime, db_session):
      """Backdate the saved_at timestamp for determinism."""
      from openlia_server.db.models.content import RepoItem

      client.post("/repo/items", json={"report_id": report_id}).raise_for_status() if False else None
      resp = client.post("/repo/items", json={"report_id": report_id})
      assert resp.status_code == 201, resp.text
      item_id = resp.json()["id"]
      row = db_session.get(RepoItem, item_id)
      row.created_at = saved_at
      db_session.add(row)
      db_session.commit()
      return item_id


  def test_list_returns_expanded_row_shape(
      client, user_factory, login_as, report_factory, db_session
  ):
      u = user_factory()
      login_as(u)
      r = report_factory(user_id=u.id, department="equity_research", title="AAPL-coverage")
      client.post("/repo/items", json={"report_id": r.id})
      body = client.get("/repo/items").json()
      assert "items" in body
      assert body["page"] == 1
      assert body["page_size"] == 50
      assert body["has_more"] is False
      item = body["items"][0]
      assert item["report_id"] == r.id
      assert item["department"] == "equity_research"
      assert item["title"] == "AAPL-coverage"
      assert item["filename"] == "AAPL-coverage.pdf"
      assert "generated_at" in item
      assert "saved_at" in item


  def test_filter_by_q_case_insensitive(
      client, user_factory, login_as, report_factory
  ):
      u = user_factory()
      login_as(u)
      a = report_factory(user_id=u.id, title="AAPL-initiation")
      b = report_factory(user_id=u.id, title="MSFT-update")
      client.post("/repo/items", json={"report_id": a.id})
      client.post("/repo/items", json={"report_id": b.id})
      body = client.get("/repo/items?q=aapl").json()
      titles = [i["title"] for i in body["items"]]
      assert titles == ["AAPL-initiation"]


  def test_filter_by_department_repeatable(
      client, user_factory, login_as, report_factory
  ):
      u = user_factory()
      login_as(u)
      a = report_factory(user_id=u.id, department="equity_research", title="A")
      b = report_factory(user_id=u.id, department="earnings_update", title="B")
      c = report_factory(user_id=u.id, department="secretary", title="C")
      for r in (a, b, c):
          client.post("/repo/items", json={"report_id": r.id})
      body = client.get(
          "/repo/items?department=equity_research&department=secretary"
      ).json()
      titles = sorted(i["title"] for i in body["items"])
      assert titles == ["A", "C"]


  def test_filter_by_department_csv(client, user_factory, login_as, report_factory):
      u = user_factory()
      login_as(u)
      a = report_factory(user_id=u.id, department="equity_research", title="A")
      b = report_factory(user_id=u.id, department="secretary", title="B")
      for r in (a, b):
          client.post("/repo/items", json={"report_id": r.id})
      body = client.get("/repo/items?department=equity_research,secretary").json()
      titles = sorted(i["title"] for i in body["items"])
      assert titles == ["A", "B"]


  def test_filter_by_generated_date_range(
      client, user_factory, login_as, report_factory, db_session
  ):
      from openlia_server.db.models.content import Report

      u = user_factory()
      login_as(u)
      old = report_factory(user_id=u.id, title="old")
      new = report_factory(user_id=u.id, title="new")
      db_session.get(Report, old.id).created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
      db_session.get(Report, new.id).created_at = datetime(2026, 4, 10, tzinfo=timezone.utc)
      db_session.commit()
      for r in (old, new):
          client.post("/repo/items", json={"report_id": r.id})
      body = client.get(
          "/repo/items?generated_from=2026-04-01&generated_to=2026-04-30"
      ).json()
      titles = [i["title"] for i in body["items"]]
      assert titles == ["new"]


  def test_filter_by_saved_date_range(
      client, user_factory, login_as, report_factory, db_session
  ):
      u = user_factory()
      login_as(u)
      a = report_factory(user_id=u.id, title="A")
      b = report_factory(user_id=u.id, title="B")
      id_a = _save(
          client, report_id=a.id, saved_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
          db_session=db_session,
      )
      id_b = _save(
          client, report_id=b.id, saved_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
          db_session=db_session,
      )
      assert id_a != id_b
      body = client.get(
          "/repo/items?saved_from=2026-04-01&saved_to=2026-04-30"
      ).json()
      titles = [i["title"] for i in body["items"]]
      assert titles == ["B"]


  def test_sort_options_all_accepted(client, user_factory, login_as, report_factory):
      u = user_factory()
      login_as(u)
      r = report_factory(user_id=u.id)
      client.post("/repo/items", json={"report_id": r.id})
      for sort in (
          "saved_desc",
          "saved_asc",
          "generated_desc",
          "generated_asc",
          "department_asc",
          "filename_asc",
      ):
          resp = client.get(f"/repo/items?sort={sort}")
          assert resp.status_code == 200, (sort, resp.text)


  def test_invalid_sort_returns_422(client, user_factory, login_as):
      login_as(user_factory())
      resp = client.get("/repo/items?sort=bogus")
      assert resp.status_code == 422


  def test_pagination_and_has_more(
      client, user_factory, login_as, report_factory, db_session
  ):
      u = user_factory()
      login_as(u)
      for i in range(7):
          r = report_factory(user_id=u.id, title=f"r{i}")
          client.post("/repo/items", json={"report_id": r.id})
      body1 = client.get("/repo/items?page=1&page_size=3&sort=filename_asc").json()
      body2 = client.get("/repo/items?page=2&page_size=3&sort=filename_asc").json()
      body3 = client.get("/repo/items?page=3&page_size=3&sort=filename_asc").json()
      assert [i["title"] for i in body1["items"]] == ["r0", "r1", "r2"]
      assert body1["has_more"] is True
      assert [i["title"] for i in body2["items"]] == ["r3", "r4", "r5"]
      assert body2["has_more"] is True
      assert [i["title"] for i in body3["items"]] == ["r6"]
      assert body3["has_more"] is False


  def test_page_size_cap_returns_422(client, user_factory, login_as):
      login_as(user_factory())
      assert client.get("/repo/items?page_size=500").status_code == 422


  def test_list_scoped_to_user(
      client, user_factory, login_as, report_factory
  ):
      a = user_factory()
      b = user_factory()
      login_as(a)
      ra = report_factory(user_id=a.id, title="ra")
      client.post("/repo/items", json={"report_id": ra.id})
      login_as(b)
      assert client.get("/repo/items").json()["items"] == []


  def test_requires_auth(client):
      assert client.get("/repo/items").status_code in (401, 403)
  ```

- [ ] **3.2 — Run (expect failure)**

  ```bash
  uv run pytest packages/server/tests/test_routes/test_repo_filter_routes.py -q
  ```
  Expected: multiple failures — the current route does not parse filter params and does not return the expanded shape.

- [ ] **3.3 — Commit**

  ```bash
  git add packages/server/tests/test_routes/test_repo_filter_routes.py
  git commit -m "test(repo): add failing route tests for filtered GET /repo/items"
  ```

---

### Task 4 — Route impl: extend `GET /repo/items`

- [ ] **4.1 — Replace `packages/server/src/openlia_server/routes/repo.py` with the expanded router**

  Exact file content:
  ```python
  """Routes for repo items (saved reports)."""

  from __future__ import annotations

  from datetime import date, datetime
  from typing import Annotated, Literal

  from fastapi import APIRouter, Depends, HTTPException, Query, status
  from pydantic import BaseModel, Field
  from sqlalchemy.orm import Session

  from openlia_server.db.deps import make_session_dependency
  from openlia_server.db.models.auth import User
  from openlia_server.middleware.auth import build_require_auth
  from openlia_server.services import repo as svc


  class RepoSaveIn(BaseModel):
      report_id: str


  class RepoItemOut(BaseModel):
      id: str
      report_id: str
      created_at: datetime  # kept for Plan 12 backward compat; duplicates saved_at
      saved_at: datetime
      generated_at: datetime
      department: str
      report_type: str
      title: str
      filename: str


  class RepoListOut(BaseModel):
      items: list[RepoItemOut]
      page: int
      page_size: int
      has_more: bool


  class RepoFacetDepartment(BaseModel):
      slug: str
      count: int


  class RepoFacetsOut(BaseModel):
      departments: list[RepoFacetDepartment]
      total: int


  _SORT_VALUES = Literal[
      "saved_desc",
      "saved_asc",
      "generated_desc",
      "generated_asc",
      "department_asc",
      "filename_asc",
  ]


  def _split_csv(values: list[str] | None) -> list[str] | None:
      if not values:
          return None
      out: list[str] = []
      for v in values:
          for part in v.split(","):
              part = part.strip()
              if part:
                  out.append(part)
      return out or None


  def build_repo_router(*, db_session_factory, mode: str) -> APIRouter:
      router = APIRouter(prefix="/repo", tags=["repo"])
      require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
      session_dep = make_session_dependency(db_session_factory)

      @router.get("/items", response_model=RepoListOut)
      def list_items_ep(
          q: Annotated[str | None, Query()] = None,
          department: Annotated[list[str] | None, Query()] = None,
          generated_from: Annotated[date | None, Query()] = None,
          generated_to: Annotated[date | None, Query()] = None,
          saved_from: Annotated[date | None, Query()] = None,
          saved_to: Annotated[date | None, Query()] = None,
          sort: Annotated[_SORT_VALUES, Query()] = "saved_desc",
          page: Annotated[int, Query(ge=1)] = 1,
          page_size: Annotated[int, Query(ge=1, le=200)] = 50,
          db: Session = Depends(session_dep),
          user: User = require_auth,
      ) -> RepoListOut:
          deps = _split_csv(department)
          rows = svc.list_items_filtered(
              db,
              user_id=user.id,
              q=q,
              departments=deps,
              generated_from=generated_from,
              generated_to=generated_to,
              saved_from=saved_from,
              saved_to=saved_to,
              sort=sort,
              page=page,
              page_size=page_size,
          )
          items = [
              RepoItemOut(
                  id=row.item.id,
                  report_id=row.report.id,
                  created_at=row.item.created_at,
                  saved_at=row.item.created_at,
                  generated_at=row.report.created_at,
                  department=row.report.department,
                  report_type=row.report.report_type,
                  title=row.report.title,
                  filename=f"{row.report.title}.pdf",
              )
              for row in rows
          ]
          return RepoListOut(
              items=items,
              page=page,
              page_size=page_size,
              has_more=len(rows) == page_size,
          )

      @router.get("/facets", response_model=RepoFacetsOut)
      def facets_ep(
          db: Session = Depends(session_dep),
          user: User = require_auth,
      ) -> RepoFacetsOut:
          f = svc.facets(db, user_id=user.id)
          return RepoFacetsOut(
              departments=[RepoFacetDepartment(**d) for d in f["departments"]],
              total=f["total"],
          )

      @router.post("/items", response_model=RepoItemOut, status_code=status.HTTP_201_CREATED)
      def save_ep(
          body: RepoSaveIn,
          db: Session = Depends(session_dep),
          user: User = require_auth,
      ) -> RepoItemOut:
          try:
              item = svc.save_to_repo(db, user_id=user.id, report_id=body.report_id)
          except LookupError as exc:
              raise HTTPException(
                  status_code=404,
                  detail={"code": "report_not_found", "message": str(exc)},
              ) from exc
          # Return the enriched shape by looking up the associated Report.
          from openlia_server.db.models.content import Report

          report = db.get(Report, item.report_id)
          if report is None:
              # Extremely unlikely (FK + just saved); keep defensive 500.
              raise HTTPException(500, "report disappeared after save")
          return RepoItemOut(
              id=item.id,
              report_id=item.report_id,
              created_at=item.created_at,
              saved_at=item.created_at,
              generated_at=report.created_at,
              department=report.department,
              report_type=report.report_type,
              title=report.title,
              filename=f"{report.title}.pdf",
          )

      @router.delete("/items", status_code=status.HTTP_204_NO_CONTENT)
      def delete_ep(
          report_id: str,
          db: Session = Depends(session_dep),
          user: User = require_auth,
      ) -> None:
          svc.unsave_from_repo(db, user_id=user.id, report_id=report_id)

      return router


  __all__ = [
      "RepoFacetDepartment",
      "RepoFacetsOut",
      "RepoItemOut",
      "RepoListOut",
      "RepoSaveIn",
      "build_repo_router",
  ]
  ```

- [ ] **4.2 — Run route tests (expect green)**

  ```bash
  uv run pytest packages/server/tests/test_routes/test_repo_filter_routes.py -q
  ```
  Expected: all pass.

- [ ] **4.3 — Re-run Plan 12's `test_repo_routes.py` (regression — shape widened but shouldn't break)**

  ```bash
  uv run pytest packages/server/tests/test_routes/test_repo_routes.py -q
  ```
  Expected: all pass. Plan 12's tests only assert `items[0]["report_id"]` and `status_code == 201/204`; adding fields is compatible.

- [ ] **4.4 — Lint + format**

  ```bash
  uv run ruff check packages/server/src/openlia_server/routes/repo.py packages/server/tests/test_routes/test_repo_filter_routes.py
  uv run ruff format packages/server/src/openlia_server/routes/repo.py packages/server/tests/test_routes/test_repo_filter_routes.py
  ```

- [ ] **4.5 — Commit**

  ```bash
  git add packages/server/src/openlia_server/routes/repo.py
  git commit -m "feat(repo): extend GET /repo/items with filter/sort/pagination"
  ```

---

### Task 5 — Route tests: `GET /repo/facets`

- [ ] **5.1 — Append `/repo/facets` tests to `test_repo_filter_routes.py`**

  Using the `Edit` tool, append these tests to the bottom of `packages/server/tests/test_routes/test_repo_filter_routes.py`:
  ```python


  def test_facets_empty(client, user_factory, login_as):
      login_as(user_factory())
      body = client.get("/repo/facets").json()
      assert body == {"departments": [], "total": 0}


  def test_facets_counts_by_department(
      client, user_factory, login_as, report_factory
  ):
      u = user_factory()
      login_as(u)
      for dep in ("equity_research", "equity_research", "secretary"):
          r = report_factory(user_id=u.id, department=dep)
          client.post("/repo/items", json={"report_id": r.id})
      body = client.get("/repo/facets").json()
      by_slug = {d["slug"]: d["count"] for d in body["departments"]}
      assert by_slug == {"equity_research": 2, "secretary": 1}
      assert body["total"] == 3


  def test_facets_requires_auth(client):
      assert client.get("/repo/facets").status_code in (401, 403)
  ```

- [ ] **5.2 — Run**

  ```bash
  uv run pytest packages/server/tests/test_routes/test_repo_filter_routes.py -q
  ```
  Expected: all pass (facets endpoint shipped in Task 4 already covers these).

- [ ] **5.3 — Commit**

  ```bash
  git add packages/server/tests/test_routes/test_repo_filter_routes.py
  git commit -m "test(repo): add route tests for GET /repo/facets"
  ```

---

### Task 6 — (Reserved — merged into Task 4)

Task 4's router already includes `GET /repo/facets`. No separate implementation step is required; tests land in Task 5 and pass against the shipped handler. Mark this task checked off:

- [ ] **6.1 — Confirm Task 5 tests cover the facets endpoint**

  ```bash
  uv run pytest packages/server/tests/test_routes/test_repo_filter_routes.py::test_facets_empty packages/server/tests/test_routes/test_repo_filter_routes.py::test_facets_counts_by_department packages/server/tests/test_routes/test_repo_filter_routes.py::test_facets_requires_auth -q
  ```
  Expected: `3 passed`.

- [ ] **6.2 — No commit (bookkeeping)**

---

### Task 7 — Contract + authorization matrix updates

- [ ] **7.1 — Add Plan 22 rows to `planning/implementation-plans/endpoint-contract-matrix.md`**

  Open the file, find the "Plan 22" section (create one if missing, after the Plan 21 section), and add:

  ```markdown
  ### Plan 22 — Repository page

  - `/repo/items` (GET, `require_auth` + owner scope) — filtered + paginated list. Query params: `q`, `department` (repeatable/CSV), `generated_from`, `generated_to`, `saved_from`, `saved_to`, `sort ∈ {saved_desc|saved_asc|generated_desc|generated_asc|department_asc|filename_asc}`, `page ≥ 1`, `page_size ∈ [1,200]`. Response `{items: RepoItemOut[], page, page_size, has_more}`. Backend fn `openlia_server.routes.repo.build_repo_router.list_items_ep`. Frontend `frontend/src/api/repo.ts::listRepoItems`. Test `packages/server/tests/test_routes/test_repo_filter_routes.py`.
  - `/repo/facets` (GET, `require_auth` + owner scope) — `{departments: [{slug, count}], total}`. Backend fn `openlia_server.routes.repo.build_repo_router.facets_ep`. Frontend `frontend/src/api/repo.ts::getRepoFacets`.

  Shape of `RepoItemOut`: `{id, report_id, created_at (= saved_at), saved_at, generated_at, department, report_type, title, filename}`. `filename = "{title}.pdf"` is derived server-side for display.
  ```

- [ ] **7.2 — Add Plan 22 rows to `planning/implementation-plans/route-authorization-matrix.md`**

  Under a new "Plan 22 — Repository" subsection:
  ```markdown
  ### Plan 22 — Repository page

  | Route | Auth | Owner scope | Admin |
  |---|---|---|---|
  | `GET /repo/items` (filtered) | `require_auth` | `RepoItem.user_id == user.id` | blocked |
  | `GET /repo/facets` | `require_auth` | `RepoItem.user_id == user.id` | blocked |

  No new write routes — removal reuses `DELETE /repo/items?report_id=<id>` (Plan 12). Undo calls `POST /repo/items` (Plan 12, idempotent).
  ```

- [ ] **7.3 — Commit**

  ```bash
  git add planning/implementation-plans/endpoint-contract-matrix.md planning/implementation-plans/route-authorization-matrix.md
  git commit -m "docs(plan-22): add repo filter/facets rows to contract + auth matrices"
  ```

---

### Task 8 — Frontend API client expansion + tests

- [ ] **8.1 — Replace `frontend/src/api/repo.ts`**

  Exact file content:
  ```ts
  import { fetchJson } from "./client";

  export type RepoSort =
    | "saved_desc"
    | "saved_asc"
    | "generated_desc"
    | "generated_asc"
    | "department_asc"
    | "filename_asc";

  export interface RepoItem {
    id: string;
    report_id: string;
    created_at: string; // legacy alias; prefer saved_at
    saved_at: string;
    generated_at: string;
    department: string;
    report_type: string;
    title: string;
    filename: string;
  }

  export interface RepoListPage {
    items: RepoItem[];
    page: number;
    page_size: number;
    has_more: boolean;
  }

  export interface RepoFacets {
    departments: { slug: string; count: number }[];
    total: number;
  }

  export interface ListRepoParams {
    q?: string;
    department?: string[];
    generated_from?: string; // YYYY-MM-DD
    generated_to?: string;
    saved_from?: string;
    saved_to?: string;
    sort?: RepoSort;
    page?: number;
    page_size?: number;
  }

  export function buildRepoListUrl(p: ListRepoParams): string {
    const sp = new URLSearchParams();
    if (p.q) sp.set("q", p.q);
    if (p.department && p.department.length > 0) {
      for (const d of p.department) sp.append("department", d);
    }
    if (p.generated_from) sp.set("generated_from", p.generated_from);
    if (p.generated_to) sp.set("generated_to", p.generated_to);
    if (p.saved_from) sp.set("saved_from", p.saved_from);
    if (p.saved_to) sp.set("saved_to", p.saved_to);
    if (p.sort) sp.set("sort", p.sort);
    if (p.page !== undefined) sp.set("page", String(p.page));
    if (p.page_size !== undefined) sp.set("page_size", String(p.page_size));
    const qs = sp.toString();
    return qs ? `/api/repo/items?${qs}` : "/api/repo/items";
  }

  export const listRepoItems = (params: ListRepoParams = {}) =>
    fetchJson<RepoListPage>(buildRepoListUrl(params));

  export const getRepoFacets = () => fetchJson<RepoFacets>("/api/repo/facets");

  export const saveToRepo = (reportId: string) =>
    fetchJson<RepoItem>("/api/repo/items", {
      method: "POST",
      json: { report_id: reportId },
    });

  export const unsaveFromRepo = (reportId: string) =>
    fetchJson<void>(
      `/api/repo/items?report_id=${encodeURIComponent(reportId)}`,
      { method: "DELETE" },
    );
  ```

- [ ] **8.2 — Write `frontend/src/api/__tests__/repo.test.ts`**

  Exact content:
  ```ts
  import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
  import { buildRepoListUrl, listRepoItems, getRepoFacets, saveToRepo, unsaveFromRepo } from "../repo";

  describe("buildRepoListUrl", () => {
    it("returns bare URL with no params", () => {
      expect(buildRepoListUrl({})).toBe("/api/repo/items");
    });

    it("encodes q + sort + page_size", () => {
      const url = buildRepoListUrl({ q: "aapl", sort: "saved_asc", page_size: 25 });
      expect(url).toContain("q=aapl");
      expect(url).toContain("sort=saved_asc");
      expect(url).toContain("page_size=25");
    });

    it("repeats department for each selection", () => {
      const url = buildRepoListUrl({ department: ["equity_research", "secretary"] });
      const sp = new URL("http://x" + url.replace("/api", "")).searchParams.getAll("department");
      expect(sp).toEqual(["equity_research", "secretary"]);
    });

    it("omits department when array is empty", () => {
      expect(buildRepoListUrl({ department: [] })).toBe("/api/repo/items");
    });
  });

  describe("repo api", () => {
    const fetchMock = vi.fn();
    beforeEach(() => {
      fetchMock.mockReset();
      vi.stubGlobal("fetch", fetchMock);
    });
    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("listRepoItems GETs with encoded params", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], page: 1, page_size: 50, has_more: false }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );
      await listRepoItems({ q: "a", page: 2 });
      const [url, init] = fetchMock.mock.calls[0];
      expect(String(url)).toContain("/api/repo/items?");
      expect(String(url)).toContain("q=a");
      expect(String(url)).toContain("page=2");
      expect(init?.method ?? "GET").toBe("GET");
    });

    it("getRepoFacets GETs /api/repo/facets", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify({ departments: [], total: 0 }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );
      await getRepoFacets();
      expect(String(fetchMock.mock.calls[0][0])).toBe("/api/repo/facets");
    });

    it("saveToRepo POSTs JSON body", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "i",
            report_id: "r",
            created_at: "2026-04-01T00:00:00Z",
            saved_at: "2026-04-01T00:00:00Z",
            generated_at: "2026-04-01T00:00:00Z",
            department: "secretary",
            report_type: "secretary_report",
            title: "t",
            filename: "t.pdf",
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        ),
      );
      await saveToRepo("r");
      const [, init] = fetchMock.mock.calls[0];
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ report_id: "r" }));
    });

    it("unsaveFromRepo DELETEs by query string", async () => {
      fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
      await unsaveFromRepo("r 1");
      const [url, init] = fetchMock.mock.calls[0];
      expect(String(url)).toBe("/api/repo/items?report_id=r%201");
      expect(init?.method).toBe("DELETE");
    });
  });
  ```

- [ ] **8.3 — Run**

  ```bash
  cd frontend && npx vitest run src/api/__tests__/repo.test.ts
  ```
  Expected: all tests pass.

- [ ] **8.4 — Commit**

  ```bash
  git add frontend/src/api/repo.ts frontend/src/api/__tests__/repo.test.ts
  git commit -m "feat(repo-ui): expand repo api client with filters + facets"
  ```

---

### Task 9 — `useRepoList` hook + tests

- [ ] **9.1 — Create `frontend/src/hooks/useRepoList.ts`**

  Exact content:
  ```ts
  import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
  import {
    listRepoItems,
    type ListRepoParams,
    type RepoItem,
    type RepoListPage,
    type RepoSort,
  } from "../api/repo";

  export interface RepoFilters {
    q: string;
    departments: string[];
    generatedFrom: string | null; // YYYY-MM-DD
    generatedTo: string | null;
    savedFrom: string | null;
    savedTo: string | null;
    sort: RepoSort;
  }

  export const EMPTY_FILTERS: RepoFilters = {
    q: "",
    departments: [],
    generatedFrom: null,
    generatedTo: null,
    savedFrom: null,
    savedTo: null,
    sort: "saved_desc",
  };

  interface State {
    items: RepoItem[];
    page: number;
    hasMore: boolean;
    loading: boolean;
    loadingMore: boolean;
    error: string | null;
  }

  type Action =
    | { type: "reset" }
    | { type: "loading" }
    | { type: "loading_more" }
    | { type: "page_loaded"; payload: RepoListPage; replace: boolean }
    | { type: "error"; payload: string }
    | { type: "remove_item"; reportId: string }
    | { type: "restore_item"; item: RepoItem };

  function reducer(state: State, action: Action): State {
    switch (action.type) {
      case "reset":
        return { items: [], page: 0, hasMore: true, loading: false, loadingMore: false, error: null };
      case "loading":
        return { ...state, loading: true, error: null };
      case "loading_more":
        return { ...state, loadingMore: true, error: null };
      case "page_loaded":
        return {
          items: action.replace ? action.payload.items : [...state.items, ...action.payload.items],
          page: action.payload.page,
          hasMore: action.payload.has_more,
          loading: false,
          loadingMore: false,
          error: null,
        };
      case "error":
        return { ...state, loading: false, loadingMore: false, error: action.payload };
      case "remove_item":
        return { ...state, items: state.items.filter((i) => i.report_id !== action.reportId) };
      case "restore_item":
        return { ...state, items: [action.item, ...state.items] };
      default:
        return state;
    }
  }

  const PAGE_SIZE = 50;

  function paramsFor(filters: RepoFilters, page: number): ListRepoParams {
    return {
      q: filters.q || undefined,
      department: filters.departments.length > 0 ? filters.departments : undefined,
      generated_from: filters.generatedFrom ?? undefined,
      generated_to: filters.generatedTo ?? undefined,
      saved_from: filters.savedFrom ?? undefined,
      saved_to: filters.savedTo ?? undefined,
      sort: filters.sort,
      page,
      page_size: PAGE_SIZE,
    };
  }

  export function useRepoList(filters: RepoFilters) {
    const [state, dispatch] = useReducer(reducer, {
      items: [],
      page: 0,
      hasMore: true,
      loading: true,
      loadingMore: false,
      error: null,
    });
    const filtersRef = useRef(filters);
    filtersRef.current = filters;

    const filtersKey = useMemo(() => JSON.stringify(filters), [filters]);

    const loadFirst = useCallback(async () => {
      dispatch({ type: "reset" });
      dispatch({ type: "loading" });
      try {
        const page = await listRepoItems(paramsFor(filtersRef.current, 1));
        dispatch({ type: "page_loaded", payload: page, replace: true });
      } catch (e) {
        dispatch({ type: "error", payload: (e as Error).message });
      }
    }, []);

    const loadMore = useCallback(async () => {
      if (state.loading || state.loadingMore || !state.hasMore) return;
      const next = state.page + 1;
      dispatch({ type: "loading_more" });
      try {
        const page = await listRepoItems(paramsFor(filtersRef.current, next));
        dispatch({ type: "page_loaded", payload: page, replace: false });
      } catch (e) {
        dispatch({ type: "error", payload: (e as Error).message });
      }
    }, [state.loading, state.loadingMore, state.hasMore, state.page]);

    useEffect(() => {
      void loadFirst();
      // refetch whenever the serialized filter key changes
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filtersKey]);

    const removeOptimistic = useCallback((reportId: string) => {
      dispatch({ type: "remove_item", reportId });
    }, []);

    const restore = useCallback((item: RepoItem) => {
      dispatch({ type: "restore_item", item });
    }, []);

    return { ...state, loadMore, reload: loadFirst, removeOptimistic, restore };
  }
  ```

- [ ] **9.2 — Write `frontend/src/hooks/__tests__/useRepoList.test.ts`**

  Exact content:
  ```ts
  import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
  import { act, renderHook, waitFor } from "@testing-library/react";
  import { EMPTY_FILTERS, useRepoList } from "../useRepoList";

  function mockResponse(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  }

  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const sampleItem = (i: number) => ({
    id: `i${i}`,
    report_id: `r${i}`,
    created_at: "2026-04-01T00:00:00Z",
    saved_at: "2026-04-01T00:00:00Z",
    generated_at: "2026-04-01T00:00:00Z",
    department: "secretary",
    report_type: "secretary_report",
    title: `t${i}`,
    filename: `t${i}.pdf`,
  });

  describe("useRepoList", () => {
    it("loads first page on mount", async () => {
      fetchMock.mockResolvedValueOnce(
        mockResponse({ items: [sampleItem(0), sampleItem(1)], page: 1, page_size: 50, has_more: false }),
      );
      const { result } = renderHook(() => useRepoList(EMPTY_FILTERS));
      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(result.current.items).toHaveLength(2);
      expect(result.current.hasMore).toBe(false);
    });

    it("loadMore appends next page", async () => {
      fetchMock
        .mockResolvedValueOnce(
          mockResponse({ items: [sampleItem(0)], page: 1, page_size: 50, has_more: true }),
        )
        .mockResolvedValueOnce(
          mockResponse({ items: [sampleItem(1)], page: 2, page_size: 50, has_more: false }),
        );
      const { result } = renderHook(() => useRepoList(EMPTY_FILTERS));
      await waitFor(() => expect(result.current.loading).toBe(false));
      await act(async () => {
        await result.current.loadMore();
      });
      expect(result.current.items.map((i) => i.report_id)).toEqual(["r0", "r1"]);
      expect(result.current.hasMore).toBe(false);
    });

    it("removeOptimistic strips by report_id; restore re-adds", async () => {
      fetchMock.mockResolvedValueOnce(
        mockResponse({ items: [sampleItem(0), sampleItem(1)], page: 1, page_size: 50, has_more: false }),
      );
      const { result } = renderHook(() => useRepoList(EMPTY_FILTERS));
      await waitFor(() => expect(result.current.loading).toBe(false));
      act(() => result.current.removeOptimistic("r0"));
      expect(result.current.items.map((i) => i.report_id)).toEqual(["r1"]);
      act(() => result.current.restore(sampleItem(0)));
      expect(result.current.items.map((i) => i.report_id)).toEqual(["r0", "r1"]);
    });

    it("refetches when filters change", async () => {
      fetchMock
        .mockResolvedValueOnce(
          mockResponse({ items: [sampleItem(0)], page: 1, page_size: 50, has_more: false }),
        )
        .mockResolvedValueOnce(
          mockResponse({ items: [sampleItem(1)], page: 1, page_size: 50, has_more: false }),
        );
      const { result, rerender } = renderHook(({ f }) => useRepoList(f), {
        initialProps: { f: EMPTY_FILTERS },
      });
      await waitFor(() => expect(result.current.items).toHaveLength(1));
      rerender({ f: { ...EMPTY_FILTERS, q: "aapl" } });
      await waitFor(() => expect(result.current.items[0].report_id).toBe("r1"));
    });
  });
  ```

- [ ] **9.3 — Run**

  ```bash
  cd frontend && npx vitest run src/hooks/__tests__/useRepoList.test.ts
  ```
  Expected: all four tests pass.

- [ ] **9.4 — Commit**

  ```bash
  git add frontend/src/hooks/useRepoList.ts frontend/src/hooks/__tests__/useRepoList.test.ts
  git commit -m "feat(repo-ui): add useRepoList infinite-list hook"
  ```

---

### Task 10 — `RepoFilterBar` component + tests

- [ ] **10.1 — Create `frontend/src/components/repo/RepoFilterBar.tsx`**

  Exact content:
  ```tsx
  import { useRef, useState } from "react";
  import { Search, SlidersHorizontal, ChevronDown, Check } from "lucide-react";
  import type { RepoFilters } from "../../hooks/useRepoList";
  import type { RepoSort } from "../../api/repo";

  export interface DepartmentOption {
    slug: string;
    label: string;
    count: number;
  }

  export interface RepoFilterBarProps {
    filters: RepoFilters;
    departments: DepartmentOption[];
    onChange: (next: RepoFilters) => void;
  }

  const SORT_LABELS: Record<RepoSort, string> = {
    saved_desc: "Date Saved (newest)",
    saved_asc: "Date Saved (oldest)",
    generated_desc: "Date Generated (newest)",
    generated_asc: "Date Generated (oldest)",
    department_asc: "Department",
    filename_asc: "Filename",
  };

  const SORTS: RepoSort[] = [
    "saved_desc",
    "saved_asc",
    "generated_desc",
    "generated_asc",
    "department_asc",
    "filename_asc",
  ];

  export function RepoFilterBar({ filters, departments, onChange }: RepoFilterBarProps): JSX.Element {
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [sortOpen, setSortOpen] = useState(false);
    const [draft, setDraft] = useState<RepoFilters>(filters);
    const filtersBtn = useRef<HTMLButtonElement>(null);

    const anyActive =
      filters.departments.length > 0 ||
      !!filters.generatedFrom ||
      !!filters.generatedTo ||
      !!filters.savedFrom ||
      !!filters.savedTo;

    const openFilters = () => {
      setDraft(filters);
      setFiltersOpen(true);
    };

    const applyDraft = () => {
      onChange(draft);
      setFiltersOpen(false);
    };

    const toggleDepartment = (slug: string) => {
      setDraft((d) =>
        d.departments.includes(slug)
          ? { ...d, departments: d.departments.filter((x) => x !== slug) }
          : { ...d, departments: [...d.departments, slug] },
      );
    };

    return (
      <div className="flex flex-col">
        <div className="flex items-center gap-3 px-6 py-3 border-b border-[--color-border-subtle]">
          <div className="flex-1 relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[--color-text-tertiary]"
              aria-hidden
            />
            <input
              type="text"
              value={filters.q}
              onChange={(e) => onChange({ ...filters, q: e.target.value })}
              placeholder="Search reports..."
              aria-label="Search reports"
              className="w-full h-9 bg-[--color-bg-input] border border-[--color-border-subtle] rounded-[--radius-md] pl-8 pr-3 text-sm text-[--color-text-primary] placeholder:text-[--color-text-tertiary] focus:border-[--color-border-secondary] focus:outline-none"
            />
          </div>
          <button
            ref={filtersBtn}
            type="button"
            onClick={openFilters}
            aria-expanded={filtersOpen}
            aria-haspopup="dialog"
            className={`flex items-center gap-1.5 h-9 px-3 rounded-[--radius-md] border text-sm hover:bg-[--color-surface-hover] ${
              anyActive
                ? "border-[--color-accent-primary] text-[--color-accent-primary]"
                : "border-[--color-border-secondary] text-[--color-text-secondary]"
            }`}
          >
            <SlidersHorizontal size={14} aria-hidden />
            Filters
          </button>
        </div>
        <div className="flex items-center px-6 py-2">
          <div className="relative">
            <button
              type="button"
              onClick={() => setSortOpen((v) => !v)}
              className="flex items-center gap-1 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
              aria-haspopup="menu"
              aria-expanded={sortOpen}
            >
              <span>Sort: {SORT_LABELS[filters.sort]}</span>
              <ChevronDown size={12} aria-hidden />
            </button>
            {sortOpen ? (
              <ul
                role="menu"
                className="absolute left-0 mt-1 z-10 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] shadow-md py-1 min-w-[220px]"
              >
                {SORTS.map((s) => (
                  <li
                    key={s}
                    role="menuitemradio"
                    aria-checked={filters.sort === s}
                    tabIndex={0}
                    onClick={() => {
                      onChange({ ...filters, sort: s });
                      setSortOpen(false);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        onChange({ ...filters, sort: s });
                        setSortOpen(false);
                      }
                    }}
                    className={`flex items-center justify-between px-3 py-2 text-sm hover:bg-[--color-surface-hover] cursor-pointer ${
                      filters.sort === s
                        ? "text-[--color-accent-primary]"
                        : "text-[--color-text-primary]"
                    }`}
                  >
                    <span>{SORT_LABELS[s]}</span>
                    {filters.sort === s ? (
                      <Check size={14} className="text-[--color-accent-primary]" aria-hidden />
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
        {filtersOpen ? (
          <div
            role="dialog"
            aria-label="Filters"
            className="absolute right-6 top-24 z-20 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md p-4 w-[300px]"
          >
            <p className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] mb-2">
              Department
            </p>
            <div className="flex flex-col">
              {departments.map((d) => (
                <label
                  key={d.slug}
                  className="flex items-center gap-2 py-1.5 text-sm text-[--color-text-primary]"
                >
                  <input
                    type="checkbox"
                    checked={draft.departments.includes(d.slug)}
                    onChange={() => toggleDepartment(d.slug)}
                  />
                  <span>{d.label}</span>
                  <span className="ml-auto text-xs text-[--color-text-tertiary]">{d.count}</span>
                </label>
              ))}
              {departments.length === 0 ? (
                <span className="text-xs text-[--color-text-tertiary]">No saved reports yet</span>
              ) : null}
            </div>
            <p className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] mt-4 mb-2">
              Date Generated
            </p>
            <div className="flex items-center gap-2">
              <input
                type="date"
                aria-label="Generated from"
                value={draft.generatedFrom ?? ""}
                onChange={(e) =>
                  setDraft({ ...draft, generatedFrom: e.target.value || null })
                }
                className="h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm"
              />
              <input
                type="date"
                aria-label="Generated to"
                value={draft.generatedTo ?? ""}
                onChange={(e) =>
                  setDraft({ ...draft, generatedTo: e.target.value || null })
                }
                className="h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm"
              />
            </div>
            <p className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] mt-4 mb-2">
              Date Saved
            </p>
            <div className="flex items-center gap-2">
              <input
                type="date"
                aria-label="Saved from"
                value={draft.savedFrom ?? ""}
                onChange={(e) => setDraft({ ...draft, savedFrom: e.target.value || null })}
                className="h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm"
              />
              <input
                type="date"
                aria-label="Saved to"
                value={draft.savedTo ?? ""}
                onChange={(e) => setDraft({ ...draft, savedTo: e.target.value || null })}
                className="h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={applyDraft}
              className="h-8 px-3 rounded-[--radius-md] text-sm w-full mt-3 bg-[--color-accent-primary] text-white hover:opacity-90"
            >
              Apply
            </button>
          </div>
        ) : null}
      </div>
    );
  }
  ```

- [ ] **10.2 — Write `frontend/src/components/repo/__tests__/RepoFilterBar.test.tsx`**

  Exact content:
  ```tsx
  import { describe, expect, it, vi } from "vitest";
  import { fireEvent, render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { RepoFilterBar } from "../RepoFilterBar";
  import { EMPTY_FILTERS } from "../../../hooks/useRepoList";

  const depts = [
    { slug: "equity_research", label: "Equity Research", count: 2 },
    { slug: "secretary", label: "Secretary", count: 1 },
  ];

  describe("RepoFilterBar", () => {
    it("emits q on input", () => {
      const onChange = vi.fn();
      render(<RepoFilterBar filters={EMPTY_FILTERS} departments={depts} onChange={onChange} />);
      fireEvent.change(screen.getByPlaceholderText("Search reports..."), {
        target: { value: "aapl" },
      });
      expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ q: "aapl" }));
    });

    it("opens sort menu and picks an option", async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<RepoFilterBar filters={EMPTY_FILTERS} departments={depts} onChange={onChange} />);
      await user.click(screen.getByRole("button", { name: /Sort:/ }));
      await user.click(screen.getByRole("menuitemradio", { name: "Filename" }));
      expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ sort: "filename_asc" }));
    });

    it("opens filters dialog and applies department + date", async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<RepoFilterBar filters={EMPTY_FILTERS} departments={depts} onChange={onChange} />);
      await user.click(screen.getByRole("button", { name: /Filters/ }));
      await user.click(screen.getByLabelText("Equity Research", { selector: undefined }));
      fireEvent.change(screen.getByLabelText("Generated from"), {
        target: { value: "2026-04-01" },
      });
      await user.click(screen.getByRole("button", { name: "Apply" }));
      expect(onChange).toHaveBeenCalledWith(
        expect.objectContaining({ departments: ["equity_research"], generatedFrom: "2026-04-01" }),
      );
    });

    it("highlights Filters button when active", () => {
      render(
        <RepoFilterBar
          filters={{ ...EMPTY_FILTERS, departments: ["equity_research"] }}
          departments={depts}
          onChange={() => {}}
        />,
      );
      expect(screen.getByRole("button", { name: /Filters/ }).className).toContain(
        "--color-accent-primary",
      );
    });
  });
  ```

- [ ] **10.3 — Run**

  ```bash
  cd frontend && npx vitest run src/components/repo/__tests__/RepoFilterBar.test.tsx
  ```
  Expected: all pass.

- [ ] **10.4 — Commit**

  ```bash
  git add frontend/src/components/repo/RepoFilterBar.tsx frontend/src/components/repo/__tests__/RepoFilterBar.test.tsx
  git commit -m "feat(repo-ui): RepoFilterBar with search, department, dates, sort"
  ```

---

### Task 11 — `RepoFilterChips` + tests

- [ ] **11.1 — Create `frontend/src/components/repo/RepoFilterChips.tsx`**

  Exact content:
  ```tsx
  import { X } from "lucide-react";
  import type { RepoFilters } from "../../hooks/useRepoList";

  export interface RepoFilterChipsProps {
    filters: RepoFilters;
    departmentLabel: (slug: string) => string;
    onChange: (next: RepoFilters) => void;
  }

  export function RepoFilterChips({
    filters,
    departmentLabel,
    onChange,
  }: RepoFilterChipsProps): JSX.Element | null {
    const chips: { key: string; label: string; clear: () => void }[] = [];
    for (const slug of filters.departments) {
      chips.push({
        key: `dep:${slug}`,
        label: departmentLabel(slug),
        clear: () =>
          onChange({ ...filters, departments: filters.departments.filter((s) => s !== slug) }),
      });
    }
    if (filters.generatedFrom || filters.generatedTo) {
      const a = filters.generatedFrom ?? "…";
      const b = filters.generatedTo ?? "…";
      chips.push({
        key: "gen",
        label: `Generated: ${a} → ${b}`,
        clear: () => onChange({ ...filters, generatedFrom: null, generatedTo: null }),
      });
    }
    if (filters.savedFrom || filters.savedTo) {
      const a = filters.savedFrom ?? "…";
      const b = filters.savedTo ?? "…";
      chips.push({
        key: "saved",
        label: `Saved: ${a} → ${b}`,
        clear: () => onChange({ ...filters, savedFrom: null, savedTo: null }),
      });
    }
    if (chips.length === 0) return null;

    const clearAll = () =>
      onChange({
        ...filters,
        departments: [],
        generatedFrom: null,
        generatedTo: null,
        savedFrom: null,
        savedTo: null,
      });

    return (
      <div className="flex items-center flex-wrap gap-2 px-6 py-2 border-b border-[--color-border-subtle]">
        {chips.map((c) => (
          <span
            key={c.key}
            className="flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-[--color-accent-subtle] border border-[--color-accent-primary]/30 text-sm text-[--color-accent-primary]"
          >
            {c.label}
            <button
              type="button"
              aria-label={`Remove filter ${c.label}`}
              onClick={c.clear}
              className="flex items-center justify-center"
            >
              <X size={12} aria-hidden />
            </button>
          </span>
        ))}
        <button
          type="button"
          onClick={clearAll}
          className="text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] ml-auto"
        >
          Clear all
        </button>
      </div>
    );
  }
  ```

- [ ] **11.2 — Write `frontend/src/components/repo/__tests__/RepoFilterChips.test.tsx`**

  Exact content:
  ```tsx
  import { describe, expect, it, vi } from "vitest";
  import { render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { RepoFilterChips } from "../RepoFilterChips";
  import { EMPTY_FILTERS } from "../../../hooks/useRepoList";

  const label = (s: string) => ({ equity_research: "Equity Research" }[s] ?? s);

  describe("RepoFilterChips", () => {
    it("returns null when no active filters", () => {
      const { container } = render(
        <RepoFilterChips filters={EMPTY_FILTERS} departmentLabel={label} onChange={() => {}} />,
      );
      expect(container.firstChild).toBeNull();
    });

    it("renders a chip per active department", () => {
      render(
        <RepoFilterChips
          filters={{ ...EMPTY_FILTERS, departments: ["equity_research"] }}
          departmentLabel={label}
          onChange={() => {}}
        />,
      );
      expect(screen.getByText("Equity Research")).toBeInTheDocument();
    });

    it("clearing a single chip removes that filter only", async () => {
      const onChange = vi.fn();
      const user = userEvent.setup();
      render(
        <RepoFilterChips
          filters={{
            ...EMPTY_FILTERS,
            departments: ["equity_research"],
            generatedFrom: "2026-04-01",
          }}
          departmentLabel={label}
          onChange={onChange}
        />,
      );
      await user.click(screen.getByLabelText("Remove filter Equity Research"));
      expect(onChange).toHaveBeenCalledWith(
        expect.objectContaining({ departments: [], generatedFrom: "2026-04-01" }),
      );
    });

    it("Clear all resets every filter", async () => {
      const onChange = vi.fn();
      const user = userEvent.setup();
      render(
        <RepoFilterChips
          filters={{
            ...EMPTY_FILTERS,
            departments: ["equity_research"],
            generatedFrom: "2026-04-01",
            savedTo: "2026-04-30",
          }}
          departmentLabel={label}
          onChange={onChange}
        />,
      );
      await user.click(screen.getByRole("button", { name: "Clear all" }));
      expect(onChange).toHaveBeenCalledWith(
        expect.objectContaining({
          departments: [],
          generatedFrom: null,
          generatedTo: null,
          savedFrom: null,
          savedTo: null,
        }),
      );
    });
  });
  ```

- [ ] **11.3 — Run**

  ```bash
  cd frontend && npx vitest run src/components/repo/__tests__/RepoFilterChips.test.tsx
  ```
  Expected: all four tests pass.

- [ ] **11.4 — Commit**

  ```bash
  git add frontend/src/components/repo/RepoFilterChips.tsx frontend/src/components/repo/__tests__/RepoFilterChips.test.tsx
  git commit -m "feat(repo-ui): RepoFilterChips with per-chip + clear-all dismiss"
  ```

---

### Task 12 — `RepoListItem` + tests

- [ ] **12.1 — Create `frontend/src/components/repo/RepoListItem.tsx`**

  Exact content:
  ```tsx
  import { FileText, Download, Trash2 } from "lucide-react";
  import { motion } from "framer-motion";
  import type { RepoItem } from "../../api/repo";

  const DEPARTMENT_LABELS: Record<string, string> = {
    secretary: "Secretary",
    equity_research: "Equity Research",
    earnings_update: "Earnings Update",
    morning_briefing: "Morning Briefing",
    retail_sentiment: "Retail Sentiment",
    macro_research: "Macro Research",
    panic_thermometer: "Panic Thermometer",
  };

  const DEPARTMENT_BADGE_CLASS: Record<string, string> = {
    secretary: "bg-[--color-accent-subtle] text-[--color-accent-primary]",
    equity_research: "bg-[--color-info]/10 text-[--color-info]",
    earnings_update: "bg-[--color-success]/10 text-[--color-success]",
    morning_briefing: "bg-[--color-accent-subtle] text-[--color-accent-primary]",
    retail_sentiment: "bg-[--color-info]/10 text-[--color-info]",
    macro_research: "bg-[--color-warning]/10 text-[--color-warning]",
    panic_thermometer: "bg-[--color-warning]/10 text-[--color-warning]",
  };

  function fmtDate(iso: string): string {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  }

  export interface RepoListItemProps {
    item: RepoItem;
    onOpen: (item: RepoItem) => void;
    onDownload: (item: RepoItem) => void;
    onRemove: (item: RepoItem) => void;
    isRemoving?: boolean;
  }

  export function RepoListItem({
    item,
    onOpen,
    onDownload,
    onRemove,
    isRemoving = false,
  }: RepoListItemProps): JSX.Element {
    const depLabel = DEPARTMENT_LABELS[item.department] ?? item.department;
    const depBadge = DEPARTMENT_BADGE_CLASS[item.department] ?? "bg-[--color-surface-hover] text-[--color-text-secondary]";
    return (
      <motion.div
        role="listitem"
        layout
        initial={{ opacity: 1, height: "auto" }}
        animate={{ opacity: isRemoving ? 0 : 1, height: isRemoving ? 0 : "auto" }}
        transition={{ duration: 0.2 }}
        onClick={() => onOpen(item)}
        className="group flex items-center gap-4 px-4 py-3.5 hover:bg-[--color-surface-hover] cursor-pointer"
      >
        <FileText
          size={20}
          className="text-[--color-text-secondary] flex-shrink-0"
          aria-hidden
        />
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-base font-medium text-[--color-text-primary] truncate">
            {item.filename}
          </span>
          <span className="text-xs text-[--color-text-secondary] flex items-center gap-1.5 mt-0.5">
            <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${depBadge}`}>
              {depLabel}
            </span>
            <span>·</span>
            <span>Generated {fmtDate(item.generated_at)}</span>
            <span>·</span>
            <span>Saved {fmtDate(item.saved_at)}</span>
          </span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            aria-label={`Download ${item.filename}`}
            onClick={(e) => {
              e.stopPropagation();
              onDownload(item);
            }}
            className="w-7 h-7 rounded-[--radius-sm] flex items-center justify-center text-[--color-text-secondary] hover:bg-[--color-surface-active] hover:text-[--color-text-primary]"
          >
            <Download size={14} aria-hidden />
          </button>
          <button
            type="button"
            aria-label={`Remove ${item.filename}`}
            onClick={(e) => {
              e.stopPropagation();
              onRemove(item);
            }}
            className="w-7 h-7 rounded-[--radius-sm] flex items-center justify-center text-[--color-text-secondary] hover:text-[--color-feedback-error] hover:bg-[--color-feedback-error]/10"
          >
            <Trash2 size={14} aria-hidden />
          </button>
        </div>
      </motion.div>
    );
  }
  ```

- [ ] **12.2 — Write `frontend/src/components/repo/__tests__/RepoListItem.test.tsx`**

  Exact content:
  ```tsx
  import { describe, expect, it, vi } from "vitest";
  import { render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { RepoListItem } from "../RepoListItem";
  import type { RepoItem } from "../../../api/repo";

  const sample: RepoItem = {
    id: "i1",
    report_id: "r1",
    created_at: "2026-04-05T12:00:00Z",
    saved_at: "2026-04-05T12:00:00Z",
    generated_at: "2026-04-03T09:00:00Z",
    department: "equity_research",
    report_type: "equity_research_initiation",
    title: "AAPL-initiation-coverage",
    filename: "AAPL-initiation-coverage.pdf",
  };

  describe("RepoListItem", () => {
    it("renders filename + department label + dates", () => {
      render(
        <RepoListItem
          item={sample}
          onOpen={() => {}}
          onDownload={() => {}}
          onRemove={() => {}}
        />,
      );
      expect(screen.getByText("AAPL-initiation-coverage.pdf")).toBeInTheDocument();
      expect(screen.getByText("Equity Research")).toBeInTheDocument();
      expect(screen.getByText(/Generated /)).toBeInTheDocument();
      expect(screen.getByText(/Saved /)).toBeInTheDocument();
    });

    it("clicking the row fires onOpen", async () => {
      const onOpen = vi.fn();
      const user = userEvent.setup();
      render(
        <RepoListItem
          item={sample}
          onOpen={onOpen}
          onDownload={() => {}}
          onRemove={() => {}}
        />,
      );
      await user.click(screen.getByText("AAPL-initiation-coverage.pdf"));
      expect(onOpen).toHaveBeenCalledWith(sample);
    });

    it("download button does not bubble to row open", async () => {
      const onOpen = vi.fn();
      const onDownload = vi.fn();
      const user = userEvent.setup();
      render(
        <RepoListItem
          item={sample}
          onOpen={onOpen}
          onDownload={onDownload}
          onRemove={() => {}}
        />,
      );
      await user.click(screen.getByRole("button", { name: /Download / }));
      expect(onDownload).toHaveBeenCalledWith(sample);
      expect(onOpen).not.toHaveBeenCalled();
    });

    it("remove button fires onRemove", async () => {
      const onRemove = vi.fn();
      const user = userEvent.setup();
      render(
        <RepoListItem
          item={sample}
          onOpen={() => {}}
          onDownload={() => {}}
          onRemove={onRemove}
        />,
      );
      await user.click(screen.getByRole("button", { name: /Remove / }));
      expect(onRemove).toHaveBeenCalledWith(sample);
    });

    it("unknown department falls back to slug text", () => {
      render(
        <RepoListItem
          item={{ ...sample, department: "custom_x" }}
          onOpen={() => {}}
          onDownload={() => {}}
          onRemove={() => {}}
        />,
      );
      expect(screen.getByText("custom_x")).toBeInTheDocument();
    });
  });
  ```

- [ ] **12.3 — Run**

  ```bash
  cd frontend && npx vitest run src/components/repo/__tests__/RepoListItem.test.tsx
  ```
  Expected: all five tests pass.

- [ ] **12.4 — Commit**

  ```bash
  git add frontend/src/components/repo/RepoListItem.tsx frontend/src/components/repo/__tests__/RepoListItem.test.tsx
  git commit -m "feat(repo-ui): RepoListItem row with open/download/remove actions"
  ```

---

### Task 13 — `RepoListSkeleton` + `RepoEmptyState` + tests

- [ ] **13.1 — Create `frontend/src/components/repo/RepoListSkeleton.tsx`**

  ```tsx
  export function RepoListSkeleton(): JSX.Element {
    const widths = ["40%", "55%", "35%", "50%", "42%", "48%", "38%", "52%"];
    return (
      <div
        role="status"
        aria-label="Loading reports"
        className="border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden mx-6 my-2 divide-y divide-[--color-border-subtle]"
      >
        {widths.map((w, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3.5">
            <div className="w-5 h-5 rounded bg-[--color-surface-hover] animate-pulse" />
            <div className="flex flex-col flex-1 gap-1.5">
              <div
                className="h-4 rounded bg-[--color-surface-hover] animate-pulse"
                style={{ width: w }}
              />
              <div className="h-3 rounded bg-[--color-surface-hover] animate-pulse w-48" />
            </div>
          </div>
        ))}
      </div>
    );
  }
  ```

- [ ] **13.2 — Create `frontend/src/components/repo/RepoEmptyState.tsx`**

  ```tsx
  import { BookOpen, SearchX } from "lucide-react";

  export interface RepoEmptyStateProps {
    variant: "no-saved" | "no-match";
    onClearFilters?: () => void;
  }

  export function RepoEmptyState({
    variant,
    onClearFilters,
  }: RepoEmptyStateProps): JSX.Element {
    if (variant === "no-saved") {
      return (
        <div className="flex flex-col items-center justify-center flex-1 gap-3 text-center px-6 py-16">
          <BookOpen size={40} className="text-[--color-text-tertiary]" aria-hidden />
          <p className="text-base font-medium text-[--color-text-primary]">
            No saved reports yet.
          </p>
          <p className="text-sm text-[--color-text-secondary]">
            Save a report from any department to see it here.
          </p>
        </div>
      );
    }
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-3 text-center px-6 py-16">
        <SearchX size={40} className="text-[--color-text-tertiary]" aria-hidden />
        <p className="text-base font-medium text-[--color-text-primary]">
          No reports match your search.
        </p>
        <p className="text-sm text-[--color-text-secondary]">
          Try adjusting your filters or search terms.
        </p>
        {onClearFilters ? (
          <button
            type="button"
            onClick={onClearFilters}
            className="text-sm text-[--color-accent-primary] hover:underline"
          >
            Clear filters
          </button>
        ) : null}
      </div>
    );
  }
  ```

- [ ] **13.3 — Write `frontend/src/components/repo/__tests__/RepoEmptyState.test.tsx`**

  ```tsx
  import { describe, expect, it, vi } from "vitest";
  import { render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { RepoEmptyState } from "../RepoEmptyState";

  describe("RepoEmptyState", () => {
    it("renders the no-saved variant", () => {
      render(<RepoEmptyState variant="no-saved" />);
      expect(screen.getByText("No saved reports yet.")).toBeInTheDocument();
    });

    it("renders the no-match variant with a Clear filters action", async () => {
      const onClear = vi.fn();
      const user = userEvent.setup();
      render(<RepoEmptyState variant="no-match" onClearFilters={onClear} />);
      await user.click(screen.getByRole("button", { name: "Clear filters" }));
      expect(onClear).toHaveBeenCalled();
    });

    it("no-match without onClearFilters hides the button", () => {
      render(<RepoEmptyState variant="no-match" />);
      expect(screen.queryByRole("button", { name: "Clear filters" })).toBeNull();
    });
  });
  ```

- [ ] **13.4 — Run**

  ```bash
  cd frontend && npx vitest run src/components/repo/__tests__/RepoEmptyState.test.tsx
  ```
  Expected: 3 passed.

- [ ] **13.5 — Commit**

  ```bash
  git add frontend/src/components/repo/RepoListSkeleton.tsx frontend/src/components/repo/RepoEmptyState.tsx frontend/src/components/repo/__tests__/RepoEmptyState.test.tsx
  git commit -m "feat(repo-ui): RepoListSkeleton + RepoEmptyState variants"
  ```

---

### Task 14 — `RemoveConfirmDialog` + tests

- [ ] **14.1 — Create `frontend/src/components/repo/RemoveConfirmDialog.tsx`**

  ```tsx
  import { useEffect, useRef } from "react";
  import { X } from "lucide-react";

  export interface RemoveConfirmDialogProps {
    filename: string | null;
    onCancel: () => void;
    onConfirm: () => void;
  }

  export function RemoveConfirmDialog({
    filename,
    onCancel,
    onConfirm,
  }: RemoveConfirmDialogProps): JSX.Element | null {
    const confirmRef = useRef<HTMLButtonElement>(null);
    useEffect(() => {
      if (filename) confirmRef.current?.focus();
    }, [filename]);
    useEffect(() => {
      if (!filename) return;
      const onKey = (e: KeyboardEvent) => {
        if (e.key === "Escape") onCancel();
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [filename, onCancel]);

    if (!filename) return null;
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        onClick={onCancel}
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Remove from Repository"
          className="bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-lg border border-[--color-border-subtle] max-w-[400px] w-full p-6"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start justify-between">
            <h2 className="text-base font-semibold text-[--color-text-primary]">
              Remove from Repository?
            </h2>
            <button
              type="button"
              aria-label="Close"
              onClick={onCancel}
              className="text-[--color-text-tertiary] hover:text-[--color-text-primary]"
            >
              <X size={16} aria-hidden />
            </button>
          </div>
          <p className="mt-3 text-sm text-[--color-text-secondary]">
            <span className="font-medium text-[--color-text-primary]">"{filename}"</span>{" "}
            will be removed from your Repository.
          </p>
          <div className="mt-6 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="h-9 px-4 rounded-[--radius-md] border border-[--color-border-secondary] text-sm text-[--color-text-secondary]"
            >
              Cancel
            </button>
            <button
              ref={confirmRef}
              type="button"
              onClick={onConfirm}
              className="h-9 px-4 rounded-[--radius-md] bg-[--color-feedback-error] text-white text-sm font-medium hover:opacity-90"
            >
              Remove
            </button>
          </div>
        </div>
      </div>
    );
  }
  ```

- [ ] **14.2 — Write `frontend/src/components/repo/__tests__/RemoveConfirmDialog.test.tsx`**

  ```tsx
  import { describe, expect, it, vi } from "vitest";
  import { render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { RemoveConfirmDialog } from "../RemoveConfirmDialog";

  describe("RemoveConfirmDialog", () => {
    it("renders nothing when filename is null", () => {
      const { container } = render(
        <RemoveConfirmDialog filename={null} onCancel={() => {}} onConfirm={() => {}} />,
      );
      expect(container.firstChild).toBeNull();
    });

    it("renders the filename + Cancel + Remove buttons", () => {
      render(
        <RemoveConfirmDialog
          filename="q1-briefing.pdf"
          onCancel={() => {}}
          onConfirm={() => {}}
        />,
      );
      expect(screen.getByText('"q1-briefing.pdf"', { exact: false })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
    });

    it("clicking Remove fires onConfirm", async () => {
      const onConfirm = vi.fn();
      const user = userEvent.setup();
      render(
        <RemoveConfirmDialog
          filename="f.pdf"
          onCancel={() => {}}
          onConfirm={onConfirm}
        />,
      );
      await user.click(screen.getByRole("button", { name: "Remove" }));
      expect(onConfirm).toHaveBeenCalled();
    });

    it("clicking Cancel fires onCancel", async () => {
      const onCancel = vi.fn();
      const user = userEvent.setup();
      render(
        <RemoveConfirmDialog
          filename="f.pdf"
          onCancel={onCancel}
          onConfirm={() => {}}
        />,
      );
      await user.click(screen.getByRole("button", { name: "Cancel" }));
      expect(onCancel).toHaveBeenCalled();
    });

    it("Escape fires onCancel", async () => {
      const onCancel = vi.fn();
      const user = userEvent.setup();
      render(
        <RemoveConfirmDialog
          filename="f.pdf"
          onCancel={onCancel}
          onConfirm={() => {}}
        />,
      );
      await user.keyboard("{Escape}");
      expect(onCancel).toHaveBeenCalled();
    });
  });
  ```

- [ ] **14.3 — Run**

  ```bash
  cd frontend && npx vitest run src/components/repo/__tests__/RemoveConfirmDialog.test.tsx
  ```
  Expected: 5 passed.

- [ ] **14.4 — Commit**

  ```bash
  git add frontend/src/components/repo/RemoveConfirmDialog.tsx frontend/src/components/repo/__tests__/RemoveConfirmDialog.test.tsx
  git commit -m "feat(repo-ui): RemoveConfirmDialog modal"
  ```

---

### Task 15 — `UndoToast` + tests

- [ ] **15.1 — Create `frontend/src/components/repo/UndoToast.tsx`**

  ```tsx
  import { useEffect, useRef } from "react";
  import { AnimatePresence, motion } from "framer-motion";

  export type ToastKind = "info" | "success" | "error";

  export interface ToastSpec {
    id: string;
    message: string;
    kind?: ToastKind;
    durationMs: number;
    undoLabel?: string;
    onUndo?: () => void;
  }

  export interface UndoToastProps {
    toast: ToastSpec | null;
    onDismiss: (id: string) => void;
  }

  export function UndoToast({ toast, onDismiss }: UndoToastProps): JSX.Element {
    const timerRef = useRef<number | null>(null);
    useEffect(() => {
      if (!toast) return;
      timerRef.current = window.setTimeout(() => onDismiss(toast.id), toast.durationMs);
      return () => {
        if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      };
    }, [toast, onDismiss]);

    return (
      <AnimatePresence>
        {toast ? (
          <motion.div
            key={toast.id}
            role="status"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className={`fixed bottom-4 right-4 z-50 flex items-center gap-3 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md px-4 py-3 text-sm ${
              toast.kind === "error"
                ? "text-[--color-feedback-error]"
                : "text-[--color-text-primary]"
            }`}
          >
            <span>{toast.message}</span>
            {toast.undoLabel && toast.onUndo ? (
              <button
                type="button"
                onClick={() => {
                  toast.onUndo?.();
                  onDismiss(toast.id);
                }}
                className="text-[--color-accent-primary] hover:underline"
              >
                {toast.undoLabel}
              </button>
            ) : null}
          </motion.div>
        ) : null}
      </AnimatePresence>
    );
  }
  ```

- [ ] **15.2 — Write `frontend/src/components/repo/__tests__/UndoToast.test.tsx`**

  ```tsx
  import { describe, expect, it, vi } from "vitest";
  import { act, render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { UndoToast, type ToastSpec } from "../UndoToast";

  const baseToast: ToastSpec = {
    id: "t1",
    message: "Removed from Repository",
    durationMs: 4000,
    undoLabel: "Undo",
    onUndo: () => {},
  };

  describe("UndoToast", () => {
    it("renders the message and the Undo button", () => {
      render(<UndoToast toast={baseToast} onDismiss={() => {}} />);
      expect(screen.getByText("Removed from Repository")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
    });

    it("auto-dismisses after durationMs", () => {
      vi.useFakeTimers();
      const onDismiss = vi.fn();
      render(<UndoToast toast={baseToast} onDismiss={onDismiss} />);
      act(() => {
        vi.advanceTimersByTime(4000);
      });
      expect(onDismiss).toHaveBeenCalledWith("t1");
      vi.useRealTimers();
    });

    it("clicking Undo fires onUndo + onDismiss", async () => {
      const onUndo = vi.fn();
      const onDismiss = vi.fn();
      const user = userEvent.setup();
      render(
        <UndoToast toast={{ ...baseToast, onUndo }} onDismiss={onDismiss} />,
      );
      await user.click(screen.getByRole("button", { name: "Undo" }));
      expect(onUndo).toHaveBeenCalled();
      expect(onDismiss).toHaveBeenCalledWith("t1");
    });

    it("toast = null renders nothing", () => {
      const { container } = render(<UndoToast toast={null} onDismiss={() => {}} />);
      expect(container.textContent ?? "").toBe("");
    });
  });
  ```

- [ ] **15.3 — Run**

  ```bash
  cd frontend && npx vitest run src/components/repo/__tests__/UndoToast.test.tsx
  ```
  Expected: 4 passed.

- [ ] **15.4 — Commit**

  ```bash
  git add frontend/src/components/repo/UndoToast.tsx frontend/src/components/repo/__tests__/UndoToast.test.tsx
  git commit -m "feat(repo-ui): UndoToast with auto-dismiss + Undo action"
  ```

---

### Task 16 — `Repository` page composition + tests

- [ ] **16.1 — Rewrite `frontend/src/pages/Repository.tsx`**

  Exact content:
  ```tsx
  import { useCallback, useEffect, useMemo, useRef, useState } from "react";
  import { useSearchParams } from "react-router-dom";
  import { RepoFilterBar, type DepartmentOption } from "../components/repo/RepoFilterBar";
  import { RepoFilterChips } from "../components/repo/RepoFilterChips";
  import { RepoListItem } from "../components/repo/RepoListItem";
  import { RepoListSkeleton } from "../components/repo/RepoListSkeleton";
  import { RepoEmptyState } from "../components/repo/RepoEmptyState";
  import { RemoveConfirmDialog } from "../components/repo/RemoveConfirmDialog";
  import { UndoToast, type ToastSpec } from "../components/repo/UndoToast";
  import { useRepoList, EMPTY_FILTERS, type RepoFilters } from "../hooks/useRepoList";
  import {
    getRepoFacets,
    saveToRepo,
    unsaveFromRepo,
    type RepoItem,
    type RepoSort,
  } from "../api/repo";
  import { reportPdfUrl } from "../api/reports";
  import { useFileViewer } from "../components/viewer/FileViewerContext";

  const DEPARTMENT_LABELS: Record<string, string> = {
    secretary: "Secretary",
    equity_research: "Equity Research",
    earnings_update: "Earnings Update",
    morning_briefing: "Morning Briefing",
    retail_sentiment: "Retail Sentiment",
    macro_research: "Macro Research",
    panic_thermometer: "Panic Thermometer",
  };

  const VALID_SORTS: ReadonlySet<RepoSort> = new Set<RepoSort>([
    "saved_desc",
    "saved_asc",
    "generated_desc",
    "generated_asc",
    "department_asc",
    "filename_asc",
  ]);

  function readFiltersFromSearch(sp: URLSearchParams): RepoFilters {
    const deps = sp.getAll("department").filter(Boolean);
    const rawSort = sp.get("sort");
    const sort: RepoSort = rawSort && VALID_SORTS.has(rawSort as RepoSort)
      ? (rawSort as RepoSort)
      : "saved_desc";
    return {
      q: sp.get("q") ?? "",
      departments: deps,
      generatedFrom: sp.get("generated_from"),
      generatedTo: sp.get("generated_to"),
      savedFrom: sp.get("saved_from"),
      savedTo: sp.get("saved_to"),
      sort,
    };
  }

  function writeFiltersToSearch(f: RepoFilters): URLSearchParams {
    const sp = new URLSearchParams();
    if (f.q) sp.set("q", f.q);
    for (const d of f.departments) sp.append("department", d);
    if (f.generatedFrom) sp.set("generated_from", f.generatedFrom);
    if (f.generatedTo) sp.set("generated_to", f.generatedTo);
    if (f.savedFrom) sp.set("saved_from", f.savedFrom);
    if (f.savedTo) sp.set("saved_to", f.savedTo);
    if (f.sort && f.sort !== "saved_desc") sp.set("sort", f.sort);
    return sp;
  }

  export default function Repository(): JSX.Element {
    const [searchParams, setSearchParams] = useSearchParams();
    const filters = useMemo(() => readFiltersFromSearch(searchParams), [searchParams]);
    const setFilters = useCallback(
      (next: RepoFilters) => setSearchParams(writeFiltersToSearch(next), { replace: true }),
      [setSearchParams],
    );

    const { items, hasMore, loading, loadingMore, error, loadMore, removeOptimistic, restore } =
      useRepoList(filters);

    const [facets, setFacets] = useState<DepartmentOption[]>([]);
    useEffect(() => {
      let cancelled = false;
      getRepoFacets()
        .then((f) => {
          if (cancelled) return;
          setFacets(
            f.departments.map((d) => ({
              slug: d.slug,
              label: DEPARTMENT_LABELS[d.slug] ?? d.slug,
              count: d.count,
            })),
          );
        })
        .catch(() => {
          /* swallow — facets are optional */
        });
      return () => {
        cancelled = true;
      };
    }, [items.length]);

    const [pendingRemove, setPendingRemove] = useState<RepoItem | null>(null);
    const [toast, setToast] = useState<ToastSpec | null>(null);
    const toastSeq = useRef(0);

    const { open: openViewer } = useFileViewer();

    const onOpen = useCallback(
      (item: RepoItem) => {
        openViewer({
          filename: item.filename,
          kind: "markdown",
          metadata: `${DEPARTMENT_LABELS[item.department] ?? item.department} · Generated ${
            new Date(item.generated_at).toLocaleDateString()
          }`,
          source: { kind: "report", reportId: item.report_id },
          initialSaved: true,
        });
      },
      [openViewer],
    );

    const onDownload = useCallback((item: RepoItem) => {
      const a = document.createElement("a");
      a.href = reportPdfUrl(item.report_id);
      a.rel = "noopener";
      a.download = item.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }, []);

    const doRemove = useCallback(
      async (item: RepoItem) => {
        setPendingRemove(null);
        removeOptimistic(item.report_id);
        try {
          await unsaveFromRepo(item.report_id);
          const id = `toast-${++toastSeq.current}`;
          setToast({
            id,
            message: "Removed from Repository",
            durationMs: 4000,
            undoLabel: "Undo",
            onUndo: async () => {
              try {
                await saveToRepo(item.report_id);
                restore(item);
                setToast({
                  id: `toast-${++toastSeq.current}`,
                  message: "Report restored.",
                  durationMs: 2000,
                });
              } catch (e) {
                setToast({
                  id: `toast-${++toastSeq.current}`,
                  message: "Failed to restore. Try again.",
                  kind: "error",
                  durationMs: 4000,
                });
              }
            },
          });
        } catch (e) {
          restore(item);
          setToast({
            id: `toast-${++toastSeq.current}`,
            message: "Failed to remove. Try again.",
            kind: "error",
            durationMs: 4000,
          });
        }
      },
      [removeOptimistic, restore],
    );

    const sentinelRef = useRef<HTMLDivElement | null>(null);
    useEffect(() => {
      const el = sentinelRef.current;
      if (!el) return;
      const io = new IntersectionObserver(
        (entries) => {
          for (const e of entries) {
            if (e.isIntersecting && hasMore && !loading && !loadingMore) {
              void loadMore();
            }
          }
        },
        { rootMargin: "200px" },
      );
      io.observe(el);
      return () => io.disconnect();
    }, [hasMore, loading, loadingMore, loadMore]);

    const chipsLabel = useCallback(
      (slug: string) => DEPARTMENT_LABELS[slug] ?? slug,
      [],
    );

    const anyFilter =
      filters.q !== "" ||
      filters.departments.length > 0 ||
      !!filters.generatedFrom ||
      !!filters.generatedTo ||
      !!filters.savedFrom ||
      !!filters.savedTo;

    return (
      <div className="flex flex-col flex-1 min-w-0">
        <header className="h-14 flex-shrink-0 flex items-center px-6 border-b border-[--color-border-subtle] bg-[--color-bg-base]">
          <h1 className="text-xl font-semibold text-[--color-text-primary]">Repository</h1>
        </header>
        <RepoFilterBar
          filters={filters}
          departments={facets}
          onChange={setFilters}
        />
        <RepoFilterChips
          filters={filters}
          departmentLabel={chipsLabel}
          onChange={setFilters}
        />
        <div className="flex-1 overflow-y-auto" data-testid="repo-scroll-container">
          {loading ? (
            <RepoListSkeleton />
          ) : error ? (
            <div className="px-6 py-16 text-center text-sm text-[--color-feedback-error]">
              Failed to load: {error}
            </div>
          ) : items.length === 0 ? (
            <RepoEmptyState
              variant={anyFilter ? "no-match" : "no-saved"}
              onClearFilters={anyFilter ? () => setFilters(EMPTY_FILTERS) : undefined}
            />
          ) : (
            <>
              <div
                role="list"
                className="border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden mx-6 my-2 divide-y divide-[--color-border-subtle]"
              >
                {items.map((i) => (
                  <RepoListItem
                    key={i.id}
                    item={i}
                    onOpen={onOpen}
                    onDownload={onDownload}
                    onRemove={setPendingRemove}
                  />
                ))}
              </div>
              <div ref={sentinelRef} />
              {loadingMore ? (
                <div className="flex justify-center py-4 gap-1" aria-label="Loading more">
                  <span className="w-1.5 h-1.5 bg-[--color-text-tertiary] rounded-full animate-pulse" />
                  <span className="w-1.5 h-1.5 bg-[--color-text-tertiary] rounded-full animate-pulse [animation-delay:120ms]" />
                  <span className="w-1.5 h-1.5 bg-[--color-text-tertiary] rounded-full animate-pulse [animation-delay:240ms]" />
                </div>
              ) : !hasMore ? (
                <div className="text-xs text-[--color-text-tertiary] text-center py-4">
                  All reports loaded
                </div>
              ) : null}
            </>
          )}
        </div>
        <RemoveConfirmDialog
          filename={pendingRemove?.filename ?? null}
          onCancel={() => setPendingRemove(null)}
          onConfirm={() => pendingRemove && void doRemove(pendingRemove)}
        />
        <UndoToast toast={toast} onDismiss={() => setToast(null)} />
      </div>
    );
  }
  ```

- [ ] **16.2 — Write `frontend/src/pages/__tests__/Repository.test.tsx`**

  Exact content:
  ```tsx
  import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
  import { render, screen, waitFor } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { MemoryRouter } from "react-router-dom";
  import Repository from "../Repository";
  import { FileViewerProvider } from "../../components/viewer/FileViewerContext";

  function mockResponse(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  }

  const fetchMock = vi.fn();

  function renderPage(url = "/repository") {
    return render(
      <MemoryRouter initialEntries={[url]}>
        <FileViewerProvider>
          <Repository />
        </FileViewerProvider>
      </MemoryRouter>,
    );
  }

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const item = (overrides: Partial<Record<string, string>> = {}) => ({
    id: "i1",
    report_id: "r1",
    created_at: "2026-04-05T12:00:00Z",
    saved_at: "2026-04-05T12:00:00Z",
    generated_at: "2026-04-03T09:00:00Z",
    department: "equity_research",
    report_type: "equity_research_initiation",
    title: "AAPL-initiation",
    filename: "AAPL-initiation.pdf",
    ...overrides,
  });

  describe("Repository page", () => {
    it("renders the empty state when there are no saved reports", async () => {
      fetchMock.mockImplementation((url: string) => {
        if (url.startsWith("/api/repo/items"))
          return Promise.resolve(
            mockResponse({ items: [], page: 1, page_size: 50, has_more: false }),
          );
        if (url === "/api/repo/facets")
          return Promise.resolve(mockResponse({ departments: [], total: 0 }));
        return Promise.reject(new Error(`unmocked ${url}`));
      });
      renderPage();
      expect(await screen.findByText("No saved reports yet.")).toBeInTheDocument();
    });

    it("renders a list and applies a search filter via URL", async () => {
      fetchMock.mockImplementation((url: string) => {
        if (url.startsWith("/api/repo/items")) {
          const u = new URL("http://x" + url.replace("/api", ""));
          if (u.searchParams.get("q") === "aapl")
            return Promise.resolve(
              mockResponse({
                items: [item({ title: "AAPL-initiation", filename: "AAPL-initiation.pdf" })],
                page: 1,
                page_size: 50,
                has_more: false,
              }),
            );
          return Promise.resolve(
            mockResponse({ items: [], page: 1, page_size: 50, has_more: false }),
          );
        }
        if (url === "/api/repo/facets")
          return Promise.resolve(
            mockResponse({
              departments: [{ slug: "equity_research", count: 1 }],
              total: 1,
            }),
          );
        return Promise.reject(new Error(`unmocked ${url}`));
      });
      renderPage("/repository?q=aapl");
      expect(await screen.findByText("AAPL-initiation.pdf")).toBeInTheDocument();
    });

    it("remove flow: confirm → optimistic remove → success toast with Undo", async () => {
      let removed = false;
      fetchMock.mockImplementation((url: string, init?: RequestInit) => {
        if (url.startsWith("/api/repo/items") && (!init || init.method === undefined || init.method === "GET")) {
          const items = removed ? [] : [item({ filename: "x.pdf" })];
          return Promise.resolve(
            mockResponse({ items, page: 1, page_size: 50, has_more: false }),
          );
        }
        if (url === "/api/repo/facets")
          return Promise.resolve(mockResponse({ departments: [], total: 0 }));
        if (init?.method === "DELETE" && url.startsWith("/api/repo/items?")) {
          removed = true;
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        return Promise.reject(new Error(`unmocked ${url} ${init?.method}`));
      });
      const user = userEvent.setup();
      renderPage();
      await screen.findByText("x.pdf");
      await user.click(screen.getByRole("button", { name: /Remove x.pdf/ }));
      await user.click(screen.getByRole("button", { name: "Remove" }));
      expect(await screen.findByText("Removed from Repository")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
      await waitFor(() => expect(screen.queryByText("x.pdf")).toBeNull());
    });

    it("download button triggers an anchor click to the PDF URL", async () => {
      fetchMock.mockImplementation((url: string) => {
        if (url.startsWith("/api/repo/items"))
          return Promise.resolve(
            mockResponse({ items: [item({ filename: "y.pdf" })], page: 1, page_size: 50, has_more: false }),
          );
        if (url === "/api/repo/facets")
          return Promise.resolve(mockResponse({ departments: [], total: 0 }));
        return Promise.reject(new Error(`unmocked ${url}`));
      });
      const user = userEvent.setup();
      const createEl = document.createElement.bind(document);
      const spy = vi.spyOn(document, "createElement");
      spy.mockImplementation((tag: string) => {
        const el = createEl(tag);
        if (tag === "a") {
          (el as HTMLAnchorElement).click = vi.fn();
        }
        return el as HTMLElement;
      });
      renderPage();
      await screen.findByText("y.pdf");
      await user.click(screen.getByRole("button", { name: /Download y.pdf/ }));
      const anchorCalls = spy.mock.calls.filter(([t]) => t === "a");
      expect(anchorCalls.length).toBeGreaterThanOrEqual(1);
      spy.mockRestore();
    });
  });
  ```

- [ ] **16.3 — Run**

  ```bash
  cd frontend && npx vitest run src/pages/__tests__/Repository.test.tsx
  ```
  Expected: all 4 tests pass.

- [ ] **16.4 — Commit**

  ```bash
  git add frontend/src/pages/Repository.tsx frontend/src/pages/__tests__/Repository.test.tsx
  git commit -m "feat(repo-ui): Repository page composition + integration tests"
  ```

---

### Task 17 — Route registration + sidebar verification

- [ ] **17.1 — Verify `Repository` is already wired into the router**

  ```bash
  grep -n "Repository" frontend/src/App.tsx frontend/src/main.tsx 2>/dev/null
  ```
  Expected: at least one import + route entry `<Route path="/repository" element={<Repository />} />` from Plan 8.
  If missing, add under the main authenticated route group in `frontend/src/App.tsx`:
  ```tsx
  import Repository from "./pages/Repository";
  // ...
  <Route path="/repository" element={<Repository />} />
  ```

- [ ] **17.2 — Verify the sidebar link targets `/repository`**

  ```bash
  grep -rn "'/repository'" frontend/src/components/sidebar 2>/dev/null
  ```
  Expected: a sidebar entry referencing `/repository` (shipped by Plan 8). If missing, append one to `frontend/src/components/sidebar/Sidebar.tsx` under the utility section (icon: `BookOpen`, label: "Repository").

- [ ] **17.3 — Verify `FileViewerProvider` wraps the authenticated shell**

  ```bash
  grep -n "FileViewerProvider" frontend/src/App.tsx frontend/src/main.tsx 2>/dev/null
  ```
  Expected: at least one match. Without the provider, `useFileViewer()` inside the page throws. Plan 12 is responsible for wiring this — if not present, escalate before proceeding.

- [ ] **17.4 — Commit (only if edits were needed)**

  If App.tsx or Sidebar.tsx were modified:
  ```bash
  git add frontend/src/App.tsx frontend/src/components/sidebar/Sidebar.tsx
  git commit -m "feat(repo-ui): wire Repository route + sidebar link"
  ```
  Otherwise skip — bookkeeping only.

---

### Task 18 — Full aggregate suite + ruff + PR

- [ ] **18.1 — Backend: ruff + format + pytest (full aggregate)**

  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest -q
  ```
  Expected: all green. Fix any cross-module collisions before proceeding.

- [ ] **18.2 — Frontend: vitest + tsc + build**

  ```bash
  cd frontend && npx vitest run && npx tsc --noEmit && npm run build
  ```
  Expected: tests pass, typecheck clean, build succeeds.

- [ ] **18.3 — Update the plan-status table**

  Edit `planning/implementation-plans/README.md`, change the Plan 22 row's status from `Not started` to `Done` with today's merge date.

- [ ] **18.4 — Commit + PR**

  ```bash
  git add planning/implementation-plans/README.md
  git commit -m "docs(plan-22): mark Repository page Done"
  git push -u origin feat/phase-22-repository
  gh pr create --title "feat(phase-22): Repository page" --body "$(cat <<'EOF'
  ## Summary
  - Extends GET /repo/items with filter/sort/pagination and adds GET /repo/facets.
  - Ships the Repository browsing page: search, filters, chips, sort dropdown, infinite scroll, FileViewer open, download, remove-with-confirmation, undo toast.
  - Contract + authorization matrices updated.

  ## Test plan
  - [x] uv run ruff check .
  - [x] uv run ruff format --check .
  - [x] uv run pytest -q
  - [x] cd frontend && npx vitest run
  - [x] cd frontend && npx tsc --noEmit
  - [x] cd frontend && npm run build
  EOF
  )"
  ```

- [ ] **18.5 — Wait for CI green, then squash-merge**

  Expected: `CI / Python — lint + test` and `CI / Frontend — test + build` both green. Merge via GitHub UI. No force-push; no skipping hooks.

---

## Post-merge checklist

1. Status table in `planning/implementation-plans/README.md` shows Plan 22 `Done (YYYY-MM-DD)`.
2. The Repository page is reachable at `/repository` with a sidebar link.
3. Saving a report from any department page (Plan 12 `SaveToRepoButton`) surfaces the row on the Repository page within one reload.
4. `uv run pytest -q` and `cd frontend && npx vitest run` stay green on `main`.

## Out-of-scope (explicit)

- **Tags.** Not in the spec. No DB column, API, or UI.
- **Archive / soft delete.** Not in the spec. Removal is a hard delete of the `repo_items` row; the underlying `reports` row persists (managed by Plan 13's `/reports/{id}` DELETE, which is a separate user action).
- **Bulk select + bulk remove.** Not in the spec.
- **Item metadata edit (title, note).** Not in the spec.
- **Grid view toggle.** The spec only shows a list with thumbnails; a grid view can be added later without schema changes.
- **Server-side SSE / realtime.** The Repo page is a pure GET/DELETE surface. Cross-tab freshness relies on page revisit; no `/repo/stream` endpoint.
- **`/repo/stats` endpoint.** The scope brief mentioned counts by month — not in the spec. `/repo/facets` covers the minimal "counts by department" the Filters panel needs; month buckets can be added in a follow-up if the sidebar ever grows a timeline widget.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Widening `RepoItemOut` breaks Plan 12 contract consumers | Low | Additive-only: `id`, `report_id`, `created_at` remain. Plan 12 tests re-run in Task 4.3. |
| Filter combinatorics cause slow queries at scale | Low | `ix_repo_items_user_id_created_at` index covers the default sort; all filters are `AND` on indexed columns (`Report.department`, `Report.created_at`, `RepoItem.created_at`). Page size capped at 200. |
| URL-driven filter state collides with back/forward | Low | `setSearchParams({...}, { replace: true })` used so typing in the search box doesn't spam history. Sort and filter dialog `Apply` are also `replace: true`. |
| Undo window loses the original `RepoItem` payload | Low | The `onUndo` closure captures the full item before dispatch; on undo, `restore(item)` re-inserts it client-side and the next reload will re-sync anyway. |
| `fetch` in test environments returns the mocked response without a JSON `content-type` | Low | `mockResponse` sets `content-type: application/json` explicitly; `fetchJson` parses strictly. |
| PDF download route rejected because browser launcher not configured | Medium | Plan 13's `/reports/{id}/export/pdf` returns 503 in that case. The page's download click receives the HTTP error via the browser navigation, not a page-level toast — consistent with department pages. A follow-up Plan 23 acceptance check ensures Playwright/Chromium is provisioned. |

---

## Notes for the executing agent

- Every task ends with either a green `pytest`/`vitest` run or a documented "no-op bookkeeping" tag. Never commit failing tests except in the deliberate "test first, red" steps (Tasks 1, 3, 5 first halves).
- Use `str(uuid.uuid4())` for every new `String(36)` id. No prefixed short-hex ids.
- No new DB migration is needed — `repo_items` ships from Plan 12 Task 0 with the exact columns Plan 22 reads and writes.
- If the pre-existing `test_repo_routes.py` breaks because of the widened `RepoItemOut`, extend the assertion to tolerate the new keys (`saved_at`, `generated_at`, `department`, `report_type`, `title`, `filename`) — do not strip them from the route response.
- Keep the Repository page free of emojis, filler words, and any non-English copy.
