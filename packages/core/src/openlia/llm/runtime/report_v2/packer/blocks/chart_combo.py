from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import ComboChartBlock, ComboSeries


def _normalize_series(raw: list[dict[str, Any]]) -> list[ComboSeries]:
    out: list[ComboSeries] = []
    for s in raw:
        name = s.get("name") or s.get("label") or "series"
        values = s.get("values") or s.get("data") or []
        out.append(ComboSeries(name=name, values=values))
    return out


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> ComboChartBlock:
    data = dict(data)  # do not mutate caller
    sources = list(data.pop("sources", []))

    # Tolerate "labels" alias for "categories".
    if "categories" not in data and "labels" in data:
        data["categories"] = data.pop("labels")

    # Tolerate either: direct bar_series/line_series keys (prompt convention),
    # or a unified series list with kind="bar"|"line" (legacy assembler shape).
    if "bar_series" in data or "line_series" in data:
        bar_series = _normalize_series(list(data.pop("bar_series", [])))
        line_series = _normalize_series(list(data.pop("line_series", [])))
        data.pop("series", None)
    else:
        raw_series = list(data.pop("series", []))
        bar_series = _normalize_series([s for s in raw_series if s.get("kind") == "bar"])
        line_series = _normalize_series([s for s in raw_series if s.get("kind") == "line"])

    return ComboChartBlock(
        type="combo_chart",
        bar_series=bar_series,
        line_series=line_series,
        **data,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:combo", assembler=_assemble)
