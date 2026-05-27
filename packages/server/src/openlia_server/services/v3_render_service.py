"""Server-side wrapper around the v3 rendering pipeline.

Loads a persisted run, runs ``assemble_html`` over it, and (when a
``BrowserLauncher`` is provided) prints the HTML to PDF through
Playwright. Also persists the chart data-URLs back onto the
``report_v3_charts.rendered_url`` column so subsequent renders are
cheap and the chart provenance is queryable.

The HTML path has no extra dependencies beyond what's already in the
project (``matplotlib`` + ``markdown-it-py``). The PDF path needs the
optional ``BrowserLauncher`` from ``services.report_export`` — when
absent the route returns 503 with a clear message.
"""

from __future__ import annotations

from dataclasses import dataclass

from openlia.llm.runtime.report_v3.rendering import (
    AssembledReport,
    assemble_html,
)
from sqlalchemy.orm import Session as DBSession

from openlia_server.services import v3_run_service as svc


@dataclass(frozen=True)
class HtmlRender:
    html: str
    assembled: AssembledReport


def render_html(
    *,
    db: DBSession,
    user_id: str,
    report_id: str,
) -> HtmlRender:
    """Assemble HTML for a persisted run, updating chart rendered_urls in place."""
    row, sections, charts, citations = svc.get_run(
        db=db, user_id=user_id, report_id=report_id
    )
    assembled = assemble_html(
        report=row,
        sections=sections,
        charts=charts,
        citations=citations,
    )
    _persist_rendered_urls(db=db, charts=charts, assembled=assembled)
    return HtmlRender(html=assembled.html, assembled=assembled)


async def render_pdf(
    *,
    db: DBSession,
    user_id: str,
    report_id: str,
    browser_launcher,
) -> bytes:
    """Render HTML, then print to PDF via Playwright.

    ``browser_launcher`` is the app's shared ``BrowserLauncher``
    (``services.report_export.BrowserLauncher``). The render service
    is provider-agnostic — it asks the launcher for a Browser and
    works with whatever chromium-like engine the host has wired.
    """
    html_render = render_html(db=db, user_id=user_id, report_id=report_id)
    browser = await browser_launcher.browser()
    page = await browser.new_page()
    try:
        await page.set_content(html_render.html, wait_until="load")
        pdf_bytes = await page.pdf(
            format="A4",
            margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
            print_background=True,
        )
    finally:
        await page.close()
    return pdf_bytes


def _persist_rendered_urls(
    *,
    db: DBSession,
    charts,
    assembled: AssembledReport,
) -> None:
    for chart_row in charts:
        url = assembled.chart_data_urls_by_id.get(chart_row.chart_id)
        if url and chart_row.rendered_url != url:
            chart_row.rendered_url = url
    db.flush()
