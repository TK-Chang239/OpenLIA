"""Dependencies that gate /setup/* routes based on wizard completion and session."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.db.session import get_db_session


def _is_completed(db: Session) -> bool:
    row = db.get(ConfigStore, "wizard.completed")
    if row is None:
        return False
    v = row.value
    if isinstance(v, bool):
        return v
    return (v or "").lower() == "true"


def require_wizard_active(db: Session = Depends(get_db_session)) -> None:
    if _is_completed(db):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"code": "wizard_completed", "message": "Setup has already been completed."},
        )


def require_wizard_session(
    openlia_wizard_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db_session),
) -> None:
    from openlia_server.services import wizard as wizard_svc

    if not wizard_svc.verify_session_token(db, openlia_wizard_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "wizard_session_active",
                "message": "Another setup session is active. Take over to continue here.",
            },
        )
