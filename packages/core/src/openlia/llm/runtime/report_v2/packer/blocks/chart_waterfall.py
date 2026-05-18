from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import WaterfallBlock, WaterfallItem


def _normalize_item(raw: dict[str, Any]) -> WaterfallItem:
    # WaterfallItem requires ``label`` + ``value`` + ``type``. The LLM
    # commonly uses ``name`` for label, ``amount`` for value, and may emit
    # ``kind`` instead of ``type``.
    label = raw.get("label") or raw.get("name") or raw.get("category") or ""
    raw_value = raw.get("value")
    if raw_value is None:
        raw_value = raw.get("amount")
    item_type = raw.get("type") or raw.get("kind") or "increase"
    return WaterfallItem(label=str(label), value=float(raw_value), type=item_type)


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> WaterfallBlock:
    sources = list(data.get("sources", []))
    # ``steps`` and ``data`` are the common drift keys for ``items``.
    raw_items = data.get("items") or data.get("steps") or data.get("data")
    if not raw_items:
        raise KeyError("items")
    items = [_normalize_item(i) for i in raw_items]
    payload = {
        k: v
        for k, v in data.items()
        if k not in ("sources", "items", "steps", "data")
    }
    return WaterfallBlock(
        type="waterfall_chart",
        items=items,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:waterfall", assembler=_assemble)
