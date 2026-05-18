from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import (
    default_block_registry,
    register_block,
)
from openlia.reports.schema import GroupBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> GroupBlock:
    child_blocks = []
    for item in data["blocks"]:
        tag = item["type"]
        entry = default_block_registry.get(tag)
        if entry is None:
            raise ValueError(f"group: unknown child block type {tag!r}")
        child_blocks.append(
            entry.assembler(
                data=item,
                citation_ids=citation_ids,
                manifest_resolver=manifest_resolver,
            )
        )
    return GroupBlock(
        type="group",
        columns=data.get("columns", 1),
        blocks=child_blocks,
    )


register_block(
    "group",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["blocks"],
        "properties": {
            "columns": {"type": "integer", "minimum": 1, "maximum": 4},
            "blocks": {"type": "array", "minItems": 1},
        },
    },
)
