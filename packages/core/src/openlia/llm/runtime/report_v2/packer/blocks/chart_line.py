from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import LineChartBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> LineChartBlock:
    sources = list(data.get("sources", []))
    payload = {k: v for k, v in data.items() if k != "sources"}
    return LineChartBlock(
        type="line_chart",
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:line", assembler=_assemble)
