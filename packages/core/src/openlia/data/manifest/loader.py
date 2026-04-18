"""Load the department requirements manifest from YAML."""

from pathlib import Path

import yaml

from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementsManifest,
    RequirementTier,
)

DEFAULT_MANIFEST_PATH: Path = Path(__file__).parent / "requirements.yaml"


def load_manifest() -> RequirementsManifest:
    """Load the bundled manifest."""
    return load_manifest_from_path(DEFAULT_MANIFEST_PATH)


def load_manifest_from_path(path: Path) -> RequirementsManifest:
    """Load a manifest from an arbitrary path (for tests or overrides)."""
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    departments = [
        DepartmentManifest(
            department=d["department"],
            requirements=tuple(
                Requirement(
                    type=r["type"],
                    description=r["description"],
                    tier=RequirementTier(r["tier"]),
                )
                for r in d.get("requirements", [])
            ),
        )
        for d in raw.get("departments", [])
    ]
    return RequirementsManifest(departments=tuple(departments))
