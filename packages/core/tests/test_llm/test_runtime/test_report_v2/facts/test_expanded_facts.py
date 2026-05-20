"""Tests for the WS2 facts expansion (segments, capital structure, FCF,
returns, SBC, dividends, share counts, forward consensus, peer absolutes,
forward valuation).

Each fact is exercised against (a) a small synthetic EODHD payload that
populates the source field, asserting both `value`, `data_as_of`, and
`source_tier`; and (b) an empty/missing payload, asserting that the Fact
resolves to `value=None` cleanly with a valid `source_ids` list (subject
fallback per the existing `_peer_source_ids_or_subject_fallback` pattern
for peer-dict facts, or the subject manifest id for subject-level facts).

The peer-set gate (`InsufficientPeerSetError`) is exercised end-to-end
against the runner; the override flag bypasses the failure cleanly."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.registry import default_registry

# Force registration of all block types so the runner can assemble the report
from openlia.llm.runtime.report_v2.packer.blocks import (  # noqa: F401
    bullet_list,
    callout_grid,
    chart_area,
    chart_bar,
    chart_candlestick,
    chart_combo,
    chart_heatmap,
    chart_line,
    chart_pie,
    chart_scatter,
    chart_treemap,
    chart_waterfall,
    comparison_split,
    group,
    key_finding,
    metric_cards,
    pull_quote,
    quote,
    rating_badge,
    table,
    text,
    timeline,
)
from openlia.llm.runtime.report_v2.peers import (
    InsufficientPeerSetError,
    count_peer_fundamentals,
)
from openlia.llm.runtime.report_v2.runner import WavedReportRunner
from openlia.llm.runtime.report_v2.types import ManifestEntry

SUBJECT_RETRIEVED_AT = "2026-05-19T05:00:00Z"
SUBJECT_FILING_DATE = "2024-12-31"


def _entry(id: int, identifier: str, payload: dict) -> ManifestEntry:
    return ManifestEntry(
        id=id,
        kind="fetch",
        provider="eodhd",
        identifier=identifier,
        raw_payload=payload,
        retrieved_at=SUBJECT_RETRIEVED_AT,
    )


def _full_payload() -> dict:
    """EODHD-shape fundamentals payload populated with every WS2 source field
    the extractors look for."""
    yearly_income = {
        f"{2020 + i}-12-31": {
            "totalRevenue": 100.0 + i * 20.0,
            "costOfRevenue": 40.0 + i * 8.0,
            "grossProfit": 60.0 + i * 12.0,
            "operatingIncome": 25.0 + i * 6.0,
            "netIncome": 18.0 + i * 5.0,
            "eps": 1.0 + i * 0.2,
        }
        for i in range(5)
    }
    yearly_balance = {
        f"{2020 + i}-12-31": {
            "cash": 10.0 + i * 2.0,
            "shortTermInvestments": 5.0 + i * 1.0,
            "shortLongTermDebtTotal": 8.0 + i * 0.5,
        }
        for i in range(5)
    }
    yearly_cashflow = {
        f"{2020 + i}-12-31": {
            "totalCashFromOperatingActivities": 20.0 + i * 4.0,
            "capitalExpenditures": -5.0 - i * 1.0,  # negative per EODHD convention
            "freeCashFlow": 15.0 + i * 3.0,
            "stockBasedCompensation": 3.0 + i * 0.5,
        }
        for i in range(5)
    }
    return {
        "General": {
            "Name": "TestCo",
            "Sector": "Technology",
            "Exchange": "NYSE",
        },
        "Highlights": {
            "MarketCapitalization": 1_000_000_000.0,
            "ReturnOnEquityTTM": 0.18,
            "ReturnOnAssetsTTM": 0.09,
            "DividendShare": 1.25,
            "DividendYield": 0.012,
            "Beta": 1.10,
            "EarningsShare": 1.80,
        },
        "Technicals": {"Beta": 1.05},
        "SharesStats": {
            "SharesOutstanding": 250_000_000.0,
            "SharesFloat": 220_000_000.0,
            "ShortPercent": 0.025,
        },
        "SegmentBreakdown": {
            "2023-12-31": {"Cloud": 70.0, "Services": 30.0},
            "2024-12-31": {"Cloud": 90.0, "Services": 30.0, "Other": 20.0},
        },
        "Earnings": {
            "Annual": {
                "2025-12-31": {"revenueEstimate": 220.0, "epsEstimate": 2.10},
                "2026-12-31": {"revenueEstimate": 260.0, "epsEstimate": 2.55},
                "2027-12-31": {"revenueEstimate": 300.0, "epsEstimate": 3.00},
            },
            "Trend": [
                {
                    "period": "+1q",
                    "revenueEstimateAvg": 55.0,
                    "revenueEstimateLow": 50.0,
                    "revenueEstimateHigh": 60.0,
                }
            ],
        },
        "Financials": {
            "Income_Statement": {"yearly": yearly_income},
            "Balance_Sheet": {"yearly": yearly_balance},
            "Cash_Flow": {"yearly": yearly_cashflow},
        },
    }


def _empty_payload() -> dict:
    """Minimal EODHD-shape payload — present only enough for subject_fundamentals
    to resolve and `revenue_annual`/`eps_annual` to extract a populated series.
    Every WS2-targeted field (segments, cash flow, returns, consensus, shares)
    is absent so the extractors can exercise their None-fallback paths."""
    return {
        "General": {"Name": "EmptyCo", "Sector": "Technology"},
        # MarketCapitalization populated so the `market_cap` extractor
        # (which uses strict `pluck`) doesn't crash; this is independent of
        # the WS2 fields under test.
        "Highlights": {"MarketCapitalization": 1.0},
        "Financials": {
            "Income_Statement": {
                "yearly": {
                    "2024-12-31": {
                        "totalRevenue": 100.0,
                        "grossProfit": 60.0,
                        "eps": 1.0,
                    }
                }
            }
        },
    }


def _subject_only(payload: dict) -> list[ManifestEntry]:
    return [_entry(1, "get_fundamentals_data/TST.US", payload)]


def _peer_payload(*, mcap: float, revenue: float, profit_margin: float, op_margin: float) -> dict:
    return {
        "General": {"Sector": "Technology"},
        "Highlights": {
            "MarketCapitalization": mcap,
            "RevenueTTM": revenue,
            "ProfitMargin": profit_margin,
            "OperatingMarginTTM": op_margin,
        },
        "Financials": {
            "Cash_Flow": {
                "yearly": {
                    "2024-12-31": {
                        "freeCashFlow": revenue * 0.20,
                    }
                }
            }
        },
    }


def _subject_plus_peers() -> list[ManifestEntry]:
    return [
        _entry(1, "get_fundamentals_data/TST.US", _full_payload()),
        _entry(
            2,
            "get_fundamentals_data/PRA.US",
            _peer_payload(mcap=500_000_000.0, revenue=80.0, profit_margin=0.15, op_margin=0.20),
        ),
        _entry(
            3,
            "get_fundamentals_data/PRB.US",
            _peer_payload(mcap=750_000_000.0, revenue=100.0, profit_margin=0.18, op_margin=0.22),
        ),
    ]


def _compile(facts_list: list[str], *, manifest: list[ManifestEntry] | None = None):
    return compile_pack(
        registry=default_registry,
        manifest=manifest or _subject_only(_full_payload()),
        requested_facts=facts_list,
        subject_ticker="TST",
    )


# ---------------------------------------------------------------------------
# Group 1 — Segment / business-model facts
# ---------------------------------------------------------------------------


def test_segment_revenue_latest_populates_from_segment_breakdown() -> None:
    pack = _compile(["segment_revenue_latest"])
    fact = pack.get("segment_revenue_latest")
    assert fact.value == {"Cloud": 90.0, "Services": 30.0, "Other": 20.0}
    assert fact.data_as_of == SUBJECT_FILING_DATE
    assert fact.source_tier == "vendor"
    assert fact.source_ids == [1]


def test_segment_revenue_latest_none_when_block_absent() -> None:
    pack = _compile(["segment_revenue_latest"], manifest=_subject_only(_empty_payload()))
    fact = pack.get("segment_revenue_latest")
    assert fact.value is None
    assert fact.source_ids == [1]
    assert fact.source_tier == "vendor"


def test_segment_revenue_yoy_populates_per_segment_series() -> None:
    pack = _compile(["segment_revenue_yoy"])
    fact = pack.get("segment_revenue_yoy")
    assert fact.value is not None
    assert fact.value["Cloud"] == [70.0, 90.0]
    assert fact.value["Services"] == [30.0, 30.0]
    assert fact.value["Other"] == [None, 20.0]
    assert fact.data_as_of == SUBJECT_FILING_DATE


def test_segment_revenue_yoy_none_when_absent() -> None:
    pack = _compile(["segment_revenue_yoy"], manifest=_subject_only(_empty_payload()))
    assert pack.get("segment_revenue_yoy").value is None


def test_fiscal_year_end_latest_returns_max_yearly_key() -> None:
    pack = _compile(["fiscal_year_end_latest"])
    fact = pack.get("fiscal_year_end_latest")
    assert fact.value == "2024-12-31"
    assert fact.source_tier == "vendor"
    assert fact.data_as_of == SUBJECT_FILING_DATE


def test_fiscal_year_end_latest_none_when_yearly_missing() -> None:
    payload = {"General": {"Name": "X"}, "Highlights": {}}
    # Need at least a fundamentals entry for subject_fundamentals_identifier to work
    payload["Financials"] = {"Income_Statement": {"yearly": {}}}
    pack = _compile(["fiscal_year_end_latest"], manifest=_subject_only(payload))
    assert pack.get("fiscal_year_end_latest").value is None


def test_segment_share_latest_derived_from_segment_revenue() -> None:
    pack = _compile(["segment_share_latest"])
    fact = pack.get("segment_share_latest")
    total = 90.0 + 30.0 + 20.0
    assert fact.value["Cloud"] == pytest.approx(90.0 / total)
    assert fact.value["Services"] == pytest.approx(30.0 / total)
    assert fact.value["Other"] == pytest.approx(20.0 / total)
    assert sum(fact.value.values()) == pytest.approx(1.0)
    assert fact.source_tier == "derived"
    assert fact.depends_on == ["segment_revenue_latest"]


def test_segment_share_latest_none_when_dependency_none() -> None:
    pack = _compile(["segment_share_latest"], manifest=_subject_only(_empty_payload()))
    assert pack.get("segment_share_latest").value is None


# ---------------------------------------------------------------------------
# Group 2 — Capital structure and returns
# ---------------------------------------------------------------------------


def test_cash_and_short_term_investments_annual_combined() -> None:
    pack = _compile(["cash_and_short_term_investments_annual"])
    fact = pack.get("cash_and_short_term_investments_annual")
    assert fact.value == [15.0, 18.0, 21.0, 24.0, 27.0]
    assert fact.data_as_of == SUBJECT_FILING_DATE
    assert fact.source_tier == "vendor"


def test_cash_and_short_term_investments_annual_none_when_absent() -> None:
    pack = _compile(
        ["cash_and_short_term_investments_annual"], manifest=_subject_only(_empty_payload())
    )
    fact = pack.get("cash_and_short_term_investments_annual")
    assert fact.value is None
    assert fact.source_ids == [1]


def test_net_cash_annual_derived_subtracts_debt() -> None:
    pack = _compile(["net_cash_annual"])
    fact = pack.get("net_cash_annual")
    # cash+sti = [15,18,21,24,27], debt = [8.0, 8.5, 9.0, 9.5, 10.0]
    assert fact.value == [7.0, 9.5, 12.0, 14.5, 17.0]
    assert fact.source_tier == "derived"
    assert fact.depends_on == ["cash_and_short_term_investments_annual", "total_debt_annual"]


def test_net_cash_annual_none_when_inputs_missing() -> None:
    pack = _compile(["net_cash_annual"], manifest=_subject_only(_empty_payload()))
    assert pack.get("net_cash_annual").value is None


def test_free_cash_flow_annual_direct_field() -> None:
    pack = _compile(["free_cash_flow_annual"])
    fact = pack.get("free_cash_flow_annual")
    assert fact.value == [15.0, 18.0, 21.0, 24.0, 27.0]
    assert fact.data_as_of == SUBJECT_FILING_DATE


def test_free_cash_flow_annual_computed_when_freecashflow_absent() -> None:
    payload = _full_payload()
    # Remove explicit freeCashFlow so the extractor falls back to OCF + capex.
    for row in payload["Financials"]["Cash_Flow"]["yearly"].values():
        row.pop("freeCashFlow")
    pack = _compile(["free_cash_flow_annual"], manifest=_subject_only(payload))
    fact = pack.get("free_cash_flow_annual")
    # OCF = [20, 24, 28, 32, 36], capex = [-5, -6, -7, -8, -9]; sum = [15..27]
    assert fact.value == [15.0, 18.0, 21.0, 24.0, 27.0]


def test_free_cash_flow_annual_none_when_absent() -> None:
    pack = _compile(["free_cash_flow_annual"], manifest=_subject_only(_empty_payload()))
    assert pack.get("free_cash_flow_annual").value is None


def test_operating_cash_flow_annual_populates() -> None:
    pack = _compile(["operating_cash_flow_annual"])
    fact = pack.get("operating_cash_flow_annual")
    assert fact.value == [20.0, 24.0, 28.0, 32.0, 36.0]
    assert fact.source_tier == "vendor"


def test_operating_cash_flow_annual_none_when_absent() -> None:
    pack = _compile(["operating_cash_flow_annual"], manifest=_subject_only(_empty_payload()))
    assert pack.get("operating_cash_flow_annual").value is None


def test_capex_annual_preserves_negative_sign() -> None:
    pack = _compile(["capex_annual"])
    fact = pack.get("capex_annual")
    assert fact.value == [-5.0, -6.0, -7.0, -8.0, -9.0]
    assert all(v <= 0 for v in fact.value)


def test_capex_annual_none_when_absent() -> None:
    pack = _compile(["capex_annual"], manifest=_subject_only(_empty_payload()))
    assert pack.get("capex_annual").value is None


def test_roe_ttm_from_highlights() -> None:
    pack = _compile(["roe_ttm"])
    fact = pack.get("roe_ttm")
    assert fact.value == 0.18
    assert fact.source_tier == "vendor"
    assert fact.data_as_of == SUBJECT_RETRIEVED_AT


def test_roe_ttm_none_when_absent() -> None:
    pack = _compile(["roe_ttm"], manifest=_subject_only(_empty_payload()))
    assert pack.get("roe_ttm").value is None


def test_roa_ttm_from_highlights() -> None:
    pack = _compile(["roa_ttm"])
    assert pack.get("roa_ttm").value == 0.09


def test_roa_ttm_none_when_absent() -> None:
    pack = _compile(["roa_ttm"], manifest=_subject_only(_empty_payload()))
    assert pack.get("roa_ttm").value is None


def test_roic_ttm_substitutes_return_on_assets() -> None:
    # EODHD lacks a direct ROIC field; the extractor documents the
    # substitution to ReturnOnAssetsTTM.
    pack = _compile(["roic_ttm"])
    assert pack.get("roic_ttm").value == 0.09


def test_roic_ttm_none_when_absent() -> None:
    pack = _compile(["roic_ttm"], manifest=_subject_only(_empty_payload()))
    assert pack.get("roic_ttm").value is None


def test_sbc_annual_populates() -> None:
    pack = _compile(["sbc_annual"])
    fact = pack.get("sbc_annual")
    assert fact.value == [3.0, 3.5, 4.0, 4.5, 5.0]
    assert fact.data_as_of == SUBJECT_FILING_DATE


def test_sbc_annual_none_when_absent() -> None:
    pack = _compile(["sbc_annual"], manifest=_subject_only(_empty_payload()))
    assert pack.get("sbc_annual").value is None


def test_buyback_authorization_documented_none() -> None:
    # EODHD does not expose buyback authorizations; the extractor returns
    # None so a future LLM-tier or catalyst-pack extractor can fill it.
    pack = _compile(["buyback_authorization"])
    fact = pack.get("buyback_authorization")
    assert fact.value is None
    assert fact.source_ids == [1]
    assert fact.source_tier == "vendor"


def test_dividend_per_share_annual_from_highlights() -> None:
    pack = _compile(["dividend_per_share_annual"])
    assert pack.get("dividend_per_share_annual").value == 1.25


def test_dividend_per_share_annual_falls_back_to_splits_dividends() -> None:
    payload = _full_payload()
    payload["Highlights"]["DividendShare"] = None
    payload["SplitsDividends"] = {"ForwardAnnualDividendRate": 2.40}
    pack = _compile(["dividend_per_share_annual"], manifest=_subject_only(payload))
    assert pack.get("dividend_per_share_annual").value == 2.40


def test_dividend_per_share_annual_none_when_absent() -> None:
    pack = _compile(["dividend_per_share_annual"], manifest=_subject_only(_empty_payload()))
    assert pack.get("dividend_per_share_annual").value is None


def test_dividend_yield_populates() -> None:
    pack = _compile(["dividend_yield"])
    assert pack.get("dividend_yield").value == 0.012


def test_dividend_yield_none_when_absent() -> None:
    pack = _compile(["dividend_yield"], manifest=_subject_only(_empty_payload()))
    assert pack.get("dividend_yield").value is None


def test_beta_prefers_technicals_block() -> None:
    pack = _compile(["beta"])
    assert pack.get("beta").value == 1.05


def test_beta_falls_back_to_highlights() -> None:
    payload = _full_payload()
    del payload["Technicals"]
    pack = _compile(["beta"], manifest=_subject_only(payload))
    assert pack.get("beta").value == 1.10


def test_beta_none_when_absent() -> None:
    pack = _compile(["beta"], manifest=_subject_only(_empty_payload()))
    assert pack.get("beta").value is None


def test_shares_outstanding_populates() -> None:
    pack = _compile(["shares_outstanding"])
    assert pack.get("shares_outstanding").value == 250_000_000.0


def test_shares_outstanding_none_when_absent() -> None:
    pack = _compile(["shares_outstanding"], manifest=_subject_only(_empty_payload()))
    assert pack.get("shares_outstanding").value is None


def test_float_shares_populates() -> None:
    pack = _compile(["float_shares"])
    assert pack.get("float_shares").value == 220_000_000.0


def test_float_shares_none_when_absent() -> None:
    pack = _compile(["float_shares"], manifest=_subject_only(_empty_payload()))
    assert pack.get("float_shares").value is None


def test_short_interest_pct_populates() -> None:
    pack = _compile(["short_interest_pct"])
    assert pack.get("short_interest_pct").value == 0.025


def test_short_interest_pct_none_when_absent() -> None:
    pack = _compile(["short_interest_pct"], manifest=_subject_only(_empty_payload()))
    assert pack.get("short_interest_pct").value is None


# ---------------------------------------------------------------------------
# Group 3 — Forward consensus
# ---------------------------------------------------------------------------


def test_consensus_revenue_fy_next_pulls_first_future_year() -> None:
    pack = _compile(["consensus_revenue_fy_next"])
    fact = pack.get("consensus_revenue_fy_next")
    assert fact.value == 220.0
    assert fact.source_tier == "vendor"


def test_consensus_revenue_fy_next_plus_one_pulls_second_future_year() -> None:
    pack = _compile(["consensus_revenue_fy_next_plus_one"])
    assert pack.get("consensus_revenue_fy_next_plus_one").value == 260.0


def test_consensus_revenue_fy_next_plus_two_pulls_third_future_year() -> None:
    pack = _compile(["consensus_revenue_fy_next_plus_two"])
    assert pack.get("consensus_revenue_fy_next_plus_two").value == 300.0


def test_consensus_eps_fy_next_pulls_first_future_year() -> None:
    pack = _compile(["consensus_eps_fy_next"])
    assert pack.get("consensus_eps_fy_next").value == 2.10


def test_consensus_eps_fy_next_plus_one_pulls_second_future_year() -> None:
    pack = _compile(["consensus_eps_fy_next_plus_one"])
    assert pack.get("consensus_eps_fy_next_plus_one").value == 2.55


def test_consensus_eps_fy_next_plus_two_pulls_third_future_year() -> None:
    pack = _compile(["consensus_eps_fy_next_plus_two"])
    assert pack.get("consensus_eps_fy_next_plus_two").value == 3.00


def test_consensus_revenue_fy_next_none_when_absent() -> None:
    pack = _compile(["consensus_revenue_fy_next"], manifest=_subject_only(_empty_payload()))
    assert pack.get("consensus_revenue_fy_next").value is None


def test_consensus_eps_fy_next_none_when_absent() -> None:
    pack = _compile(["consensus_eps_fy_next"], manifest=_subject_only(_empty_payload()))
    assert pack.get("consensus_eps_fy_next").value is None


def test_consensus_revenue_growth_fy_next_derived() -> None:
    pack = _compile(["consensus_revenue_growth_fy_next"])
    fact = pack.get("consensus_revenue_growth_fy_next")
    # latest revenue = 100 + 4*20 = 180; next FY consensus = 220
    assert fact.value == pytest.approx(220.0 / 180.0 - 1.0)
    assert fact.source_tier == "derived"
    assert fact.depends_on == ["consensus_revenue_fy_next", "revenue_annual"]


def test_consensus_revenue_growth_fy_next_none_when_inputs_missing() -> None:
    pack = _compile(["consensus_revenue_growth_fy_next"], manifest=_subject_only(_empty_payload()))
    assert pack.get("consensus_revenue_growth_fy_next").value is None


def test_consensus_eps_growth_fy_next_derived() -> None:
    pack = _compile(["consensus_eps_growth_fy_next"])
    fact = pack.get("consensus_eps_growth_fy_next")
    # eps latest = 1.0 + 4*0.2 = 1.8; next FY EPS = 2.10
    assert fact.value == pytest.approx(2.10 / 1.80 - 1.0)
    assert fact.source_tier == "derived"


def test_consensus_growth_data_as_of_tracks_consensus_side_not_annual_anchor() -> None:
    """Regression: derived growth facts inherited the older (annual) date from
    their historical anchor and tripped the consensus_ 14-day freshness budget
    even when the consensus estimate itself was fresh. The fix points the
    derived `data_as_of` at the consensus side (the newer of the two)."""
    from datetime import UTC, datetime

    from openlia.llm.runtime.report_v2.facts.extractors.stock_initiation import (
        _newest_dep_as_of,
    )
    from openlia.llm.runtime.report_v2.types import Fact

    consensus = Fact(
        name="consensus_revenue_fy_next",
        value=100.0,
        source_ids=[1],
        extractor="deterministic",
        data_as_of=datetime(2026, 5, 15, tzinfo=UTC),
    )
    annual = Fact(
        name="revenue_annual",
        value=[80.0, 90.0, 95.0],
        source_ids=[1],
        extractor="deterministic",
        data_as_of=datetime(2026, 1, 31, tzinfo=UTC),
    )
    assert _newest_dep_as_of(consensus, annual) == datetime(2026, 5, 15, tzinfo=UTC)
    # Order independence.
    assert _newest_dep_as_of(annual, consensus) == datetime(2026, 5, 15, tzinfo=UTC)
    # Missing data_as_of is ignored, not treated as max.
    no_date = Fact(
        name="consensus_revenue_fy_next",
        value=100.0,
        source_ids=[1],
        extractor="deterministic",
        data_as_of=None,
    )
    assert _newest_dep_as_of(no_date, annual) == datetime(2026, 1, 31, tzinfo=UTC)


def test_next_quarter_revenue_guide_midpoint_populates() -> None:
    pack = _compile(["next_quarter_revenue_guide_midpoint"])
    assert pack.get("next_quarter_revenue_guide_midpoint").value == 55.0


def test_next_quarter_revenue_guide_low_populates() -> None:
    pack = _compile(["next_quarter_revenue_guide_low"])
    assert pack.get("next_quarter_revenue_guide_low").value == 50.0


def test_next_quarter_revenue_guide_high_populates() -> None:
    pack = _compile(["next_quarter_revenue_guide_high"])
    assert pack.get("next_quarter_revenue_guide_high").value == 60.0


def test_next_quarter_revenue_guide_none_when_absent() -> None:
    pack = _compile(
        [
            "next_quarter_revenue_guide_midpoint",
            "next_quarter_revenue_guide_low",
            "next_quarter_revenue_guide_high",
        ],
        manifest=_subject_only(_empty_payload()),
    )
    assert pack.get("next_quarter_revenue_guide_midpoint").value is None
    assert pack.get("next_quarter_revenue_guide_low").value is None
    assert pack.get("next_quarter_revenue_guide_high").value is None


# ---------------------------------------------------------------------------
# Group 4 — Peer absolute sizes
# ---------------------------------------------------------------------------


def test_peer_market_cap_dict_keyed_by_ticker() -> None:
    pack = _compile(["peer_market_cap"], manifest=_subject_plus_peers())
    fact = pack.get("peer_market_cap")
    assert fact.value == {"PRA": 500_000_000.0, "PRB": 750_000_000.0}
    # source_ids point to peer manifest entries only
    assert set(fact.source_ids) == {2, 3}
    assert fact.source_tier == "vendor"


def test_peer_market_cap_falls_back_to_subject_when_no_peers() -> None:
    pack = _compile(["peer_market_cap"], manifest=_subject_only(_full_payload()))
    fact = pack.get("peer_market_cap")
    assert fact.value == {}
    # source_ids fallback to subject manifest id
    assert fact.source_ids == [1]


def test_peer_revenue_ttm_dict_populates() -> None:
    pack = _compile(["peer_revenue_ttm"], manifest=_subject_plus_peers())
    assert pack.get("peer_revenue_ttm").value == {"PRA": 80.0, "PRB": 100.0}


def test_peer_net_margin_ttm_dict_populates() -> None:
    pack = _compile(["peer_net_margin_ttm"], manifest=_subject_plus_peers())
    assert pack.get("peer_net_margin_ttm").value == {"PRA": 0.15, "PRB": 0.18}


def test_peer_operating_margin_ttm_dict_populates() -> None:
    pack = _compile(["peer_operating_margin_ttm"], manifest=_subject_plus_peers())
    assert pack.get("peer_operating_margin_ttm").value == {"PRA": 0.20, "PRB": 0.22}


def test_peer_fcf_yield_computed_per_peer() -> None:
    pack = _compile(["peer_fcf_yield"], manifest=_subject_plus_peers())
    fact = pack.get("peer_fcf_yield")
    # PRA: fcf = 80 * 0.20 = 16; mcap = 5e8 -> 3.2e-8
    # PRB: fcf = 100 * 0.20 = 20; mcap = 7.5e8 -> ~2.667e-8
    assert fact.value["PRA"] == pytest.approx(16.0 / 500_000_000.0)
    assert fact.value["PRB"] == pytest.approx(20.0 / 750_000_000.0)


def test_peer_fcf_yield_empty_when_peer_cashflow_missing() -> None:
    # Peers that lack cash flow detail should drop out cleanly.
    manifest = [
        _entry(1, "get_fundamentals_data/TST.US", _full_payload()),
        _entry(
            2,
            "get_fundamentals_data/PRA.US",
            {
                "General": {"Sector": "Technology"},
                "Highlights": {"MarketCapitalization": 5_000_000.0},
                "Financials": {},
            },
        ),
    ]
    pack = _compile(["peer_fcf_yield"], manifest=manifest)
    assert pack.get("peer_fcf_yield").value == {}


# ---------------------------------------------------------------------------
# Group 5 — Forward valuation
# ---------------------------------------------------------------------------


def test_ev_to_ebitda_forward_documented_none() -> None:
    # EODHD does not expose forward EV/EBITDA; future WS7 helper will compute.
    pack = _compile(["ev_to_ebitda_forward"])
    fact = pack.get("ev_to_ebitda_forward")
    assert fact.value is None
    assert fact.source_ids == [1]


def test_ev_to_sales_forward_documented_none() -> None:
    pack = _compile(["ev_to_sales_forward"])
    fact = pack.get("ev_to_sales_forward")
    assert fact.value is None
    assert fact.source_ids == [1]


def test_fcf_yield_derived_from_fcf_and_market_cap() -> None:
    pack = _compile(["fcf_yield"])
    fact = pack.get("fcf_yield")
    # latest fcf = 27, market cap = 1_000_000_000
    assert fact.value == pytest.approx(27.0 / 1_000_000_000.0)
    assert fact.source_tier == "derived"
    assert fact.depends_on == ["free_cash_flow_annual", "market_cap"]


def test_fcf_yield_none_when_inputs_missing() -> None:
    pack = _compile(["fcf_yield"], manifest=_subject_only(_empty_payload()))
    assert pack.get("fcf_yield").value is None


# ---------------------------------------------------------------------------
# Peer-set sufficiency gate
# ---------------------------------------------------------------------------


def test_count_peer_fundamentals_excludes_subject() -> None:
    manifest = _subject_plus_peers()
    assert count_peer_fundamentals(manifest, subject_ticker="TST") == 2


def test_count_peer_fundamentals_subject_only_returns_zero() -> None:
    manifest = _subject_only(_full_payload())
    assert count_peer_fundamentals(manifest, subject_ticker="TST") == 0


def _good_section_md(section_id: str) -> str:
    body = " ".join(["word"] * 500) + " [1]."
    return f"""---
