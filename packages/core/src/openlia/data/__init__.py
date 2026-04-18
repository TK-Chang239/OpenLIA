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

__all__ = [
    "DataNotAvailable",
    "DataProviderError",
    "DataSourceError",
    "RateLimitError",
]
