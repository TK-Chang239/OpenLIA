"""ArtifactType registry with boot-time DAG validation.

Per schema-and-skills §2 and §4.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from .enums import Fidelity

_YAML_PATH = Path(__file__).parent / "artifact_types.yaml"


class ArtifactType(BaseModel):
    """One registered artifact type."""

    name: str
    description: str = ""
    fidelity: dict[Fidelity, str]  # fidelity level -> description of that render
    depends_on: list[str] = []  # names of ArtifactTypes that must be produced first


def _load_yaml(path: Path) -> list[dict[str, Any]]:
    with path.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "artifact_types" not in data:
        raise ValueError(f"artifact_types.yaml missing top-level 'artifact_types' key: {path}")
    return data["artifact_types"]  # type: ignore[return-value]


def _parse_entry(raw: dict[str, Any]) -> ArtifactType:
    name = raw["name"]
    fidelity_raw: dict[str, str] = raw.get("fidelity", {})
    fidelity: dict[Fidelity, str] = {}
    for level_str, desc in fidelity_raw.items():
        try:
            fidelity[Fidelity(level_str)] = desc
        except ValueError as exc:
            raise ValueError(
                f"artifact_types.yaml entry {name!r}: unknown fidelity level {level_str!r}"
            ) from exc
    return ArtifactType(
        name=name,
        description=raw.get("description", ""),
        fidelity=fidelity,
        depends_on=raw.get("depends_on", []),
    )


class ArtifactTypeRegistry:
    """Loads artifact_types.yaml and exposes lookup + DAG validation."""

    def __init__(self, path: Path = _YAML_PATH) -> None:
        self._types: dict[str, ArtifactType] = {}
        entries = _load_yaml(path)
        for raw in entries:
            at = _parse_entry(raw)
            if at.name in self._types:
                raise ValueError(f"Duplicate artifact type in registry: {at.name!r}")
            self._types[at.name] = at

    def get(self, name: str) -> ArtifactType | None:
        return self._types.get(name)

    def list_all(self) -> list[ArtifactType]:
        return list(self._types.values())

    def validate_dag(self) -> None:
        """Raise ValueError with cycle path if depends_on graph contains a cycle.

        Uses DFS with a recursion stack (white-grey-black colouring).
        Per schema-and-skills §4, validation runs at registry boot.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        colour: dict[str, int] = {name: WHITE for name in self._types}
        path: list[str] = []

        def visit(node: str) -> None:
            colour[node] = GREY
            path.append(node)
            for dep in self._types[node].depends_on:
                if dep not in self._types:
                    raise ValueError(
                        f"ArtifactType {node!r} depends_on {dep!r} which is not in the registry"
                    )
                if colour[dep] == GREY:
                    # cycle detected — report full path
                    cycle_start = path.index(dep)
                    cycle = [*path[cycle_start:], dep]
                    raise ValueError(f"Cycle detected in ArtifactType DAG: {' -> '.join(cycle)}")
                if colour[dep] == WHITE:
                    visit(dep)
            path.pop()
            colour[node] = BLACK

        for name in list(self._types):
            if colour[name] == WHITE:
                visit(name)


# Module-level singleton — loaded once at import time.
# validate_dag() called immediately so any cycle fails at boot.
_registry = ArtifactTypeRegistry()
_registry.validate_dag()
