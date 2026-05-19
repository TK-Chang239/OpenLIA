"""Analyst-coverage fact extractors and full income-statement / balance-sheet
series. These power the deterministic analyst section header and the
always-included historical financial tables.

The no-advocacy policy makes these facts the *only* source of buy/hold/sell
labels and price targets in the report — the LLM is forbidden from authoring
them. Coverage on the empty-payload path is therefore load-bearing: when an
issuer has no analyst coverage, the facts must resolve to None so the
assembler can omit the verdict card and section header cleanly.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.registry import default_registry
from openlia.llm.runtime.report_v2.types import ManifestEntry


def _entry(id: int, identifier: str, payload: dict) -> ManifestEntry:
    return ManifestEntry(
        id=id,
        kind="fetch",
        provider="eodhd",
        identifier=identifier,
        raw_payload=payload,
        retrieved_at="2026-05-19T05:00:00Z",
    )


def _fundamentals_with_analysts(**overrides) -> dict:
    """EODHD-shape fundamentals payload with the fields the new extractors need."""
    base = {
        "General": {
            "Name": "Salesforce, Inc.",
            "Sector": "Technology",
            "Exchange": "NYSE",
            "IPODate": "2004-06-23",
            "FullTimeEmployees": 76000,
            "AddressData": {"City": "San Francisco", "State": "CA", "Country": "USA"},
        },
        "Highlights": {
            "MarketCapitalization": 141_900_000_000,
            "PERatio": 22.2,
            "ForwardPE": 18.5,
            "WallStreetTargetPrice": 320.0,
            "ProfitMargin": 0.16,
            "OperatingMarginTTM": 0.21,
            "EBITDA": 12_400_000_000,
            "RevenueTTM": 41_500_000_000,
            "EarningsShare": 6.83,
        },
        "AnalystRatings": {
            "Rating": 2.1,
            "TargetPrice": 320.0,
            "StrongBuy": 18,
            "Buy": 22,
            "Hold": 8,
            "Sell": 1,
            "StrongSell": 0,
        },
        "Financials": {
            "Income_Statement": {
                "yearly": {
                    f"{2020 + i}-12-31": {
                        "totalRevenue": 26_500_000_000 + i * 3_750_000_000,
                        "costOfRevenue": 7_000_000_000 + i * 800_000_000,
                        "grossProfit": 19_500_000_000 + i * 3_200_000_000,
                        "operatingIncome": 5_000_000_000 + i * 1_200_000_000,
                        "netIncome": 4_100_000_000 + i * 1_000_000_000,
                        "eps": 4.5 + i * 0.5,
                    }
                    for i in range(5)
                }
            },
            "Balance_Sheet": {
                "yearly": {
                    f"{2020 + i}-12-31": {
                        "totalAssets": 50_000_000_000 + i * 5_000_000_000,
                        "totalLiab": 20_000_000_000 + i * 2_000_000_000,
                        "totalStockholderEquity": 30_000_000_000 + i * 3_000_000_000,
                        "cash": 5_000_000_000 + i * 500_000_000,
                        "shortLongTermDebtTotal": 8_000_000_000 + i * 800_000_000,
                    }
                    for i in range(5)
                }
            },
        },
    }
    for k, v in overrides.items():
        base[k] = v
    return base


def _make_manifest(payload: dict) -> list[ManifestEntry]:
    return [_entry(1, "get_fundamentals_data/CRM.US", payload)]


def test_analyst_consensus_rating_maps_to_buy() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=["analyst_consensus_rating"],
        subject_ticker="CRM",
    )
    assert pack.get("analyst_consensus_rating").value == "Buy"


def test_analyst_consensus_rating_handles_strong_buy() -> None:
    payload = _fundamentals_with_analysts()
    payload["AnalystRatings"]["Rating"] = 1.2
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(payload),
        requested_facts=["analyst_consensus_rating"],
        subject_ticker="CRM",
    )
    assert pack.get("analyst_consensus_rating").value == "Strong Buy"


def test_analyst_consensus_rating_handles_strong_sell() -> None:
    payload = _fundamentals_with_analysts()
    payload["AnalystRatings"]["Rating"] = 4.8
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(payload),
        requested_facts=["analyst_consensus_rating"],
        subject_ticker="CRM",
    )
    assert pack.get("analyst_consensus_rating").value == "Strong Sell"


def test_analyst_consensus_rating_none_when_no_coverage() -> None:
    payload = _fundamentals_with_analysts()
    payload["AnalystRatings"] = None
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(payload),
        requested_facts=["analyst_consensus_rating"],
        subject_ticker="CRM",
    )
    assert pack.get("analyst_consensus_rating").value is None


def test_analyst_target_mean_prefers_wallstreet_target() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=["analyst_target_mean"],
        subject_ticker="CRM",
    )
    assert pack.get("analyst_target_mean").value == 320.0


def test_analyst_target_mean_falls_back_to_analyst_block() -> None:
    payload = _fundamentals_with_analysts()
    payload["Highlights"]["WallStreetTargetPrice"] = None
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(payload),
        requested_facts=["analyst_target_mean"],
        subject_ticker="CRM",
    )
    assert pack.get("analyst_target_mean").value == 320.0


def test_analyst_count_sums_buckets() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=["analyst_count"],
        subject_ticker="CRM",
    )
    assert pack.get("analyst_count").value == 49  # 18+22+8+1+0


def test_analyst_rating_distribution_returns_nonzero_buckets() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=["analyst_rating_distribution"],
        subject_ticker="CRM",
    )
    value = pack.get("analyst_rating_distribution").value
    assert value == {"StrongBuy": 18, "Buy": 22, "Hold": 8, "Sell": 1}
    # StrongSell is 0 — must be omitted from the dict, not rendered as a 0 bar.
    assert "StrongSell" not in value


def test_consensus_upside_pct_computed_from_target_and_price() -> None:
    payload = _fundamentals_with_analysts()
    pack = compile_pack(
        registry=default_registry,
        manifest=[
            _entry(1, "get_fundamentals_data/CRM.US", payload),
            _entry(2, "get_live_stock_prices/CRM.US", {"close": 320.0 / 1.10}),
        ],
        requested_facts=["consensus_upside_pct"],
        subject_ticker="CRM",
    )
    upside = pack.get("consensus_upside_pct").value
    assert upside == pytest.approx(0.10, rel=1e-3)


def test_consensus_upside_pct_none_when_price_missing() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=["consensus_upside_pct"],
        subject_ticker="CRM",
    )
    assert pack.get("consensus_upside_pct").value is None


# ---------------------------------------------------------------------------
# Subject identity facts
# ---------------------------------------------------------------------------


def test_ipo_date_employees_exchange_hq() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=["ipo_date", "employees", "exchange", "headquarters"],
        subject_ticker="CRM",
    )
    assert pack.get("ipo_date").value == "2004-06-23"
    assert pack.get("employees").value == 76000
    assert pack.get("exchange").value == "NYSE"
    assert pack.get("headquarters").value == "San Francisco, CA, USA"


def test_headquarters_handles_partial_address() -> None:
    payload = _fundamentals_with_analysts()
    payload["General"]["AddressData"] = {"City": "Austin", "State": "TX"}
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(payload),
        requested_facts=["headquarters"],
        subject_ticker="CRM",
    )
    assert pack.get("headquarters").value == "Austin, TX"


# ---------------------------------------------------------------------------
# Income statement / balance sheet series
# ---------------------------------------------------------------------------


def test_full_income_statement_series_extracted() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=[
            "cogs_annual",
            "operating_income_annual",
            "net_income_annual",
            "eps_annual",
            "revenue_years",
        ],
        subject_ticker="CRM",
    )
    assert pack.get("cogs_annual").value == [
        7_000_000_000.0,
        7_800_000_000.0,
        8_600_000_000.0,
        9_400_000_000.0,
        10_200_000_000.0,
    ]
    assert pack.get("operating_income_annual").value[0] == 5_000_000_000.0
    assert pack.get("net_income_annual").value[-1] == 8_100_000_000.0
    assert pack.get("eps_annual").value == [4.5, 5.0, 5.5, 6.0, 6.5]
    assert pack.get("revenue_years").value == [
        "2020-12-31",
        "2021-12-31",
        "2022-12-31",
        "2023-12-31",
        "2024-12-31",
    ]


def test_balance_sheet_series_extracted() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=[
            "total_assets_annual",
            "total_liabilities_annual",
            "equity_annual",
            "cash_annual",
            "total_debt_annual",
        ],
        subject_ticker="CRM",
    )
    assert pack.get("total_assets_annual").value[0] == 50_000_000_000.0
    assert pack.get("total_liabilities_annual").value[-1] == 28_000_000_000.0
    assert pack.get("equity_annual").value[-1] == 42_000_000_000.0
    assert pack.get("cash_annual").value[0] == 5_000_000_000.0
    assert pack.get("total_debt_annual").value[-1] == 11_200_000_000.0


# ---------------------------------------------------------------------------
# Margin progression (computed from series)
# ---------------------------------------------------------------------------


def test_margin_progression_computed() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_make_manifest(_fundamentals_with_analysts()),
        requested_facts=[
            "gross_margin_annual",
            "operating_margin_annual",
            "net_margin_annual",
        ],
        subject_ticker="CRM",
    )
    gm = pack.get("gross_margin_annual").value
    om = pack.get("operating_margin_annual").value
    nm = pack.get("net_margin_annual").value
    assert len(gm) == 5
    assert gm[0] == pytest.approx(19_500_000_000 / 26_500_000_000, rel=1e-3)
    assert om[0] == pytest.approx(5_000_000_000 / 26_500_000_000, rel=1e-3)
    assert nm[-1] == pytest.approx(8_100_000_000 / 41_500_000_000, rel=1e-3)
