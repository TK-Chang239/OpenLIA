"""Default `stock_initiation` template loader — canonical source of truth.

After PR 2 the loader owns the section list, briefs, word targets, system role,
and style guide for the equity-research-initiation report. The runner re-exports
these names at module level for backward compatibility, but the canonical
definitions live here.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.freshness import FRESHNESS_BUDGETS
from openlia.llm.runtime.report_v2.scanners.catalyst_pack import ALL_CATALYST_CLASSES
from openlia.llm.runtime.report_v2.scanners.material_events import ALL_MATERIAL_EVENT_CLASSES
from openlia.llm.runtime.report_v2.validators.identity_equations import IdentityEquationSpec
from openlia.reports.frameworks.registry import default_registry
from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec

IDENTITY_EQUATIONS: tuple[IdentityEquationSpec, ...] = (
    IdentityEquationSpec(
        name="market_cap_check",
        lhs_a="current_price",
        op="mul",
        lhs_b="shares_outstanding",
        rhs="market_cap",
        tolerance_pct=2.0,
    ),
    IdentityEquationSpec(
        name="operating_income_check",
        lhs_a="revenue_ttm",
        op="mul",
        lhs_b="operating_margin_ttm",
        rhs="operating_income_ttm",
        tolerance_pct=0.5,
    ),
)

BODY_SECTION_IDS: tuple[str, ...] = (
    "company_overview",
    "industry_overview",
    "products_and_services",
    "business_model",
    "management_team",
    "historical_financials",
    "financial_analysis",
    "financial_projections",
    "valuation_analysis",
    "competitive_analysis",
    "recent_developments",
)

SYNTHESIS_SECTION_IDS: tuple[str, ...] = (
    "competitive_advantages_and_weaknesses",
    "risk_analysis",
    "investment_recommendation",
    "cover",
)

WORD_TARGETS: dict[str, int] = {sid: 600 for sid in BODY_SECTION_IDS} | {
    "competitive_advantages_and_weaknesses": 500,
    "risk_analysis": 500,
    "investment_recommendation": 400,
    "cover": 400,
}

SECTION_BRIEFS: dict[str, str] = {
    "company_overview": (
        "Section: company_overview. Cover ticker, sector, headquarters, "
        "headcount, founding date, key milestones, and core value "
        "proposition. Preferred exhibits: ``metric_cards`` for headline "
        "stats (market cap, P/E, revenue scale, headcount), ``key_finding`` "
        "for the positioning one-liner, ``pull_quote`` for the mission or "
        "CEO line."
    ),
    "industry_overview": (
        "Section: industry_overview. Describe market size, growth, "
        "structure, and where the company sits. Preferred exhibits: "
        "``chart:pie`` or ``chart:treemap`` for market share or "
        "segmentation, ``chart:bar`` for player ranking once there are "
        "three or more competitors, ``callout_grid`` for market segments, "
        "``table`` for TAM/SAM/SOM."
    ),
    "products_and_services": (
        "Section: products_and_services. Walk through product families, "
        "pricing, and customer types. Preferred exhibits: ``callout_grid`` "
        "with eyebrow + description for each product or module family, "
        "``table`` for a feature matrix, ``bullet_list`` for a tight "
        "list of capabilities."
    ),
    "business_model": (
        "Section: business_model. Cover revenue model, unit economics, "
        "moats, and distribution. Preferred exhibits: ``callout_grid`` for "
        "revenue pillars, ``chart:pie`` for revenue mix when disclosed, "
        "``comparison_split`` for the model vs. its nearest alternative, "
        "``key_finding``."
    ),
    "management_team": (
        "Section: management_team. Profile the C-suite and board with "
        "named individuals. Preferred exhibits: ``table`` for the officer "
        "and director list with role + background, ``key_finding`` for "
        "notable hires or departures."
    ),
    "historical_financials": (
        "Section: historical_financials. Show revenue, profitability, "
        "cash, and balance-sheet trends. Preferred exhibits: ``chart:combo``"
        " for revenue bars plus a margin line across multiple years, "
        "``chart:line`` for a single-metric trend, ``table`` for the "
        "multi-period KPI grid."
    ),
    "financial_analysis": (
        "Section: financial_analysis. Decompose margins, capital "
        "efficiency, and ratios. Preferred exhibits: ``chart:line`` for "
        "margin trends, ``table`` for KPIs vs. peers, ``waterfall_chart`` "
        "for a revenue or EBITDA bridge, ``key_finding``."
    ),
    "financial_projections": (
        "Section: financial_projections. Forward look on revenue, margins, "
        "FCF. Preferred exhibits: ``chart:line`` for the 3-5 year "
        "projection curve, ``chart:combo`` for revenue + growth %, "
        "``table`` for assumptions plus outputs."
    ),
    "valuation_analysis": (
        "Section: valuation_analysis. Multiples, DCF, peer comp — present "
        "the math, not a recommendation. Preferred exhibits: ``table`` for "
        "the peer multiples matrix (P/E, P/B, EV/EBITDA, PEG, 3Y growth — "
        "the server pre-builds the peer matrix from facts; you may augment "
        "with additional cited rows), ``chart:scatter`` for P/E vs. growth, "
        "``comparison_split`` for sensitivity scenarios labeled by "
        "methodology (e.g. 'Conservative · 18x EPS' vs 'Optimistic · "
        "28x EPS'), ``waterfall_chart`` for a DCF bridge. Do not author a "
        "single 'price target' — show the methodology's output and let the "
        "reader compare it to analyst consensus (rendered separately in "
        "Analyst View)."
    ),
    "competitive_analysis": (
        "Section: competitive_analysis. Name competitors and quantify "
        "where the company stands. Preferred exhibits: ``comparison_split``"
        " for subject vs. top rival, ``table`` for a feature or share "
        "matrix. Peer revenue ranking is owned by ``industry_overview`` — "
        "reference it in prose here and use a different exhibit family."
    ),
    "recent_developments": (
        "Section: recent_developments. Catalysts and news flow in the "
        "last twelve months. Preferred exhibits: ``timeline`` with dated "
        "events and ``impact_tag`` annotations whenever you have at least "
        "three dated events, ``key_finding`` for the single most important "
        "development, ``bullet_list`` for a tight catalog when dates are "
        "not available."
    ),
    "competitive_advantages_and_weaknesses": (
        "Section: competitive_advantages_and_weaknesses. Preferred "
        "exhibits: ``comparison_split`` for strengths (left tone positive) "
        "vs. weaknesses (right tone negative), ``callout_grid`` for moats "
        "by type, ``key_finding`` for the durable advantage."
    ),
    "risk_analysis": (
        "Section: risk_analysis. Preferred exhibits: ``callout_grid`` for "
        "risk categories (market, regulatory, execution, financial), "
        "``comparison_split`` for controlled vs. uncontrolled risks, "
        "``timeline`` for known risk events."
    ),
    "investment_recommendation": (
        "Section: Analyst View (information aggregation; no advocacy). The "
        "server pre-populates the rating distribution chart, consensus "
        "price-target metric_cards, and rating-badge from EODHD AnalystRatings "
        "— do NOT emit those blocks yourself. Your job: (1) a "
        "``comparison_split`` with 'Bull-case arguments' (left) vs "
        "'Bear-case arguments' (right), each item an argument observed in "
        "analyst notes / news / management commentary with a citation; "
        "(2) when news_search surfaced upgrades/downgrades, a ``table`` of "
        "recent rating changes (Date, Firm, Action, From -> To, Target "
        "Price), each row cited; (3) a closing 3-4 sentence prose paragraph "
        "summarizing what the consensus reflects, citing sources. Use "
        "third-person sourcing language: 'JPMorgan rates Buy [c12]', "
        "'consensus reflects a Hold [c1]'. Never write 'we recommend', "
        "'our rating', 'our target', 'we view this as'."
    ),
    "cover": (
        "Section: cover. Headline summary that drives the report's hero "
        "panel. Required blocks, in this order: (1) a ``pull_quote`` "
        "containing a single neutral framing sentence (what this report "
        "covers and why it matters; one full sentence, <=240 chars, no "
        "quotes around it, no recommendation language) — this becomes "
        "the cover tagline; (2) a ``bullet_list`` of 3-5 short, "
        "declarative ``Key findings`` — neutral, evidence-based, each "
        "phrased as an observation citable to sources, NOT as a "
        "recommendation; this is lifted as the Executive Summary; (3) a "
        "``metric_cards`` block with 4-5 headline metrics — this "
        "replaces the server-built deterministic metrics if present. "
        "Wrap one short prose paragraph (3-5 sentences) before and "
        "after the metric_cards to provide context. Do not emit "
        "exhibit blocks like charts or tables. Do not use phrases like "
        "'we recommend', 'our view', 'investment thesis' — frame as "
        "'what the data shows', not what to do about it."
    ),
}

SYSTEM_ROLE: str = "You are an equity research section writer."

STYLE_GUIDE: str = (
    "Institutional tone, precise, cited. INFORMATION-AGGREGATION ONLY: "
    "this report gathers and synthesizes information for the reader. "
    "Never recommend an action. Never write 'we recommend', 'we "
    "initiate at', 'our rating', 'our price target', 'our view is', "
    "'we view this as', 'investment thesis', or any first-person "
    "advocacy. Any buy/hold/sell language must be attributed to a "
    "specific cited source (e.g. 'JPMorgan rates Buy [c12]', "
    "'consensus reflects a Hold [c1]'). Frame conclusions as 'what "
    "the data shows', not 'what to do about it'."
)


def _section_brief(section_id: str) -> str:
    return SECTION_BRIEFS.get(
        section_id,
        f"Section: {section_id}. Write a substantive analytical section.",
    )


_THIRD_PERSON_ONLY_SECTIONS: frozenset[str] = frozenset({"investment_recommendation"})


def _build_sections(section_ids: tuple[str, ...]) -> tuple[SectionSpec, ...]:
    return tuple(
        SectionSpec(
            id=sid,
            title=sid.replace("_", " ").title(),
            brief=_section_brief(sid),
            word_target=WORD_TARGETS[sid],
            voice="third_person_only" if sid in _THIRD_PERSON_ONLY_SECTIONS else "any",
        )
        for sid in section_ids
    )


def load_stock_initiation_template() -> TemplateSpec:
    return TemplateSpec(
        name="stock_initiation",
        global_preface="",
        body_sections=_build_sections(BODY_SECTION_IDS),
        synthesis_sections=_build_sections(SYNTHESIS_SECTION_IDS),
        style_guide=STYLE_GUIDE,
        system_role=SYSTEM_ROLE,
        default_word_targets=dict(WORD_TARGETS),
        web_search_budget_default=20,
        freshness_budgets=dict(FRESHNESS_BUDGETS),
        identity_equations=IDENTITY_EQUATIONS,
        material_event_classes=tuple(sorted(ALL_MATERIAL_EVENT_CLASSES)),
        catalyst_classes=tuple(sorted(ALL_CATALYST_CLASSES)),
        industry_modes=("generic", "saas", "semis", "distressed"),
    )


default_registry.register("stock_initiation", load_stock_initiation_template)
