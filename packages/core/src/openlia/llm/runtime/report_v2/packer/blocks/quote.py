from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import QuoteBlock, Tag


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> QuoteBlock:
    sources = list(data.get("sources", []))
    tag = None
    if "tag" in data and data["tag"] is not None:
        tag = Tag(**data["tag"])
    return QuoteBlock(
        type="quote",
        text=data["text"],
        speaker=data.get("speaker"),
        role=data.get("role"),
        tag=tag,
        timestamp=data.get("timestamp"),
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block(
    "quote",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["text"],
        "properties": {"text": {"type": "string"}},
    },
)
