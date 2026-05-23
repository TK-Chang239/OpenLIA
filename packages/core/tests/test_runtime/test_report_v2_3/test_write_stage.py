"""Unit tests for WriteStage — preconditions, placeholder discipline, retry."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.clients.writer import (
    FakeWriterClient,
    WriterRequest,
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
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    ValuationPlan,
    VerifyIssue,
    VerifyResult,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.stages import StageContext, WriteStage
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
            "moat": BundleFact(id="moat", label="Moat", value="network", source=_src()),
        },
    )


def _outline() -> Outline:
    return Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(id="overview", title="Overview"),
            OutlineSection(id="financials", title="Financials"),
        ],
    )


def _thesis(*, with_chart: bool = True) -> ReportThesis:
    charts: list[ChartSpec] = []
    chart_ids_for_financials: list[str] = []
    if with_chart:
        charts = [
            ChartSpec(
                id="rev_chart",
                section_id="financials",
                claim="revenue rising",
                chart_type=ChartType.LINE,
                title="Revenue",
                category_labels=["Q1", "Q2"],
                series=[ChartSeries(name="rev", value_fact_ids=["rev_ttm"])],
            )
        ]
        chart_ids_for_financials = ["rev_chart"]

    return ReportThesis(
        language=Language.EN,
        central_argument="Durable growth.",
        key_takeaways=["beat", "raise"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="gm", display="65.0%")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="business overview",
                does_not_cover="financial line items",
                chart_ids=[],
                relevant_fact_ids=["moat"],
            ),
            SectionMandate(
                section_id="financials",
                covers="financial line items",
                does_not_cover="overview",
                chart_ids=chart_ids_for_financials,
                relevant_fact_ids=["rev_ttm", "gm"],
            ),
        ],
        charts=charts,
    )


def _state(*, with_chart: bool = True) -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )
    s.bundle = _bundle()
    s.outline = _outline()
    s.thesis = _thesis(with_chart=with_chart)
    return s


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def _responder_for_mandates(
    bodies: dict[str, str],
) -> callable:
    def _make(request: WriterRequest) -> WrittenSection:
        sid = request.section_mandate.section_id
        return WrittenSection(
            section_id=sid,
            title=sid.title(),
            body=bodies[sid],
        )

    return _make


# ---------------------------------------------------------------------------
# Happy path + slice filtering
# ---------------------------------------------------------------------------


def test_happy_path_writes_one_section_per_mandate() -> None:
    bodies = {
        "overview": "Moat type: {{CITE:moat}}.",
        "financials": "Revenue is {{CITE:rev_ttm}} and see {{FIG:rev_chart}}.",
    }
    client = FakeWriterClient(responder=_responder_for_mandates(bodies))
    stage = WriteStage(client)

    state = stage.run(_state(), _ctx())

    assert [s.section_id for s in state.sections] == ["overview", "financials"]
    assert state.sections[1].body.startswith("Revenue is")
    assert len(client.calls) == 2


def test_writer_only_sees_mandate_facts_and_charts() -> None:
    """Each writer request must carry the per-mandate slice — not the
    full bundle and not the full chart list."""
    bodies = {"overview": "Moat: {{CITE:moat}}.", "financials": "Rev: {{CITE:rev_ttm}}."}
    client = FakeWriterClient(responder=_responder_for_mandates(bodies))
    WriteStage(client).run(_state(), _ctx())

    overview_call = client.calls[0]
    financials_call = client.calls[1]
    assert set(overview_call.relevant_facts.keys()) == {"moat"}
    assert overview_call.assigned_charts == []
    assert set(financials_call.relevant_facts.keys()) == {"rev_ttm", "gm"}
    assert [c.id for c in financials_call.assigned_charts] == ["rev_chart"]


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


def test_missing_thesis_raises() -> None:
    state = _state()
    state.thesis = None
    with pytest.raises(RuntimeError, match=r"state\.thesis"):
        WriteStage(
            FakeWriterClient(result=WrittenSection(section_id="x", title="x", body=""))
        ).run(state, _ctx())


def test_missing_bundle_raises() -> None:
    state = _state()
    state.bundle = None
    with pytest.raises(RuntimeError, match=r"state\.bundle"):
        WriteStage(
            FakeWriterClient(result=WrittenSection(section_id="x", title="x", body=""))
        ).run(state, _ctx())


# ---------------------------------------------------------------------------
# Placeholder discipline
# ---------------------------------------------------------------------------


def test_writer_returning_wrong_section_id_raises() -> None:
    def _wrong_id(req: WriterRequest) -> WrittenSection:
        return WrittenSection(section_id="not_the_mandate", title="x", body="")

    with pytest.raises(RuntimeError, match="section_id"):
        WriteStage(FakeWriterClient(responder=_wrong_id)).run(_state(), _ctx())


def test_section_citing_fact_outside_mandate_raises() -> None:
    """The 'overview' mandate only allows {{CITE:moat}}, but the writer
    tries to cite a fact from the 'financials' slice — must reject."""

    bodies = {
        "overview": "Sneaky: {{CITE:rev_ttm}}.",  # rev_ttm is not in overview's slice
        "financials": "Rev: {{CITE:rev_ttm}}.",
    }
    client = FakeWriterClient(responder=_responder_for_mandates(bodies))
    with pytest.raises(RuntimeError, match="cites facts outside"):
        WriteStage(client).run(_state(), _ctx())


def test_section_referencing_chart_outside_mandate_raises() -> None:
    """Only 'financials' has rev_chart assigned; 'overview' references it."""
    bodies = {
        "overview": "See {{FIG:rev_chart}}.",
        "financials": "Rev: {{CITE:rev_ttm}}.",
    }
    client = FakeWriterClient(responder=_responder_for_mandates(bodies))
    with pytest.raises(RuntimeError, match="charts outside"):
        WriteStage(client).run(_state(), _ctx())


# ---------------------------------------------------------------------------
# Verify -> rewrite retry plumbing
# ---------------------------------------------------------------------------


def test_retry_passes_prior_attempt_and_critique_to_writer() -> None:
    """When state.verify_result + prior state.sections are populated (as
    happens on the runner's verify->write retry), the next WRITE call
    must carry them so the writer can target the rewrite."""
    state = _state()
    state.sections = [
        WrittenSection(section_id="overview", title="Overview", body="old {{CITE:moat}}"),
        WrittenSection(section_id="financials", title="Financials", body="old {{CITE:rev_ttm}}"),
    ]
    state.verify_result = VerifyResult(
        issues=[
            VerifyIssue(
                section_id="financials",
                kind=IssueKind.VALUE_MISMATCH,
                severity=IssueSeverity.HIGH,
                detail="stated 14% but bundle says 14.2%",
            )
        ]
    )

    bodies = {
        "overview": "{{CITE:moat}}",
        "financials": "Rev: {{CITE:rev_ttm}}.",
    }
    client = FakeWriterClient(responder=_responder_for_mandates(bodies))
    WriteStage(client).run(state, _ctx())

    overview_call = next(c for c in client.calls if c.section_mandate.section_id == "overview")
    financials_call = next(c for c in client.calls if c.section_mandate.section_id == "financials")

    assert overview_call.prior_attempt is not None
    assert overview_call.prior_attempt.body == "old {{CITE:moat}}"
    # Overview had no critique, so the critique slice should be None or empty.
    assert not overview_call.critique

    assert financials_call.prior_attempt is not None
    assert financials_call.critique is not None
    assert len(financials_call.critique) == 1
    assert financials_call.critique[0].kind == IssueKind.VALUE_MISMATCH
