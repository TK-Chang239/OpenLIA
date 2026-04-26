"""Provider catalog — machine-readable adapter metadata.

`build_catalog()` snapshots the in-process adapter registry into a frozen,
serialization-friendly view of every adapter's `kind`, `category`, and
`capabilities`. The setup-wizard AI review uses this to ground LLM mappings
in what each adapter actually supports (instead of letting the LLM infer
from the provider's name alone).
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from openlia.data.base import ProviderAdapter
from openlia.data.types import ProviderCategory


class CatalogEntry(BaseModel):
    """One row in the provider catalog — a snapshot of an adapter class."""

    model_config = ConfigDict(frozen=True)

    kind: str
    category: ProviderCategory
    capabilities: tuple[str, ...]


class ProviderCatalog(BaseModel):
    """All adapter classes the runtime knows about."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[CatalogEntry, ...]

    def find(self, kind: str) -> CatalogEntry | None:
        for entry in self.entries:
            if entry.kind == kind:
                return entry
        return None

    def kinds(self) -> tuple[str, ...]:
        return tuple(e.kind for e in self.entries)


def build_catalog(
    adapters: Mapping[str, type[ProviderAdapter]] | None = None,
) -> ProviderCatalog:
    """Snapshot adapters into a `ProviderCatalog`.

    Defaults to the live registry. Pass an explicit mapping in tests to
    isolate from registry mutation.
    """
    if adapters is None:
        from openlia.data.adapters import ADAPTERS

        adapters = ADAPTERS
    entries: list[CatalogEntry] = []
    for kind, cls in adapters.items():
        entries.append(
            CatalogEntry(
                kind=kind,
                category=cls.category,
                capabilities=tuple(sorted(cls.capabilities)),
            )
        )
    entries.sort(key=lambda e: e.kind)
    return ProviderCatalog(entries=tuple(entries))


__all__ = ["CatalogEntry", "ProviderCatalog", "build_catalog"]
