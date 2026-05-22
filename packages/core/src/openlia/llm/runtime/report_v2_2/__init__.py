"""report_v2_2 — foundation package for the v2.2 equity research runtime.

Public surface: schema sub-models, enums, verifier issue model, ArtifactType
registry, and the helper registry. Imports from this package are stable after
PR 0.1 merges; downstream helpers bind against these contracts.
"""

from .artifact_types import ArtifactType, ArtifactTypeRegistry
from .enums import Category, Fidelity, VerifierIssueType
from .schema import (
    DirectoryEntry,
    HelperExample,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
)
from .tools.library_helpers import RegisteredHelper, list_helpers
from .verifier_models import VerifierIssue

__all__ = [
    "ArtifactType",
    "ArtifactTypeRegistry",
    "Category",
    "DirectoryEntry",
    "Fidelity",
    "HelperExample",
    "HelperOutput",
    "HelperParam",
    "HelperSchema",
    "MechanicalContract",
    "RegisteredHelper",
    "SelectionGuidance",
    "SkillDocRef",
    "VerifierIssue",
    "VerifierIssueType",
    "list_helpers",
]
