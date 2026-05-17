"""Routes for chat session CRUD and message listing."""

from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatAttachment, ChatMessage, ChatSession, Report
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import chat_sessions as svc

_REVISE_TOOL_NAME = "revise_report"
_SOURCE_CHAT_LOCKS: dict[str, Any] = defaultdict(lambda: __import__("asyncio").Lock())


def _chat_followup_enabled() -> bool:
    return os.environ.get("OPENLIA_REPORT_CHAT_ENABLED", "0") == "1"


def _revision_flag_on() -> bool:
    return os.environ.get("OPENLIA_REVISION_PASS_ENABLED", "0") == "1"


async def _trigger_revision(
    *,
    db: Session,
    user_id: str,
    source_report_id: str,
    chat_session_id: str,
    revision_brief: str,
    sections_to_focus: list[str] | None,
    request: Request,
) -> str:
    """Insert a new revision Report row and submit to the background registry.

    Returns the new ``report_id``. Mirrors the core logic in
    ``reports_revise.revise_report_ep`` so the chat-route intercept path
    can trigger revision without an internal HTTP round-trip.
    """
    import asyncio

    source_row = db.get(Report, source_report_id)
    if source_row is None or source_row.user_id != user_id:
        raise HTTPException(404, "report not found")

    async with _SOURCE_CHAT_LOCKS[chat_session_id]:
        new_report_id = f"r_{uuid.uuid4().hex[:12]}"
        new_row = Report(
            id=new_report_id,
            user_id=user_id,
            department=source_row.department,
            report_type=source_row.report_type,
            title=source_row.title,
            content_markdown="",
            content_structured={},
            model_ref="",
            status="generating",
            started_at=datetime.now(UTC),
            original_request={
                "kind": "revision",
                "source_report_id": source_report_id,
                "chat_session_id": chat_session_id,
                "revision_brief": revision_brief,
                "sections_to_focus": sections_to_focus,
            },
        )
        db.add(new_row)
        db.commit()

    registry: Any = getattr(request.app.state, "bg_report_registry", None)
    presence: Any = getattr(request.app.state, "user_presence_registry", None)

    if registry is None:
        from openlia_server.services.background_report_registry import BackgroundReportRegistry

        registry = BackgroundReportRegistry()

    if presence is None:
        from openlia_server.services.user_presence_registry import UserPresenceRegistry

        presence = UserPresenceRegistry()

    bundle_dir = Path(
        os.environ.get("OPENLIA_REPORT_BUNDLE_DIR") or Path.home() / ".openlia" / "report_bundles"
    )

    resolve_fn = getattr(request.app.state, "revision_resolve", None)
    flagship_factory = getattr(request.app.state, "revision_flagship_provider_factory", None)

    if resolve_fn is None or flagship_factory is None:
        from openlia.llm.adapters import build_adapter
        from openlia.llm.resolver import resolve as _resolve

        def resolve_fn(  # type: ignore[misc]
            *,
            department_id: str,
            user_id: str | None,
            registry: Any,
            role: str = "flagship",
            model_id_override: str | None = None,
        ):
            return _resolve(
                department_id=department_id,
                registry=registry,
                user_id=user_id,
            )

        def flagship_factory(resolved: Any) -> Any:  # type: ignore[misc]
            return build_adapter(
                kind=resolved.provider_kind,
                credentials=resolved.credentials,
                model=resolved.model_ref,
                capabilities=resolved.capabilities,
            )

    from openlia.llm.runtime.prompts import PromptLoader
    from openlia.llm.runtime.revision_runner import RevisionRunner

    from openlia_server.services.revision_wrapper import run_wrapped_revision

    prompts = PromptLoader()

    runner = RevisionRunner(
        prompts=prompts,
        resolve=resolve_fn,
        registry=registry,
        flagship_provider_factory=flagship_factory,
        report_id_factory=lambda: new_report_id,
        bundle_dir=bundle_dir,
        db_session_factory=None,  # type: ignore[arg-type]
    )

    runner_coro = runner.run(
        department_id=source_row.department,
        user_id=user_id,
        source_report_id=source_report_id,
        chat_session_id=chat_session_id,
        revision_brief=revision_brief,
        sections_to_focus=sections_to_focus,
    )

    task = registry.submit(
        user_id=user_id,
        report_id=new_report_id,
        runner_coro=runner_coro,
    )

    async def _subscribe():
        from openlia.llm.runtime.events import ReportComplete, ReportError

        queue: Any = asyncio.Queue(maxsize=512)
        task.subscriber_queues.add(queue)
        try:
            while True:
                ev = await queue.get()
                yield ev
                if isinstance(ev, (ReportComplete, ReportError)):
                    return
        finally:
            task.subscriber_queues.discard(queue)

    _wrapper_task = asyncio.create_task(
        run_wrapped_revision(
            runner_coro=_subscribe(),
            new_report_id=new_report_id,
            source_chat_session_id=chat_session_id,
            user_id=user_id,
            db_session_factory=None,  # type: ignore[arg-type]
            presence=presence,
            registry=registry,
        )
    )
    getattr(request.app.state, "_revision_tasks", set()).add(_wrapper_task)
    _wrapper_task.add_done_callback(
        lambda t: getattr(request.app.state, "_revision_tasks", set()).discard(t)
    )

    return new_report_id


