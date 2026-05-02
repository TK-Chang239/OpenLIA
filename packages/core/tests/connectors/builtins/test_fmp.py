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


def test_fmp_runner_specs_cover_stock_quote_cpi_yoy_gdp_yoy() -> None:
    """FMP and EODHD are alternative providers. FMP covers the macro
    indicators its economics-indicators API actually exposes:

    - stock_quote (via the `quote` tool)
    - cpi_yoy (via name=inflationRate, reduced with latest_value_by_date)
    - gdp_yoy (via name=realGDP, reduced with yoy_pct_quarterly)

    The other 4 macro/sentiment needs (debt_gdp, cpi_core_yoy, pmi,
    social_posts) genuinely don't exist on FMP's hosted MCP. Users who
    want full macro coverage pick EODHD.
    """
    need_ids = {spec.need_id for spec in FMP_TEMPLATE.runner_specs}
    assert need_ids == {"stock_quote", "cpi_yoy", "gdp_yoy"}


def test_fmp_cpi_yoy_uses_inflation_rate_with_latest_value_reducer() -> None:
    spec = next(s for s in FMP_TEMPLATE.runner_specs if s.need_id == "cpi_yoy")
    assert spec.tool_name == "economics"
    assert spec.constants["endpoint"] == "economics-indicators"
    assert spec.constants["name"] == "inflationRate"
    assert spec.result_reducer == "latest_value_by_date"


def test_fmp_gdp_yoy_uses_real_gdp_with_yoy_pct_quarterly_reducer() -> None:
    spec = next(s for s in FMP_TEMPLATE.runner_specs if s.need_id == "gdp_yoy")
    assert spec.tool_name == "economics"
    assert spec.constants["endpoint"] == "economics-indicators"
    assert spec.constants["name"] == "realGDP"
    assert spec.result_reducer == "yoy_pct_quarterly"


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
