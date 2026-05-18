"""WavedReportRunner — orchestrates six waves end-to-end."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from typing import Any

# Force registration of all deterministic + compute facts
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.registry import default_registry
from openlia.llm.runtime.report_v2.manifest.aggregator import (
    aggregate_declarations,
    execute_aggregated,
)
from openlia.llm.runtime.report_v2.manifest.baseline import (
    BASELINE_STOCK_INITIATION,
    materialize,
    run_baseline,
)
from openlia.llm.runtime.report_v2.manifest.preflight import run_section_preflight
from openlia.llm.runtime.report_v2.packer.assembler import assemble_report

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
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.llm.runtime.report_v2.packer.validator import validate_section
from openlia.llm.runtime.report_v2.sections.dispatcher import (
    SectionDispatch,
    dispatch_sections,
)
from openlia.llm.runtime.report_v2.sections.prompts import (
    assemble_body_section_prompt,
    assemble_synthesis_section_prompt,
)
from openlia.llm.runtime.report_v2.sections.synthesis_hooks import (
    SynthesisHooksBundle,
    extract_hooks_from_section_result,
)
from openlia.llm.runtime.report_v2.telemetry import ReportTelemetry
from openlia.reports.schema import ReportSchema

BODY_SECTIONS_STOCK_INITIATION: tuple[str, ...] = (
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

SYNTHESIS_SECTIONS_STOCK_INITIATION: tuple[str, ...] = (
    "competitive_advantages_and_weaknesses",
    "risk_analysis",
    "investment_recommendation",
    "cover",
)

DEFAULT_WORD_TARGETS: dict[str, int] = {
    sid: 600 for sid in BODY_SECTIONS_STOCK_INITIATION
} | {
    "competitive_advantages_and_weaknesses": 500,
    "risk_analysis": 500,
    "investment_recommendation": 400,
    "cover": 250,
}

DEFAULT_BRIEFS: dict[str, str] = {
    sid: f"Section: {sid}. Write a substantive analytical section."
    for sid in (*BODY_SECTIONS_STOCK_INITIATION, *SYNTHESIS_SECTIONS_STOCK_INITIATION)
}


@dataclass
class ReportRunOutput:
    schema: ReportSchema
    telemetry: ReportTelemetry


class WavedReportRunner:
    def __init__(
        self,
        *,
        report_type: str,
        ticker: str,
        dispatcher: Any,
        websearch: Any,
        preflight_provider: Any,
        body_writer: Any,
        synthesis_writer: Any,
        system_role: str = "You are an equity research section writer.",
        style_guide: str = "Institutional tone, precise, cited.",
        max_retries: int = 1,
    ) -> None:
        assert report_type == "stock_initiation", "only stock_initiation supported in v1"
        self.report_type = report_type
        self.ticker = ticker
        self.dispatcher = dispatcher
        self.websearch = websearch
        self.preflight_provider = preflight_provider
        self.body_writer = body_writer
        self.synthesis_writer = synthesis_writer
        self.system_role = system_role
        self.style_guide = style_guide
        self.max_retries = max_retries
        self.telemetry = ReportTelemetry()

    def _load_facts_framework(self) -> dict[str, list[str]]:
        path = (
            resources.files("openlia.llm.runtime.report_v2.frameworks")
            / "stock_initiation.facts.json"
        )
        return json.loads(path.read_text())["sections"]

    async def run(self) -> ReportRunOutput:
        framework = self._load_facts_framework()

        # W1: baseline fetch
        t0 = time.monotonic()
        manifest = await run_baseline(
            catalog=materialize(BASELINE_STOCK_INITIATION, ticker=self.ticker),
            dispatcher=self.dispatcher,
        )
        self.telemetry.record_wave("W1_baseline", duration_ms=int((time.monotonic() - t0) * 1000))

        # W2: per-section preflight + aggregate + execute
        t0 = time.monotonic()
        all_sections = (*BODY_SECTIONS_STOCK_INITIATION, *SYNTHESIS_SECTIONS_STOCK_INITIATION)
        known_facts = default_registry.names()
        preflights = await asyncio.gather(*(
            run_section_preflight(
                provider=self.preflight_provider,
                section_id=sid,
                section_brief=DEFAULT_BRIEFS[sid],
                manifest=manifest,
                known_fact_names=known_facts,
            )
            for sid in all_sections
        ))
        for d in preflights:
            if d.proposed_facts:
                self.telemetry.record_proposed_facts(d.section_id, d.proposed_facts)
        work = aggregate_declarations(list(preflights))
        await execute_aggregated(
            work=work,
            manifest=manifest,
            dispatcher=self.dispatcher,
            websearch=self.websearch,
        )
        self.telemetry.record_wave("W2_preflight", duration_ms=int((time.monotonic() - t0) * 1000))

        # W3: compile facts pack
        t0 = time.monotonic()
        requested = sorted({n for names in framework.values() for n in names})
        pack = compile_pack(
            registry=default_registry,
            manifest=manifest.entries,
            requested_facts=requested,
        )
        self.telemetry.record_wave("W3_facts", duration_ms=int((time.monotonic() - t0) * 1000))

        # W4: body sections
        t0 = time.monotonic()
        body_dispatches = [
            SectionDispatch(
                section_id=sid,
                prompt=assemble_body_section_prompt(
                    system_role=self.system_role,
                    style_guide=self.style_guide,
                    framework_brief=DEFAULT_BRIEFS[sid],
                    manifest=manifest,
                    facts_slice=pack.slice_for(framework[sid]),
                    word_target=DEFAULT_WORD_TARGETS[sid],
                ),
                target_word_count=DEFAULT_WORD_TARGETS[sid],
                facts_slice=pack.slice_for(framework[sid]),
            )
            for sid in BODY_SECTIONS_STOCK_INITIATION
        ]
        body_results = await dispatch_sections(
            dispatches=body_dispatches,
            writer=self.body_writer,
            validator=validate_section,
            max_retries=self.max_retries,
            known_block_tags=default_block_registry.tags(),
        )
        for r in body_results:
            self.telemetry.record_section(r)
        self.telemetry.record_wave("W4_body", duration_ms=int((time.monotonic() - t0) * 1000))

        # W5: synthesis sections
        t0 = time.monotonic()
        hooks = [
            h
            for h in (extract_hooks_from_section_result(r) for r in body_results)
            if h is not None
        ]
        bundle = SynthesisHooksBundle(hooks=hooks).render()
        synth_dispatches = [
            SectionDispatch(
                section_id=sid,
                prompt=assemble_synthesis_section_prompt(
                    system_role=self.system_role,
                    style_guide=self.style_guide,
                    framework_brief=DEFAULT_BRIEFS[sid],
                    manifest=manifest,
                    synthesis_hooks_bundle=bundle,
                    facts_slice=pack.slice_for(framework[sid]),
                    word_target=DEFAULT_WORD_TARGETS[sid],
                ),
                target_word_count=DEFAULT_WORD_TARGETS[sid],
                facts_slice=pack.slice_for(framework[sid]),
            )
            for sid in SYNTHESIS_SECTIONS_STOCK_INITIATION
        ]
        synth_results = await dispatch_sections(
            dispatches=synth_dispatches,
            writer=self.synthesis_writer,
            validator=validate_section,
            max_retries=self.max_retries,
            known_block_tags=default_block_registry.tags(),
        )
        for r in synth_results:
            self.telemetry.record_section(r)
        self.telemetry.record_wave("W5_synthesis", duration_ms=int((time.monotonic() - t0) * 1000))

        # W6: assemble final report
        t0 = time.monotonic()
        all_results = list(body_results) + list(synth_results)
        schema = assemble_report(
            manifest=manifest,
            facts_pack=pack,
            sections=all_results,
            department="equity_research",
            ticker=self.ticker,
            generated_at=datetime.now(UTC),
        )
        self.telemetry.record_wave("W6_pack", duration_ms=int((time.monotonic() - t0) * 1000))

        return ReportRunOutput(schema=schema, telemetry=self.telemetry)
