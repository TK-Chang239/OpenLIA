"""Abstract base class every data provider adapter inherits from.

Contract:
- Class attribute `kind`: str matching the `ProviderEntry.kind` used to
  construct the adapter (e.g. "eodhd", "fmp").
- Class attribute `category`: ProviderCategory — which column in
  DataProvidersConfig this adapter fills.
- Class attribute `capabilities`: frozenset[str] — the set of manifest
  requirement `type` strings this adapter can satisfy.
- `fetch(capability, params)`: async coroutine resolving to a ToolResult,
  or raising DataNotAvailable / RateLimitError / DataSourceError.
- `health_check()`: async coroutine returning True iff credentials are
  valid and the service is reachable. Used by the admin "test connection"
  endpoint; never raises — returns False on failure.

Adapters do NOT read the database. The server-side service layer builds the
ProviderEntry (with decrypted api_key) and passes it to the adapter
constructor.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from openlia.data.types import ProviderCategory, ProviderEntry, ToolResult


class ProviderAdapter(ABC):
    """Abstract base for every data provider adapter."""

    kind: ClassVar[str]
    category: ClassVar[ProviderCategory]
    capabilities: ClassVar[frozenset[str]]

    def __init__(self, entry: ProviderEntry) -> None:
        if entry.kind != self.kind:
            raise ValueError(f"kind mismatch: adapter={self.kind!r} entry={entry.kind!r}")
        self.entry = entry

    @abstractmethod
    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        """Fetch data for a capability. Raises typed errors on failure."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True iff the adapter can reach its backend and authenticate."""
