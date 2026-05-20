from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks._shape_helpers import (
    apply_default_data_labels,
    validate_categories,
    validate_series_values,
)
from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import ComboChartBlock, ComboSeries


def _normalize_series(raw: list[dict[str, Any]]) -> list[ComboSeries]:
    out: list[ComboSeries] = []
    for s in raw:
        name = s.get("name") or s.get("label") or "series"
        values = s.get("values") or s.get("data") or []
        out.append(ComboSeries(name=name, values=values))
    return out


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> ComboChartBlock:
    data = dict(data)  # do not mutate caller
    sources = list(data.pop("sources", []))
    data.pop("purpose_tag", None)

    # Tolerate "labels" alias for "categories".
    if "categories" not in data and "labels" in data:
        data["categories"] = data.pop("labels")

    # Tolerate either: direct bar_series/line_series keys (prompt convention),
    # or a unified series list with kind="bar"|"line" (legacy assembler shape).
    if "bar_series" in data or "line_series" in data:
        bar_series = _normalize_series(list(data.pop("bar_series", [])))
        line_series = _normalize_series(list(data.pop("line_series", [])))
        data.pop("series", None)
    else:
        raw_series = list(data.pop("series", []))
        bar_series = _normalize_series([s for s in raw_series if s.get("kind") == "bar"])
        line_series = _normalize_series([s for s in raw_series if s.get("kind") == "line"])

    return ComboChartBlock(
        type="combo_chart",
        bar_series=bar_series,
        line_series=line_series,
        **data,
        source_ids=manifest_resolver(sources or citation_ids),
    )


def _validate_shape(block: dict[str, Any]) -> list[str]:
    apply_default_data_labels(block)
    errors: list[str] = []
    errors.extend(validate_categories(block.get("categories"), tag="chart:combo"))
    bar_series = block.get("bar_series")
    line_series = block.get("line_series")
    unified = block.get("series")
    if bar_series is None and line_series is None and unified is None:
        errors.append("chart:combo: at least one of bar_series/line_series/series required")
        return errors
    if bar_series is not None:
        errors.extend(validate_series_values(bar_series, tag="chart:combo[bar]"))
    if line_series is not None:
        errors.extend(validate_series_values(line_series, tag="chart:combo[line]"))
    if bar_series is None and line_series is None and unified is not None:
        errors.extend(validate_series_values(unified, tag="chart:combo"))
    return errors


register_block("chart:combo", assembler=_assemble, validate_shape=_validate_shape)
