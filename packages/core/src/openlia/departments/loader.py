"""Loader for per-department artifacts.

Reads sibling files next to each `<dept>.py`:
  - `<dept>.routing_context.md` — markdown copy injected into the
    runtime router's prompt template (spec §5.3). Required.
  - `<dept>.needs.yaml` — connector need declarations used by the
    spec-approval flow (spec §5.4). Optional; absent / empty for
    chat-flow depts that declare no needs.

`load_routing_context` is used by the runtime router.
`load_needs` is used by the connector spec-approval/save flow
(`resolver_save_flow._load_need`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from openlia.connectors.types import NeedParameter, RunnerNeed
from openlia.departments import _REGISTRY
from openlia.departments.base import Department

_DEPT_DIR = Path(__file__).parent


def _routing_context_path(department_id: str) -> Path:
    return _DEPT_DIR / f"{department_id}.routing_context.md"


def _needs_path(department_id: str) -> Path:
    return _DEPT_DIR / f"{department_id}.needs.yaml"


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


def load_needs(department_id: str) -> list[RunnerNeed]:
    """Read `<dept>.needs.yaml` and parse it into a list of `RunnerNeed`.

    Returns `[]` when the file does not exist — the dept is chat-flow
    only and has no deterministic-runner needs to declare. Raises
    `ValueError` when the file exists but the schema is malformed.
    """
    path = _needs_path(department_id)
    if not path.exists():
        return []

    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping")

    declared_dept = raw.get("department")
    if declared_dept is not None and declared_dept != department_id:
        raise ValueError(
            f"{path}: declared department '{declared_dept}' "
            f"does not match file id '{department_id}'"
        )

    needs_raw = raw.get("needs", [])
    if not isinstance(needs_raw, list):
        raise ValueError(f"{path}: 'needs' must be a list")

    out: list[RunnerNeed] = []
    for entry in needs_raw:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: each need entry must be a mapping")
        try:
            need_id = entry["id"]
            description = entry["description"]
            shape = entry["shape"]
        except KeyError as exc:
            raise ValueError(f"{path}: need entry missing required field {exc}") from exc

        params_raw = entry.get("parameters", []) or []
        if not isinstance(params_raw, list):
            raise ValueError(f"{path}: '{need_id}.parameters' must be a list")

        params: list[NeedParameter] = []
        for p in params_raw:
            if not isinstance(p, dict):
                raise ValueError(f"{path}: '{need_id}.parameters' entries must be mappings")
            try:
                params.append(
                    NeedParameter(
                        name=p["name"],
                        description=p["description"],
                        type=p["type"],
                        required=bool(p["required"]),
                        default=p.get("default"),
                    )
                )
            except KeyError as exc:
                raise ValueError(
                    f"{path}: parameter for '{need_id}' missing required field {exc}"
                ) from exc

        canonical_raw = entry.get("canonical_keys")
        canonical_keys: dict[str, str] | None
        shape_str = str(shape)
        if canonical_raw is None:
            if shape_str == "list[dict]":
                raise ValueError(
                    f"{path}: '{need_id}' has shape 'list[dict]' but no "
                    f"'canonical_keys' map; declare the canonical key set the "
                    f"dept-side adapter expects."
                )
            canonical_keys = None
        else:
            if shape_str != "list[dict]":
                raise ValueError(
                    f"{path}: '{need_id}' has shape '{shape_str}' but declares "
                    f"'canonical_keys'; canonical_keys is only valid for "
                    f"shape 'list[dict]'."
                )
            if not isinstance(canonical_raw, dict) or not canonical_raw:
                raise ValueError(
                    f"{path}: '{need_id}.canonical_keys' must be a non-empty "
                    f"mapping of str -> str type-hint."
                )
            canonical_keys = {}
            for k, v in canonical_raw.items():
                if not isinstance(k, str) or not k.strip():
                    raise ValueError(
                        f"{path}: '{need_id}.canonical_keys' has a non-string or empty key: {k!r}"
                    )
                if not isinstance(v, str) or not v.strip():
                    raise ValueError(
                        f"{path}: '{need_id}.canonical_keys[{k}]' must be a "
                        f"non-empty type-hint string."
                    )
                canonical_keys[k] = v

        out.append(
            RunnerNeed(
                id=str(need_id),
                description=str(description).strip(),
                parameters=params,
                shape=shape_str,
                canonical_keys=canonical_keys,
            )
        )
    return out


def all_departments() -> list[Department]:
    """Return every registered department instance.

    Provides a stable iteration order over the dept registry, used by
    the drift-safety tests and by health-check sweeps.
    """
    return list(_REGISTRY.values())
