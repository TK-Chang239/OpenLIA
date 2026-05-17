"""Task 16: lifespan wires BackgroundReportRegistry, UserPresenceRegistry,
and auto-cancel sweep task onto app.state."""

from __future__ import annotations

import os
from unittest.mock import patch

from fastapi.testclient import TestClient
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.user_presence_registry import UserPresenceRegistry


def test_app_state_carries_registry_and_presence() -> None:
    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "0",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app):
            assert isinstance(app.state.bg_report_registry, BackgroundReportRegistry)
            assert isinstance(app.state.user_presence, UserPresenceRegistry)
