"""GET /chat/sessions/{id}/stream — named-event SSE route for chat.

Contract (Phase 12 ↔ 13):
  - Endpoint: GET /chat/sessions/{session_id}/stream?q=<user message>
  - Frames: `event: <type>\ndata: <json>\n\n` — named events so the
    browser EventSource `addEventListener(type, ...)` receives them.
  - Session row owns the department; user messages are persisted on
    entry, assistant messages on chat.done.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import ChatError, ChatGuardrail, to_wire
from openlia.llm.runtime.messages import ChatMessage as RuntimeChatMessage
from openlia.safety.output_moderation import ActionTier, decide_action
from openlia.safety.output_moderation import scan as moderation_scan
from openlia.safety.persona_refusal import detect_refusal
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatMessage
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import chat_sessions as svc
from openlia_server.services.guardrail_log import (
    record_persona_refusal,
    record_tripwire_match,
)

log = logging.getLogger(__name__)


def _sse_frame(wire: dict[str, Any]) -> bytes:
    """Build a named-event SSE frame (`event:` + `data:`)."""
    return f"event: {wire['type']}\ndata: {json.dumps(wire)}\n\n".encode()


def build_chat_stream_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    """Mount `GET /chat/sessions/{session_id}/stream`.

    The chat-runner factory is resolved from `request.app.state.chat_runner_factory`
    at each request so tests can swap it without rebuilding the app.
    """
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/chat/sessions", tags=["chat"])

    @router.get("/{session_id}/stream")
    async def stream_chat(
        session_id: str,
        q: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
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

        db.add(
            ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="user",
                content=q,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()

        # Auto-title the session from the first user message — no-op when
        # the title has already been set to anything other than "New chat".
        try:
            svc.ensure_titled(db, session_id=session_id, first_user_text=q)
        except Exception:
            # auto-title is best-effort; never fail user request on title bug.
            log.warning("ensure_titled failed", exc_info=True)

        rows = svc.list_messages(db, session_id=session_id, user_id=user.id)
        messages = [RuntimeChatMessage(role=r.role, content=r.content) for r in rows]

        factory: Callable[[], ChatRunner] = request.app.state.chat_runner_factory
        persist = _Persistence(db_session_factory=db_session_factory, session_id=session_id)

        return StreamingResponse(
            _event_source(
                messages=messages,
                user=user,
                factory=factory,
                department=session_row.department,
                persist=persist,
                request=request,
                db_session_factory=db_session_factory,
                session_id=session_id,
                last_user_text=q,
            ),
            media_type="text/event-stream",
        )

    return router


async def _watch_disconnect(request: Request, token: CancellationToken) -> None:
    """Poll `request.is_disconnected()` every 250ms; flip the token on True.

    Spawned as a background task by `_event_source`; cancelled in its finally
    block so a clean stream completion doesn't leave the watcher orphaned.
    """
    while True:
        try:
            disconnected = await request.is_disconnected()
        except Exception:
            return
        if disconnected:
            token.cancel()
            return
        await asyncio.sleep(0.25)


class _Persistence:
    """Save assistant output back to the session once streaming completes."""

    def __init__(
        self,
        *,
        db_session_factory: Callable[[], DBSession],
        session_id: str,
    ) -> None:
        self._factory = db_session_factory
        self._session_id = session_id

    def save_assistant(
        self,
        *,
        content: str,
        tool_calls: list[dict[str, Any]] | None,
        stopped: bool = False,
    ) -> None:
        if not content and not tool_calls:
            return
        db = self._factory()
        try:
            now = datetime.now(UTC)
            db.add(
                ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=self._session_id,
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


async def _event_source(
    *,
    messages: list[RuntimeChatMessage],
    user: User,
    factory: Callable[[], ChatRunner],
    department: str,
    persist: _Persistence | None = None,
    request: Request | None = None,
    db_session_factory: Callable[[], DBSession] | None = None,
    session_id: str | None = None,
    last_user_text: str = "",
) -> AsyncIterator[bytes]:
    token = CancellationToken()
    runner = factory()

    assistant_text: list[str] = []
    tool_calls_log: list[dict[str, Any]] = []
    current_message_id: str = ""

    watcher: asyncio.Task[None] | None = None
    if request is not None:
        watcher = asyncio.create_task(_watch_disconnect(request, token))

    try:
        async for event in runner.run(
            department_id=department,
            user_id=user.id,
            messages=messages,
            cancel_token=token,
        ):
            wire = to_wire(event)
            etype = wire["type"]
            if etype == "chat.start":
                current_message_id = wire.get("message_id", "")
            elif etype == "chat.token":
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
            yield _sse_frame(wire)

        # Component B + E — post-stream moderation + audit
        full_text = "".join(assistant_text)
        if full_text and db_session_factory is not None and session_id is not None:
            user_hash = hashlib.sha256(last_user_text.encode("utf-8")).hexdigest()
            excerpt = full_text[:500]

            matches = moderation_scan(full_text)
            decision = decide_action(matches)
            refusal_clause = detect_refusal(full_text)

            if matches or refusal_clause is not None:
                db_log = db_session_factory()
                try:
                    for m in matches:
                        record_tripwire_match(
                            db_log,
                            session_id=session_id,
                            user_id=user.id,
                            department_id=department,
                            match=m,
                            user_input_hash=user_hash,
                            response_excerpt=excerpt,
                            model_ref=None,
                        )
                    if refusal_clause is not None:
                        record_persona_refusal(
                            db_log,
                            session_id=session_id,
                            user_id=user.id,
                            department_id=department,
                            clause_id=refusal_clause,
                            user_input_hash=user_hash,
                            response_excerpt=excerpt,
                            model_ref=None,
                        )
                    db_log.commit()
                finally:
                    db_log.close()

            if decision is not None and decision.action is not ActionTier.LOG:
                guardrail_event = ChatGuardrail(
                    message_id=current_message_id,
                    category=decision.category,
                    action=str(decision.action),
                    replacement=(
                        decision.message if decision.action is ActionTier.REPLACE else None
                    ),
                    chip_text=(decision.message if decision.action is ActionTier.WARN else None),
                )
                yield _sse_frame(to_wire(guardrail_event))

        if persist is not None:
            persist.save_assistant(
                content="".join(assistant_text),
                tool_calls=tool_calls_log or None,
                stopped=token.is_cancelled,
            )
    except asyncio.CancelledError:
        token.cancel()
        if persist is not None:
            persist.save_assistant(
                content="".join(assistant_text),
                tool_calls=tool_calls_log or None,
                stopped=True,
            )
        raise
    except Exception as exc:
        log.warning("chat stream terminated with error", exc_info=True)
        error_event = ChatError(
            message_id=f"m_{uuid.uuid4().hex[:12]}",
            error_class=type(exc).__name__,
            message=str(exc),
        )
        yield _sse_frame(to_wire(error_event))
    finally:
        if watcher is not None and not watcher.done():
            watcher.cancel()
            try:
                await watcher
            except (asyncio.CancelledError, Exception):
                pass
