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
    """EODHD covers three Portfolio needs via ExtendedAPIClient:
    stock_quote (live price), company_profile (fundamentals), and
    eod_history (daily OHLCV time-series).
    """
    need_ids = {spec.need_id for spec in EODHD_TEMPLATE.runner_specs}
    assert need_ids == {"stock_quote", "company_profile", "eod_history"}


def test_eodhd_portfolio_specs_target_correct_sdk_methods() -> None:
    """Each portfolio spec must target the right ExtendedAPIClient method."""
    method_for: dict[str, str] = {}
    for spec in EODHD_TEMPLATE.runner_specs:
        method_for[spec.need_id] = spec.method or ""
    assert method_for["stock_quote"] == "ExtendedAPIClient.get_live_stock_prices"
    assert method_for["company_profile"] == "ExtendedAPIClient.get_fundamentals_data"
    assert method_for["eod_history"] == "ExtendedAPIClient.get_eod_historical_stock_market_data"


def test_eodhd_runner_specs_have_python_lib_or_mcp_access_mode() -> None:
    for spec in EODHD_TEMPLATE.runner_specs:
        assert spec.access_mode in ("python_lib", "cli_mcp", "remote_mcp")
        if spec.access_mode == "python_lib":
            # All three portfolio specs target the eodhd package via ExtendedAPIClient.
            assert spec.module == "eodhd"
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
            f"{tool_name} override input_schema contains Anthropic-incompatible keys: {leaked}"
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


def test_financial_news_override_has_topic_enum() -> None:
    """The `t` parameter must declare its full standard-tag enum so the
    Anthropic tool validator rejects hallucinated topics before the SDK
    round-trip. Without this, the model picks plausible-sounding values
    like "general" and EODHD returns "Incorrect value was fullfiled for
    s or t", killing the chat turn."""
    overrides = dict(EODHD_TEMPLATE.tool_overrides)
    schema = overrides["financial_news"]["input_schema"]
    t_prop = schema["properties"]["t"]
    assert t_prop["type"] == "string"
    assert "enum" in t_prop, "`t` must declare an enum of valid topic tags"
    assert tuple(t_prop["enum"]) == _FINANCIAL_NEWS_STANDARD_TAGS


def test_financial_news_override_steers_broad_queries_to_tickers() -> None:
    """The original failure mode: model picks `t="general"` for "what
    happened in the market today". Even with the enum locking out
    invalid values, a broad query has no good topic match. The tool's
    top-level description must steer such queries toward `s` with
    index tickers instead of guessing a topic."""
    overrides = dict(EODHD_TEMPLATE.tool_overrides)
    description = overrides["financial_news"]["description"].lower()
    assert "broad" in description or "market-wide" in description, (
        "description should explicitly address broad-market queries"
    )
    assert "spy" in description or "index" in description, (
        "description should point at index tickers as the alternative to topic guessing"
    )


def test_financial_news_override_describes_s_as_single_ticker() -> None:
    """EODHD's news endpoint rejects comma-separated values for `s`
    with "Only one ticker is allowed in parameter s." The previous
    description told the model `s` accepted a comma-separated list
    (which is true for stock_prices, but NOT for news), and the model
    duly tried 'SPY.US,QQQ.US,DIA.US,IWM.US'. Lock the description's
    'single ticker' wording so the regression can't sneak back."""
    overrides = dict(EODHD_TEMPLATE.tool_overrides)
    description = overrides["financial_news"]["description"].lower()
    s_prop_desc = overrides["financial_news"]["input_schema"]["properties"]["s"][
        "description"
    ].lower()
    assert "single ticker" in description, (
        "top-level description must say `s` is a single ticker for this endpoint"
    )
    assert (
        "single ticker" in s_prop_desc
        or "rejects comma-separated" in s_prop_desc
        or "one per ticker" in s_prop_desc
    ), "`s` property description must explicitly forbid comma-separated values"
