"""EODHD built-in connector template.

Sources:
- https://github.com/EodHistoricalData/EODHD-APIs-Python-Financial-Library
- https://eodhd.com/financial-apis/macroeconomics-data-and-macro-indicators-api
- https://eodhistoricaldata.com/financial-apis/economic-events-data-api/

Covers most of Macro Research's macro indicators plus stock_quote and
the retail_sentiment social_posts need. The macro-indicators catalog
exposes debt_percent_gdp, gdp_growth_annual, and inflation_consumer_prices_annual.
The economic-events feed (via our ExtendedAPIClient wrapper) covers
core inflation rate and ISM Manufacturing PMI. The remaining
interest_revenue need is covered by Firecrawl scraping (see firecrawl.py).
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


def _reducer_spec(*, need_id: str, method_name: str) -> CallableSpec:
    """Macro-indicator spec that targets one of ExtendedAPIClient's
    reducer methods (debt_to_gdp / gdp_growth_yoy / cpi_yoy / …).

    The reducer translates iso-2 → iso-3 internally, calls EODHD's
    macro-indicators endpoint, and returns the latest non-null Value
    as a float. Country code stays iso-2 on the wire (matches needs.yaml).
    """
    return CallableSpec(
        need_id=need_id,
        access_mode="python_lib",
        module="openlia.data.eodhd_extended",
        method=f"ExtendedAPIClient.{method_name}",
        instance_factory=_API_CLIENT,
        param_bindings={"country": ParamBinding(to_arg="country")},
        constants={},
        result_path=(),
        shape="float",
    )


# Macro-indicator-catalog series, reduced to floats by ExtendedAPIClient.
_DEBT_GDP = _reducer_spec(need_id="debt_gdp", method_name="debt_to_gdp")
_GDP_YOY = _reducer_spec(need_id="gdp_yoy", method_name="gdp_growth_yoy")
_CPI_YOY = _reducer_spec(need_id="cpi_yoy", method_name="cpi_yoy")

# Derived series. Core CPI and ISM PMI aren't in EODHD's macro-indicators
# catalog, but both surface in its economic-events feed. ExtendedAPIClient
# filters and reduces each to a latest-non-null float. Country code here
# follows the events-feed convention (alpha-2), no transform applied.
_CPI_CORE_YOY = CallableSpec(
    need_id="cpi_core_yoy",
    access_mode="python_lib",
    module="openlia.data.eodhd_extended",
    method="ExtendedAPIClient.core_inflation_rate",
    instance_factory=_API_CLIENT,
    param_bindings={"country": ParamBinding(to_arg="country")},
    constants={},
    result_path=(),
    shape="float",
)

_PMI = CallableSpec(
    need_id="pmi",
    access_mode="python_lib",
    module="openlia.data.eodhd_extended",
    method="ExtendedAPIClient.ism_manufacturing_pmi",
    instance_factory=_API_CLIENT,
    param_bindings={"country": ParamBinding(to_arg="country")},
    constants={},
    result_path=(),
    shape="float",
)

# APIClient.get_live_stock_prices(ticker, s=None). The first positional arg
# is named "ticker" on the SDK, matching the runtime parameter from
# macro_research.needs.yaml#stock_quote.
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

# APIClient.get_sentiment(s, from_date=None, to_date=None). Comma-separated
# tickers (we pass one). The runtime param "ticker" maps to the SDK's "s".
#
# EODHD's sentiment endpoint returns aggregated daily sentiment per ticker
# ({date, count, normalized}), not per-post records. This catalog spec is
# intentionally best-effort: the field_map covers RawSocialPost's canonical
# key set so the spec passes the catalog invariant, but `text`/`source`/
# `ticker` source paths are not present in the response. Phase 7 smoke
# will classify the runtime KeyError as schema_miss and the user will be
# prompted to repick a different connector or endpoint.
_SOCIAL_POSTS = CallableSpec(
    need_id="social_posts",
    access_mode="python_lib",
    module="eodhd",
    method="ExtendedAPIClient.get_sentiment",
    instance_factory=_API_CLIENT,
    param_bindings={"ticker": ParamBinding(to_arg="s")},
    constants={},
    result_path=(),
    shape="list[dict]",
    field_map={
        "id": "date",
        "ticker": "ticker",
        "source": "source",
        "text": "text",
        "created_at": "date",
        "engagement": "count",
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
        "(comma-separated ticker codes, e.g. 'AAPL.US') OR `t` (a topic "
        "tag from the enum). Calling without one will fail. "
        "For broad market-wide news (e.g. 'what moved the market today'), "
        "set `s` to major index tickers like 'SPY.US,QQQ.US,DIA.US,IWM.US' "
        "rather than guessing a topic tag — `t` is for topic-specific "
        "filtering. Optional: `from_date`/`to_date` (YYYY-MM-DD), "
        "`limit` (1-1000, default 50), `offset` (default 0)."
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
                    "Ticker code(s), comma-separated (e.g. 'AAPL.US' or "
                    "'SPY.US,QQQ.US'). Required if `t` is empty. Use this "
                    "for broad market queries with index tickers."
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
    runner_specs=(
        _DEBT_GDP,
        _GDP_YOY,
        _CPI_YOY,
        _CPI_CORE_YOY,
        _PMI,
        _STOCK_QUOTE,
        _SOCIAL_POSTS,
    ),
    tool_overrides=(("financial_news", _FINANCIAL_NEWS_OVERRIDE),),
    tool_argument_constraints=(("financial_news", "require_one_of", (("s", "t"),)),),
)
