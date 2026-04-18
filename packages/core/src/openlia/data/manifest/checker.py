"""Validate a manifest against the union of active provider capabilities.

Plan 3 uses a simple set-membership check: a requirement is satisfied iff
at least one configured provider's adapter declares the requirement type
in its `capabilities` class-var. The future AI-review layer will replace
this with a confidence-scored endpoint match.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from openlia.data.manifest.types import RequirementsManifest, RequirementTier


@dataclass(frozen=True, slots=True)
class UnmetRequirement:
    """One (department, requirement_type) pair that no active provider covers."""

    department: str
    requirement_type: str


def unmet_basic_requirements(
    *,
    manifest: RequirementsManifest,
    active_capabilities: Iterable[str],
) -> list[UnmetRequirement]:
    """Return every basic requirement not covered by `active_capabilities`.

    Order is deterministic: departments in manifest order, requirements in
    declaration order within each department.
    """
    covered = frozenset(active_capabilities)
    unmet: list[UnmetRequirement] = []
    for dm in manifest.departments:
        for req in dm.requirements:
            if req.tier is RequirementTier.BASIC and req.type not in covered:
                unmet.append(
                    UnmetRequirement(
                        department=dm.department,
                        requirement_type=req.type,
                    )
                )
    return unmet
