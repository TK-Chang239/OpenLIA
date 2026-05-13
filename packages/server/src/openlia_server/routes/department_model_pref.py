"""Per-(user, department) model preference endpoints.

Mounted under ``/api/departments/{department}/model-pref``. The
``{department}`` slug is the dash-form (e.g. ``morning-briefing``);
internally normalized to underscore form for storage. Wins over the
user-level preferred model and server slot default — see
``openlia.llm.resolver.resolve``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.resolver import resolve as resolve_model
from openlia.prompts import DEPARTMENT_LABELS
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.config import LLMModel
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import user_department_model_pref as svc
from openlia_server.services.llm_registry import SQLModelRegistry


def _normalize_department(slug: str) -> str:
    """Accept dash- or underscore-form; return underscore-form."""
    underscore = slug.replace("-", "_")
    if underscore not in DEPARTMENT_LABELS:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"unknown department: {slug!r}",
        )
    return underscore


class _ModelPrefOut(BaseModel):
    department_id: str
    model_id: str | None
    effective_model_id: str | None


class _ModelPrefIn(BaseModel):
    model_id: str


def _resolve_effective_model_id(db: DBSession, *, user_id: str, department_id: str) -> str | None:
    """Return the model_id the resolver would pick today.

    Mirrors the chain in ``openlia.llm.resolver.resolve``:
    dept user override → user-level pref → server slot default. Used so the
    picker can show what's actually in use even when no per-dept override is
    set.
    """
    try:
        resolved = resolve_model(
            department_id=department_id,
            registry=SQLModelRegistry(db),
            user_id=user_id,
        )
    except ModelNotConfiguredError:
        return None
    return resolved.model_id


def build_department_model_pref_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/departments", tags=["department-model-pref"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/{department}/model-pref", response_model=_ModelPrefOut)
    def get_model_pref(
        department: str,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _ModelPrefOut:
        dept_id = _normalize_department(department)
        override = svc.get(db, user_id=user.id, department_id=dept_id)
        effective = _resolve_effective_model_id(db, user_id=user.id, department_id=dept_id)
        return _ModelPrefOut(
            department_id=dept_id,
            model_id=override,
            effective_model_id=effective,
        )

    @router.put("/{department}/model-pref", response_model=_ModelPrefOut)
    def put_model_pref(
        department: str,
        payload: _ModelPrefIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _ModelPrefOut:
        dept_id = _normalize_department(department)
        if db.get(LLMModel, payload.model_id) is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"unknown model_id: {payload.model_id!r}",
            )
        svc.upsert(db, user_id=user.id, department_id=dept_id, model_id=payload.model_id)
        db.commit()
        return _ModelPrefOut(
            department_id=dept_id,
            model_id=payload.model_id,
            effective_model_id=payload.model_id,
        )

    @router.delete("/{department}/model-pref", status_code=status.HTTP_204_NO_CONTENT)
    def delete_model_pref(
        department: str,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> None:
        dept_id = _normalize_department(department)
        svc.clear(db, user_id=user.id, department_id=dept_id)
        db.commit()

    return router
