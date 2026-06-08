"""EODHD built-in connector template.

Sources:
- https://github.com/EodHistoricalData/EODHD-APIs-Python-Financial-Library
- https://eodhd.com/financial-apis/stock-market-financial-news-api

Covers Portfolio's stock_quote need via ExtendedAPIClient.get_live_stock_prices.
The financial_news tool is also available for chat departments.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    CliMcpRecipe,
    PythonLibRecipe,
)
from openlia.connectors.types import (
    CallableSpec,
    Category,
    InstanceFactory,
    ParamBinding,
)

_API_KEY_PLACEHOLDER = "$EODHD_API_KEY"
# We instantiate openlia.data.eodhd_extended.ExtendedAPIClient (a subclass
# of eodhd.APIClient) so callers get every official APIClient method plus
# our derived series (core_inflation_rate, ism_manufacturing_pmi).
_API_CLIENT = InstanceFactory(cls="ExtendedAPIClient", args={"api_key": _API_KEY_PLACEHOLDER})


# APIClient.get_live_stock_prices(ticker, s=None). The first positional arg
# is named "ticker" on the SDK, matching the portfolio stock_quote need.
_STOCK_QUOTE = CallableSpec(
    need_id="stock_quote",
    access_mode="python_lib",
    module="eodhd",
    method="ExtendedAPIClient.get_live_stock_prices",
    instance_factory=_API_CLIENT,
    param_bindings={"ticker": ParamBinding(to_arg="ticker")},
    constants={},
    result_path=(),
    shape="dict",
)

# APIClient.get_fundamentals_data(ticker). Returns a dict of company
# fundamentals (General, Highlights, Valuation, …). Portfolio uses this
# for the company_profile need.
_COMPANY_PROFILE = CallableSpec(
    need_id="company_profile",
    access_mode="python_lib",
    module="eodhd",
    method="ExtendedAPIClient.get_fundamentals_data",
    instance_factory=_API_CLIENT,
    param_bindings={"ticker": ParamBinding(to_arg="ticker")},
    constants={},
    result_path=(),
    shape="dict",
)

# APIClient.get_eod_historical_stock_market_data(symbol, period, from_date,
# to_date). Returns list[dict] of daily OHLCV records. Portfolio uses this
# for the eod_history need. `ticker` maps to SDK's `symbol`.
# EODHD response keys (date, open, high, low, close, adjusted_close, volume)
# are already canonical — field_map uses identity mapping.
_EOD_HISTORY = CallableSpec(
    need_id="eod_history",
    access_mode="python_lib",
    module="eodhd",
    method="ExtendedAPIClient.get_eod_historical_stock_market_data",
    instance_factory=_API_CLIENT,
    param_bindings={
        "ticker": ParamBinding(to_arg="symbol"),
        "from_date": ParamBinding(to_arg="from_date"),
        "to_date": ParamBinding(to_arg="to_date"),
    },
    constants={},
    result_path=(),
    shape="list[dict]",
    field_map={
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "adjusted_close": "adjusted_close",
        "volume": "volume",
    },
)


# EODHD's documented standard topic-tag vocabulary for the financial_news
# endpoint. Source: https://eodhd.com/financial-apis/stock-market-financial-news-api
# Anthropic's tool validator can enforce these as a schema enum so the
# model can't hallucinate an unsupported tag (e.g. "general") that the
# upstream API rejects with "Incorrect value was fullfiled for s or t".
# EODHD also returns AI-auto-detected tags beyond this list, but those
# are an open vocabulary, not a guaranteed contract — intentionally
# excluded from the enum.
_FINANCIAL_NEWS_STANDARD_TAGS: tuple[str, ...] = (
    "balance sheet",
    "capital employed",
    "class action",
    "company announcement",
    "consensus eps estimate",
    "consensus estimate",
    "credit rating",
    "discounted cash flow",
    "dividend payments",
    "earnings estimate",
    "earnings growth",
    "earnings per share",
    "earnings release",
    "earnings report",
    "earnings results",
    "earnings surprise",
    "estimate revisions",
    "european regulatory news",
    "financial results",
    "fourth quarter",
    "free cash flow",
    "future cash flows",
    "growth rate",
    "initial public offering",
    "insider ownership",
    "insider transactions",
    "institutional investors",
    "institutional ownership",
    "intrinsic value",
    "market research reports",
    "net income",
    "operating income",
    "present value",
    "press releases",
    "price target",
    "quarterly earnings",
    "quarterly results",
    "ratings",
    "research analysis and reports",
    "return on equity",
    "revenue estimates",
    "revenue growth",
    "roce",
    "roe",
    "share price",
    "shareholder",
    "shareholder rights",
    "shares outstanding",
    "split",
    "strong buy",
    "total revenue",
    "zacks investment research",
    "zacks rank",
)


# EODHD's `financial_news` SDK signature has every kwarg defaulting to
# None, so a signature-derived JSON schema can't express that the
# upstream API still requires either `s` (ticker) or `t` (topic).
# Without this override the chat LLM happily calls the tool with no
# args and EODHD returns "Incorrect value was fullfiled for s or t".
_FINANCIAL_NEWS_OVERRIDE: dict = {
    "description": (
        "Fetch financial news from EODHD. REQUIRED: provide EITHER `s` "
        "(a SINGLE ticker code, e.g. 'AAPL.US' — this endpoint rejects "
        "comma-separated lists) OR `t` (a topic tag from the enum). "
        "Calling without one will fail. For broad market-wide news "
        "(e.g. 'what moved the market today'), pick ONE anchor index "
        "ticker like 'SPY.US' for `s`, or call this tool multiple times "
        "with different single tickers — do NOT guess a topic tag for "
        "broad queries. `t` is for topic-specific filtering only. "
        "Optional: `from_date`/`to_date` (YYYY-MM-DD), `limit` "
        "(1-1000, default 50), `offset` (default 0)."
    ),
    # Note: Anthropic's tool `input_schema` validator doesn't accept
    # JSON-Schema combinators like `anyOf`/`oneOf` — only the basic
    # `{type, properties, required}` triple plus `enum` on individual
    # properties. The s-OR-t requirement stays in the description and
    # is also enforced server-side by the dispatcher's `require_one_of`
    # argument constraint. The `enum` on `t` lets the validator reject
    # hallucinated tags before the SDK round-trip.
    "input_schema": {
        "type": "object",
        "properties": {
            "s": {
                "type": "string",
                "description": (
                    "A SINGLE ticker code (e.g. 'AAPL.US' or 'SPY.US'). "
                    "The news endpoint rejects comma-separated lists — "
                    "if you need news on several tickers, call the tool "
                    "once per ticker. Required if `t` is empty."
                ),
            },
            "t": {
                "type": "string",
                "enum": list(_FINANCIAL_NEWS_STANDARD_TAGS),
                "description": (
                    "Topic tag for filtered news. Choose ONE value from "
                    "the enum. Common picks: 'earnings results' / "
                    "'quarterly earnings' for results, 'price target' / "
                    "'ratings' for analyst calls, 'initial public offering' "
                    "for IPOs, 'insider transactions' for insider activity, "
                    "'press releases' for company announcements. Required "
                    "if `s` is empty."
                ),
            },
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD."},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD."},
            "limit": {"type": "integer", "description": "1-1000, default 50."},
            "offset": {"type": "integer", "description": "Default 0."},
        },
    },
}


EODHD_TEMPLATE = BuiltInTemplate(
    template_id="eodhd",
    display_name="EODHD",
    category=Category.FINANCIAL,
    api_key_env_var="EODHD_API_KEY",
    available_modes=(
        PythonLibRecipe(
            kind="python_lib",
            pip_name="eodhd",
            pip_version=">=1.0.0,<2.0.0",
            import_module="openlia.data.eodhd_extended",
            instance_factory_cls="ExtendedAPIClient",
            instance_factory_args=(("api_key", _API_KEY_PLACEHOLDER),),
        ),
        CliMcpRecipe(
            kind="cli_mcp",
            argv=("uvx", "eodhd-mcp"),
            env_keys=("EODHD_API_KEY",),
        ),
    ),
    canary_tool="get_live_stock_prices",
    runner_specs=(_STOCK_QUOTE, _COMPANY_PROFILE, _EOD_HISTORY),
    tool_overrides=(("financial_news", _FINANCIAL_NEWS_OVERRIDE),),
    tool_argument_constraints=(("financial_news", "require_one_of", (("s", "t"),)),),
)
