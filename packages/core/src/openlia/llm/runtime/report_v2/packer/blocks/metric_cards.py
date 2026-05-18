from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import Metric, MetricCardsBlock, Tag


def _normalize_metric(m: dict[str, Any]) -> Metric:
    m = dict(m)
    # Accept "name", "title", or "metric" as alias for "label".
    if "label" not in m:
        for alias in ("name", "title", "metric"):
            if alias in m:
                m["label"] = m.pop(alias)
                break
    # Accept "amount" or "figure" as alias for "value".
    if "value" not in m:
        for alias in ("amount", "figure"):
            if alias in m:
                m["value"] = m.pop(alias)
                break
    # Coerce non-string values to string (model often emits numbers).
    if "value" in m and not isinstance(m["value"], str):
        m["value"] = str(m["value"])
    if "tag" in m and m["tag"] is not None and isinstance(m["tag"], dict):
        m["tag"] = Tag(**m["tag"])
    return Metric(**m)


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> MetricCardsBlock:
    # Tolerate "cards", "items", or "values" as alias for "metrics".
    raw = data.get("metrics")
    if raw is None:
        for alias in ("cards", "items", "values"):
            if alias in data:
                raw = data[alias]
                break
    if raw is None:
        raise KeyError("metrics")
    metrics = [_normalize_metric(m) for m in raw]
    return MetricCardsBlock(type="metric_cards", metrics=metrics)


register_block(
    "metric_cards",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["metrics"],
        "properties": {"metrics": {"type": "array", "minItems": 1}},
    },
)
