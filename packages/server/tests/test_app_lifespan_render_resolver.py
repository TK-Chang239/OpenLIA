from __future__ import annotations

import os
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_lifespan_attaches_render_base_url_resolver() -> None:
    """app.state.render_base_url_resolver must be set on startup so the PDF
    and DOCX routes can ask it where to point Playwright."""
    from openlia_server.services.render_base_url import RenderBaseUrlResolver

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
            resolver = getattr(app.state, "render_base_url_resolver", None)
            assert resolver is not None
            assert isinstance(resolver, RenderBaseUrlResolver)