def _attach_report_as_context(
    db: Session, *, session_id: str, user_id: str, report_id: str
) -> None:
    """Insert a ``user``-role chat message containing the report's title +
    structured payload as JSON. The Secretary LLM sees this as the first
    message in the conversation and can ground follow-ups against it.

    Silently no-ops when the report is missing or owned by a different user
    so a malformed handoff URL doesn't fail session creation.
    """
    report = db.get(Report, report_id)
    if report is None or report.user_id != user_id:
        return
    payload: dict = {
        "type": "attached_report",
        "report_id": report.id,
        "department": report.department,
        "title": report.title,
        "schema": report.content_structured,
    }
    body = (
        f"[Report attached: {report.title}]\n"
        f"The user has attached a report from {report.department}. "
        "Use it as the primary reference when answering follow-up questions.\n\n"
        f"```json\n{json.dumps(payload)}\n```"
    )
    db.add(
        ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content=body,
        )
    )
    db.flush()


class SessionOut(BaseModel):
    id: str
    department: str
    title: str
    is_pinned: bool
    is_archived: bool
    created_at: datetime
    attached_report_id: str | None = None
    model_id: str | None = None
    disabled_connector_ids: list[str] = Field(default_factory=list)
    disabled_skill_ids: list[str] = Field(default_factory=list)
    response_length: str | None = None


class SessionListOut(BaseModel):
    items: list[SessionOut]


_DEPARTMENT_PATTERN = (
    r"^(secretary|equity_research|earnings_update|morning_briefing"
    r"|retail_sentiment|macro_research|panic_thermometer)$"
)


class SessionCreateIn(BaseModel):
    department: str = Field(..., pattern=_DEPARTMENT_PATTERN)
    title: str = Field(..., min_length=1, max_length=200)
    # Optional report to attach to the new session. When set, the server
    # injects a system-role message containing the report's structured
    # JSON so the assistant has the report content as conversational
    # context. Used by "Ask in Secretary →" handoffs from report viewers.
    attached_report_id: str | None = None


class DepartmentIn(BaseModel):
    department: str = Field(..., pattern=_DEPARTMENT_PATTERN)


