"""Company-mode auth HTTP surface.

Routes are mounted only when `OPENLIA_MODE == company`. The shared app factory
(see `app.py`) gates inclusion. In personal mode these paths return 404.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.middleware.auth import COOKIE_NAME, build_require_auth
from openlia_server.middleware.rate_limit import LIMITS, limiter
from openlia_server.services.auth import login as login_service
from openlia_server.services.auth import password_reset as reset_service
from openlia_server.services.auth import registration, sessions, signup_policy
from openlia_server.services.auth.errors import AuthError


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=128)
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

    def _cookie_secure() -> bool:
        # Default off so http://testserver (TestClient) works; set OPENLIA_COOKIE_SECURE=true
        # in production behind TLS.
        return os.environ.get("OPENLIA_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")

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
    def register(body: RegisterIn, request: Request, response: Response):
        ip = _ip(request)
        rl_limit, rl_window = LIMITS["register_ip"]
        if not limiter().check_and_tick(
            f"register_ip:{ip}", limit=rl_limit, window_seconds=rl_window
        ):
            return JSONResponse(
                status_code=429,
                content={"code": "rate_limited", "message": "Too many requests."},
            )

        db = db_session_factory()
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
        return {"user_id": user.id, "email": user.email, "display_name": user.display_name}

    @router.post("/login")
    def login(body: LoginIn, request: Request, response: Response):
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

        db = db_session_factory()
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
                    "retry_after_seconds": exc.retry_after_seconds,
                },
            )
        except AuthError as exc:
            return JSONResponse(
                status_code=_status_for(exc.code),
                content={"code": exc.code, "message": str(exc)},
            )

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
    ):
        if openlia_session:
            db = db_session_factory()
            validated = sessions.validate_session(db, openlia_session)
            if validated is not None:
                sessions.revoke_session(db, validated.session.id)
        response.delete_cookie(COOKIE_NAME, path="/")
        return Response(status_code=204)

    @router.post("/logout-all", status_code=204)
    def logout_all(response: Response, user=require_auth):
        db = db_session_factory()
        sessions.revoke_all_sessions(db, user_id=user.id)
        response.delete_cookie(COOKIE_NAME, path="/")
        return Response(status_code=204)

    @router.get("/session")
    def get_session(user=require_auth):
        return {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_admin": user.is_admin,
        }

    @router.get("/signup-policy")
    def get_signup_policy():
        db = db_session_factory()
        policy = signup_policy.get_policy(db)
        return {
            "mode": policy.mode,
            "invite_required": policy.mode == "invite_only",
        }

    @router.post("/password-reset/request")
    def password_reset_request(body: PasswordResetRequestIn, request: Request):
        ip = _ip(request)
        rl_limit, rl_window = LIMITS["password_reset_ip"]
        if not limiter().check_and_tick(
            f"password_reset_ip:{ip}", limit=rl_limit, window_seconds=rl_window
        ):
            return JSONResponse(status_code=429, content={"code": "rate_limited"})

        db = db_session_factory()
        reset_service.request_reset(db, email=body.email, ip_address=ip)
        return {"status": "ok"}

    @router.post("/password-reset/consume")
    def password_reset_consume(body: PasswordResetConsumeIn):
        db = db_session_factory()
        try:
            reset_service.consume_token(db, token=body.token, new_password=body.new_password)
        except AuthError as exc:
            return JSONResponse(
                status_code=_status_for(exc.code),
                content={"code": exc.code, "message": str(exc)},
            )
        return {"status": "ok"}

    @router.post("/change-password")
    def change_password(body: ChangePasswordIn, user=require_auth):
        db = db_session_factory()
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
    "must_change_password": 200,
}


def _status_for(code: str) -> int:
    return _STATUS_MAP.get(code, 400)
