from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import RatingBadgeBlock


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> RatingBadgeBlock:
    return RatingBadgeBlock(
        type="rating_badge",
        rating=data["rating"],
        previous_rating=data.get("previous_rating"),
        change_date=data.get("change_date"),
    )


register_block(
    "rating_badge",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["rating"],
        "properties": {"rating": {"type": "string"}},
    },
)
