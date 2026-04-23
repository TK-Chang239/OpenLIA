# Shared Chat Components Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Audit 2026-04-20 normalizations (apply before executing this plan):**
> - `ChatSession` fields are `is_pinned: bool`, `is_archived: bool`, `context: dict | None`. There is **no** `pinned` column and **no** `archived_at` column. Service code must construct `ChatSession(user_id=..., department=..., title=..., is_pinned=False)` and filter with `.where(ChatSession.is_archived.is_(False))`. If archive timestamps are required by the UI, add a migration deliberately in Task 0 — don't rely on `archived_at`.
> - All IDs are UUID strings (`String(36)`). `user_id`, `session_id`, `report_id`, `repo_item_id` are `str` at every service boundary and path param.
> - Backend imports: `ChatSession`, `ChatMessage`, `Report`, `RepoItem` from `openlia_server.db.models.content`; auth via `build_require_auth(...)` router factories — no bare `current_user` / `require_user`. `RepoItem` creation stays in this plan's Task 0 per the README cross-plan contract.
> - SSE consumption: the server-side serializer is `from openlia.llm.runtime.events import to_wire` — there is no `serialize_sse`. `ReportRequest` lives at `openlia.llm.runtime.messages`.
> - API prefix normalization (already applied 2026-04-20): frontend hits `/api/chat/sessions`, `/api/repo/items`; backend mounts bare `/chat/sessions`, `/repo`. Keep this; do not revert.

**Goal:** Build the shared frontend chat stack — `ChatInterface` (SSE streaming, message rendering, welcome, input), `ChatHistory` (session list + persistence routes), `FileViewer` (side panel with per-type renderers), `FileDownload`, and `SaveToRepo` — along with the minimal backend endpoints they depend on (`/chat/sessions`, `/chat/sessions/{id}/messages`, `/repo/items`, `/reports/{id}/download`).

**Architecture:** Chat state is driven by a single `useChatStream` hook that owns the SSE event-stream state machine (`chat.start` → `chat.tool_call.*` → `chat.token` → `chat.done`/`chat.error`/disconnect). Message/session persistence happens server-side on terminal events; the client just reads rendered sessions from REST. The `FileViewer` is a single persistent side panel whose content swaps when a different attachment chip is clicked. `SaveToRepo` and `FileDownload` each ship as dual-surface components (chip-variant + viewer-header-variant) that share core logic.

**Tech Stack:** React 18 + TypeScript strict, react-router-dom v6, Framer Motion (animations), Tailwind v3 (design tokens as CSS custom properties), lucide-react (icons), react-markdown + remark-gfm (markdown rendering), pdfjs-dist (PDF rendering), vitest + @testing-library/react. Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, StreamingResponse for download.

**Dependencies:**
- Plan 1A (tables `chat_sessions`, `chat_messages`, `chat_attachments`, `reports`). Note: `repo_items` is **not** in Plan 1A — this plan creates it in Task 0 below.
- Plan 2 (auth / session cookies)
- Plan 5 (SSE event taxonomy `chat.*` already documented; this plan consumes but does not emit)
- Plan 8 (AppShell, design tokens, router, API client base)
- Plan 9 (auth context + `useCurrentUser`)

---

## File Structure

### Backend (`packages/server/src/openlia_server/`)

- `routes/chat_sessions.py` — `/chat/sessions` CRUD (list, create, get, rename, pin, archive, delete) + `/chat/sessions/{id}/messages` GET.
- `routes/repo.py` — `/repo/items` GET + POST (save), `/repo/items/{id}` DELETE (unsave), idempotent on conflicts.
- `routes/files.py` — `/reports/{id}/download`, `/chat/attachments/{id}/download` StreamingResponse with `Content-Disposition: attachment; filename="..."`.
- `services/chat_sessions.py` — create/list/update session rows; enforces `user_id` ownership.
- `services/repo.py` — upsert-by-(user_id, report_id) idempotent save; soft-list by `user_id`.
- `services/files.py` — resolve file path for a report or attachment; enforce auth.

### Frontend (`frontend/src/`)

**Chat layer:**
- `api/chat.ts` — typed client: sessions CRUD, message fetch, SSE stream open.
- `api/repo.ts` — typed client: list/save/unsave repo items.
- `api/files.ts` — download URL builders.
- `components/chat/useChatStream.ts` — SSE consumer hook; owns streaming state machine.
- `components/chat/ChatInterface.tsx` — top-level component wiring welcome, message list, input, stream hook.
- `components/chat/MessageList.tsx` — scroll container + virtualization-friendly layout.
- `components/chat/UserBubble.tsx` — right-aligned user message.
- `components/chat/AssistantMessage.tsx` — LIA-badged assistant message with streaming cursor.
- `components/chat/ThinkingIndicator.tsx` — three-dot pill animation.
- `components/chat/ToolCallChip.tsx` — inline tool-call narration chip.
- `components/chat/ErrorMessage.tsx` — inline error state with Retry.
- `components/chat/WelcomeOverlay.tsx` — greeting + chip row + dot-grid background.
- `components/chat/ChatInput.tsx` — textarea + send/stop buttons.
- `components/chat/ChatHistoryDrawer.tsx` — session list (pinned, active, archived).

**Attachments:**
- `components/chat/AttachmentChip.tsx` — file chip with hover-action buttons.
- `components/chat/ReportThumbnail.tsx` — attachment chip variant for generated reports.

**FileViewer:**
- `components/viewer/FileViewer.tsx` — panel shell (slide-in, resize, close).
- `components/viewer/ViewerHeader.tsx` — filename + metadata + action row.
- `components/viewer/renderers/MarkdownRenderer.tsx`
- `components/viewer/renderers/PdfRenderer.tsx`
- `components/viewer/renderers/CsvRenderer.tsx`
- `components/viewer/renderers/CodeRenderer.tsx`
- `components/viewer/renderers/ImageRenderer.tsx`
- `components/viewer/renderers/UnsupportedRenderer.tsx`
- `components/viewer/ResizeHandle.tsx`
- `components/viewer/FileViewerContext.tsx` — provider + `useFileViewer` hook.

**Action buttons:**
- `components/chat/SaveToRepoButton.tsx` — shared logic, `variant: 'chip' | 'viewer-header'`.
- `components/chat/FileDownloadButton.tsx` — shared logic, `variant: 'chip' | 'viewer-header'`.

---

## Design Rules

1. **Event-stream state machine is authoritative.** `useChatStream` is the single source of truth for streaming UI state. Rendering components read a reducer-driven view model — no side-channel updates.
2. **Terminal events are mutually exclusive.** `chat.done`, `chat.error`, and disconnect each finalize a turn in exactly one way. Never transition from `error` back to streaming.
3. **No new events after terminal.** Any event received after the terminal event is dropped with a console warning.
4. **Client-side cancellation = connection close.** `Stop` button calls `EventSource.close()` or aborts the fetch; server observes and stops streaming. UI renders "Response stopped."
5. **Persistence is a server concern.** The frontend does not write chat messages to any DB. Client re-fetches `/messages` to rehydrate after reload.
6. **FileViewer is a singleton.** Exactly one panel exists app-wide; opening a different chip swaps content in place. Managed by `FileViewerProvider`.
7. **Design tokens only.** All colors, spacing, shadows, radii reference CSS custom properties from Plan 8. Never hardcode hex or rgb.
8. **Reuse across surfaces.** `SaveToRepoButton` and `FileDownloadButton` ship as a single component with a `variant` prop; no duplicated state logic per surface.
9. **Accessibility first.** Every streaming region uses `aria-live="polite"`; the FileViewer panel is `role="complementary"`; thinking indicator announces "LIA is thinking..."; all buttons have accessible names.
10. **Animations with `prefers-reduced-motion`.** Framer Motion animations respect the reduced-motion media query (no-op or instant transitions).
11. **TDD.** Test fails → implement → test passes → commit. One commit per task.
12. **No placeholders.** Every step contains complete, runnable code.
13. **No `any`.** Strict TypeScript throughout; SSE events typed via a discriminated union.
14. **Assumes Plan 5 SSE contract.** The event types, field names (`tool_name`, `args_preview`, `summary`, `ok`), and terminal semantics come directly from `planning/specs/systems/llm-runtime-design.md` and are consumed as-is. If Plan 5's event names differ at integration time, update `useChatStream`'s event-type union — the rest of the stack is oblivious.

---

## Task Overview

0. `repo_items` table + SQLAlchemy model + Alembic migration (prerequisite — not created by Plan 1A).
1. Chat sessions service + routes (GET /chat/sessions, GET /chat/sessions/{id}/messages, PATCH/DELETE).
2. Repo service + routes (list/save/unsave, idempotent).
3. File download routes with StreamingResponse.
4. Typed API clients: `api/chat.ts`, `api/repo.ts`, `api/files.ts`.
5. `useChatStream` hook + event-stream state machine.
6. `UserBubble` + `AssistantMessage` + `ThinkingIndicator` + `ToolCallChip` + `ErrorMessage`.
7. `MessageList` scroll container.
8. `ChatInput` (textarea + send/stop).
9. `WelcomeOverlay`.
10. `ChatInterface` integrating everything.
11. `ChatHistoryDrawer`.
12. `AttachmentChip` + `ReportThumbnail`.
13. `FileViewerContext` + `FileViewer` shell.
14. `ViewerHeader`.
15. FileViewer renderers (Markdown + Code + CSV + Image + Unsupported).
16. PdfRenderer (with pdf.js).
17. `ResizeHandle` + localStorage width persistence.
18. `SaveToRepoButton` (chip + viewer-header variants).
19. `FileDownloadButton` (chip + viewer-header variants).
20. Smoke test + docs update.

---

### Task 0: `repo_items` table + model + migration

> **Landed with REM-P1-007 on 2026-04-22.** The `repo_items` migration and
> `RepoItem` model already exist on `main` (branch `feat/plan-12-blockers`).
> Task 0 is a no-op for this plan; proceed to Task 1.

**Context.** Plan 1A did **not** create `repo_items`. It must be added here before Task 2 can use it.

**Files:**
- Create: `packages/server/src/openlia_server/db/models/repo.py` (or append to an existing content-models module)
- Create: `packages/server/migrations/versions/<next>_add_repo_items.py`
- Test: `packages/server/tests/test_db/test_repo_items_model.py`

- [ ] **Step 1: Write failing model test**

```python
# packages/server/tests/test_db/test_repo_items_model.py
"""Verify repo_items enforces (user_id, report_id) uniqueness and cascades on report delete."""
import pytest
import uuid
from sqlalchemy.exc import IntegrityError

def test_repo_items_unique_per_user_report(create_tables, db_session, user_factory, report_factory):
    from openlia_server.db.models.content import RepoItem
    u = user_factory()
    r = report_factory(user_id=u.id)
    db_session.add(RepoItem(id=str(uuid.uuid4()), user_id=u.id, report_id=r.id))
    db_session.commit()
    db_session.add(RepoItem(id=str(uuid.uuid4()), user_id=u.id, report_id=r.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/server/tests/test_db/test_repo_items_model.py -v`
Expected: FAIL — `RepoItem` not defined / table missing.

- [ ] **Step 3: Implement the model**

