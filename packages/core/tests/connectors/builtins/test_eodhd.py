"""Built-in EODHD template tests."""

from __future__ import annotations

from openlia.connectors.builtins.eodhd import EODHD_TEMPLATE
from openlia.connectors.builtins.types import CliMcpRecipe, PythonLibRecipe
from openlia.connectors.types import Category


def test_eodhd_template_id_and_category() -> None:
    assert EODHD_TEMPLATE.template_id == "eodhd"
    assert EODHD_TEMPLATE.category == Category.FINANCIAL
    assert EODHD_TEMPLATE.api_key_env_var == "EODHD_API_KEY"


def test_eodhd_has_both_cli_mcp_and_python_lib_modes() -> None:
    modes = EODHD_TEMPLATE.available_modes
    assert any(isinstance(m, CliMcpRecipe) for m in modes), "expected CLI MCP mode"
    assert any(isinstance(m, PythonLibRecipe) for m in modes), "expected python_lib mode"


def test_eodhd_python_lib_recipe_targets_extended_api_client() -> None:
    """We instantiate ExtendedAPIClient (subclass of eodhd.APIClient) so
    derived series (core_inflation_rate, ism_manufacturing_pmi) are
    available alongside every official APIClient method.
    """
    py = next(m for m in EODHD_TEMPLATE.available_modes if isinstance(m, PythonLibRecipe))
    assert py.pip_name == "eodhd"
    assert py.import_module == "openlia.data.eodhd_extended"
    assert py.instance_factory_cls == "ExtendedAPIClient"
    args = dict(py.instance_factory_args)
    assert args.get("api_key") == "$EODHD_API_KEY"


def test_eodhd_runner_specs_cover_expected_needs() -> None:
    """EODHD covers macro-indicators-catalog series (debt_percent_gdp,
    gdp_growth_annual, inflation_consumer_prices_annual) plus the two
    derived series surfaced via ExtendedAPIClient (core_inflation_rate,
    ism_manufacturing_pmi). interest_revenue is uncovered here — it
    falls to Firecrawl scraping.
    """
    need_ids = {spec.need_id for spec in EODHD_TEMPLATE.runner_specs}
    assert need_ids == {
        "debt_gdp",
        "gdp_yoy",
        "cpi_yoy",
        "cpi_core_yoy",
        "pmi",
        "stock_quote",
        "social_posts",
    }


def test_eodhd_runner_specs_have_python_lib_or_mcp_access_mode() -> None:
    for spec in EODHD_TEMPLATE.runner_specs:
        assert spec.access_mode in ("python_lib", "cli_mcp", "remote_mcp")
        if spec.access_mode == "python_lib":
            # Module varies: get_macro_indicators_data / get_live_stock_prices /
            # get_sentiment come from the eodhd package; core_inflation_rate
            # and ism_manufacturing_pmi come from our wrapper module.
            assert spec.module in ("eodhd", "openlia.data.eodhd_extended")
            assert spec.method is not None
            assert spec.instance_factory is not None
            assert spec.instance_factory.cls == "ExtendedAPIClient"
            assert spec.instance_factory.args.get("api_key") == "$EODHD_API_KEY"


def test_eodhd_canary_tool_is_set() -> None:
    assert EODHD_TEMPLATE.canary_tool is not None
