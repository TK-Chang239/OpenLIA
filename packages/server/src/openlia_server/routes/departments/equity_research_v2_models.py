"""v2.2 equity-research per-stage model assignment endpoints.

Two endpoints:

- ``GET /api/departments/equity-research/v2/model-assignments``: return the
  caller's saved {slot: model_id} mapping plus the canonical slot list and
  the list of `missing` slots that must be assigned before a v2 run will
  be accepted.
- ``PUT /api/departments/equity-research/v2/model-assignments``: replace
  the caller's assignments. The body is `{assignments: {slot: model_id}}`
  with optional `prune: bool` (default true — slots absent from the body
  are deleted). Every supplied model_id must resolve via SQLModelRegistry.

There is intentionally no server-side default model; v2.2 runs return 422
when any required slot is unassigned.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from openlia.llm.runtime.report_v2.slots import REQUIRED_V2_SLOTS, V2Slot
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import er_v2_models as svc
from openlia_server.services.llm_registry import SQLModelRegistry


class AssignmentsOut(BaseModel):
    assignments: dict[str, str]
    slots: list[str]
    missing: list[str]


class AssignmentsIn(BaseModel):
    assignments: dict[str, str] = Field(default_factory=dict)


def build_equity_research_v2_models_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(
        prefix="/departments/equity-research/v2/model-assignments",
        tags=["equity-research-v2-models"],
    )

    @router.get("", response_model=AssignmentsOut)
    def get_assignments(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> AssignmentsOut:
        mapping = svc.get_assignments(db, user_id=user.id)
        return AssignmentsOut(
            assignments=mapping,
            slots=[s.value for s in REQUIRED_V2_SLOTS],
            missing=svc.missing_slots(mapping),
        )

    @router.put("", response_model=AssignmentsOut)
    def put_assignments(
        payload: AssignmentsIn,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> AssignmentsOut:
        known = {s.value for s in V2Slot}
        unknown = sorted(set(payload.assignments.keys()) - known)
        if unknown:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "unknown_slots",
                    "message": f"unknown slot(s): {unknown}",
                },
            )
        registry = SQLModelRegistry(db)
        bad: list[dict[str, str]] = []
        for slot, model_id in payload.assignments.items():
            if registry.get_by_id(model_id) is None:
                bad.append({"slot": slot, "model_id": model_id})
        if bad:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "model_not_found",
                    "message": "one or more model_id values do not resolve",
                    "bad": bad,
                },
            )
        mapping = svc.set_assignments(
            db, user_id=user.id, mapping=payload.assignments
        )
        db.commit()
        return AssignmentsOut(
            assignments=mapping,
            slots=[s.value for s in REQUIRED_V2_SLOTS],
            missing=svc.missing_slots(mapping),
        )

    return router
