"""Deterministic JSONPath-style extractors. Stateless helpers; the
register_fact decorations live in the per-report-type module
(e.g. stock_initiation.py) so importing this module has no side effects."""
from __future__ import annotations

from typing import Any


def pluck(payload: Any, *path: str) -> Any:
    """Walk a nested dict path, raising KeyError with full breadcrumb on miss."""
    cur = payload
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            raise KeyError(f"missing key {'.'.join(path)!r} (failed at {key!r})")
        cur = cur[key]
    return cur


def pluck_or_none(payload: Any, *path: str) -> Any:
    try:
        return pluck(payload, *path)
    except KeyError:
        return None


def yearly_series(payload: Any, *, statement: str, field: str, n_years: int = 5) -> list[float]:
    """Extract last-N-years series from EODHD income/balance/cashflow shape."""
    yearly = pluck(payload, "Financials", statement, "yearly")
    sorted_dates = sorted(yearly.keys())[-n_years:]
    return [float(yearly[d][field]) for d in sorted_dates]
