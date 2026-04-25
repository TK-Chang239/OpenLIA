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
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import ChatError, to_wire
from openlia.llm.runtime.messages import ChatMessage as RuntimeChatMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatMessage
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.routes.chat_stream import _watch_disconnect
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
    ) -> StreamingResponse:
        factory: Callable[[], ChatRunner] = request.app.state.chat_runner_factory
        runner = factory()
        cancel_token = CancellationToken()
        messages = [RuntimeChatMessage(role="user", content=message)]

        # Persist the user message immediately when a session is supplied.
        if session_id:
            db.add(
                ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role="user",
                    content=message,
                    created_at=datetime.now(UTC),
                )
            )
            db.commit()

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
                    cancel_token=cancel_token,
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

    @router.post("/chat")
    async def post_chat(
        payload: SecretaryChatPayload,
        request: Request,
        user: User = require_user,
        db: DBSession = Depends(session_dep),
    ) -> StreamingResponse:
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