```python
# packages/server/src/openlia_server/db/models/content.py
from datetime import datetime
from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


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

- [ ] **Step 4: Create and run the migration**

```bash
uv run alembic -c packages/server/alembic.ini revision -m "add_repo_items"
# edit the file under packages/server/migrations/versions/ to create the table matching the model,
# then:
uv run alembic -c packages/server/alembic.ini upgrade head
uv run pytest packages/server/tests/test_db/test_repo_items_model.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/models/content.py \
        packages/server/migrations/versions/*_add_repo_items.py \
        packages/server/tests/test_db/test_repo_items_model.py
git commit -m "feat(db): add repo_items table + model for saved-report repo"
```

---

### Task 1: Chat sessions service + routes

**Files:**
- Create: `packages/server/src/openlia_server/services/chat_sessions.py`
- Create: `packages/server/src/openlia_server/routes/chat_sessions.py`
- Modify: `packages/server/src/openlia_server/app.py` (register router)
- Test: `packages/server/tests/test_services/test_chat_sessions.py`
- Test: `packages/server/tests/test_routes/test_chat_sessions_routes.py`

- [ ] **Step 1: Write failing test for the service**

```python
# packages/server/tests/test_services/test_chat_sessions.py
import uuid

import pytest
from openlia_server.services import chat_sessions as svc
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatMessage, ChatSession

def test_create_session_returns_row(db_session, user_factory):
    u: User = user_factory()
    row = svc.create_session(db_session, user_id=u.id, department="secretary", title="hi")
    assert row.id is not None
    assert row.user_id == u.id
    assert row.department == "secretary"
    assert row.is_pinned is False
    assert row.is_archived is False

def test_list_sessions_excludes_other_users(db_session, user_factory):
    a, b = user_factory(), user_factory()
    svc.create_session(db_session, user_id=a.id, department="secretary", title="A")
    svc.create_session(db_session, user_id=b.id, department="secretary", title="B")
    rows = svc.list_sessions(db_session, user_id=a.id)
    assert len(rows) == 1
    assert rows[0].title == "A"

def test_list_sessions_ordered_by_last_activity(db_session, user_factory):
    u = user_factory()
    s1 = svc.create_session(db_session, user_id=u.id, department="secretary", title="old")
    s2 = svc.create_session(db_session, user_id=u.id, department="secretary", title="new")
    rows = svc.list_sessions(db_session, user_id=u.id)
    assert rows[0].id == s2.id
    assert rows[1].id == s1.id

def test_rename_session_updates_title(db_session, user_factory):
    u = user_factory()
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    svc.rename_session(db_session, session_id=s.id, user_id=u.id, new_title="renamed")
    db_session.refresh(s)
    assert s.title == "renamed"

def test_rename_session_rejects_other_users(db_session, user_factory):
    a, b = user_factory(), user_factory()
    s = svc.create_session(db_session, user_id=a.id, department="secretary", title="x")
    with pytest.raises(PermissionError):
        svc.rename_session(db_session, session_id=s.id, user_id=b.id, new_title="y")

def test_pin_toggle(db_session, user_factory):
    u = user_factory()
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    svc.set_pinned(db_session, session_id=s.id, user_id=u.id, pinned=True)
    db_session.refresh(s)
    assert s.is_pinned is True

def test_archive_sets_flag(db_session, user_factory):
    u = user_factory()
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    svc.archive_session(db_session, session_id=s.id, user_id=u.id)
    db_session.refresh(s)
    assert s.is_archived is True

def test_delete_cascades_messages(db_session, user_factory):
    u = user_factory()
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    db_session.add(ChatMessage(id=str(uuid.uuid4()), session_id=s.id, role="user", content="hi"))
    db_session.commit()
    svc.delete_session(db_session, session_id=s.id, user_id=u.id)
    assert db_session.query(ChatMessage).filter_by(session_id=s.id).count() == 0

def test_list_messages_scopes_to_session_owner(db_session, user_factory):
    a, b = user_factory(), user_factory()
    s = svc.create_session(db_session, user_id=a.id, department="secretary", title="x")
    db_session.add(ChatMessage(id=str(uuid.uuid4()), session_id=s.id, role="user", content="hi"))
    db_session.commit()
    rows = svc.list_messages(db_session, session_id=s.id, user_id=a.id)
    assert len(rows) == 1
    with pytest.raises(PermissionError):
        svc.list_messages(db_session, session_id=s.id, user_id=b.id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_services/test_chat_sessions.py -v`
Expected: FAIL with `ModuleNotFoundError: openlia_server.services.chat_sessions`.

- [ ] **Step 3: Implement the service**

```python
# packages/server/src/openlia_server/services/chat_sessions.py
from __future__ import annotations
import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from openlia_server.db.models.content import ChatMessage, ChatSession


def create_session(db: Session, *, user_id: str, department: str, title: str) -> ChatSession:
    row = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        department=department,
        title=title,
        is_pinned=False,
        is_archived=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_sessions(db: Session, *, user_id: str, include_archived: bool = False) -> list[ChatSession]:
    last_activity = (
        select(ChatMessage.session_id, func.max(ChatMessage.created_at).label("last_at"))
        .group_by(ChatMessage.session_id)
        .subquery()
    )
    stmt = (
        select(ChatSession)
        .outerjoin(last_activity, ChatSession.id == last_activity.c.session_id)
        .where(ChatSession.user_id == user_id)
        .order_by(
            ChatSession.is_pinned.desc(),
            func.coalesce(last_activity.c.last_at, ChatSession.created_at).desc(),
        )
    )
    if not include_archived:
        stmt = stmt.where(ChatSession.is_archived.is_(False))
    return list(db.execute(stmt).scalars())


def get_session(db: Session, *, session_id: str, user_id: str) -> ChatSession:
    row = db.get(ChatSession, session_id)
    if row is None:
        raise LookupError(f"session {session_id} not found")
    if row.user_id != user_id:
        raise PermissionError("session does not belong to this user")
    return row


def rename_session(db: Session, *, session_id: str, user_id: str, new_title: str) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    if not new_title.strip():
        raise ValueError("title cannot be empty")
    row.title = new_title.strip()[:200]
    db.commit()


def set_pinned(db: Session, *, session_id: str, user_id: str, pinned: bool) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    row.is_pinned = pinned
    db.commit()


def archive_session(db: Session, *, session_id: str, user_id: str) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    row.is_archived = True
    db.commit()


def unarchive_session(db: Session, *, session_id: str, user_id: str) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    row.is_archived = False
    db.commit()


def delete_session(db: Session, *, session_id: str, user_id: str) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    db.query(ChatMessage).filter(ChatMessage.session_id == row.id).delete()
    db.delete(row)
    db.commit()


def list_messages(db: Session, *, session_id: str, user_id: str) -> list[ChatMessage]:
    get_session(db, session_id=session_id, user_id=user_id)  # authz
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
    )
    return list(db.execute(stmt).scalars())
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_chat_sessions.py -v`
Expected: all pass.

- [ ] **Step 5: Write failing test for the routes**

```python
# packages/server/tests/test_routes/test_chat_sessions_routes.py
import pytest
from fastapi.testclient import TestClient

def test_list_returns_sessions_for_user(client: TestClient, user_factory, login_as):
    u = user_factory()
    login_as(u)
    client.post("/chat/sessions", json={"department": "secretary", "title": "first"})
    r = client.get("/chat/sessions")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "first"

def test_list_hides_other_users_sessions(client: TestClient, user_factory, login_as):
    a = user_factory(); b = user_factory()
    login_as(a); client.post("/chat/sessions", json={"department": "secretary", "title": "A"})
    login_as(b)
    assert client.get("/chat/sessions").json()["items"] == []

def test_create_session_returns_id(client: TestClient, user_factory, login_as):
    login_as(user_factory())
    r = client.post("/chat/sessions", json={"department": "secretary", "title": "hi"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] > 0 and body["title"] == "hi" and body["department"] == "secretary"

def test_rename_session(client: TestClient, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    r = client.patch(f"/chat/sessions/{sid}", json={"title": "renamed"})
    assert r.status_code == 200
    assert client.get("/chat/sessions").json()["items"][0]["title"] == "renamed"

def test_pin_and_archive_via_patch(client: TestClient, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    assert client.patch(f"/chat/sessions/{sid}", json={"pinned": True}).status_code == 200
    assert client.patch(f"/chat/sessions/{sid}", json={"archived": True}).status_code == 200
    assert client.get("/chat/sessions?include_archived=true").json()["items"][0]["is_archived"] is True

def test_delete_session(client: TestClient, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    assert client.delete(f"/chat/sessions/{sid}").status_code == 204
    assert client.get("/chat/sessions").json()["items"] == []

def test_list_messages(client: TestClient, user_factory, login_as, seed_message):
    u = user_factory(); login_as(u)
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    seed_message(session_id=sid, role="user", content="hello")
    r = client.get(f"/chat/sessions/{sid}/messages")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items == [{"id": items[0]["id"], "role": "user", "content": "hello", "tool_calls": None, "model_ref": None, "token_usage": None, "created_at": items[0]["created_at"]}]

def test_list_messages_rejects_other_users(client: TestClient, user_factory, login_as):
    a = user_factory(); login_as(a)
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    b = user_factory(); login_as(b)
    assert client.get(f"/chat/sessions/{sid}/messages").status_code == 403
```

- [ ] **Step 6: Run route tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_chat_sessions_routes.py -v`
Expected: FAIL.

- [ ] **Step 7: Implement routes**

```python
# packages/server/src/openlia_server/routes/chat_sessions.py
from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import chat_sessions as svc


class SessionOut(BaseModel):
    id: str
    department: str
    title: str
    is_pinned: bool
    is_archived: bool
    created_at: datetime


class SessionListOut(BaseModel):
    items: list[SessionOut]


class SessionCreateIn(BaseModel):
    department: str = Field(..., pattern=r"^(secretary|equity_research)$")
    title: str = Field(..., min_length=1, max_length=200)


class SessionPatchIn(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    archived: bool | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: list[dict] | None = None
    model_ref: str | None = None
    token_usage: dict | None = None
    created_at: datetime


class MessageListOut(BaseModel):
    items: list[MessageOut]


def build_chat_sessions_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("", response_model=SessionListOut)
    def list_sessions_ep(
        include_archived: bool = False,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionListOut:
        rows = svc.list_sessions(db, user_id=user.id, include_archived=include_archived)
        return SessionListOut(items=[SessionOut.model_validate(r, from_attributes=True) for r in rows])

    @router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
    def create_session_ep(
        body: SessionCreateIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionOut:
        row = svc.create_session(db, user_id=user.id, department=body.department, title=body.title)
        return SessionOut.model_validate(row, from_attributes=True)

    @router.patch("/{session_id}")
    def patch_session_ep(
        session_id: str,
        body: SessionPatchIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        try:
            if body.title is not None:
                svc.rename_session(db, session_id=session_id, user_id=user.id, new_title=body.title)
            if body.pinned is not None:
                svc.set_pinned(db, session_id=session_id, user_id=user.id, pinned=body.pinned)
            if body.archived is True:
                svc.archive_session(db, session_id=session_id, user_id=user.id)
            if body.archived is False:
                svc.unarchive_session(db, session_id=session_id, user_id=user.id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": str(exc)}) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": str(exc)}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid", "message": str(exc)}) from exc
        return {"ok": True}

    @router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_session_ep(
        session_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        try:
            svc.delete_session(db, session_id=session_id, user_id=user.id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": str(exc)}) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": str(exc)}) from exc

    @router.get("/{session_id}/messages", response_model=MessageListOut)
    def list_messages_ep(
        session_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> MessageListOut:
        try:
            rows = svc.list_messages(db, session_id=session_id, user_id=user.id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": str(exc)}) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": str(exc)}) from exc
        return MessageListOut(
            items=[
                MessageOut(
                    id=r.id, role=r.role, content=r.content,
                    tool_calls=r.tool_calls, model_ref=r.model_ref,
                    token_usage=r.token_usage, created_at=r.created_at,
                )
                for r in rows
            ]
        )

    return router
```

- [ ] **Step 8: Wire into `app.py`**

```python
from openlia_server.routes.chat_sessions import build_chat_sessions_router
app.include_router(build_chat_sessions_router(db_session_factory=factory, mode=mode))
```

- [ ] **Step 9: Run route tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_chat_sessions_routes.py -v`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add packages/server/src/openlia_server/services/chat_sessions.py \
        packages/server/src/openlia_server/routes/chat_sessions.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_services/test_chat_sessions.py \
        packages/server/tests/test_routes/test_chat_sessions_routes.py
git commit -m "feat(chat): add /chat/sessions CRUD + /messages list route"
```

---

### Task 2: Repo service + routes (idempotent save/unsave)

**Files:**
- Create: `packages/server/src/openlia_server/services/repo.py`
- Create: `packages/server/src/openlia_server/routes/repo.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_services/test_repo.py`
- Test: `packages/server/tests/test_routes/test_repo_routes.py`

- [ ] **Step 1: Write failing test for the service**

```python
# packages/server/tests/test_services/test_repo.py
import pytest
from openlia_server.services import repo as svc

def test_save_creates_entry(db_session, user_factory, report_factory):
    u = user_factory(); r = report_factory(user_id=u.id)
    item = svc.save_to_repo(db_session, user_id=u.id, report_id=r.id)
    assert item.id is not None
    assert item.user_id == u.id
    assert item.report_id == r.id

def test_save_is_idempotent(db_session, user_factory, report_factory):
    u = user_factory(); r = report_factory(user_id=u.id)
    a = svc.save_to_repo(db_session, user_id=u.id, report_id=r.id)
    b = svc.save_to_repo(db_session, user_id=u.id, report_id=r.id)
    assert a.id == b.id

def test_unsave_removes_entry(db_session, user_factory, report_factory):
    u = user_factory(); r = report_factory(user_id=u.id)
    svc.save_to_repo(db_session, user_id=u.id, report_id=r.id)
    svc.unsave_from_repo(db_session, user_id=u.id, report_id=r.id)
    assert svc.list_items(db_session, user_id=u.id) == []

def test_unsave_is_idempotent_when_absent(db_session, user_factory, report_factory):
    u = user_factory(); r = report_factory(user_id=u.id)
    svc.unsave_from_repo(db_session, user_id=u.id, report_id=r.id)  # does not raise

def test_list_items_scoped_to_user(db_session, user_factory, report_factory):
    a = user_factory(); b = user_factory()
    ra = report_factory(user_id=a.id); rb = report_factory(user_id=b.id)
    svc.save_to_repo(db_session, user_id=a.id, report_id=ra.id)
    svc.save_to_repo(db_session, user_id=b.id, report_id=rb.id)
    assert [i.report_id for i in svc.list_items(db_session, user_id=a.id)] == [ra.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_services/test_repo.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the service**

```python
# packages/server/src/openlia_server/services/repo.py
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import RepoItem, Report


def save_to_repo(db: Session, *, user_id: str, report_id: str) -> RepoItem:
    existing = db.execute(
        select(RepoItem).where(RepoItem.user_id == user_id, RepoItem.report_id == report_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    report = db.get(Report, report_id)
    if report is None:
        raise LookupError(f"report {report_id} not found")
    item = RepoItem(
        user_id=user_id,
        report_id=report_id,
        saved_at=datetime.now(timezone.utc),
        filename=report.filename,
        department=report.department,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def unsave_from_repo(db: Session, *, user_id: str, report_id: str) -> None:
    db.query(RepoItem).filter(
        RepoItem.user_id == user_id, RepoItem.report_id == report_id
    ).delete()
    db.commit()


def list_items(db: Session, *, user_id: str) -> list[RepoItem]:
    stmt = select(RepoItem).where(RepoItem.user_id == user_id).order_by(RepoItem.saved_at.desc())
    return list(db.execute(stmt).scalars())
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_repo.py -v`
Expected: all pass.

- [ ] **Step 5: Write failing test for the routes**

```python
# packages/server/tests/test_routes/test_repo_routes.py
def test_save_then_list(client, user_factory, login_as, report_factory):
    u = user_factory(); login_as(u)
    r = report_factory(user_id=u.id)
    resp = client.post(f"/repo/items", json={"report_id": r.id})
    assert resp.status_code == 201
    assert client.get("/repo/items").json()["items"][0]["report_id"] == r.id

def test_save_twice_is_idempotent(client, user_factory, login_as, report_factory):
    u = user_factory(); login_as(u)
    r = report_factory(user_id=u.id)
    first = client.post("/repo/items", json={"report_id": r.id}).json()
    second = client.post("/repo/items", json={"report_id": r.id}).json()
    assert first["id"] == second["id"]

def test_delete_by_report_id(client, user_factory, login_as, report_factory):
    u = user_factory(); login_as(u)
    r = report_factory(user_id=u.id)
    client.post("/repo/items", json={"report_id": r.id})
    assert client.delete(f"/repo/items?report_id={r.id}").status_code == 204
    assert client.get("/repo/items").json()["items"] == []

def test_delete_when_absent_is_idempotent(client, user_factory, login_as, report_factory):
    u = user_factory(); login_as(u)
    r = report_factory(user_id=u.id)
    assert client.delete(f"/repo/items?report_id={r.id}").status_code == 204
```

- [ ] **Step 6: Implement routes**

```python
# packages/server/src/openlia_server/routes/repo.py
from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import repo as svc


class RepoSaveIn(BaseModel):
    report_id: str


class RepoItemOut(BaseModel):
    id: str
    report_id: str
    filename: str
    department: str
    saved_at: datetime


class RepoListOut(BaseModel):
    items: list[RepoItemOut]


def build_repo_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/repo", tags=["repo"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/items", response_model=RepoListOut)
    def list_items_ep(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoListOut:
        rows = svc.list_items(db, user_id=user.id)
        return RepoListOut(items=[RepoItemOut.model_validate(r, from_attributes=True) for r in rows])

    @router.post("/items", response_model=RepoItemOut, status_code=status.HTTP_201_CREATED)
    def save_ep(
        body: RepoSaveIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoItemOut:
        try:
            item = svc.save_to_repo(db, user_id=user.id, report_id=body.report_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail={"code": "report_not_found", "message": str(exc)}) from exc
        return RepoItemOut.model_validate(item, from_attributes=True)

    @router.delete("/items", status_code=status.HTTP_204_NO_CONTENT)
    def delete_ep(
        report_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        svc.unsave_from_repo(db, user_id=user.id, report_id=report_id)

    return router
```

- [ ] **Step 7: Wire into `app.py`**

```python
from openlia_server.routes.repo import build_repo_router
app.include_router(build_repo_router(db_session_factory=factory, mode=mode))
```

- [ ] **Step 8: Run route tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_repo_routes.py -v`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add packages/server/src/openlia_server/services/repo.py \
        packages/server/src/openlia_server/routes/repo.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_services/test_repo.py \
        packages/server/tests/test_routes/test_repo_routes.py
git commit -m "feat(repo): add idempotent /repo/items save/unsave routes"
```

---

### Task 3: File download routes (StreamingResponse with Content-Disposition)

**Files:**
- Create: `packages/server/src/openlia_server/routes/files.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_routes/test_files_routes.py`

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/test_routes/test_files_routes.py
import io

def test_download_report_returns_binary_with_filename_header(client, user_factory, login_as, report_factory, tmp_path):
    u = user_factory(); login_as(u)
    path = tmp_path / "hello.pdf"
    path.write_bytes(b"%PDF-1.4\nhello")
    r = report_factory(user_id=u.id, file_path=str(path), filename="hello.pdf")
    resp = client.get(f"/reports/{r.id}/download")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4\nhello"
    assert 'filename="hello.pdf"' in resp.headers["content-disposition"]

def test_download_report_forbids_other_users(client, user_factory, login_as, report_factory, tmp_path):
    a = user_factory(); b = user_factory()
    path = tmp_path / "x.pdf"; path.write_bytes(b"x")
    r = report_factory(user_id=a.id, file_path=str(path), filename="x.pdf")
    login_as(b)
    assert client.get(f"/reports/{r.id}/download").status_code == 403

def test_download_report_404_when_missing(client, user_factory, login_as):
    login_as(user_factory())
    assert client.get("/reports/99999/download").status_code == 404

def test_download_report_410_when_file_missing_on_disk(client, user_factory, login_as, report_factory):
    u = user_factory(); login_as(u)
    r = report_factory(user_id=u.id, file_path="/tmp/does-not-exist-xyz.pdf", filename="x.pdf")
    assert client.get(f"/reports/{r.id}/download").status_code == 410
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_routes/test_files_routes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement routes**

```python
# packages/server/src/openlia_server/routes/files.py
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatAttachment, Report
from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.auth import build_require_auth


def _safe_filename(name: str) -> str:
    return name.replace('"', "").replace("\r", "").replace("\n", "")


def build_files_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="", tags=["files"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/reports/{report_id}/download")
    def download_report(
        report_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> FileResponse:
        row = db.get(Report, report_id)
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "report_not_found"})
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail={"code": "forbidden"})
        path = Path(row.file_path)
        if not path.is_file():
            raise HTTPException(status_code=410, detail={"code": "file_gone"})
        return FileResponse(
            path,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(row.filename)}"'},
        )

    @router.get("/chat/attachments/{attachment_id}/download")
    def download_attachment(
        attachment_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> FileResponse:
        row = db.get(ChatAttachment, attachment_id)
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "attachment_not_found"})
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail={"code": "forbidden"})
        path = Path(row.file_path)
        if not path.is_file():
            raise HTTPException(status_code=410, detail={"code": "file_gone"})
        return FileResponse(
            path,
            media_type=row.mime_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(row.file_name)}"'},
        )

    return router
```

- [ ] **Step 4: Wire into `app.py`**

```python
from openlia_server.routes.files import build_files_router
app.include_router(build_files_router(db_session_factory=factory, mode=mode))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/test_files_routes.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/files.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_routes/test_files_routes.py
git commit -m "feat(files): add /reports/{id}/download + /chat/attachments/{id}/download"
```

---

### Task 4: Typed API clients (`api/chat.ts`, `api/repo.ts`, `api/files.ts`)

**Files:**
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/api/repo.ts`
- Create: `frontend/src/api/files.ts`
- Test: `frontend/src/api/__tests__/chat.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/api/__tests__/chat.test.ts
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { createSession, listSessions, listMessages, deleteSession, patchSession } from '../chat';
import { saveToRepo, unsaveFromRepo, listRepoItems } from '../repo';
import { downloadUrlForReport, downloadUrlForAttachment } from '../files';

describe('chat api', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()));

  it('GET /api/chat/sessions returns typed list', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [{ id: '00000000-0000-4000-8000-000000000001', department: 'secretary', title: 'x', is_pinned: false, is_archived: false, created_at: '2026-04-01T00:00:00Z' }] }),
    });
    const r = await listSessions();
    expect(r.items[0].department).toBe('secretary');
  });

  it('POST /api/chat/sessions returns new session', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: '00000000-0000-4000-8000-000000000002', department: 'secretary', title: 'y', is_pinned: false, is_archived: false, created_at: '2026-04-01T00:00:00Z' }),
    });
    const r = await createSession({ department: 'secretary', title: 'y' });
    expect(r.id).toBe(2);
  });

  it('PATCH /api/chat/sessions/{id}', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true }) });
    await patchSession(3, { title: 'renamed' });
    expect((fetch as any).mock.calls[0][0]).toBe('/api/chat/sessions/3');
  });

  it('DELETE session', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, status: 204, json: async () => ({}) });
    await deleteSession(3);
    expect((fetch as any).mock.calls[0][1].method).toBe('DELETE');
  });

  it('GET messages', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [{ id: '00000000-0000-4000-8000-000000000009', role: 'user', content: 'hi', tool_calls: null, model_ref: null, token_usage: null, created_at: '2026-04-01T00:00:00Z' }] }),
    });
    const r = await listMessages(7);
    expect(r.items[0].role).toBe('user');
  });
});

describe('repo api', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()));

  it('saveToRepo POSTs report_id', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: '00000000-0000-4000-8000-000000000001', report_id: '00000000-0000-4000-8000-000000000005', filename: 'r.pdf', department: 'secretary', saved_at: '2026-04-01T00:00:00Z' }),
    });
    const r = await saveToRepo(5);
    expect(r.id).toBe(1);
  });

  it('unsaveFromRepo uses DELETE with query param', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, status: 204, json: async () => ({}) });
    await unsaveFromRepo(5);
    expect((fetch as any).mock.calls[0][0]).toBe('/api/repo/items?report_id=5');
  });

  it('listRepoItems returns list', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) });
    const r = await listRepoItems();
    expect(r.items).toEqual([]);
  });
});

describe('files helpers', () => {
  it('downloadUrlForReport returns correct URL', () => {
    expect(downloadUrlForReport(5)).toBe('/api/reports/5/download');
  });
  it('downloadUrlForAttachment returns correct URL', () => {
    expect(downloadUrlForAttachment(7)).toBe('/api/chat/attachments/7/download');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/__tests__/chat.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement `chat.ts`**

```typescript
// frontend/src/api/chat.ts
import { ApiError } from './settings';

export type Department = 'secretary' | 'equity_research';
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

export interface ChatSession {
  id: string;
  department: Department;
  title: string;
  is_pinned: boolean;
  is_archived: boolean;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  tool_calls: unknown[] | null;
  model_ref: string | null;
  token_usage: Record<string, unknown> | null;
  created_at: string;
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
  if (r.status === 204) return undefined as T;
  return r.json();
}

export const listSessions = (includeArchived = false) =>
  request<{ items: ChatSession[] }>(
    `/api/chat/sessions${includeArchived ? '?include_archived=true' : ''}`,
  );

export const createSession = (body: { department: Department; title: string }) =>
  request<ChatSession>('/api/chat/sessions', { method: 'POST', body: JSON.stringify(body) });

export const patchSession = (id: string, patch: { title?: string; pinned?: boolean; archived?: boolean }) =>
  request<{ ok: true }>(`/api/chat/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(patch) });

export const deleteSession = (id: string) =>
  request<void>(`/api/chat/sessions/${id}`, { method: 'DELETE' });

export const listMessages = (sessionId: number) =>
  request<{ items: ChatMessage[] }>(`/api/chat/sessions/${sessionId}/messages`);
```

- [ ] **Step 4: Implement `repo.ts`**

```typescript
// frontend/src/api/repo.ts
import { ApiError } from './settings';
import { Department } from './chat';

export interface RepoItem {
  id: string;
  report_id: string;
  filename: string;
  department: Department;
  saved_at: string;
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
  if (r.status === 204) return undefined as T;
  return r.json();
}

export const listRepoItems = () => request<{ items: RepoItem[] }>('/api/repo/items');

export const saveToRepo = (reportId: number) =>
  request<RepoItem>('/api/repo/items', { method: 'POST', body: JSON.stringify({ report_id: reportId }) });

export const unsaveFromRepo = (reportId: number) =>
  request<void>(`/api/repo/items?report_id=${reportId}`, { method: 'DELETE' });
```

- [ ] **Step 5: Implement `files.ts`**

```typescript
// frontend/src/api/files.ts
export const downloadUrlForReport = (reportId: number): string =>
  `/api/reports/${reportId}/download`;

export const downloadUrlForAttachment = (attachmentId: number): string =>
  `/api/chat/attachments/${attachmentId}/download`;
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/api/__tests__/chat.test.ts`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/chat.ts frontend/src/api/repo.ts frontend/src/api/files.ts \
        frontend/src/api/__tests__/chat.test.ts
git commit -m "feat(chat): add typed API clients for chat sessions, repo, and file downloads"
```

---

### Task 5: `useChatStream` hook + SSE event state machine

**Files:**
- Create: `frontend/src/components/chat/useChatStream.ts`
- Test: `frontend/src/components/chat/__tests__/useChatStream.test.tsx`

The hook consumes the SSE event stream from Plan 5 and exposes a view model:

```ts
interface StreamState {
  status: 'idle' | 'opening' | 'thinking' | 'streaming' | 'done' | 'error' | 'stopped';
  message: string;            // accumulated assistant text
  toolCalls: ToolCallView[];  // chip narrations
  reportThumbnails: Array<{ report_id: string; filename: string }>;
  errorMessage: string | null;
}
```

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/chat/__tests__/useChatStream.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useChatStream, ChatStreamEvent } from '../useChatStream';

class MockEventSource {
  listeners: Record<string, ((ev: MessageEvent) => void)[]> = {};
  closed = false;
  constructor(public url: string) {
    (MockEventSource.instances as any).push(this);
  }
  static instances: MockEventSource[] = [];
  addEventListener(type: string, cb: (ev: MessageEvent) => void) {
    this.listeners[type] ??= [];
    this.listeners[type].push(cb);
  }
  close() { this.closed = true; }
  emit(type: string, data: unknown) {
    const cbs = this.listeners[type] ?? [];
    for (const cb of cbs) cb(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal('EventSource', MockEventSource);
});

function lastSource(): MockEventSource {
  return MockEventSource.instances[MockEventSource.instances.length - 1];
}

describe('useChatStream', () => {
  it('starts in idle and opens the stream on send', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    expect(result.current.state.status).toBe('idle');
    act(() => result.current.send('hello'));
    expect(result.current.state.status).toBe('opening');
    expect(lastSource().url).toContain('/api/chat/sessions/1/stream');
  });

  it('chat.start -> thinking, chat.token -> streaming with content', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    act(() => result.current.send('hello'));
    act(() => lastSource().emit('chat.start', {}));
    expect(result.current.state.status).toBe('thinking');
    act(() => lastSource().emit('chat.token', { text: 'Hi ' }));
    expect(result.current.state.status).toBe('streaming');
    expect(result.current.state.message).toBe('Hi ');
    act(() => lastSource().emit('chat.token', { text: 'there.' }));
    expect(result.current.state.message).toBe('Hi there.');
  });

  it('tool_call.start appends a chip, tool_call.result finalizes it', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    act(() => result.current.send('x'));
    act(() => lastSource().emit('chat.tool_call.start', {
      call_id: 'c1', tool_name: 'get_quote', args_preview: 'AAPL',
    }));
    expect(result.current.state.toolCalls[0]).toMatchObject({
      callId: 'c1', status: 'running', toolName: 'get_quote',
    });
    act(() => lastSource().emit('chat.tool_call.result', {
      call_id: 'c1', ok: true, summary: 'Got quote for AAPL',
    }));
    expect(result.current.state.toolCalls[0].status).toBe('done');
    expect(result.current.state.toolCalls[0].summary).toBe('Got quote for AAPL');
  });

  it('tool_call.result with ok=false marks the chip as failed', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    act(() => result.current.send('x'));
    act(() => lastSource().emit('chat.tool_call.start', { call_id: 'c1', tool_name: 't', args_preview: '' }));
    act(() => lastSource().emit('chat.tool_call.result', { call_id: 'c1', ok: false, summary: 'Failed' }));
    expect(result.current.state.toolCalls[0].status).toBe('failed');
  });

  it('chat.done finalizes the stream and closes the event source', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    act(() => result.current.send('x'));
    act(() => lastSource().emit('chat.token', { text: 'ok' }));
    act(() => lastSource().emit('chat.done', {}));
    expect(result.current.state.status).toBe('done');
    expect(lastSource().closed).toBe(true);
  });

  it('chat.error transitions to error', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    act(() => result.current.send('x'));
    act(() => lastSource().emit('chat.error', { message: 'LLM unavailable' }));
    expect(result.current.state.status).toBe('error');
    expect(result.current.state.errorMessage).toBe('LLM unavailable');
  });

  it('stop() closes the stream and marks status=stopped', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    act(() => result.current.send('x'));
    act(() => lastSource().emit('chat.token', { text: 'partial' }));
    act(() => result.current.stop());
    expect(result.current.state.status).toBe('stopped');
    expect(lastSource().closed).toBe(true);
  });

  it('ignores events received after terminal', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    act(() => result.current.send('x'));
    act(() => lastSource().emit('chat.done', {}));
    act(() => lastSource().emit('chat.token', { text: 'late' }));
    expect(result.current.state.message).toBe('');
  });

  it('chat.report_thumbnail records thumbnails', () => {
    const { result } = renderHook(() => useChatStream({ sessionId: 1 }));
    act(() => result.current.send('x'));
    act(() => lastSource().emit('chat.report_thumbnail', { report_id: '00000000-0000-4000-8000-000000000042', filename: 'r.pdf' }));
    expect(result.current.state.reportThumbnails[0]).toEqual({ report_id: '00000000-0000-4000-8000-000000000042', filename: 'r.pdf' });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/useChatStream.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `useChatStream.ts`**

```typescript
// frontend/src/components/chat/useChatStream.ts
import { useCallback, useEffect, useReducer, useRef } from 'react';

export interface ToolCallView {
  callId: string;
  toolName: string;
  argsPreview: string;
  status: 'running' | 'done' | 'failed';
  summary?: string;
}

export type ChatStreamEvent =
  | { type: 'chat.start'; data: Record<string, unknown> }
  | { type: 'chat.tool_call.start'; data: { call_id: string; tool_name: string; args_preview: string } }
  | { type: 'chat.tool_call.result'; data: { call_id: string; ok: boolean; summary: string } }
  | { type: 'chat.token'; data: { text: string } }
  | { type: 'chat.report_thumbnail'; data: { report_id: string; filename: string } }
  | { type: 'chat.done'; data: Record<string, unknown> }
  | { type: 'chat.error'; data: { message: string } };

export type StreamStatus =
  | 'idle'
  | 'opening'
  | 'thinking'
  | 'streaming'
  | 'done'
  | 'error'
  | 'stopped';

export interface StreamState {
  status: StreamStatus;
  message: string;
  toolCalls: ToolCallView[];
  reportThumbnails: Array<{ report_id: string; filename: string }>;
  errorMessage: string | null;
}

const INITIAL: StreamState = {
  status: 'idle',
  message: '',
  toolCalls: [],
  reportThumbnails: [],
  errorMessage: null,
};

type Action =
  | { kind: 'SEND' }
  | { kind: 'EVENT'; event: ChatStreamEvent }
  | { kind: 'STOP' }
  | { kind: 'RESET' };

function isTerminal(s: StreamStatus): boolean {
  return s === 'done' || s === 'error' || s === 'stopped';
}

function reducer(state: StreamState, action: Action): StreamState {
  if (action.kind === 'RESET') return INITIAL;
  if (action.kind === 'SEND') return { ...INITIAL, status: 'opening' };
  if (action.kind === 'STOP') {
    if (isTerminal(state.status)) return state;
    return { ...state, status: 'stopped' };
  }
  if (isTerminal(state.status)) return state;
  const ev = action.event;
  switch (ev.type) {
    case 'chat.start':
      return { ...state, status: 'thinking' };
    case 'chat.tool_call.start':
      return {
        ...state,
        toolCalls: [
          ...state.toolCalls,
          {
            callId: ev.data.call_id,
            toolName: ev.data.tool_name,
            argsPreview: ev.data.args_preview,
            status: 'running',
          },
        ],
      };
    case 'chat.tool_call.result': {
      const next = state.toolCalls.map((c) =>
        c.callId === ev.data.call_id
          ? { ...c, status: ev.data.ok ? 'done' : 'failed', summary: ev.data.summary }
          : c,
      ) as ToolCallView[];
      return { ...state, toolCalls: next };
    }
    case 'chat.token':
      return { ...state, status: 'streaming', message: state.message + ev.data.text };
    case 'chat.report_thumbnail':
      return {
        ...state,
        reportThumbnails: [...state.reportThumbnails, ev.data],
      };
    case 'chat.done':
      return { ...state, status: 'done' };
    case 'chat.error':
      return { ...state, status: 'error', errorMessage: ev.data.message };
    default:
      return state;
  }
}

interface Options {
  sessionId: number;
}

export function useChatStream({ sessionId }: Options) {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const sourceRef = useRef<EventSource | null>(null);

  const send = useCallback(
    (userMessage: string) => {
      dispatch({ kind: 'SEND' });
      const qs = new URLSearchParams({ q: userMessage });
      const es = new EventSource(`/api/chat/sessions/${sessionId}/stream?${qs.toString()}`, {
        withCredentials: true,
      });
      const handler = (type: ChatStreamEvent['type']) => (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          dispatch({ kind: 'EVENT', event: { type, data } as ChatStreamEvent });
          if (type === 'chat.done' || type === 'chat.error') es.close();
        } catch {
          // malformed event — ignore
        }
      };
      (
        [
          'chat.start',
          'chat.tool_call.start',
          'chat.tool_call.result',
          'chat.token',
          'chat.report_thumbnail',
          'chat.done',
          'chat.error',
        ] as const
      ).forEach((t) => es.addEventListener(t, handler(t)));
      es.addEventListener('error', () => {
        if (\!state.status.startsWith('done') && state.status \!== 'error') {
          dispatch({ kind: 'STOP' });
        }
        es.close();
      });
      sourceRef.current = es;
    },
    [sessionId, state.status],
  );

  const stop = useCallback(() => {
    sourceRef.current?.close();
    dispatch({ kind: 'STOP' });
  }, []);

  const reset = useCallback(() => {
    sourceRef.current?.close();
    dispatch({ kind: 'RESET' });
  }, []);

  useEffect(() => () => { sourceRef.current?.close(); }, []);

  return { state, send, stop, reset };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/useChatStream.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/useChatStream.ts \
        frontend/src/components/chat/__tests__/useChatStream.test.tsx
git commit -m "feat(chat): add useChatStream hook with SSE event state machine"
```

---

### Task 6: Message components (UserBubble, AssistantMessage, ThinkingIndicator, ToolCallChip, ErrorMessage)

**Files:**
- Create: `frontend/src/components/chat/UserBubble.tsx`
- Create: `frontend/src/components/chat/AssistantMessage.tsx`
- Create: `frontend/src/components/chat/ThinkingIndicator.tsx`
- Create: `frontend/src/components/chat/ToolCallChip.tsx`
- Create: `frontend/src/components/chat/ErrorMessage.tsx`
- Create: `frontend/src/components/chat/LiaBadge.tsx`
- Test: `frontend/src/components/chat/__tests__/messages.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/chat/__tests__/messages.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { UserBubble } from '../UserBubble';
import { AssistantMessage } from '../AssistantMessage';
import { ThinkingIndicator } from '../ThinkingIndicator';
import { ToolCallChip } from '../ToolCallChip';
import { ErrorMessage } from '../ErrorMessage';

describe('UserBubble', () => {
  it('renders content with role="article"', () => {
    render(<UserBubble content="What moved the market?" />);
    expect(screen.getByRole('article')).toHaveTextContent('What moved the market?');
  });
});

describe('AssistantMessage', () => {
  it('renders content and shows LIA badge', () => {
    render(<AssistantMessage content="Top movers" streaming={false} />);
    expect(screen.getByText('Top movers')).toBeInTheDocument();
    expect(screen.getByLabelText(/lia badge/i)).toBeInTheDocument();
  });
  it('shows cursor when streaming=true', () => {
    render(<AssistantMessage content="partial" streaming={true} />);
    expect(screen.getByTestId('streaming-cursor')).toBeInTheDocument();
  });
  it('hides cursor when streaming=false', () => {
    render(<AssistantMessage content="done" streaming={false} />);
    expect(screen.queryByTestId('streaming-cursor')).toBeNull();
  });
});

describe('ThinkingIndicator', () => {
  it('announces "LIA is thinking..." via aria-live', () => {
    render(<ThinkingIndicator />);
    expect(screen.getByRole('status')).toHaveTextContent(/lia is thinking/i);
  });
});

describe('ToolCallChip', () => {
  it('renders running state with ellipsis', () => {
    render(<ToolCallChip toolName="get_quote" argsPreview="AAPL" status="running" />);
    expect(screen.getByText(/get_quote.*AAPL/i)).toBeInTheDocument();
  });
  it('renders done state with summary', () => {
    render(<ToolCallChip toolName="get_quote" argsPreview="AAPL" status="done" summary="Got quote for AAPL" />);
    expect(screen.getByText('Got quote for AAPL')).toBeInTheDocument();
  });
  it('renders failed state with muted style', () => {
    render(<ToolCallChip toolName="get_quote" argsPreview="AAPL" status="failed" summary="Failed" />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });
});

describe('ErrorMessage', () => {
  it('renders error and Try again button', () => {
    const retry = vi.fn();
    render(<ErrorMessage message="LLM unavailable" onRetry={retry} />);
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(retry).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/messages.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `LiaBadge.tsx`**

```tsx
// frontend/src/components/chat/LiaBadge.tsx
import React from 'react';

export function LiaBadge(): JSX.Element {
  return (
    <div
      aria-label="LIA badge"
      aria-hidden="true"
      className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-[--color-accent-primary] text-xs font-semibold text-white shadow-sm"
    >
      L
    </div>
  );
}
```

- [ ] **Step 4: Implement `UserBubble.tsx`**

```tsx
// frontend/src/components/chat/UserBubble.tsx
import React from 'react';
import { motion } from 'framer-motion';

interface Props { content: string; timestamp?: string }

export function UserBubble({ content, timestamp }: Props): JSX.Element {
  return (
    <motion.article
      role="article"
      aria-label="User message"
      initial={{ x: 12, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="flex flex-col items-end"
    >
      <div className="max-w-[72%] whitespace-pre-wrap rounded-2xl rounded-br-sm border border-[--color-border-secondary] bg-[--color-accent-primary]/10 px-4 py-3 text-md leading-relaxed text-[--color-text-primary]">
        {content}
      </div>
      {timestamp ? (
        <time className="mt-1 text-xs text-[--color-text-tertiary]">{timestamp}</time>
      ) : null}
    </motion.article>
  );
}
```

- [ ] **Step 5: Implement `AssistantMessage.tsx`**

```tsx
// frontend/src/components/chat/AssistantMessage.tsx
import React from 'react';
import { motion } from 'framer-motion';
import { LiaBadge } from './LiaBadge';

interface Props {
  content: string;
  streaming: boolean;
  timestamp?: string;
  stopped?: boolean;
}

export function AssistantMessage({ content, streaming, timestamp, stopped }: Props): JSX.Element {
  return (
    <motion.article
      role="article"
      aria-label="Assistant message"
      initial={{ y: 8, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="flex items-start gap-3"
    >
      <LiaBadge />
      <div className="min-w-0 flex-1">
        <div
          aria-live="polite"
          className="whitespace-pre-wrap text-md leading-[1.75] text-[--color-text-primary]"
        >
          {content}
          {streaming ? (
            <span
              data-testid="streaming-cursor"
              className="ml-0.5 inline-block animate-[cursor-blink_800ms_ease-in-out_infinite] text-[--color-accent-primary]/50"
            >
              &#9612;
            </span>
          ) : null}
        </div>
        {stopped ? (
          <span className="mt-1.5 block text-xs italic text-[--color-text-tertiary]">
            Response stopped.
          </span>
        ) : null}
        {timestamp ? (
          <time className="mt-1 block text-xs text-[--color-text-tertiary]">{timestamp}</time>
        ) : null}
      </div>
    </motion.article>
  );
}
```

- [ ] **Step 6: Implement `ThinkingIndicator.tsx`**

```tsx
// frontend/src/components/chat/ThinkingIndicator.tsx
import React from 'react';
import { motion } from 'framer-motion';
import { LiaBadge } from './LiaBadge';

export function ThinkingIndicator(): JSX.Element {
  return (
    <div className="flex items-center gap-3" role="status" aria-live="polite">
      <LiaBadge />
      <div className="flex items-center gap-1.5 rounded-full border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3.5 py-2.5 shadow-sm">
        {[0, 150, 300].map((delay) => (
          <motion.span
            key={delay}
            aria-hidden="true"
            className="h-1.5 w-1.5 rounded-full bg-[--color-accent-primary]/50"
            animate={{ scaleY: [0.5, 1.0, 0.5], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 0.9, repeat: Infinity, delay: delay / 1000 }}
          />
        ))}
      </div>
      <span className="sr-only">LIA is thinking...</span>
    </div>
  );
}
```

- [ ] **Step 7: Implement `ToolCallChip.tsx`**

```tsx
// frontend/src/components/chat/ToolCallChip.tsx
import React from 'react';

interface Props {
  toolName: string;
  argsPreview: string;
  status: 'running' | 'done' | 'failed';
  summary?: string;
}

const STATUS_STYLE: Record<Props['status'], string> = {
  running: 'border-[--color-border-subtle] text-[--color-text-secondary]',
  done: 'border-[--color-border-subtle] text-[--color-text-secondary]',
  failed: 'border-[--color-border-subtle] text-[--color-text-tertiary]',
};

export function ToolCallChip({ toolName, argsPreview, status, summary }: Props): JSX.Element {
  let label: string;
  if (status === 'running') {
    label = `${toolName}(${argsPreview})…`;
  } else {
    label = summary ?? `${toolName}(${argsPreview})`;
  }
  return (
    <div
      className={`inline-flex max-w-full items-center gap-2 rounded-full border bg-[--color-bg-elevated] px-3 py-1 text-sm ${STATUS_STYLE[status]}`}
    >
      <span className="truncate">{label}</span>
    </div>
  );
}
```

- [ ] **Step 8: Implement `ErrorMessage.tsx`**

```tsx
// frontend/src/components/chat/ErrorMessage.tsx
import React from 'react';
import { AlertCircle } from 'lucide-react';
import { LiaBadge } from './LiaBadge';

interface Props {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: Props): JSX.Element {
  return (
    <div className="flex items-start gap-3">
      <LiaBadge />
      <div className="flex items-center gap-2 text-sm text-[--color-feedback-error]">
        <AlertCircle size={14} aria-hidden="true" />
        <span>{message}</span>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="ml-1 text-[--color-accent-primary] hover:underline"
          >
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/messages.test.tsx`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/chat/LiaBadge.tsx \
        frontend/src/components/chat/UserBubble.tsx \
        frontend/src/components/chat/AssistantMessage.tsx \
        frontend/src/components/chat/ThinkingIndicator.tsx \
        frontend/src/components/chat/ToolCallChip.tsx \
        frontend/src/components/chat/ErrorMessage.tsx \
        frontend/src/components/chat/__tests__/messages.test.tsx
git commit -m "feat(chat): add message, badge, indicator, tool-call, and error components"
```

---

### Task 7: MessageList scroll container

**Files:**
- Create: `frontend/src/components/chat/MessageList.tsx`
- Test: `frontend/src/components/chat/__tests__/MessageList.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/chat/__tests__/MessageList.test.tsx
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageList } from '../MessageList';

describe('MessageList', () => {
  it('renders children in a scroll container', () => {
    render(
      <MessageList>
        <div>first</div>
        <div>second</div>
      </MessageList>,
    );
    expect(screen.getByText('first')).toBeInTheDocument();
    expect(screen.getByText('second')).toBeInTheDocument();
  });

  it('applies the message column max-width', () => {
    render(<MessageList><div>x</div></MessageList>);
    const inner = screen.getByTestId('message-column');
    expect(inner.className).toMatch(/max-w-\[720px\]/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/MessageList.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `MessageList.tsx`**

```tsx
// frontend/src/components/chat/MessageList.tsx
import React, { useEffect, useRef } from 'react';

interface Props {
  children: React.ReactNode;
  autoscrollKey?: unknown;
}

export function MessageList({ children, autoscrollKey }: Props): JSX.Element {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [autoscrollKey]);

  return (
    <div className="absolute inset-0 overflow-y-auto">
      <div
        data-testid="message-column"
        className="mx-auto max-w-[720px] space-y-2 px-6 py-8 pb-6"
      >
        {children}
        <div ref={endRef} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/MessageList.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/MessageList.tsx \
        frontend/src/components/chat/__tests__/MessageList.test.tsx
git commit -m "feat(chat): add MessageList scroll container with autoscroll"
```

---

### Task 8: ChatInput (textarea + send/stop buttons)

**Files:**
- Create: `frontend/src/components/chat/ChatInput.tsx`
- Test: `frontend/src/components/chat/__tests__/ChatInput.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/chat/__tests__/ChatInput.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ChatInput } from '../ChatInput';

describe('ChatInput', () => {
  it('disables send when empty', () => {
    render(<ChatInput onSend={() => {}} isStreaming={false} placeholder="Ask" />);
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled();
  });

  it('enables send when user types', () => {
    render(<ChatInput onSend={() => {}} isStreaming={false} placeholder="Ask" />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hi' } });
    expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled();
  });

  it('calls onSend with text and clears on Enter', () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="Ask" />);
    const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: 'hello' } });
    fireEvent.keyDown(ta, { key: 'Enter' });
    expect(onSend).toHaveBeenCalledWith('hello');
    expect(ta.value).toBe('');
  });

  it('does not send on Shift+Enter', () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="Ask" />);
    const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: 'hi' } });
    fireEvent.keyDown(ta, { key: 'Enter', shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it('shows stop button while streaming', () => {
    const onStop = vi.fn();
    render(<ChatInput onSend={() => {}} onStop={onStop} isStreaming={true} placeholder="Ask" />);
    fireEvent.click(screen.getByRole('button', { name: /stop generating/i }));
    expect(onStop).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/ChatInput.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ChatInput.tsx`**

```tsx
// frontend/src/components/chat/ChatInput.tsx
import React, { useState } from 'react';
import { ArrowUp, Square } from 'lucide-react';

interface Props {
  onSend: (text: string) => void;
  onStop?: () => void;
  isStreaming: boolean;
  placeholder: string;
}

export function ChatInput({ onSend, onStop, isStreaming, placeholder }: Props): JSX.Element {
  const [value, setValue] = useState('');

  const submit = () => {
    const trimmed = value.trim();
    if (\!trimmed) return;
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && \!e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex-shrink-0 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-6 py-4">
      <div className="mx-auto max-w-[720px]">
        <div className="flex items-end gap-2 rounded-xl border border-[--color-border-subtle] bg-[--color-bg-input] px-4 py-3 transition-all duration-fast focus-within:border-[--color-accent-primary]/40 focus-within:shadow-[0_0_0_1px_rgba(59,130,246,0.12),_0_4px_20px_rgba(59,130,246,0.06)]">
          <textarea
            aria-label="Chat message"
            placeholder={placeholder}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 resize-none bg-transparent text-md leading-relaxed text-[--color-text-primary] outline-none placeholder:text-[--color-text-tertiary]"
            style={{ maxHeight: 120 }}
          />
          {isStreaming ? (
            <button
              type="button"
              aria-label="Stop generating"
              onClick={onStop}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-[--color-surface-active] text-[--color-text-secondary] transition-colors duration-fast hover:bg-[--color-surface-hover]"
            >
              <Square size={14} />
            </button>
          ) : (
            <button
              type="button"
              aria-label="Send"
              onClick={submit}
              disabled={value.trim().length === 0}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-[--color-accent-primary] text-white transition-all duration-fast hover:bg-[--color-accent-hover] hover:scale-105 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
            >
              <ArrowUp size={14} />
            </button>
          )}
        </div>
        <p className="mt-2 select-none text-center text-xs text-[--color-text-tertiary]">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/ChatInput.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/ChatInput.tsx \
        frontend/src/components/chat/__tests__/ChatInput.test.tsx
git commit -m "feat(chat): add ChatInput with send/stop and keyboard handling"
```

---

### Task 9: WelcomeOverlay

**Files:**
- Create: `frontend/src/components/chat/WelcomeOverlay.tsx`
- Test: `frontend/src/components/chat/__tests__/WelcomeOverlay.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/chat/__tests__/WelcomeOverlay.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { WelcomeOverlay } from '../WelcomeOverlay';

describe('WelcomeOverlay', () => {
  it('renders greeting and sub-text', () => {
    render(<WelcomeOverlay greeting="Good morning" subtext="What can I do?" chips={[]} onChipClick={() => {}} />);
    expect(screen.getByText('Good morning')).toBeInTheDocument();
    expect(screen.getByText('What can I do?')).toBeInTheDocument();
  });

  it('renders chips and fires onChipClick with the chip value', () => {
    const onClick = vi.fn();
    render(
      <WelcomeOverlay
        greeting="Hi"
        subtext=""
        chips={[
          { label: 'Market today', value: 'What moved the market today?' },
          { label: 'Top movers', value: 'Top movers' },
        ]}
        onChipClick={onClick}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /market today/i }));
    expect(onClick).toHaveBeenCalledWith('What moved the market today?');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/WelcomeOverlay.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `WelcomeOverlay.tsx`**

```tsx
// frontend/src/components/chat/WelcomeOverlay.tsx
import React from 'react';
import { motion } from 'framer-motion';

interface Chip { label: string; value: string }

interface Props {
  greeting: string;
  subtext: string;
  chips: Chip[];
  onChipClick: (value: string) => void;
}

export function WelcomeOverlay({ greeting, subtext, chips, onChipClick }: Props): JSX.Element {
  return (
    <motion.div
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.2, ease: 'easeIn' }}
      className="relative flex h-full w-full flex-col items-center justify-center px-6"
      style={{
        backgroundImage:
          'radial-gradient(circle, var(--color-border-subtle) 1px, transparent 1px)',
        backgroundSize: '28px 28px',
      }}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 65% 45% at 50% 65%, var(--color-accent-subtle) 0%, transparent 70%)',
          opacity: 0.6,
        }}
      />
      <h1
        className="relative text-center text-[30px] text-[--color-text-primary]"
        style={{ fontFamily: 'DM Serif Display, serif' }}
      >
        {greeting}
      </h1>
      {subtext ? (
        <p className="relative mt-2 text-center text-md text-[--color-text-secondary]">{subtext}</p>
      ) : null}
      {chips.length > 0 ? (
        <div className="relative mt-8 flex max-w-[540px] flex-wrap justify-center gap-2">
          {chips.map((c, idx) => (
            <motion.button
              key={c.label}
              type="button"
              onClick={() => onChipClick(c.value)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut', delay: 0.2 + idx * 0.05 }}
              whileHover={{ scale: 1.02, transition: { type: 'spring', stiffness: 400, damping: 20 } }}
              className="rounded-full border border-[--color-border-secondary]/60 bg-[--color-bg-elevated]/80 px-3.5 py-2 text-sm text-[--color-text-secondary] backdrop-blur-sm hover:border-[--color-accent-primary]/40 hover:bg-[--color-accent-subtle]/50 hover:text-[--color-accent-primary]"
            >
              {c.label}
            </motion.button>
          ))}
        </div>
      ) : null}
    </motion.div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/WelcomeOverlay.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/WelcomeOverlay.tsx \
        frontend/src/components/chat/__tests__/WelcomeOverlay.test.tsx
git commit -m "feat(chat): add WelcomeOverlay with dot-grid background and chip row"
```

---

### Task 10: ChatInterface top-level component

**Files:**
- Create: `frontend/src/components/chat/ChatInterface.tsx`
- Test: `frontend/src/components/chat/__tests__/ChatInterface.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/chat/__tests__/ChatInterface.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatInterface } from '../ChatInterface';
import * as chatApi from '../../../api/chat';

vi.mock('../useChatStream', () => ({
  useChatStream: () => ({
    state: {
      status: 'idle',
      message: '',
      toolCalls: [],
      reportThumbnails: [],
      errorMessage: null,
    },
    send: vi.fn(),
    stop: vi.fn(),
    reset: vi.fn(),
  }),
}));

describe('ChatInterface', () => {
  beforeEach(() => {
    vi.spyOn(chatApi, 'listMessages').mockResolvedValue({ items: [] });
  });

  it('shows welcome overlay when there are no messages', async () => {
    render(<ChatInterface sessionId={1} greeting="Good evening" subtext="Ask LIA" chips={[]} inputPlaceholder="Ask" />);
    await waitFor(() => screen.getByText('Good evening'));
  });

  it('hides welcome overlay after first send', async () => {
    render(<ChatInterface sessionId={1} greeting="Good evening" subtext="Ask LIA" chips={[]} inputPlaceholder="Ask" />);
    await waitFor(() => screen.getByText('Good evening'));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hello' } });
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    await waitFor(() => expect(screen.queryByText('Good evening')).toBeNull());
  });

  it('renders persisted messages from the backend', async () => {
    vi.spyOn(chatApi, 'listMessages').mockResolvedValue({
      items: [
        { id: '00000000-0000-4000-8000-000000000001', role: 'user', content: 'hi', tool_calls: null, model_ref: null, token_usage: null, created_at: '2026-04-01T00:00:00Z' },
        { id: '00000000-0000-4000-8000-000000000002', role: 'assistant', content: 'hello', tool_calls: null, model_ref: null, token_usage: null, created_at: '2026-04-01T00:00:00Z' },
      ],
    });
    render(<ChatInterface sessionId={1} greeting="x" subtext="" chips={[]} inputPlaceholder="Ask" />);
    await waitFor(() => screen.getByText('hi'));
    expect(screen.getByText('hello')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/ChatInterface.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ChatInterface.tsx`**

```tsx
// frontend/src/components/chat/ChatInterface.tsx
import React, { useEffect, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ChatMessage, listMessages } from '../../api/chat';
import { ChatInput } from './ChatInput';
import { MessageList } from './MessageList';
import { UserBubble } from './UserBubble';
import { AssistantMessage } from './AssistantMessage';
import { ThinkingIndicator } from './ThinkingIndicator';
import { ToolCallChip } from './ToolCallChip';
import { ErrorMessage } from './ErrorMessage';
import { WelcomeOverlay } from './WelcomeOverlay';
import { useChatStream } from './useChatStream';
import { ReportThumbnail } from './ReportThumbnail';

interface Chip { label: string; value: string }

interface Props {
  sessionId: number;
  greeting: string;
  subtext: string;
  chips: Chip[];
  inputPlaceholder: string;
}

export function ChatInterface({ sessionId, greeting, subtext, chips, inputPlaceholder }: Props): JSX.Element {
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [sentOnce, setSentOnce] = useState(false);
  const { state, send, stop } = useChatStream({ sessionId });

  useEffect(() => {
    listMessages(sessionId).then((r) => {
      setHistory(r.items);
      if (r.items.length > 0) setSentOnce(true);
      setLoaded(true);
    });
  }, [sessionId]);

  const onSend = (text: string) => {
    setSentOnce(true);
    setHistory((prev) => [
      ...prev,
      {
        id: -Date.now(),
        role: 'user',
        content: text,
        tool_calls: null,
        model_ref: null, token_usage: null,
        created_at: new Date().toISOString(),
      },
    ]);
    send(text);
  };

  const isStreaming =
    state.status === 'opening' ||
    state.status === 'thinking' ||
    state.status === 'streaming';

  const showWelcome = loaded && \!sentOnce;

  return (
    <div className="relative flex h-full flex-col">
      <div className="relative flex-1">
        <AnimatePresence>{showWelcome ? (
          <WelcomeOverlay
            greeting={greeting}
            subtext={subtext}
            chips={chips}
            onChipClick={onSend}
          />
        ) : null}</AnimatePresence>
        {\!showWelcome ? (
          <MessageList autoscrollKey={state.message + history.length}>
            {history.map((m) =>
              m.role === 'user' ? (
                <UserBubble key={m.id} content={m.content} />
              ) : (
                <AssistantMessage key={m.id} content={m.content} streaming={false} stopped={false} />
              ),
            )}
            {state.status === 'thinking' ? <ThinkingIndicator /> : null}
            {state.toolCalls.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {state.toolCalls.map((c) => (
                  <ToolCallChip
                    key={c.callId}
                    toolName={c.toolName}
                    argsPreview={c.argsPreview}
                    status={c.status}
                    summary={c.summary}
                  />
                ))}
              </div>
            ) : null}
            {(state.status === 'streaming' || state.status === 'done' || state.status === 'stopped') &&
            state.message ? (
              <AssistantMessage
                content={state.message}
                streaming={state.status === 'streaming'}
                stopped={state.status === 'stopped'}
              />
            ) : null}
            {state.reportThumbnails.map((t) => (
              <ReportThumbnail key={t.report_id} reportId={t.report_id} filename={t.filename} />
            ))}
            {state.status === 'error' && state.errorMessage ? (
              <ErrorMessage
                message={state.errorMessage}
                onRetry={() => send(history[history.length - 1]?.content ?? '')}
              />
            ) : null}
          </MessageList>
        ) : null}
      </div>
      <ChatInput
        onSend={onSend}
        onStop={stop}
        isStreaming={isStreaming}
        placeholder={inputPlaceholder}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/ChatInterface.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/ChatInterface.tsx \
        frontend/src/components/chat/__tests__/ChatInterface.test.tsx
git commit -m "feat(chat): add ChatInterface top-level component"
```

---

### Task 11: ChatHistoryDrawer (session list)

**Files:**
- Create: `frontend/src/components/chat/ChatHistoryDrawer.tsx`
- Test: `frontend/src/components/chat/__tests__/ChatHistoryDrawer.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/chat/__tests__/ChatHistoryDrawer.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatHistoryDrawer } from '../ChatHistoryDrawer';
import * as chatApi from '../../../api/chat';

describe('ChatHistoryDrawer', () => {
  beforeEach(() => {
    vi.spyOn(chatApi, 'listSessions').mockResolvedValue({
      items: [
        { id: '00000000-0000-4000-8000-000000000001', department: 'secretary', title: 'Pinned', is_pinned: true, is_archived: false, created_at: '2026-04-01T00:00:00Z' },
        { id: '00000000-0000-4000-8000-000000000002', department: 'secretary', title: 'Recent', is_pinned: false, is_archived: false, created_at: '2026-04-01T00:00:00Z' },
      ],
    });
  });

  it('renders pinned and recent sections', async () => {
    render(<ChatHistoryDrawer department="secretary" activeSessionId={1} onSelect={() => {}} onCreate={() => {}} />);
    await waitFor(() => screen.getByText('Pinned'));
    expect(screen.getByText('Recent')).toBeInTheDocument();
  });

  it('fires onSelect when a session is clicked', async () => {
    const onSelect = vi.fn();
    render(<ChatHistoryDrawer department="secretary" activeSessionId={1} onSelect={onSelect} onCreate={() => {}} />);
    await waitFor(() => screen.getByText('Recent'));
    fireEvent.click(screen.getByText('Recent'));
    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it('creates a new session', async () => {
    const onCreate = vi.fn();
    vi.spyOn(chatApi, 'createSession').mockResolvedValue({
      id: '00000000-0000-4000-8000-000000000009'9, department: 'secretary', title: 'New', is_pinned: false, is_archived: false, created_at: '2026-04-01T00:00:00Z',
    });
    render(<ChatHistoryDrawer department="secretary" activeSessionId={1} onSelect={() => {}} onCreate={onCreate} />);
    await waitFor(() => screen.getByText('Recent'));
    fireEvent.click(screen.getByRole('button', { name: /new chat/i }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(99));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/ChatHistoryDrawer.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ChatHistoryDrawer.tsx`**

```tsx
// frontend/src/components/chat/ChatHistoryDrawer.tsx
import React, { useEffect, useState } from 'react';
import { ChatSession, Department, createSession, listSessions, patchSession, deleteSession } from '../../api/chat';
import { Pin, Archive, Trash, Pencil, Plus } from 'lucide-react';

interface Props {
  department: Department;
  activeSessionId: number | null;
  onSelect: (sessionId: number) => void;
  onCreate: (sessionId: number) => void;
}

export function ChatHistoryDrawer({ department, activeSessionId, onSelect, onCreate }: Props): JSX.Element {
  const [items, setItems] = useState<ChatSession[] | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const refresh = async () => {
    const r = await listSessions();
    setItems(r.items.filter((i) => i.department === department));
  };

  useEffect(() => { refresh(); }, [department]);

  const newChat = async () => {
    const row = await createSession({ department, title: 'New chat' });
    await refresh();
    onCreate(row.id);
  };

  const pinned = (items ?? []).filter((i) => i.is_pinned);
  const recent = (items ?? []).filter((i) => \!i.is_pinned);

  const SessionRow = ({ s }: { s: ChatSession }) => {
    const active = s.id === activeSessionId;
    const isEditing = editingId === s.id;
    return (
      <li
        className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
          active ? 'bg-[--color-surface-active] text-[--color-text-primary]' : 'text-[--color-text-secondary] hover:bg-[--color-surface-hover]'
        }`}
      >
        {isEditing ? (
          <input
            autoFocus
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={async () => {
              if (editTitle.trim()) await patchSession(s.id, { title: editTitle.trim() });
              setEditingId(null);
              refresh();
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
              if (e.key === 'Escape') setEditingId(null);
            }}
            className="flex-1 rounded bg-[--color-bg-input] px-1 py-0.5 text-[--color-text-primary] outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={() => onSelect(s.id)}
            className="flex-1 truncate text-left"
          >
            {s.title}
          </button>
        )}
        <div className="hidden gap-1 group-hover:flex">
          <button
            type="button"
            aria-label="Rename"
            onClick={() => {
              setEditingId(s.id);
              setEditTitle(s.title);
            }}
            className="rounded p-1 hover:bg-[--color-surface-hover]"
          >
            <Pencil size={12} />
          </button>
          <button
            type="button"
            aria-label={s.is_pinned ? 'Unpin' : 'Pin'}
            onClick={async () => {
              await patchSession(s.id, { pinned: \!s.is_pinned });
              refresh();
            }}
            className="rounded p-1 hover:bg-[--color-surface-hover]"
          >
            <Pin size={12} />
          </button>
          <button
            type="button"
            aria-label="Archive"
            onClick={async () => {
              await patchSession(s.id, { archived: true });
              refresh();
            }}
            className="rounded p-1 hover:bg-[--color-surface-hover]"
          >
            <Archive size={12} />
          </button>
          <button
            type="button"
            aria-label="Delete"
            onClick={async () => {
              if (window.confirm(`Delete "${s.title}"? This cannot be undone.`)) {
                await deleteSession(s.id);
                refresh();
              }
            }}
            className="rounded p-1 text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
          >
            <Trash size={12} />
          </button>
        </div>
      </li>
    );
  };

  return (
    <aside className="flex h-full w-60 flex-col border-r border-[--color-border-subtle] bg-[--color-bg-base]">
      <div className="flex items-center justify-between p-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[--color-text-tertiary]">
          Chat history
        </h2>
        <button
          type="button"
          onClick={newChat}
          aria-label="New chat"
          className="flex h-6 w-6 items-center justify-center rounded-md bg-[--color-accent-primary] text-white hover:bg-[--color-accent-hover]"
        >
          <Plus size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {pinned.length > 0 ? (
          <>
            <h3 className="mt-2 px-2 text-[11px] font-semibold uppercase text-[--color-text-tertiary]">
              Pinned
            </h3>
            <ul className="mt-1 space-y-0.5">
              {pinned.map((s) => <SessionRow key={s.id} s={s} />)}
            </ul>
          </>
        ) : null}
        {recent.length > 0 ? (
          <>
            <h3 className="mt-4 px-2 text-[11px] font-semibold uppercase text-[--color-text-tertiary]">
              Recent
            </h3>
            <ul className="mt-1 space-y-0.5">
              {recent.map((s) => <SessionRow key={s.id} s={s} />)}
            </ul>
          </>
        ) : null}
        {items \!== null && items.length === 0 ? (
          <p className="mt-6 px-2 text-xs text-[--color-text-tertiary]">No conversations yet.</p>
        ) : null}
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/ChatHistoryDrawer.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/ChatHistoryDrawer.tsx \
        frontend/src/components/chat/__tests__/ChatHistoryDrawer.test.tsx
git commit -m "feat(chat): add ChatHistoryDrawer with pin/rename/archive/delete"
```

---

### Task 12: AttachmentChip + ReportThumbnail + FileViewerContext

**Files:**
- Create: `frontend/src/components/viewer/FileViewerContext.tsx`
- Create: `frontend/src/components/chat/AttachmentChip.tsx`
- Create: `frontend/src/components/chat/ReportThumbnail.tsx`
- Test: `frontend/src/components/chat/__tests__/AttachmentChip.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/chat/__tests__/AttachmentChip.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AttachmentChip } from '../AttachmentChip';
import { FileViewerProvider, useFileViewer } from '../../viewer/FileViewerContext';

function Probe() {
  const { current } = useFileViewer();
  return <div data-testid="probe">{current ? `${current.filename}:${current.kind}` : 'none'}</div>;
}

describe('AttachmentChip', () => {
  it('opens the file viewer context on click', () => {
    render(
      <FileViewerProvider>
        <Probe />
        <AttachmentChip
          filename="q.pdf"
          fileType="pdf"
          metadata="PDF · 248 KB"
          source={{ kind: 'attachment', attachmentId: 7 }}
        />
      </FileViewerProvider>,
    );
    expect(screen.getByTestId('probe')).toHaveTextContent('none');
    fireEvent.click(screen.getByText('q.pdf'));
    expect(screen.getByTestId('probe')).toHaveTextContent('q.pdf:pdf');
  });

  it('does not open viewer when clicking the download button', () => {
    render(
      <FileViewerProvider>
        <Probe />
        <AttachmentChip
          filename="q.pdf"
          fileType="pdf"
          metadata="PDF"
          source={{ kind: 'attachment', attachmentId: 7 }}
        />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: /download/i }));
    expect(screen.getByTestId('probe')).toHaveTextContent('none');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/AttachmentChip.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `FileViewerContext.tsx`**

```tsx
// frontend/src/components/viewer/FileViewerContext.tsx
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

export type FileKind = 'pdf' | 'markdown' | 'text' | 'code' | 'csv' | 'image' | 'docx' | 'unknown';

export type FileSource =
  | { kind: 'attachment'; attachmentId: number }
  | { kind: 'report'; reportId: number };

export interface FileViewerTarget {
  filename: string;
  kind: FileKind;
  metadata: string;
  source: FileSource;
}

interface ContextShape {
  current: FileViewerTarget | null;
  open: (target: FileViewerTarget) => void;
  close: () => void;
}

const FileViewerContext = createContext<ContextShape | null>(null);

export function FileViewerProvider({ children }: { children: React.ReactNode }): JSX.Element {
  const [current, setCurrent] = useState<FileViewerTarget | null>(null);
  const open = useCallback((t: FileViewerTarget) => setCurrent(t), []);
  const close = useCallback(() => setCurrent(null), []);
  const value = useMemo(() => ({ current, open, close }), [current, open, close]);
  return <FileViewerContext.Provider value={value}>{children}</FileViewerContext.Provider>;
}

export function useFileViewer(): ContextShape {
  const ctx = useContext(FileViewerContext);
  if (\!ctx) throw new Error('useFileViewer requires FileViewerProvider');
  return ctx;
}

export function kindFromFilename(name: string): FileKind {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (ext === 'pdf') return 'pdf';
  if (ext === 'md' || ext === 'markdown') return 'markdown';
  if (ext === 'txt' || ext === 'log') return 'text';
  if (['py', 'js', 'ts', 'tsx', 'json', 'yaml', 'yml', 'toml'].includes(ext)) return 'code';
  if (ext === 'csv' || ext === 'tsv') return 'csv';
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) return 'image';
  if (ext === 'docx' || ext === 'pptx') return 'docx';
  return 'unknown';
}
```

- [ ] **Step 4: Implement `AttachmentChip.tsx`**

```tsx
// frontend/src/components/chat/AttachmentChip.tsx
import React from 'react';
import { FileText, Sheet, Image as ImageIcon, FileCode, File } from 'lucide-react';
import { FileKind, FileSource, useFileViewer } from '../viewer/FileViewerContext';
import { SaveToRepoButton } from './SaveToRepoButton';
import { FileDownloadButton } from './FileDownloadButton';

interface Props {
  filename: string;
  fileType: FileKind;
  metadata: string;
  source: FileSource;
  reportId?: number;
}

const ICON: Record<FileKind, React.ComponentType<{ size: number }>> = {
  pdf: FileText,
  markdown: FileText,
  text: FileText,
  code: FileCode,
  csv: Sheet,
  image: ImageIcon,
  docx: FileText,
  unknown: File,
};

export function AttachmentChip({ filename, fileType, metadata, source, reportId }: Props): JSX.Element {
  const { open } = useFileViewer();
  const Icon = ICON[fileType];

  const openViewer = () => open({ filename, kind: fileType, metadata, source });

  return (
    <div
      className="group inline-flex max-w-[320px] cursor-pointer items-center gap-3 rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-2.5 transition-all duration-fast hover:border-[--color-border-secondary] hover:shadow-sm"
      onClick={(e) => {
        if ((e.target as HTMLElement).closest('[data-chip-action]')) return;
        openViewer();
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openViewer();
        }
      }}
    >
      <Icon size={20} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-base font-medium text-[--color-text-primary]" style={{ maxWidth: 160 }}>
          {filename}
        </p>
        <p className="text-xs text-[--color-text-secondary]">{metadata}</p>
      </div>
      <div className="ml-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100" data-chip-action>
        {reportId \!== undefined ? (
          <SaveToRepoButton variant="chip" reportId={reportId} filename={filename} />
        ) : null}
        <FileDownloadButton variant="chip" source={source} filename={filename} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implement `ReportThumbnail.tsx`**

```tsx
// frontend/src/components/chat/ReportThumbnail.tsx
import React from 'react';
import { AttachmentChip } from './AttachmentChip';
import { kindFromFilename } from '../viewer/FileViewerContext';

interface Props {
  reportId: number;
  filename: string;
  metadata?: string;
}

export function ReportThumbnail({ reportId, filename, metadata }: Props): JSX.Element {
  const kind = kindFromFilename(filename);
  return (
    <AttachmentChip
      filename={filename}
      fileType={kind}
      metadata={metadata ?? kind.toUpperCase()}
      source={{ kind: 'report', reportId }}
      reportId={reportId}
    />
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/AttachmentChip.test.tsx`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/viewer/FileViewerContext.tsx \
        frontend/src/components/chat/AttachmentChip.tsx \
        frontend/src/components/chat/ReportThumbnail.tsx \
        frontend/src/components/chat/__tests__/AttachmentChip.test.tsx
git commit -m "feat(chat): add AttachmentChip, ReportThumbnail, and FileViewerContext"
```

---

### Task 13: FileViewer shell + ViewerHeader

**Files:**
- Create: `frontend/src/components/viewer/FileViewer.tsx`
- Create: `frontend/src/components/viewer/ViewerHeader.tsx`
- Create: `frontend/src/components/viewer/ResizeHandle.tsx`
- Test: `frontend/src/components/viewer/__tests__/FileViewer.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/viewer/__tests__/FileViewer.test.tsx
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { FileViewer } from '../FileViewer';
import { FileViewerProvider, useFileViewer } from '../FileViewerContext';

function Trigger() {
  const { open } = useFileViewer();
  return (
    <button onClick={() => open({ filename: 'q.pdf', kind: 'pdf', metadata: 'PDF · 12 pages', source: { kind: 'report', reportId: 5 } })}>
      open
    </button>
  );
}

describe('FileViewer', () => {
  it('renders nothing when no file is open', () => {
    const { container } = render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    expect(container.querySelector('[role="complementary"]')).toBeNull();
  });

  it('renders panel with filename + metadata after opening', () => {
    render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByText('open'));
    expect(screen.getByText('q.pdf')).toBeInTheDocument();
    expect(screen.getByText('PDF · 12 pages')).toBeInTheDocument();
  });

  it('closes when the close button is clicked', () => {
    const { container } = render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByText('open'));
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(container.querySelector('[role="complementary"]')).toBeNull();
  });

  it('closes on Escape', () => {
    const { container } = render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByText('open'));
    fireEvent.keyDown(screen.getByRole('complementary'), { key: 'Escape' });
    expect(container.querySelector('[role="complementary"]')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/viewer/__tests__/FileViewer.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ResizeHandle.tsx`**

```tsx
// frontend/src/components/viewer/ResizeHandle.tsx
import React, { useCallback, useRef } from 'react';

interface Props {
  onWidthChange: (next: number) => void;
  viewportWidth: number;
}

export function ResizeHandle({ onWidthChange, viewportWidth }: Props): JSX.Element {
  const dragging = useRef(false);

  const onDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      dragging.current = true;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [],
  );

  const onMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (\!dragging.current) return;
      const next = Math.max(360, Math.min(viewportWidth * 0.7, viewportWidth - e.clientX));
      onWidthChange(next);
      try {
        localStorage.setItem('fileviewer_width', String(Math.round(next)));
      } catch {}
    },
    [onWidthChange, viewportWidth],
  );

  const onUp = useCallback(() => { dragging.current = false; }, []);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize file viewer"
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      className="absolute inset-y-0 left-0 z-10 w-1 cursor-col-resize hover:bg-[--color-border-secondary] [[data-dragging=true]_&]:bg-[--color-accent-primary]"
    />
  );
}
```

- [ ] **Step 4: Implement `ViewerHeader.tsx`**

```tsx
// frontend/src/components/viewer/ViewerHeader.tsx
import React from 'react';
import { X } from 'lucide-react';
import { FileSource } from './FileViewerContext';
import { SaveToRepoButton } from '../chat/SaveToRepoButton';
import { FileDownloadButton } from '../chat/FileDownloadButton';

interface Props {
  filename: string;
  metadata: string;
  source: FileSource;
  reportId?: number;
  onClose: () => void;
}

export function ViewerHeader({ filename, metadata, source, reportId, onClose }: Props): JSX.Element {
  return (
    <div className="flex min-h-[56px] flex-shrink-0 items-start justify-between gap-3 border-b border-[--color-border-subtle] bg-[--color-bg-elevated] px-4 py-3">
      <div className="flex min-w-0 flex-1 flex-col">
        <p className="truncate text-base font-medium text-[--color-text-primary]">{filename}</p>
        <p className="mt-0.5 truncate text-xs text-[--color-text-secondary]">{metadata}</p>
      </div>
      <div className="ml-2 flex flex-shrink-0 items-center gap-1.5">
        {reportId \!== undefined ? (
          <SaveToRepoButton variant="viewer-header" reportId={reportId} filename={filename} />
        ) : null}
        <FileDownloadButton variant="viewer-header" source={source} filename={filename} />
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-[--radius-md] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implement `FileViewer.tsx`**

```tsx
// frontend/src/components/viewer/FileViewer.tsx
import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useFileViewer } from './FileViewerContext';
import { ViewerHeader } from './ViewerHeader';
import { ResizeHandle } from './ResizeHandle';
import { MarkdownRenderer } from './renderers/MarkdownRenderer';
import { PdfRenderer } from './renderers/PdfRenderer';
import { CsvRenderer } from './renderers/CsvRenderer';
import { CodeRenderer } from './renderers/CodeRenderer';
import { ImageRenderer } from './renderers/ImageRenderer';
import { UnsupportedRenderer } from './renderers/UnsupportedRenderer';

function initialWidth(): number {
  const stored = typeof localStorage \!== 'undefined' ? localStorage.getItem('fileviewer_width') : null;
  return stored ? Math.max(360, parseInt(stored, 10) || 560) : 560;
}

export function FileViewer(): JSX.Element | null {
  const { current, close } = useFileViewer();
  const [width, setWidth] = useState<number>(initialWidth);
  const [viewportWidth, setViewportWidth] = useState<number>(
    typeof window \!== 'undefined' ? window.innerWidth : 1200,
  );

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return (
    <AnimatePresence>
      {current ? (
        <motion.aside
          key={current.filename}
          role="complementary"
          aria-label={`File viewer: ${current.filename}`}
          tabIndex={-1}
          onKeyDown={(e) => {
            if (e.key === 'Escape') close();
          }}
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="relative flex h-full flex-shrink-0 flex-col border-l border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg"
          style={{ width }}
        >
          <ResizeHandle
            onWidthChange={setWidth}
            viewportWidth={viewportWidth}
          />
          <ViewerHeader
            filename={current.filename}
            metadata={current.metadata}
            source={current.source}
            reportId={current.source.kind === 'report' ? current.source.reportId : undefined}
            onClose={close}
          />
          <div className="flex-1 overflow-y-auto">
            {current.kind === 'markdown' && <MarkdownRenderer source={current.source} />}
            {current.kind === 'pdf' && <PdfRenderer source={current.source} />}
            {current.kind === 'csv' && <CsvRenderer source={current.source} />}
            {current.kind === 'code' && <CodeRenderer source={current.source} />}
            {current.kind === 'text' && <CodeRenderer source={current.source} />}
            {current.kind === 'image' && <ImageRenderer source={current.source} />}
            {(current.kind === 'docx' || current.kind === 'unknown') && (
              <UnsupportedRenderer source={current.source} filename={current.filename} />
            )}
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/viewer/__tests__/FileViewer.test.tsx`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/viewer/FileViewer.tsx \
        frontend/src/components/viewer/ViewerHeader.tsx \
        frontend/src/components/viewer/ResizeHandle.tsx \
        frontend/src/components/viewer/__tests__/FileViewer.test.tsx
git commit -m "feat(viewer): add FileViewer shell with header and resize handle"
```

---

### Task 14: FileViewer renderers (Markdown, Code, CSV, Image, Unsupported)

**Files:**
- Create: `frontend/src/components/viewer/renderers/MarkdownRenderer.tsx`
- Create: `frontend/src/components/viewer/renderers/CodeRenderer.tsx`
- Create: `frontend/src/components/viewer/renderers/CsvRenderer.tsx`
- Create: `frontend/src/components/viewer/renderers/ImageRenderer.tsx`
- Create: `frontend/src/components/viewer/renderers/UnsupportedRenderer.tsx`
- Test: `frontend/src/components/viewer/renderers/__tests__/renderers.test.tsx`

These renderers fetch file contents via the download endpoint (which serves the bytes inline when called without `Accept: application/octet-stream`). For the initial implementation, all renderers use `fetch()` against the same URL as the download button; the server already returns the raw bytes with the appropriate `Content-Type`. For binary formats (images), we use an `<img>` tag pointing at the download URL directly.

- [ ] **Step 1: Install markdown deps**

```bash
cd frontend && npm install react-markdown remark-gfm
```

- [ ] **Step 2: Write failing test**

```tsx
// frontend/src/components/viewer/renderers/__tests__/renderers.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MarkdownRenderer } from '../MarkdownRenderer';
import { CodeRenderer } from '../CodeRenderer';
import { CsvRenderer } from '../CsvRenderer';
import { ImageRenderer } from '../ImageRenderer';
import { UnsupportedRenderer } from '../UnsupportedRenderer';

function mockFetchText(body: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      text: async () => body,
    }),
  );
}

describe('renderers', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('Markdown renders headings and paragraphs', async () => {
    mockFetchText('# Hello\n\nThis is content.');
    render(<MarkdownRenderer source={{ kind: 'report', reportId: 1 }} />);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Hello' })).toBeInTheDocument());
  });

  it('Code renders monospace body with line numbers', async () => {
    mockFetchText('line1\nline2');
    render(<CodeRenderer source={{ kind: 'report', reportId: 1 }} />);
    await waitFor(() => expect(screen.getByText(/line1/)).toBeInTheDocument());
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('CSV renders table with header and rows', async () => {
    mockFetchText('a,b\n1,2\n3,4');
    render(<CsvRenderer source={{ kind: 'report', reportId: 1 }} />);
    await waitFor(() => expect(screen.getByText('a')).toBeInTheDocument());
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('Image renders <img> with download URL', () => {
    render(<ImageRenderer source={{ kind: 'attachment', attachmentId: 7 }} />);
    const img = screen.getByRole('img') as HTMLImageElement;
    expect(img.src).toContain('/api/chat/attachments/7/download');
  });

  it('Unsupported shows message + download link', () => {
    render(<UnsupportedRenderer source={{ kind: 'report', reportId: 5 }} filename="x.exe" />);
    expect(screen.getByText(/preview not available/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /download/i })).toHaveAttribute('href', '/api/reports/5/download');
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/viewer/renderers/__tests__/renderers.test.tsx`
Expected: FAIL.

- [ ] **Step 4: Implement helper + renderers**

```tsx
// frontend/src/components/viewer/renderers/sourceUrl.ts
import { FileSource } from '../FileViewerContext';
import { downloadUrlForAttachment, downloadUrlForReport } from '../../../api/files';

export function sourceUrl(source: FileSource): string {
  return source.kind === 'report'
    ? downloadUrlForReport(source.reportId)
    : downloadUrlForAttachment(source.attachmentId);
}
```

```tsx
// frontend/src/components/viewer/renderers/MarkdownRenderer.tsx
import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileSource } from '../FileViewerContext';
import { sourceUrl } from './sourceUrl';

export function MarkdownRenderer({ source }: { source: FileSource }): JSX.Element {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetch(sourceUrl(source), { credentials: 'same-origin' })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setText)
      .catch((e) => setError((e as Error).message));
  }, [source]);
  if (error) return <div className="p-6 text-sm text-[--color-feedback-error]">{error}</div>;
  if (text === null) return <div className="animate-pulse space-y-2 p-6">{[...Array(6)].map((_, i) => <div key={i} className="h-4 rounded bg-[--color-surface-hover]" />)}</div>;
  return (
    <article className="mx-auto max-w-[680px] px-6 py-5 text-md leading-relaxed text-[--color-text-primary] prose prose-sm dark:prose-invert">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </article>
  );
}
```

```tsx
// frontend/src/components/viewer/renderers/CodeRenderer.tsx
import React, { useEffect, useState } from 'react';
import { FileSource } from '../FileViewerContext';
import { sourceUrl } from './sourceUrl';

export function CodeRenderer({ source }: { source: FileSource }): JSX.Element {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    fetch(sourceUrl(source), { credentials: 'same-origin' })
      .then((r) => r.text())
      .then(setText);
  }, [source]);
  if (text === null) return <div className="animate-pulse p-6">Loading…</div>;
  const lines = text.split('\n');
  return (
    <div className="flex text-sm">
      <div className="flex-shrink-0 select-none border-r border-[--color-border-subtle] bg-[--color-bg-base] px-4 py-4 text-right font-mono text-[--color-text-tertiary]">
        {lines.map((_, i) => (
          <div key={i}>{i + 1}</div>
        ))}
      </div>
      <pre className="flex-1 overflow-x-auto whitespace-pre bg-[--color-bg-code] px-4 py-4 font-mono text-[--color-text-code]">
        {text}
      </pre>
    </div>
  );
}
```

```tsx
// frontend/src/components/viewer/renderers/CsvRenderer.tsx
import React, { useEffect, useState } from 'react';
import { FileSource } from '../FileViewerContext';
import { sourceUrl } from './sourceUrl';

function parseCsv(text: string, delim = ','): string[][] {
  // v1: split by line and delim; does not handle quoted embedded delimiters.
  // Good enough for typical report CSVs; swap for papaparse when needed.
  return text
    .split('\n')
    .filter((l) => l.length > 0)
    .map((line) => line.split(delim));
}

export function CsvRenderer({ source }: { source: FileSource }): JSX.Element {
  const [rows, setRows] = useState<string[][] | null>(null);
  useEffect(() => {
    fetch(sourceUrl(source), { credentials: 'same-origin' })
      .then((r) => r.text())
      .then((t) => setRows(parseCsv(t)));
  }, [source]);
  if (rows === null) return <div className="p-6 text-sm text-[--color-text-secondary]">Loading…</div>;
  const [header, ...data] = rows;
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-[--color-bg-base]">
          <tr>
            {header.map((h, i) => (
              <th key={i} className="whitespace-nowrap border-b border-[--color-border-subtle] px-3 py-2 font-medium text-[--color-text-primary]">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, ri) => (
            <tr key={ri} className={`border-b border-[--color-border-subtle] last:border-0 ${ri % 2 === 1 ? 'bg-[--color-surface-hover]/40' : ''}`}>
              {row.map((cell, ci) => (
                <td key={ci} className="whitespace-nowrap px-3 py-2 text-[--color-text-secondary]">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

```tsx
// frontend/src/components/viewer/renderers/ImageRenderer.tsx
import React from 'react';
import { FileSource } from '../FileViewerContext';
import { sourceUrl } from './sourceUrl';

export function ImageRenderer({ source }: { source: FileSource }): JSX.Element {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <img
        src={sourceUrl(source)}
        alt=""
        className="max-h-full max-w-full object-contain"
      />
    </div>
  );
}
```

```tsx
// frontend/src/components/viewer/renderers/UnsupportedRenderer.tsx
import React from 'react';
import { FileX } from 'lucide-react';
import { FileSource } from '../FileViewerContext';
import { sourceUrl } from './sourceUrl';

interface Props { source: FileSource; filename: string }

export function UnsupportedRenderer({ source, filename }: Props): JSX.Element {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6">
      <FileX size={40} className="text-[--color-text-tertiary]" aria-hidden="true" />
      <p className="text-base text-[--color-text-secondary]">Preview not available for this file type.</p>
      <a
        href={sourceUrl(source)}
        download={filename}
        className="text-sm text-[--color-accent-primary] hover:underline"
      >
        Download the file to view it
      </a>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/viewer/renderers/__tests__/renderers.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/viewer/renderers/ \
        frontend/package.json frontend/package-lock.json \
        frontend/src/components/viewer/renderers/__tests__/renderers.test.tsx
git commit -m "feat(viewer): add Markdown, Code, CSV, Image, Unsupported renderers"
```

---

### Task 15: PdfRenderer with pdf.js

**Files:**
- Create: `frontend/src/components/viewer/renderers/PdfRenderer.tsx`
- Test: `frontend/src/components/viewer/renderers/__tests__/PdfRenderer.test.tsx`

- [ ] **Step 1: Install pdfjs-dist**

```bash
cd frontend && npm install pdfjs-dist
```

- [ ] **Step 2: Write failing test**

```tsx
// frontend/src/components/viewer/renderers/__tests__/PdfRenderer.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PdfRenderer } from '../PdfRenderer';

vi.mock('pdfjs-dist', () => ({
  getDocument: () => ({
    promise: Promise.resolve({
      numPages: 3,
      getPage: vi.fn().mockResolvedValue({
        getViewport: () => ({ width: 100, height: 100 }),
        render: () => ({ promise: Promise.resolve() }),
      }),
    }),
  }),
  GlobalWorkerOptions: { workerSrc: '' },
}));

describe('PdfRenderer', () => {
  it('renders a page navigator', async () => {
    render(<PdfRenderer source={{ kind: 'report', reportId: 9 }} />);
    expect(await screen.findByText(/page 1 of 3/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/viewer/renderers/__tests__/PdfRenderer.test.tsx`
Expected: FAIL.

- [ ] **Step 4: Implement `PdfRenderer.tsx`**

```tsx
// frontend/src/components/viewer/renderers/PdfRenderer.tsx
import React, { useEffect, useRef, useState } from 'react';
import * as pdfjs from 'pdfjs-dist';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { FileSource } from '../FileViewerContext';
import { sourceUrl } from './sourceUrl';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

export function PdfRenderer({ source }: { source: FileSource }): JSX.Element {
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(1);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pdfRef = useRef<any>(null);

  useEffect(() => {
    const task = pdfjs.getDocument(sourceUrl(source));
    task.promise.then((doc: any) => {
      pdfRef.current = doc;
      setNumPages(doc.numPages);
      setPage(1);
    });
    return () => {
      pdfRef.current?.destroy?.();
      pdfRef.current = null;
    };
  }, [source]);

  useEffect(() => {
    if (\!pdfRef.current || \!canvasRef.current || numPages === 0) return;
    pdfRef.current.getPage(page).then((p: any) => {
      const viewport = p.getViewport({ scale: 1.3 });
      const canvas = canvasRef.current\!;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      p.render({ canvasContext: canvas.getContext('2d'), viewport });
    });
  }, [page, numPages]);

  if (numPages === 0) return <div className="p-6 text-sm text-[--color-text-secondary]">Loading…</div>;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-auto px-6 py-4">
        <canvas ref={canvasRef} className="mx-auto block rounded-[--radius-md] bg-white shadow-sm" />
      </div>
      <div className="flex flex-shrink-0 items-center justify-between border-t border-[--color-border-subtle] px-4 py-2">
        <span className="text-sm text-[--color-text-secondary]">
          Page {page} of {numPages}
        </span>
        <div className="flex gap-1">
          <button
            type="button"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="flex h-7 w-7 items-center justify-center rounded-[--radius-md] hover:bg-[--color-surface-hover] disabled:opacity-40"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            aria-label="Next page"
            disabled={page >= numPages}
            onClick={() => setPage((p) => Math.min(numPages, p + 1))}
            className="flex h-7 w-7 items-center justify-center rounded-[--radius-md] hover:bg-[--color-surface-hover] disabled:opacity-40"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/viewer/renderers/__tests__/PdfRenderer.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/viewer/renderers/PdfRenderer.tsx \
        frontend/src/components/viewer/renderers/__tests__/PdfRenderer.test.tsx \
        frontend/package.json frontend/package-lock.json
git commit -m "feat(viewer): add PdfRenderer with pdf.js page navigation"
```

---

### Task 16: SaveToRepoButton (dual-surface)

Shared save/unsave control. Renders as a hover-visible icon chip in message surfaces and as a persistent icon+label button in the FileViewer header. All network and state logic lives here; surfaces differ only in chrome.

**Files:**
- Create: `frontend/src/components/chat/SaveToRepoButton.tsx`
- Test: `frontend/src/components/chat/__tests__/SaveToRepoButton.test.tsx`

Spec: `planning/specs/components/SaveToRepoSpec.md`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/chat/__tests__/SaveToRepoButton.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SaveToRepoButton } from '../SaveToRepoButton';
import * as repoApi from '../../../api/repo';

vi.mock('../../../api/repo');

describe('SaveToRepoButton', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('renders chip variant with bookmark icon and no label', () => {
    render(<SaveToRepoButton reportId="r1" initialSaved={false} variant="chip" />);
    const btn = screen.getByRole('button', { name: /save to repository/i });
    expect(btn).toBeInTheDocument();
    expect(btn.textContent?.trim()).toBe('');
  });

  it('renders viewer-header variant with a visible label', () => {
    render(<SaveToRepoButton reportId="r1" initialSaved={false} variant="viewer-header" />);
    expect(screen.getByRole('button', { name: /save to repository/i })).toHaveTextContent(/save/i);
  });

  it('calls saveToRepo when clicked in unsaved state and flips to saved', async () => {
    (repoApi.saveToRepo as any).mockResolvedValue({ saved: true });
    render(<SaveToRepoButton reportId="r1" initialSaved={false} variant="viewer-header" />);
    fireEvent.click(screen.getByRole('button', { name: /save to repository/i }));
    await waitFor(() => expect(repoApi.saveToRepo).toHaveBeenCalledWith('r1'));
    expect(await screen.findByRole('button', { name: /remove from repository/i })).toBeInTheDocument();
  });

  it('calls unsaveFromRepo when clicked in saved state and flips to unsaved', async () => {
    (repoApi.unsaveFromRepo as any).mockResolvedValue({ saved: false });
    render(<SaveToRepoButton reportId="r1" initialSaved={true} variant="viewer-header" />);
    fireEvent.click(screen.getByRole('button', { name: /remove from repository/i }));
    await waitFor(() => expect(repoApi.unsaveFromRepo).toHaveBeenCalledWith('r1'));
    expect(await screen.findByRole('button', { name: /save to repository/i })).toBeInTheDocument();
  });

  it('shows an error indicator when the call fails and does not flip state', async () => {
    (repoApi.saveToRepo as any).mockRejectedValue(new Error('offline'));
    render(<SaveToRepoButton reportId="r1" initialSaved={false} variant="viewer-header" />);
    fireEvent.click(screen.getByRole('button', { name: /save to repository/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not save/i);
    expect(screen.getByRole('button', { name: /save to repository/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/SaveToRepoButton.test.tsx`
Expected: FAIL with "Cannot find module '../SaveToRepoButton'".

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/chat/SaveToRepoButton.tsx
import { useState } from 'react';
import { Bookmark, BookmarkCheck, Loader2 } from 'lucide-react';
import { saveToRepo, unsaveFromRepo } from '../../api/repo';

export type SaveToRepoVariant = 'chip' | 'viewer-header';

export interface SaveToRepoButtonProps {
  reportId: string;
  initialSaved: boolean;
  variant: SaveToRepoVariant;
  onChange?: (saved: boolean) => void;
}

type Status = 'idle' | 'pending' | 'error';

export function SaveToRepoButton({
  reportId,
  initialSaved,
  variant,
  onChange,
}: SaveToRepoButtonProps) {
  const [saved, setSaved] = useState(initialSaved);
  const [status, setStatus] = useState<Status>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const label = saved ? 'Remove from repository' : 'Save to repository';

  const onClick = async () => {
    setStatus('pending');
    setErrorMessage(null);
    try {
      if (saved) {
        await unsaveFromRepo(reportId);
        setSaved(false);
        onChange?.(false);
      } else {
        await saveToRepo(reportId);
        setSaved(true);
        onChange?.(true);
      }
      setStatus('idle');
    } catch {
      setStatus('error');
      setErrorMessage(saved ? 'Could not remove from repository' : 'Could not save to repository');
    }
  };

  const Icon = status === 'pending' ? Loader2 : saved ? BookmarkCheck : Bookmark;
  const iconProps = {
    size: variant === 'chip' ? 14 : 16,
    className: status === 'pending' ? 'animate-spin' : '',
    'aria-hidden': true,
  } as const;

  const baseClasses =
    variant === 'chip'
      ? 'inline-flex h-6 w-6 items-center justify-center rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]'
      : 'inline-flex items-center gap-1.5 rounded-[--radius-md] px-2.5 py-1.5 text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]';

  return (
    <>
      <button
        type="button"
        aria-label={label}
        aria-pressed={saved}
        title={label}
        disabled={status === 'pending'}
        onClick={onClick}
        className={baseClasses}
      >
        <Icon {...iconProps} />
        {variant === 'viewer-header' ? <span>{saved ? 'Saved' : 'Save'}</span> : null}
      </button>
      {errorMessage ? (
        <span role="alert" className="sr-only" aria-live="polite">
          {errorMessage}
        </span>
      ) : null}
    </>
  );
}
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/SaveToRepoButton.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/SaveToRepoButton.tsx \
        frontend/src/components/chat/__tests__/SaveToRepoButton.test.tsx
git commit -m "feat(chat): add SaveToRepoButton with chip and viewer-header variants"
```

---

### Task 17: FileDownloadButton (dual-surface)

Download control. Renders as a hover-visible icon chip in message surfaces and as a persistent icon+label in the FileViewer header. Shows a 1.5 s success checkmark on successful kick-off and a 2 s error indicator on failure.

**Files:**
- Create: `frontend/src/components/chat/FileDownloadButton.tsx`
- Test: `frontend/src/components/chat/__tests__/FileDownloadButton.test.tsx`

Spec: `planning/specs/components/FileDownloadSpec.md`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/chat/__tests__/FileDownloadButton.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FileDownloadButton } from '../FileDownloadButton';

describe('FileDownloadButton', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders chip variant with download icon and no label', () => {
    render(<FileDownloadButton url="/f/1" filename="report.pdf" variant="chip" />);
    const btn = screen.getByRole('button', { name: /download report\.pdf/i });
    expect(btn.textContent?.trim()).toBe('');
  });

  it('renders viewer-header variant with a visible label', () => {
    render(<FileDownloadButton url="/f/1" filename="report.pdf" variant="viewer-header" />);
    expect(screen.getByRole('button', { name: /download/i })).toHaveTextContent(/download/i);
  });

  it('invokes the click handler and shows a temporary success indicator', async () => {
    const onTrigger = vi.fn();
    render(
      <FileDownloadButton
        url="/f/1"
        filename="report.pdf"
        variant="viewer-header"
        onTrigger={onTrigger}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /download/i }));
    expect(onTrigger).toHaveBeenCalledWith('/f/1', 'report.pdf');
    expect(await screen.findByTestId('download-success')).toBeInTheDocument();
    await waitFor(() => vi.advanceTimersByTime(1500));
    expect(screen.queryByTestId('download-success')).not.toBeInTheDocument();
  });

  it('shows a temporary error indicator when onTrigger throws', async () => {
    const onTrigger = vi.fn(() => {
      throw new Error('boom');
    });
    render(
      <FileDownloadButton
        url="/f/1"
        filename="report.pdf"
        variant="viewer-header"
        onTrigger={onTrigger}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /download/i }));
    expect(await screen.findByTestId('download-error')).toBeInTheDocument();
    await waitFor(() => vi.advanceTimersByTime(2000));
    expect(screen.queryByTestId('download-error')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/FileDownloadButton.test.tsx`
Expected: FAIL with "Cannot find module '../FileDownloadButton'".

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/chat/FileDownloadButton.tsx
import { useEffect, useState } from 'react';
import { Download, Check, AlertTriangle } from 'lucide-react';

export type FileDownloadVariant = 'chip' | 'viewer-header';

export interface FileDownloadButtonProps {
  url: string;
  filename: string;
  variant: FileDownloadVariant;
  /** Optional override for how the download is triggered (used in tests). */
  onTrigger?: (url: string, filename: string) => void;
}

