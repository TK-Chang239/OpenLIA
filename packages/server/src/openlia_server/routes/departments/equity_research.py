"""GET/PUT /departments/equity-research/config routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.equity_research_config import (
    CustomSectionDTO,
    EquityResearchConfigService,
)


class CustomSectionPayload(BaseModel):
    id: str
    title: str
    description: str | None = None


class ErConfigPatch(BaseModel):
    report_mode: str | None = None
    report_length: str | None = None
    sections_by_mode: dict[str, list[str]] | None = None
    custom_sections_by_mode: dict[str, list[CustomSectionPayload]] | None = None


def _serialize(cfg) -> dict:
    return {
        "report_mode": cfg.report_mode,
        "report_length": cfg.report_length,
        "sections_by_mode": cfg.sections_by_mode,
        "custom_sections_by_mode": {
            mode: [{"id": c.id, "title": c.title, "description": c.description} for c in customs]
            for mode, customs in cfg.custom_sections_by_mode.items()
        },
    }


def build_equity_research_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/departments/equity-research", tags=["equity-research"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/config")
    def get_config(
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> dict:
        svc = EquityResearchConfigService(session)
        return _serialize(svc.get_config(user.id))

    @router.put("/config")
    def put_config(
        patch: ErConfigPatch,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> dict:
        svc = EquityResearchConfigService(session)
        try:
            updated = svc.update_config(
                user.id,
                report_mode=patch.report_mode,
                report_length=patch.report_length,
                sections_by_mode=patch.sections_by_mode,
                custom_sections_by_mode=(
                    {
                        m: [
                            CustomSectionDTO(id=c.id, title=c.title, description=c.description)
                            for c in customs
                        ]
                        for m, customs in patch.custom_sections_by_mode.items()
                    }
                    if patch.custom_sections_by_mode is not None
                    else None
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _serialize(updated)

    return router
