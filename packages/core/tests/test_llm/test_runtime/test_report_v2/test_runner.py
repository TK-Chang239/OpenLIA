from __future__ import annotations

import json
from pathlib import Path
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

FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "fixtures"
    / "report_v2"
    / "eodhd_fundamentals_net.json"
)


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
    if "industry_overview" in prompt:
        return "industry_overview"
    return "company_overview"


def _section_md_with_numeric_claim(section_id: str, cagr_value: str) -> str:
    """Return a well-formed section markdown that contains a specific revenue CAGR 3y claim."""
    body = " ".join(["word"] * 500) + f" revenue CAGR 3y of {cagr_value} [1]."
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


@pytest.mark.asyncio
async def test_runner_end_to_end_minimal() -> None:
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
    )
    report = await runner.run()

    assert report.schema.cover.ticker == "NET.US"
    assert report.telemetry.snapshot()["section_states"]["success"] >= 11
    assert len(report.schema.sections) == 15  # 11 body + 4 synthesis


@pytest.mark.asyncio
async def test_runner_records_cross_section_inconsistencies_in_telemetry() -> None:
    """Two body sections disagree on revenue CAGR 3y value; runner should
    record at least one cross-section finding in telemetry after the run."""
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

    # Two body sections claim different revenue CAGR 3y values; all others are generic.
    inconsistent_sections = {
        "company_overview": _section_md_with_numeric_claim("company_overview", "23.4%"),
        "historical_financials": _section_md_with_numeric_claim("historical_financials", "25.7%"),
    }

    def _write(prompt: str) -> str:
        sid = _extract_section_id(prompt)
        if sid in inconsistent_sections:
            return inconsistent_sections[sid]
        return _good_section_md(sid)

    writer = AsyncMock()
    writer.write.side_effect = _write

    runner = WavedReportRunner(
        report_type="stock_initiation",
        ticker="NET.US",
        dispatcher=dispatcher,
        websearch=websearch,
        preflight_provider=preflight_provider,
        body_writer=writer,
        synthesis_writer=writer,
    )
    report = await runner.run()

    findings = report.telemetry.snapshot()["cross_section_findings"]
    assert len(findings) >= 1, f"expected cross-section finding, got: {findings}"
    cagr_findings = [f for f in findings if "revenue cagr 3y" in f["detail"].lower()]
    assert cagr_findings, f"expected a revenue CAGR 3y finding, got: {findings}"
