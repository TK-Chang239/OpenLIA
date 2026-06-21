"""Cache admin API (X5).

GET  /api/cache/stats       — total entry count and total bytes stored.
DELETE /api/cache/documents — flush all or per-ticker cached documents.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.cache import CachedDocument
from openlia_server.middleware.auth import build_require_active_admin


def build_cache_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"] = "personal",
) -> APIRouter:
    """Mount the cache admin API under /cache.

    The router is gated by `require_active_admin`: GET /cache/stats and the
    destructive DELETE /cache/documents must never be reachable unauthenticated.
    In personal mode the dependency resolves to the synthetic `local` user; in
    company mode it requires a session cookie tied to an admin user.
    """
    require_admin = build_require_active_admin(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/cache", tags=["cache"], dependencies=[require_admin])
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/stats")
    def cache_stats(session: DBSession = Depends(session_dep)) -> dict:
        total = session.query(CachedDocument).count()
        total_bytes = session.query(func.coalesce(func.sum(CachedDocument.bytes_size), 0)).scalar()
        return {"total_entries": total, "total_bytes": int(total_bytes or 0)}

    @router.delete("/documents")
    def clear_cache(
        ticker: str | None = Query(None),
        session: DBSession = Depends(session_dep),
    ) -> dict:
        q = session.query(CachedDocument)
        if ticker:
            q = q.filter(CachedDocument.ticker == ticker)
        count = q.count()
        q.delete()
        session.commit()
        return {"deleted": count}

    return router
