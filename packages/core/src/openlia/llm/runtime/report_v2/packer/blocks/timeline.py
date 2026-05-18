from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import Tag, TimelineBlock, TimelineEvent


def _normalize_event(raw: Any) -> TimelineEvent:
    # TimelineEvent requires ``when`` + ``what``. The LLM frequently reaches
    # for ``date``/``time``/``year`` for the time axis, and
    # ``event``/``description``/``text`` for the headline. Also tolerate a
    # raw string entry by treating it as the ``what``.
    if isinstance(raw, str):
        return TimelineEvent(when="", what=raw)
    e = dict(raw)
    when = (
        e.get("when")
        or e.get("date")
        or e.get("time")
        or e.get("year")
        or e.get("period")
        or ""
    )
    what = (
        e.get("what")
        or e.get("event")
        or e.get("description")
        or e.get("text")
        or e.get("title")
        or ""
    )
    impact = e.get("impact")
    impact_tag = e.get("impact_tag")
    if isinstance(impact_tag, dict):
        impact_tag = Tag(**impact_tag)
    return TimelineEvent(
        when=str(when),
        what=str(what),
        impact=impact,
        impact_tag=impact_tag,
        highlight=bool(e.get("highlight", False)),
    )


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TimelineBlock:
    events = [_normalize_event(e) for e in data["events"]]
    return TimelineBlock(
        type="timeline",
        title=data.get("title"),
        events=events,
    )


register_block(
    "timeline",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["events"],
        "properties": {"events": {"type": "array", "minItems": 1}},
    },
)
