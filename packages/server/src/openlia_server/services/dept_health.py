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

from openlia_server.db.models.connectors import Connector, RunnerCallableSpec

log = logging.getLogger(__name__)


def compute_all(session: Session) -> dict[str, DepartmentHealth]:
    """Re-derive `DepartmentHealth` for every registered department."""
    connectors = list(session.execute(select(Connector)).scalars().all())
    specs = list(session.execute(select(RunnerCallableSpec)).scalars().all())
    out: dict[str, DepartmentHealth] = {}
    for dept in _REGISTRY.values():
        out[dept.name] = check_dept_health(
            dept,
            validated_connectors=connectors,
            runner_specs=specs,
        )
    return out


def serialize(health: DepartmentHealth) -> dict:
    """JSON-serializable shape for the GET endpoint."""
    return {
        "department_id": health.department_id,
        "status": health.status,
        "reason": health.reason,
        "missing_categories": [c.value for c in health.missing_categories],
        "unresolved_needs": list(health.unresolved_needs),
    }
