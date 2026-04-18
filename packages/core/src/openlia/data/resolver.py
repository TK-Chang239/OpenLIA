"""Deterministic capability resolver.

Given a list of configured provider entries and a capability string, returns
the highest-priority enabled provider whose adapter declares support.

Priority ordering: LOWER integer = HIGHER priority (convention matches
web_search_providers.priority default=100 in database-design.md). Ties are
broken by list order (kept stable via sorted(...)'s stability guarantee).

No LLM inference — this is a pure set-membership lookup. The catalog/review
flow described in data-provider-design.md is a later addition that will
augment (not replace) this resolver.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from openlia.data.base import ProviderAdapter
from openlia.data.manifest.types import Requirement
from openlia.data.types import ProviderEntry


@dataclass(frozen=True, slots=True)
class ResolvedProvider:
    """The (entry, adapter class) pair that covers one capability."""

    capability: str
    entry: ProviderEntry
    adapter_cls: type[ProviderAdapter]


def resolve_provider_for_capability(
    *,
    capability: str,
    entries: Iterable[ProviderEntry],
    adapters: Mapping[str, type[ProviderAdapter]],
) -> ResolvedProvider | None:
    """Return the winning provider for `capability`, or None if none cover it."""
    candidates: list[tuple[int, ProviderEntry, type[ProviderAdapter]]] = []
    for entry in entries:
        if not entry.is_enabled:
            continue
        adapter_cls = adapters.get(entry.kind)
        if adapter_cls is None:
            continue
        if capability not in adapter_cls.capabilities:
            continue
        candidates.append((entry.priority, entry, adapter_cls))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[0])
    _, entry, adapter_cls = candidates[0]
    return ResolvedProvider(
        capability=capability,
        entry=entry,
        adapter_cls=adapter_cls,
    )


def resolve_tools_for_requirements(
    *,
    requirements: Iterable[Requirement],
    entries: Iterable[ProviderEntry],
    adapters: Mapping[str, type[ProviderAdapter]],
) -> tuple[list[ResolvedProvider], list[str]]:
    """Resolve every requirement; return (resolved, unmet_types)."""
    entries_list = list(entries)  # single-pass safety
    resolved: list[ResolvedProvider] = []
    unmet: list[str] = []
    for req in requirements:
        r = resolve_provider_for_capability(
            capability=req.type,
            entries=entries_list,
            adapters=adapters,
        )
        if r is None:
            unmet.append(req.type)
        else:
            resolved.append(r)
    return resolved, unmet
