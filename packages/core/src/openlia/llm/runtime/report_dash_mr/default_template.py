"""Built-in default Morning Briefing template.

Codifies a general market-briefing section set as a ``TemplateSpec`` so
MB v2 ships a working report shape out of the box. The migration seeds a
``report_mb_templates`` row from this. MB runs are never ticker-anchored,
so ``ticker_anchored`` is ``False``.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec

_SECTIONS = [
    (
        "market_wrap",
        "Market Wrap",
        "Overnight and pre-open moves across major indices, futures, rates, "
        "FX, and commodities, with what drove them.",
    ),
    (
        "macro_economic_calendar",
        "Macro & Economic Calendar",
        "Today's scheduled data releases, central-bank events, and auctions, "
        "with the consensus and why each matters.",
    ),
    (
        "headlines",
        "Headlines",
        "The most market-relevant news since the prior session, grouped by "
        "theme with a one-line read on each.",
    ),
    (
        "themes_to_watch",
        "Themes to Watch",
        "Cross-asset narratives and sector rotations building underneath the "
        "tape that traders are positioning around.",
    ),
    (
        "outlook",
        "Outlook",
        "What to watch into the session and the key levels or catalysts that "
        "would shift the day's direction.",
    ),
]


def build_default_template() -> TemplateSpec:
    """Build the five-section built-in Morning Briefing template."""
    return TemplateSpec(
        template_id="mb_default",
        name="Morning Briefing (Default)",
        shape_description=(
            "Daily pre-market briefing covering overnight moves, the day's "
            "macro calendar, market-moving headlines, and the themes and "
            "catalysts to watch into the session."
        ),
        ticker_anchored=False,
        default_length="normal",
        sections=[
            SectionSpec(id=sid, title=title, intent=intent) for sid, title, intent in _SECTIONS
        ],
    )
