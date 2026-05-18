from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Force registration of all block types
from openlia.llm.runtime.report_v2.packer.blocks import (  # noqa: F401
    text,
    table,
    chart_line,
    chart_bar,
    chart_area,
    chart_pie,
    chart_combo,
    chart_candlestick,
    chart_waterfall,
    chart_scatter,
    chart_heatmap,
    chart_treemap,
    metric_cards,
    key_finding,
    rating_badge,
    pull_quote,
    callout_grid,
    timeline,
    bullet_list,
    comparison_split,
    quote,
    group,
)

# Force registration of all deterministic + compute facts
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401

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
