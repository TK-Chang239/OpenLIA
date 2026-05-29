"""Tests for the v3 download filename builder.

The builder runs server-side to set the Content-Disposition header on
the /html, /pdf, and /docx endpoints so downloads land on disk with
useful names instead of the opaque ``v3-report-<uuid>.ext`` legacy
form. Format is ``Subject_Template_Date.ext`` to match v1.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from openlia_server.services.v3_filename import (
    build_download_filename as _build_download_filename,
)
from openlia_server.services.v3_filename import (
    slugify_filename_component as _slugify_filename_component,
)
from openlia_server.services.v3_filename import (
    template_label as _template_label,
)


def _row(
    *,
    subject: str = "RKLB.US",
    template_id: str = "initiation_default",
    completed_at: datetime | None = None,
    created_at: datetime | None = None,
):
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        subject=subject,
        template_id=template_id,
        created_at=created_at or datetime(2026, 5, 28, 14, 5, tzinfo=UTC),
        completed_at=completed_at,
    )


def test_builtin_template_uses_friendly_label():
    row = _row(template_id="initiation_default")
    assert _build_download_filename(row=row, ext="pdf") == ("RKLB.US_Initiation_2026-05-28.pdf")


def test_update_template_label():
    row = _row(template_id="update_default")
    assert _build_download_filename(row=row, ext="docx") == ("RKLB.US_Update_2026-05-28.docx")


def test_sector_research_label():
    row = _row(subject="Semiconductor Sector", template_id="sector_research_default")
    assert _build_download_filename(row=row, ext="html") == (
        "Semiconductor_Sector_Sector-Research_2026-05-28.html"
    )


def test_user_uploaded_template_falls_back_to_title_cased_slug():
    # Pretend the user uploaded a template with this opaque uuid id —
    # in practice these are 32-char hex strings; for the label we want
    # something readable derived from the id, not perfect.
    row = _row(template_id="custom_deep_dive")
    assert _template_label("custom_deep_dive") == "Custom-Deep-Dive"
    assert _build_download_filename(row=row, ext="pdf") == (
        "RKLB.US_Custom-Deep-Dive_2026-05-28.pdf"
    )


def test_prefers_completed_at_over_created_at():
    row = _row(
        completed_at=datetime(2026, 6, 1, tzinfo=UTC),
        created_at=datetime(2026, 5, 28, tzinfo=UTC),
    )
    assert _build_download_filename(row=row, ext="pdf").endswith("_2026-06-01.pdf")


def test_falls_back_to_created_at_when_no_completed_at():
    row = _row(completed_at=None, created_at=datetime(2026, 5, 28, tzinfo=UTC))
    assert _build_download_filename(row=row, ext="pdf").endswith("_2026-05-28.pdf")


def test_slugify_strips_unsafe_chars_keeps_ticker_dots():
    assert _slugify_filename_component("RKLB.US") == "RKLB.US"
    assert _slugify_filename_component("Q&A / Research") == "Q-A_Research"
    assert _slugify_filename_component("  spaced  out  ") == "spaced_out"
    assert _slugify_filename_component("") == "report"


def test_subject_with_quotes_or_slashes_is_safe():
    row = _row(subject='Strange/Subject"With Quotes')
    filename = _build_download_filename(row=row, ext="docx")
    # No raw quote characters land in a filesystem-bound name.
    assert '"' not in filename
    assert "/" not in filename
    assert filename.endswith(".docx")
