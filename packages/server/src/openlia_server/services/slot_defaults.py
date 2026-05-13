"""CRUD for `llm_slot_defaults`. Replaces the per-tier default mechanism.

Validates `slot_kind` against {'department', 'system_role'} and `slot_id`
against the registered departments (from `get_registered_department_ids`)
or system roles (from `SYSTEM_ROLE_IDS`).
"""

from __future__ import annotations

from openlia.departments import get_registered_department_ids
from openlia.llm.system_roles import SYSTEM_ROLE_IDS
from sqlalchemy.orm import Session

from openlia_server.db.models.config import LLMSlotDefault


class InvalidSlotError(ValueError):
    pass


_VALID_KINDS = {"department", "system_role"}


def _validate_slot(slot_kind: str, slot_id: str) -> None:
    if slot_kind not in _VALID_KINDS:
        raise InvalidSlotError(f"Unknown slot_kind {slot_kind!r}")
    if slot_kind == "department" and slot_id not in get_registered_department_ids():
        raise InvalidSlotError(f"Unknown department {slot_id!r}")
    if slot_kind == "system_role" and slot_id not in SYSTEM_ROLE_IDS:
        raise InvalidSlotError(f"Unknown system role {slot_id!r}")


def set_slot_default(
    db: Session, *, slot_kind: str, slot_id: str, model_id: str
) -> LLMSlotDefault:
    _validate_slot(slot_kind, slot_id)
    row = db.get(LLMSlotDefault, (slot_kind, slot_id))
    if row is None:
        row = LLMSlotDefault(slot_kind=slot_kind, slot_id=slot_id, model_id=model_id)
        db.add(row)
    else:
        row.model_id = model_id
    db.commit()
    db.refresh(row)
    return row


def get_slot_default_model_id(
    db: Session, slot_kind: str, slot_id: str
) -> str | None:
    row = db.get(LLMSlotDefault, (slot_kind, slot_id))
    return row.model_id if row is not None else None


def delete_slot_default(db: Session, *, slot_kind: str, slot_id: str) -> None:
    row = db.get(LLMSlotDefault, (slot_kind, slot_id))
    if row is not None:
        db.delete(row)
        db.commit()


def list_slot_defaults(db: Session) -> list[LLMSlotDefault]:
    return db.query(LLMSlotDefault).all()


class SlotDefaultsService:
    """Thin wrapper for route handlers that prefer a class API."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, slot_kind: str, slot_id: str) -> str | None:
        return get_slot_default_model_id(self._db, slot_kind, slot_id)

    def set(self, slot_kind: str, slot_id: str, model_id: str) -> LLMSlotDefault:
        return set_slot_default(
            self._db, slot_kind=slot_kind, slot_id=slot_id, model_id=model_id
        )

    def delete(self, slot_kind: str, slot_id: str) -> None:
        delete_slot_default(self._db, slot_kind=slot_kind, slot_id=slot_id)

    def list_all(self) -> list[LLMSlotDefault]:
        return list_slot_defaults(self._db)
