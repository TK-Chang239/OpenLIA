"""Unit tests for the v2.3 /payload projection — lane coverage signals.

Exercises ``_project_payload`` directly so we don't have to thread a
full LLM stack through the route fixture to prove a single field
round-trips. The projection logic is the only piece the route layer
owns between ``state.verify_result.{data,web}_coverage`` and the JSON
the frontend reads.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    DataProviderSource,
    LaneCoverage,
    Language,
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    ResolvedReport,
    ValuationPlan,
    VerifyResult,
)
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import get_builtin
from openlia_server.routes.departments.equity_research_v2_3 import _project_payload


def _state_for_projection() -> ReportState:
    """Build the minimal completed state ``_project_payload`` needs."""
    state = ReportState(
        run_id="r1",
        user_id="u1",
        raw_prompt="init NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
    )
    state.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
    )
    state.bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "gm": BundleFact(
                id="gm",
                label="Gross margin",
                value=0.65,
                source=DataProviderSource(
                    provider="EODHD",
                    endpoint="fundamentals",
                    period="TTM",
                    retrieved_at=datetime.now(UTC),
                ),
            )
        },
    )
    state.thesis = ReportThesis(
        language=Language.EN,
        central_argument="Thesis intact.",
        key_takeaways=["Takeaway."],
        valuation_stance="Buy.",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="gm", display="65.0%")],
        mandates=[],
        charts=[],
    )
    state.resolved = ResolvedReport(
        section_bodies={"overview": "Body."},
        footnotes=["EODHD (fundamentals), TTM."],
        figure_labels={},
    )
    return state


def test_projection_omits_coverage_when_verify_result_is_none() -> None:
    """An older run that completed before VERIFY populated the signal
    must still project cleanly with both lane coverage fields None."""
    state = _state_for_projection()
    state.verify_result = None
    payload = _project_payload(state)
    assert payload.data_coverage is None
    assert payload.web_coverage is None
    assert payload.narrative_coverage is None


def test_projection_omits_coverage_when_lane_signals_are_none() -> None:
    """VerifyStage already encodes N/A as ``None`` on each lane; the
    route must not invent a zero-coverage block for either."""
    state = _state_for_projection()
    state.verify_result = VerifyResult(issues=[], data_coverage=None, web_coverage=None)
    payload = _project_payload(state)
    assert payload.data_coverage is None
    assert payload.web_coverage is None
    assert payload.narrative_coverage is None


def test_projection_surfaces_data_and_web_coverage_when_present() -> None:
    state = _state_for_projection()
    state.verify_result = VerifyResult(
        issues=[],
        data_coverage=LaneCoverage(total=5, satisfied=5, pct=1.0),
        web_coverage=LaneCoverage(total=4, satisfied=3, pct=0.75),
    )
    payload = _project_payload(state)

    assert payload.data_coverage is not None
    assert payload.data_coverage.total == 5
    assert payload.data_coverage.satisfied == 5
    assert payload.data_coverage.pct == 1.0

    assert payload.web_coverage is not None
    assert payload.web_coverage.total == 4
    assert payload.web_coverage.satisfied == 3
    assert payload.web_coverage.pct == 0.75


def test_projection_mirrors_web_coverage_into_narrative_coverage_alias() -> None:
    """Until the frontend coverage chip migrates to the new lane names,
    the route mirrors web_coverage into narrative_coverage so the
    existing 'Narrative coverage' chip keeps rendering."""
    state = _state_for_projection()
    state.verify_result = VerifyResult(
        issues=[],
        data_coverage=LaneCoverage(total=5, satisfied=5, pct=1.0),
        web_coverage=LaneCoverage(total=4, satisfied=3, pct=0.75),
    )
    payload = _project_payload(state)
    assert payload.narrative_coverage is not None
    assert payload.narrative_coverage.total == 4
    assert payload.narrative_coverage.satisfied == 3
    assert payload.narrative_coverage.pct == 0.75