class SessionPatchIn(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    archived: bool | None = None
    disabled_connector_ids: list[str] | None = None
    disabled_skill_ids: list[str] | None = None
    # Composer response-length picker. ``None`` (key omitted) leaves the
    # current value unchanged. To explicitly clear, send ``"normal"`` —
    # the service treats ``"normal"`` and unset identically (no length
    # directive injected into the system prompt).
    response_length: str | None = None


class SessionModelIn(BaseModel):
    """``model_id=null`` clears the override and reverts to slot-based resolution."""

    model_id: str | None = None


class AttachmentOut(BaseModel):
    filename: str
    size_bytes: int


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: list[dict] | None = None
    model_ref: str | None = None
    token_usage: dict | None = None
    created_at: datetime
    stopped_at: datetime | None = None
    attachments: list[AttachmentOut] = Field(default_factory=list)


class MessageListOut(BaseModel):
    items: list[MessageOut]


class MessageIn(BaseModel):
    content: str = Field(..., min_length=1)


def build_chat_sessions_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("", response_model=SessionListOut)
    def list_sessions_ep(
        include_archived: bool = False,
        department: str | None = None,
        q: str | None = None,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionListOut:
        rows = svc.list_sessions(
            db,
            user_id=user.id,
            include_archived=include_archived,
            department=department,
            q=q,
        )
        return SessionListOut(
            items=[SessionOut.model_validate(r, from_attributes=True) for r in rows]
        )

    @router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
    def create_session_ep(
        body: SessionCreateIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionOut:
        # Idempotent reuse: if this user already has a session bound to this
        # report, return it instead of creating a duplicate.
        if body.attached_report_id:
            existing = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user.id,
                    ChatSession.attached_report_id == body.attached_report_id,
                )
                .first()
            )
            if existing is not None:
                return SessionOut.model_validate(existing, from_attributes=True)

        row = svc.create_session(
            db,
            user_id=user.id,
            department=body.department,
            title=body.title,
            attached_report_id=body.attached_report_id,
        )
        if body.attached_report_id:
            _attach_report_as_context(
                db, session_id=row.id, user_id=user.id, report_id=body.attached_report_id
            )
            db.commit()
        return SessionOut.model_validate(row, from_attributes=True)

    @router.get("/by-department/{department}", response_model=SessionOut)
    def get_or_create_by_department_ep(
        department: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionOut:
        try:
            DepartmentIn(department=department)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "invalid_department", "message": str(exc)}
            ) from exc
        row = svc.get_or_create_default_session(db, user_id=user.id, department=department)
        return SessionOut.model_validate(row, from_attributes=True)

    @router.get("/{session_id}", response_model=SessionOut)
    def get_session_ep(
        session_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionOut:
        try:
            row = svc.get_session(db, session_id=session_id, user_id=user.id)
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
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
            if body.disabled_connector_ids is not None or body.disabled_skill_ids is not None:
                svc.set_session_disabled_lists(
                    db,
                    session_id=session_id,
                    user_id=user.id,
                    disabled_connector_ids=body.disabled_connector_ids,
                    disabled_skill_ids=body.disabled_skill_ids,
                )
            if body.response_length is not None:
                svc.set_session_response_length(
                    db,
                    session_id=session_id,
                    user_id=user.id,
                    response_length=body.response_length,
                )
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "invalid", "message": str(exc)}
            ) from exc
        return {"ok": True}

    @router.put("/{session_id}/model")
    def put_session_model_ep(
        session_id: str,
        body: SessionModelIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        if body.model_id is not None:
            from openlia_server.db.models.config import LLMModel

            model = db.get(LLMModel, body.model_id)
            if model is None or not model.is_enabled:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "model_not_found", "message": "Model id not in roster."},
                )
        try:
            svc.set_session_model(
                db, session_id=session_id, user_id=user.id, model_id=body.model_id
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
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
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc

    @router.post("/{session_id}/messages")
    async def post_message_ep(
        session_id: str,
        body: MessageIn,
        request: Request,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict:
        """Pre-flight message endpoint.

        When the session has ``attached_report_id``, loads the bundle and
        checks whether the report context is still accessible. Returns
        ``{"locked": True, "lock_message": ...}`` when the bundle is missing
        or the report is tombstoned. Returns ``{"ok": True}`` otherwise so
        the caller can proceed to the SSE stream endpoint.

        When ``OPENLIA_REVISION_PASS_ENABLED=1`` is also set, runs the LLM
        turn and intercepts any ``revise_report`` tool calls — triggering the
        revision pipeline and returning ``{"revision_started": True,
        "new_report_id": ...}`` instead of ``{"ok": True}``.
        """
        try:
            session_row = svc.get_session(db, session_id=session_id, user_id=user.id)
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc

        if session_row.attached_report_id and _chat_followup_enabled():
            from openlia.llm.runtime.tools import ToolDispatcher
            from openlia.llm.runtime.web_search import WebSearchResolution

            from openlia_server.services.report_chat_context import (
                build_chat_context_for_session,
            )
            from openlia_server.services.runtime import _EmptyDataDispatcher

            bundle_dir = Path(
                os.environ.get("OPENLIA_REPORT_BUNDLE_DIR")
                or Path.home() / ".openlia" / "report_bundles"
            )

            report = db.get(Report, session_row.attached_report_id)
            is_tombstoned = report is None or getattr(report, "expired_at", None) is not None

            dispatcher = ToolDispatcher(
                data_dispatcher=_EmptyDataDispatcher(),
                web_search=WebSearchResolution(False, None, None),
            )

            context_result = build_chat_context_for_session(
                attached_report_id=session_row.attached_report_id,
                bundle_dir=bundle_dir,
                report_is_tombstoned=is_tombstoned,
                dispatcher=dispatcher,
                department_id=session_row.department,
                has_web_search=False,
            )
            if context_result.locked:
                return {"locked": True, "lock_message": context_result.lock_message}

            # When revision flag is on, run the LLM turn and intercept any
            # ``revise_report`` tool calls — do not dispatch them to ToolDispatcher.
            if _revision_flag_on():
                from openlia.llm.runtime.events import ChatToolCallStart
                from openlia.llm.runtime.messages import ChatMessage as RuntimeChatMessage

                rows = svc.list_messages(db, session_id=session_id, user_id=user.id)
                messages = [RuntimeChatMessage(role=r.role, content=r.content) for r in rows]
                # Append the incoming user message so the LLM sees it.
                messages.append(RuntimeChatMessage(role="user", content=body.content))

                factory = getattr(request.app.state, "chat_runner_factory", None)
                if factory is not None:
                    runner = factory()
                    revise_calls: list[dict[str, Any]] = []
                    async for event in runner.run(
                        department_id=session_row.department,
                        user_id=user.id,
                        messages=messages,
                    ):
                        if isinstance(event, ChatToolCallStart):
                            if event.tool_name == _REVISE_TOOL_NAME:
                                revise_calls.append(
                                    {
                                        "call_id": event.call_id,
                                        "args_preview": event.args_preview or "",
                                    }
                                )

                    if revise_calls:
                        # Parse revision_brief from the first revise_report call's
                        # args_preview (best-effort; fall back to empty string).
                        first_args_str = revise_calls[0].get("args_preview", "")
                        try:
                            first_args = json.loads(first_args_str)
                        except (json.JSONDecodeError, ValueError):
                            first_args = {}
                        revision_brief: str = first_args.get("revision_brief", "")
                        sections_to_focus: list[str] | None = first_args.get("sections_to_focus")

                        new_report_id = await _trigger_revision(
                            db=db,
                            user_id=user.id,
                            source_report_id=session_row.attached_report_id,
                            chat_session_id=session_id,
                            revision_brief=revision_brief,
                            sections_to_focus=sections_to_focus,
                            request=request,
                        )
                        return {
                            "revision_started": True,
                            "new_report_id": new_report_id,
                        }

        return {"ok": True}

    @router.get("/{session_id}/messages", response_model=MessageListOut)
    def list_messages_ep(
        session_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> MessageListOut:
        try:
            rows = svc.list_messages(db, session_id=session_id, user_id=user.id)
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
        message_ids = [r.id for r in rows]
        attachments_by_message: dict[str, list[AttachmentOut]] = {}
        if message_ids:
            att_stmt = (
                select(ChatAttachment)
                .where(ChatAttachment.message_id.in_(message_ids))
                .order_by(ChatAttachment.created_at.asc(), ChatAttachment.id.asc())
            )
            for a in db.execute(att_stmt).scalars():
                attachments_by_message.setdefault(a.message_id, []).append(
                    AttachmentOut(filename=a.filename, size_bytes=a.size_bytes)
                )
        return MessageListOut(
            items=[
                MessageOut(
                    id=r.id,
                    role=r.role,
                    content=r.content,
                    tool_calls=r.tool_calls,
                    model_ref=r.model_ref,
                    token_usage=r.token_usage,
                    created_at=r.created_at,
                    stopped_at=r.stopped_at,
                    attachments=attachments_by_message.get(r.id, []),
                )
                for r in rows
            ]
        )

    return router
