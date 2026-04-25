"""GET /reports/{id} and POST /reports/{id}/export/pdf."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from openlia.reports.schema import Cover, Metric, PageFurniture, ReportSchema, Section, TextBlock
from openlia_server.services.reports import create_report
from sqlalchemy.orm import Session


def _seed_report(db_session: Session, user_id: str) -> str:
    schema = ReportSchema(
        schema_version="1.0",
        department="equity_research",
        generated_at=datetime(2026, 4, 11, tzinfo=UTC),
        page_furniture=PageFurniture(
            header={"left": "OpenLIA", "right": "ER"},
            footer={"left": "Gen", "center": "Page {page}", "right": "Internal"},
            disclaimer="Not advice.",
        ),
        cover=Cover(
            title="Apple Inc.",
            subtitle="Q1 2026",
            ticker="AAPL",
            tagline="Strong.",
            key_metrics=[Metric(label="P", value="$198")],
        ),
        sections=[
            Section(
                id="fin",
                title="Financial Overview",
                blocks=[TextBlock(type="text", content="Apple reported...")],
            )
        ],
    )
    return create_report(
        db_session,
        user_id=user_id,
        department="equity_research",
        mode="initiation",
        schema=schema,
    )


def test_get_report_returns_schema(personal_client: TestClient, db_session: Session) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    r = personal_client.get(f"/reports/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["schema"]["cover"]["ticker"] == "AAPL"


def test_get_report_404_when_missing(personal_client: TestClient) -> None:
    r = personal_client.get("/reports/does-not-exist")
    assert r.status_code == 404


def test_get_report_requires_auth(company_client_anon: TestClient) -> None:
    r = company_client_anon.get("/reports/anything")
    assert r.status_code == 401


def test_export_pdf_streams_pdf_bytes(personal_client: TestClient, db_session: Session) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    r = personal_client.post(f"/reports/{rid}/export/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:4] == b"%PDF"


def test_export_docx_streams_docx_bytes(personal_client: TestClient, db_session: Session) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    r = personal_client.get(f"/reports/{rid}/docx")
    assert r.status_code == 200
    assert (
        r.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "attachment" in r.headers["content-disposition"]
    # .docx files are zip archives — verify the PK\x03\x04 magic header.
    assert r.content[:4] == b"PK\x03\x04"


def test_export_docx_404_when_missing(personal_client: TestClient) -> None:
    r = personal_client.get("/reports/does-not-exist/docx")
    assert r.status_code == 404


def test_export_docx_requires_auth(company_client_anon: TestClient) -> None:
    r = company_client_anon.get("/reports/anything/docx")
    assert r.status_code == 401


def test_render_route_returns_spa_shell_when_bundle_present(
    personal_client: TestClient, db_session: Session, monkeypatch
) -> None:
    """When `frontend/dist/index.html` resolves, the render route returns a
    minimal HTML shell that injects `window.__REPORT_SCHEMA__` and loads
    the Vite bundle. This is the SPA-driven preview path (Option A)."""
    import os

    # Point the resolver at a synthetic dist that always resolves.
    import tempfile
    import textwrap

    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "assets"), exist_ok=True)
        with open(os.path.join(tmp, "index.html"), "w", encoding="utf-8") as f:
            f.write(
                textwrap.dedent(
                    """
                    <!doctype html><html><head>
                      <script type="module" crossorigin src="/assets/index-X.js"></script>
                      <link rel="stylesheet" crossorigin href="/assets/index-Y.css">
                    </head><body><div id="root"></div></body></html>
                    """
                ).strip()
            )
        monkeypatch.setenv("OPENLIA_FRONTEND_DIST", tmp)
        rid = _seed_report(db_session, "local")
        db_session.commit()
        r = personal_client.get(f"/reports/{rid}/render")
        assert r.status_code == 200
        body = r.text
        assert "window.__REPORT_SCHEMA__" in body
        assert "/assets/index-X.js" in body
        assert "/assets/index-Y.css" in body
        # Static fallback markers should NOT be present.
        assert "report-print" not in body  # full SPA shell, not fallback


def test_render_route_falls_back_to_static_html_without_bundle(
    personal_client: TestClient, db_session: Session, monkeypatch
) -> None:
    """When no bundle is reachable, the route returns the static HTML
    fallback so Playwright/users still see chart titles and content."""
    monkeypatch.setenv("OPENLIA_FRONTEND_DIST", "/nonexistent/path/that/does/not/exist")
    rid = _seed_report(db_session, "local")
    db_session.commit()
    r = personal_client.get(f"/reports/{rid}/render")
    assert r.status_code == 200
    body = r.text
    assert "Apple Inc." in body
    assert "Financial Overview" in body
    # Fallback shell uses inline <style>, not a hashed bundle.
    assert "/assets/index-" not in body
