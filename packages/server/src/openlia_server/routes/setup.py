"""Setup Wizard routes under /setup/*."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.wizard_gate import build_wizard_gate
from openlia_server.services import wizard as wizard_svc


def _set_wizard_cookie(response: Response, token: str) -> None:
    # Path "/" because the browser hits /api/setup/* while the server
    # strips /api before routing — a /setup-scoped cookie would never be
    # sent. The cookie is httponly + samesite=lax so broader scope is safe.
    response.set_cookie(
        "openlia_wizard_session",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
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


class _SetupTierEntryIn(BaseModel):
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    env_var_name: str | None = None
    capabilities: dict | None = None
    is_tier_default: bool = True


class ModelsIn(BaseModel):
    thinking: list[_SetupTierEntryIn] = Field(default_factory=list)
    everyday: list[_SetupTierEntryIn] = Field(default_factory=list)
    quick: list[_SetupTierEntryIn] = Field(default_factory=list)


class ModelsTestIn(BaseModel):
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    env_var_name: str | None = None


class RequiredTiersOut(BaseModel):
    required_tiers: list[str]
    enabled_departments: list[str]


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_setup_router(
    *,
    db_session_factory: Callable[[], Session],
    mode: str,
    is_loopback_request: Callable[[Request], bool],
) -> APIRouter:
    router = APIRouter(prefix="/setup", tags=["setup"])
    session_dep = make_session_dependency(db_session_factory)
    require_wizard_active, require_wizard_session = build_wizard_gate(session_dep)

    # Background tasks live in a closure so each app gets its own set;
    # `lifespan` (in app.py) cancels them via `app.state.setup_background_tasks`.
    background_tasks: set[asyncio.Task[Any]] = set()

    def require_loopback_during_wizard(request: Request) -> None:
        """Loopback gate: the wizard binds to 127.0.0.1 during setup regardless of mode.

        Once `wizard.completed == true`, this gate is irrelevant — the
        `require_wizard_active` 410-gate blocks /setup/* writes anyway.
        """
        if not is_loopback_request(request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "loopback_required",
                    "message": "Setup must be accessed via a local connection.",
                },
            )

    @router.get("/status", response_model=StatusOut)
    def get_status(db: Session = Depends(session_dep)) -> StatusOut:
        s = wizard_svc.get_status(db, env=dict(os.environ))
        return StatusOut(
            mode=s.mode,
            wizard_completed=s.wizard_completed,
            current_step=s.current_step,
            completed_steps=s.completed_steps,
            env_overrides=s.env_overrides,
        )

    @router.get("/required_tiers", response_model=RequiredTiersOut)
    def get_required_tiers(db: Session = Depends(session_dep)) -> RequiredTiersOut:
        from openlia.departments import (
            get_enabled_default_tiers,
            get_registered_department_ids,
        )

        enabled = get_registered_department_ids()
        tiers = get_enabled_default_tiers(enabled)
        # Stable ordering: thinking > everyday > quick (most-demanding first).
        order = ["thinking", "everyday", "quick"]
        ordered = [t for t in order if t in tiers]
        return RequiredTiersOut(required_tiers=ordered, enabled_departments=enabled)

    @router.post(
        "/mode",
        dependencies=[Depends(require_loopback_during_wizard), Depends(require_wizard_active)],
    )
    def post_mode(
        payload: ModeIn,
        response: Response,
        db: Session = Depends(session_dep),
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

    @router.post("/takeover", dependencies=[Depends(require_loopback_during_wizard)])
    def post_takeover(response: Response, db: Session = Depends(session_dep)) -> dict[str, bool]:
        token = wizard_svc.rotate_session_token(db)
        _set_wizard_cookie(response, token)
        return {"ok": True}

    @router.post(
        "/identity",
        dependencies=[Depends(require_loopback_during_wizard), Depends(require_wizard_active)],
    )
    def post_identity(
        payload: IdentityIn,
        db: Session = Depends(session_dep),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        wizard_svc.upsert_local_user(db, payload.display_name)
        wizard_svc.advance_step(db, "identity", "personal")
        return {"display_name": payload.display_name}

    @router.post(
        "/admin",
        dependencies=[Depends(require_loopback_during_wizard), Depends(require_wizard_active)],
    )
    def post_admin(
        payload: AdminIn,
        db: Session = Depends(session_dep),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        try:
            wizard_svc.create_first_admin(db, payload.email, payload.password, payload.display_name)
        except wizard_svc.AdminExistsError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "admin_exists",
                    "message": "An administrator is already configured.",
                },
            ) from exc
        wizard_svc.advance_step(db, "admin", "company")
        return {"email": payload.email}

    @router.post(
        "/access_control",
        dependencies=[Depends(require_loopback_during_wizard), Depends(require_wizard_active)],
    )
    def post_access_control(
        payload: AccessControlIn,
        db: Session = Depends(session_dep),
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

    @router.post(
        "/models",
        dependencies=[Depends(require_loopback_during_wizard), Depends(require_wizard_active)],
    )
    def post_models(
        payload: ModelsIn,
        db: Session = Depends(session_dep),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, bool]:
        from openlia_server.services.wizard_models import UnknownLLMKindError, save_models

        try:
            save_models(db, payload)
        except UnknownLLMKindError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "unknown_llm_kind", "message": str(exc)},
            ) from exc
        wizard_svc.advance_step(db, "models", "shared")
        return {"ok": True}

    @router.post(
        "/models/test",
        dependencies=[Depends(require_loopback_during_wizard), Depends(require_wizard_active)],
    )
    async def post_models_test(
        payload: ModelsTestIn,
        _: None = Depends(require_wizard_session),
    ) -> dict[str, Any]:
        from openlia_server.routes.settings import _run_connection_test

        result = await _run_connection_test(
            payload.provider,
            api_key=payload.api_key,
            base_url=payload.base_url,
            env_var_name=payload.env_var_name,
            model=payload.model,
        )
        # Frontend expects {ok, latency_ms, error}; settings returns
        # {ok, latency_ms, error_class, error_msg}. Map down.
        out = result.model_dump()
        return {
            "ok": out.get("ok", False),
            "latency_ms": out.get("latency_ms"),
            "error": out.get("error_msg") or out.get("error_class"),
        }

    @router.post(
        "/finish",
        dependencies=[Depends(require_loopback_during_wizard), Depends(require_wizard_active)],
    )
    def post_finish(
        db: Session = Depends(session_dep),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        mode = wizard_svc.get_status(db, env=dict(os.environ)).mode
        wizard_svc.finalize(db, mode)
        redirect = "/" if mode == "personal" else "/login"
        return {"redirect": redirect, "mode": mode}

    # Expose the closure-local task set to the lifespan for cancellation.
    router.state_background_tasks = background_tasks  # type: ignore[attr-defined]

    return router
