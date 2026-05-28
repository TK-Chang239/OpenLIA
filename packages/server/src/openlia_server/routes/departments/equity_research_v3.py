"""v3 equity-research route — single-model engine.

Phase 0 ships one endpoint:

- ``POST /api/departments/equity-research/v3/runs``
    Start a v3 run. Returns the (placeholder) ``RunResult``.

The route is gated by the ``REPORT_ENGINE_VERSION`` environment
variable. When the value is anything other than ``v3`` (default
``v2.3``) the endpoint returns 503 with a clear message — the route is
still mounted so callers see a meaningful error instead of a 404.

Capability gate failures (``CapabilityError`` from the runner) come
back as 400. Other ``ValueError``/``RuntimeError`` failures from the
runner come back as 500. Phase 1 introduces persistence and SSE; this
file stays small until then.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    CapabilityError,
    Language,
    ReportLength,
    Runner,
    RunRequest,
    RunResult,
    TemplateSpec,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth

_ENV_FLAG = "REPORT_ENGINE_VERSION"
_ENABLED_VALUE = "v3"


class StartV3Payload(BaseModel):
    subject: str = Field(..., min_length=1)
    language: Language = Language.EN
    length: ReportLength = ReportLength.NORMAL
    # Phase 0 resolves the template from the ``report_type`` built-in
    # registry. Phase 1.5 will accept user-uploaded templates via a
    # separate ``template_id`` field; Phase 0 keeps the surface minimal.
    report_type: ReportType = ReportType.INITIATION
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)


def _engine_disabled() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(
            f"v3 engine disabled. Set {_ENV_FLAG}={_ENABLED_VALUE} to enable. "
            f"Default engine is v2.3 at /departments/equity-research/v2.3/runs."
        ),
    )


def _engine_enabled() -> bool:
    return os.environ.get(_ENV_FLAG, "").strip().lower() == _ENABLED_VALUE


def build_equity_research_v3_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(
        prefix="/departments/equity-research/v3",
        tags=["equity-research-v3"],
    )

    @router.post("/runs", response_model=RunResult)
    async def start_run(
        payload: StartV3Payload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunResult:
        if not _engine_enabled():
            raise _engine_disabled()

        template: TemplateSpec = get_builtin(payload.report_type)
        run_request = RunRequest(
            subject=payload.subject,
            template=template,
            language=payload.language,
            length=payload.length,
            provider_kind=payload.provider_kind,
            model=payload.model,
        )
        runner = Runner()
        try:
            return await runner.run(run_request)
        except CapabilityError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
