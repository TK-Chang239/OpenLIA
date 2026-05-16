from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_capture_chart_pngs_returns_dict_keyed_by_block_path() -> None:
    from openlia_server.services.report_export import capture_chart_pngs

    fake_locator_a = MagicMock()
    fake_locator_a.screenshot = AsyncMock(return_value=b"PNG_A")
    fake_locator_b = MagicMock()
    fake_locator_b.screenshot = AsyncMock(return_value=b"PNG_B")

    fake_page = MagicMock()
    fake_page.goto = AsyncMock()
    fake_page.wait_for_function = AsyncMock()
    fake_page.evaluate = AsyncMock(return_value=["0-1", "1-3"])
    fake_page.locator = MagicMock(side_effect=[fake_locator_a, fake_locator_b])

    fake_context = MagicMock()
    fake_context.add_cookies = AsyncMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)
    fake_context.close = AsyncMock()

    fake_browser = MagicMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)

    fake_launcher = MagicMock()
    fake_launcher.browser = AsyncMock(return_value=fake_browser)

    result = await capture_chart_pngs(fake_launcher, bundle_url="http://test/render", cookies=None)

    assert result == {"0-1": b"PNG_A", "1-3": b"PNG_B"}
    fake_page.goto.assert_awaited_once_with("http://test/render", wait_until="networkidle")
    fake_page.wait_for_function.assert_awaited_once()
    # 2x DPI is part of the contract — verify the context was created with it.
    fake_browser.new_context.assert_awaited_once()
    kwargs = fake_browser.new_context.await_args.kwargs
    assert kwargs.get("device_scale_factor") == 2.0


@pytest.mark.asyncio
async def test_capture_chart_pngs_forwards_cookies() -> None:
    from openlia_server.services.report_export import capture_chart_pngs

    fake_page = MagicMock()
    fake_page.goto = AsyncMock()
    fake_page.wait_for_function = AsyncMock()
    fake_page.evaluate = AsyncMock(return_value=[])
    fake_page.locator = MagicMock()

    fake_context = MagicMock()
    fake_context.add_cookies = AsyncMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)
    fake_context.close = AsyncMock()

    fake_browser = MagicMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)

    fake_launcher = MagicMock()
    fake_launcher.browser = AsyncMock(return_value=fake_browser)

    cookies = [{"name": "openlia_session", "value": "tok", "domain": "x", "path": "/"}]
    await capture_chart_pngs(fake_launcher, bundle_url="http://x", cookies=cookies)
    fake_context.add_cookies.assert_awaited_once_with(cookies)


@pytest.mark.asyncio
async def test_capture_chart_pngs_empty_dict_when_no_charts() -> None:
    from openlia_server.services.report_export import capture_chart_pngs

    fake_page = MagicMock()
    fake_page.goto = AsyncMock()
    fake_page.wait_for_function = AsyncMock()
    fake_page.evaluate = AsyncMock(return_value=[])
    fake_page.locator = MagicMock()

    fake_context = MagicMock()
    fake_context.add_cookies = AsyncMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)
    fake_context.close = AsyncMock()

    fake_browser = MagicMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)

    fake_launcher = MagicMock()
    fake_launcher.browser = AsyncMock(return_value=fake_browser)

    result = await capture_chart_pngs(fake_launcher, bundle_url="http://x")
    assert result == {}
    fake_page.locator.assert_not_called()
