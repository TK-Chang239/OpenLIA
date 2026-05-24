"""Unit tests for ResearchStage — dispatch + ticker validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.clients.researcher import (
    FakeResearcherClient,
    ResearchRequest,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    ClarifyProceed,
    DataNeed,
    DataProviderSource,
    Language,
    Outline,
    OutlineSection,
    ReportType,
    ResearchBundle,
)
from openlia.llm.runtime.report_v2_3.stages import ResearchStage, StageContext
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import get_builtin


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _state() -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
    )
    s.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="financials",
                title="Financials",
                data_needs=[
                    DataNeed(description="revenue last 8 quarters", expected_fact_ids=["rev_q"]),
                ],
            )
        ],
    )
    s.clarify_result = ClarifyProceed(assumptions=["audience: PM"])
    return s


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def _bundle(tickers: list[str] | None = None) -> ResearchBundle:
    return ResearchBundle(
        tickers=tickers if tickers is not None else ["NVDA"],
        facts={
            "rev_ttm": BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=_src()),
        },
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_writes_bundle_to_state() -> None:
    expected = _bundle()
    client = FakeResearcherClient(result=expected)

    state = ResearchStage(client).run(_state(), _ctx())
    assert state.bundle is expected
    assert len(client.calls) == 1
    request = client.calls[0]
    assert isinstance(request, ResearchRequest)
    assert request.tickers == ["NVDA"]
    assert request.raw_prompt == "initiate on NVDA"
    assert isinstance(request.clarify_result, ClarifyProceed)
    # outline.data_needs is what RESEARCH consumes — confirm it flows through.
    section = request.outline.sections[0]
    assert section.data_needs[0].description == "revenue last 8 quarters"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_bundle_with_mismatched_tickers_raises() -> None:
    """A researcher cannot silently widen scope to other tickers."""
    bad = _bundle(tickers=["AAPL"])
    client = FakeResearcherClient(result=bad)
    with pytest.raises(RuntimeError, match="tickers"):
        ResearchStage(client).run(_state(), _ctx())


def test_missing_outline_raises() -> None:
    state = _state()
    state.outline = None
    client = FakeResearcherClient(result=_bundle())
    with pytest.raises(RuntimeError, match=r"state\.outline"):
        ResearchStage(client).run(state, _ctx())


# ---------------------------------------------------------------------------
# Fake configuration guards
# ---------------------------------------------------------------------------


def test_fake_researcher_rejects_double_config() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        FakeResearcherClient(result=_bundle(), responder=lambda r: _bundle())
    with pytest.raises(ValueError, match="exactly one"):
        FakeResearcherClient()  # type: ignore[call-arg]


def test_fake_researcher_responder_varies_by_request() -> None:
    """Useful when a test wants the bundle to depend on outline.data_needs."""

    def _responder(req: ResearchRequest) -> ResearchBundle:
        return _bundle()

    client = FakeResearcherClient(responder=_responder)
    state = ResearchStage(client).run(_state(), _ctx())
    assert state.bundle is not None
    assert "rev_ttm" in state.bundle.facts
