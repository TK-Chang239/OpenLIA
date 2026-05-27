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
    DataNeed,
    DataProviderSource,
    IssueKind,
    IssueSeverity,
    Language,
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    ValuationPlan,
    VerifyIssue,
    VerifyResult,
    WebSource,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.stages import StageContext, VerifyStage
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import get_builtin


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
        template=get_builtin(ReportType.INITIATION),
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


# ---------------------------------------------------------------------------
# Narrative coverage signal (soft — not a gate)
# ---------------------------------------------------------------------------


def _web_src(url: str = "https://example.com/article") -> WebSource:
    return WebSource(
        url=url,
        title="article",
        publisher="Example",
        snippet="snip",
        retrieved_at=datetime.now(UTC),
    )


def _state_with_outline(*, outline: Outline, bundle: ResearchBundle) -> ReportState:
    s = _state()
    s.outline = outline
    s.bundle = bundle
    return s


def test_lane_coverage_is_none_for_both_lanes_when_no_outline() -> None:
    """No outline → no signal in either lane. The runner's plan path
    always populates outline before VERIFY, but the helper handles
    None defensively so paused runs and older tests don't crash."""
    state = _state()
    state.outline = None
    stage = VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[])))
    stage.run(state, _ctx())
    assert state.verify_result is not None
    assert state.verify_result.data_coverage is None
    assert state.verify_result.web_coverage is None


# ---------------------------------------------------------------------------
# Dual-lane coverage (TDD red-tests for the data/web lane refactor)
#
# Replaces the single narrative_coverage signal with per-lane scoring so a
# report can show that BOTH the structured (EODHD) and open-web lanes
# fired. The RKLB regression — model satisfies a web-lane id with an
# EODHD news fact — must surface as web_coverage.pct=0 even when the id
# itself is present in the bundle.
# ---------------------------------------------------------------------------


def test_verify_result_has_separate_data_and_web_coverage_fields() -> None:
    """VerifyResult exposes data_coverage and web_coverage in place of
    the single narrative_coverage block. Each scores its lane
    independently so a report can show both lanes fired."""
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="risks",
                title="Risks",
                data_needs=[
                    DataNeed(
                        description="revenue history",
                        data_fact_ids=["rev_ttm"],
                    ),
                    DataNeed(
                        description="analyst price targets",
                        web_fact_ids=["analyst_pt"],
                    ),
                ],
            )
        ],
    )
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=_src()),
            # analyst_pt deliberately absent — web lane is unsatisfied
        },
    )
    state = _state_with_outline(outline=outline, bundle=bundle)
    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(state, _ctx())

    dc = state.verify_result.data_coverage  # type: ignore[union-attr]
    wc = state.verify_result.web_coverage  # type: ignore[union-attr]
    assert dc is not None and dc.total == 1 and dc.satisfied == 1 and dc.pct == 1.0
    assert wc is not None and wc.total == 1 and wc.satisfied == 0 and wc.pct == 0.0


def test_layered_need_counts_once_per_lane() -> None:
    """A single DataNeed that lists ids in BOTH lanes contributes one to
    each lane's denominator. The need is satisfied per-lane independently."""
    outline = Outline(
        tickers=["RKLB"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[
                    DataNeed(
                        description="recent news + framing",
                        data_fact_ids=["news_headlines"],
                        web_fact_ids=["news_framing"],
                    ),
                ],
            )
        ],
    )
    bundle = ResearchBundle(
        tickers=["RKLB"],
        facts={
            "news_headlines": BundleFact(
                id="news_headlines", label="Headlines", value="..", source=_src()
            ),
            "news_framing": BundleFact(
                id="news_framing", label="Framing", value="..", source=_web_src()
            ),
        },
    )
    state = _state_with_outline(outline=outline, bundle=bundle)
    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(state, _ctx())
    dc = state.verify_result.data_coverage  # type: ignore[union-attr]
    wc = state.verify_result.web_coverage  # type: ignore[union-attr]
    assert dc.total == 1 and dc.satisfied == 1
    assert wc.total == 1 and wc.satisfied == 1


def test_web_lane_zero_when_id_present_but_backed_by_data_provider_source() -> None:
    """The RKLB regression: model emits a fact with an id from
    web_fact_ids, but the fact's source is DataProviderSource (it came
    from get_company_news, not web_search). The web lane must score
    this as UNSATISFIED — the entire point of the metric is to surface
    this silent substitution."""
    outline = Outline(
        tickers=["RKLB"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="risks",
                title="Risks",
                data_needs=[
                    DataNeed(
                        description="analyst commentary on RKLB",
                        web_fact_ids=["analyst_commentary"],
                    ),
                ],
            )
        ],
    )
    bundle = ResearchBundle(
        tickers=["RKLB"],
        facts={
            "analyst_commentary": BundleFact(
                id="analyst_commentary",
                label="Analyst commentary",
                # The fact exists with the expected id, but source is
                # DataProviderSource — exactly the failure mode the
                # metric is built to catch.
                value="Headline from EODHD news, no framing.",
                source=_src(),
            ),
        },
    )
    state = _state_with_outline(outline=outline, bundle=bundle)
    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(state, _ctx())
    wc = state.verify_result.web_coverage  # type: ignore[union-attr]
    assert wc is not None
    assert wc.total == 1
    assert wc.satisfied == 0
    assert wc.pct == 0.0


def test_data_lane_zero_when_id_present_but_backed_by_web_source() -> None:
    """Symmetric to the web-lane mismatch test: an id listed in
    data_fact_ids that's only ever backed by a WebSource fails the
    data lane. This prevents the model from declaring victory on a
    structured need with an open-web hit."""
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="fin",
                title="Financials",
                data_needs=[
                    DataNeed(
                        description="revenue TTM (structured)",
                        data_fact_ids=["rev_ttm"],
                    ),
                ],
            )
        ],
    )
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": BundleFact(
                id="rev_ttm",
                label="Revenue TTM",
                value=100.0,
                source=_web_src(),  # wrong lane
            ),
        },
    )
    state = _state_with_outline(outline=outline, bundle=bundle)
    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(state, _ctx())
    dc = state.verify_result.data_coverage  # type: ignore[union-attr]
    assert dc is not None and dc.total == 1 and dc.satisfied == 0 and dc.pct == 0.0


def test_lane_coverage_is_none_when_no_needs_in_that_lane() -> None:
    """An outline with only data_fact_ids needs reports
    web_coverage=None (N/A), not zero. Mirrors the prior
    narrative_coverage convention so cover-page renderers can
    distinguish 'measured and failed' from 'nothing to measure'."""
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="fin",
                title="Financials",
                data_needs=[
                    DataNeed(description="rev", data_fact_ids=["rev_ttm"]),
                ],
            )
        ],
    )
    state = _state_with_outline(outline=outline, bundle=_bundle())
    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(state, _ctx())
    assert state.verify_result.data_coverage is not None  # type: ignore[union-attr]
    assert state.verify_result.web_coverage is None  # type: ignore[union-attr]


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
