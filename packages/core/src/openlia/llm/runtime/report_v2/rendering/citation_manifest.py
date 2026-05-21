"""Citation manifest: scan block texts for [c:id] markers, number citations,
substitute inline superscript links, and render an aggregated Sources footer.

Task O2 — Equity Research v2.2 pipeline.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from openlia.llm.runtime.report_v2.schemas.research_pool import Citation

MARKER_RE = re.compile(r"\[c:([a-zA-Z0-9_]+)\]")


@dataclass
class CitationManifest:
    citations: list[Citation] = field(default_factory=list)
    id_to_number: dict[str, int] = field(default_factory=dict)
    backlink_counts: dict[str, int] = field(default_factory=dict)


def assemble_citation_manifest(
    pool: dict[str, Citation],
    block_texts: list[str],
) -> CitationManifest:
    """Scan block_texts for [c:id] markers and build a CitationManifest.

    Citations are ordered by first appearance; duplicates increment backlink count.
    IDs not present in pool are silently skipped.
    """
    manifest = CitationManifest()
    next_number = 1

    for text in block_texts:
        for match in MARKER_RE.finditer(text):
            cid = match.group(1)
            if cid not in pool:
                continue
            if cid not in manifest.id_to_number:
                manifest.id_to_number[cid] = next_number
                manifest.citations.append(pool[cid])
                manifest.backlink_counts[cid] = 0
                next_number += 1
            manifest.backlink_counts[cid] += 1

    return manifest


def substitute_markers(text: str, manifest: CitationManifest) -> str:
    """Replace each [c:id] with a superscript anchor [N].

    Unresolved markers (id not in manifest) are left unchanged.
    """

    def _replace(match: re.Match[str]) -> str:
        cid = match.group(1)
        if cid not in manifest.id_to_number:
            return match.group(0)
        n = manifest.id_to_number[cid]
        # href points to the <li> anchor; id allows backlink from sources footer
        return f'<sup><a class="cite-link" href="#cite-{n}" id="ref-{cid}-{n}">[{n}]</a></sup>'

    return MARKER_RE.sub(_replace, text)


def render_sources_footer(manifest: CitationManifest) -> str:
    """Render a Sources <section> with one <li> per citation and backlink chevrons.

    Returns empty string when manifest has no citations.
    """
    if not manifest.citations:
        return ""

    parts: list[str] = [
        '<section id="sources"><h2>Sources</h2><ol class="citations">',
    ]

    for citation in manifest.citations:
        n = manifest.id_to_number[citation.id]
        count = manifest.backlink_counts.get(citation.id, 0)

        title_escaped = html.escape(citation.title, quote=True)

        source_label = ""
        if citation.source_type and citation.tool:
            src = html.escape(citation.source_type, quote=True)
            tool = html.escape(citation.tool, quote=True)
            source_label = f" ({src} &mdash; {tool})"

        link_html = ""
        if citation.url:
            url_escaped = html.escape(citation.url, quote=True)
            link_html = f' <a href="{url_escaped}">{html.escape(citation.url, quote=True)}</a>'

        backlinks = "".join(
            f'<a class="cite-backlink" href="#ref-{citation.id}-{n}">&#8593;</a>'
            for _ in range(count)
        )

        parts.append(f'<li id="cite-{n}">{title_escaped}{source_label}{link_html} {backlinks}</li>')

    parts.append("</ol></section>")
    return "".join(parts)
