"""Built-in TemplateSpec instances — one per ReportType.

These replace the per-``ReportType`` paragraph that previously lived in
``clients/llm_clarifier.py::_BUILTIN_TEMPLATE_SHAPES``. The structures
here are deliberately small starting shapes — Phase 1.5 will let users
upload their own templates with different section layouts.

Adding a new ``ReportType`` requires adding an entry here; the
``test_every_report_type_has_a_builtin`` test guards that.
"""

from __future__ import annotations

from ..schemas import ReportLength, ReportType
from .spec import SectionSpec, TemplateSpec

_INITIATION = TemplateSpec(
    template_id="initiation_default",
    name="Initiation (default)",
    shape_description=(
        "Comprehensive initiation: business overview, financial profile, "
        "competitive position, valuation (DCF + comps), risks, and "
        "recommendation. Long-form, written for someone who has not "
        "covered the name before."
    ),
    default_length=ReportLength.ELABORATIVE,
    sections=[
        SectionSpec(
            id="overview",
            title="Business Overview",
            intent=(
                "Describe what the company does, how it makes money, and "
                "the segment / geography mix that drives revenue today."
            ),
        ),
        SectionSpec(
            id="financial_profile",
            title="Financial Profile",
            intent=(
                "Lay out the multi-period revenue, margin, and cash-flow "
                "trajectory. Flag growth quality and balance-sheet posture."
            ),
        ),
        SectionSpec(
            id="competitive_position",
            title="Competitive Position",
            intent=(
                "Map the relevant peer set, the company's share / "
                "differentiation, and the structural drivers of any moat."
            ),
        ),
        SectionSpec(
            id="valuation",
            title="Valuation",
            intent=(
                "Present the DCF and comps output side by side. Explain "
                "which assumptions matter most for the central case."
            ),
            methodology_hints=["dcf", "comps"],
        ),
        SectionSpec(
            id="risks",
            title="Risks",
            intent=(
                "Enumerate the load-bearing risks — operational, financial, "
                "regulatory, market — that would invalidate the central case."
            ),
        ),
        SectionSpec(
            id="recommendation",
            title="Recommendation",
            intent=(
                "Synthesize the stance: rating, target, horizon, and the "
                "one-line catalyst path. Ground in the valuation section."
            ),
        ),
    ],
)

_UPDATE = TemplateSpec(
    template_id="update_default",
    name="Update (default)",
    shape_description=(
        "Targeted update: what changed since last coverage, what it means "
        "for the financial trajectory, and whether the view shifts. "
        "Written for someone already familiar with the name."
    ),
    default_length=ReportLength.NORMAL,
    sections=[
        SectionSpec(
            id="what_changed",
            title="What Changed",
            intent=(
                "Crisp narrative of the news / event that prompted the "
                "update. Anchor to dated sources."
            ),
        ),
        SectionSpec(
            id="financial_implications",
            title="Financial Implications",
            intent=(
                "Re-cut the relevant financial line(s) for the change — "
                "revenue, margin, capex, leverage — with quantified deltas."
            ),
        ),
        SectionSpec(
            id="view",
            title="View",
            intent=(
                "State whether the central case shifts. If the rating / "
                "target moves, say why; if it holds, say why the change "
                "is already in the model."
            ),
        ),
    ],
)

_SECTOR_RESEARCH = TemplateSpec(
    template_id="sector_research_default",
    name="Sector Research (default)",
    shape_description=(
        "Sector-level note: industry primer, the drivers shaping "
        "fundamentals, the competitive landscape and the cross-cutting "
        "themes that matter for stock selection."
    ),
    default_length=ReportLength.ELABORATIVE,
    sections=[
        SectionSpec(
            id="industry_primer",
            title="Industry Primer",
            intent=(
                "Set up the sector — size, growth, value-chain shape, key "
                "metrics readers will need throughout the rest of the note."
            ),
        ),
        SectionSpec(
            id="drivers",
            title="Drivers",
            intent=(
                "Identify the structural and cyclical drivers shaping "
                "fundamentals — demand, supply, pricing, regulation."
            ),
        ),
        SectionSpec(
            id="competitive_landscape",
            title="Competitive Landscape",
            intent=(
                "Map the major players, share dynamics, and emerging "
                "challengers worth watching."
            ),
        ),
        SectionSpec(
            id="themes",
            title="Themes",
            intent=(
                "Pull out 2-4 cross-cutting themes a generalist PM would "
                "act on, with the names most exposed to each."
            ),
        ),
    ],
)

_MORNING_BRIEF = TemplateSpec(
    template_id="morning_brief_default",
    name="Morning Brief (default)",
    shape_description=(
        "Short pre-market brief covering the overnight signals that "
        "should reshape today's watchlist. Headline-style, scannable."
    ),
    default_length=ReportLength.CONCISE,
    sections=[
        SectionSpec(
            id="overnight",
            title="Overnight",
            intent=(
                "Summarize the load-bearing overnight moves — macro, "
                "single-stock catalysts, cross-asset signals."
            ),
        ),
        SectionSpec(
            id="watchlist",
            title="Watchlist",
            intent=(
                "Surface 3-5 names worth a closer look today and the "
                "specific reason each one is on the list."
            ),
        ),
    ],
)

_EARNINGS_REVIEW = TemplateSpec(
    template_id="earnings_review_default",
    name="Earnings Review (default)",
    shape_description=(
        "Post-print analysis: what the quarter said, what it means for "
        "the model, and how the outlook shifts. Written same-day for "
        "someone who saw the press release but not the call."
    ),
    default_length=ReportLength.NORMAL,
    sections=[
        SectionSpec(
            id="quarter_highlights",
            title="Quarter Highlights",
            intent=(
                "Headline the prints that matter — revenue, margins, "
                "guidance, segment mix surprises — vs. consensus and "
                "the prior quarter."
            ),
        ),
        SectionSpec(
            id="financial_detail",
            title="Financial Detail",
            intent=(
                "Walk the financial line items the print moved most. "
                "Quantify the YoY / QoQ deltas and the implied trajectory."
            ),
        ),
        SectionSpec(
            id="outlook",
            title="Outlook",
            intent=(
                "Re-state the forward view: where guidance lands vs. the "
                "Street and what would change the view in the next two "
                "quarters."
            ),
        ),
    ],
)

BUILTIN_TEMPLATES: dict[ReportType, TemplateSpec] = {
    ReportType.INITIATION: _INITIATION,
    ReportType.UPDATE: _UPDATE,
    ReportType.SECTOR_RESEARCH: _SECTOR_RESEARCH,
    ReportType.MORNING_BRIEF: _MORNING_BRIEF,
    ReportType.EARNINGS_REVIEW: _EARNINGS_REVIEW,
}


def get_builtin(report_type: ReportType) -> TemplateSpec:
    """Return the default built-in TemplateSpec for a ReportType.

    Raises KeyError if no built-in is registered — the
    test_every_report_type_has_a_builtin test ensures this never fires
    in production but bare lookup keeps the failure mode loud.
    """
    return BUILTIN_TEMPLATES[report_type]
