from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import Tag, TimelineBlock, TimelineEvent


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TimelineBlock:
    events = []
    for e in data["events"]:
        e = dict(e)
        if "impact_tag" in e and e["impact_tag"] is not None:
            e["impact_tag"] = Tag(**e["impact_tag"])
        events.append(TimelineEvent(**e))
    return TimelineBlock(
        type="timeline",
        title=data.get("title"),
        events=events,
    )


register_block(
    "timeline",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["events"],
        "properties": {"events": {"type": "array", "minItems": 1}},
    },
)
