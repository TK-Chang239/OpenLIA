"""Built-in default Earnings Update template.

Codifies the section set the v1 ``earnings_update.yaml`` report produced
as a ``TemplateSpec`` so EU v2 ships a working report shape out of the
box. The migration seeds a ``report_eu_templates`` row from this.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec

_SECTIONS = [
    (
        "quick_take",
        "Quick Take",
        "One-paragraph verdict: beat/miss vs expectations and what it means.",
    ),
    (
        "market_reaction",
        "Market Reaction",
        "Price move on the print and why.",
    ),
    (
        "key_financials",
        "Key Financials",
        "Revenue, EPS, margins vs consensus and prior year.",
    ),
    (
        "operational_highlights",
        "Operational Highlights",
        "Segment and KPI movements that drove the quarter.",
    ),
    (
        "forward_guidance",
        "Forward Guidance",
        "Management guidance vs prior guidance and consensus.",
    ),
    (
        "earnings_call",
        "Earnings Call",
        "Notable management commentary and analyst Q&A signal.",
    ),
    (
        "risk_assessment",
        "Risk Assessment",
        "New or changed risks surfaced by the quarter.",
    ),
    (
        "thesis_check",
        "Thesis Check",
        "Does the quarter confirm or challenge the investment thesis.",
    ),
]


def build_default_template() -> TemplateSpec:
    """Build the eight-section built-in Earnings Update template."""
    return TemplateSpec(
        template_id="eu_default",
        name="Earnings Update (Default)",
        shape_description=(
            "Post-earnings scorecard assessing the quarter against "
            "expectations and the prior thesis."
        ),
        ticker_anchored=True,
        default_length="normal",
        sections=[
            SectionSpec(id=sid, title=title, intent=intent) for sid, title, intent in _SECTIONS
        ],
    )
