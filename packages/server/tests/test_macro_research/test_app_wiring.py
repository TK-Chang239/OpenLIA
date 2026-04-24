from __future__ import annotations

from openlia_server.app import create_app


def test_macro_research_routes_mounted() -> None:
    app = create_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/departments/macro_research/dashboards" in paths
    assert "/departments/macro_research/dashboards/{slug}" in paths
    assert "/departments/macro_research/schedule" in paths
