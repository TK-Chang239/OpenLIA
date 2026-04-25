from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import Browser, Playwright, async_playwright


class BrowserLauncher:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._closed = False

    async def browser(self) -> Browser:
        async with self._lock:
            if self._closed:
                raise RuntimeError("BrowserLauncher has been shut down")
            if self._browser is None:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
            return self._browser

    async def shutdown(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None


async def export_report_pdf(
    launcher: BrowserLauncher,
    html: str,
    *,
    header_html: str | None = None,
    footer_html: str | None = None,
    bundle_url: str | None = None,
    cookies: list[dict[str, Any]] | None = None,
) -> bytes:
    """Render a report HTML body to PDF bytes via Playwright.

    Two paths:
      - When `bundle_url` is provided: navigate the page to that URL with
        `wait_until="networkidle"`. Use this for the SPA-driven flow where
        the React `ReportRenderer` mounts and ECharts renders real vector
        graphics. Optional `cookies` are forwarded so the SPA can call
        `/api/reports/:id` against the protected backend.
      - Otherwise: use `page.set_content(html)`. This is the static-fallback
        path that ships chart titles, tables, and metric cards baked into
        the HTML — used by tests and any environment where the SPA bundle
        isn't reachable.
    """
    browser = await launcher.browser()
    context = await browser.new_context()
    try:
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()
        if bundle_url is not None:
            await page.goto(bundle_url, wait_until="networkidle")
        else:
            await page.set_content(html, wait_until="networkidle")
        kwargs: dict[str, Any] = {
            "format": "A4",
            "margin": {"top": "20mm", "bottom": "25mm", "left": "20mm", "right": "20mm"},
            "print_background": True,
        }
        if header_html or footer_html:
            kwargs["display_header_footer"] = True
            if header_html:
                kwargs["header_template"] = header_html
            if footer_html:
                kwargs["footer_template"] = footer_html
        return await page.pdf(**kwargs)
    finally:
        await context.close()
