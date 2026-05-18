from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import TableBlock, TableHeader


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TableBlock:
    headers = [TableHeader(**h) for h in data["headers"]]
    sources = list(data.get("sources", []))
    return TableBlock(
        type="table",
        title=data["title"],
        headers=headers,
        rows=data["rows"],
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block(
    "table",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["title", "headers", "rows"],
    },
)
