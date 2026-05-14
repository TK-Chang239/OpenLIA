"""Compact stub generator for externalized tool-result payloads.

When a tool result exceeds the size threshold, ToolDispatcher stores
the full payload in a per-run store and returns a stub to the LLM:
{ref, tool, shape, size_chars, sample, ...}. The model uses `ref` +
`path` with the `read_payload` tool to fetch specific slices.

Pure-function module. Six shape variants: tabular, time_series, record,
nested, unknown_list, unknown_dict. Shape detection is heuristic with
locked tie-breaker rules.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

# Caps
MAX_COLUMNS_IN_STUB = 20
MAX_TOP_KEYS_IN_STUB = 20
TABULAR_SAMPLE_ROWS = 3
TIME_SERIES_HEAD_TAIL = 2  # head + tail count each
RECORD_SAMPLE_FIELDS = 5
UNKNOWN_LIST_SAMPLE_ITEMS = 2
UNKNOWN_LIST_ITEM_CHARS = 500
UNKNOWN_DICT_REPR_CHARS = 800
RECORD_STRING_VALUE_MAX_CHARS = 200
TABULAR_STRING_VALUE_MAX_CHARS = 100

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_QUARTER = re.compile(r"^\d{4}Q[1-4]$")
_YEAR_INT_RANGE = range(1900, 2200)


def generate_stub(payload: Any, *, ref: str, tool_name: str) -> dict[str, Any]:
    """Detect shape and return the appropriate stub dict.

    Always includes: ref, tool, shape, size_chars, truncated=True.
    """
    size_chars = len(json.dumps(payload, default=str))
    shape = _detect_shape(payload)
    kw = dict(ref=ref, tool_name=tool_name, size_chars=size_chars)
    if shape == "tabular":
        return _tabular_stub(payload, **kw)
    if shape == "time_series":
        return _time_series_stub(payload, **kw)
    if shape == "record":
        return _record_stub(payload, **kw)
    if shape == "nested":
        return _nested_stub(payload, **kw)
    if shape == "unknown_list":
        return _unknown_list_stub(payload, **kw)
    return _unknown_dict_stub(payload, **kw)


# ---------------------------------------------------------------------------
# Shape detection
# ---------------------------------------------------------------------------


def _detect_shape(payload: Any) -> str:
    if not isinstance(payload, (list, dict)):
        return "unknown_dict"
    if isinstance(payload, list):
        if not payload or (len(payload) == 1 and isinstance(payload[0], dict)):
            return "tabular"
        if _is_tabular_list_of_dicts(payload):
            return "time_series" if _has_monotonic_date_column(payload) else "tabular"
        return "unknown_list"
    if _is_nested_dict(payload):
        return "nested"
    return "record"


def _is_tabular_list_of_dicts(items: list) -> bool:
    if not items or not all(isinstance(x, dict) for x in items):
        return False
    union_keys: set[str] = set()
    for it in items:
        union_keys.update(it.keys())
    if not union_keys:
        return False
    rows_with_80pct = sum(
        1 for it in items if len(set(it.keys()) & union_keys) >= 0.8 * len(union_keys)
    )
    return rows_with_80pct >= 0.8 * len(items)


def _is_nested_dict(payload: dict) -> bool:
    values = list(payload.values())
    if not values:
        return False
    for v in values:
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            return True
    dict_values = [v for v in values if isinstance(v, dict)]
    if len(dict_values) < 2 or len(dict_values) != len(values):
        return False
    base_keys = set(dict_values[0].keys())
    for dv in dict_values[1:]:
        other_keys = set(dv.keys())
        if not base_keys and not other_keys:
            continue
        intersection = base_keys & other_keys
        union = base_keys | other_keys
        if min(len(base_keys), len(other_keys)) == 0:
            continue
        if len(intersection) >= 2 or len(intersection) >= 0.5 * len(union):
            return True
    return False


# ---------------------------------------------------------------------------
# Time-series helpers
# ---------------------------------------------------------------------------


def _looks_like_date(v: Any) -> bool:
    if isinstance(v, (datetime, date)):
        return True
    if isinstance(v, int):
        return v in _YEAR_INT_RANGE
    if isinstance(v, str):
        return bool(_ISO_DATE.match(v) or _QUARTER.match(v))
    return False


def _looks_like_date_col(values: list) -> bool:
    return bool(values) and sum(1 for v in values if _looks_like_date(v)) >= 0.8 * len(values)


def _date_sort_key(v: Any) -> str:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def _is_monotonic(values: list) -> str | None:
    if len(values) <= 1:
        return "asc"
    try:
        keyed = [_date_sort_key(v) for v in values]
        asc = sorted(keyed)
        if keyed == asc:
            return "asc"
        if keyed == list(reversed(asc)):
            return "desc"
    except (TypeError, ValueError):
        pass
    return None


def _col_values(rows: list[dict], col: str) -> list:
    return [row[col] for row in rows if col in row]


def _union_keys(rows: list[dict]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        keys.update(row.keys())
    return keys


def _has_monotonic_date_column(rows: list[dict]) -> bool:
    if not rows or not isinstance(rows[0], dict):
        return False
    for col in _union_keys(rows):
        vals = _col_values(rows, col)
        if _looks_like_date_col(vals) and _is_monotonic(vals) is not None:
            return True
    return False


def _find_date_column_info(rows: list[dict]) -> tuple[str | None, str | None, list | None]:
    for col in _union_keys(rows):
        vals = _col_values(rows, col)
        if _looks_like_date_col(vals):
            ordering = _is_monotonic(vals)
            if ordering is not None:
                return col, ordering, vals
    return None, None, None


def _period_range(values: list) -> list | None:
    if not values:
        return None
    try:
        sv = sorted(values, key=_date_sort_key)
        to_s = lambda v: v.isoformat() if isinstance(v, (datetime, date)) else str(v)  # noqa: E731
        return [to_s(sv[0]), to_s(sv[-1])]
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Value truncation
# ---------------------------------------------------------------------------


def _cap(v: Any, max_chars: int) -> Any:
    return v[:max_chars] if isinstance(v, str) and len(v) > max_chars else v


def _cap_row(row: dict, max_chars: int) -> dict:
    return {k: _cap(v, max_chars) for k, v in row.items()}


# ---------------------------------------------------------------------------
# Stub builders
# ---------------------------------------------------------------------------


def _ordered_keys(rows: list[dict]) -> list[str]:
    return list(dict.fromkeys(k for row in rows for k in row))


def _tabular_stub(payload: list, *, ref: str, tool_name: str, size_chars: int) -> dict[str, Any]:
    n_rows = len(payload)
    all_cols = _ordered_keys(payload) if payload else []
    n_columns = len(all_cols)
    return {
        "ref": ref,
        "tool": tool_name,
        "shape": "tabular",
        "n_rows": n_rows,
        "size_chars": size_chars,
        "columns": all_cols[:MAX_COLUMNS_IN_STUB],
        "n_columns": n_columns,
        "columns_truncated": n_columns > MAX_COLUMNS_IN_STUB,
        "sample": [
            _cap_row(r, TABULAR_STRING_VALUE_MAX_CHARS) for r in payload[:TABULAR_SAMPLE_ROWS]
        ],
        "truncated": True,
    }


def _time_series_stub(
    payload: list, *, ref: str, tool_name: str, size_chars: int
) -> dict[str, Any]:
    n_rows = len(payload)
    all_cols = _ordered_keys(payload)
    n_columns = len(all_cols)
    _col, ordering, date_values = _find_date_column_info(payload)
    head = [_cap_row(r, TABULAR_STRING_VALUE_MAX_CHARS) for r in payload[:TIME_SERIES_HEAD_TAIL]]
    tail = (
        [_cap_row(r, TABULAR_STRING_VALUE_MAX_CHARS) for r in payload[-TIME_SERIES_HEAD_TAIL:]]
        if len(payload) > TIME_SERIES_HEAD_TAIL
        else []
    )
    return {
        "ref": ref,
        "tool": tool_name,
        "shape": "time_series",
        "n_rows": n_rows,
        "size_chars": size_chars,
        "columns": all_cols[:MAX_COLUMNS_IN_STUB],
        "n_columns": n_columns,
        "columns_truncated": n_columns > MAX_COLUMNS_IN_STUB,
        "period_range": _period_range(date_values) if date_values else None,
        "ordering": ordering,
        "sample": {"head": head, "tail": tail},
        "truncated": True,
    }


def _record_stub(payload: dict, *, ref: str, tool_name: str, size_chars: int) -> dict[str, Any]:
    all_keys = list(payload.keys())
    n_keys = len(all_keys)
    return {
        "ref": ref,
        "tool": tool_name,
        "shape": "record",
        "size_chars": size_chars,
        "top_keys": all_keys[:MAX_TOP_KEYS_IN_STUB],
        "n_keys": n_keys,
        "keys_truncated": n_keys > MAX_TOP_KEYS_IN_STUB,
        "sample": {
            k: _cap(payload[k], RECORD_STRING_VALUE_MAX_CHARS)
            for k in all_keys[:RECORD_SAMPLE_FIELDS]
        },
        "truncated": True,
    }


def _subshape_label(v: Any) -> str:
    try:
        sub = _detect_shape(v)
        if sub in ("tabular", "time_series", "unknown_list") and isinstance(v, list):
            counts = {"tabular": "rows", "time_series": "rows", "unknown_list": "items"}
            return f"{sub} ({len(v)} {counts[sub]})"
        return sub
    except Exception:
        return "unknown"


def _nested_stub(payload: dict, *, ref: str, tool_name: str, size_chars: int) -> dict[str, Any]:
    all_keys = list(payload.keys())
    n_keys = len(all_keys)
    top_keys = all_keys[:MAX_TOP_KEYS_IN_STUB]
    return {
        "ref": ref,
        "tool": tool_name,
        "shape": "nested",
        "size_chars": size_chars,
        "top_keys": top_keys,
        "n_keys": n_keys,
        "keys_truncated": n_keys > MAX_TOP_KEYS_IN_STUB,
        "subshapes": {k: _subshape_label(payload[k]) for k in top_keys},
        "truncated": True,
    }


def _unknown_list_stub(
    payload: list, *, ref: str, tool_name: str, size_chars: int
) -> dict[str, Any]:
    return {
        "ref": ref,
        "tool": tool_name,
        "shape": "unknown_list",
        "n_items": len(payload),
        "size_chars": size_chars,
        "sample": [
            repr(item)[:UNKNOWN_LIST_ITEM_CHARS] for item in payload[:UNKNOWN_LIST_SAMPLE_ITEMS]
        ],
        "truncated": True,
    }


def _unknown_dict_stub(
    payload: Any, *, ref: str, tool_name: str, size_chars: int
) -> dict[str, Any]:
    stub: dict[str, Any] = {
        "ref": ref,
        "tool": tool_name,
        "shape": "unknown_dict",
        "size_chars": size_chars,
        "n_keys": None,
        "keys_truncated": False,
        "sample_repr": repr(payload)[:UNKNOWN_DICT_REPR_CHARS],
        "truncated": True,
    }
    if isinstance(payload, dict):
        all_keys = list(payload.keys())
        n_keys = len(all_keys)
        stub["top_keys"] = all_keys[:MAX_TOP_KEYS_IN_STUB]
        stub["n_keys"] = n_keys
        stub["keys_truncated"] = n_keys > MAX_TOP_KEYS_IN_STUB
    return stub
