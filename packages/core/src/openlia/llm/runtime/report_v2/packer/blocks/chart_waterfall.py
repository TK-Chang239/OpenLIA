from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import WaterfallBlock, WaterfallItem


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> WaterfallBlock:
    sources = list(data.get("sources", []))
    items = [WaterfallItem(**item) for item in data["items"]]
    payload = {k: v for k, v in data.items() if k not in ("sources", "items")}
    return WaterfallBlock(
        type="waterfall_chart",
        items=items,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:waterfall", assembler=_assemble)
