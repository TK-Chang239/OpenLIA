from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks._shape_helpers import apply_default_data_labels
from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import PieChartBlock, PieSegment


def _normalize_segment(raw: dict[str, Any]) -> PieSegment:
    # PieSegment requires ``label`` + ``value``. The LLM commonly emits
    # ``name`` / ``category`` for the label and ``share`` / ``amount`` /
    # ``percentage`` for the value.
    label = raw.get("label") or raw.get("name") or raw.get("category") or raw.get("title") or ""
    raw_value = raw.get("value")
    if raw_value is None:
        raw_value = (
            raw.get("share")
            if raw.get("share") is not None
            else raw.get("amount")
            if raw.get("amount") is not None
            else raw.get("percentage")
        )
    return PieSegment(label=str(label), value=float(raw_value))


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> PieChartBlock:
    sources = list(data.get("sources", []))
    # ``slices`` and ``data`` are the common drift keys for ``segments``.
    raw_segments = data.get("segments") or data.get("slices") or data.get("data")
    if not raw_segments:
        raise KeyError("segments")
    segments = [_normalize_segment(s) for s in raw_segments]
    payload = {
        k: v
        for k, v in data.items()
        if k not in ("sources", "segments", "slices", "data", "purpose_tag")
    }
    return PieChartBlock(
        type="pie_chart",
        segments=segments,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


def _validate_shape(block: dict[str, Any]) -> list[str]:
    """Segments must sum to 100 (+/- 1%) or to a declared absolute total."""
    apply_default_data_labels(block)
    errors: list[str] = []
    raw_segments = block.get("segments") or block.get("slices") or block.get("data")
    if not raw_segments or not isinstance(raw_segments, list):
        errors.append("chart:pie: missing 'segments' list")
        return errors
    total_decl = block.get("total")
    values: list[float] = []
    for idx, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            errors.append(f"chart:pie: segment[{idx}] must be a mapping")
            continue
        raw_value = raw.get("value")
        if raw_value is None:
            raw_value = raw.get("share") or raw.get("amount") or raw.get("percentage")
        try:
            values.append(float(raw_value))
        except (TypeError, ValueError):
            errors.append(f"chart:pie: segment[{idx}] has non-numeric value {raw_value!r}")
    if errors:
        return errors
    total = sum(values)
    if total_decl is not None:
        try:
            expected = float(total_decl)
        except (TypeError, ValueError):
            errors.append(f"chart:pie: declared total {total_decl!r} is not numeric")
            return errors
        tol = max(abs(expected) * 0.01, 1e-6)
        if abs(total - expected) > tol:
            errors.append(
                f"chart:pie: segments sum to {total:.4f}; expected {expected:.4f} (within 1%)"
            )
    else:
        # Percent mode: must sum to ~100.
        if abs(total - 100.0) > 1.0:
            errors.append(f"chart:pie: segments sum to {total:.4f}%; expected 100% (+/- 1%)")
    return errors


register_block("chart:pie", assembler=_assemble, validate_shape=_validate_shape)
