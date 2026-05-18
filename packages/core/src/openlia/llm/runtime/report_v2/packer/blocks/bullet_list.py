from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import BulletListBlock


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> BulletListBlock:
    return BulletListBlock(
        type="bullet_list",
        items=data["items"],
        tone=data.get("tone", "default"),
    )


register_block(
    "bullet_list",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "minItems": 1}},
    },
)
