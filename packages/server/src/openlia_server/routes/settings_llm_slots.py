"""Admin endpoints for managing LLM slot defaults.

Slot defaults map (slot_kind, slot_id) -> model_id, replacing the
per-tier default mechanism. `slot_kind` is 'department' or 'system_role';
`slot_id` is a department id (e.g. 'secretary') or a system role id
(e.g. 'ai_review').
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.auth import build_require_active_admin
from openlia_server.services.slot_defaults import (
    InvalidSlotError,
    delete_slot_default,
    list_slot_defaults,
    set_slot_default,
)


class SlotDefaultIn(BaseModel):
    model_id: str


class SlotDefaultOut(BaseModel):
    slot_kind: str
    slot_id: str
    model_id: str


def build_llm_slot_defaults_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(
        prefix="/settings/admin/llm/slot-defaults",
        tags=["llm-admin", "slot-defaults"],
    )
    require_admin = build_require_active_admin(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("")
    def list_defaults(_=require_admin, db: DBSession = Depends(session_dep)) -> dict:
        rows = list_slot_defaults(db)
        return {
            "defaults": [
                SlotDefaultOut(
                    slot_kind=r.slot_kind,
                    slot_id=r.slot_id,
                    model_id=r.model_id,
                ).model_dump()
                for r in rows
            ]
        }

    @router.put("/{slot_kind}/{slot_id}", response_model=SlotDefaultOut)
    def upsert_default(
        slot_kind: str,
        slot_id: str,
        body: SlotDefaultIn,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> SlotDefaultOut:
        try:
            row = set_slot_default(
                db,
                slot_kind=slot_kind,
                slot_id=slot_id,
                model_id=body.model_id,
            )
        except InvalidSlotError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return SlotDefaultOut(
            slot_kind=row.slot_kind,
            slot_id=row.slot_id,
            model_id=row.model_id,
        )

    @router.delete("/{slot_kind}/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
    def remove_default(
        slot_kind: str,
        slot_id: str,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> None:
        try:
            delete_slot_default(db, slot_kind=slot_kind, slot_id=slot_id)
        except InvalidSlotError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return router