type Status = 'idle' | 'success' | 'error';

function defaultTrigger(url: string, filename: string) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function FileDownloadButton({
  url,
  filename,
  variant,
  onTrigger,
}: FileDownloadButtonProps) {
  const [status, setStatus] = useState<Status>('idle');

  useEffect(() => {
    if (status === 'idle') return;
    const ms = status === 'success' ? 1500 : 2000;
    const t = window.setTimeout(() => setStatus('idle'), ms);
    return () => window.clearTimeout(t);
  }, [status]);

  const onClick = () => {
    try {
      (onTrigger ?? defaultTrigger)(url, filename);
      setStatus('success');
    } catch {
      setStatus('error');
    }
  };

  const label = `Download ${filename}`;
  const showLabel = variant === 'viewer-header';

  const baseClasses =
    variant === 'chip'
      ? 'inline-flex h-6 w-6 items-center justify-center rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]'
      : 'inline-flex items-center gap-1.5 rounded-[--radius-md] px-2.5 py-1.5 text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]';

  const Icon =
    status === 'success' ? Check : status === 'error' ? AlertTriangle : Download;
  const testId =
    status === 'success'
      ? 'download-success'
      : status === 'error'
        ? 'download-error'
        : undefined;

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={baseClasses}
      data-testid={testId}
    >
      <Icon size={variant === 'chip' ? 14 : 16} aria-hidden />
      {showLabel ? <span>Download</span> : null}
    </button>
  );
}
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/FileDownloadButton.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/FileDownloadButton.tsx \
        frontend/src/components/chat/__tests__/FileDownloadButton.test.tsx
