"""GET /notifications/stream — app-shell SSE for completion toasts."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services.user_presence_registry import UserPresenceRegistry


def _get_presence(request: Request) -> UserPresenceRegistry:
    presence: Any = getattr(request.app.state, "user_presence_registry", None)
    if presence is None:
        presence = UserPresenceRegistry()
        request.app.state.user_presence_registry = presence
    return presence


def build_notifications_stream_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
    heartbeat_seconds: int = 30,
) -> APIRouter:
    router = APIRouter(tags=["notifications"])
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)

    @router.get("/notifications/stream")
    async def stream_notifications(
        request: Request,
        user=require_auth,
    ) -> StreamingResponse:
        presence = _get_presence(request)
        queue = presence.attach(user.id)

        async def gen() -> AsyncIterator[bytes]:
            try:
                while True:
                    try:
                        ev = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                        name = ev.get("type", "event")
                        yield f"event: {name}\ndata: {json.dumps(ev, default=str)}\n\n".encode()
                    except TimeoutError:
                        yield b"event: report.heartbeat\ndata: {}\n\n"
            finally:
                presence.detach(user.id, queue)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @router.post("/notifications/presence-close")
    def presence_close(
        request: Request,
        user=require_auth,
    ) -> dict:
        presence = _get_presence(request)
        presence.set_imminent_disconnect(user.id)
        return {"ok": True}

    return router
