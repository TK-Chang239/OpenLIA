from datetime import UTC, datetime

from openlia_server.db.models.report_eu import ReportEu, ReportEuSection
from openlia_server.services.eu_v2_docx import render_docx


def test_render_docx_returns_zip_bytes():
    row = ReportEu(
        id="r1",
        user_id="u1",
        subject="AAPL",
        ticker="AAPL",
        trigger_kind="on_demand",
        fiscal_date=None,
        template_id="eu_default",
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="m",
        status="completed",
        error_message=None,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        cover_json=None,
        reasoning_effort=None,
    )
    sections = [
        ReportEuSection(
            report_id="r1",
            section_id="quick_take",
            section_index=0,
            title="Quick Take",
            markdown="Body text.",
            version=1,
        )
    ]
    out = render_docx(report=row, sections=sections, charts=[], citations=[])
    assert isinstance(out, (bytes, bytearray)) and out[:2] == b"PK"  # .docx is a zip
