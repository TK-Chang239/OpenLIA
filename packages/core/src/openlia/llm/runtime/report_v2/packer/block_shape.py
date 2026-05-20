"""Section-level block shape validation and exhibit deduplication.

WS8 gates rejecting structurally broken exhibits (single-row peer tables,
single-dot scatters, placeholder axes, broken waterfalls, redundant pies)
BEFORE the section is rendered. Defects feed back into the section retry
prompt so the LLM gets a chance to fix them.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.packer.blocks.registry import (
    BlockShapeError,
    default_block_registry,
)
from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment,
    ParsedSection,
)


def dedupe_by_purpose_tag(parsed: ParsedSection) -> list[str]:
    """Strip the second (and later) block in a section that share a purpose_tag.

    Mutates ``parsed.segments`` in place. Returns a list of human-readable
    log lines describing every duplicate that was removed so the runner can
    surface them as degradation warnings.
    """
    seen: dict[str, FencedBlockSegment] = {}
    kept = []
    log: list[str] = []
    for seg in parsed.segments:
        if not isinstance(seg, FencedBlockSegment):
            kept.append(seg)
            continue
        purpose = seg.data.get("purpose_tag")
        if not purpose or not isinstance(purpose, str):
            kept.append(seg)
            continue
        if purpose in seen:
            log.append(f"dropped duplicate {seg.block_type} block with purpose_tag={purpose!r}")
            continue
        seen[purpose] = seg
        kept.append(seg)
    parsed.segments = kept
    return log


def validate_block_shapes(parsed: ParsedSection) -> list[str]:
    """Run every registered ``validate_shape`` against each fenced block.

    Returns a flat list of defect strings. Empty list means every block in
    the section passed its shape gate.
    """
    defects: list[str] = []
    for idx, seg in enumerate(parsed.segments):
        if not isinstance(seg, FencedBlockSegment):
            continue
        entry = default_block_registry.get(seg.block_type)
        if entry is None or entry.validate_shape is None:
            continue
        block_errors = entry.validate_shape(seg.data)
        for err in block_errors:
            defects.append(f"block[{idx}] {seg.block_type}: {err}")
    return defects


def enforce_block_shapes(parsed: ParsedSection) -> list[str]:
    """Full pre-render pass: dedupe by purpose_tag, then validate shapes.

    Returns a list of degradation log messages (currently just the dedup
    drops). Raises ``BlockShapeError`` if any block fails shape validation.
    """
    log = dedupe_by_purpose_tag(parsed)
    defects = validate_block_shapes(parsed)
    if defects:
        raise BlockShapeError(defects)
    return log


__all__ = [
    "BlockShapeError",
    "dedupe_by_purpose_tag",
    "enforce_block_shapes",
    "validate_block_shapes",
]
