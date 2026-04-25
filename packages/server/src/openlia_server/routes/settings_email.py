"""Route for PATCH /settings/email with current-password confirmation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services.auth.passwords import verify_password


class EmailChangeIn(BaseModel):
    new_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    current_password: str


def build_settings_email_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.patch("/email")
    def patch_email(
        payload: EmailChangeIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, str]:
        # Re-fetch user in this session so mutations are tracked and committed.
        db_user = db.get(User, user.id)
        if db_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated"
            )
        if not verify_password(db_user.password_hash, payload.current_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_credentials", "message": "Current password is incorrect."},
            )
        clash = db.query(User).filter_by(email=payload.new_email).first()
        if clash and clash.id != db_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "email_in_use", "message": "Email already in use."},
            )
        db_user.email = payload.new_email
        db.flush()
        return {"email": db_user.email}

    return router
