from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import ScatterBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> ScatterBlock:
    sources = list(data.get("sources", []))
    payload = {k: v for k, v in data.items() if k not in ("sources", "purpose_tag")}
    return ScatterBlock(
        type="scatter_plot",
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


def _validate_shape(block: dict[str, Any]) -> list[str]:
    """Require >=3 points per series. Single-dot scatters are rejected."""
    errors: list[str] = []
    series = block.get("series") or []
    if not series:
        errors.append("chart:scatter: at least one series required")
        return errors
    for idx, s in enumerate(series):
        if not isinstance(s, dict):
            errors.append(f"chart:scatter: series[{idx}] must be a mapping")
            continue
        points = s.get("points") or []
        if len(points) < 3:
            name = s.get("name", f"series[{idx}]")
            errors.append(
                f"chart:scatter: series {name!r} has {len(points)} point(s); >=3 required"
            )
    return errors


register_block("chart:scatter", assembler=_assemble, validate_shape=_validate_shape)
