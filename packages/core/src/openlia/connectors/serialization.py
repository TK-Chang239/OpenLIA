"""JSON-coercion helper for connector tool results.

Tool returns flow `transport.call_tool()` -> dispatcher -> chat runtime,
where they get `json.dumps`'d into the conversation as the `tool` message
content. Many real SDKs (firecrawl-py's SearchData, pydantic models in
general, dataclasses, datetimes, Decimals) aren't JSON-native, so a
naive `json.dumps(payload)` raises TypeError and kills the chat turn.

`to_jsonable` runs a single recursive coercion pass:

1. Native JSON types pass through unchanged.
2. Pydantic v1/v2 models: try `model_dump()` then `dict()`.
3. Dataclasses / objects with `__dict__`: convert via that mapping.
4. Anything else: fall back to `str(value)`.

This is the dispatch boundary's contract: callers may assume the result
of `to_jsonable(x)` is safe to pass to `json.dumps` without `default=`.
"""

from __future__ import annotations

import dataclasses
from typing import Any

_PRIMITIVES = (str, int, float, bool, type(None))


def to_jsonable(value: Any) -> Any:
    if isinstance(value, _PRIMITIVES):
        return value
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [to_jsonable(v) for v in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return to_jsonable(dump())
        except Exception:
            pass
    legacy_dict = getattr(value, "dict", None)
    if callable(legacy_dict) and type(value).__name__ != "type":
        try:
            return to_jsonable(legacy_dict())
        except Exception:
            pass
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    inner = getattr(value, "__dict__", None)
    if isinstance(inner, dict) and inner:
        return {str(k): to_jsonable(v) for k, v in inner.items()}
    return str(value)