section_id: {section_id}
title: {section_id.replace("_", " ").title()}
sources_used: [1]
synthesis_hooks:
  thesis_contribution: "Strong thesis"
  bull_case_inputs: ["Growth case [1]"]
  bear_case_inputs: ["Risk case [1]"]
---

## {section_id}

{body}
"""


def _extract_section_id(prompt: str) -> str:
    for line in prompt.splitlines():
        if "Section:" in line:
            return line.split("Section:")[1].split(".")[0].strip().lower().replace(" ", "_")
    return "company_overview"


FIXTURE = (
    Path(__file__).parent.parent.parent.parent.parent
    / "fixtures"
    / "report_v2"
    / "eodhd_fundamentals_net.json"
)


@pytest.mark.asyncio
async def test_runner_raises_insufficient_peer_set_when_peers_below_two() -> None:
    """End-to-end: a single-ticker manifest (no peers) fails the gate."""
    fundamentals = json.loads(FIXTURE.read_text())

    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = lambda provider, tool, args: (
        fundamentals if tool == "get_fundamentals_data" else {"ok": True}
    )

    websearch = AsyncMock()
    websearch.search.return_value = []

    preflight_provider = AsyncMock()
    preflight_provider.structured_output.return_value = {
        "searches": [],
        "fetches": [],
        "proposed_facts": [],
    }

    writer = AsyncMock()
    writer.write.side_effect = lambda prompt: _good_section_md(_extract_section_id(prompt))

    runner = WavedReportRunner(
        report_type="stock_initiation",
        ticker="NET.US",
        dispatcher=dispatcher,
        websearch=websearch,
        preflight_provider=preflight_provider,
        body_writer=writer,
        synthesis_writer=writer,
        freshness_override=True,
        # peer_set_override defaults False — gate must fire.
    )
    with pytest.raises(InsufficientPeerSetError) as exc_info:
        await runner.run()
    assert exc_info.value.peer_count == 0
    assert exc_info.value.minimum == 2


@pytest.mark.asyncio
async def test_runner_peer_set_override_bypasses_gate() -> None:
    """End-to-end: setting peer_set_override=True lets the run proceed."""
    fundamentals = json.loads(FIXTURE.read_text())

    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = lambda provider, tool, args: (
        fundamentals if tool == "get_fundamentals_data" else {"ok": True}
    )

    websearch = AsyncMock()
    websearch.search.return_value = []

    preflight_provider = AsyncMock()
    preflight_provider.structured_output.return_value = {
        "searches": [],
        "fetches": [],
        "proposed_facts": [],
    }

    writer = AsyncMock()
    writer.write.side_effect = lambda prompt: _good_section_md(_extract_section_id(prompt))

    runner = WavedReportRunner(
        report_type="stock_initiation",
        ticker="NET.US",
        dispatcher=dispatcher,
        websearch=websearch,
        preflight_provider=preflight_provider,
        body_writer=writer,
        synthesis_writer=writer,
        freshness_override=True,
        peer_set_override=True,
    )
    report = await runner.run()
    assert report.schema.cover.ticker == "NET.US"
