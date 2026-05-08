"""Seed the Repository with fake reports for visual UI testing.

Run with:
    uv run python packages/server/scripts/seed_repo_fakes.py [--user-email EMAIL] [--reset]

The script is idempotent: each fake row carries `subject = "__seed_fakes__"`,
so repeated runs skip already-seeded rows. Pass `--reset` to delete the
previously seeded set first.

All payloads target ReportSchema 2.0 (callout_grid, timeline, bullet_list,
comparison_split, quote, top-level rail + citations). Not for production data.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select

from openlia_server.db import bootstrap, session as session_mod
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import RepoItem, Report

SEED_SUBJECT = "__seed_fakes__"

AAPL_INIT_MARKDOWN = """\
# Apple Inc. — Initiating at Buy

A credible re-rating path on Services compounding and AI-on-device, with
downside cushioned by a $165B net cash position.

We initiate AAPL at Buy with a 12-month price target of $245.
"""

AAPL_EARNINGS_MARKDOWN = """\
# AAPL · Q2 FY26 — Beat on Services, In-Line on iPhone

Q2 FY26 print: revenue and EPS beat consensus on Services strength;
gross margin +20bp ahead. Maintaining Buy and $245 PT.
"""


def _aapl_initiation_payload(generated: datetime) -> dict[str, Any]:
    """Schema 2.0 stock-initiation payload exercising the new block types."""
    return {
        "schema_version": "2.0",
        "department": "equity_research",
        "generated_at": generated.isoformat(),
        "page_furniture": {
            "header": {"left": "OpenLIA", "right": "Equity Research"},
            "footer": {
                "left": "Generated " + generated.strftime("%b %d, %Y"),
                "center": "Page {page}",
                "right": "Internal — not investment advice",
            },
            "disclaimer": "This is a placeholder report seeded for UI testing. Not investment advice.",
        },
        "cover": {
            "title": "Apple Inc. — Initiating at Buy",
            "subtitle": "Equity Research · Q2 FY26",
            "eyebrow": "Stock Initiation · " + generated.strftime("%b %d, %Y"),
            "ticker": "AAPL",
            "tagline": (
                "A credible re-rating path on Services compounding and AI-on-device, "
                "with downside cushioned by a $165B net cash position."
            ),
            "tldr": [
                "We initiate AAPL at Buy with a 12-month price target of $245. "
                "Services revenue compounded at 14.1% over the last five years and now "
                "contributes 26% of total revenue at 74% gross margin — a structural "
                "mix shift the market has yet to fully capitalize. [1]",
                "Vision Pro remains a ~$3.4B business — small, but a credible runway "
                "for spatial computing as content libraries deepen. We model it as ~1% "
                "of FY27 revenue, with optionality, not the thesis. [2]",
            ],
            "key_metrics": [
                {"label": "Ticker", "value": "AAPL · NASDAQ"},
                {"label": "Rating", "value": "Buy", "tag": {"label": "Buy", "tone": "positive"}},
                {"label": "Price Target (12M)", "value": "$245.00"},
                {"label": "Upside", "value": "+18.0%", "delta_direction": "up"},
                {"label": "Last Close", "value": "$207.62"},
            ],
        },
        "rail": {
            "verdict": {
                "rating": "Buy",
                "previous_rating": "Not Rated",
                "target": "$245.00",
                "upside": "+18.0%",
                "as_of": "Apr 29, 2026",
            },
            "quick_stats": [
                {"label": "Mkt Cap", "value": "$3.21T"},
                {"label": "P/E NTM", "value": "26.4x"},
                {"label": "EV/Sales", "value": "7.9x"},
                {"label": "FCF Yield", "value": "3.5%"},
                {"label": "Net Cash", "value": "$165B"},
                {"label": "52W Range", "value": "$164–$220"},
            ],
            "sparkline": {
                "label": "Last 60 days",
                "points": [
                    {"x": i, "y": 195 + (i % 7) * 0.6 + (0.3 if i > 30 else 0) * i}
                    for i in range(60)
                ],
            },
        },
        "sections": [
            {
                "id": "summary",
                "title": "Executive Summary",
                "blocks": [
                    {
                        "type": "text",
                        "content": (
                            "Apple is no longer a phone-cycle stock. Through five years of "
                            "post-pandemic noise, the iPhone installed base expanded from ~1.0B "
                            "to ~1.46B active devices [3], and the company has methodically "
                            "converted that base into recurring software-economics revenue: "
                            "App Store, services, advertising, and financial products."
                        ),
                    },
                    {
                        "type": "text",
                        "content": (
                            "We see three under-appreciated factors driving a re-rating: "
                            "(1) Services mix continuing to lift consolidated gross margin into "
                            "the 47–48% range, (2) a credible AI-on-device thesis as Apple "
                            "Intelligence matures into a paid tier in late FY26, and "
                            "(3) capital return remains a floor — buybacks reduced share count "
                            "by 3.1% in FY25 alone. [4]"
                        ),
                    },
                ],
            },
            {
                "id": "thesis",
                "title": "Investment Thesis",
                "blocks": [
                    {
                        "type": "key_finding",
                        "content": (
                            "Three pillars — Services mix, AI-on-device monetization, and "
                            "capital-return-driven share-count compression — together support "
                            "a 28x NTM multiple, a modest premium to the 5-yr mean of 25x."
                        ),
                    },
                    {
                        "type": "callout_grid",
                        "columns": 3,
                        "items": [
                            {
                                "eyebrow": "Pillar 01",
                                "title": "Services as the structural margin lever",
                                "description": (
                                    "Services now 26% of revenue at 74% GM. Each 100bp of mix "
                                    "shift = ~30bp consolidated GM expansion."
                                ),
                            },
                            {
                                "eyebrow": "Pillar 02",
                                "title": "AI-on-device as a re-rating catalyst",
                                "description": (
                                    "Apple Intelligence shifts from free feature to paid tier in "
                                    "late FY26. Conservative 15% attach on iPhone base = ~$8B "
                                    "high-margin run-rate."
                                ),
                            },
                            {
                                "eyebrow": "Pillar 03",
                                "title": "Capital return as a floor under the multiple",
                                "description": (
                                    "$110B annualized buyback + dividend program. Even at flat "
                                    "earnings, ~3% shrink/yr is meaningful in our terminal."
                                ),
                            },
                        ],
                    },
                ],
            },
            {
                "id": "financials",
                "title": "Financial Snapshot",
                "blocks": [
                    {
                        "type": "table",
                        "title": "Five-year operating picture ($B unless noted)",
                        "headers": [
                            {"key": "metric", "label": "Metric", "align": "left"},
                            {"key": "fy21", "label": "FY21", "align": "right"},
                            {"key": "fy22", "label": "FY22", "align": "right"},
                            {"key": "fy23", "label": "FY23", "align": "right"},
                            {"key": "fy24", "label": "FY24", "align": "right"},
                            {"key": "fy25", "label": "FY25", "align": "right"},
                        ],
                        "rows": [
                            {"metric": "Revenue", "fy21": "365.8", "fy22": "394.3", "fy23": "383.3", "fy24": "391.0", "fy25": "420.6"},
                            {"metric": "Gross profit", "fy21": "152.8", "fy22": "170.8", "fy23": "169.1", "fy24": "180.7", "fy25": "198.4"},
                            {"metric": "Operating income", "fy21": "108.9", "fy22": "119.4", "fy23": "114.3", "fy24": "123.2", "fy25": "134.7"},
                            {"metric": "Net income", "fy21": "94.7", "fy22": "99.8", "fy23": "97.0", "fy24": "103.9", "fy25": "112.2"},
                            {"metric": "EPS, diluted", "fy21": "5.61", "fy22": "6.11", "fy23": "6.13", "fy24": "6.71", "fy25": "7.40"},
                            {"metric": "GM %", "fy21": "41.8", "fy22": "43.3", "fy23": "44.1", "fy24": "46.2", "fy25": "47.2"},
                        ],
                    },
                    {
                        "type": "line_chart",
                        "title": "Services revenue, $B (FY20–FY25)",
                        "x_label": "Fiscal year",
                        "y_label": "Revenue ($B)",
                        "series": [
                            {
                                "name": "Services",
                                "data": [
                                    {"x": "FY20", "y": 53.8},
                                    {"x": "FY21", "y": 68.4},
                                    {"x": "FY22", "y": 78.1},
                                    {"x": "FY23", "y": 85.2},
                                    {"x": "FY24", "y": 96.2},
                                    {"x": "FY25", "y": 104.2},
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "id": "catalysts",
                "title": "Catalysts",
                "blocks": [
                    {
                        "type": "timeline",
                        "title": "Six events that move the model in the next 12 months",
                        "events": [
                            {
                                "when": "Jun 2026 · WWDC",
                                "what": "Apple Intelligence Pro tier announced",
                                "impact": "Confirms AI-on-device monetization step-up; our model uses 15% attach.",
                                "impact_tag": {"label": "+$245 → $258", "tone": "positive"},
                                "highlight": True,
                            },
                            {
                                "when": "Jul 2026",
                                "what": "FQ3 print + first Vision Pro 2 disclosures",
                                "impact": "Watch installed-base growth, services exiting +14%, and any guide on Vision Pro 2 launch window.",
                                "impact_tag": {"label": "+/−$8", "tone": "neutral"},
                            },
                            {
                                "when": "Sep 2026",
                                "what": "iPhone 17 launch",
                                "impact": "Channel checks suggest +3% builds y/y; sell-side at +1%.",
                                "impact_tag": {"label": "Constructive", "tone": "positive"},
                            },
                            {
                                "when": "Oct 2026",
                                "what": "FQ4 print",
                                "impact": "First quarter to reflect Apple Intelligence Pro attach rates.",
                            },
                        ],
                    },
                ],
            },
            {
                "id": "risks",
                "title": "Risks",
                "blocks": [
                    {
                        "type": "comparison_split",
                        "left": {
                            "title": "▲ Upside",
                            "tone": "positive",
                            "items": [
                                "Apple Intelligence Pro attach rate exceeds our 15% assumption.",
                                "Services GM stable at 74% in higher-content quarter.",
                                "Vision Pro 2 with sub-$2,000 price reignites volume narrative.",
                            ],
                        },
                        "right": {
                            "title": "▼ Downside",
                            "tone": "negative",
                            "items": [
                                "Google TAC — DOJ remedy ruling expected late June; worst case $20B annualized headwind.",
                                "FX — JPY weakness already in guide; further EUR slip drags Q3 revenue 30bp.",
                                "EU DMA — alt-app-store enforcement compresses App Store take rate.",
                            ],
                        },
                    },
                    {
                        "type": "pull_quote",
                        "text": "We see Services as the durable engine; hardware is the cyclic damper.",
                        "attribution": "OpenLIA Equity Research",
                    },
                ],
            },
        ],
        "citations": [
            {"id": "1", "title": "Apple Q2 FY26 10-Q", "source": "SEC", "date": "2026-04-30"},
            {"id": "2", "title": "Vision Pro unit estimates — internal model", "source": "OpenLIA"},
            {"id": "3", "title": "Apple installed base disclosures (FY21 → FY25 10-Ks)", "source": "SEC"},
            {"id": "4", "title": "Apple capital return program", "source": "Apple IR", "date": "2026-04-30"},
            {"id": "5", "title": "Visible Alpha consensus — AAPL", "source": "Visible Alpha"},
        ],
    }


def _aapl_earnings_payload(generated: datetime) -> dict[str, Any]:
    """Schema 2.0 earnings-update payload exercising QuoteBlock + tagged metrics."""
    return {
        "schema_version": "2.0",
        "department": "earnings_update",
        "generated_at": generated.isoformat(),
        "page_furniture": {
            "header": {"left": "OpenLIA", "right": "Earnings Update"},
            "footer": {
                "left": "Generated " + generated.strftime("%b %d, %Y · %H:%M ET"),
                "center": "Page {page}",
                "right": "Internal — not investment advice",
            },
            "disclaimer": "This is a placeholder report seeded for UI testing. Not investment advice.",
        },
        "cover": {
            "title": "AAPL · Q1 FY26 — Beat on Services, In-Line on iPhone",
            "subtitle": "Earnings Update · Q1 FY2026",
            "eyebrow": "Earnings Update · " + generated.strftime("%b %d, %Y") + " · 16:30 ET",
            "ticker": "AAPL",
            "tagline": (
                "Beat on Services and EPS; iPhone in-line. Maintain Buy, $245 PT — "
                "small upward tweaks to FY26 estimates."
            ),
            "tldr_label": "Verdict",
            "tldr": [
                "Q1 FY26 print is constructive: revenue +$0.7B vs consensus on Services "
                "strength, EPS +$0.06 ahead, gross margin 47.4% (highest Q2 in company "
                "history). Hardware mix moved ~110bp toward Services vs Q2 FY25.",
                "Q3 guidance midpoint ~$88.5B sits +10bp above consensus — enough to "
                "validate, not enough to force upward revisions. GM range midpoint "
                "+40bp ahead is the number to watch.",
            ],
            "key_metrics": [
                {
                    "label": "Revenue",
                    "value": "$94.2B",
                    "tag": {"label": "Beat +$0.7B", "tone": "positive"},
                    "context": "Cons. $93.5B · y/y +5.4%",
                },
                {
                    "label": "EPS, diluted",
                    "value": "$1.78",
                    "tag": {"label": "Beat +$0.06", "tone": "positive"},
                    "context": "Cons. $1.72 · y/y +9.9%",
                },
                {
                    "label": "Gross Margin",
                    "value": "47.4%",
                    "tag": {"label": "+20bp vs cons.", "tone": "positive"},
                    "context": "Cons. 47.2% · prior-yr 46.6%",
                },
                {
                    "label": "After-hours",
                    "value": "$211.04",
                    "delta": "+1.65%",
                    "delta_direction": "up",
                    "context": "Last close $207.62 · vol 4.8x",
                },
            ],
        },
        "rail": {
            "verdict": {
                "rating": "Buy",
                "target": "$245.00",
                "upside": "+18.0%",
                "as_of": "Apr 30, 2026 · post-print",
            },
            "quick_stats": [
                {"label": "Beats", "value": "7 of 10", "tag": {"label": "+", "tone": "positive"}},
                {"label": "Misses", "value": "2 of 10", "tag": {"label": "-", "tone": "negative"}},
                {"label": "In-line", "value": "1 of 10"},
                {"label": "EPS surprise", "value": "+3.5%", "tag": {"label": "+", "tone": "positive"}},
                {"label": "Rev. surprise", "value": "+0.7%", "tag": {"label": "+", "tone": "positive"}},
                {"label": "Lia signal", "value": "82 / 100"},
            ],
            "sparkline": {
                "label": "After-hours · AAPL",
                "points": [
                    {"x": i, "y": 207.6 if i < 12 else 209 + (i - 12) * 0.18}
                    for i in range(40)
                ],
            },
        },
        "sections": [
            {
                "id": "firstread",
                "title": "First Read",
                "blocks": [
                    {
                        "type": "text",
                        "content": (
                            "Apple delivered a clean beat on Services and EPS, with revenue "
                            "$0.7B above consensus and gross margin 20bp ahead. Hardware mix "
                            "moved ~110bp in favor of Services vs Q2 FY25, contributing ~60bp "
                            "to consolidated GM. The 47.4% GM print is the highest Q2 in "
                            "company history. [1]"
                        ),
                    },
                    {
                        "type": "key_finding",
                        "content": (
                            "Services growth at +15.2% y/y with stable 74% GM is the structural "
                            "story. Q3 guide midpoint +10bp above consensus validates the trend "
                            "without forcing immediate upward revisions."
                        ),
                    },
                ],
            },
            {
                "id": "pnl",
                "title": "P&L vs Consensus",
                "blocks": [
                    {
                        "type": "table",
                        "title": "Q1 FY26 actuals vs consensus ($B)",
                        "headers": [
                            {"key": "line", "label": "Line", "align": "left"},
                            {"key": "actual", "label": "Actual", "align": "right"},
                            {"key": "cons", "label": "Cons.", "align": "right"},
                            {"key": "delta_pct", "label": "Δ %", "align": "right"},
                            {"key": "yoy", "label": "y/y", "align": "right"},
                            {"key": "tag", "label": "Tag", "align": "right"},
                        ],
                        "rows": [
                            {"line": "Total revenue", "actual": "94.2", "cons": "93.5", "delta_pct": "+0.7%", "yoy": "+5.4%", "tag": "Beat"},
                            {"line": "iPhone", "actual": "45.1", "cons": "45.4", "delta_pct": "-0.7%", "yoy": "+1.0%", "tag": "In-line"},
                            {"line": "Services", "actual": "26.8", "cons": "26.0", "delta_pct": "+3.0%", "yoy": "+15.2%", "tag": "Beat"},
                            {"line": "Wearables, Home & Acc.", "actual": "8.4", "cons": "8.6", "delta_pct": "-2.5%", "yoy": "-1.0%", "tag": "Miss"},
                            {"line": "Mac", "actual": "7.9", "cons": "7.5", "delta_pct": "+5.7%", "yoy": "+10.4%", "tag": "Beat"},
                            {"line": "Gross profit", "actual": "44.6", "cons": "44.1", "delta_pct": "+1.1%", "yoy": "+7.2%", "tag": "Beat"},
                            {"line": "Operating income", "actual": "30.1", "cons": "29.4", "delta_pct": "+2.4%", "yoy": "+8.3%", "tag": "Beat"},
                            {"line": "Net income", "actual": "26.4", "cons": "25.5", "delta_pct": "+3.6%", "yoy": "+8.6%", "tag": "Beat"},
                            {"line": "EPS, diluted ($)", "actual": "1.78", "cons": "1.72", "delta_pct": "+3.5%", "yoy": "+9.9%", "tag": "Beat"},
                        ],
                    },
                ],
            },
            {
                "id": "guide",
                "title": "Q3 Guidance",
                "blocks": [
                    {
                        "type": "metric_cards",
                        "metrics": [
                            {
                                "label": "Q3 Revenue",
                                "value": "$87–90B",
                                "context": "+3% to +6% y/y · cons. $88.4B",
                                "highlight": True,
                            },
                            {
                                "label": "Q3 Gross Margin",
                                "value": "47.0–48.0%",
                                "context": "cons. 47.1% · midpoint +40bp",
                            },
                            {"label": "Q3 OpEx", "value": "$14.6–14.8B"},
                            {"label": "Tax Rate", "value": "~16.0%"},
                            {"label": "OI&E", "value": "~$50M"},
                            {
                                "label": "Capital Return",
                                "value": "+$110B auth.",
                                "context": "div +4% to $0.27 / sh",
                            },
                        ],
                    },
                ],
            },
            {
                "id": "call",
                "title": "Conference Call Highlights",
                "blocks": [
                    {
                        "type": "quote",
                        "text": (
                            "On the AI-on-device monetization question — we are ==moving "
                            "deliberately==, and we'll have ==more to say at WWDC==. The "
                            "opportunity is large; we want to get the experience right before "
                            "we get the price right."
                        ),
                        "speaker": "Tim Cook",
                        "role": "CEO",
                        "tag": {"label": "AI · monetization", "tone": "neutral"},
                        "timestamp": "17:21 · A&O 04",
                    },
                    {
                        "type": "quote",
                        "text": (
                            "Greater China returned to growth on a constant-currency basis. "
                            "The ==iPhone installed base in China hit an all-time high==, and "
                            "upgraders set a March-quarter record."
                        ),
                        "speaker": "Tim Cook",
                        "role": "CEO",
                        "tag": {"label": "china", "tone": "positive"},
                        "timestamp": "17:09 · A&O 01",
                    },
                    {
                        "type": "quote",
                        "text": (
                            "Q3 gross margin range reflects ==a small FX headwind from JPY "
                            "weakness== that we've absorbed in the guide; otherwise the "
                            "underlying mix story is consistent with Q2."
                        ),
                        "speaker": "Luca Maestri",
                        "role": "CFO",
                        "tag": {"label": "guide · qualifier", "tone": "warn"},
                        "timestamp": "17:03 · prepared",
                    },
                ],
            },
            {
                "id": "watch",
                "title": "What to Watch",
                "blocks": [
                    {
                        "type": "comparison_split",
                        "left": {
                            "title": "▲ Upside watch",
                            "tone": "positive",
                            "items": [
                                "WWDC · Jun 8. Apple Intelligence Pro tier monetization framework.",
                                "iPhone 17 channel checks. Foxconn April reads suggest +3% builds y/y.",
                                "Services GM stability at 74% in a higher-content quarter.",
                            ],
                        },
                        "right": {
                            "title": "▼ Downside watch",
                            "tone": "negative",
                            "items": [
                                "Google TAC — DOJ remedy ruling expected late June. Worst case $20B annualized.",
                                "FX — JPY weakness already in guide; further EUR slip would drag Q3 revenue 30bp.",
                                "EU DMA — alt-app-store enforcement could compress App Store take rate.",
                            ],
                        },
                    },
                ],
            },
        ],
        "citations": [
            {"id": "1", "title": "Apple Q2 FY26 Press Release & Data Summary", "source": "apple.com", "date": "2026-04-30 · 16:30 ET"},
            {"id": "2", "title": "Q2 FY26 Earnings Conference Call · live transcript", "source": "internal"},
            {"id": "3", "title": "Visible Alpha consensus — AAPL Q2 FY26 (frozen 16:00 ET)", "source": "Visible Alpha"},
            {"id": "4", "title": "Form 8-K — Q2 FY26 Financial Statements & Notes", "source": "SEC", "date": "2026-04-30 · 16:33 ET"},
            {"id": "5", "title": "OpenLia — AAPL Initiation Report (Apr 29)", "source": "internal"},
        ],
    }


def _placeholder_payload(title: str, department: str, generated: datetime) -> dict[str, Any]:
    """Minimal valid 2.0 schema for placeholder rows.

    The fetch endpoint validates against ReportSchema, so a non-rich row still
    needs a well-formed payload — empty cover/sections will fail validation."""
    return {
        "schema_version": "2.0",
        "department": department,
        "generated_at": generated.isoformat(),
        "cover": {
            "title": title,
            "subtitle": "Seed fixture",
            "tagline": "Placeholder seed report (visual fixture only).",
            "eyebrow": "Placeholder · " + generated.strftime("%b %d, %Y"),
        },
        "sections": [
            {
                "id": "placeholder",
                "title": "Placeholder",
                "blocks": [
                    {
                        "type": "text",
                        "content": (
                            "This row is a seeded placeholder used to populate the Repository "
                            "for visual evaluation. No real content."
                        ),
                    }
                ],
            }
        ],
    }


@dataclass(frozen=True)
class FakeReport:
    title: str
    department: str
    generated: datetime
    saved: datetime
    payload: str = "placeholder"  # "placeholder" | "aapl_init" | "aapl_earnings"


def _dt(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 12, 0, 0, tzinfo=UTC)


# Titles + dates lifted from the OpenLIAv3 repository.html design rows.
FAKES: list[FakeReport] = [
    FakeReport("AAPL-initiation-coverage", "equity_research", _dt(4, 3), _dt(4, 5), payload="aapl_init"),
    FakeReport("AAPL-earnings-q1-2026", "earnings_update", _dt(4, 2), _dt(4, 4), payload="aapl_earnings"),
    FakeReport("morning-briefing-apr-04", "morning_briefing", _dt(4, 4), _dt(4, 4)),
    FakeReport("morning-briefing-apr-03", "morning_briefing", _dt(4, 3), _dt(4, 3)),
    FakeReport("q1-macro-briefing", "macro_research", _dt(4, 1), _dt(4, 1)),
    FakeReport("retail-flow-meme-cohort-apr", "retail_sentiment", _dt(3, 31), _dt(3, 31)),
    FakeReport("NVDA-q3-deep-dive", "equity_research", _dt(3, 28), _dt(3, 29)),
    FakeReport("TSM-foundry-supply-chain-memo", "equity_research", _dt(3, 27), _dt(3, 28)),
    FakeReport("META-q4-earnings-recap", "earnings_update", _dt(3, 25), _dt(3, 26)),
    FakeReport("china-rare-earth-supply-memo", "macro_research", _dt(3, 22), _dt(3, 24)),
    FakeReport("secretary-weekly-recap-w14", "secretary", _dt(3, 22), _dt(3, 22)),
    FakeReport("MSFT-azure-ai-thesis", "equity_research", _dt(3, 20), _dt(3, 20)),
]


def _open_session():
    load_dotenv(".env", override=False)
    load_dotenv(".env.local", override=False)
    url = bootstrap.resolve_db_url()
    try:
        session_mod.get_engine()
    except RuntimeError:
        session_mod.configure_engine(url)
    return session_mod.SessionLocal()


def _resolve_user(db, email: str | None) -> User:
    if email:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            sys.exit(f"Error: no user with email {email!r}.")
        return user
    user = db.execute(select(User).order_by(User.created_at.asc())).scalars().first()
    if user is None:
        sys.exit(
            "Error: no users in DB. Run the setup wizard first or pass --user-email.",
        )
    return user


def _delete_existing_seed(db, user_id: str) -> int:
    rows = db.execute(
        select(Report).where(
            Report.user_id == user_id, Report.subject == SEED_SUBJECT
        )
    ).scalars().all()
    n = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    return n


def _build_payload(fake: FakeReport) -> tuple[dict[str, Any], str]:
    if fake.payload == "aapl_init":
        return _aapl_initiation_payload(fake.generated), AAPL_INIT_MARKDOWN
    if fake.payload == "aapl_earnings":
        return _aapl_earnings_payload(fake.generated), AAPL_EARNINGS_MARKDOWN
    return (
        _placeholder_payload(fake.title, fake.department, fake.generated),
        f"# {fake.title}\n\n_Placeholder seed report (visual fixture only)._\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-email", help="Seed for this user (default: first user)")
    parser.add_argument("--reset", action="store_true", help="Delete previously seeded fakes before inserting")
    args = parser.parse_args()

    db = _open_session()
    try:
        user = _resolve_user(db, args.user_email)
        print(f"Seeding for user: {user.email} ({user.id})")

        if args.reset:
            removed = _delete_existing_seed(db, user.id)
            print(f"Removed {removed} previously seeded report(s).")

        existing_titles = set(
            db.execute(
                select(Report.title).where(
                    Report.user_id == user.id, Report.subject == SEED_SUBJECT
                )
            )
            .scalars()
            .all()
        )

        created = 0
        skipped = 0
        for fake in FAKES:
            if fake.title in existing_titles:
                skipped += 1
                continue
            structured, markdown = _build_payload(fake)
            report = Report(
                id=str(uuid.uuid4()),
                user_id=user.id,
                department=fake.department,
                report_type="seed",
                title=fake.title,
                subject=SEED_SUBJECT,
                content_markdown=markdown,
                content_structured=structured,
                model_ref="seed:none",
            )
            report.created_at = fake.generated
            report.updated_at = fake.generated
            db.add(report)
            db.flush()

            item = RepoItem(
                id=str(uuid.uuid4()),
                user_id=user.id,
                report_id=report.id,
            )
            item.created_at = fake.saved
            db.add(item)
            created += 1

        db.commit()
        print(f"Created {created} fake report(s); skipped {skipped} already present.")
        print("Open /repository in the app to view.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
