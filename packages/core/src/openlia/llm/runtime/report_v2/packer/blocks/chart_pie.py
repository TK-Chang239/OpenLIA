from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import PieChartBlock, PieSegment


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> PieChartBlock:
    sources = list(data.get("sources", []))
    segments = [PieSegment(**s) for s in data["segments"]]
    payload = {k: v for k, v in data.items() if k not in ("sources", "segments")}
    return PieChartBlock(
        type="pie_chart",
        segments=segments,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:pie", assembler=_assemble)
