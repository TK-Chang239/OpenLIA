"""Shared shape validation helpers for chart block packers."""

from __future__ import annotations

import re
from typing import Any

# Placeholder axis labels the LLM emits when it lacks real fiscal-year data.
# Reject these so the block packer never ships a chart with fake axes.
_PLACEHOLDER_AXIS_RE = re.compile(
    r"^\s*(?:"
    r"year\s*\d+"
    r"|y\d+"
    r"|period\s*\d+"
    r"|p\d+"
    r"|t\d+"
    r"|t\s*[-+]?\s*\d+"
    r"|ttm\s*/\s*late"
    r"|late"
    r"|early"
    r"|n/?a"
    r"|placeholder"
    r"|tbd"
    r"|supplied\s*data\s*point"
    r")\s*$",
    re.IGNORECASE,
)


def is_placeholder_label(label: Any) -> bool:
    if not isinstance(label, str):
        return False
    return bool(_PLACEHOLDER_AXIS_RE.match(label))


def validate_categories(categories: Any, *, tag: str) -> list[str]:
    """Reject placeholder axis labels like 'Year 1', 'TTM/Late', etc."""
    errors: list[str] = []
    if categories is None:
        errors.append(f"{tag}: missing 'categories'")
        return errors
    if not isinstance(categories, list):
        errors.append(f"{tag}: 'categories' must be a list")
        return errors
    for idx, cat in enumerate(categories):
        if is_placeholder_label(cat):
            errors.append(
                f"{tag}: categories[{idx}]={cat!r} is a placeholder label; "
                "use real dates or fiscal-year strings"
            )
    return errors


def validate_series_values(series_list: Any, *, tag: str, key: str = "values") -> list[str]:
    """Ensure every series has a non-empty ``values`` array of numbers/None."""
    errors: list[str] = []
    if not series_list:
        errors.append(f"{tag}: at least one series required")
        return errors
    if not isinstance(series_list, list):
        errors.append(f"{tag}: series must be a list")
        return errors
    for idx, s in enumerate(series_list):
        if not isinstance(s, dict):
            errors.append(f"{tag}: series[{idx}] must be a mapping")
            continue
        # Accept the canonical key plus the common LLM drift ('data').
        values = s.get(key)
        if values is None:
            values = s.get("data")
        name = s.get("name", f"series[{idx}]")
        if not isinstance(values, list) or len(values) == 0:
            errors.append(f"{tag}: series {name!r} missing non-empty {key!r} array")
            continue
        for vi, v in enumerate(values):
            if v is None:
                continue
            if isinstance(v, bool):
                # Booleans are technically int subclasses; reject explicitly.
                errors.append(
                    f"{tag}: series {name!r}[{vi}]={v!r} is a boolean; expected number or null"
                )
                continue
            if not isinstance(v, (int, float)):
                errors.append(
                    f"{tag}: series {name!r}[{vi}]={v!r} must be a number or null, "
                    f"not {type(v).__name__}"
                )
    return errors


def count_data_points(block: dict[str, Any]) -> int:
    """Best-effort count of data points across the block's series.

    Used to decide whether ``data_labels: true`` should be the default. Counts
    flat ``values`` arrays for bar/line/area/combo and scatter ``points``.
    """
    total = 0
    series_keys = ("series", "bar_series", "line_series")
    for key in series_keys:
        for s in block.get(key) or []:
            if not isinstance(s, dict):
                continue
            for vk in ("values", "points", "data"):
                v = s.get(vk)
                if isinstance(v, list):
                    total += len(v)
                    break
    # Pie segments + treemap nodes + waterfall items + heatmap cells.
    for key in ("segments", "items", "data"):
        v = block.get(key)
        if isinstance(v, list):
            # Avoid double-counting series 'data' captured above by skipping
            # when we already saw any series.
            if total == 0:
                total += len(v)
    return total


def apply_default_data_labels(block: dict[str, Any]) -> None:
    """Default ``data_labels`` to True when the block has <=8 data points.

    Mutates the block dict in place. Does nothing if ``data_labels`` is set.
    """
    if "data_labels" in block and block["data_labels"] is not None:
        return
    if count_data_points(block) <= 8:
        block["data_labels"] = True
