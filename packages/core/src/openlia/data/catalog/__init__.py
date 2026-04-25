"""Provider catalog — DEFERRED.

Per data-provider-design.md §"Provider Catalog", this layer publishes
machine-readable adapter metadata for the AI review flow. Implementation
deferred to a follow-up phase; the placeholder lets downstream consumers
import the namespace and feature-detect via `__deferred__`.
"""

__deferred__ = True


def build_catalog(*_args: object, **_kwargs: object) -> object:  # pragma: no cover
    raise NotImplementedError(
        "openlia.data.catalog is a deferred subsystem; see data-provider-design.md "
        "Implementation Status section for the owning phase"
    )
