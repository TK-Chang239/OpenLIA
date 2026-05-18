from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import ComparisonColumn, ComparisonSplitBlock


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> ComparisonSplitBlock:
    return ComparisonSplitBlock(
        type="comparison_split",
        left=ComparisonColumn(**data["left"]),
        right=ComparisonColumn(**data["right"]),
    )


register_block(
    "comparison_split",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["left", "right"],
    },
)
