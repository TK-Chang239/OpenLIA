import pytest
from openlia_server.services.report_export import (
    BrowserLauncher,
    export_report_pdf,
)


@pytest.mark.asyncio
async def test_export_small_html_produces_pdf_bytes():
    launcher = BrowserLauncher()
    try:
        html = (
            "<html><head><title>Hello</title>"
            "<style>@page{size:A4;margin:20mm}body{font:15px Inter}</style>"
            "</head><body><h1>Apple Q1 2026</h1>"
            "<p>Revenue 124.3B, up 31.1%.</p></body></html>"
        )
        data = await export_report_pdf(launcher, html)
        assert isinstance(data, bytes)
        assert data.startswith(b"%PDF-")
        assert len(data) > 2000
    finally:
        await launcher.shutdown()


@pytest.mark.asyncio
async def test_shutdown_is_idempotent():
    launcher = BrowserLauncher()
    await launcher.shutdown()
    await launcher.shutdown()
