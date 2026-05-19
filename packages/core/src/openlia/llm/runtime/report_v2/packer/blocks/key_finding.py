from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import KeyFindingBlock


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> KeyFindingBlock:
    sources = list(data.get("sources", []))
    # The LLM occasionally reaches for ``text``/``finding``/``body`` instead
    # of the canonical ``content``. Accept the obvious aliases so a single
    # field-name slip does not blank the block.
    content = data.get("content") or data.get("text") or data.get("finding") or data.get("body")
    if content is None:
        raise KeyError("content")
    return KeyFindingBlock(
        type="key_finding",
        content=content,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block(
    "key_finding",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["content"],
        "properties": {"content": {"type": "string"}},
    },
)
