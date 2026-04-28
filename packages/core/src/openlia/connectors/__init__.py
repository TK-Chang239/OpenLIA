"""Public surface for the connector subsystem (v2).

Re-exports the runtime entry points consumers need.
"""

from __future__ import annotations

from openlia.connectors.dispatch import (
    PREFIX_SEP,
    DispatchError,
    Dispatcher,
    NeedNotResolved,
    PreparedConnector,
)

__all__ = [
    "PREFIX_SEP",
    "DispatchError",
    "Dispatcher",
    "NeedNotResolved",
    "PreparedConnector",
]
