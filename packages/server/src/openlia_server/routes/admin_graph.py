"""Slice 7 — admin force-run of graph extraction.

``POST /admin/graph/extract-now?user_id=<id>``

Runs the same extraction pipeline the nightly scheduler runs, but for
one target user, right now. Primary purpose is dev iteration so we
don't wait until 03:00 in the user's TZ to see proposals materialize.

The route writes one ``graph_extraction_runs`` audit row per
invocation. On extractor failure the row is committed with the error
string before the route raises 500 — otherwise the FastAPI session
dependency would roll back our audit alongside the failure.

The ``extract_fn_factory`` parameter exists so tests can substitute a
fake without spinning up a real LLM provider.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, LLMResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatSession
from openlia_server.middleware.auth import build_require_active_admin
from openlia_server.services import (
    graph_extraction,
    graph_extraction_llm,
    graph_extraction_runs,
)
from openlia_server.services.adapter_llm_client import (
    AdapterLlmNotConfigured,
    _resolve_provider_for_role,
)


class ExtractNowOut(BaseModel):
    run_id: str
    proposals_inserted: int
    sessions_processed: int
    error: str | None


ExtractFnFactory = Callable[[DBSession, str], tuple[graph_extraction.ExtractFn, str]]


class _SyncProviderAdapter:
    """Bridge async ``LLMProvider.generate`` to the sync ``.generate``
    signature ``graph_extraction_llm.make_extract_fn`` expects.

    Extraction runs inside a synchronous request handler, so we drive
    the coroutine with ``asyncio.run`` per call. The nightly scheduler
    will eventually call the async path directly; this adapter is the
    bridge until that wiring exists.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def generate(self, request: LLMRequest) -> LLMResponse:
        return asyncio.run(self._provider.generate(request))


def _default_extract_fn_factory(
    db: DBSession, user_id: str
) -> tuple[graph_extraction.ExtractFn, str]:
    provider = _resolve_provider_for_role(db, "graph_extraction")
    client = _SyncProviderAdapter(provider)
    extract_fn = graph_extraction_llm.make_extract_fn(client)
    return extract_fn, provider.model


def build_admin_graph_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
    extract_fn_factory: ExtractFnFactory | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/admin/graph", tags=["admin-graph"])
    require_admin = build_require_active_admin(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    factory: ExtractFnFactory = extract_fn_factory or _default_extract_fn_factory

    @router.post("/extract-now", response_model=ExtractNowOut)
    def extract_now(
        user_id: str,
        admin: User = require_admin,
        db: DBSession = Depends(session_dep),
    ) -> ExtractNowOut:
        target = db.get(User, user_id)
        if target is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "user_not_found", "message": f"unknown user_id: {user_id!r}"},
            )

        try:
            extract_fn, model_id = factory(db, user_id)
        except AdapterLlmNotConfigured as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "llm_not_configured", "message": str(exc)},
            ) from exc

        run = graph_extraction_runs.record_run_start(db, user_id=user_id, model_id=model_id)
        # Commit the open audit row so a downstream extractor exception
        # doesn't take it down with the rest of the transaction.
        db.commit()
        run_id = run.id

        try:
            inserted, processed = _run_extraction(db, user_id=user_id, extract_fn=extract_fn)
        except Exception as exc:
            db.rollback()
            graph_extraction_runs.record_run_finish(db, run_id=run_id, error=str(exc)[:256])
            db.commit()
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "extraction_failed",
                    "message": str(exc),
                    "run_id": run_id,
                },
            ) from exc

        graph_extraction_runs.record_run_finish(
            db,
            run_id=run_id,
            proposals_inserted=inserted,
            sessions_processed=processed,
        )
        return ExtractNowOut(
            run_id=run_id,
            proposals_inserted=inserted,
            sessions_processed=processed,
            error=None,
        )

    return router


def _run_extraction(
    db: DBSession,
    *,
    user_id: str,
    extract_fn: graph_extraction.ExtractFn,
) -> tuple[int, int]:
    """Loop over eligible sessions and call the extractor on each.

    Watermark of ``None`` means "first run for this user" — include
    every session.
    """
    watermark = graph_extraction_runs.high_watermark(db, user_id=user_id)
    stmt = select(ChatSession).where(ChatSession.user_id == user_id)
    if watermark is not None:
        stmt = stmt.where(ChatSession.updated_at > watermark)
    sessions: list[ChatSession] = list(db.execute(stmt).scalars())

    proposals_inserted = 0
    sessions_processed = 0
    for s in sessions:
        rows = graph_extraction.extract_proposals_from_session(
            db,
            session_id=s.id,
            user_id=user_id,
            extract_fn=extract_fn,
        )
        proposals_inserted += len(rows)
        sessions_processed += 1
    return proposals_inserted, sessions_processed


__all__: list[str] = [
    "ExtractNowOut",
    "build_admin_graph_router",
]
