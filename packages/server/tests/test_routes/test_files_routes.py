"""Route tests for /chat/attachments/{id}/download.

The /reports/{id}/download markdown route was removed in Phase 5 of the
report-download-formats migration; PDF/DOCX exports are served by the
/reports/{id}/export/{pdf,docx} routes and exercised in
test_reports.py / test_reports_pdf_export.py / test_reports_docx_export.py.
"""

from __future__ import annotations

import uuid


def test_md_download_route_is_gone_404(client, user_factory, login_as, report_factory):
    """The legacy markdown download endpoint must no longer route."""
    u = user_factory()
    login_as(u)
    r = report_factory(user_id=u.id, title="My Report", content_markdown="# Hello")
    assert client.get(f"/reports/{r.id}/download").status_code == 404


def test_download_attachment_404_when_missing(client, user_factory, login_as):
    login_as(user_factory())
    assert client.get(f"/chat/attachments/{uuid.uuid4()}/download").status_code == 404
