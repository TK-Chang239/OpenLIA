"""GET /reports/{id}/export/docx — Phase 4 SPA-driven DOCX path."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.reports.schema import Cover, Metric, PageFurniture, ReportSchema, Section, TextBlock
from openlia_server.services.reports import create_report
from sqlalchemy.orm import Session


def _seed_report(db_session: Session, user_id: str) -> str:
    schema = ReportSchema(
        schema_version="2.0",
        department="equity_research",
        generated_at=datetime(2026, 5, 16, tzinfo=UTC),
        page_furniture=PageFurniture(
            header={"left": "OpenLIA", "right": "ER"},
            footer={"left": "Gen", "center": "Page {page}", "right": "Internal"},
            disclaimer="Not advice.",
        ),
        cover=Cover(
            title="Acme",
            subtitle="Q2 2026",
            ticker="ACME",
            tagline="Strong",
            key_metrics=[Metric(label="P", value="$95")],
        ),
        sections=[
            Section(
                id="thesis",
                title="Thesis",
                blocks=[TextBlock(type="text", content="Hello.")],
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


class _FixedResolver:
    def __init__(self, url: str) -> None:
        self._url = url

    def resolve(self) -> str | None:
        return self._url

    def invalidate(self) -> None:
        return None


class _NoneResolver:
    def resolve(self) -> str | None:
        return None

    def invalidate(self) -> None:
        return None


def test_docx_route_returns_503_when_resolver_returns_none(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    personal_client.app.state.render_base_url_resolver = _NoneResolver()
    r = personal_client.get(f"/reports/{rid}/export/docx")
    assert r.status_code == 503


def test_docx_route_streams_docx_bytes(
    personal_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openlia_server.routes import reports as reports_mod

    async def fake_capture(*args, **kwargs):
        return {}

    monkeypatch.setattr(reports_mod, "capture_chart_pngs", fake_capture)

    rid = _seed_report(db_session, "local")
    db_session.commit()
    personal_client.app.state.render_base_url_resolver = _FixedResolver("http://test")

    r = personal_client.get(f"/reports/{rid}/export/docx")
    assert r.status_code == 200
    assert r.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    cd = r.headers["content-disposition"]
    assert ".docx" in cd
    # docx is a zip archive
    assert r.content[:4] == b"PK\x03\x04"


def test_docx_route_invalidates_resolver_on_render_failure(
    personal_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openlia_server.routes import reports as reports_mod

    async def boom(*args, **kwargs):
        raise RuntimeError("playwright timeout")

    monkeypatch.setattr(reports_mod, "capture_chart_pngs", boom)

    invalidated = {"called": False}

    class _SpyResolver(_FixedResolver):
        def invalidate(self) -> None:
            invalidated["called"] = True

    rid = _seed_report(db_session, "local")
    db_session.commit()
    personal_client.app.state.render_base_url_resolver = _SpyResolver("http://test")

    r = personal_client.get(f"/reports/{rid}/export/docx")
    assert r.status_code == 503
    assert invalidated["called"] is True
