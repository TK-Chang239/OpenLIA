"""Build the structured ReportV2 payload at the end of a v2.2 run.

Replaces the prior HTML-stringifying assembler. v1's React renderer (and
therefore v2's, after WS-B) dispatches on typed block dicts to produce
branded components (ReportCover, BlockRenderer, CitationsRail, charts), so
the backend has no business collapsing those dicts to HTML before they
reach the frontend.

Inputs come from the v2.2 pipeline:
  - sections          : assembled section dicts (id, name, status,
                        blocks, skip_reason, degraded_reason). Built by
                        runner_v2._stage_assemble from SectionOutput.
  - composer_inputs   : the original user inputs (ticker, prompt, …).
                        Used to synthesise the cover.
  - template_spec     : the loaded TemplateSpecV2. Provides template_id,
                        template_name, report_type for the cover eyebrow.
  - research_pool     : citation list shipped through verbatim.
  - run_summary       : populated by the runner.
  - verification_history: included only in dev_mode.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from openlia.llm.runtime.report_v2.schemas.report_v2 import (
    ReportV2,
    ReportV2Cover,
    ReportV2Section,
)
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary
from openlia.llm.runtime.report_v2.schemas.verification_history import VerificationHistory


def _synthesise_cover(
    composer_inputs: dict[str, Any],
    template_spec: Any,
) -> ReportV2Cover:
    """Build a minimal cover from the inputs the pipeline already has.

    Analyst-consensus and key-metric blocks live on the v1 cover too, but
    the v2.2 backend doesn't emit them yet. They'll fill in once their
    upstream stages exist; for now the cover is title + eyebrow + tagline
    + ticker, which is what ReportCover renders with at minimum.
    """
    ticker = str(composer_inputs.get("ticker") or "").strip().upper() or None
    prompt = str(composer_inputs.get("prompt") or "").strip()

    template_name = str(getattr(template_spec, "template_name", "") or "").strip()
    report_type = str(getattr(template_spec, "report_type", "") or "").strip()

    eyebrow_parts = [p for p in ("Equity Research", report_type or template_name) if p]
    eyebrow = " — ".join(eyebrow_parts) if eyebrow_parts else None

    title = ticker or template_name or "Equity Research Report"
    tagline = prompt if prompt else (template_name or None)

    return ReportV2Cover(
        title=title,
        eyebrow=eyebrow,
        subtitle=template_name or None,
        tagline=tagline,
        ticker=ticker,
    )


def build_report_v2(
    *,
    sections: list[dict[str, Any]],
    composer_inputs: dict[str, Any],
    template_spec: Any,
    pool_citations: dict[str, Citation],
    run_summary: RunSummary,
    verification_history: VerificationHistory,
    dev_mode: bool,
) -> ReportV2:
    """Build a ReportV2 from the assembled section dicts + pipeline metadata.

    Section dicts must include ``id``, ``name``, ``blocks``. They may
    optionally include ``status`` (default "OK"), ``skip_reason``, and
    ``degraded_reason``.

    Citations are passed through as the deduplicated list the renderer
    expects (preserves first-appearance order from the citation manifest).
    """
    typed_sections: list[ReportV2Section] = [
        ReportV2Section(
            id=str(s.get("id", "")),
            name=str(s.get("name", "")),
            status=s.get("status", "OK"),
            blocks=list(s.get("blocks", []) or []),
            skip_reason=s.get("skip_reason"),
            degraded_reason=s.get("degraded_reason"),
        )
        for s in sections
    ]

    cover = _synthesise_cover(composer_inputs, template_spec)

    return ReportV2(
        engine_version=run_summary.engine_version,
        generated_at=datetime.now(tz=timezone.utc),
        template_id=run_summary.template_id,
        template_name=run_summary.template_name,
        cover=cover,
        sections=typed_sections,
        citations=list(pool_citations.values()),
        run_summary=run_summary,
        verification_history=verification_history if dev_mode else None,
    )
