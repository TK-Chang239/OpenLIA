"""CRUD for the per-(user, department) model preference."""

from __future__ import annotations

from sqlalchemy.orm import Session

from openlia_server.db.models.config import UserDepartmentModelPref


def get(db: Session, *, user_id: str, department_id: str) -> str | None:
    row = db.get(UserDepartmentModelPref, (user_id, department_id))
    return row.model_id if row is not None else None


def upsert(db: Session, *, user_id: str, department_id: str, model_id: str) -> None:
    row = db.get(UserDepartmentModelPref, (user_id, department_id))
    if row is None:
        db.add(
            UserDepartmentModelPref(
                user_id=user_id,
                department_id=department_id,
                model_id=model_id,
            )
        )
    else:
        row.model_id = model_id
    db.flush()


def clear(db: Session, *, user_id: str, department_id: str) -> None:
    row = db.get(UserDepartmentModelPref, (user_id, department_id))
    if row is not None:
        db.delete(row)
        db.flush()
