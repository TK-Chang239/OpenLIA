"""Compliance disclaimer acceptance — company-mode storage layer."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.safety import UserDisclaimerAcceptance


def has_accepted(db: Session, *, user_id: str, version: str) -> bool:
    stmt = select(UserDisclaimerAcceptance).where(
        UserDisclaimerAcceptance.user_id == user_id,
        UserDisclaimerAcceptance.disclaimer_version == version,
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def record_acceptance(db: Session, *, user_id: str, version: str) -> None:
    db.flush()
    if has_accepted(db, user_id=user_id, version=version):
        return
    db.add(
        UserDisclaimerAcceptance(
            user_id=user_id,
            disclaimer_version=version,
            accepted_at=datetime.now(UTC),
        )
    )
