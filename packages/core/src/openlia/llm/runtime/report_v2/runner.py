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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlia.reports.frameworks.template_spec import TemplateSpec

from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
)

# Force registration of all deterministic + compute facts
from openlia.llm.runtime.report_v2.facts import helpers as _helpers  # noqa: F401
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.registry import default_registry
from openlia.llm.runtime.report_v2.framework_overlay import (
    apply_facts_overlay,
    load_overlay,
    overlay_section_emphasis,
    report_mode_label,
)
from openlia.llm.runtime.report_v2.freshness import (
    StaleDataError,
    check_freshness,
    oldest_data_as_of,
)
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
from openlia.llm.runtime.report_v2.mode_selector import ReportMode, select_report_mode
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
from openlia.llm.runtime.report_v2.peers import (
    InsufficientPeerSetError,
    count_peer_fundamentals,
)
from openlia.llm.runtime.report_v2.scanners import (
    MaterialEventError,
    catalyst_event_to_dict,
    scan_catalysts,
    scan_manifest,
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
from openlia.llm.runtime.report_v2.types import Fact
from openlia.llm.runtime.report_v2.validators import (
    NumericValidationError,
    validate_sections,
)
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
    "cover": 400,
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

DEFAULT_BRIEFS: dict[str, str] = {
    sid: _SECTION_BRIEFS.get(sid, f"Section: {sid}. Write a substantive analytical section.")
    for sid in (*BODY_SECTIONS_STOCK_INITIATION, *SYNTHESIS_SECTIONS_STOCK_INITIATION)
}

DEFAULT_SYSTEM_ROLE: str = "You are an equity research section writer."

DEFAULT_STYLE_GUIDE: str = (
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


@dataclass
class ReportRunOutput:
    schema: ReportSchema
    telemetry: ReportTelemetry
    # Compiled facts pack from W3 + post-W3 injectables (e.g. WS3-A
    # `catalysts_recent`). Exposed for diagnostics / tests; not part of the
    # serialised report.
    facts: dict[str, Any] | None = None


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
        system_role: str = DEFAULT_SYSTEM_ROLE,
        style_guide: str = DEFAULT_STYLE_GUIDE,
        max_retries: int = 1,
        sse_emitter: Callable[[Any], Awaitable[None]] | None = None,
        report_id: str | None = None,
        concurrency_limit: int | None = None,
        preflight_concurrency: int = 4,
        body_concurrency: int = 1,
        synthesis_concurrency: int = 1,
        language: str | None = None,
        freshness_override: bool = False,
        material_events_override: bool = False,
        peer_set_override: bool = False,
        report_mode_override: ReportMode | None = None,
        numeric_validation_override: bool = False,
        catalyst_pack_enabled: bool = True,
        template: TemplateSpec | None = None,
    ) -> None:
        # PR 1 — template resolution. When an explicit TemplateSpec is provided,
        # it takes precedence and the runner no longer requires `report_type` to
        # be a registered template. When None, look up via the default registry;
        # unknown report types now raise `UnknownTemplateError` from there.
        if template is None:
            # Importing the loaders package ensures default templates are registered
            # before the registry is consulted. Done lazily here to avoid an import
            # cycle (loaders depend on this module's constants).
            import openlia.reports.frameworks.loaders  # noqa: F401
            from openlia.reports.frameworks.registry import (
                default_registry as _template_registry,
            )

            template = _template_registry.get(report_type)
        self.template = template
        self.report_type = report_type
        self.ticker = ticker
        self.dispatcher = dispatcher
        self.websearch = websearch
        self.preflight_provider = preflight_provider
        self.body_writer = body_writer
        self.synthesis_writer = synthesis_writer
        self.system_role = system_role
        self.style_guide = style_guide
        # Per-user output language directive (`"zh-TW"`, `"both"`, or `None`/`"en"`).
        # Injected into every body/synthesis section prompt by the assemble helpers.
        self.language = language
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
        # When True, hard-block freshness violations are logged but the runner
        # proceeds. Default False: stale data refuses to render.
        self.freshness_override = freshness_override
        # When True, hard-block material events (Chapter 11, restatement, etc.)
        # detected after `data_as_of` are logged but the runner proceeds.
        self.material_events_override = material_events_override
        # When True, an insufficient peer set (<2 peers) is logged but the
        # runner proceeds. Default False: shipping a single-row peer table is
        # a P1 quality defect for an initiation report.
        self.peer_set_override = peer_set_override
        # When set, forces a specific industry overlay regardless of the
        # auto-selector output. Useful for misclassified or freshly-relisted
        # names. Defaults to None -> auto-selection runs.
        self.report_mode_override: ReportMode | None = report_mode_override
        # When True, hard numeric-validation failures are logged but the
        # runner proceeds. Default False: any hard failure raises
        # NumericValidationError.
        self.numeric_validation_override = numeric_validation_override
        # When True (default), the WS3-A catalyst-pack scanner runs after the
        # material-events scanner and before section dispatch, packing a
        # `catalysts_recent` Fact (list of catalyst dicts) into the facts
        # pack. Disable in tests where news scanning is undesirable.
        self.catalyst_pack_enabled = catalyst_pack_enabled
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
            # `catalysts_recent` is not registered in the FactRegistry — it is
            # injected directly after the WS3-A catalyst scanner runs (below).
            # Filter it out of the requested-facts set so compile_pack does
            # not raise on the unknown name.
            requested = sorted(
                {n for names in framework.values() for n in names if n != "catalysts_recent"}
            )
            pack = compile_pack(
                registry=default_registry,
                manifest=manifest.entries,
                requested_facts=requested,
                subject_ticker=self.ticker,
            )
            self.telemetry.record_wave("W3_facts", duration_ms=int((time.monotonic() - t0) * 1000))

            # WS10-B: per-fact freshness gate. Runs after facts are compiled
            # and before any section generation. Hard-block violations refuse
            # to render unless `freshness_override=True`, in which case the
            # runner proceeds and surfaces a STALE DATA cover banner via
            # telemetry.
            now = datetime.now(UTC)
            violations = check_freshness(pack.facts, as_of=now)
            hard = [v for v in violations if v.severity == "hard_block"]
            banner_oldest = oldest_data_as_of(pack.facts)
            banner_violations: list[dict[str, Any]] = [
                {
                    "fact_name": v.fact_name,
                    "data_as_of": (
                        v.data_as_of.isoformat()
                        if isinstance(v.data_as_of, datetime)
                        else v.data_as_of
                    ),
                    "age_days": v.age_days,
                    "budget_days": v.budget_days,
                    "severity": v.severity,
                }
                for v in violations
            ]
            self.telemetry.record_freshness_banner(
                oldest_data_as_of=(
                    banner_oldest.isoformat()
                    if isinstance(banner_oldest, datetime)
                    else banner_oldest
                ),
                violations=banner_violations,
                override=self.freshness_override,
            )
            if hard and not self.freshness_override:
                raise StaleDataError(hard)
            if hard:
                for v in hard:
                    print(
                        f"[runner] WARN stale fact {v.fact_name!r} "
                        f"(as_of={v.data_as_of}, age={v.age_days}d > "
                        f"budget={v.budget_days}d) — proceeding due to "
                        f"freshness_override=True",
                        flush=True,
                    )

            # WS3-B: material-events gate. Scans manifest news entries for
            # the seven event classes (Chapter 11, emergence, going-private,
            # M&A target, delisting, splits, restatements). Events dated
            # after the oldest data_as_of carry hard_block / warning_banner
            # severity; events on or before are demoted to informational.
            events = scan_manifest(
                manifest.entries,
                subject_ticker=self.ticker,
                as_of_date=banner_oldest,
            )
            hard_events = [e for e in events if e.severity == "hard_block"]
            banner_events: list[dict[str, Any]] = [
                {
                    "event_class": e.event_class,
                    "event_date": (e.event_date.isoformat() if e.event_date is not None else None),
                    "confidence": e.confidence,
                    "severity": e.severity,
                    "evidence": list(e.evidence),
                    "description": e.description,
                }
                for e in events
            ]
            self.telemetry.record_material_events_banner(
                events=banner_events,
                override=self.material_events_override,
            )
            if hard_events and not self.material_events_override:
                raise MaterialEventError(hard_events)
            if hard_events:
                for e in hard_events:
                    print(
                        f"[runner] WARN material event {e.event_class!r} "
                        f"detected (date={e.event_date}, "
                        f"confidence={e.confidence}) — proceeding due to "
                        f"material_events_override=True",
                        flush=True,
                    )

            # WS3-A: fresh-catalyst pack. Runs after material-events (so the
            # runner has already blocked on Chapter 11 / restatements before
            # we spend cycles on catalyst classification). Scans manifest
            # news entries for product announcements, customer-concentration
            # disclosures, hyperscaler capex prints, sovereign-AI deals,
            # export-control changes, material partnerships, and guidance
            # updates. Results are packed into the facts dict as
            # `catalysts_recent` (list of catalyst dicts with manifest-id
            # evidence) so body sections can cite them like any other source.
            #
            # The `catalyst_pack_enabled=False` runner kwarg skips the scan
            # cleanly (used by tests that don't want news scanning). When
            # skipped, `catalysts_recent` is injected as an empty list so the
            # framework's section facts slices still resolve.
            if self.catalyst_pack_enabled:
                catalysts = scan_catalysts(
                    manifest.entries,
                    subject_ticker=self.ticker,
                    as_of_date=banner_oldest,
                )
            else:
                catalysts = []
            catalyst_values: list[dict[str, Any]] = [catalyst_event_to_dict(c) for c in catalysts]
            # Evidence IDs across all catalysts form the source_ids list. When
            # no catalysts were found, fall back to manifest entry id=1 to
            # satisfy the Fact's `min_length=1` source_ids constraint — the
            # value list is empty in that case so prose treats it as "none".
            evidence_ids = sorted({eid for c in catalysts for eid in c.evidence})
            if not evidence_ids and manifest.entries:
                evidence_ids = [manifest.entries[0].id]
            elif not evidence_ids:
                evidence_ids = [1]
            pack.facts["catalysts_recent"] = Fact(
                name="catalysts_recent",
                value=catalyst_values,
                source_ids=evidence_ids,
                extractor="compute",
                depends_on=[],
                source_tier="derived",
            )
            print(
                f"[runner] catalyst-pack scan: enabled={self.catalyst_pack_enabled}, "
                f"hits={len(catalyst_values)}",
                flush=True,
            )

            # WS9: industry-mode selection. Pick one of four overlays
            # (generic / saas / semis / distressed) from facts + material
            # events; apply the matching JSON to both the facts framework
            # (per-section fact lists) and the section briefs (emphasis text
            # appended to base brief). Manual override takes precedence.
            mode_as_of: Any
            if isinstance(banner_oldest, datetime):
                mode_as_of = banner_oldest.date()
            elif isinstance(banner_oldest, str):
                try:
                    mode_as_of = datetime.fromisoformat(banner_oldest.rstrip("Z")).date()
                except ValueError:
                    mode_as_of = None
            else:
                mode_as_of = None
            auto_mode: ReportMode = select_report_mode(pack.facts, events, as_of=mode_as_of)
            if self.report_mode_override is not None:
                chosen_mode: ReportMode = self.report_mode_override
                auto_selected = False
            else:
                chosen_mode = auto_mode
                auto_selected = True
            overlay = load_overlay(chosen_mode)
            framework = apply_facts_overlay(framework, overlay)
            section_emphasis = overlay_section_emphasis(overlay)
            mode_label = report_mode_label(overlay)
            section_briefs: dict[str, str] = dict(DEFAULT_BRIEFS)
            for sid, emphasis in section_emphasis.items():
                base = section_briefs.get(sid, "")
                section_briefs[sid] = (base + "\n\n" + emphasis).strip() if base else emphasis
            self.telemetry.record_report_mode_banner(
                mode=chosen_mode,
                label=mode_label,
                auto_selected=auto_selected,
            )
            print(
                f"[runner] industry-mode overlay applied: mode={chosen_mode!r} "
                f"(auto_selected={auto_selected}, label={mode_label!r})",
                flush=True,
            )

            # WS2: peer-set sufficiency gate. An initiation report must carry
            # at least two peers; shipping a single-row peer table is a P1
            # quality defect. The override flag downgrades the failure to a
            # logged warning.
            peer_count = count_peer_fundamentals(manifest.entries, subject_ticker=self.ticker)
            if peer_count < 2 and not self.peer_set_override:
                raise InsufficientPeerSetError(peer_count)
            if peer_count < 2:
                print(
                    f"[runner] WARN insufficient peer set "
                    f"(peers={peer_count}, need>=2) — proceeding due to "
                    f"peer_set_override=True",
                    flush=True,
                )

            # W4: body sections
            await self._emit(ReportPhase(report_id=rid, phase="section_drafting"))
            t0 = time.monotonic()
            body_dispatches = [
                SectionDispatch(
                    section_id=sid,
                    prompt=assemble_body_section_prompt(
                        system_role=self.system_role,
                        style_guide=self.style_guide,
                        framework_brief=section_briefs[sid],
                        manifest=manifest,
                        facts_slice=pack.slice_for(framework[sid]),
                        word_target=DEFAULT_WORD_TARGETS[sid],
                        language=self.language,
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
                        framework_brief=section_briefs[sid],
                        manifest=manifest,
                        synthesis_hooks_bundle=bundle,
                        facts_slice=pack.slice_for(framework[sid]),
                        word_target=DEFAULT_WORD_TARGETS[sid],
                        language=self.language,
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

            # WS4 / P7: numeric reconciliation validator. Runs after all
            # sections are written and parsed. Hard failures (identity
            # equations, arithmetic disagreements, first-person voice,
            # tombstone phrases, year-label mismatches) raise
            # NumericValidationError unless `numeric_validation_override` is
            # set. Soft failures (numeric_not_in_facts,
            # missing_data_as_of) are surfaced via telemetry only.
            section_files: dict[str, str] = {
                r.section_id: r.markdown
                for r in (*body_results, *synth_results)
                if r.markdown is not None
            }
            numeric_report = validate_sections(
                section_files=section_files,
                facts=pack.facts,
            )
            for f in numeric_report.failures:
                self.telemetry.record_cross_section_finding(
                    check=f"numeric_consistency.{f.failure_type}",
                    sections=f.section_id,
                    detail=f.detail,
                )
            if numeric_report.hard_failures and not self.numeric_validation_override:
                raise NumericValidationError(numeric_report.hard_failures)
            if numeric_report.hard_failures:
                for f in numeric_report.hard_failures:
                    print(
                        f"[runner] WARN numeric validation {f.failure_type!r} "
                        f"in section {f.section_id!r}: {f.detail} — proceeding "
                        f"due to numeric_validation_override=True",
                        flush=True,
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
        return ReportRunOutput(schema=schema, telemetry=self.telemetry, facts=pack.facts)
