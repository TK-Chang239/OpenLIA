"""Deterministic runner integration with the v2 connector dispatcher.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §9.

Deterministic runners (Macro Research T1, Retail Sentiment data fetch,
scheduled jobs) consume data without an LLM in the path. They declare
their needs via stable id tuples and call the dispatcher by id:

    async with dispatcher.in_department("macro_research"):
        debt = await dispatcher.fetch_need("debt_gdp", country="US")

This module owns the small translation layer that maps the legacy
T1_REQUIREMENTS strings (e.g. `"stock_quote:TIP"`,
`"macro_indicator:debt_gdp"`, `"company_news:geopolitical"`) to v2
`(need_id, runtime_args)` pairs declared in
`packages/core/src/openlia/departments/macro_research.needs.yaml`.

Failure semantics (§9.3): missing callable specs surface as
`NeedNotResolved`; underlying call failures propagate. No silent
fallbacks; callers handle retries / staleness explicitly.
"""

from __future__ import annotations

from typing import Any, Protocol

from openlia.connectors.dispatch import NeedNotResolved


class _DispatcherProtocol(Protocol):
    """Minimal subset of the v2 Dispatcher we depend on."""

    def in_department(self, department_id: str) -> Any: ...

    async def fetch_need(self, need_id: str, **runtime_args: Any) -> Any: ...


# --- Macro Research: T1 requirement strings -> (need_id, runtime_args) ---


def parse_mr_requirement(requirement: str) -> tuple[str, dict[str, Any]]:
    """Translate a legacy MR requirement key into a (need_id, runtime_args) pair.

    Three families:

      - `macro_indicator:<id>` — passes straight through to that need
        (e.g. `debt_gdp`, `interest_revenue`, `pmi`, `gdp_yoy`,
        `cpi_yoy`, `cpi_core_yoy`, `usd_fx_reserve_share`,
        `cb_gold_purchases`, `foreign_treasury_holdings`).
      - `stock_quote:<TICKER>` — the parameterized `stock_quote` need
        with `ticker=<TICKER>`.
      - `company_news:<topic>` — the `geopolitical_news` need (currently
        the only news need in MR's `needs.yaml`); the topic suffix is
        carried as a runtime_args hint but otherwise ignored.

    Unknown prefixes are returned as `(requirement, {})` so callers
    surface a clear `NeedNotResolved` from the dispatcher.
    """
    if ":" not in requirement:
        return requirement, {}
    prefix, _, suffix = requirement.partition(":")
    if prefix == "macro_indicator":
        # needs.yaml declares `country` defaulting to "US" for every macro
        # indicator. The dispatcher doesn't auto-merge yaml defaults, so we
        # propagate it here. Per-country support (e.g. macro_indicator:de:cpi_yoy)
        # is a future scope item.
        return suffix, {"country": "US"}
    if prefix == "stock_quote":
        return "stock_quote", {"ticker": suffix}
    if prefix == "company_news":
        # MR's only news need today is `geopolitical_news`. Topic suffix
        # currently maps 1:1; future news needs will land here.
        return "geopolitical_news", {}
    # Unknown family — let the dispatcher fail loudly.
    return requirement, {}


async def fetch_mr_t1_data(
    *,
    dispatcher: _DispatcherProtocol,
    requirements: tuple[str, ...],
) -> dict[str, Any]:
    """Walk MR's T1 requirement list and resolve each via the dispatcher.

    The caller is expected to be inside `dispatcher.in_department(
    "macro_research")` (the assembler enters this context for the whole
    T1 stage). `NeedNotResolved` propagates unchanged.
    """
    out: dict[str, Any] = {}
    for req in requirements:
        need_id, runtime_args = parse_mr_requirement(req)
        out[req] = await dispatcher.fetch_need(need_id, **runtime_args)
    return out


# --- Retail Sentiment: social_posts fetch ---


async def fetch_rs_social_posts(
    *,
    dispatcher: _DispatcherProtocol,
    ticker: str,
) -> Any:
    """Fetch raw social posts for `ticker` via the v2 dispatcher.

    RS's `needs.yaml` declares `social_posts(ticker)`. The wizard
    adapter resolves it to the financial connector's sentiment endpoint
    (e.g. `eodhd.APIClient.sentiment_data`).

    Caller must be inside `dispatcher.in_department("retail_sentiment")`.
    """
    return await dispatcher.fetch_need("social_posts", ticker=ticker)


__all__ = [
    "NeedNotResolved",
    "fetch_mr_t1_data",
    "fetch_rs_social_posts",
    "parse_mr_requirement",
]
