"""Adapter registry.

Maps `kind` strings (as stored in data_providers.kind) to adapter classes.
Server code uses this to look up the right adapter when instantiating a
ProviderAdapter from a ProviderEntry.
"""

from openlia.data.adapters.eodhd import EODHDAdapter
from openlia.data.base import ProviderAdapter

ADAPTERS: dict[str, type[ProviderAdapter]] = {
    EODHDAdapter.kind: EODHDAdapter,
}

__all__ = ["ADAPTERS", "EODHDAdapter"]
