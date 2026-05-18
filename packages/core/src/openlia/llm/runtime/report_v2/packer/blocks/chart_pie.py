from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import PieChartBlock, PieSegment


def _normalize_segment(raw: dict[str, Any]) -> PieSegment:
    # PieSegment requires ``label`` + ``value``. The LLM commonly emits
    # ``name`` / ``category`` for the label and ``share`` / ``amount`` /
    # ``percentage`` for the value.
    label = (
        raw.get("label")
        or raw.get("name")
        or raw.get("category")
        or raw.get("title")
        or ""
    )
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
    raw_segments = (
        data.get("segments") or data.get("slices") or data.get("data")
    )
    if not raw_segments:
        raise KeyError("segments")
    segments = [_normalize_segment(s) for s in raw_segments]
    payload = {
        k: v
        for k, v in data.items()
        if k not in ("sources", "segments", "slices", "data")
    }
    return PieChartBlock(
        type="pie_chart",
        segments=segments,
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:pie", assembler=_assemble)
