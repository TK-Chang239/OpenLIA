"""Market-index quotes for the Home TickerStrip.

``GET /markets/indices`` returns a fixed basket of live index quotes sourced
from EODHD. When no EODHD key is configured (env or a validated connector),
``available`` is false so the frontend can show a connect-EODHD empty state
rather than an error. Results are cached in-process for a short TTL so a busy
Home page does not fan out to EODHD on every render.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services import markets_quotes
from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

log = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 60.0
_FETCH_TIMEOUT_SECONDS = 20.0


def build_markets_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    require_user = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/markets", tags=["markets"])

    # Process-local TTL cache shared across users (index quotes are not
    # user-specific). Holds the last successful basket + its timestamp.
    cache: dict[str, object] = {"ts": 0.0, "data": None}

    def _resolve_key() -> str | None:
        with db_session_factory() as db:
            return resolve_eodhd_api_key(db)

    @router.get("/indices")
    async def indices(_user: User = require_user) -> dict:
        api_key = _resolve_key()
        if not api_key:
            return {"available": False, "indices": [], "as_of": None}

        now = time.monotonic()
        cached = cache["data"]
        if cached is not None and now - float(cache["ts"]) < _CACHE_TTL_SECONDS:
            return {"available": True, "indices": cached, "as_of": cache.get("as_of")}

        try:
            data = await asyncio.wait_for(
                asyncio.to_thread(markets_quotes.fetch_indices, api_key),
                timeout=_FETCH_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            log.warning("markets indices fetch failed: %s", exc)
            # Serve stale data if we have any; otherwise an empty (but available)
            # basket so the strip degrades quietly rather than erroring.
            if cached is not None:
                return {"available": True, "indices": cached, "as_of": cache.get("as_of")}
            return {"available": True, "indices": [], "as_of": None}

        cache["data"] = data
        cache["ts"] = now
        # Fetch timestamp, so the UI can label how fresh (and from which
        # source) these figures are — engine-authored dashboards may cite
        # different feeds and moments, and unlabeled disagreement reads as
        # a bug.
        cache["as_of"] = datetime.now(UTC).isoformat()
        return {"available": True, "indices": data, "as_of": cache["as_of"]}

    return router


__all__ = ["build_markets_router"]
