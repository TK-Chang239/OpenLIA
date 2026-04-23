"""POST /departments/secretary/chat — first runtime-backed SSE route."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import ChatError, to_wire
from openlia.llm.runtime.messages import ChatMessage as RuntimeChatMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user

log = logging.getLogger(__name__)


class SecretaryChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class SecretaryChatRequest(BaseModel):
    messages: list[SecretaryChatMessage]


def build_chat_stream_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    """Mount `/departments/secretary/chat`.

    The chat-runner factory is resolved from `request.app.state.chat_runner_factory`
    at each request so tests can swap it without rebuilding the app.
    """
    require_auth = build_require_active_user(
        db_session_factory=db_session_factory, mode=mode
    )
    router = APIRouter(prefix="/departments/secretary", tags=["chat"])

    @router.post("/chat")
    async def stream_chat(
        payload: SecretaryChatRequest,
        request: Request,
        user: User = require_auth,
    ) -> StreamingResponse:
        factory: Callable[[], ChatRunner] = request.app.state.chat_runner_factory
        return StreamingResponse(
            _event_source(payload, user, factory),
            media_type="text/event-stream",
        )

    return router


async def _event_source(
    payload: SecretaryChatRequest,
    user: User,
    factory: Callable[[], ChatRunner],
) -> AsyncIterator[bytes]:
    token = CancellationToken()
    messages = [
        RuntimeChatMessage(role=m.role, content=m.content) for m in payload.messages
    ]
    runner = factory()

    try:
        async for event in runner.run(
            department_id="secretary",
            user_id=user.id,
            messages=messages,
            cancel_token=token,
        ):
            yield f"data: {json.dumps(to_wire(event))}\n\n".encode()
    except asyncio.CancelledError:
        token.cancel()
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("chat stream terminated with error", exc_info=True)
        error_event = ChatError(
            message_id="",
            error_class=type(exc).__name__,
            message=str(exc),
        )
        yield f"data: {json.dumps(to_wire(error_event))}\n\n".encode()
