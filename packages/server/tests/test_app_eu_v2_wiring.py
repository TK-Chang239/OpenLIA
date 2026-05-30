"""Tests for EU v2 app-level wiring.

Verifies that create_app() mounts the earnings-update v2 router and
initialises app.state.eu_v2_event_broker when the engine is enabled.
"""

from __future__ import annotations


def test_eu_v2_router_mounted(monkeypatch):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "v2")
    from openlia_server.app import create_app

    app = create_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/departments/earnings-update/v2/settings" in paths
    assert hasattr(app.state, "eu_v2_event_broker")
