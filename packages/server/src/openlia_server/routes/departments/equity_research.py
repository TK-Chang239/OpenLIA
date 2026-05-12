"""GET/PUT /departments/equity-research/config routes."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from openlia.departments.equity_research import EquityResearchDepartment
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import to_wire
from openlia.llm.runtime.messages import Attachment as RuntimeAttachment
from openlia.llm.runtime.messages import ChatMessage as RuntimeChatMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatMessage as DbChatMessage
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import chat_sessions as chat_sessions_svc
from openlia_server.services.attachments import (
    FileUpload,
    persist_attachments,
    validate_uploads,
)
from openlia_server.services.equity_research_config import (
    CustomSectionDTO,
    EquityResearchConfigService,
)
from openlia_server.services.equity_research_runner import (
    EquityResearchRunner,
    ReportSavedEvent,
)


class CustomSectionPayload(BaseModel):
    id: str
    title: str
    description: str | None = None


class ErConfigPatch(BaseModel):
    report_mode: str | None = None
    report_length: str | None = None
    sections_by_mode: dict[str, list[str]] | None = None
    custom_sections_by_mode: dict[str, list[CustomSectionPayload]] | None = None


class ReportPayload(BaseModel):
    mode: str
    user_input: str
    session_id: str | None = None


class ChatPayload(BaseModel):
    message: str
    session_id: str | None = None


def _serialize_event(ev) -> dict:
    if isinstance(ev, ReportSavedEvent):
        return {"type": "report.saved", "report_id": ev.report_id}
    return to_wire(ev)


def _serialize(cfg) -> dict:
    return {
        "report_mode": cfg.report_mode,
        "report_length": cfg.report_length,
        "sections_by_mode": cfg.sections_by_mode,
        "custom_sections_by_mode": {
            mode: [{"id": c.id, "title": c.title, "description": c.description} for c in customs]
            for mode, customs in cfg.custom_sections_by_mode.items()
        },
    }


def build_equity_research_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/departments/equity-research", tags=["equity-research"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/config")
    def get_config(
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> dict:
        svc = EquityResearchConfigService(session)
        return _serialize(svc.get_config(user.id))

    @router.put("/config")
    def put_config(
        patch: ErConfigPatch,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> dict:
        svc = EquityResearchConfigService(session)
        try:
            updated = svc.update_config(
                user.id,
                report_mode=patch.report_mode,
                report_length=patch.report_length,
                sections_by_mode=patch.sections_by_mode,
                custom_sections_by_mode=(
                    {
                        m: [
                            CustomSectionDTO(id=c.id, title=c.title, description=c.description)
                            for c in customs
                        ]
                        for m, customs in patch.custom_sections_by_mode.items()
                    }
                    if patch.custom_sections_by_mode is not None
                    else None
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _serialize(updated)

    _VALID_MODES = EquityResearchDepartment().valid_modes

    async def _stream_report(
        *,
        request: Request,
        db: DBSession,
        user: User,
        mode: str,
        user_input: str,
        session_id: str | None,
        uploads: list[FileUpload] | None,
    ) -> StreamingResponse:
        if mode not in _VALID_MODES:
            raise HTTPException(status_code=400, detail=f"unknown mode: {mode!r}")

        runtime_attachments: list[RuntimeAttachment] = []
        if uploads:
            if session_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="session_id is required when uploading attachments",
                )
            holder_id = str(uuid.uuid4())
            db.add(
                DbChatMessage(
                    id=holder_id,
                    session_id=session_id,
                    role="user",
                    content=user_input,
                    created_at=datetime.now(UTC),
                )
            )
            db.commit()
            rows = persist_attachments(db, message_id=holder_id, uploads=uploads)
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

        inner_factory = request.app.state.equity_research_inner_factory
        inner = inner_factory()
        runner = EquityResearchRunner(db_session=db, inner=inner)

        async def stream() -> AsyncIterator[bytes]:
            async for ev in runner.run_report(
                user_id=user.id,
                mode=mode,
                user_input=user_input,
                session_id=session_id,
                attachments=runtime_attachments or None,
            ):
                wire = _serialize_event(ev)
                yield f"event: {wire['type']}\ndata: {json.dumps(wire)}\n\n".encode()

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    @router.post("/report", response_model=None)
    async def post_report(
        request: Request,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> StreamingResponse | JSONResponse:
        """Dual-mode: ``application/json`` keeps the legacy
        ``{mode, user_input, session_id}`` shape; ``multipart/form-data``
        adds a ``files[]`` array for composer attachments."""
        content_type = request.headers.get("content-type", "")
        is_form = content_type.startswith("multipart/form-data") or content_type.startswith(
            "application/x-www-form-urlencoded"
        )
        if is_form:
            form = await request.form()
            mode = (form.get("mode") or "").strip()
            user_input = (form.get("user_input") or "").strip()
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
            return await _stream_report(
                request=request,
                db=session,
                user=user,
                mode=mode,
                user_input=user_input,
                session_id=session_id,
                uploads=uploads,
            )
        body = await request.json()
        try:
            payload = ReportPayload.model_validate(body)
        except Exception as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        return await _stream_report(
            request=request,
            db=session,
            user=user,
            mode=payload.mode,
            user_input=payload.user_input,
            session_id=payload.session_id,
            uploads=None,
        )

    async def _stream_chat(
        *,
        request: Request,
        db: DBSession,
        user: User,
        message: str,
        session_id: str | None,
        uploads: list[FileUpload] | None,
    ) -> StreamingResponse:
        factory: Callable[[], ChatRunner] = request.app.state.chat_runner_factory
        runner = factory()
        cancel_token = CancellationToken()

        session_model_id: str | None = None
        disabled_connector_ids: tuple[str, ...] = ()
        disabled_skill_ids: tuple[str, ...] = ()
        session_response_length: str | None = None
        runtime_attachments: list[RuntimeAttachment] = []

        if session_id is not None:
            try:
                session_row = chat_sessions_svc.get_session(
                    db, session_id=session_id, user_id=user.id
                )
            except (LookupError, PermissionError) as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            session_model_id = session_row.model_id
            disabled_connector_ids = tuple(session_row.disabled_connector_ids or ())
            disabled_skill_ids = tuple(session_row.disabled_skill_ids or ())
            session_response_length = session_row.response_length
            user_message_id = str(uuid.uuid4())
            db.add(
                DbChatMessage(
                    id=user_message_id,
                    session_id=session_id,
                    role="user",
                    content=message,
                    created_at=datetime.now(UTC),
                )
            )
            db.commit()
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
            try:
                chat_sessions_svc.ensure_titled(
                    db,
                    session_id=session_id,
                    first_user_text=message,
                )
            except Exception:
                pass
            rows_msgs = chat_sessions_svc.list_messages(db, session_id=session_id, user_id=user.id)
            messages = [RuntimeChatMessage(role=r.role, content=r.content) for r in rows_msgs]
        else:
            if uploads:
                raise HTTPException(
                    status_code=400,
                    detail="session_id is required when uploading attachments",
                )
            messages = [RuntimeChatMessage(role="user", content=message)]

        assistant_text: list[str] = []
        tool_calls_log: list[dict[str, Any]] = []

        async def stream() -> AsyncIterator[bytes]:
            async for event in runner.run(
                department_id="equity_research",
                user_id=user.id,
                messages=messages,
                attachments=runtime_attachments or None,
                cancel_token=cancel_token,
                session_id=session_id,
                model_id_override=session_model_id,
                disabled_connector_ids=disabled_connector_ids,
                disabled_skill_ids=disabled_skill_ids,
                response_length=session_response_length,
            ):
                wire = to_wire(event)
                etype = wire["type"]
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
                    for tc in tool_calls_log:
                        if tc["call_id"] == wire.get("call_id"):
                            tc["status"] = "done" if wire.get("ok") else "failed"
                            tc["summary"] = wire.get("summary")
                            if wire.get("structured") is not None:
                                tc["structured"] = wire["structured"]
                            break
                yield f"event: {wire['type']}\ndata: {json.dumps(wire)}\n\n".encode()
            if session_id is not None and (assistant_text or tool_calls_log):
                content = "".join(assistant_text)
                db.add(
                    DbChatMessage(
                        id=str(uuid.uuid4()),
                        session_id=session_id,
                        role="assistant",
                        content=content,
                        tool_calls=tool_calls_log or None,
                        created_at=datetime.now(UTC),
                    )
                )
                db.commit()

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    @router.post("/chat", response_model=None)
    async def post_chat(
        request: Request,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> StreamingResponse | JSONResponse:
        """Dual-mode: ``application/json`` keeps the legacy
        ``{message, session_id}`` shape; ``multipart/form-data`` adds a
        ``files[]`` array for composer attachments."""
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
            return await _stream_chat(
                request=request,
                db=session,
                user=user,
                message=message,
                session_id=session_id,
                uploads=uploads,
            )
        body = await request.json()
        try:
            payload = ChatPayload.model_validate(body)
        except Exception as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        return await _stream_chat(
            request=request,
            db=session,
            user=user,
            message=payload.message,
            session_id=payload.session_id,
            uploads=None,
        )

    return router
