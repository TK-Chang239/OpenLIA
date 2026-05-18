from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import TreemapBlock, TreemapNode


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TreemapBlock:
    sources = list(data.get("sources", []))
    tree_data = [TreemapNode(**node) for node in data["data"]]
    payload = {k: v for k, v in data.items() if k not in ("sources", "data")}
    return TreemapBlock(
        type="treemap",
        data=tree_data,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:treemap", assembler=_assemble)
