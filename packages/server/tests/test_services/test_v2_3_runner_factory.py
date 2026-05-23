"""Integration tests for `make_v2_3_runner_factory`.

The factory's job is to assemble a `ReportRunner` for one request. These
tests exercise the wiring: when no synthesizer client is supplied the
SYNTHESIZE slot stays NoOp (PR3 behavior preserved); when one is supplied
the real `SynthesizeStage` runs and produces a thesis once it is reached
in the pipeline.

Bundle and outline are pre-populated on the input state to stand in for
PLAN + RESEARCH, which are still NoOps until later PRs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.clients.clarifier import FakeClarifierClient
from openlia.llm.runtime.report_v2_3.clients.planner import (
    FakePlannerClient,
    PlannerRequest,
)
from openlia.llm.runtime.report_v2_3.clients.synthesizer import FakeSynthesizerClient
from openlia.llm.runtime.report_v2_3.clients.verifier import (
    FakeVerifierClient,
    VerifierRequest,
)
from openlia.llm.runtime.report_v2_3.clients.writer import (
    FakeWriterClient,
    WriterRequest,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    ClarifyProceed,
    DataProviderSource,
    IssueKind,
    IssueSeverity,
    Language,
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    RunStatus,
    SectionMandate,
    ValuationPlan,
    VerifyIssue,
    VerifyResult,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia_server.services.v2_3_runner_factory import make_v2_3_runner_factory


def _seed_state() -> ReportState:
    state = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )
    src = DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )
    state.bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=src),
        },
    )
    state.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
    )
    return state


def _thesis() -> ReportThesis:
    return ReportThesis(
        language=Language.EN,
        central_argument="durable growth",
        key_takeaways=["x"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="rev_ttm", display="$100M")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="business overview",
                does_not_cover="valuation",
                relevant_fact_ids=["rev_ttm"],
            )
        ],
        charts=[],
    )


def test_factory_default_keeps_synthesize_as_noop() -> None:
    factory = make_v2_3_runner_factory(
        FakeClarifierClient(result=ClarifyProceed(assumptions=["x"]))
    )
    runner = factory()
    state = runner.start(_seed_state())
    assert state.status == RunStatus.COMPLETE
    # No synthesizer wired => thesis must remain unset.
    assert state.thesis is None


def test_factory_with_synthesizer_populates_thesis() -> None:
    expected = _thesis()
    fake_synth = FakeSynthesizerClient(result=expected)
    factory = make_v2_3_runner_factory(
        FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])),
        synthesizer_client=fake_synth,
    )
    runner = factory()
    state = runner.start(_seed_state())

    assert state.status == RunStatus.COMPLETE
    assert state.thesis is expected
    assert len(fake_synth.calls) == 1
    request = fake_synth.calls[0]
    assert request.bundle.tickers == ["NVDA"]
    assert {s.id for s in request.outline.sections} == {"overview"}
    # CLARIFY result must flow through to SYNTHESIZE.
    assert isinstance(request.clarify_result, ClarifyProceed)
    assert request.clarify_result.assumptions == ["x"]


def test_factory_synthesize_failure_marks_run_failed() -> None:
    """If the synthesizer returns a thesis that fails validation, the stage
    raises and the runner converts that into a FAILED state — better than
    silently advancing to WRITE with a broken thesis."""
    bad_thesis = ReportThesis(
        language=Language.EN,
        central_argument="x",
        key_takeaways=["x"],
        valuation_stance="x",
        valuation_plan=ValuationPlan(),
        canonical_figures=[],
        # mandate references a section NOT in our seeded outline.
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="x",
                does_not_cover="y",
                relevant_fact_ids=["rev_ttm", "ghost"],
            )
        ],
        charts=[],
    )
    factory = make_v2_3_runner_factory(
        FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])),
        synthesizer_client=FakeSynthesizerClient(result=bad_thesis),
    )
    state = factory().start(_seed_state())
    assert state.status == RunStatus.FAILED
    assert state.last_error is not None
    assert "synthesize" in state.last_error


def test_factory_with_planner_populates_outline() -> None:
    """Planner wired alone: outline must land on state.outline. Bundle/
    outline pre-seeding from `_seed_state` is overwritten by the real
    planner — that's the contract."""
    fresh_outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(id="thesis", title="Thesis"),
            OutlineSection(id="risks", title="Risks"),
        ],
    )
    fake_planner = FakePlannerClient(result=fresh_outline)
    factory = make_v2_3_runner_factory(
        FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])),
        planner_client=fake_planner,
    )

    state = factory().start(_seed_state())
    assert state.status == RunStatus.COMPLETE
    assert state.outline is fresh_outline
    assert [s.id for s in state.outline.sections] == ["thesis", "risks"]
    assert len(fake_planner.calls) == 1
    request = fake_planner.calls[0]
    assert isinstance(request, PlannerRequest)
    assert request.tickers == ["NVDA"]
    # CLARIFY result must flow into PLAN — the planner needs the captured
    # assumptions to shape the outline.
    assert isinstance(request.clarify_result, ClarifyProceed)
    assert request.clarify_result.assumptions == ["x"]


