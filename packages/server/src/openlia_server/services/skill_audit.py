from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.safety import LiaGuardrailEvent


def _write(
    sf: Callable[[], DBSession],
    *,
    event_type: str,
    session_id: str | None = None,
    user_id: str | None = None,
    department_id: str | None = None,
    payload: dict[str, Any],
) -> None:
    with sf() as db:
        db.add(
            LiaGuardrailEvent(
                id=str(uuid.uuid4()),
                session_id=session_id,
                user_id=user_id,
                department_id=department_id,
                event_type=event_type,
                category=payload.get("skill_id", "unknown"),
                action_taken="logged",
                user_input_hash=None,
                response_excerpt=None,
                payload_json=payload,
            )
        )
        db.commit()


def record_skill_installed(sf, *, skill_id, scope, user_id, source, version):
    _write(
        sf,
        event_type="skill_installed",
        user_id=user_id,
        payload={"skill_id": skill_id, "scope": scope, "source": source, "version": version},
    )


def record_skill_uninstalled(sf, *, skill_id, scope, user_id):
    _write(
        sf,
        event_type="skill_uninstalled",
        user_id=user_id,
        payload={"skill_id": skill_id, "scope": scope},
    )


def record_skill_toggled(sf, *, skill_id, scope, user_id, enabled):
    et = "skill_enabled" if enabled else "skill_disabled"
    _write(
        sf,
        event_type=et,
        user_id=user_id,
        payload={"skill_id": skill_id, "scope": scope},
    )


def record_skill_loaded(sf, *, skill_id, session_id, user_id, department_id):
    _write(
        sf,
        event_type="skill_loaded",
        session_id=session_id,
        user_id=user_id,
        department_id=department_id,
        payload={"skill_id": skill_id},
    )
