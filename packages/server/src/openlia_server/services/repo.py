"""CRUD for repo_items — saved reports, scoped to a single user."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import RepoItem, Report


def save_to_repo(db: Session, *, user_id: str, report_id: str) -> RepoItem:
    existing = db.execute(
        select(RepoItem).where(RepoItem.user_id == user_id, RepoItem.report_id == report_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    if db.get(Report, report_id) is None:
        raise LookupError(f"report {report_id} not found")
    import uuid

    item = RepoItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        report_id=report_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def unsave_from_repo(db: Session, *, user_id: str, report_id: str) -> None:
    db.query(RepoItem).filter(RepoItem.user_id == user_id, RepoItem.report_id == report_id).delete()
    db.commit()


def list_items(db: Session, *, user_id: str) -> list[RepoItem]:
    stmt = select(RepoItem).where(RepoItem.user_id == user_id).order_by(RepoItem.created_at.desc())
    return list(db.execute(stmt).scalars())
