from __future__ import annotations

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.sections.prompts import (
    assemble_body_section_prompt,
    assemble_synthesis_section_prompt,
)
from openlia.llm.runtime.report_v2.types import Fact


def _facts_slice() -> dict:
    return {
        "market_cap": Fact(
            name="market_cap", value=30_200_000_000, source_ids=[1], extractor="deterministic"
        ),
        "sector": Fact(
            name="sector", value="Technology", source_ids=[1], extractor="deterministic"
        ),
    }


def _manifest() -> Manifest:
    m = Manifest()
    m.append(
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/NET.US",
        raw_payload={},
        retrieved_at="t",
    )
    m.append(
        kind="search",
        provider="websearch",
        identifier="edge market 2025",
        raw_payload=[],
        retrieved_at="t",
    )
    return m


def test_body_prompt_orders_cached_prefix_before_dynamic() -> None:
    parts = assemble_body_section_prompt(
        system_role="You are a section writer.",
        style_guide="Use neutral institutional tone.",
        framework_brief="Section: industry_overview. Cover TAM, growth, key players.",
        manifest=_manifest(),
        facts_slice=_facts_slice(),
        word_target=600,
    )
    # Stable prefix (across runs) precedes variable prefix (manifest, facts).
    sys_idx = parts.find("You are a section writer")
    style_idx = parts.find("neutral institutional")
    brief_idx = parts.find("industry_overview")
    manifest_idx = parts.find("[1] eodhd")
    facts_idx = parts.find("market_cap")
    word_idx = parts.find("Word target")
    assert sys_idx < style_idx < brief_idx < manifest_idx < facts_idx < word_idx


def test_synthesis_prompt_includes_hooks_after_framework_brief() -> None:
    hooks_bundle = (
        "industry_overview:\n"
        "  thesis_contribution: Edge market expanding fast\n"
        "  bull_case_inputs: [Market 28% CAGR [12]]\n"
    )
    parts = assemble_synthesis_section_prompt(
        system_role="You are a synthesis writer.",
        style_guide="Sharpen the thesis.",
        framework_brief="Section: investment_recommendation.",
        manifest=_manifest(),
        synthesis_hooks_bundle=hooks_bundle,
        facts_slice=_facts_slice(),
        word_target=400,
    )
    fw_idx = parts.find("investment_recommendation")
    hooks_idx = parts.find("industry_overview:")
    assert fw_idx < hooks_idx


def test_facts_slice_renders_with_citation_tags() -> None:
    parts = assemble_body_section_prompt(
        system_role="x",
        style_guide="y",
        framework_brief="z",
        manifest=_manifest(),
        facts_slice=_facts_slice(),
        word_target=500,
    )
    assert "market_cap" in parts
    assert "sources: [1]" in parts or "[1]" in parts


def test_prompt_instructs_ranking_charts_to_plot_underlying_metric() -> None:
    """Ranking charts must plot the actual metric (share %, revenue $), not ordinal ranks.

    Real-world failure: equity research report for CRM emitted a horizontal bar chart
    with values [1, 2, 3, 4, 5, 6] for vendor ranking — the ordinal positions instead
    of market-share percentages, with Salesforce shown smallest despite leading the
    market. The prompt must steer the LLM toward plotting the underlying metric and
    sorting descending.
    """
    parts = assemble_body_section_prompt(
        system_role="x",
        style_guide="y",
        framework_brief="z",
        manifest=_manifest(),
        facts_slice=_facts_slice(),
        word_target=500,
    )
    assert "UNDERLYING METRIC VALUE" in parts
    assert "DESCENDING" in parts
    # Explicit prohibition on ordinal-rank values like 1, 2, 3, 4.
    assert "ordinal rank" in parts


def test_prompt_restricts_line_charts_to_ordered_series_of_4plus_points() -> None:
    """Line charts require a continuous/time-ordered x-axis with at least 4 points.

    Real-world failure: a line chart connected two unrelated scalars
    ("operating margin" → "revenue growth"), which falsely implies a series.
    Such 1-3 independent KPIs should use metric_cards instead.
    """
    parts = assemble_body_section_prompt(
        system_role="x",
        style_guide="y",
        framework_brief="z",
        manifest=_manifest(),
        facts_slice=_facts_slice(),
        word_target=500,
    )
    assert "four or more aligned points" in parts
    assert "four or more time periods" in parts
    # metric_cards is the correct alternative for 1-3 independent scalars.
    assert "metric_cards" in parts
