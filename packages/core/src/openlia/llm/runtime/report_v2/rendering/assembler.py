"""Full report assembler for Equity Research v2.2.

Task O5 — stage 9.

Combines block rendering, citation substitution, and section ordering into a
single HTML document.
"""

from __future__ import annotations

import html as _html

from openlia.llm.runtime.report_v2.rendering.block_renderer import render_block
from openlia.llm.runtime.report_v2.rendering.citation_manifest import (
    assemble_citation_manifest,
    render_sources_footer,
    substitute_markers,
)
from openlia.llm.runtime.report_v2.rendering.run_summary_renderer import render_run_summary
from openlia.llm.runtime.report_v2.rendering.verification_history_renderer import (
    render_verification_history,
)
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary
from openlia.llm.runtime.report_v2.schemas.verification_history import VerificationHistory


def _collect_block_texts(sections: list[dict]) -> list[str]:
    """Extract text values from every block that carries a 'text' key.

    Used by assemble_citation_manifest to scan for [c:id] markers.
    """
    texts: list[str] = []
    for section in sections:
        for block in section.get("blocks", []):
            if isinstance(block, dict) and "text" in block:
                texts.append(block["text"])
    return texts


def assemble_report(
    sections: list[dict],
    pool_citations: dict[str, Citation],
    run_summary: RunSummary,
    verification_history: VerificationHistory,
    dev_mode: bool,
) -> str:
    """Assemble the full report HTML document.

    Section ordering:
      1. Template sections (input order)
      2. Sources (omitted when no citations)
      3. Run Summary
      4. Verification History (only when dev_mode=True)

    Wrapped in <article class="openlia-report"> with a <footer>.
    """
    block_texts = _collect_block_texts(sections)
    manifest = assemble_citation_manifest(pool_citations, block_texts)

    parts: list[str] = ['<article class="openlia-report">']

    # Template sections
    for section in sections:
        section_id = _html.escape(str(section.get("id", "")), quote=True)
        section_name = _html.escape(str(section.get("name", "")))
        rendered_blocks: list[str] = []
        for block in section.get("blocks", []):
            if not isinstance(block, dict):
                continue
            rendered = render_block(block)
            rendered = substitute_markers(rendered, manifest)
            rendered_blocks.append(rendered)
        parts.append(
            f'<section id="{section_id}"><h2>{section_name}</h2>'
            + "".join(rendered_blocks)
            + "</section>"
        )

    # Sources
    sources_html = render_sources_footer(manifest)
    if sources_html:
        parts.append(sources_html)

    # Run Summary
    parts.append(render_run_summary(run_summary))

    # Verification History (dev_mode only)
    verification_html = render_verification_history(verification_history, dev_mode)
    if verification_html:
        parts.append(verification_html)

    # Footer
    engine_version = _html.escape(run_summary.engine_version)
    parts.append(f'<footer class="report-footer">Engine v{engine_version}</footer>')

    parts.append("</article>")
    return "".join(parts)
