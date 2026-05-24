"""Unit tests for VerifyStage — deterministic checks + LLM merge."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.clients.verifier import (
    FakeVerifierClient,
    VerifierRequest,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    ChartSeries,
    ChartSpec,
    ChartType,
    DataProviderSource,
    IssueKind,
    IssueSeverity,
    Language,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    ValuationPlan,
    VerifyIssue,
    VerifyResult,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.stages import StageContext, VerifyStage
from openlia.llm.runtime.report_v2_3.state import ReportState


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _bundle() -> ResearchBundle:
    return ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=_src()),
            "gm": BundleFact(id="gm", label="Gross margin", value=0.65, source=_src()),
        },
    )


def _thesis() -> ReportThesis:
    return ReportThesis(
        language=Language.EN,
        central_argument="Durable growth.",
        key_takeaways=["beat"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="gm", display="65.0%")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="business overview",
                does_not_cover="financials",
                relevant_fact_ids=["gm"],
            ),
            SectionMandate(
                section_id="financials",
                covers="financials",
                does_not_cover="overview",
                chart_ids=["rev_chart"],
                relevant_fact_ids=["rev_ttm"],
            ),
        ],
        charts=[
            ChartSpec(
                id="rev_chart",
                section_id="financials",
                claim="rev rising",
                chart_type=ChartType.LINE,
                title="Revenue",
                category_labels=["Q1"],
                series=[ChartSeries(name="rev", value_fact_ids=["rev_ttm"])],
            )
        ],
    )


def _state(*, sections: list[WrittenSection] | None = None) -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )
    s.bundle = _bundle()
    s.thesis = _thesis()
    s.sections = (
        sections
        if sections is not None
        else [
            WrittenSection(section_id="overview", title="Overview", body="Margin {{CITE:gm}}."),
            WrittenSection(
                section_id="financials",
                title="Financials",
                body="Rev {{CITE:rev_ttm}} see {{FIG:rev_chart}}.",
            ),
        ]
    )
    return s


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


# ---------------------------------------------------------------------------
# Happy path — clean run
# ---------------------------------------------------------------------------


def test_happy_path_writes_empty_issues_when_all_clean() -> None:
    fake = FakeVerifierClient(result=VerifyResult())
    state = VerifyStage(fake).run(_state(), _ctx())

    assert state.verify_result is not None
    assert state.verify_result.issues == []
    assert state.verify_result.must_rewrite is False
    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert isinstance(request, VerifierRequest)
    assert request.bundle is state.bundle
    assert request.thesis is state.thesis


# ---------------------------------------------------------------------------
# LLM-driven issue propagates
# ---------------------------------------------------------------------------


def test_llm_high_severity_issue_sets_must_rewrite() -> None:
    fake = FakeVerifierClient(
        result=VerifyResult(
            issues=[
                VerifyIssue(
                    section_id="financials",
                    kind=IssueKind.VALUE_MISMATCH,
                    severity=IssueSeverity.HIGH,
                    detail="prose says 14% but fact says 14.2%",
                )
            ]
        )
    )
    state = VerifyStage(fake).run(_state(), _ctx())
    assert state.verify_result is not None
    assert state.verify_result.must_rewrite is True
    assert any(i.kind == IssueKind.VALUE_MISMATCH for i in state.verify_result.issues)


def test_llm_low_severity_only_does_not_block() -> None:
    fake = FakeVerifierClient(
        result=VerifyResult(
            issues=[
                VerifyIssue(
                    section_id=None,
                    kind=IssueKind.REDUNDANCY,
                    severity=IssueSeverity.LOW,
                    detail="minor overlap",
                )
            ]
        )
    )
    state = VerifyStage(fake).run(_state(), _ctx())
    assert state.verify_result is not None
    assert state.verify_result.must_rewrite is False


# ---------------------------------------------------------------------------
# Deterministic dangling-cite / broken-fig detection
# ---------------------------------------------------------------------------


def test_deterministic_dangling_cite_caught_before_llm() -> None:
    sections = [
        WrittenSection(
            section_id="overview",
            title="Overview",
            body="ghost {{CITE:not_in_bundle}}",
        )
    ]
    fake = FakeVerifierClient(result=VerifyResult())
    state = VerifyStage(fake).run(_state(sections=sections), _ctx())

    assert state.verify_result is not None
    issues = state.verify_result.issues
    assert any(
        i.kind == IssueKind.DANGLING_CITE
        and i.severity == IssueSeverity.HIGH
        and i.section_id == "overview"
        for i in issues
    )
    assert state.verify_result.must_rewrite is True


def test_deterministic_broken_fig_ref_caught() -> None:
    sections = [
        WrittenSection(
            section_id="overview",
            title="Overview",
            body="see {{FIG:nonexistent_chart}}",
        )
    ]
    fake = FakeVerifierClient(result=VerifyResult())
    state = VerifyStage(fake).run(_state(sections=sections), _ctx())

    assert state.verify_result is not None
    issues = state.verify_result.issues
    assert any(
        i.kind == IssueKind.BROKEN_FIG_REF and i.severity == IssueSeverity.HIGH for i in issues
    )


def test_deterministic_and_llm_issues_merged() -> None:
    """Both deterministic + LLM issues land in the final result."""
    sections = [
        WrittenSection(
            section_id="overview",
            title="Overview",
            body="ghost {{CITE:not_in_bundle}}",
        )
    ]
    fake = FakeVerifierClient(
        result=VerifyResult(
            issues=[
                VerifyIssue(
                    section_id=None,
                    kind=IssueKind.REDUNDANCY,
                    severity=IssueSeverity.LOW,
                    detail="minor overlap",
                )
            ]
        )
    )
    state = VerifyStage(fake).run(_state(sections=sections), _ctx())
    assert state.verify_result is not None
    kinds = {i.kind for i in state.verify_result.issues}
    assert kinds == {IssueKind.DANGLING_CITE, IssueKind.REDUNDANCY}


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


def test_missing_thesis_raises() -> None:
    state = _state()
    state.thesis = None
    with pytest.raises(RuntimeError, match=r"state\.thesis"):
        VerifyStage(FakeVerifierClient(result=VerifyResult())).run(state, _ctx())


def test_missing_bundle_raises() -> None:
    state = _state()
    state.bundle = None
    with pytest.raises(RuntimeError, match=r"state\.bundle"):
        VerifyStage(FakeVerifierClient(result=VerifyResult())).run(state, _ctx())


def test_missing_sections_raises() -> None:
    state = _state()
    state.sections = []
    with pytest.raises(RuntimeError, match=r"state\.sections"):
        VerifyStage(FakeVerifierClient(result=VerifyResult())).run(state, _ctx())


def test_verify_flags_uncited_number_through_deterministic_path() -> None:
    """A naked number in body text must reach state.verify_result as a
    HIGH UNCITED_NUMBER issue via the deterministic path, even when the
    LLM verifier reports nothing."""
    state = _state(
        sections=[
            WrittenSection(
                section_id="overview",
                title="Overview",
                body="Trades at 15x forward earnings.",
            )
        ]
    )

    stage = VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[])))
    stage.run(state, _ctx())

    assert state.verify_result is not None
    kinds = [i.kind for i in state.verify_result.issues]
    assert IssueKind.UNCITED_NUMBER in kinds
    assert state.verify_result.must_rewrite is True
