"""GET /reports/{id} and POST /reports/{id}/export/pdf."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from openlia.reports.schema import Cover, Metric, PageFurniture, ReportSchema, Section, TextBlock
from openlia_server.services.report_store import create_report


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
