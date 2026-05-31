"""Generic, connector-agnostic pruning of tool-result payloads.

``prune_empty`` recursively removes value-less fields (``None``, ``""``,
empty list/dict) from a data-connector payload before it enters the
model's context. It is strictly lossless of signal: an empty container
or null field carries no information, so dropping it shrinks the
first-read (and any cached copy) without changing what the model can
learn.

The function knows nothing about EODHD — or any provider — so every
financial connector routed through a data-tool wrapper gets the same
treatment for free. Real values are preserved exactly: ``0``, ``0.0``,
and ``False`` are kept (a zero margin or a false flag is data, not
emptiness). List length is preserved — only dict keys with empty values
are dropped — so any positional or counted array stays intact.
"""

from __future__ import annotations

from typing import Any


def prune_empty(value: Any) -> Any:
    """Return ``value`` with empty fields recursively removed.

    Dicts: drop every key whose pruned value is empty. Lists: recurse
    into each element but keep length. Scalars: returned unchanged
    (numbers and booleans always kept).
    """
    if isinstance(value, dict):
        pruned: dict[Any, Any] = {}
        for key, raw in value.items():
            child = prune_empty(raw)
            if not _is_empty(child):
                pruned[key] = child
        return pruned
    if isinstance(value, list):
        return [prune_empty(item) for item in value]
    return value


def _is_empty(value: Any) -> bool:
    """True for ``None`` / ``""`` / empty list/dict/tuple; False otherwise.

    Numbers (including ``0`` and ``0.0``) and ``False`` are never empty.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


__all__ = ["prune_empty"]
