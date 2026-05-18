from __future__ import annotations

from openlia.llm.runtime.report_v2.telemetry import ReportTelemetry, WaveTimings
from openlia.llm.runtime.report_v2.types import SectionResult, SectionTerminalState


def test_telemetry_records_section_outcomes() -> None:
    t = ReportTelemetry()
    t.record_section(SectionResult(section_id="a", state=SectionTerminalState.SUCCESS, attempts=1, markdown="..."))
    t.record_section(SectionResult(section_id="b", state=SectionTerminalState.DEGRADED, attempts=2, markdown="..."))
    t.record_section(SectionResult(section_id="c", state=SectionTerminalState.EXHAUSTED, attempts=2, failed_attempts=["x", "y"]))

    snap = t.snapshot()
    assert snap["section_states"]["success"] == 1
    assert snap["section_states"]["degraded"] == 1
    assert snap["section_states"]["exhausted"] == 1
    assert snap["sections"]["a"]["attempts"] == 1
    assert snap["sections"]["c"]["state"] == "exhausted"


def test_telemetry_records_proposed_facts_per_section() -> None:
    t = ReportTelemetry()
    t.record_proposed_facts("industry_overview", ["edge_tam"])
    t.record_proposed_facts("competitive_analysis", ["peer_revenue_growth", "edge_tam"])
    snap = t.snapshot()
    assert snap["proposed_facts"]["industry_overview"] == ["edge_tam"]
    assert "peer_revenue_growth" in snap["proposed_facts"]["competitive_analysis"]


def test_telemetry_records_wave_timings_in_ms() -> None:
    t = ReportTelemetry()
    t.record_wave("W1_baseline", duration_ms=320)
    t.record_wave("W4_body", duration_ms=42000)
    snap = t.snapshot()
    assert snap["wave_ms"]["W1_baseline"] == 320
    assert snap["wave_ms"]["W4_body"] == 42000


def test_telemetry_records_search_sentinels() -> None:
    t = ReportTelemetry()
    t.record_search_sentinel("industry_overview", "edge platform market share 2026")
    snap = t.snapshot()
    assert "industry_overview" in snap["search_sentinels"]
    assert "edge platform market share 2026" in snap["search_sentinels"]["industry_overview"]
