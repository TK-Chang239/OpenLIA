from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import ComparisonColumn, ComparisonSplitBlock


def _normalize_column(col: dict[str, Any]) -> ComparisonColumn:
    col = dict(col)
    # Accept "label" or "heading" or "name" as alias for "title".
    if "title" not in col:
        for alias in ("label", "heading", "name"):
            if alias in col:
                col["title"] = col.pop(alias)
                break
    # Accept "bullets", "points", or "values" as alias for "items".
    if "items" not in col:
        for alias in ("bullets", "points", "values"):
            if alias in col:
                col["items"] = col.pop(alias)
                break
    return ComparisonColumn(**col)


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> ComparisonSplitBlock:
    return ComparisonSplitBlock(
        type="comparison_split",
        left=_normalize_column(data["left"]),
        right=_normalize_column(data["right"]),
    )


register_block(
    "comparison_split",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["left", "right"],
    },
)
