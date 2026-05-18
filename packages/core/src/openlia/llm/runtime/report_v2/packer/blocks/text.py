from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import TextBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TextBlock:
    # TextBlock has no source_ids field; citation resolution is a no-op here
    return TextBlock(
        type="text",
        content=data["content"],
    )


register_block(
    "text",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["content"],
        "properties": {"content": {"type": "string"}},
    },
)
