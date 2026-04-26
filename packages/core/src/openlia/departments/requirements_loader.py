"""Sibling-YAML loader for department data requirements.

See docs/superpowers/specs/2026-04-26-connector-redesign-design.md §4.3.
Pure: yaml + connector value types only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from openlia.connectors.scope import DepartmentRequirements
from openlia.connectors.types import Category

_VALID_CATEGORIES = {c.value for c in Category}


def load_requirements_yaml(path: Path) -> dict[str, dict[str, Any]]:
    """Parse and validate a sibling *.requirements.yaml file."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    for cat, body in raw.items():
        if cat not in _VALID_CATEGORIES:
            raise ValueError(f"{path}: unknown category '{cat}'")
        if not isinstance(body, dict) or "required" not in body or "description" not in body:
            raise ValueError(f"{path}: '{cat}' must have 'required' and 'description'")
        if not isinstance(body["required"], bool):
            raise ValueError(f"{path}: '{cat}.required' must be bool")
        if not isinstance(body["description"], str) or not body["description"].strip():
            raise ValueError(f"{path}: '{cat}.description' must be non-empty string")
    return raw


def load_department_requirements(department_id: str, yaml_path: Path) -> DepartmentRequirements:
    return DepartmentRequirements(
        department_id=department_id,
        per_category=load_requirements_yaml(yaml_path),
    )
