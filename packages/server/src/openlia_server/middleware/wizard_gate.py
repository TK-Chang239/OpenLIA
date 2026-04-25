"""Dependencies that gate /setup/* routes based on wizard completion and session.

Both gates need a SQLAlchemy Session. We do NOT import the global
`get_db_session` at module scope — that hard-codes a single engine and breaks
factory-based router wiring. Callers must build the gates via
`build_wizard_gate(session_dep)` so the session source matches whichever
factory the router was built with.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from openlia_server.db.models.infrastructure import ConfigStore


def _is_completed(db: Session) -> bool:
    row = db.get(ConfigStore, "wizard.completed")
    if row is None:
        return False
    v = row.value
    if isinstance(v, bool):
        return v
    return (v or "").lower() == "true"


def build_wizard_gate(
    session_dep: Callable[..., object],
) -> tuple[Callable[..., None], Callable[..., None]]:
    """Build (require_wizard_active, require_wizard_session) bound to `session_dep`.

    `session_dep` is the same FastAPI session dependency used by the router
    factory (`make_session_dependency(factory)`). Both returned dependencies
    take their `Session` from it — no global import of `get_db_session` here.
    """

    def require_wizard_active(db: Session = Depends(session_dep)) -> None:
        if _is_completed(db):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "code": "wizard_completed",
                    "message": "Setup has already been completed.",
                },
            )

    def require_wizard_session(
        openlia_wizard_session: str | None = Cookie(default=None),
        db: Session = Depends(session_dep),
    ) -> None:
        from openlia_server.services import wizard as wizard_svc

        if not wizard_svc.verify_session_token(db, openlia_wizard_session):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "wizard_session_active",
                    "message": ("Another setup session is active. Take over to continue here."),
                },
            )

    return require_wizard_active, require_wizard_session
