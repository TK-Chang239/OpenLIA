"""Tests for the v2.2 token-cost telemetry module.

Covers:
  - TelemetryCollector records Stage7aMaterializeEvent with expected fields.
  - TelemetryCollector records Stage7bDrafterCallEvent with expected fields.
  - snapshot() aggregates correctly across multiple events.
  - materialize_section() emits events when telemetry= is passed.
  - materialize() emits events when telemetry= is passed.
  - merge() combines two collectors.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_2.enums import Fidelity
from openlia.llm.runtime.report_v2_2.materialize import (
    materialize,
    materialize_section,
)
from openlia.llm.runtime.report_v2_2.section_plan import (
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
)
from openlia.llm.runtime.report_v2_2.telemetry import (
    Stage7aMaterializeEvent,
    Stage7bDrafterCallEvent,
    TelemetryCollector,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ARTIFACTS = {
    "dcf_output": {"ticker": "MSFT", "dcf_equity_value_per_share": 312.0, "wacc": 9.8},
    "ratio_output": {"ticker": "MSFT", "pe_forward": 28.5, "ev_ebitda": 22.1},
}

_SECTION_PLAN = SectionPlan(
    section_id="valuation_dcf",
    title="Valuation DCF",
    artifacts=[
        SectionArtifactRef(artifact_id="dcf_output", fidelity=Fidelity.FULL),
    ],
)

_REPORT_PLAN = ReportSectionPlan(
    template_id="test_template",
    sections=[
        SectionPlan(
            section_id="exec_summary",
            title="Executive Summary",
            artifacts=[
                SectionArtifactRef(artifact_id="dcf_output", fidelity=Fidelity.HEADLINE),
            ],
        ),
        SectionPlan(
            section_id="valuation",
            title="Valuation",
            artifacts=[
                SectionArtifactRef(artifact_id="ratio_output", fidelity=Fidelity.SUMMARY),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Unit tests for TelemetryCollector
# ---------------------------------------------------------------------------


class TestTelemetryCollector:
    def test_record_materialize_emits_event(self) -> None:
        collector = TelemetryCollector()
        collector.record_materialize(
            section_id="valuation_dcf",
            artifact_id="dcf_output",
            helper_name="__materialization__",
            fidelity="full",
            rendered_chars=480,
            was_truncated=False,
        )
        events = collector.events()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, Stage7aMaterializeEvent)
        assert evt.section_id == "valuation_dcf"
        assert evt.artifact_id == "dcf_output"
        assert evt.helper_name == "__materialization__"
        assert evt.fidelity == "full"
        assert evt.rendered_chars == 480
        assert evt.was_truncated is False
        assert evt.ts  # non-empty ISO timestamp

    def test_record_drafter_call_emits_event(self) -> None:
        collector = TelemetryCollector()
        collector.record_drafter_call(
            section_id="valuation_dcf",
            fidelity="full",
            tokens_in=420,
            tokens_out=310,
            cached_tokens=200,
        )
        events = collector.events()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, Stage7bDrafterCallEvent)
        assert evt.section_id == "valuation_dcf"
        assert evt.fidelity == "full"
        assert evt.tokens_in == 420
        assert evt.tokens_out == 310
        assert evt.cached_tokens == 200
        assert evt.ts

    def test_snapshot_aggregates_multiple_events(self) -> None:
        collector = TelemetryCollector()
        collector.record_materialize(
            section_id="s1",
            artifact_id="a1",
            helper_name="h1",
            fidelity="headline",
            rendered_chars=100,
            was_truncated=False,
        )
        collector.record_materialize(
            section_id="s1",
            artifact_id="a2",
            helper_name="h1",
            fidelity="summary",
            rendered_chars=200,
            was_truncated=True,
        )
        collector.record_drafter_call(
            section_id="s1",
            fidelity="summary",
            tokens_in=300,
            tokens_out=150,
            cached_tokens=100,
        )
        collector.record_drafter_call(
            section_id="s2",
            fidelity="full",
            tokens_in=500,
            tokens_out=200,
            cached_tokens=0,
        )

        snap = collector.snapshot()
        assert snap["total_rendered_chars"] == 300
        assert snap["total_tokens_in"] == 800
        assert snap["total_tokens_out"] == 350
        assert snap["total_cached_tokens"] == 100
        assert snap["materialize_events"] == 2
        assert snap["drafter_call_events"] == 2

        s1 = snap["per_section"]["s1"]
        assert s1["rendered_chars"] == 300
        assert s1["artifact_count"] == 2
        assert s1["truncated_count"] == 1
        assert s1["tokens_in"] == 300
        assert s1["tokens_out"] == 150
        assert s1["cached_tokens"] == 100

        s2 = snap["per_section"]["s2"]
        assert s2["tokens_in"] == 500

        # All raw events serialised in snapshot.
        assert len(snap["events"]) == 4

    def test_snapshot_empty_collector(self) -> None:
        collector = TelemetryCollector()
        snap = collector.snapshot()
        assert snap["total_rendered_chars"] == 0
        assert snap["total_tokens_in"] == 0
        assert snap["materialize_events"] == 0
        assert snap["drafter_call_events"] == 0
        assert snap["per_section"] == {}
        assert snap["events"] == []

    def test_merge_combines_events(self) -> None:
        c1 = TelemetryCollector()
        c1.record_materialize(
            section_id="s1",
            artifact_id="a1",
            helper_name="h1",
            fidelity="full",
            rendered_chars=100,
            was_truncated=False,
        )
        c2 = TelemetryCollector()
        c2.record_drafter_call(
            section_id="s1",
            fidelity="full",
            tokens_in=300,
            tokens_out=100,
        )
        c1.merge(c2)
        assert len(c1.events()) == 2
        snap = c1.snapshot()
        assert snap["materialize_events"] == 1
        assert snap["drafter_call_events"] == 1

    def test_drafter_call_defaults_cached_to_zero(self) -> None:
        collector = TelemetryCollector()
        collector.record_drafter_call(
            section_id="s1",
            tokens_in=100,
            tokens_out=50,
        )
        evt = collector.events()[0]
        assert isinstance(evt, Stage7bDrafterCallEvent)
        assert evt.cached_tokens == 0

    def test_event_type_literals(self) -> None:
        assert Stage7aMaterializeEvent.TYPE == "report_v2_2.stage7a.materialize"
        assert Stage7bDrafterCallEvent.TYPE == "report_v2_2.stage7b.drafter_call"


# ---------------------------------------------------------------------------
# Integration: materialize_section() with telemetry
# ---------------------------------------------------------------------------


class TestMaterializeSectionTelemetry:
    def test_materialize_section_emits_event(self) -> None:
        collector = TelemetryCollector()
        materialize_section(_SECTION_PLAN, _ARTIFACTS, telemetry=collector)

        events = collector.events()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, Stage7aMaterializeEvent)
        assert evt.section_id == "valuation_dcf"
        assert evt.artifact_id == "dcf_output"
        assert evt.fidelity == "full"
        assert evt.rendered_chars > 0

    def test_materialize_section_no_telemetry_is_noop(self) -> None:
        # Should not raise even with telemetry=None (default).
        ms = materialize_section(_SECTION_PLAN, _ARTIFACTS)
        assert ms.section_id == "valuation_dcf"

    def test_materialize_section_multiple_artifacts_all_recorded(self) -> None:
        plan = SectionPlan(
            section_id="multi",
            title="Multi",
            artifacts=[
                SectionArtifactRef(artifact_id="dcf_output", fidelity=Fidelity.HEADLINE),
                SectionArtifactRef(artifact_id="ratio_output", fidelity=Fidelity.SUMMARY),
            ],
        )
        collector = TelemetryCollector()
        materialize_section(plan, _ARTIFACTS, telemetry=collector)

        events = collector.events()
        artifact_ids = [e.artifact_id for e in events if isinstance(e, Stage7aMaterializeEvent)]
        assert "dcf_output" in artifact_ids
        assert "ratio_output" in artifact_ids
        assert len(artifact_ids) == 2


# ---------------------------------------------------------------------------
# Integration: materialize() (full report) with telemetry
# ---------------------------------------------------------------------------


class TestMaterializeFullReportTelemetry:
    def test_materialize_emits_one_event_per_canonical_artifact(self) -> None:
        """materialize() renders each artifact at its canonical (highest) fidelity once.

        _REPORT_PLAN has two sections each referencing a different artifact —
        so 2 canonical render events expected.
        """
        collector = TelemetryCollector()
        materialize(_REPORT_PLAN, _ARTIFACTS, telemetry=collector)

        mat_events = [e for e in collector.events() if isinstance(e, Stage7aMaterializeEvent)]
        # Two distinct artifacts → two events.
        assert len(mat_events) == 2
        recorded_artifact_ids = {e.artifact_id for e in mat_events}
        assert recorded_artifact_ids == {"dcf_output", "ratio_output"}

    def test_materialize_fidelity_recorded_is_canonical(self) -> None:
        """Highest-fidelity-wins: canonical render fidelity logged in the event."""
        collector = TelemetryCollector()
        materialize(_REPORT_PLAN, _ARTIFACTS, telemetry=collector)

        mat_events = {
            e.artifact_id: e for e in collector.events() if isinstance(e, Stage7aMaterializeEvent)
        }
        # exec_summary requests HEADLINE; that's the only reference → canonical = headline.
        assert mat_events["dcf_output"].fidelity == "headline"
        # valuation requests SUMMARY → canonical = summary.
        assert mat_events["ratio_output"].fidelity == "summary"

    def test_materialize_no_telemetry_is_noop(self) -> None:
        # No telemetry= → no crash.
        report = materialize(_REPORT_PLAN, _ARTIFACTS)
        assert len(report.sections) == 2
