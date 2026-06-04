"""Loader for per-department artifacts.

Reads sibling files next to each `<dept>.py`:
  - `<dept>.routing_context.md` — markdown copy injected into the
    runtime router's prompt template (spec §5.3). Required.

`load_routing_context` is used by the runtime router.
"""

from __future__ import annotations

from pathlib import Path

from openlia.departments import _REGISTRY
from openlia.departments.base import Department

_DEPT_DIR = Path(__file__).parent


def _routing_context_path(department_id: str) -> Path:
    return _DEPT_DIR / f"{department_id}.routing_context.md"


def load_routing_context(department_id: str) -> str:
    """Read `<dept>.routing_context.md` from the departments package.

    Raises `FileNotFoundError` if the dept is not registered or the
    routing-context markdown is missing. The router prompt template
    requires a non-empty document — a missing file is a drift bug,
    not a graceful-degrade case, so we fail loudly.
    """
    path = _routing_context_path(department_id)
    if not path.exists():
        raise FileNotFoundError(
            f"Routing context not found for department '{department_id}': {path}"
        )
    return path.read_text(encoding="utf-8")


def all_departments() -> list[Department]:
    """Return every registered department instance.

    Provides a stable iteration order over the dept registry, used by
    the drift-safety tests and by health-check sweeps.
    """
    return list(_REGISTRY.values())
