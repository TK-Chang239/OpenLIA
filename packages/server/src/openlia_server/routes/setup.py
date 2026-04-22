"""Setup Wizard routes under /setup/*."""
from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.ai_review import store as review_store_mod
from openlia_server.ai_review.runner import run_review as _run_review
from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.wizard_gate import require_wizard_active, require_wizard_session
from openlia_server.services import wizard as wizard_svc

# Departments and their basic data requirements for the AI review step.
_background_tasks: set[asyncio.Task[Any]] = set()

_DEPT_REQS: dict[str, list[str]] = {
    "secretary": [],
    "equity_research": ["stock_quote", "company_profile", "financial_statements"],
    "earnings_update": ["earnings_data", "stock_quote"],
    "morning_briefing": ["market_news", "stock_quote"],
    "retail_sentiment": ["social_posts"],
    "macro_research": ["macro_indicators", "stock_quote"],
    "panic_thermometer": ["market_news", "stock_quote"],
}


class _ReviewLLMWrapper:
    """Bridges the runner's (prompt, max_tokens) protocol with the real LLM adapter."""

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    async def generate(self, *, prompt: str, max_tokens: int) -> Any:
        from openlia.llm.types import LLMRequest, Message

        req = LLMRequest(messages=[Message(role="user", content=prompt)], max_tokens=max_tokens)
        return await self._adapter.generate(req)


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


def build_setup_router(
    *,
    db_session_factory: Callable[[], Session],
    mode: str,
    is_loopback_request: Callable[[Request], bool],
) -> APIRouter:
    router = APIRouter(prefix="/setup", tags=["setup"])
    session_dep = make_session_dependency(db_session_factory)

    def require_loopback_if_personal(request: Request) -> None:
        if mode == "personal" and not is_loopback_request(request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "loopback_required",
                    "message": "Setup writes require a local connection in personal mode.",
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

    @router.post("/mode", dependencies=[
        Depends(require_loopback_if_personal), Depends(require_wizard_active)
    ])
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

    @router.post("/takeover", dependencies=[Depends(require_loopback_if_personal)])
    def post_takeover(response: Response, db: Session = Depends(session_dep)) -> dict[str, bool]:
        token = wizard_svc.rotate_session_token(db)
        _set_wizard_cookie(response, token)
        return {"ok": True}

    @router.post("/identity", dependencies=[
        Depends(require_loopback_if_personal), Depends(require_wizard_active)
    ])
    def post_identity(
        payload: IdentityIn,
        db: Session = Depends(session_dep),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        wizard_svc.upsert_local_user(db, payload.display_name)
        wizard_svc.advance_step(db, "identity", "personal")
        return {"display_name": payload.display_name}

    @router.post("/admin", dependencies=[
        Depends(require_loopback_if_personal), Depends(require_wizard_active)
    ])
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

    @router.post("/access_control", dependencies=[
        Depends(require_loopback_if_personal), Depends(require_wizard_active)
    ])
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

    @router.post("/review/run", dependencies=[
        Depends(require_loopback_if_personal), Depends(require_wizard_active)
    ])
    async def post_review_run(
        db: Session = Depends(session_dep),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        from openlia.llm.adapters import build_adapter
        from openlia.llm.capabilities import capabilities_for
        from openlia.llm.types import ModelTier

        from openlia_server.services.data_providers import list_providers as list_dp
        from openlia_server.services.llm_registry import SQLModelRegistry

        store = review_store_mod.DEFAULT_STORE
        review_id = store.create()

        registry = SQLModelRegistry(db)
        row = (
            registry.get_tier_default(ModelTier.QUICK)
            or registry.get_any_in_tier(ModelTier.QUICK)
        )

        departments = list(_DEPT_REQS.items())
        dp_rows = list_dp(db)
        providers = [
            {"id": r.id, "category": r.kind, "provider": r.kind}
            for r in dp_rows
        ]

        if row is None:
            store.update(review_id, state="failed", error="No Quick-tier LLM configured.")
        else:
            adapter = build_adapter(
                kind=row.provider_kind,
                credentials=row.credentials,
                model=row.model_ref,
                capabilities=capabilities_for(
                    row.provider_kind, row.model_ref, row.capability_override
                ),
            )
            llm_wrapper = _ReviewLLMWrapper(adapter)
            task = asyncio.create_task(
                _run_review(
                    review_id=review_id,
                    db=db,
                    llm=llm_wrapper,
                    departments=departments,
                    providers=providers,
                    store=store,
                )
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        return {"review_id": review_id}

    @router.get("/review/{review_id}")
    def get_review(
        review_id: str,
        _: None = Depends(require_wizard_session),
    ) -> dict[str, object]:
        entry = review_store_mod.DEFAULT_STORE.get(review_id)
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "review_not_found", "message": "Unknown review id."},
            )
        return entry

    @router.post("/finish", dependencies=[
        Depends(require_loopback_if_personal), Depends(require_wizard_active)
    ])
    def post_finish(
        db: Session = Depends(session_dep),
        _: None = Depends(require_wizard_session),
    ) -> dict[str, str]:
        mode = wizard_svc.get_status(db, env=dict(os.environ)).mode
        wizard_svc.finalize(db, mode)
        redirect = "/" if mode == "personal" else "/login"
        return {"redirect": redirect, "mode": mode}

    return router
