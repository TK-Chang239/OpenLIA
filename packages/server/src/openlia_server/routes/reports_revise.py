"""POST /reports/{source_report_id}/revise — kicks off a RevisionRunner
as a background task and returns the new report_id immediately."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatSession, Report
from openlia_server.middleware.auth import build_require_auth


class ReviseReportIn(BaseModel):
    chat_session_id: str
    revision_brief: str
    sections_to_focus: list[str] | None = None


_SOURCE_CHAT_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _flag_on() -> bool:
    return os.environ.get("OPENLIA_REVISION_PASS_ENABLED", "0") == "1"


def _get_bundle_dir() -> Path:
    return Path(
        os.environ.get("OPENLIA_REPORT_BUNDLE_DIR") or Path.home() / ".openlia" / "report_bundles"
    )


async def _execute_revise(
    *,
    db: DBSession,
    user: User,
    source_report_id: str,
    body: ReviseReportIn,
    db_session_factory: Callable[[], DBSession],
    app_state: Any = None,
) -> dict:
    """Core revise logic, callable from both the /revise endpoint and the
    retry handler.  ``app_state`` is ``request.app.state`` when available;
    None is acceptable (falls back to inline registry/presence construction).
    """
    if not _flag_on():
        raise HTTPException(503, "revision pass not enabled")

    source_row = db.get(Report, source_report_id)
    if source_row is None or source_row.user_id != user.id:
        raise HTTPException(404, "report not found")

    chat = db.get(ChatSession, body.chat_session_id)
    if chat is None or chat.user_id != user.id or chat.attached_report_id != source_report_id:
        raise HTTPException(400, "chat session is not bound to this report")

    async with _SOURCE_CHAT_LOCKS[body.chat_session_id]:
        new_report_id = f"r_{uuid.uuid4().hex[:12]}"
        new_row = Report(
            id=new_report_id,
            user_id=user.id,
            department=source_row.department,
            report_type=source_row.report_type,
            title=source_row.title,
            content_markdown="",
            content_structured={},
            model_ref="",
            status="generating",
            started_at=datetime.now(UTC),
            original_request={
                "kind": "revision",
                "source_report_id": source_report_id,
                "chat_session_id": body.chat_session_id,
                "revision_brief": body.revision_brief,
                "sections_to_focus": body.sections_to_focus,
            },
        )
        db.add(new_row)
        db.commit()

    registry: Any = getattr(app_state, "bg_report_registry", None) if app_state else None
    presence: Any = getattr(app_state, "user_presence_registry", None) if app_state else None

    if registry is None:
        # No registry available — still return successfully; runner starts
        # but fan-out to subscribers is unavailable (acceptable in dev/test).
        from openlia_server.services.background_report_registry import (
            BackgroundReportRegistry,
        )

        registry = BackgroundReportRegistry()

    if presence is None:
        from openlia_server.services.user_presence_registry import UserPresenceRegistry

        presence = UserPresenceRegistry()

    bundle_dir = _get_bundle_dir()

    # Pull resolve + flagship_provider_factory from app_state when available
    # (wired by lifespan); fall back to building inline for tests/dev.
    resolve_fn = getattr(app_state, "revision_resolve", None) if app_state else None
    flagship_factory = (
        getattr(app_state, "revision_flagship_provider_factory", None) if app_state else None
    )

    if resolve_fn is None or flagship_factory is None:
        from openlia.llm.adapters import build_adapter
        from openlia.llm.resolver import resolve as _resolve

        def resolve_fn(  # type: ignore[misc]
            *,
            department_id: str,
            user_id: str | None,
            registry: Any,
            role: str = "flagship",
            model_id_override: str | None = None,
        ):
            return _resolve(
                department_id=department_id,
                registry=registry,
                user_id=user_id,
            )

        def flagship_factory(resolved):  # type: ignore[misc]
            return build_adapter(
                kind=resolved.provider_kind,
                credentials=resolved.credentials,
                model=resolved.model_ref,
                capabilities=resolved.capabilities,
            )

    from openlia.llm.runtime.prompts import PromptLoader
    from openlia.llm.runtime.revision_runner import RevisionRunner

    from openlia_server.services.revision_wrapper import run_wrapped_revision

    prompts = PromptLoader()

    runner = RevisionRunner(
        prompts=prompts,
        resolve=resolve_fn,
        registry=registry,
        flagship_provider_factory=flagship_factory,
        report_id_factory=lambda: new_report_id,
        bundle_dir=bundle_dir,
        db_session_factory=db_session_factory,
    )

    runner_coro = runner.run(
        department_id=source_row.department,
        user_id=user.id,
        source_report_id=source_report_id,
        chat_session_id=body.chat_session_id,
        revision_brief=body.revision_brief,
        sections_to_focus=body.sections_to_focus,
    )

    task = registry.submit(
        user_id=user.id,
        report_id=new_report_id,
        runner_coro=runner_coro,
    )

    async def _subscribe():
        from openlia.llm.runtime.events import ReportComplete, ReportError

        queue: asyncio.Queue = asyncio.Queue(maxsize=512)
        task.subscriber_queues.add(queue)
        try:
            while True:
                ev = await queue.get()
                yield ev
                if isinstance(ev, (ReportComplete, ReportError)):
                    return
        finally:
            task.subscriber_queues.discard(queue)

    _wrapper_task = asyncio.create_task(
        run_wrapped_revision(
            runner_coro=_subscribe(),
            new_report_id=new_report_id,
            source_chat_session_id=body.chat_session_id,
            user_id=user.id,
            db_session_factory=db_session_factory,
            presence=presence,
            registry=registry,
        )
    )
    # Keep a reference to prevent garbage collection before completion.
    if app_state is not None:
        getattr(app_state, "_revision_tasks", set()).add(_wrapper_task)
        _wrapper_task.add_done_callback(
            lambda t: getattr(app_state, "_revision_tasks", set()).discard(t)
        )

    return {"report_id": new_report_id, "status": "generating"}


def build_reports_revise_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    router = APIRouter(tags=["reports"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.post("/reports/{source_report_id}/revise")
    async def revise_report_ep(
        source_report_id: str,
        body: ReviseReportIn,
        request: Request,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> dict:
        return await _execute_revise(
            db=db,
            user=user,
            source_report_id=source_report_id,
            body=body,
            db_session_factory=db_session_factory,
            app_state=request.app.state,
        )

    return router
