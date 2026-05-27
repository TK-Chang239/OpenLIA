"""Citation rewriting + bibliography assembly.

Two passes:

  1. ``rewrite_section_markdown`` walks one section's markdown and
     replaces every ``[^source_id]`` marker with ``[^N]`` per the
     supplied display-index map. Unknown markers are left untouched
     so they show up in the rendered output (a reader-visible signal
     the citation broke). Chart markers (``{{chart:id}}``) are left
     for the assembler to substitute.

  2. ``build_bibliography`` produces the ordered list of bibliography
     entries (one per source_id with an assigned display_index) that
     the assembler appends to the report body.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass

CITATION_MARKER_RE = re.compile(r"\[\^([a-z0-9_]+)\]")


@dataclass(frozen=True)
class RewrittenSection:
    """Output of ``rewrite_section_markdown`` — markdown + which sources it cited."""

    section_id: str
    title: str
    markdown: str
    cited_source_ids: tuple[str, ...]


@dataclass(frozen=True)
class BibliographyEntry:
    """One reader-facing bibliography line.

    ``display_index`` is the ``[^N]`` number shown in the body.
    ``label`` is a short human-readable string assembled from the
    citation's provenance (URL + title for web; provider + endpoint
    for data tools; method for computed tools).
    """

    display_index: int
    source_id: str
    label: str
    url: str | None


def rewrite_section_markdown(
    *,
    section_id: str,
    title: str,
    markdown: str,
    display_index_by_source_id: dict[str, int],
) -> RewrittenSection:
    """Replace [^source_id] markers with [^display_index]."""
    cited: list[str] = []
    seen: set[str] = set()

    def _replace(match: re.Match[str]) -> str:
        sid = match.group(1)
        if sid not in seen:
            seen.add(sid)
            cited.append(sid)
        idx = display_index_by_source_id.get(sid)
        if idx is None:
            # Unknown source — leave the marker so the reader sees it
            # didn't resolve. Phase 2b's job isn't to hide bugs.
            return match.group(0)
        return f"[^{idx}]"

    rewritten = CITATION_MARKER_RE.sub(_replace, markdown)
    return RewrittenSection(
        section_id=section_id,
        title=title,
        markdown=rewritten,
        cited_source_ids=tuple(cited),
    )


def build_bibliography(
    citations: Iterable,
) -> list[BibliographyEntry]:
    """Turn persisted ``ReportV3Citation`` rows into ordered bibliography entries.

    Skips rows with ``display_index is None`` — those source_ids were
    logged but never actually cited in the body. Result is sorted by
    display_index.
    """
    entries: list[BibliographyEntry] = []
    for row in citations:
        display_index = getattr(row, "display_index", None)
        if display_index is None:
            continue
        provenance = _parse_provenance(row)
        label = _label_for(row.tool_name, provenance, row.source_id)
        url = _url_for(provenance)
        entries.append(
            BibliographyEntry(
                display_index=display_index,
                source_id=row.source_id,
                label=label,
                url=url,
            )
        )
    entries.sort(key=lambda e: e.display_index)
    return entries


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _parse_provenance(row) -> dict:
    """Pull a dict view of provenance whether it's stored as text or already dict."""
    raw = getattr(row, "provenance_json", None) or getattr(row, "provenance", None)
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _label_for(tool_name: str, provenance: dict, source_id: str) -> str:
    """Human-readable label for one bibliography entry.

    Falls back through several provenance shapes (web / data / computed)
    so the renderer never shows an empty entry. Source_id stays in the
    label as a stable handle the user can search for.
    """
    title = provenance.get("title")
    url = provenance.get("url")
    publisher = provenance.get("publisher")
    provider = provenance.get("provider")
    endpoint = provenance.get("endpoint")
    method = provenance.get("method")
    period = provenance.get("period")

    if tool_name == "web_search":
        head = (title or url or "Web source").strip()
        if publisher:
            return f"{head} — {publisher} ({source_id})"
        return f"{head} ({source_id})"

    if provider and endpoint:
        label = f"{provider} {endpoint}"
        if period:
            label = f"{label} ({period})"
        return f"{label} [{source_id}]"

    if method:
        return f"Computed: {method} [{source_id}]"

    if title:
        return f"{title} [{source_id}]"
    return f"{tool_name} [{source_id}]"


def _url_for(provenance: dict) -> str | None:
    url = provenance.get("url")
    if isinstance(url, str) and url and not url.startswith("search://"):
        return url
    return None
