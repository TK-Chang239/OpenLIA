from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks._shape_helpers import apply_default_data_labels
from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import TreemapBlock, TreemapNode


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TreemapBlock:
    sources = list(data.get("sources", []))
    tree_data = [TreemapNode(**node) for node in data["data"]]
    excluded = ("sources", "data", "purpose_tag", "total")
    payload = {k: v for k, v in data.items() if k not in excluded}
    return TreemapBlock(
        type="treemap",
        data=tree_data,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


def _validate_shape(block: dict[str, Any]) -> list[str]:
    """Top-level nodes must sum to 100 (+/- 1%) or to a declared absolute total."""
    apply_default_data_labels(block)
    errors: list[str] = []
    nodes = block.get("data")
    if not nodes or not isinstance(nodes, list):
        errors.append("chart:treemap: missing 'data' list")
        return errors
    values: list[float] = []
    for idx, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            errors.append(f"chart:treemap: node[{idx}] must be a mapping")
            continue
        try:
            values.append(float(raw.get("value")))
        except (TypeError, ValueError):
            errors.append(f"chart:treemap: node[{idx}] has non-numeric value")
    if errors:
        return errors
    total = sum(values)
    total_decl = block.get("total")
    if total_decl is not None:
        try:
            expected = float(total_decl)
        except (TypeError, ValueError):
            errors.append(f"chart:treemap: declared total {total_decl!r} is not numeric")
            return errors
        tol = max(abs(expected) * 0.01, 1e-6)
        if abs(total - expected) > tol:
            errors.append(
                f"chart:treemap: nodes sum to {total:.4f}; expected {expected:.4f} (within 1%)"
            )
    else:
        if abs(total - 100.0) > 1.0:
            errors.append(f"chart:treemap: nodes sum to {total:.4f}%; expected 100% (+/- 1%)")
    return errors


register_block("chart:treemap", assembler=_assemble, validate_shape=_validate_shape)
