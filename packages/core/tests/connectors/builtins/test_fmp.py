"""Built-in FMP template tests."""

from __future__ import annotations

from openlia.connectors.builtins.fmp import FMP_TEMPLATE
from openlia.connectors.builtins.types import RemoteMcpRecipe
from openlia.connectors.types import Category


def test_fmp_template_id_and_category() -> None:
    assert FMP_TEMPLATE.template_id == "fmp"
    assert FMP_TEMPLATE.category == Category.FINANCIAL
    assert FMP_TEMPLATE.api_key_env_var == "FMP_API_KEY"


def test_fmp_has_only_remote_mcp_mode() -> None:
    """Stale fmpsdk and unverified local CLI are not shipped — hosted MCP only."""
    modes = FMP_TEMPLATE.available_modes
    assert len(modes) == 1
    assert isinstance(modes[0], RemoteMcpRecipe)


def test_fmp_remote_mcp_url_targets_official_endpoint() -> None:
    remote = FMP_TEMPLATE.available_modes[0]
    assert isinstance(remote, RemoteMcpRecipe)
    assert remote.url == "https://financialmodelingprep.com/mcp?apikey={FMP_API_KEY}"


def test_fmp_runner_specs_cover_only_stock_quote() -> None:
    """FMP and EODHD are alternative providers; FMP's runner-side day-1
    coverage is just stock_quote.

    FMP's economics tool returns list[dict] of dated records (shape
    mismatch with shape='float'); EODHD's macro indicators are wrapped
    in ExtendedAPIClient reducer methods to return floats. The day-1
    catalog targets EODHD as the macro-coverage path; FMP stock_quote
    is the redundant alternative for users who prefer FMP.
    """
    need_ids = {spec.need_id for spec in FMP_TEMPLATE.runner_specs}
    assert need_ids == {"stock_quote"}


def test_fmp_runner_specs_use_remote_mcp_with_tool_names() -> None:
    for spec in FMP_TEMPLATE.runner_specs:
        assert spec.access_mode == "remote_mcp"
        assert spec.tool_name is not None
        assert spec.module is None
        assert spec.method is None
        # FMP's MCP dispatches via an `endpoint` enum constant.
        assert "endpoint" in spec.constants


def test_fmp_canary_tool_is_quote() -> None:
    """quote is verified from FMP's official MCP usage example."""
    assert FMP_TEMPLATE.canary_tool == "quote"
