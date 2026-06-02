from datetime import UTC, datetime

from openlia_server.db.models.report_eu import ReportEu
from openlia_server.services.eu_v2_filename import build_download_filename


def _row() -> ReportEu:
    return ReportEu(
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
        created_at=datetime(2026, 4, 9, tzinfo=UTC),
        completed_at=datetime(2026, 4, 9, tzinfo=UTC),
        cover_json=None,
        reasoning_effort=None,
    )


def test_filename_shape():
    assert build_download_filename(row=_row(), ext="pdf") == "AAPL_Earnings-Update_2026-04-09.pdf"
