"""WavedReportRunner — orchestrates six waves end-to-end."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from typing import Any

from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
)

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
from openlia.llm.runtime.report_v2.packer.parser import parse_section_file
from openlia.llm.runtime.report_v2.packer.validator import (
    cross_section_numeric_consistency,
    validate_section,
)
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

DEFAULT_WORD_TARGETS: dict[str, int] = {sid: 600 for sid in BODY_SECTIONS_STOCK_INITIATION} | {
    "competitive_advantages_and_weaknesses": 500,
    "risk_analysis": 500,
    "investment_recommendation": 400,
    "cover": 250,
}

_SECTION_BRIEFS: dict[str, str] = {
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
        "Section: valuation_analysis. Multiples, DCF, peer comp. Preferred "
        "exhibits: ``table`` for the peer multiples matrix, "
        "``chart:scatter`` for P/E vs. growth, ``comparison_split`` for "
        "bull / base / bear cases, ``waterfall_chart`` for a DCF bridge."
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
        "Section: investment_recommendation. Preferred exhibits: "
        "``rating_badge`` for the BUY/HOLD/SELL call with "
        "``previous_rating`` and ``change_date``, ``metric_cards`` for "
        "price target / upside / time horizon, ``pull_quote`` for the "
        "one-sentence thesis."
    ),
    "cover": (
        "Section: cover. Headline summary. Preferred content: a tldr list "
        "of 3-5 short bullets and ``key_metrics`` (the server already "
        "populates market cap and P/E). The cover renders best as text "
        "and metrics; leave exhibit blocks to the body sections."
    ),
}

DEFAULT_BRIEFS: dict[str, str] = {
    sid: _SECTION_BRIEFS.get(sid, f"Section: {sid}. Write a substantive analytical section.")
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
        sse_emitter: Callable[[Any], Awaitable[None]] | None = None,
        report_id: str | None = None,
        concurrency_limit: int | None = None,
        preflight_concurrency: int = 4,
        body_concurrency: int = 1,
        synthesis_concurrency: int = 1,
    ) -> None:
        if report_type != "stock_initiation":
            raise ValueError("only stock_initiation supported in v1")
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
        self.sse_emitter = sse_emitter
        self.report_id = report_id or uuid.uuid4().hex
        # concurrency_limit is a backward-compat alias that sets all three pools uniformly
        if concurrency_limit is not None:
            self.preflight_concurrency = concurrency_limit
            self.body_concurrency = concurrency_limit
            self.synthesis_concurrency = concurrency_limit
        else:
            self.preflight_concurrency = preflight_concurrency
            self.body_concurrency = body_concurrency
            self.synthesis_concurrency = synthesis_concurrency
        self.telemetry = ReportTelemetry()

    async def _emit(self, event: Any) -> None:
        if self.sse_emitter is not None:
            await self.sse_emitter(event)

    def _load_facts_framework(self) -> dict[str, list[str]]:
        path = (
            resources.files("openlia.llm.runtime.report_v2.frameworks")
            / "stock_initiation.facts.json"
        )
        return json.loads(path.read_text())["sections"]

    async def run(self) -> ReportRunOutput:
        print(f"[runner] starting run for ticker={self.ticker!r}", flush=True)
        framework = self._load_facts_framework()
        all_section_ids = list(
            (*BODY_SECTIONS_STOCK_INITIATION, *SYNTHESIS_SECTIONS_STOCK_INITIATION)
        )
        rid = self.report_id
        preflight_sem = asyncio.Semaphore(self.preflight_concurrency)
        body_sem = asyncio.Semaphore(self.body_concurrency)
        synthesis_sem = asyncio.Semaphore(self.synthesis_concurrency)

        await self._emit(
            ReportStart(
                report_id=rid,
                department="equity_research",
                mode=self.report_type,
                section_titles=all_section_ids,
            )
        )

        try:
            # W1: baseline fetch
            await self._emit(ReportPhase(report_id=rid, phase="fetching_data"))
            t0 = time.monotonic()
            manifest = await run_baseline(
                catalog=materialize(BASELINE_STOCK_INITIATION, ticker=self.ticker),
                dispatcher=self.dispatcher,
            )
            self.telemetry.record_wave(
                "W1_baseline", duration_ms=int((time.monotonic() - t0) * 1000)
            )

            # W2: per-section preflight + aggregate + execute
            await self._emit(ReportPhase(report_id=rid, phase="planning"))
            t0 = time.monotonic()
            all_sections = (*BODY_SECTIONS_STOCK_INITIATION, *SYNTHESIS_SECTIONS_STOCK_INITIATION)
            known_facts = default_registry.names()

            async def _bounded_preflight(sid: str) -> Any:
                async with preflight_sem:
                    return await run_section_preflight(
                        provider=self.preflight_provider,
                        section_id=sid,
                        section_brief=DEFAULT_BRIEFS[sid],
                        manifest=manifest,
                        known_fact_names=known_facts,
                        ticker=self.ticker,
                    )

            preflights = await asyncio.gather(*(_bounded_preflight(sid) for sid in all_sections))
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
            self.telemetry.record_wave(
                "W2_preflight", duration_ms=int((time.monotonic() - t0) * 1000)
            )

            # W3: compile facts pack
            await self._emit(ReportPhase(report_id=rid, phase="loading_context"))
            t0 = time.monotonic()
            requested = sorted({n for names in framework.values() for n in names})
            pack = compile_pack(
                registry=default_registry,
                manifest=manifest.entries,
                requested_facts=requested,
                subject_ticker=self.ticker,
            )
            self.telemetry.record_wave("W3_facts", duration_ms=int((time.monotonic() - t0) * 1000))

            # W4: body sections
            await self._emit(ReportPhase(report_id=rid, phase="section_drafting"))
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
                concurrency_semaphore=body_sem,
            )
            for r in body_results:
                self.telemetry.record_section(r)
            self.telemetry.record_wave("W4_body", duration_ms=int((time.monotonic() - t0) * 1000))

            # W5: synthesis sections
            await self._emit(ReportPhase(report_id=rid, phase="editing"))
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
                concurrency_semaphore=synthesis_sem,
            )
            for r in synth_results:
                self.telemetry.record_section(r)
            self.telemetry.record_wave(
                "W5_synthesis", duration_ms=int((time.monotonic() - t0) * 1000)
            )

            # Cross-section consistency check (between W5 and W6)
            # Parse all sections with markdown and run the cross-section validator.
            # Findings with severity=="error" are logged as telemetry warnings —
            # no retries, as these emerge from multi-section state.
            all_completed = [r for r in (*body_results, *synth_results) if r.markdown is not None]
            parsed_sections = []
            for r in all_completed:
                try:
                    parsed_sections.append(parse_section_file(r.markdown))
                except Exception:
                    pass  # malformed section — skip; per-section validator caught it
            cross_findings = cross_section_numeric_consistency(parsed_sections)
            for finding in cross_findings:
                if finding.severity == "error":
                    self.telemetry.record_cross_section_finding(
                        check=finding.check,
                        sections=finding.section_id,
                        detail=finding.detail,
                    )

            # W6: assemble final report
            await self._emit(ReportPhase(report_id=rid, phase="finalizing"))
            t0 = time.monotonic()
            all_results = list(body_results) + list(synth_results)
            schema = assemble_report(
                manifest=manifest,
                facts_pack=pack,
                sections=all_results,
                department="equity_research",
                ticker=self.ticker,
                generated_at=datetime.now(UTC),
                on_omitted_block=self.telemetry.record_omitted_block,
            )
            self.telemetry.record_wave("W6_pack", duration_ms=int((time.monotonic() - t0) * 1000))

        except Exception as exc:
            await self._emit(
                ReportError(
                    report_id=rid,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
            )
            raise

        schema.telemetry = self.telemetry.snapshot()
        await self._emit(ReportComplete(report_id=rid, schema=schema.model_dump(mode="json")))
        return ReportRunOutput(schema=schema, telemetry=self.telemetry)
