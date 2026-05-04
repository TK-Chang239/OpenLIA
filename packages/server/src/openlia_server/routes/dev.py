"""Dev-mode visibility endpoints — gated by ``OPENLIA_DEV_MODE``.

Mounts ``GET /dev/info``, ``GET /dev/events`` and
``GET /dev/events/stream`` (SSE). When the env var isn't set, every
endpoint returns 404 so the frontend's probe naturally hides the panel.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from openlia_server import dev_events


def build_dev_router() -> APIRouter:
    router = APIRouter(prefix="/dev", tags=["dev"])

    @router.get("/info")
    def dev_info() -> dict[str, bool]:
        if not dev_events.is_enabled():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return {"enabled": True}

    @router.get("/events")
    def list_events() -> dict[str, list[dict]]:
        if not dev_events.is_enabled():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return {"items": dev_events.snapshot()}

    @router.get("/events/stream")
    async def stream_events(request: Request) -> StreamingResponse:
        if not dev_events.is_enabled():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        async def gen() -> AsyncIterator[bytes]:
            async for event in dev_events.stream():
                if await request.is_disconnected():
                    return
                yield (
                    f"event: dev.event\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                ).encode()
                # Yield control so disconnect detection has a chance to fire.
                await asyncio.sleep(0)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    return router
