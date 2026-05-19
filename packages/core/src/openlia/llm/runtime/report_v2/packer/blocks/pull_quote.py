from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import PullQuoteBlock


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> PullQuoteBlock:
    sources = list(data.get("sources", []))
    # ``quote``/``content`` are the common drift keys when the LLM forgets
    # the canonical ``text``. Author can also tag the attribution via
    # ``author`` or ``speaker``.
    text = data.get("text") or data.get("quote") or data.get("content")
    if text is None:
        raise KeyError("text")
    attribution = data.get("attribution") or data.get("author") or data.get("speaker")
    return PullQuoteBlock(
        type="pull_quote",
        text=text,
        attribution=attribution,
        source=data.get("source"),
        timestamp=data.get("timestamp"),
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block(
    "pull_quote",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["text"],
        "properties": {"text": {"type": "string"}},
    },
)
