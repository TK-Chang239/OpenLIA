"""Department data requirements manifest.

A manifest is a union of every department's basic + advanced data needs,
expressed as string `type` fields matching adapter capabilities. Loaded once
at startup from `requirements.yaml` bundled with the package.
"""

from openlia.data.manifest.loader import (
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    load_manifest_from_path,
)
from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementsManifest,
    RequirementTier,
)

__all__ = [
    "DEFAULT_MANIFEST_PATH",
    "DepartmentManifest",
    "Requirement",
    "RequirementTier",
    "RequirementsManifest",
    "load_manifest",
    "load_manifest_from_path",
]
