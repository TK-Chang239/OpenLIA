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


async def capture_chart_pngs(
    launcher: BrowserLauncher,
    *,
    bundle_url: str,
    cookies: list[dict[str, Any]] | None = None,
    device_scale_factor: float = 2.0,
) -> dict[str, bytes]:
    """Render a report's print page and screenshot every chart block.

    Returns a mapping of `data-block-path` (e.g. "0-3") to PNG bytes.
    Charts are captured at 2x DPI for retina-sharp embedding in DOCX.
    Empty mapping when the page contains no `[data-block-path]` elements.
    """
    browser = await launcher.browser()
    context = await browser.new_context(device_scale_factor=device_scale_factor)
    try:
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto(bundle_url, wait_until="networkidle")
        await page.wait_for_function("window.__REPORT_READY__ === true", timeout=15_000)
        paths: list[str] = await page.evaluate(
            "Array.from(document.querySelectorAll('[data-block-path]'))"
            ".map(el => el.getAttribute('data-block-path'))"
        )
        out: dict[str, bytes] = {}
        for path in paths:
            locator = page.locator(f'[data-block-path="{path}"]')
            out[path] = await locator.screenshot(type="png")
        return out
    finally:
        await context.close()


async def export_report_pdf(
    launcher: BrowserLauncher,
    *,
    bundle_url: str,
    header_html: str | None = None,
    footer_html: str | None = None,
    cookies: list[dict[str, Any]] | None = None,
) -> bytes:
    """Render a report's print page to PDF bytes via Playwright.

    Navigates to `bundle_url` (the SPA's `/reports/:id/render` route) and
    captures the rendered DOM as PDF. The print page sets
    `window.__REPORT_READY__ = true` once its schema has rendered; we wait
    for that flag in addition to `networkidle` so charts are mounted before
    capture. Cookies, when provided, are forwarded so the SPA can call
    `/api/reports/:id` against the protected backend.
    """
    browser = await launcher.browser()
    context = await browser.new_context()
    try:
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto(bundle_url, wait_until="networkidle")
        await page.wait_for_function("window.__REPORT_READY__ === true", timeout=15_000)
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
