"""Data provider adapter system.

Public surface kept minimal in Plan 3: errors, types, adapter base, resolver.
Catalog, dispatch, review, and expansion layers are added in later plans.
"""

from openlia.data.base import ProviderAdapter
from openlia.data.errors import (
    DataNotAvailable,
    DataProviderError,
    DataSourceError,
    RateLimitError,
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
    "DataNotAvailable",
    "DataProviderError",
    "DataSourceError",
    "ProviderAdapter",
    "ProviderCategory",
    "ProviderEntry",
    "ProviderMode",
    "RateLimitError",
    "ResolvedProvider",
    "ToolResult",
    "resolve_provider_for_capability",
    "resolve_tools_for_requirements",
]
