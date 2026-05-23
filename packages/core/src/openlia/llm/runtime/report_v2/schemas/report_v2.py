"""Structured payload emitted by RunnerV2 at the end of a successful run.

The v2.2 pipeline previously HTML-rendered each block in the assembler and
shipped a single string to the frontend. That broke v1's rendering surface:
React's ReportRenderer dispatches on typed block dicts to produce branded
components (ReportCover, BlockRenderer, CitationsRail, charts), and HTML is
a one-way conversion away from that tree.

ReportV2 keeps the typed-block dicts intact so the frontend can render the
same way it renders v1 reports. The block payloads inside `sections[].blocks`
stay as plain dicts; the renderer dispatches on each dict's `type` field
(prose, table, kpi_strip, chart, quote_block, skip_banner, degraded_banner,
excel_attachment) and degrades unknown types to a visible placeholder.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from openlia.llm.runtime.report_v2.schemas.research_pool import Citation
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary
from openlia.llm.runtime.report_v2.schemas.verification_history import VerificationHistory


SectionStatus = Literal["OK", "SKIPPED", "DEGRADED"]


class ReportV2Cover(BaseModel):
    """Minimal cover for v2.2 reports.

    Currently synthesised from composer_inputs + the loaded template (A3);
    enriched later when the backend grows analyst-consensus and
    key-metrics emitters.
    """

    title: str
    eyebrow: str | None = None
    subtitle: str | None = None
    tagline: str | None = None
    ticker: str | None = None


class ReportV2Section(BaseModel):
    """One section of the report.

    `blocks` stays as a list of dicts on purpose — the frontend dispatches
    on `block["type"]` against the v2 block vocabulary (prose, table,
    kpi_strip, chart, quote_block, skip_banner, degraded_banner,
    excel_attachment). Strict typing would lock the LLM into a vocabulary
    that evolves; the renderer degrades unknown types gracefully.
    """

    id: str
    name: str
    status: SectionStatus = "OK"
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    skip_reason: str | None = None
    degraded_reason: str | None = None


class ReportV2(BaseModel):
    """Structured payload emitted on RunnerV2's Completed event.

    Mirrors what the v1 ReportRenderer reads (cover, sections, citations,
    run_summary, verification_history) so the frontend can wire v2 reports
    into the same React surface that renders v1 reports.
    """

    engine_version: str
    generated_at: datetime
    template_id: str
    template_name: str
    cover: ReportV2Cover
    sections: list[ReportV2Section] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    run_summary: RunSummary
    verification_history: VerificationHistory | None = None
