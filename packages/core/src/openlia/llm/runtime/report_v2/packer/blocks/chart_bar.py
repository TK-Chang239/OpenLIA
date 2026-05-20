from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks._shape_helpers import (
    apply_default_data_labels,
    validate_categories,
    validate_series_values,
)
from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import BarChartBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> BarChartBlock:
    sources = list(data.get("sources", []))
    payload = {k: v for k, v in data.items() if k not in ("sources", "purpose_tag")}
    return BarChartBlock(
        type="bar_chart",
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


def _validate_shape(block: dict[str, Any]) -> list[str]:
    apply_default_data_labels(block)
    errors: list[str] = []
    errors.extend(validate_categories(block.get("categories"), tag="chart:bar"))
    errors.extend(validate_series_values(block.get("series"), tag="chart:bar"))
    return errors


register_block("chart:bar", assembler=_assemble, validate_shape=_validate_shape)
