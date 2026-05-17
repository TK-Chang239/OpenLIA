import pytest
from openlia_server.services.report_export import BrowserLauncher


@pytest.mark.asyncio
async def test_shutdown_is_idempotent() -> None:
    launcher = BrowserLauncher()
    await launcher.shutdown()
    await launcher.shutdown()
