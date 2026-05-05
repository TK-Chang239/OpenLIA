"""Built-in EODHD template tests."""

from __future__ import annotations

from openlia.connectors.builtins.eodhd import (
    _FINANCIAL_NEWS_STANDARD_TAGS,
    EODHD_TEMPLATE,
)
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


def test_eodhd_macro_specs_target_float_reducer_methods() -> None:
    """The 3 macro indicators that come from get_macro_indicators_data
    (debt_gdp, gdp_yoy, cpi_yoy) must point at ExtendedAPIClient reducer
    methods (debt_to_gdp / gdp_growth_yoy / cpi_yoy), not at the raw
    SDK call. The raw call returns list[dict] which would be a runtime
    shape mismatch against shape='float'.
    """
    method_for: dict[str, str] = {}
    for spec in EODHD_TEMPLATE.runner_specs:
        method_for[spec.need_id] = spec.method or ""
    assert method_for["debt_gdp"] == "ExtendedAPIClient.debt_to_gdp"
    assert method_for["gdp_yoy"] == "ExtendedAPIClient.gdp_growth_yoy"
    assert method_for["cpi_yoy"] == "ExtendedAPIClient.cpi_yoy"


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


def test_eodhd_tool_overrides_use_anthropic_compatible_schema() -> None:
    """Anthropic's tool `input_schema` validator rejects JSON-Schema
    combinators (`anyOf`, `oneOf`, `allOf`, `not`). A builtin override
    that uses any of them breaks every chat turn for users on Claude
    via OpenRouter. Guard against accidental reintroduction."""
    forbidden_keys = {"anyOf", "oneOf", "allOf", "not"}
    for tool_name, override in EODHD_TEMPLATE.tool_overrides:
        schema = override.get("input_schema") or {}
        leaked = forbidden_keys & set(schema.keys())
        assert not leaked, (
            f"{tool_name} override input_schema contains "
            f"Anthropic-incompatible keys: {leaked}"
        )
        assert schema.get("type") == "object", f"{tool_name}: input_schema.type must be 'object'"
        assert isinstance(schema.get("properties"), dict), (
            f"{tool_name}: input_schema.properties must be an object"
        )


def test_financial_news_standard_tags_constant() -> None:
    """The standard-tag list is the source of truth for the financial_news
    `t` enum. Lock its size, casing, and uniqueness so a careless edit
    doesn't quietly drop a valid value."""
    assert len(_FINANCIAL_NEWS_STANDARD_TAGS) == 53
    assert len(set(_FINANCIAL_NEWS_STANDARD_TAGS)) == 53, "duplicate tags"
    assert all(tag == tag.lower() for tag in _FINANCIAL_NEWS_STANDARD_TAGS), (
        "all tags must be lowercase to match EODHD API"
    )
    for anchor in (
        "earnings results",
        "price target",
        "initial public offering",
        "zacks rank",
    ):
        assert anchor in _FINANCIAL_NEWS_STANDARD_TAGS
