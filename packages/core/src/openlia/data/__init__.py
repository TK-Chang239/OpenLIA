"""Data provider adapter system.

Public surface kept minimal in Plan 3: errors, types, adapter base, resolver.
Catalog, dispatch, review, and expansion layers are added in later plans.
"""

from openlia.data.errors import (
    DataNotAvailable,
    DataProviderError,
    DataSourceError,
    RateLimitError,
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
    "ProviderCategory",
    "ProviderEntry",
    "ProviderMode",
    "RateLimitError",
    "ToolResult",
]
