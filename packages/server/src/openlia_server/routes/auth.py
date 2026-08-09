"""Company-mode auth HTTP surface.

Routes are mounted only when `OPENLIA_MODE == company`. The shared app factory
(see `app.py`) gates inclusion. In personal mode these paths return 404.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.auth import COOKIE_NAME, build_require_auth
from openlia_server.middleware.rate_limit import LIMITS, limiter
from openlia_server.services.auth import login as login_service
from openlia_server.services.auth import password_reset as reset_service
from openlia_server.services.auth import registration, sessions, signup_policy
from openlia_server.services.auth.errors import AuthError


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    display_name: str | None = Field(default=None, max_length=128)
    invite_token: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    persistent: bool = False


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConsumeIn(BaseModel):
    token: str
    new_password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


def build_auth_router(*, db_session_factory: Callable[[], DBSession]) -> APIRouter:
    router = APIRouter(prefix="/auth")
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode="company")
    session_dep = make_session_dependency(db_session_factory)

    def _cookie_secure() -> bool:
        # Default to true in company mode (production-safe), false otherwise so
        # TestClient and local personal mode work over http://testserver.
        # Explicit OPENLIA_COOKIE_SECURE overrides either default.
        override = os.environ.get("OPENLIA_COOKIE_SECURE")
        if override is not None:
            return override.lower() in ("1", "true", "yes")
        return os.environ.get("OPENLIA_MODE", "personal").lower() == "company"

    def _ip(request: Request) -> str | None:
        if os.environ.get("OPENLIA_TRUST_PROXY_HEADERS", "false").lower() in (
            "1",
            "true",
            "yes",
        ):
            fwd = request.headers.get("x-forwarded-for")
            if fwd:
                return fwd.split(",")[0].strip()
        return request.client.host if request.client else None

    @router.post("/register", status_code=201)
    def register(
        body: RegisterIn,
        request: Request,
        response: Response,
        db: DBSession = Depends(session_dep),
    ):
        ip = _ip(request)
        rl_limit, rl_window = LIMITS["register_ip"]
        if not limiter().check_and_tick(
            f"register_ip:{ip}", limit=rl_limit, window_seconds=rl_window
        ):
            return JSONResponse(
                status_code=429,
                content={"code": "rate_limited", "message": "Too many requests."},
            )

        try:
            user = registration.register(
                db,
                email=body.email,
                password=body.password,
                display_name=body.display_name,
                invite_token=body.invite_token,
            )
        except AuthError as exc:
            return JSONResponse(
                status_code=_status_for(exc.code),
                content={"code": exc.code, "message": str(exc)},
            )

        created = sessions.create_session(
            db,
            user_id=user.id,
            persistent=False,
            user_agent=request.headers.get("user-agent"),
            ip_address=ip,
        )
        _set_cookie(response, created.raw_token, persistent=False, secure=_cookie_secure())
        return {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_admin": user.is_admin,
            "must_change_password": user.must_change_password,
        }

    @router.post("/login")
    def login(
        body: LoginIn,
        request: Request,
        response: Response,
        openlia_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
        db: DBSession = Depends(session_dep),
    ):
        ip = _ip(request)
        lim = limiter()
        ip_limit, ip_window = LIMITS["login_ip"]
        email_limit, email_window = LIMITS["login_email"]
        if not lim.check_and_tick(f"login_ip:{ip}", limit=ip_limit, window_seconds=ip_window):
            return JSONResponse(status_code=429, content={"code": "rate_limited"})
        if not lim.check_and_tick(
            f"login_email:{body.email.lower()}",
            limit=email_limit,
            window_seconds=email_window,
        ):
            return JSONResponse(status_code=429, content={"code": "rate_limited"})

        try:
            auth = login_service.authenticate(
                db,
                email=body.email,
                password=body.password,
                ip_address=ip,
                user_agent=request.headers.get("user-agent"),
            )
        except login_service.AccountLockedError as exc:
            return JSONResponse(
                status_code=423,
                content={
                    "code": "account_locked",
                    "message": "Account is temporarily locked.",
                    "metadata": {"retry_after_seconds": exc.retry_after_seconds},
                },
            )
        except AuthError as exc:
            return JSONResponse(
                status_code=_status_for(exc.code),
                content={"code": exc.code, "message": str(exc)},
            )

        # Session-fixation defense: revoke any cookie the caller arrived with
        # before minting a new one. AccountManagementSpec §13.2.
        if openlia_session:
            prior = sessions.validate_session(db, openlia_session)
            if prior is not None:
                sessions.revoke_session(db, prior.session.id)

        created = sessions.create_session(
            db,
            user_id=auth.user.id,
            persistent=body.persistent,
            user_agent=request.headers.get("user-agent"),
            ip_address=ip,
        )
        _set_cookie(
            response,
            created.raw_token,
            persistent=body.persistent,
            secure=_cookie_secure(),
        )
        return {
            "user_id": auth.user.id,
            "email": auth.user.email,
            "display_name": auth.user.display_name,
            "is_admin": auth.user.is_admin,
            "must_change_password": auth.must_change_password,
        }

    @router.post("/logout", status_code=204)
    def logout(
        response: Response,
        openlia_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
        db: DBSession = Depends(session_dep),
    ):
        if openlia_session:
            validated = sessions.validate_session(db, openlia_session)
            if validated is not None:
                sessions.revoke_session(db, validated.session.id)
        response.delete_cookie(COOKIE_NAME, path="/")
        return Response(status_code=204)

    @router.post("/logout-all", status_code=204)
    def logout_all(
        response: Response,
        user=require_auth,
        db: DBSession = Depends(session_dep),
    ):
        sessions.revoke_all_sessions(db, user_id=user.id)
        response.delete_cookie(COOKIE_NAME, path="/")
        return Response(status_code=204)

    @router.get("/sessions")
    def list_sessions(
        user=require_auth,
        openlia_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
        db: DBSession = Depends(session_dep),
    ):
        current_id: str | None = None
        if openlia_session:
            validated = sessions.validate_session(db, openlia_session)
            if validated is not None:
                current_id = validated.session.id
        rows = sessions.list_active_sessions(db, user_id=user.id)
        return {
            "sessions": [
                {
                    "id": s.id,
                    "created_at": s.created_at.isoformat(),
                    "last_seen_at": s.last_seen_at.isoformat(),
                    "expires_at": s.expires_at.isoformat(),
                    "user_agent": s.user_agent,
                    "ip_address": s.ip_address,
                    "current": s.id == current_id,
                }
                for s in rows
            ]
        }

    @router.delete("/sessions/{session_id}", status_code=204)
    def revoke_one_session(
        session_id: str,
        user=require_auth,
        db: DBSession = Depends(session_dep),
    ):
        # Ownership is enforced in the service; revoking a session the caller
        # does not own (or one already gone) is a no-op that still returns 204.
        sessions.revoke_session_for_user(db, user_id=user.id, session_id=session_id)
        return Response(status_code=204)

    @router.get("/session")
    def get_session(user=require_auth):
        return {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_admin": user.is_admin,
            "must_change_password": user.must_change_password,
        }

    @router.get("/signup-policy")
    def get_signup_policy(db: DBSession = Depends(session_dep)):
        policy = signup_policy.get_policy(db)
        # Pre-wizard: signup_policy row not yet seeded — registration is closed.
        mode = policy.mode if policy is not None else "closed"
        return {
            "mode": mode,
            "invite_required": mode == "invite_only",
        }

    @router.post("/password-reset/request")
    def password_reset_request(
        body: PasswordResetRequestIn,
        request: Request,
        db: DBSession = Depends(session_dep),
    ):
        ip = _ip(request)
        rl_limit, rl_window = LIMITS["password_reset_ip"]
        if not limiter().check_and_tick(
            f"password_reset_ip:{ip}", limit=rl_limit, window_seconds=rl_window
        ):
            return JSONResponse(status_code=429, content={"code": "rate_limited"})

        reset_service.request_reset(db, email=body.email, ip_address=ip)
        return {"status": "ok"}

    @router.post("/password-reset/consume")
    def password_reset_consume(
        body: PasswordResetConsumeIn,
        db: DBSession = Depends(session_dep),
    ):
        try:
            reset_service.consume_token(db, token=body.token, new_password=body.new_password)
        except AuthError as exc:
            return JSONResponse(
                status_code=_status_for(exc.code),
                content={"code": exc.code, "message": str(exc)},
            )
        return {"status": "ok"}

    @router.post("/change-password")
    def change_password(
        body: ChangePasswordIn,
        user=require_auth,
        db: DBSession = Depends(session_dep),
    ):
        try:
            reset_service.change_password(
                db,
                user_id=user.id,
                current_password=body.current_password,
                new_password=body.new_password,
            )
        except AuthError as exc:
            return JSONResponse(
                status_code=_status_for(exc.code),
                content={"code": exc.code, "message": str(exc)},
            )
        return {"status": "ok"}

    return router


def _set_cookie(response: Response, raw_token: str, *, persistent: bool, secure: bool) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        max_age=int(sessions.PERSISTENT_TTL.total_seconds()) if persistent else None,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


# `must_change_password` is intentionally absent. It is a non-fatal flag on
# /auth/login and /auth/session response bodies; the 403 enforcement lives in
# `middleware.auth.build_require_active_user`, not in any AuthError raised
# from this module.
_STATUS_MAP = {
    "invalid_credentials": 401,
    "account_disabled": 403,
    "account_locked": 423,
    "rate_limited": 429,
    "signup_closed": 403,
    "invite_required": 403,
    "invite_invalid": 403,
    "weak_password": 400,
    "email_in_use": 409,
    "email_domain_not_allowed": 403,
    "registration_failed": 400,
    "token_invalid": 400,
    "token_expired": 410,
}


def _status_for(code: str) -> int:
    return _STATUS_MAP.get(code, 400)
