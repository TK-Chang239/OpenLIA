from __future__ import annotations

from datetime import UTC, datetime

import pytest
from _macro_research_fakes import FakeDataProvider, FakeLLMClient
from openlia.macro_research.assembler import DashboardAssembler


@pytest.fixture
def assembler() -> DashboardAssembler:
    data = FakeDataProvider(
        values={
            "stock_quote:TIP": {"price": 110.0},
            "stock_quote:UUP": {"price": 30.0},
            "macro_indicator:debt_gdp": 120.0,
            "macro_indicator:interest_revenue": 16.0,
            "stock_quote:HYG": {"price": 75.0},
            "stock_quote:LQD": {"price": 105.0},
            "macro_indicator:pmi": 49.0,
            "macro_indicator:gdp_yoy": 1.5,
            "macro_indicator:cpi_yoy": 3.8,
        }
    )
    llm = FakeLLMClient(scripted_response={"assessment": "stub", "severity": "amber"})
    return DashboardAssembler(data_provider=data, llm_client=llm)


def test_runs_t1_t2_t3_live(assembler: DashboardAssembler) -> None:
    result = assembler.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=False,
    )
    tiers = {t.tier for t in result.tiers}
    assert {"T1", "T2", "T3"}.issubset(tiers)


def test_honours_cached_t4(assembler: DashboardAssembler) -> None:
    cached = {
        "assessment": "cached text",
        "severity": "red",
        "generated_at": datetime.now(UTC),
    }
    result = assembler.run(
        dashboard_slug="world_order",
        user_id="u-1",
        portfolio=None,
        t4_cached=cached,
        smart_mode=False,
    )
    t4 = next(t for t in result.tiers if t.tier == "T4")
    assert t4.data["assessment"] == "cached text"


def test_unknown_slug_raises(assembler: DashboardAssembler) -> None:
    with pytest.raises(KeyError):
        assembler.run(
            dashboard_slug="nonexistent",
            user_id="u-1",
            portfolio=None,
            t4_cached=None,
            smart_mode=False,
        )


def test_severity_derives_from_worst_tier(assembler: DashboardAssembler) -> None:
    result = assembler.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached={
            "assessment": "stub",
            "severity": "red",
            "generated_at": datetime.now(UTC),
        },
        smart_mode=False,
    )
    assert result.severity == "red"


def test_integration_debt_cycle_red_phase() -> None:
    data = FakeDataProvider(
        values={
            "macro_indicator:debt_gdp": 130.0,
            "macro_indicator:interest_revenue": 22.0,
            "stock_quote:TIP": {"price": 110.0},
            "stock_quote:UUP": {"price": 28.5},
        }
    )
    asm = DashboardAssembler(data_provider=data, llm_client=FakeLLMClient())
    result = asm.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached={
            "assessment": "Late-cycle",
            "severity": "red",
            "generated_at": datetime.now(UTC),
        },
        smart_mode=False,
    )
    assert result.severity == "red"
    t3 = next(t for t in result.tiers if t.tier == "T3")
    assert t3.data["phase"] == "Deleveraging"


def test_smart_mode_propagates_to_t5_tier() -> None:
    data = FakeDataProvider(
        values={
            "macro_indicator:debt_gdp": 95.0,
            "macro_indicator:interest_revenue": 12.0,
            "stock_quote:TIP": {"price": 110.0},
            "stock_quote:UUP": {"price": 30.0},
        }
    )
    asm = DashboardAssembler(data_provider=data)
    result = asm.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=True,
    )
    t5 = next(t for t in result.tiers if t.tier == "T5")
    assert t5.data["smart_mode"] is True


def test_integration_four_seasons_summer() -> None:
    data = FakeDataProvider(
        values={
            "macro_indicator:pmi": 55.0,
            "macro_indicator:gdp_yoy": 2.8,
            "macro_indicator:cpi_yoy": 4.5,
            "macro_indicator:cpi_core_yoy": 4.2,
            "stock_quote:HYG": {"price": 73.0},
            "stock_quote:LQD": {"price": 102.0},
        }
    )
    asm = DashboardAssembler(data_provider=data)
    result = asm.run(
        dashboard_slug="four_seasons",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=False,
    )
    t3 = next(t for t in result.tiers if t.tier == "T3")
    assert t3.data["season"] == "Summer"


def test_integration_all_weather_red_on_concentration() -> None:
    asm = DashboardAssembler(data_provider=FakeDataProvider())
    result = asm.run(
        dashboard_slug="all_weather",
        user_id="u-1",
        portfolio={"equities": 0.95, "long_bonds": 0.05},
        t4_cached=None,
        smart_mode=False,
    )
    assert result.severity == "red"
    t3 = next(t for t in result.tiers if t.tier == "T3")
    assert t3.data["overall_coverage_label"] == "Concentrated"


def test_integration_world_order_with_cached_t4() -> None:
    data = FakeDataProvider(
        values={
            "macro_indicator:usd_fx_reserve_share": 58.0,
            "macro_indicator:cb_gold_purchases": 1030.0,
            "macro_indicator:foreign_treasury_holdings": 7500.0,
            "stock_quote:UUP": {"price": 28.0},
            "company_news:geopolitical": [],
        }
    )
    asm = DashboardAssembler(data_provider=data, llm_client=FakeLLMClient())
    result = asm.run(
        dashboard_slug="world_order",
        user_id="u-1",
        portfolio=None,
        t4_cached={
            "assessment": "Stage 5 pressure",
            "severity": "red",
            "stage": "Pressure",
            "generated_at": datetime.now(UTC),
        },
        smart_mode=False,
    )
    t4 = next(t for t in result.tiers if t.tier == "T4")
    assert t4.data["assessment"] == "Stage 5 pressure"
    assert result.severity == "red"


def test_integration_five_forces_turning_point() -> None:
    data = FakeDataProvider(
        values={
            "force_debt_money": 8,
            "force_political": 8,
            "force_geopolitical": 7,
            "force_technology": 7,
            "force_natural": 6,
        }
    )
    asm = DashboardAssembler(data_provider=data)
    result = asm.run(
        dashboard_slug="five_forces",
        user_id="u-1",
        portfolio=None,
        t4_cached={
            "assessment": "Forces stacking",
            "severity": "red",
            "active_force_count": 4,
            "generated_at": datetime.now(UTC),
        },
        smart_mode=False,
    )
    t3 = next(t for t in result.tiers if t.tier == "T3")
    assert t3.data["bucket"] == "Historical turning point zone"
    assert result.severity == "red"
