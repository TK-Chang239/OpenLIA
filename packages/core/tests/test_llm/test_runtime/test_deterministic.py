"""Tests for openlia.llm.runtime.deterministic.

Cover the spec §9 contract: legacy MR T1 requirement strings translate
to (need_id, runtime_args) pairs; the dispatcher is invoked once per
requirement; `NeedNotResolved` propagates unchanged.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest
from openlia.connectors.dispatch import NeedNotResolved
from openlia.llm.runtime.deterministic import (
    fetch_mr_t1_data,
    fetch_rs_social_posts,
    parse_mr_requirement,
)


def test_parse_macro_indicator() -> None:
    assert parse_mr_requirement("macro_indicator:debt_gdp") == ("debt_gdp", {})


def test_parse_stock_quote() -> None:
    assert parse_mr_requirement("stock_quote:TIP") == ("stock_quote", {"ticker": "TIP"})


def test_parse_company_news() -> None:
    assert parse_mr_requirement("company_news:geopolitical") == ("geopolitical_news", {})


def test_parse_unknown_passes_through() -> None:
    # Unknown prefix is returned as-is so the dispatcher can fail loudly.
    assert parse_mr_requirement("force_debt_money") == ("force_debt_money", {})


class _FakeDispatcher:
    def __init__(self, results: dict[tuple[str, frozenset], Any]) -> None:
        self._results = results
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.dept_stack: list[str] = []

    @asynccontextmanager
    async def in_department(self, dept: str):
        self.dept_stack.append(dept)
        try:
            yield
        finally:
            self.dept_stack.pop()

    async def fetch_need(self, need_id: str, **runtime_args: Any) -> Any:
        self.calls.append((need_id, runtime_args))
        key = (need_id, frozenset(runtime_args.items()))
        if key not in self._results:
            raise NeedNotResolved(f"no resolved spec for {need_id!r}")
        return self._results[key]


@pytest.mark.asyncio
async def test_fetch_mr_t1_walks_each_requirement() -> None:
    results: dict[tuple[str, frozenset], Any] = {
        ("debt_gdp", frozenset()): 120.0,
        ("interest_revenue", frozenset()): 16.0,
        ("stock_quote", frozenset({("ticker", "TIP")})): {"price": 110.0},
    }
    dispatcher = _FakeDispatcher(results)
    out = await fetch_mr_t1_data(
        dispatcher=dispatcher,
        requirements=(
            "macro_indicator:debt_gdp",
            "macro_indicator:interest_revenue",
            "stock_quote:TIP",
        ),
    )
    assert out == {
        "macro_indicator:debt_gdp": 120.0,
        "macro_indicator:interest_revenue": 16.0,
        "stock_quote:TIP": {"price": 110.0},
    }
    assert [name for name, _ in dispatcher.calls] == [
        "debt_gdp",
        "interest_revenue",
        "stock_quote",
    ]


@pytest.mark.asyncio
async def test_fetch_mr_t1_propagates_need_not_resolved() -> None:
    dispatcher = _FakeDispatcher({})
    with pytest.raises(NeedNotResolved):
        await fetch_mr_t1_data(
            dispatcher=dispatcher,
            requirements=("macro_indicator:nonexistent",),
        )


@pytest.mark.asyncio
async def test_fetch_rs_social_posts_returns_dispatcher_payload() -> None:
    results: dict[tuple[str, frozenset], Any] = {
        ("social_posts", frozenset({("ticker", "AAPL")})): [
            {"text": "post 1"},
            {"text": "post 2"},
        ],
    }
    dispatcher = _FakeDispatcher(results)
    out = await fetch_rs_social_posts(dispatcher=dispatcher, ticker="AAPL")
    assert out == [{"text": "post 1"}, {"text": "post 2"}]
    assert dispatcher.calls == [("social_posts", {"ticker": "AAPL"})]


@pytest.mark.asyncio
async def test_fetch_rs_social_posts_raises_on_missing_spec() -> None:
    dispatcher = _FakeDispatcher({})
    with pytest.raises(NeedNotResolved):
        await fetch_rs_social_posts(dispatcher=dispatcher, ticker="AAPL")


@pytest.mark.asyncio
async def test_dashboard_assembler_v2_path_invokes_dispatcher() -> None:
    """End-to-end: DashboardAssembler with `dispatcher=` injected runs T1
    via the dispatcher and produces a populated DashboardResult."""
    from openlia.macro_research.assembler import DashboardAssembler

    results: dict[tuple[str, frozenset], Any] = {
        ("debt_gdp", frozenset()): 130.0,
        ("interest_revenue", frozenset()): 22.0,
        ("stock_quote", frozenset({("ticker", "TIP")})): {"price": 110.0},
        ("stock_quote", frozenset({("ticker", "UUP")})): {"price": 28.5},
    }
    dispatcher = _FakeDispatcher(results)
    asm = DashboardAssembler(dispatcher=dispatcher)
    result = await asm.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=False,
    )
    # All four T1 requirements were dispatched.
    assert {name for name, _ in dispatcher.calls} == {
        "debt_gdp",
        "interest_revenue",
        "stock_quote",
    }
    assert dispatcher.dept_stack == []  # context manager exited cleanly
    t1 = next(t for t in result.tiers if t.tier == "T1")
    assert t1.data["inputs"]["macro_indicator:debt_gdp"] == 130.0
    assert t1.data["inputs"]["stock_quote:TIP"] == {"price": 110.0}
