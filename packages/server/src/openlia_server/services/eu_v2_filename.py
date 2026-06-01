"""Shared filename convention for v2 Earnings Update reports.

Used by:
  - the download endpoints (html / pdf / docx) for ``Content-Disposition``
  - the repo list builder for the saved-item filename shown in the
    Repository page and used by the side-viewer download menu

Keeping the helpers in one place means downloads and repo entries
agree on the same ``Subject_Template_Date.ext`` shape — users see
the same name whether they download a fresh run or open a saved one.
"""

from __future__ import annotations

import re

from openlia_server.db.models.report_eu import ReportEu

_TEMPLATE_LABEL: dict[str, str] = {
    "eu_default": "Earnings-Update",
}


def slugify_filename_component(value: str) -> str:
    """Strip characters that confuse common filesystems / Content-
    Disposition parsers. Spaces -> underscores; other punctuation ->
    dashes; tickers like ``RKLB.US`` keep their dot. Runs of two or
    more separators collapse to a single underscore so a stray
    "Q&A / Research" becomes "Q-A_Research", not "Q-A_-_Research".
    Lone single separators are preserved so "Earnings-Update" stays
    intact through the slugifier."""
    cleaned: list[str] = []
    for ch in value.strip():
        if ch.isalnum() or ch in {".", "-", "_"}:
            cleaned.append(ch)
        elif ch.isspace():
            cleaned.append("_")
        else:
            cleaned.append("-")
    raw = "".join(cleaned)
    raw = re.sub(r"[-_]{2,}", "_", raw)
    out = raw.strip("-_.")
    return out or "report"


def template_label(template_id: str) -> str:
    if template_id in _TEMPLATE_LABEL:
        return _TEMPLATE_LABEL[template_id]
    base = template_id.removesuffix("_default")
    parts = [p for p in base.replace("_", " ").replace("-", " ").split() if p]
    return "-".join(p.capitalize() for p in parts) or "Report"


def build_download_filename(*, row: ReportEu, ext: str) -> str:
    """Subject_Template_Date.ext.

    ``ext`` should not include the leading dot. The date is the run's
    ``completed_at`` if present, else ``created_at``, formatted as
    YYYY-MM-DD in UTC.
    """
    when = row.completed_at or row.created_at
    date_str = when.strftime("%Y-%m-%d") if when is not None else "undated"
    subject = slugify_filename_component(row.subject or "report")
    template = slugify_filename_component(template_label(row.template_id))
    return f"{subject}_{template}_{date_str}.{ext}"


__all__ = [
    "build_download_filename",
    "slugify_filename_component",
    "template_label",
]