git commit -m "feat(chat): add FileDownloadButton with chip and viewer-header variants"
```

---

### Task 18: Manual smoke test + flip README row to Draft

With every piece landed, run a targeted smoke test before marking the plan Draft. Keep the smoke test short — Plans 13+ will build full feature tests.

**Files:**
- Modify: `planning/implementation-plans/README.md`

- [ ] **Step 1: Start the backend**

Run: `uv run openlia serve`
Expected: server listens on `http://localhost:8000` with no stack trace.

- [ ] **Step 2: Start the frontend**

Run (in a second terminal): `cd frontend && npm run dev`
Expected: Vite prints `Local: http://localhost:5173/`.

- [ ] **Step 3: Verify chat sessions CRUD**

Log in as a seeded user. Open DevTools → Network, then exercise:
- `GET /api/chat/sessions?department=secretary` returns `{ sessions: [] }` for a fresh user.
- Start a new chat in Secretary, send a message — confirm `chat.start` → `chat.token` → `chat.done` SSE events arrive.
- Reload and confirm `GET /api/chat/sessions/{id}/messages` returns the saved user + assistant messages in order.

- [ ] **Step 4: Verify FileViewer singleton behaviour**

In the same chat:
- Click a report thumbnail. The FileViewer slides in from the right (200 ms). Confirm `prefers-reduced-motion: reduce` disables the slide.
- Resize via the drag handle and reload the page. Width persists from `localStorage`.
- Click a second thumbnail while the viewer is open. Content swaps in place without a close/open flicker.
- Press Escape. Viewer closes.

- [ ] **Step 5: Verify Save / Download on both surfaces**

- Hover a chip → chip Save and Download icons appear.
- Click chip Save → toggles to filled bookmark. Click again → unfills. `POST /api/repo/items` then `DELETE /api/repo/items?report_id=...` in Network tab.
- Open a report in the viewer header. Save and Download labels are visible by default (no hover required).
- Click Download. Browser dialog prompts with the filename from the server's `Content-Disposition` header.

- [ ] **Step 6: Verify renderers**

Open files of every supported type (PDF, Markdown, code, CSV, image, unsupported) and confirm each renderer paints correctly. For PDFs, use the page nav to move between pages.

- [ ] **Step 7: Flip the README row**

Edit `planning/implementation-plans/README.md`:

```
| 12 | Shared chat components (chat UI, history, viewer, download, save-to-repo) | Draft | 2026-04-17-phase-12-shared-chat-components.md |
```

- [ ] **Step 8: Commit the docs flip**

```bash
git add planning/implementation-plans/README.md
git commit -m "docs(plan): mark Phase 12 (shared chat components) as Draft"
```

---
