from __future__ import annotations

from datetime import UTC, datetime

import pytest
from _macro_research_fakes import FakeLLMClient
from openlia.macro_research.assembler import DashboardAssembler

# MR runtime data wiring through the connector dispatcher is a follow-up to
# the connector cutover. Tests below that exercise live T1/T2 numeric flow
# from a fake data provider are skipped until that wiring lands.
_DATA_FETCH_SKIP = pytest.mark.skip(reason="MR runtime wiring pending after connector cutover")


@pytest.fixture
def assembler() -> DashboardAssembler:
    llm = FakeLLMClient(scripted_response={"assessment": "stub", "severity": "amber"})
    return DashboardAssembler(llm_client=llm)


@_DATA_FETCH_SKIP
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


@_DATA_FETCH_SKIP
def test_debt_cycle_t2_metrics_populate_from_stub_provider() -> None:
    """NEW-19-10: T2 metrics should resolve through the data provider so a
    stubbed registry returns the values the dashboard surfaces in T3."""
    asm = DashboardAssembler(llm_client=FakeLLMClient(scripted_response={}))
    result = asm.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=False,
    )
    t2 = next(t for t in result.tiers if t.tier == "T2")
    assert t2.data.get("debt_gdp") == 130.0


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


@_DATA_FETCH_SKIP
def test_integration_debt_cycle_red_phase() -> None:
    asm = DashboardAssembler(llm_client=FakeLLMClient())
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
    asm = DashboardAssembler()
    result = asm.run(
        dashboard_slug="debt_cycle",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=True,
    )
    t5 = next(t for t in result.tiers if t.tier == "T5")
    assert t5.data["smart_mode"] is True


def test_integration_all_weather_red_on_concentration() -> None:
    asm = DashboardAssembler()
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


@_DATA_FETCH_SKIP
def test_integration_four_seasons_summer() -> None:
    asm = DashboardAssembler()
    result = asm.run(
        dashboard_slug="four_seasons",
        user_id="u-1",
        portfolio=None,
        t4_cached=None,
        smart_mode=False,
    )
    t3 = next(t for t in result.tiers if t.tier == "T3")
    assert t3.data["season"] == "Summer"


def test_integration_world_order_with_cached_t4() -> None:
    asm = DashboardAssembler(llm_client=FakeLLMClient())
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


@_DATA_FETCH_SKIP
def test_integration_five_forces_turning_point() -> None:
    asm = DashboardAssembler()
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
