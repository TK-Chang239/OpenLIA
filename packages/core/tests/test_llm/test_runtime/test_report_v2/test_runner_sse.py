"""Test SSE event emission from WavedReportRunner across wave boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from openlia.llm.runtime.events import ReportComplete, ReportError, ReportPhase, ReportStart

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


@pytest.mark.asyncio
async def test_runner_emits_lifecycle_events_in_order() -> None:
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

    emitted: list[object] = []

    async def capture(event: object) -> None:
        emitted.append(event)

    runner = WavedReportRunner(
        report_type="stock_initiation",
        ticker="NET.US",
        dispatcher=dispatcher,
        websearch=websearch,
        preflight_provider=preflight_provider,
        body_writer=writer,
        synthesis_writer=writer,
        sse_emitter=capture,
        # Static fixture; bypass freshness gate.
        freshness_override=True,
    )
    await runner.run()

    # First event must be ReportStart
    assert isinstance(emitted[0], ReportStart)
    assert emitted[0].report_id == runner.report_id

    # Last event must be ReportComplete with a non-empty schema payload
    assert isinstance(emitted[-1], ReportComplete)
    assert emitted[-1].report_id == runner.report_id
    assert emitted[-1].schema, "ReportComplete.schema must be non-empty"
    assert "cover" in emitted[-1].schema, "ReportComplete.schema must contain cover"
    # Telemetry must travel with the schema so it gets persisted into the
    # reports row (content_structured.telemetry) for post-hoc diagnosis.
    telemetry = emitted[-1].schema.get("telemetry")
    assert telemetry is not None, "ReportComplete.schema must embed telemetry"
    assert "section_states" in telemetry
    assert "wave_ms" in telemetry

    # Exactly 6 ReportPhase events (one per wave)
    phase_events = [e for e in emitted if isinstance(e, ReportPhase)]
    assert len(phase_events) == 6

    # No ReportError emitted on success
    assert not any(isinstance(e, ReportError) for e in emitted)

    # Order: ReportStart first, then phases interspersed, ReportComplete last
    types = [type(e) for e in emitted]
    assert types[0] is ReportStart
    assert types[-1] is ReportComplete