def test_factory_planner_output_flows_to_synthesizer() -> None:
    """When PLAN + SYNTHESIZE are both real, the outline PLAN produces is
    the one SYNTHESIZE receives — the runner threads stage outputs into
    the next stage's input through ReportState."""
    fresh_outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
    )
    fake_planner = FakePlannerClient(result=fresh_outline)
    fake_synth = FakeSynthesizerClient(result=_thesis())
    factory = make_v2_3_runner_factory(
        FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])),
        planner_client=fake_planner,
        synthesizer_client=fake_synth,
    )

    state = factory().start(_seed_state())
    assert state.status == RunStatus.COMPLETE
    # The synthesizer must have been called with the outline PLAN produced,
    # not the one pre-seeded by `_seed_state`.
    assert fake_synth.calls[0].outline is fresh_outline


def test_factory_with_writer_populates_sections() -> None:
    """When a writer client is wired and a thesis is on the state, the
    runner reaches WRITE and produces one section per mandate."""

    def _responder(req: WriterRequest) -> WrittenSection:
        sid = req.section_mandate.section_id
        return WrittenSection(
            section_id=sid,
            title=sid.title(),
            body=f"body of {sid} citing {{{{CITE:rev_ttm}}}}",
        )

    fake_writer = FakeWriterClient(responder=_responder)
    factory = make_v2_3_runner_factory(
        FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])),
        synthesizer_client=FakeSynthesizerClient(result=_thesis()),
        writer_client=fake_writer,
    )

    state = factory().start(_seed_state())
    assert state.status == RunStatus.COMPLETE
    assert [s.section_id for s in state.sections] == ["overview"]
    assert state.sections[0].cited_fact_ids() == ["rev_ttm"]
    assert len(fake_writer.calls) == 1


def test_verify_high_issue_triggers_write_retry_through_factory() -> None:
    """End-to-end verify->write retry across real PLAN+SYNTHESIZE+WRITE+
    VERIFY: first VERIFY emits HIGH issue, runner re-runs WRITE, second
    VERIFY returns clean, run COMPLETES with retry_count=1."""

    def _writer_responder(req: WriterRequest) -> WrittenSection:
        sid = req.section_mandate.section_id
        # On retry, the body changes slightly so we can see the rewrite.
        suffix = " (rewritten)" if req.prior_attempt is not None else ""
        return WrittenSection(
            section_id=sid,
            title=sid.title(),
            body=f"body of {sid} citing {{{{CITE:rev_ttm}}}}{suffix}",
        )

    verifier_calls = {"n": 0}

    def _verifier_responder(req: VerifierRequest) -> VerifyResult:
        verifier_calls["n"] += 1
        if verifier_calls["n"] == 1:
            return VerifyResult(
                issues=[
                    VerifyIssue(
                        section_id="overview",
                        kind=IssueKind.VALUE_MISMATCH,
                        severity=IssueSeverity.HIGH,
                        detail="prose says X but bundle says Y",
                    )
                ]
            )
        return VerifyResult()

    fake_writer = FakeWriterClient(responder=_writer_responder)
    factory = make_v2_3_runner_factory(
        FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])),
        synthesizer_client=FakeSynthesizerClient(result=_thesis()),
        writer_client=fake_writer,
        verifier_client=FakeVerifierClient(responder=_verifier_responder),
    )

    state = factory().start(_seed_state())
    assert state.status == RunStatus.COMPLETE
    assert state.retry_count == 1
    assert verifier_calls["n"] == 2
    # Writer must have run twice (original + retry); the second call
    # carried prior_attempt + critique.
    assert len(fake_writer.calls) == 2
    second_call = fake_writer.calls[1]
    assert second_call.prior_attempt is not None
    assert second_call.critique is not None
    assert len(second_call.critique) == 1
    assert second_call.critique[0].kind == IssueKind.VALUE_MISMATCH
    # Final section body reflects the rewrite suffix.
    assert state.sections[0].body.endswith("(rewritten)")


def test_verify_clean_run_does_not_retry() -> None:
    """No issues -> runner advances straight to ASSEMBLE; no rewrite."""

    def _writer_responder(req: WriterRequest) -> WrittenSection:
        sid = req.section_mandate.section_id
        return WrittenSection(
            section_id=sid,
            title=sid.title(),
            body=f"body of {sid} citing {{{{CITE:rev_ttm}}}}",
        )

    fake_writer = FakeWriterClient(responder=_writer_responder)
    factory = make_v2_3_runner_factory(
        FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])),
        synthesizer_client=FakeSynthesizerClient(result=_thesis()),
        writer_client=fake_writer,
        verifier_client=FakeVerifierClient(result=VerifyResult()),
    )
    state = factory().start(_seed_state())
    assert state.status == RunStatus.COMPLETE
    assert state.retry_count == 0
    assert len(fake_writer.calls) == 1
