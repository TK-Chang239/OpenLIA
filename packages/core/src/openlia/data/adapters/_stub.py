"""Deferred-implementation adapter base.

`_StubAdapter` exists so server callers (`routes/settings.py`,
`services/wizard_providers.py`) can do `issubclass(adapter_cls, _StubAdapter)`
to short-circuit live health checks for any future provider whose adapter
has not been implemented yet. As of the 2026-04-25 expansion, no concrete
adapter inherits from this class — every registered `kind` ships with a
real HTTP implementation.
"""

from typing import Any, ClassVar

from openlia.data.base import ProviderAdapter
from openlia.data.errors import DataNotAvailable
from openlia.data.types import ToolResult


class _StubAdapter(ProviderAdapter):
    """Base for adapters whose implementation is deferred."""

    capabilities: ClassVar[frozenset[str]] = frozenset()

    async def fetch(self, capability: str, params: dict[str, Any]) -> ToolResult:
        raise DataNotAvailable(
            provider_kind=self.kind,
            capability=capability,
            reason=f"adapter {self.kind!r} is a registry stub; implementation deferred",
        )

    async def health_check(self) -> bool:
        return False
