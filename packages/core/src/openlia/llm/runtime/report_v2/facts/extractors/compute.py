"""Pure-Python compute extractors. Operate on already-extracted facts, no payload access."""
from __future__ import annotations


def cagr(series: list[float], years: int) -> float:
    if len(series) < years + 1:
        raise ValueError(
            f"need {years + 1} points for {years}-year CAGR, got {len(series)}"
        )
    start = series[-(years + 1)]
    end = series[-1]
    return (end / start) ** (1 / years) - 1


def union_source_ids(*facts) -> list[int]:
    ids: set[int] = set()
    for f in facts:
        ids.update(f.source_ids)
    return sorted(ids)
