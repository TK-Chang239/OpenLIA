"""Repository-surface tests for v2.3: list / delete / docx download."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.report_v2_3.clients.clarifier import FakeClarifierClient
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyNeedsInput,
    ClarifyProceed,
    ClarifyQuestion,
)
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.services.v2_3_runner_factory import make_v2_3_runner_factory


@pytest.fixture
def v2_3_client(tmp_path, monkeypatch):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/v23repo.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/v23repo.db")
    Base.metadata.create_all(session_mod.get_engine())

    with session_mod.SessionLocal() as s:
        s.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                is_admin=True,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    try:
        yield app, TestClient(app)
    finally:
        session_mod.dispose_engine()


def _payload(prompt: str, ticker: str) -> dict:
    return {
        "raw_prompt": prompt,
        "language": "en",
        "report_type": "initiation",
        "tickers": [ticker],
    }


def _install_factory(app, client: FakeClarifierClient) -> None:
    app.state.v2_3_runner_factory = make_v2_3_runner_factory(client)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def test_list_empty(v2_3_client) -> None:
    _, client = v2_3_client
    res = client.get("/api/departments/equity-research/v2.3/runs")
    assert res.status_code == 200
    assert res.json() == []


def test_list_returns_newest_first(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed()))

    for prompt, ticker in [("first", "AAPL"), ("second", "NVDA"), ("third", "AVGO")]:
        r = client.post(
            "/api/departments/equity-research/v2.3/runs",
            json=_payload(prompt, ticker),
        )
        assert r.status_code == 200

    res = client.get("/api/departments/equity-research/v2.3/runs")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 3
    # Newest first — last-inserted should be first row.
    assert body[0]["tickers"] == ["AVGO"]
    assert body[-1]["tickers"] == ["AAPL"]
    # Summary carries the projected fields.
    assert {"run_id", "status", "tickers", "raw_prompt", "report_type", "language"} <= body[
        0
    ].keys()


def test_list_filters_by_status(v2_3_client) -> None:
    app, client = v2_3_client

    # First run suspends (CLARIFY needs input).
    _install_factory(
        app,
        FakeClarifierClient(
            result=ClarifyNeedsInput(
                questions=[
                    ClarifyQuestion(
                        id="h",
                        question="?",
                        why_blocking="why",
                        default="d",
                    )
                ]
            )
        ),
    )
    client.post(
        "/api/departments/equity-research/v2.3/runs",
        json=_payload("suspended one", "NVDA"),
    )

    # Second run proceeds and completes.
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed()))
    client.post(
        "/api/departments/equity-research/v2.3/runs",
        json=_payload("proceed one", "AAPL"),
    )

    waiting = client.get("/api/departments/equity-research/v2.3/runs?status=waiting_on_user")
    complete = client.get("/api/departments/equity-research/v2.3/runs?status=complete")
    assert [r["tickers"] for r in waiting.json()] == [["NVDA"]]
    assert [r["tickers"] for r in complete.json()] == [["AAPL"]]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_removes_run(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed()))
    r = client.post(
        "/api/departments/equity-research/v2.3/runs",
        json=_payload("p", "NVDA"),
    )
    run_id = r.json()["run_id"]

    del_res = client.delete(f"/api/departments/equity-research/v2.3/runs/{run_id}")
    assert del_res.status_code == 204

    follow = client.get(f"/api/departments/equity-research/v2.3/runs/{run_id}")
    assert follow.status_code == 404


def test_delete_unknown_run_404s(v2_3_client) -> None:
    _, client = v2_3_client
    res = client.delete("/api/departments/equity-research/v2.3/runs/does-not-exist")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# DOCX download
# ---------------------------------------------------------------------------


def test_docx_download_works_for_completed_run(v2_3_client) -> None:
    """A run whose state has resolved/outline/thesis/bundle populated
    renders a real .docx. We seed such a state directly since the all-
    NoOp test factory never materializes those slots."""
    import uuid

    from openlia.llm.runtime.report_v2_3.schemas import (
        BundleFact,
        CanonicalFigure,
        DataProviderSource,
        Language,
        Outline,
        OutlineSection,
        ReportThesis,
        ReportType,
        ResearchBundle,
        ResolvedReport,
        RunStatus,
        SectionMandate,
        WrittenSection,
    )
    from openlia.llm.runtime.report_v2_3.state import ReportState
    from openlia_server.services.v2_3_state_store import SqlStateStore

    app, _ = v2_3_client
    run_id = str(uuid.uuid4())
    src = DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )
    state = ReportState(
        run_id=run_id,
        user_id="local",
        raw_prompt="initiate NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        status=RunStatus.COMPLETE,
    )
    state.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
    )
    state.bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={"rev": BundleFact(id="rev", label="Revenue", value=100.0, source=src)},
    )
    state.thesis = ReportThesis(
        language=Language.EN,
        central_argument="x",
        key_takeaways=[],
        valuation_stance="x",
        canonical_figures=[CanonicalFigure(fact_id="rev", display="$100")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="x",
                does_not_cover="y",
                relevant_fact_ids=["rev"],
            )
        ],
        charts=[],
    )
    state.sections = [
        WrittenSection(section_id="overview", title="Overview", body="See {{CITE:rev}}.")
    ]
    state.resolved = ResolvedReport(
        section_bodies={"overview": "See [^1]."},
        footnotes=["EODHD (fundamentals), TTM."],
        figure_labels={},
    )

    with session_mod.SessionLocal() as s:
        SqlStateStore(s).save(state)
        s.commit()

    from fastapi.testclient import TestClient

    with TestClient(app) as fresh_client:
        docx = fresh_client.get(f"/api/departments/equity-research/v2.3/runs/{run_id}/docx")
    assert docx.status_code == 200
    assert docx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    # docx files are zip-based; the magic bytes are "PK".
    assert docx.content[:2] == b"PK"
    # Filename embeds the ticker + a slice of the run id.
    disp = docx.headers["content-disposition"]
    assert 'attachment; filename="v2.3_NVDA_' in disp


def test_payload_returns_structured_view_for_completed_run(v2_3_client) -> None:
    """A completed run exposes the structured payload the React renderer
    consumes. We seed the same state as the docx test and assert the
    Provenance is dropped while the renderable fields survive."""
    import uuid

    from openlia.llm.runtime.report_v2_3.schemas import (
        BundleFact,
        BundleSeries,
        BundleSeriesPoint,
        CanonicalFigure,
        ChartSeries,
        ChartSpec,
        ChartType,
        DataProviderSource,
        Language,
        Outline,
        OutlineSection,
        ReportThesis,
        ReportType,
        ResearchBundle,
        ResolvedReport,
        RunStatus,
        SectionMandate,
        WrittenSection,
    )
    from openlia.llm.runtime.report_v2_3.state import ReportState
    from openlia_server.services.v2_3_state_store import SqlStateStore

    app, _ = v2_3_client
    run_id = str(uuid.uuid4())
    src = DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )
    state = ReportState(
        run_id=run_id,
        user_id="local",
        raw_prompt="initiate NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        status=RunStatus.COMPLETE,
    )
    state.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
    )
    state.bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev": BundleFact(id="rev", label="Revenue", value=100.0, source=src),
            "rev_series": BundleFact(
                id="rev_series",
                label="Revenue (FY)",
                value=BundleSeries(
                    points=[
                        BundleSeriesPoint(period="FY2024", value=60.9),
                        BundleSeriesPoint(period="FY2025", value=88.0),
                    ],
                    unit="USD_billions",
                ),
                source=src,
            ),
        },
    )
    state.thesis = ReportThesis(
        language=Language.EN,
        central_argument="NVDA is the AI-infra leader.",
        key_takeaways=["Compute moat", "Pricing power"],
        valuation_stance="Reasonable",
        canonical_figures=[CanonicalFigure(fact_id="rev", display="$100")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="x",
                does_not_cover="y",
                relevant_fact_ids=["rev"],
            )
        ],
        charts=[
            ChartSpec(
                id="rev_chart",
                section_id="overview",
                claim="Revenue grew",
                chart_type=ChartType.COLUMN,
                title="Revenue by fiscal year",
                category_labels=["FY2024", "FY2025"],
                series=[ChartSeries(name="Revenue", value_fact_ids=["rev_series"])],
            )
        ],
    )
    state.sections = [
        WrittenSection(
            section_id="overview", title="Overview", body="See {{CITE:rev}} and {{FIG:rev_chart}}."
        )
    ]
    state.resolved = ResolvedReport(
        section_bodies={"overview": "See [^1] and {{FIG:rev_chart}}."},
        footnotes=["EODHD (fundamentals), TTM."],
        figure_labels={"rev_chart": 1},
    )

    with session_mod.SessionLocal() as s:
        SqlStateStore(s).save(state)
        s.commit()

    from fastapi.testclient import TestClient

    with TestClient(app) as fresh_client:
        res = fresh_client.get(f"/api/departments/equity-research/v2.3/runs/{run_id}/payload")
    assert res.status_code == 200
    body = res.json()

    assert body["run_id"] == run_id
    assert body["tickers"] == ["NVDA"]
    assert body["thesis"]["central_argument"] == "NVDA is the AI-infra leader."
    assert body["sections"] == [{"id": "overview", "title": "Overview"}]
    assert body["section_bodies"]["overview"] == "See [^1] and {{FIG:rev_chart}}."
    assert body["footnotes"] == ["EODHD (fundamentals), TTM."]
    assert body["figure_labels"] == {"rev_chart": 1}
    # Charts strip the python enum.
    assert body["charts"][0]["chart_type"] == "column"
    assert body["charts"][0]["series"] == [{"name": "Revenue", "value_fact_ids": ["rev_series"]}]
    # Scalar fact → number; series fact → list[{period, value}]; provenance gone.
    assert body["bundle_facts"]["rev"]["value"] == 100.0
    assert "source" not in body["bundle_facts"]["rev"]
    assert body["bundle_facts"]["rev_series"]["value"] == [
        {"period": "FY2024", "value": 60.9},
        {"period": "FY2025", "value": 88.0},
    ]


def test_payload_404_for_unknown_run(v2_3_client) -> None:
    _, client = v2_3_client
    res = client.get("/api/departments/equity-research/v2.3/runs/missing/payload")
    assert res.status_code == 404


def test_payload_409_for_non_complete_run(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(
        app,
        FakeClarifierClient(
            result=ClarifyNeedsInput(
                questions=[ClarifyQuestion(id="h", question="?", why_blocking="w", default="d")]
            )
        ),
    )
    r = client.post(
        "/api/departments/equity-research/v2.3/runs",
        json=_payload("p", "NVDA"),
    )
    run_id = r.json()["run_id"]
    res = client.get(f"/api/departments/equity-research/v2.3/runs/{run_id}/payload")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "run_not_complete"


def test_docx_download_409_for_non_complete_run(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(
        app,
        FakeClarifierClient(
            result=ClarifyNeedsInput(
                questions=[ClarifyQuestion(id="h", question="?", why_blocking="w", default="d")]
            )
        ),
    )
    r = client.post(
        "/api/departments/equity-research/v2.3/runs",
        json=_payload("p", "NVDA"),
    )
    run_id = r.json()["run_id"]
    docx = client.get(f"/api/departments/equity-research/v2.3/runs/{run_id}/docx")
    assert docx.status_code == 409
    assert docx.json()["detail"]["code"] == "run_not_complete"


def test_docx_download_404_for_unknown_run(v2_3_client) -> None:
    _, client = v2_3_client
    res = client.get("/api/departments/equity-research/v2.3/runs/missing/docx")
    assert res.status_code == 404
