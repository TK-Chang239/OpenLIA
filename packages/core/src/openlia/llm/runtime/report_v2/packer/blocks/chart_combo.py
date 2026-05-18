from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import ComboChartBlock, ComboSeries


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> ComboChartBlock:
    sources = list(data.get("sources", []))
    raw_series = data.get("series", [])
    bar_series = [
        ComboSeries(name=s["name"], values=s["values"])
        for s in raw_series
        if s.get("kind") == "bar"
    ]
    line_series = [
        ComboSeries(name=s["name"], values=s["values"])
        for s in raw_series
        if s.get("kind") == "line"
    ]
    payload = {
        k: v
        for k, v in data.items()
        if k not in ("sources", "series", "bar_series", "line_series")
    }
    return ComboChartBlock(
        type="combo_chart",
        bar_series=bar_series,
        line_series=line_series,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:combo", assembler=_assemble)
