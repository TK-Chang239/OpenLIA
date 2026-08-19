"""Citation rows for the RS / MR dashboard cache payloads.

The dashboard engines emit ledger-style ``[^source_id]`` markers in their
narrative prose, but the cached payloads historically carried no citation
table — the frontend could only strip the markers. This maps the engine's
``CitationLogEntry`` ledger into compact ``{source_id, title, url}`` rows
the UI can link markers against.
"""

from __future__ import annotations

from typing import Any


def citation_rows(citations: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in citations:
        provenance = getattr(entry, "provenance", None) or {}
        url = provenance.get("url")
        if not isinstance(url, str) or url.startswith("search://"):
            url = None
        title = provenance.get("title") or provenance.get("publisher")
        if not title:
            provider = provenance.get("provider") or getattr(entry, "tool_name", "source")
            endpoint = provenance.get("endpoint")
            title = f"{provider} {endpoint}" if endpoint else str(provider)
        rows.append(
            {
                "source_id": getattr(entry, "source_id", ""),
                "title": str(title),
                "url": url,
            }
        )
    return rows
