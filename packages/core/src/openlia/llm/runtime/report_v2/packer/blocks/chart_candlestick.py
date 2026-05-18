from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import CandleRow, CandlestickBlock


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> CandlestickBlock:
    sources = list(data.get("sources", []))
    candle_data = [CandleRow(**row) for row in data["data"]]
    payload = {k: v for k, v in data.items() if k not in ("sources", "data")}
    return CandlestickBlock(
        type="candlestick_chart",
        data=candle_data,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:candlestick", assembler=_assemble)
