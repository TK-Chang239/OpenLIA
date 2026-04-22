"""Setup Wizard routes under /setup/*."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.session import get_db_session
from openlia_server.middleware.wizard_gate import require_wizard_active, require_wizard_session
from openlia_server.services import wizard as wizard_svc


def _set_wizard_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "openlia_wizard_session",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/setup",
    )


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class StatusOut(BaseModel):
    mode: str
    wizard_completed: bool
    current_step: str
    completed_steps: list[str]
    env_overrides: dict[str, str]


class ModeIn(BaseModel):
    mode: str = Field(pattern="^(personal|company)$")


class IdentityIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)


class AdminIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=60)


class AccessControlIn(BaseModel):
    signup_policy: str = Field(pattern="^(invite_only|closed)$")
    allowed_domains: str | None = None
    bind_host: str = Field(min_length=1, max_length=253)
    bind_port: int = Field(ge=1, le=65535)


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_setup_router() -> APIRouter:
    router = APIRouter(prefix="/setup", tags=["setup"])

    @router.get("/status", response_model=StatusOut)
    def get_status(db: Session = Depends(get_db_session)) -> StatusOut:
        s = wizard_svc.get_status(db, env=dict(os.environ))
        return StatusOut(
            mode=s.mode,
            wizard_completed=s.wizard_completed,
            current_step=s.current_step,
            completed_steps=s.completed_steps,
            env_overrides=s.env_overrides,
        )

    @router.post("/mode", dependencies=[Depends(require_wizard_active)])
    def post_mode(
        payload: ModeIn,
        response: Response,
        db: Session = Depends(get_db_session),
    ) -> dict[str, str]:
        if os.environ.get("OPENLIA_MODE"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "env_locked", "message": "Mode is locked by OPENLIA_MODE env var."},
            )
        wizard_svc.set_mode(db, payload.mode)  # type: ignore[arg-type]
        wizard_svc.advance_step(db, "mode", payload.mode)  # type: ignore[arg-type]
        token = wizard_svc.rotate_session_token(db)
        _set_wizard_cookie(response, token)
        return {"mode": payload.mode}

    @router.post("/takeover")
    def post_takeover(response: Response, db: Session = Depends(get_db_session)) -> dict[str, bool]:
        token = wizard_svc.rotate_session_token(db)
        _set_wizard_cookie(response, token)
        return {"ok": True}

    @router.post("/identity", dependencies=[Depends(require_wizard_active)])
    def post_identity(
        payload: IdentityIn,
        db: Session = Depends(get_db_session),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        wizard_svc.upsert_local_user(db, payload.display_name)
        wizard_svc.advance_step(db, "identity", "personal")
        return {"display_name": payload.display_name}

    @router.post("/admin", dependencies=[Depends(require_wizard_active)])
    def post_admin(
        payload: AdminIn,
        db: Session = Depends(get_db_session),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        try:
            wizard_svc.create_first_admin(db, payload.email, payload.password, payload.display_name)
        except wizard_svc.AdminExistsError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "admin_exists", "message": "An administrator is already configured."},
            ) from exc
        wizard_svc.advance_step(db, "admin", "company")
        return {"email": payload.email}

    @router.post("/access_control", dependencies=[Depends(require_wizard_active)])
    def post_access_control(
        payload: AccessControlIn,
        db: Session = Depends(get_db_session),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, bool]:
        mode = wizard_svc.get_status(db, env=dict(os.environ)).mode
        if mode != "company":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "wrong_mode", "message": "Access control is company-mode only."},
            )
        wizard_svc.set_signup_policy(
            db, policy=payload.signup_policy, allowed_domains=payload.allowed_domains
        )
        wizard_svc.set_config(db, "server.bind_host", payload.bind_host)
        wizard_svc.set_config(db, "server.bind_port", str(payload.bind_port))
        wizard_svc.advance_step(db, "access_control", "company")
        return {"ok": True}

    @router.post("/finish", dependencies=[Depends(require_wizard_active)])
    def post_finish(
        db: Session = Depends(get_db_session),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        mode = wizard_svc.get_status(db, env=dict(os.environ)).mode
        wizard_svc.finalize(db, mode)
        redirect = "/" if mode == "personal" else "/login"
        return {"redirect": redirect, "mode": mode}

    return router
