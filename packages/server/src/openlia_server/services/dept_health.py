"""Server-side department-health cache + invalidation (Phase 10 Task 10.2).

Maintains a `dict[str, DepartmentHealth]` keyed by department id on
`app.state.dept_health`. The map is populated at startup and recomputed
whenever a connector or runner-spec mutation could flip a dept's status.

The pure derivation lives in `openlia.departments.health.check_dept_health`;
this module just reads the persisted ORM rows and feeds them in.
"""

from __future__ import annotations

import logging

from openlia.departments import _REGISTRY
from openlia.departments.health import DepartmentHealth, check_dept_health
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import Connector

log = logging.getLogger(__name__)


def compute_all(session: Session) -> dict[str, DepartmentHealth]:
    """Re-derive `DepartmentHealth` for every registered department."""
    connectors = list(session.execute(select(Connector)).scalars().all())
    out: dict[str, DepartmentHealth] = {}
    for dept in _REGISTRY.values():
        out[dept.name] = check_dept_health(
            dept,
            validated_connectors=connectors,
        )
    return out


def serialize(health: DepartmentHealth) -> dict:
    """JSON-serializable shape for the GET endpoint."""
    dept = _REGISTRY.get(health.department_id)
    required_cats: list[str] = []
    optional_cats: list[str] = []
    any_of: list[list[str]] = []
    if dept is not None:
        required_cats = [c.value for c in getattr(dept, "required_categories", ())]
        optional_cats = [c.value for c in getattr(dept, "optional_categories", ())]
        any_of = [[c.value for c in group] for group in getattr(dept, "required_any_of", ()) or ()]
    return {
        "department_id": health.department_id,
        "status": health.status,
        "reason": health.reason,
        "missing_categories": [c.value for c in health.missing_categories],
        "required_categories": required_cats,
        "required_any_of": any_of,
        "unsatisfied_any_of": [[c.value for c in group] for group in health.unsatisfied_any_of],
        "optional_categories": optional_cats,
        "satisfied_categories": [c.value for c in health.satisfied_categories],
    }


def is_disabled(
    state_map: dict[str, DepartmentHealth] | None, dept_id: str
) -> tuple[bool, str | None]:
    """Return `(disabled, reason)` for `dept_id` against a cache map.

    A missing entry is treated as not-disabled so depts that haven't been
    computed yet (e.g. tests bypassing the lifespan) don't 409 spuriously.
    """
    if not state_map:
        return False, None
    health = state_map.get(dept_id)
    if health is None:
        return False, None
    if health.status == "disabled":
        return True, health.reason
    return False, None
