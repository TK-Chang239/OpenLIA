"""Shared utilities for helper-tier (WS7) facts."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.types import Fact


def oldest_data_as_of_of_deps(facts: Iterable[Fact]) -> datetime | str | None:
    """Oldest `data_as_of` across an iterable of dependency facts.

    Returns the original value (str or datetime) for display; mirrors
    `_oldest_dep_as_of` in `extractors.stock_initiation`."""
    oldest: tuple[datetime, datetime | str] | None = None
    for f in facts:
        v = f.data_as_of
        if v is None:
            continue
        parsed: datetime | None
        if isinstance(v, datetime):
            parsed = v if v.tzinfo is not None else v.replace(tzinfo=UTC)
        elif isinstance(v, str):
            s = v.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(s)
            except ValueError:
                try:
                    parsed = datetime.strptime(s, "%Y-%m-%d")
                except ValueError:
                    parsed = None
            if parsed is not None and parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = None
        if parsed is None:
            continue
        if oldest is None or parsed < oldest[0]:
            oldest = (parsed, v)
    return oldest[1] if oldest is not None else None


def last_or_none(fact: Fact) -> float | None:
    """Latest value from a series fact, or None if the series is empty/None."""
    v = fact.value
    if isinstance(v, list) and v:
        return v[-1]
    return None
