"""Manifest rendering — turns a tool list into the prompt-injectable block.

Simple tools render their full signature inline; complex tools render only
the one-liner + a pointer to `get_helper_docs(name)` for the worked example.
This is the "discovery vs. loading" separation from the PR 8 design:
discovery is always loaded, full docs fetched on demand.
"""

from __future__ import annotations

from collections.abc import Iterable

from openlia.llm.runtime.report_v2.tools.protocol import ToolHandler


def _render_one(handler: ToolHandler) -> str:
    if handler.complexity == "simple":
        # Inline the (compact) input_schema property list so the model can call
        # without inspecting. Schema rendered as `arg1, arg2, ...`.
        props = handler.input_schema.get("properties", {})
        signature = ", ".join(props.keys())
        return f"- `{handler.name}({signature})` — {handler.summary}. Use when: {handler.use_when}"
    return (
        f"- `{handler.name}(...)` — {handler.summary}. Use when: {handler.use_when}. "
        f"Call `get_helper_docs({handler.name!r})` for full signature and a worked example."
    )


def render_manifest(handlers: Iterable[ToolHandler]) -> str:
    """Render the section-prompt manifest block.

    Empty input returns an empty string so callers can unconditionally append
    the manifest without worrying about formatting empty headers.
    """
    items = list(handlers)
    if not items:
        return ""
    body = "\n".join(_render_one(h) for h in items)
    return "## Helpers Available\n" + body
