"""Tests for the fresh-catalyst scanner (WS3 Part A)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

# Force registration of all deterministic + compute facts
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401

# Force registration of all block types
from openlia.llm.runtime.report_v2.packer.blocks import (  # noqa: F401
    bullet_list,
    callout_grid,
    chart_area,
    chart_bar,
    chart_candlestick,
    chart_combo,
    chart_heatmap,
    chart_line,
    chart_pie,
    chart_scatter,
    chart_treemap,
    chart_waterfall,
    comparison_split,
    group,
    key_finding,
    metric_cards,
    pull_quote,
    quote,
    rating_badge,
    table,
    text,
    timeline,
)
from openlia.llm.runtime.report_v2.runner import WavedReportRunner
from openlia.llm.runtime.report_v2.scanners.catalyst_pack import (
    CatalystEvent,
    CatalystScanner,
    catalyst_event_to_dict,
    scan_catalysts,
)
from openlia.llm.runtime.report_v2.types import ManifestEntry

FIXTURE = (
    Path(__file__).parent.parent.parent.parent.parent
    / "fixtures"
    / "report_v2"
    / "eodhd_fundamentals_net.json"
)


def _news_entry(
    *,
    entry_id: int = 1,
    identifier: str = "financial_news/NVDA.US",
    articles: list[dict[str, Any]],
) -> ManifestEntry:
    return ManifestEntry(
        id=entry_id,
        kind="fetch",
        provider="eodhd",
        identifier=identifier,
        raw_payload=articles,
        retrieved_at="2026-05-19T12:00:00Z",
    )


def _article(
    *,
    title: str,
    content: str = "",
    article_date: str = "2026-03-18",
    link: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"date": article_date, "title": title, "content": content}
    if link is not None:
        out["link"] = link
    return out


# ---------------------------------------------------------------------------
# Positive fixtures — one per catalyst class
# ---------------------------------------------------------------------------


def test_product_announcement_positive_gtc_rubin() -> None:
    """Canonical NVDA / GTC 2026 case: 'NVIDIA unveils Vera Rubin platform at
    GTC 2026; cumulative AI sales visibility tops $1 trillion'."""
    entry = _news_entry(
        articles=[
            _article(
                title=(
                    "NVIDIA unveils Vera Rubin platform at GTC 2026; "
                    "cumulative AI sales visibility tops $1 trillion"
                ),
                content=(
                    "NVIDIA today unveiled the next-generation Vera Rubin "
                    "platform at the GTC 2026 keynote. The company also "
                    "disclosed that cumulative AI sales visibility tops "
                    "$1 trillion across the Blackwell + Rubin roadmap."
                ),
                article_date="2026-03-18",
                link="https://example.com/nvda/gtc-2026",
            )
        ]
    )
    events = scan_catalysts(
        [entry],
        subject_company="NVIDIA",
        subject_ticker="NVDA",
    )
    product_events = [e for e in events if e.catalyst_class == "product_announcement"]
    seen_classes = [e.catalyst_class for e in events]
    assert product_events, f"expected product_announcement, got {seen_classes}"
    rubin = product_events[0]
    assert rubin.confidence == "high"
    assert rubin.event_date == date(2026, 3, 18)
    assert rubin.evidence == [1]
    assert rubin.source_url == "https://example.com/nvda/gtc-2026"
    assert rubin.relevance_score > 0.7
    assert "Vera Rubin" in rubin.title or "Rubin" in rubin.summary


def test_product_announcement_negative_marketing_fluff() -> None:
    """Generic press copy without product-launch verbs does not fire."""
    entry = _news_entry(
        articles=[
            _article(
                title="NVIDIA reports record quarterly revenue",
                content="NVIDIA beat consensus and raised full-year guidance.",
                article_date="2026-02-22",
            )
        ]
    )
    events = scan_catalysts([entry], subject_ticker="NVDA")
    classes = [e.catalyst_class for e in events]
    assert "product_announcement" not in classes


