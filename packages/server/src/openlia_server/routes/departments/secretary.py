"""Secretary HTTP routes — POST/GET /departments/secretary/chat (SSE).

Auth: `build_require_active_user` (forces password-reset gate on company
mode). Streams `chat.start` → `chat.token+` → `chat.tool_call.*` →
`chat.done` events as named SSE frames matching the wire format produced
by `openlia.llm.runtime.events.to_wire`.

Cancellation mirrors `routes/chat_stream.py`: a watcher task polls
`request.is_disconnected()` and flips a `CancellationToken`; the runner
stops yielding once the token is cancelled. Persisted assistant messages
get `stopped_at = now` when the stream was cancelled mid-flight.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import ChatError, to_wire
from openlia.llm.runtime.messages import Attachment as RuntimeAttachment
from openlia.llm.runtime.messages import ChatMessage as RuntimeChatMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server import dev_events
from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatMessage
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.routes.chat_stream import _watch_disconnect
from openlia_server.services import chat_sessions as chat_sessions_svc
from openlia_server.services.attachments import (
    FileUpload,
    persist_attachments,
    validate_uploads,
)
from openlia_server.services.secretary_chat_runner import (
    SaveReportToRepoError,
    build_secretary_persistence_handlers,
)

log = logging.getLogger(__name__)


class SecretaryChatPayload(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


def _sse_frame(wire: dict[str, Any]) -> bytes:
    return f"event: {wire['type']}\ndata: {json.dumps(wire)}\n\n".encode()


def build_secretary_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/departments/secretary", tags=["secretary"])
    require_user = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    async def _stream(
        *,
        request: Request,
        db: DBSession,
        user: User,
        message: str,
        session_id: str | None,
        uploads: list[FileUpload] | None = None,
    ) -> StreamingResponse:
        factory: Callable[[], ChatRunner] = request.app.state.chat_runner_factory
        runner = factory()
        cancel_token = CancellationToken()
        messages = [RuntimeChatMessage(role="user", content=message)]
        uploads = uploads or []

        dev_events.record(
            "chat.request",
            f"secretary chat: {message[:80]}",
            {
                "department": "secretary",
                "user_id": user.id,
                "session_id": session_id,
                "message_len": len(message),
            },
        )

        session_model_id: str | None = None
        disabled_connector_ids: tuple[str, ...] = ()
        disabled_skill_ids: tuple[str, ...] = ()
        session_response_length: str | None = None
        runtime_attachments: list[RuntimeAttachment] = []
        # Persist the user message immediately when a session is supplied.
        if session_id:
            from openlia_server.db.models.content import ChatSession as DbChatSession

            row = db.get(DbChatSession, session_id)
            if row is not None and row.user_id == user.id:
                session_model_id = row.model_id
                disabled_connector_ids = tuple(row.disabled_connector_ids or ())
                disabled_skill_ids = tuple(row.disabled_skill_ids or ())
                session_response_length = row.response_length
            user_message_id = str(uuid.uuid4())
            db.add(
                ChatMessage(
                    id=user_message_id,
                    session_id=session_id,
                    role="user",
                    content=message,
                    created_at=datetime.now(UTC),
                )
            )
            db.commit()
            # Persist any uploaded attachments and surface them as runtime
            # Attachment objects for the runner to materialize.
            if uploads:
                rows = persist_attachments(db, message_id=user_message_id, uploads=uploads)
                runtime_attachments = [
                    RuntimeAttachment(
                        id=r.id,
                        filename=r.filename,
                        mime_type=r.mime_type,
                        storage_path=r.storage_path,
                        size_bytes=r.size_bytes,
                        extracted_text=r.extracted_text,
                    )
                    for r in rows
                ]
            # Auto-title the session from the first user message — no-op once
            # the title is something other than the default "New chat".
            try:
                chat_sessions_svc.ensure_titled(db, session_id=session_id, first_user_text=message)
            except Exception:
                log.warning("ensure_titled failed", exc_info=True)

        handlers = build_secretary_persistence_handlers(
            db_session_factory=db_session_factory,
            user_id=user.id,
        )

        async def gen() -> AsyncIterator[bytes]:
            assistant_text: list[str] = []
            tool_calls_log: list[dict[str, Any]] = []
            watcher: asyncio.Task[None] | None = asyncio.create_task(
                _watch_disconnect(request, cancel_token)
            )
            try:
                async for event in runner.run(
                    department_id="secretary",
                    user_id=user.id,
                    messages=messages,
                    attachments=runtime_attachments or None,
                    cancel_token=cancel_token,
                    model_id_override=session_model_id,
                    disabled_connector_ids=disabled_connector_ids,
                    disabled_skill_ids=disabled_skill_ids,
                    response_length=session_response_length,
                ):
                    wire = to_wire(event)
                    etype = wire["type"]
                    if etype == "chat.start":
                        dev_events.record(
                            "chat.event",
                            "stream started",
                            {"message_id": wire.get("message_id")},
                        )
                    elif etype == "chat.tool_call.start":
                        dev_events.record(
                            "chat.tool_call",
                            f"tool: {wire.get('tool_name')}",
                            {
                                "call_id": wire.get("call_id"),
                                "tool_name": wire.get("tool_name"),
                                "args_preview": wire.get("args_preview"),
                            },
                        )
                    elif etype == "chat.tool_call.result":
                        dev_events.record(
                            "chat.tool_result",
                            f"{'ok' if wire.get('ok') else 'failed'}",
                            {
                                "call_id": wire.get("call_id"),
                                "ok": wire.get("ok"),
                                "summary": wire.get("summary"),
                            },
                        )
                    elif etype == "chat.error":
                        dev_events.record(
                            "chat.error",
                            wire.get("message", "error"),
                            {"error_class": wire.get("error_class")},
                        )
                    if etype == "chat.token":
                        assistant_text.append(wire.get("text", ""))
                    elif etype == "chat.tool_call.start":
                        tool_calls_log.append(
                            {
                                "call_id": wire.get("call_id"),
                                "tool_name": wire.get("tool_name"),
                                "args_preview": wire.get("args_preview"),
                                "status": "running",
                            }
                        )
                    elif etype == "chat.tool_call.result":
                        tool_name = next(
                            (
                                tc["tool_name"]
                                for tc in tool_calls_log
                                if tc["call_id"] == wire.get("call_id")
                            ),
                            None,
                        )
                        if tool_name in handlers and wire.get("ok"):
                            try:
                                args = (wire.get("structured") or {}).get("arguments") or {}
                                effect = handlers[tool_name](args)
                                wire = {
                                    **wire,
                                    "structured": {
                                        **(wire.get("structured") or {}),
                                        **effect,
                                    },
                                }
                            except SaveReportToRepoError as exc:
                                wire = {**wire, "ok": False, "summary": str(exc)}
                        for tc in tool_calls_log:
                            if tc["call_id"] == wire.get("call_id"):
                                tc["status"] = "done" if wire.get("ok") else "failed"
                                tc["summary"] = wire.get("summary")
                                if wire.get("structured") is not None:
                                    tc["structured"] = wire["structured"]
                                break
                    yield _sse_frame(wire)

                if session_id:
                    _persist_assistant(
                        db_session_factory=db_session_factory,
                        session_id=session_id,
                        content="".join(assistant_text),
                        tool_calls=tool_calls_log or None,
                        stopped=cancel_token.is_cancelled,
                    )
                dev_events.record(
                    "chat.done",
                    f"persisted {len(''.join(assistant_text))} chars",
                    {
                        "session_id": session_id,
                        "tool_calls": len(tool_calls_log),
                        "stopped": cancel_token.is_cancelled,
                    },
                )
            except asyncio.CancelledError:
                cancel_token.cancel()
                if session_id:
                    _persist_assistant(
                        db_session_factory=db_session_factory,
                        session_id=session_id,
                        content="".join(assistant_text),
                        tool_calls=tool_calls_log or None,
                        stopped=True,
                    )
                raise
            except Exception as exc:
                log.warning("secretary stream terminated with error", exc_info=True)
                err = ChatError(
                    message_id=f"m_{uuid.uuid4().hex[:12]}",
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                yield _sse_frame(to_wire(err))
            finally:
                if watcher is not None and not watcher.done():
                    watcher.cancel()
                    try:
                        await watcher
                    except (asyncio.CancelledError, Exception):
                        pass

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    @router.post("/chat", response_model=None)
    async def post_chat(
        request: Request,
        user: User = require_user,
        db: DBSession = Depends(session_dep),
    ) -> StreamingResponse | JSONResponse:
        """Dual-mode: ``application/json`` keeps the legacy ``{message,
        session_id}`` shape; ``multipart/form-data`` adds a ``files[]`` array
        for composer attachments. Validation failures on the multipart path
        return 4xx JSON before the SSE stream opens (atomic-at-send)."""
        content_type = request.headers.get("content-type", "")
        is_form = content_type.startswith("multipart/form-data") or content_type.startswith(
            "application/x-www-form-urlencoded"
        )
        if is_form:
            form = await request.form()
            message = (form.get("message") or "").strip()
            if not message:
                return JSONResponse({"detail": "message must not be empty"}, status_code=400)
            session_id = form.get("session_id") or None
            uploads: list[FileUpload] = []
            for upload in form.getlist("files"):
                if not hasattr(upload, "read"):
                    continue
                content = await upload.read()
                uploads.append(
                    FileUpload(
                        filename=upload.filename or "unnamed",
                        mime_type=upload.content_type or "application/octet-stream",
                        content=content,
                    )
                )
            errors = validate_uploads(uploads)
            if errors:
                return JSONResponse(
                    {"errors": [{"filename": e.filename, "reason": e.reason} for e in errors]},
                    status_code=400,
                )
            return await _stream(
                request=request,
                db=db,
                user=user,
                message=message,
                session_id=session_id,
                uploads=uploads,
            )
        # JSON path (legacy)
        body = await request.json()
        try:
            payload = SecretaryChatPayload.model_validate(body)
        except Exception as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        return await _stream(
            request=request,
            db=db,
            user=user,
            message=payload.message,
            session_id=payload.session_id,
        )

    @router.get("/chat")
    async def get_chat(
        request: Request,
        q: str = Query(..., min_length=1, alias="q"),
        session_id: str | None = Query(None, alias="session_id"),
        user: User = require_user,
        db: DBSession = Depends(session_dep),
    ) -> StreamingResponse:
        return await _stream(
            request=request,
            db=db,
            user=user,
            message=q,
            session_id=session_id,
        )

    return router


def _persist_assistant(
    *,
    db_session_factory: Callable[[], DBSession],
    session_id: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None,
    stopped: bool,
) -> None:
    """Open a fresh DB session, persist the assistant turn, close.

    Mirrors the `_Persistence` pattern in `routes/chat_stream.py`. Skips
    the write when there is nothing to save (no tokens emitted, no
    tool calls). When `stopped=True`, sets `chat_messages.stopped_at`.
    """
    if not content and not tool_calls:
        return
    db = db_session_factory()
    try:
        now = datetime.now(UTC)
        db.add(
            ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="assistant",
                content=content,
                tool_calls=tool_calls,
                created_at=now,
                stopped_at=now if stopped else None,
            )
        )
        db.commit()
    finally:
        db.close()
