from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import Metric, MetricCardsBlock, Tag


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> MetricCardsBlock:
    metrics = []
    for m in data["metrics"]:
        m = dict(m)
        if "tag" in m and m["tag"] is not None:
            m["tag"] = Tag(**m["tag"])
        metrics.append(Metric(**m))
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