def test_customer_concentration_positive_tsmc_apple() -> None:
    """'TSMC discloses Apple represents 25% of revenue in 10-K' -> fires."""
    entry = _news_entry(
        identifier="financial_news/TSM.US",
        articles=[
            _article(
                title="TSMC 10-K discloses Apple represents 25% of total revenue",
                content=(
                    "In its annual report TSMC disclosed that Apple, its "
                    "single largest customer, represents 25% of total "
                    "revenue. The top five customers together account "
                    "for roughly 60% of revenue."
                ),
                article_date="2026-04-10",
            )
        ],
    )
    events = scan_catalysts(
        [entry],
        subject_company="Taiwan Semiconductor",
        subject_ticker="TSM",
    )
    ccd = [e for e in events if e.catalyst_class == "customer_concentration_disclosure"]
    seen = [e.catalyst_class for e in events]
    assert ccd, f"expected customer_concentration_disclosure, got {seen}"
    assert ccd[0].confidence in {"high", "medium"}


def test_customer_concentration_negative_growth_news() -> None:
    """Generic customer-growth headline does not fire."""
    entry = _news_entry(
        articles=[
            _article(
                title="ACME signs new enterprise customer",
                content="ACME added a Fortune 500 customer this quarter.",
                article_date="2026-04-10",
            )
        ]
    )
    events = scan_catalysts([entry], subject_ticker="ACME")
    assert all(e.catalyst_class != "customer_concentration_disclosure" for e in events)


def test_hyperscaler_capex_positive_microsoft_80b() -> None:
    """'Microsoft raises FY26 capex to $80 billion' -> fires for an NVDA
    scan even without 'NVIDIA' in the article (industry-scope class)."""
    entry = _news_entry(
        articles=[
            _article(
                title="Microsoft raises FY26 capex to $80 billion",
                content=(
                    "Microsoft today disclosed that it raised its FY26 "
                    "capital expenditure guidance to $80 billion, citing "
                    "AI infrastructure build-out."
                ),
                article_date="2026-04-25",
            )
        ]
    )
    events = scan_catalysts(
        [entry],
        subject_company="NVIDIA",
        subject_ticker="NVDA",
    )
    hcx = [e for e in events if e.catalyst_class == "hyperscaler_capex_print"]
    assert hcx, f"expected hyperscaler_capex_print, got {[e.catalyst_class for e in events]}"
    # Industry-scope catalyst: name not required, but still relevant to NVDA.
    assert hcx[0].relevance_score >= 0.4


def test_hyperscaler_capex_negative_random_capex_mention() -> None:
    """A non-hyperscaler company mentioning capex does not fire."""
    entry = _news_entry(
        articles=[
            _article(
                title="Local utility plans $200 million capex program",
                content="A regional utility announced a five-year capex plan.",
                article_date="2026-02-01",
            )
        ]
    )
    events = scan_catalysts([entry], subject_ticker="NVDA")
    assert all(e.catalyst_class != "hyperscaler_capex_print" for e in events)


def test_sovereign_ai_deal_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="Saudi Arabia's AI infrastructure deal with NVIDIA announced",
                content=(
                    "Saudi Arabia's AI infrastructure programme today "
                    "announced a deal with NVIDIA to deploy a sovereign "
                    "AI cluster."
                ),
                article_date="2026-05-12",
            )
        ]
    )
    events = scan_catalysts(
        [entry],
        subject_company="NVIDIA",
        subject_ticker="NVDA",
    )
    s = [e for e in events if e.catalyst_class == "sovereign_ai_deal"]
    assert s, f"expected sovereign_ai_deal, got {[e.catalyst_class for e in events]}"
    assert s[0].confidence == "high"


def test_sovereign_ai_deal_negative_generic_ai_news() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="A startup launches a new AI assistant",
                content="The startup released a productivity AI tool.",
                article_date="2026-05-12",
            )
        ]
    )
    events = scan_catalysts([entry], subject_ticker="NVDA")
    assert all(e.catalyst_class != "sovereign_ai_deal" for e in events)


