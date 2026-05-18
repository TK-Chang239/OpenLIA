from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import CalloutGridBlock, CalloutItem


def _normalize_item(raw: dict[str, Any]) -> CalloutItem:
    # CalloutItem requires ``title`` + ``description``. The LLM commonly
    # drifts to ``heading``/``headline`` for the title and
    # ``body``/``content``/``text``/``summary`` for the description.
    title = raw.get("title") or raw.get("heading") or raw.get("headline")
    description = (
        raw.get("description")
        or raw.get("body")
        or raw.get("content")
        or raw.get("text")
        or raw.get("summary")
    )
    return CalloutItem(
        eyebrow=raw.get("eyebrow") or raw.get("kicker") or raw.get("label"),
        title=title or "",
        description=description or "",
    )


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> CalloutGridBlock:
    items = [_normalize_item(i) for i in data["items"]]
    return CalloutGridBlock(
        type="callout_grid",
        columns=data.get("columns", 3),
        items=items,
    )


register_block(
    "callout_grid",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "minItems": 2}},
    },
)
