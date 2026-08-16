"""Admin HTTP surface for invite + user + reset-request management."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import PasswordResetRequest, SignupInvite, User
from openlia_server.middleware.auth import build_require_active_admin
from openlia_server.middleware.rate_limit import limiter
from openlia_server.services.auth import admin_roles, sessions, tokens
from openlia_server.services.auth import password_reset as reset_service
from openlia_server.services.auth.errors import AuthError

# State-changing admin endpoints share one per-admin sliding window, mirroring
# the per-IP/per-email windows the auth router applies (rate_limit.LIMITS). The
# limiter is imported read-only; rate_limit.py owns the window primitive.
ADMIN_WRITE_LIMIT = 30
ADMIN_WRITE_WINDOW_SECONDS = 60


class CreateInviteIn(BaseModel):
    label: str | None = None
    max_uses: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None


class SetRoleIn(BaseModel):
    is_admin: bool


def _build_register_url(raw_token: str) -> str:
    """Fully-qualified register URL from OPENLIA_PUBLIC_URL, else a relative path.

    Mirrors cli.py's read of OPENLIA_PUBLIC_URL. When unset the caller (browser)
    resolves the relative path against its own origin.
    """
    base = os.environ.get("OPENLIA_PUBLIC_URL")
    if base:
        return f"{base.rstrip('/')}/register?invite={raw_token}"
    return f"/register?invite={raw_token}"


class DirectResetIn(BaseModel):
    new_password: str | None = None


class DirectResetOut(BaseModel):
    temporary_password: str


def build_admin_router(*, db_session_factory: Callable[[], DBSession]) -> APIRouter:
    router = APIRouter(prefix="/admin")
    require_admin = build_require_active_admin(
        db_session_factory=db_session_factory, mode="company"
    )
    session_dep = make_session_dependency(db_session_factory)

    def _throttle_write(admin_id: str) -> None:
        if not limiter().check_and_tick(
            f"admin_write:{admin_id}",
            limit=ADMIN_WRITE_LIMIT,
            window_seconds=ADMIN_WRITE_WINDOW_SECONDS,
        ):
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "message": "Too many requests."},
            )

    @router.get("/invites")
    def list_invites(admin=require_admin, db: DBSession = Depends(session_dep)):
        rows = list(
            db.execute(select(SignupInvite).order_by(SignupInvite.created_at.desc())).scalars()
        )
        return [
            {
                "id": r.id,
                "label": r.label,
                "use_count": r.use_count,
                "max_uses": r.max_uses,
                "expires_at": r.expires_at,
                "revoked_at": r.revoked_at,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    @router.post("/invites", status_code=201)
    def create_invite(
        body: CreateInviteIn,
        admin=require_admin,
        db: DBSession = Depends(session_dep),
    ):
        _throttle_write(admin.id)
        raw_token = tokens.generate_opaque_token()
        invite = SignupInvite(
            id=str(uuid.uuid4()),
            token_hash=tokens.hash_token(raw_token),
            label=body.label,
            max_uses=body.max_uses,
            use_count=0,
            expires_at=body.expires_at,
            created_by_user_id=admin.id,
            created_at=datetime.now(UTC),
        )
        db.add(invite)
        db.flush()
        db.refresh(invite)
        return {
            "id": invite.id,
            "token": raw_token,
            "label": invite.label,
            "register_url": _build_register_url(raw_token),
        }

    @router.post("/invites/{invite_id}/revoke", status_code=204)
    def revoke_invite(
        invite_id: str,
        admin=require_admin,
        db: DBSession = Depends(session_dep),
    ):
        _throttle_write(admin.id)
        invite = db.get(SignupInvite, invite_id)
        if invite is None:
            raise HTTPException(status_code=404)
        if invite.revoked_at is None:
            invite.revoked_at = datetime.now(UTC)
        return Response(status_code=204)

    @router.get("/users")
    def list_users(admin=require_admin, db: DBSession = Depends(session_dep)):
        rows = list(db.execute(select(User).order_by(User.created_at.desc())).scalars())
        return [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "is_admin": u.is_admin,
                "is_disabled": u.is_disabled,
                "last_login_at": u.last_login_at,
                "must_change_password": u.must_change_password,
            }
            for u in rows
        ]

    @router.post("/users/{user_id}/disable", status_code=204)
    def disable_user(
        user_id: str,
        admin=require_admin,
        db: DBSession = Depends(session_dep),
    ):
        _throttle_write(admin.id)
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404)
        # Never lock the instance out. Disabling the last active admin, or an
        # admin disabling their own account (revoke_all_sessions kills their
        # live session), would leave only CLI recovery.
        if user.is_admin and not user.is_disabled and admin_roles.count_active_admins(db) <= 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "last_admin",
                    "message": "Cannot disable the last remaining admin.",
                },
            )
        if user.id == admin.id:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "cannot_disable_self",
                    "message": "You cannot disable your own account.",
                },
            )
        user.is_disabled = True
        user.updated_at = datetime.now(UTC)
        sessions.revoke_all_sessions(db, user_id=user.id)
        return Response(status_code=204)

    @router.post("/users/{user_id}/enable", status_code=204)
    def enable_user(
        user_id: str,
        admin=require_admin,
        db: DBSession = Depends(session_dep),
    ):
        _throttle_write(admin.id)
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404)
        user.is_disabled = False
        user.updated_at = datetime.now(UTC)
        return Response(status_code=204)

    @router.post("/users/{user_id}/role")
    def set_user_role(
        user_id: str,
        body: SetRoleIn,
        admin=require_admin,
        db: DBSession = Depends(session_dep),
    ):
        _throttle_write(admin.id)
        try:
            user = admin_roles.set_admin_flag(db, user_id=user_id, is_admin=body.is_admin)
        except admin_roles.UserNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": exc.code, "message": str(exc)}
            ) from exc
        except admin_roles.LastAdminError as exc:
            raise HTTPException(
                status_code=409, detail={"code": exc.code, "message": str(exc)}
            ) from exc
        return {"id": user.id, "is_admin": user.is_admin}

    @router.post("/users/{user_id}/reset-password", response_model=DirectResetOut)
    def direct_reset(
        user_id: str,
        body: DirectResetIn,
        admin=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> DirectResetOut:
        _throttle_write(admin.id)
        try:
            password = reset_service.admin_direct_reset(
                db,
                user_id=user_id,
                new_password=body.new_password,
                admin_user_id=admin.id,
            )
        except AuthError as exc:
            raise HTTPException(
                status_code=400, detail={"code": exc.code, "message": str(exc)}
            ) from exc
        return DirectResetOut(temporary_password=password)

    @router.get("/password-reset-requests")
    def list_reset_requests(admin=require_admin, db: DBSession = Depends(session_dep)):
        rows = list(
            db.execute(
                select(PasswordResetRequest).where(PasswordResetRequest.status == "pending")
            ).scalars()
        )
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "status": r.status,
                "requested_at": r.requested_at,
                "requested_ip": r.requested_ip,
            }
            for r in rows
        ]

    @router.post("/password-reset-requests/{request_id}/approve")
    def approve_reset_request(
        request_id: str,
        admin=require_admin,
        db: DBSession = Depends(session_dep),
    ):
        _throttle_write(admin.id)
        try:
            raw = reset_service.approve_request(db, request_id=request_id, admin_user_id=admin.id)
        except AuthError as exc:
            raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
        return {"reset_token": raw}

    @router.post("/password-reset-requests/{request_id}/reject", status_code=204)
    def reject_reset_request(
        request_id: str,
        admin=require_admin,
        db: DBSession = Depends(session_dep),
    ):
        _throttle_write(admin.id)
        try:
            reset_service.reject_request(db, request_id=request_id, admin_user_id=admin.id)
        except AuthError as exc:
            raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
        return Response(status_code=204)

    return router