def test_export_control_change_positive_h20() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="BIS rule adds NVIDIA H20 chip to export controls",
                content=(
                    "The Bureau of Industry and Security issued a new BIS "
                    "rule restricting export of the H20 chip to certain "
                    "destinations under the entity list framework."
                ),
                article_date="2026-04-04",
            )
        ]
    )
    events = scan_catalysts(
        [entry],
        subject_company="NVIDIA",
        subject_ticker="NVDA",
    )
    ec = [e for e in events if e.catalyst_class == "export_control_change"]
    assert ec, f"expected export_control_change, got {[e.catalyst_class for e in events]}"
    assert ec[0].confidence in {"high", "medium"}


def test_export_control_change_negative_unrelated() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="Company announces share buyback",
                content="The company plans to repurchase $1B in stock.",
                article_date="2026-04-04",
            )
        ]
    )
    events = scan_catalysts([entry], subject_ticker="NVDA")
    assert all(e.catalyst_class != "export_control_change" for e in events)


def test_material_partnership_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="NVIDIA and OpenAI enter strategic partnership",
                content=(
                    "NVIDIA and OpenAI today announced a strategic "
                    "partnership covering a 10-year contract for AI "
                    "infrastructure."
                ),
                article_date="2026-03-01",
            )
        ]
    )
    events = scan_catalysts(
        [entry],
        subject_company="NVIDIA",
        subject_ticker="NVDA",
    )
    mp = [e for e in events if e.catalyst_class == "material_partnership"]
    assert mp, f"expected material_partnership, got {[e.catalyst_class for e in events]}"
    assert mp[0].confidence == "high"


def test_material_partnership_negative() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="NVIDIA hosts developer meet-up",
                content="An informal community event.",
                article_date="2026-03-01",
            )
        ]
    )
    events = scan_catalysts([entry], subject_ticker="NVDA")
    assert all(e.catalyst_class != "material_partnership" for e in events)


def test_guidance_update_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="NVIDIA raised full-year guidance after preliminary results",
                content=(
                    "NVIDIA today raised its full-year outlook, citing "
                    "preliminary results that exceeded internal targets."
                ),
                article_date="2026-04-02",
            )
        ]
    )
    events = scan_catalysts(
        [entry],
        subject_company="NVIDIA",
        subject_ticker="NVDA",
    )
    gu = [e for e in events if e.catalyst_class == "guidance_update"]
    assert gu, f"expected guidance_update, got {[e.catalyst_class for e in events]}"
    assert gu[0].confidence == "high"


def test_guidance_update_negative_no_action_verb() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="NVIDIA hosts industry summit",
                content="A roundtable on AI policy.",
                article_date="2026-04-02",
            )
        ]
    )
    events = scan_catalysts([entry], subject_ticker="NVDA")
    assert all(e.catalyst_class != "guidance_update" for e in events)


# ---------------------------------------------------------------------------
# General behaviour
# ---------------------------------------------------------------------------


def test_unrelated_news_returns_empty() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="Markets close higher on Friday",
                content="Stocks finished the week up across the board.",
                article_date="2026-05-15",
            )
        ]
    )
    events = scan_catalysts([entry], subject_ticker="NVDA")
    assert events == []


def test_no_news_entries_returns_empty() -> None:
    fundamentals = ManifestEntry(
        id=1,
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/NVDA.US",
        raw_payload={"General": {"Code": "NVDA"}},
        retrieved_at="2026-05-19T12:00:00Z",
    )
    events = scan_catalysts([fundamentals], subject_ticker="NVDA")
    assert events == []


def test_scanner_class_round_trip() -> None:
    scanner = CatalystScanner(subject_ticker="NVDA", company_names=["NVIDIA"])
    entry = _news_entry(
        articles=[
            _article(
                title="NVIDIA unveils next-generation Rubin platform",
                content="NVIDIA today unveiled the next-generation Rubin GPU.",
                article_date="2026-03-18",
            )
        ]
    )
    events = scanner.scan(
        manifest_entries=[entry],
        subject_company="NVIDIA",
        subject_ticker="NVDA",
    )
    assert any(e.catalyst_class == "product_announcement" for e in events)


