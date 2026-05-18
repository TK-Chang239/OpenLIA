from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import CalloutGridBlock, CalloutItem


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> CalloutGridBlock:
    items = [CalloutItem(**i) for i in data["items"]]
    return CalloutGridBlock(
        type="callout_grid",
        columns=data.get("columns", 3),
        items=items,
    )


register_block(
    "callout_grid",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "minItems": 2}},
    },
)
