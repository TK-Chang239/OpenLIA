from __future__ import annotations

import os
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_lifespan_sets_scheduler_on_app_state_when_enabled() -> None:
    """With OPENLIA_SCHEDULER_ENABLED=1, the lifespan must create the
    SchedulerService and park it on app.state.scheduler."""
    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "1",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert getattr(app.state, "scheduler", None) is not None
            assert app.state.scheduler.is_running is True


def test_lifespan_skips_scheduler_when_disabled() -> None:
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
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            # Either attribute is missing or is_running=False.
            svc = getattr(app.state, "scheduler", None)
            assert svc is None or svc.is_running is False