def test_envelope_payload_with_items_key() -> None:
    entry = ManifestEntry(
        id=1,
        kind="fetch",
        provider="eodhd",
        identifier="financial_news/NVDA.US",
        raw_payload={
            "items": [
                {
                    "title": "NVIDIA unveils next-generation chip",
                    "content": "Unveiled today at GTC.",
                    "date": "2026-03-18",
                }
            ]
        },
        retrieved_at="2026-05-19T12:00:00Z",
    )
    events = scan_catalysts([entry], subject_ticker="NVDA")
    assert any(e.catalyst_class == "product_announcement" for e in events)


def test_catalyst_event_to_dict_roundtrip() -> None:
    ev = CatalystEvent(
        catalyst_class="product_announcement",
        event_date=date(2026, 3, 18),
        confidence="high",
        title="NVIDIA unveils Rubin",
        summary="NVIDIA unveiled the Rubin platform at GTC 2026.",
        evidence=[1, 2],
        source_url="https://example.com/gtc",
        relevance_score=0.85,
    )
    d = catalyst_event_to_dict(ev)
    assert d["catalyst_class"] == "product_announcement"
    assert d["event_date"] == "2026-03-18"
    assert d["evidence"] == [1, 2]
    assert d["source_url"] == "https://example.com/gtc"
    assert d["relevance_score"] == 0.85


def test_relevance_score_increases_with_name_match() -> None:
    """The same strong pattern lands with a higher relevance score when the
    subject name is present in the article."""
    e_with_name = _news_entry(
        articles=[
            _article(
                title="NVIDIA unveils next-generation Rubin platform",
                content="NVIDIA unveiled the platform.",
                article_date="2026-03-18",
            )
        ]
    )
    e_without_name = _news_entry(
        entry_id=2,
        articles=[
            _article(
                title="An unnamed semiconductor company unveils a next-generation product",
                content="The product was unveiled today.",
                article_date="2026-03-18",
            )
        ],
    )
    events_with = [
        e
        for e in scan_catalysts(
            [e_with_name],
            subject_company="NVIDIA",
            subject_ticker="NVDA",
        )
        if e.catalyst_class == "product_announcement"
    ]
    events_without = [
        e
        for e in scan_catalysts(
            [e_without_name],
            subject_company="NVIDIA",
            subject_ticker="NVDA",
        )
        if e.catalyst_class == "product_announcement"
    ]
    assert events_with and events_without
    assert events_with[0].relevance_score > events_without[0].relevance_score


def test_multiple_catalyst_classes_in_single_article() -> None:
    """One article can carry multiple catalyst classes (e.g. a product
    announcement + a hyperscaler capex print + a partnership)."""
    entry = _news_entry(
        articles=[
            _article(
                title=(
                    "NVIDIA unveils Rubin platform; strategic partnership with "
                    "Microsoft on AI capital expenditure"
                ),
                content=(
                    "NVIDIA today unveiled the Rubin platform and announced a "
                    "strategic partnership with Microsoft, which raised its "
                    "FY26 capex to $80 billion citing AI infrastructure."
                ),
                article_date="2026-03-18",
            )
        ]
    )
    events = scan_catalysts(
        [entry],
        subject_company="NVIDIA",
        subject_ticker="NVDA",
    )
    classes = {e.catalyst_class for e in events}
    assert {"product_announcement", "material_partnership", "hyperscaler_capex_print"} <= classes


# ---------------------------------------------------------------------------
# Runner integration
# ---------------------------------------------------------------------------


