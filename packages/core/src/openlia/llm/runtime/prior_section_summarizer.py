"""Deterministic summarizer that converts a SectionDraft into a
PriorSection. No LLM. Used by the subagent runner to pass threading
context forward to subsequent subagents.

Word-budget contract: ``summary`` truncated to ``summary_word_cap`` words
(default 200). ``key_facts_for_threading`` capped at ``facts_cap`` entries
(default 5). Callers can pass values from the template's
``threading: {summary_word_cap, facts_cap}`` block.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.section_draft import PriorSection, SectionDraft

_SUMMARY_WORD_CAP = 200
_THREADING_FACTS_CAP = 5


def _truncate_words(text: str, cap: int = _SUMMARY_WORD_CAP) -> str:
    words = text.strip().split()
    if len(words) <= cap:
        return " ".join(words)
    return " ".join(words[:cap]) + "..."


def _metric_card_bullets(block: dict[str, Any], *, facts_cap: int) -> list[str]:
    bullets = []
    for m in (block.get("metrics") or [])[:facts_cap]:
        label = str(m.get("label", "")).strip()
        value = str(m.get("value", "")).strip()
        if label and value:
            bullets.append(f"{label}: {value}")
    return bullets


def _table_bullet(block: dict[str, Any]) -> str | None:
    headers = block.get("headers") or []
    rows = block.get("rows") or []
    if not headers or not rows:
        return None
    keys = [str(h.get("key", "")) for h in headers if isinstance(h, dict)]
    first_row = rows[0] if isinstance(rows[0], dict) else {}
    parts = [f"{k}={first_row.get(k)}" for k in keys[:3]]
    return f"table[{block.get('title', '')}]: " + ", ".join(parts)


def _chart_bullet(block: dict[str, Any]) -> str | None:
    title = block.get("title")
    if not title:
        return None
    return f"chart: {title}"


_CHART_TYPES = {
    "line_chart",
    "bar_chart",
    "area_chart",
    "pie_chart",
    "candlestick_chart",
    "waterfall_chart",
    "scatter_plot",
    "heatmap",
    "treemap",
    "combo_chart",
}


def summarize_section_draft(
    draft: SectionDraft,
    *,
    title: str,
    summary_word_cap: int = _SUMMARY_WORD_CAP,
    facts_cap: int = _THREADING_FACTS_CAP,
) -> PriorSection:
    """Collapse a SectionDraft into a PriorSection.

    ``summary`` is built by concatenating TextBlock contents (in order)
    and truncating to ``summary_word_cap`` words. ``key_facts_for_threading``
    is built by walking other block types and producing at most ``facts_cap``
    short bullets. Callers can pass values from the template's
    ``threading: {summary_word_cap, facts_cap}`` block; unset fields use the
    defaults (200 / 5) preserving existing behaviour.
    """
    text_parts: list[str] = []
    facts: list[str] = []

    for block in draft.blocks:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(str(block.get("content", "")))
        elif btype == "metric_cards":
            facts.extend(_metric_card_bullets(block, facts_cap=facts_cap))
        elif btype == "table":
            bullet = _table_bullet(block)
            if bullet:
                facts.append(bullet)
        elif btype in _CHART_TYPES:
            bullet = _chart_bullet(block)
            if bullet:
                facts.append(bullet)

    summary = _truncate_words(
        " ".join(text_parts).strip() or "(no narrative text)", cap=summary_word_cap
    )
    return PriorSection(
        section_id=draft.section_id,
        title=title,
        summary=summary,
        key_facts_for_threading=facts[:facts_cap],
    )
