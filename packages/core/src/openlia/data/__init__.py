"""Data provider adapter system.

Public surface: errors, types, adapter base, resolver, adapter registry,
manifest helpers. Catalog, dispatch, review, python_providers, and
sentiment subpackages are deferred placeholders — importable but their
top-level callables raise NotImplementedError.
"""

from openlia.data.adapters import ADAPTERS
from openlia.data.base import ProviderAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataProviderError,
    DataSourceError,
    RateLimitError,
)
from openlia.data.manifest import (
    DepartmentManifest,
    Requirement,
    RequirementsManifest,
    RequirementTier,
    load_manifest,
    load_manifest_from_path,
)
from openlia.data.resolver import (
    ResolvedProvider,
    resolve_provider_for_capability,
    resolve_tools_for_requirements,
)
from openlia.data.types import (
    ProviderCategory,
    ProviderEntry,
    ProviderMode,
    ToolResult,
)

__all__ = [
    "ADAPTERS",
    "AuthenticationError",
    "DataNotAvailable",
    "DataProviderError",
    "DataSourceError",
    "DepartmentManifest",
    "ProviderAdapter",
    "ProviderCategory",
    "ProviderEntry",
    "ProviderMode",
    "RateLimitError",
    "Requirement",
    "RequirementTier",
    "RequirementsManifest",
    "ResolvedProvider",
    "ToolResult",
    "load_manifest",
    "load_manifest_from_path",
    "resolve_provider_for_capability",
    "resolve_tools_for_requirements",
]