def _good_section_md(section_id: str) -> str:
    body = " ".join(["word"] * 500) + " [1]."
    return f"""---
section_id: {section_id}
title: {section_id.replace("_", " ").title()}
sources_used: [1]
synthesis_hooks:
  thesis_contribution: "Strong thesis"
  bull_case_inputs: ["Growth case [1]"]
  bear_case_inputs: ["Risk case [1]"]
---

## {section_id}

{body}
"""


def _extract_section_id(prompt: str) -> str:
    for line in prompt.splitlines():
        if "Section:" in line:
            return line.split("Section:")[1].split(".")[0].strip().lower().replace(" ", "_")
    return "company_overview"


@pytest.mark.asyncio
async def test_runner_populates_catalysts_recent_when_enabled() -> None:
    """When `catalyst_pack_enabled=True` (default), the runner runs the
    scanner over manifest news entries and packs the result into
    `pack.facts['catalysts_recent']`."""
    fundamentals = json.loads(FIXTURE.read_text())
    # Surface a GTC-style article on the financial_news endpoint so the
    # scanner fires.
    news_payload = [
        {
            "date": "2026-03-18",
            "title": "NVIDIA unveils next-generation Rubin platform at GTC 2026",
            "content": (
                "NVIDIA today unveiled the next-generation Rubin platform "
                "at GTC 2026. Cumulative AI sales visibility tops $1 trillion."
            ),
            "link": "https://example.com/nvda/gtc-2026",
        }
    ]

    async def _dispatch(provider: str, tool: str, args: dict[str, Any]) -> Any:
        if tool == "get_fundamentals_data":
            return fundamentals
        if tool == "financial_news":
            return news_payload
        return {"ok": True}

    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = _dispatch

    websearch = AsyncMock()
    websearch.search.return_value = []

    preflight_provider = AsyncMock()
    preflight_provider.structured_output.return_value = {
        "searches": [],
        "fetches": [],
        "proposed_facts": [],
    }

    writer = AsyncMock()
    writer.write.side_effect = lambda prompt: _good_section_md(_extract_section_id(prompt))

    runner = WavedReportRunner(
        report_type="stock_initiation",
        ticker="NET.US",
        dispatcher=dispatcher,
        websearch=websearch,
        preflight_provider=preflight_provider,
        body_writer=writer,
        synthesis_writer=writer,
        freshness_override=True,
        peer_set_override=True,
        catalyst_pack_enabled=True,
    )
    report = await runner.run()
    assert report.schema is not None
    # The runner must have surfaced the GTC-style product_announcement
    # catalyst in the facts pack.
    assert report.facts is not None
    assert "catalysts_recent" in report.facts
    catalysts_value = report.facts["catalysts_recent"].value
    assert isinstance(catalysts_value, list)
    classes = {c["catalyst_class"] for c in catalysts_value}
    assert "product_announcement" in classes


@pytest.mark.asyncio
async def test_runner_skips_catalyst_pack_when_disabled() -> None:
    """When `catalyst_pack_enabled=False`, the scanner does not run and
    `catalysts_recent` is injected as an empty list (so framework slices
    still resolve)."""
    fundamentals = json.loads(FIXTURE.read_text())

    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = lambda provider, tool, args: (
        fundamentals if tool == "get_fundamentals_data" else {"ok": True}
    )

    websearch = AsyncMock()
    websearch.search.return_value = []

    preflight_provider = AsyncMock()
    preflight_provider.structured_output.return_value = {
        "searches": [],
        "fetches": [],
        "proposed_facts": [],
    }

    writer = AsyncMock()
    writer.write.side_effect = lambda prompt: _good_section_md(_extract_section_id(prompt))

    runner = WavedReportRunner(
        report_type="stock_initiation",
        ticker="NET.US",
        dispatcher=dispatcher,
        websearch=websearch,
        preflight_provider=preflight_provider,
        body_writer=writer,
        synthesis_writer=writer,
        freshness_override=True,
        peer_set_override=True,
        catalyst_pack_enabled=False,
    )
    report = await runner.run()
    assert report.facts is not None
    assert "catalysts_recent" in report.facts
    assert report.facts["catalysts_recent"].value == []
