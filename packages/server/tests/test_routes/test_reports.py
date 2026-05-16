"""GET /reports/{id} and POST /reports/{id}/export/pdf."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from openlia.reports.schema import Cover, Metric, PageFurniture, ReportSchema, Section, TextBlock
from openlia_server.db.models.content import RepoItem, Report
from openlia_server.services.reports import create_report, tombstone_report
from sqlalchemy.orm import Session


def _seed_report(db_session: Session, user_id: str) -> str:
    schema = ReportSchema(
        schema_version="2.0",
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


def test_export_pdf_via_get_for_download_links(
    personal_client: TestClient, db_session: Session
) -> None:
    """The download anchor (`<a href download>`) issues a GET, so the PDF
    export must be reachable via GET as well as POST."""
    rid = _seed_report(db_session, "local")
    db_session.commit()
    r = personal_client.get(f"/reports/{rid}/export/pdf")
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


# ---------------------------------------------------------------------------
# Retention / tombstone behavior
# ---------------------------------------------------------------------------


def test_list_default_filters_tombstoned_rows(
    personal_client: TestClient, db_session: Session
) -> None:
    alive_id = _seed_report(db_session, "local")
    expired_id = _seed_report(db_session, "local")
    db_session.commit()
    tombstone_report(db_session, report_id=expired_id)
    db_session.commit()

    r = personal_client.get("/reports?department=equity_research")
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert alive_id in ids
    assert expired_id not in ids


def test_list_include_expired_returns_tombstones(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    tombstone_report(db_session, report_id=rid)
    db_session.commit()

    r = personal_client.get(
        "/reports?department=equity_research&include_expired=true"
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == rid
    assert items[0]["expired_at"] is not None


def test_detail_returns_tombstone_payload(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    tombstone_report(db_session, report_id=rid)
    db_session.commit()

    r = personal_client.get(f"/reports/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["schema"] is None
    assert body["expired_at"] is not None
    assert body["title"] == "Apple Inc."
    assert body["department"] == "equity_research"


def test_detail_alive_report_includes_expired_at_null(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()

    r = personal_client.get(f"/reports/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["schema"]["cover"]["ticker"] == "AAPL"
    assert body["expired_at"] is None


def test_export_pdf_returns_410_on_tombstone(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    tombstone_report(db_session, report_id=rid)
    db_session.commit()

    r = personal_client.post(f"/reports/{rid}/export/pdf")
    assert r.status_code == 410
    assert r.json()["detail"]["code"] == "report_expired"


def test_export_docx_returns_410_on_tombstone(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    tombstone_report(db_session, report_id=rid)
    db_session.commit()

    r = personal_client.get(f"/reports/{rid}/docx")
    assert r.status_code == 410


def test_render_returns_410_on_tombstone(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()
    tombstone_report(db_session, report_id=rid)
    db_session.commit()

    r = personal_client.get(f"/reports/{rid}/render")
    assert r.status_code == 410


def test_delete_tombstones_instead_of_dropping_row(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    # Save it to the repo so we can verify the RepoItem is removed by the
    # tombstone op.
    db_session.add(RepoItem(id="ri-test", user_id="local", report_id=rid))
    db_session.commit()

    r = personal_client.delete(f"/reports/{rid}")
    assert r.status_code == 204

    db_session.expire_all()
    row = db_session.get(Report, rid)
    assert row is not None  # row preserved as tombstone anchor
    assert row.expired_at is not None
    assert row.content_markdown == ""
    assert row.content_structured == {}
    assert (
        db_session.query(RepoItem).filter(RepoItem.report_id == rid).count() == 0
    )


def test_delete_is_idempotent_via_route(
    personal_client: TestClient, db_session: Session
) -> None:
    rid = _seed_report(db_session, "local")
    db_session.commit()

    r1 = personal_client.delete(f"/reports/{rid}")
    r2 = personal_client.delete(f"/reports/{rid}")
    assert r1.status_code == 204
    assert r2.status_code == 204  # tombstone_report returns False but route still 204s


def test_delete_404_for_other_users_report(
    personal_client: TestClient, db_session: Session
) -> None:
    """Cross-user delete is hidden as a 404 (ownership check before tombstone)."""
    from openlia_server.db.models.auth import User

    other = User(
        id="other",
        email="other@x",
        display_name="Other",
        is_admin=False,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(other)
    db_session.commit()
    rid = _seed_report(db_session, "other")
    db_session.commit()

    r = personal_client.delete(f"/reports/{rid}")
    assert r.status_code == 404
    # Row untouched.
    db_session.expire_all()
    assert db_session.get(Report, rid).expired_at is None
