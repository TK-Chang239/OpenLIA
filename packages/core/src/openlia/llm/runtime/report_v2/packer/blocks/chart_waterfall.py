from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks._shape_helpers import apply_default_data_labels
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
        if k not in ("sources", "items", "steps", "data", "purpose_tag")
    }
    return WaterfallBlock(
        type="waterfall_chart",
        items=items,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


def _coerce_item(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    label = raw.get("label") or raw.get("name") or raw.get("category") or ""
    raw_value = raw.get("value")
    if raw_value is None:
        raw_value = raw.get("amount")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    item_type = raw.get("type") or raw.get("kind") or "increase"
    return {"label": str(label), "value": value, "type": str(item_type).lower()}


def _validate_shape(block: dict[str, Any]) -> list[str]:
    """Sum-check waterfall items against declared totals (0.5% tolerance).

    Also blocks the NVDA-style failure where a decrease bar (Cost of Revenue)
    pushes the running balance above the starting total or below zero.
    """
    apply_default_data_labels(block)
    errors: list[str] = []
    raw_items = block.get("items") or block.get("steps") or block.get("data")
    if not raw_items or not isinstance(raw_items, list):
        errors.append("chart:waterfall: missing 'items' list")
        return errors
    items = []
    for idx, raw in enumerate(raw_items):
        item = _coerce_item(raw)
        if item is None:
            errors.append(f"chart:waterfall: item[{idx}] is malformed")
            return errors
        items.append(item)

    # Find the starting total. If the first item is a total, treat its value
    # as the starting balance; otherwise running balance starts at 0.
    running = 0.0
    starting_total: float | None = None
    if items and items[0]["type"] == "total":
        starting_total = items[0]["value"]
        running = starting_total

    for idx, item in enumerate(items):
        kind = item["type"]
        value = item["value"]
        if idx == 0 and kind == "total":
            continue
        if kind == "total":
            tol = max(abs(value) * 0.005, 1e-6)
            if abs(running - value) > tol:
                errors.append(
                    f"chart:waterfall: total {item['label']!r}={value} disagrees with "
                    f"running sum {running:.4f} (tolerance 0.5%)"
                )
        elif kind in ("increase", "decrease"):
            if kind == "increase":
                delta = value
            else:
                # Tolerate signed values with kind=decrease.
                delta = -abs(value)
            prev_running = running
            running += delta
            # The NVDA-class margin-bridge bug: a "decrease" (Cost of Revenue)
            # bar that floats ABOVE the starting revenue. A correctly-signed
            # decrease moves the running balance DOWN, so flag any decrease
            # whose effective delta is non-negative.
            if kind == "decrease" and delta >= 0:
                errors.append(
                    f"chart:waterfall: decrease bar {item['label']!r} has "
                    f"non-negative effect ({delta:+.4f}); decrease bars must "
                    "reduce the running balance"
                )
            # A decrease that drives the running balance below zero (Cost
            # of Revenue larger than starting Revenue, NVDA-style).
            if (
                kind == "decrease"
                and starting_total is not None
                and starting_total > 0
                and running < -1e-6
            ):
                errors.append(
                    f"chart:waterfall: after {item['label']!r}, running balance "
                    f"{running:.4f} fell below zero"
                )
            # An "increase" with a negative effective value should not
            # cross zero when starting positive.
            if (
                kind == "increase"
                and starting_total is not None
                and starting_total > 0
                and running < -1e-6
                and prev_running >= 0
            ):
                errors.append(
                    f"chart:waterfall: after {item['label']!r}, running balance "
                    f"{running:.4f} fell below zero"
                )
        else:
            # Unknown kind — skip but record.
            errors.append(f"chart:waterfall: item[{idx}] unknown type {kind!r}")
    return errors


register_block("chart:waterfall", assembler=_assemble, validate_shape=_validate_shape)
