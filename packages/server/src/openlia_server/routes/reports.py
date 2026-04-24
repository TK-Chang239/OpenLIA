"""Reports API: list/read/delete and PDF export."""

from __future__ import annotations

import html as html_escape
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.report_export import export_report_pdf
from openlia_server.services.report_store import (
    ReportNotFoundError,
    get_report,
)


def _esc(value: Any) -> str:
    return html_escape.escape(str(value))


def _render_block(block: dict) -> str:
    btype = block.get("type", "")
    if btype == "text":
        return f"<p>{_esc(block.get('content', ''))}</p>"
    if btype == "key_finding":
        heading = _esc(block.get("heading", ""))
        body = _esc(block.get("body", ""))
        return f'<div class="key-finding"><strong>{heading}</strong><p>{body}</p></div>'
    if btype == "rating_badge":
        label = _esc(block.get("label", ""))
        value = _esc(block.get("value", ""))
        return f'<p class="rating">{label}: <strong>{value}</strong></p>'
    if btype == "metric_cards":
        cards = block.get("cards", []) or []
        parts = ['<div class="metrics">']
        for c in cards:
            label = _esc(c.get("label", ""))
            value = _esc(c.get("value", ""))
            parts.append(
                f'<div class="metric"><div class="metric-label">{label}</div>'
                f'<div class="metric-value">{value}</div></div>'
            )
        parts.append("</div>")
        return "".join(parts)
    if btype == "table":
        columns = block.get("columns", []) or []
        rows = block.get("rows", []) or []
        thead = "".join(f"<th>{_esc(c)}</th>" for c in columns)
        tbody_rows = []
        for row in rows:
            cells = "".join(f"<td>{_esc(v)}</td>" for v in row)
            tbody_rows.append(f"<tr>{cells}</tr>")
        return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(tbody_rows)}</tbody></table>"
    if btype == "group":
        inner = "".join(_render_block(b) for b in block.get("blocks", []) or [])
        return f'<div class="group">{inner}</div>'
    # Chart and other structured blocks — degrade gracefully with a title and note.
    title = block.get("title") or btype.replace("_", " ").title()
    return f'<p class="placeholder"><em>[{_esc(title)}]</em></p>'


def _schema_to_html(schema: dict) -> str:
    cover = schema.get("cover", {}) or {}
    parts = [
        f"<h1>{_esc(cover.get('title', 'Report'))}</h1>",
    ]
    if cover.get("subtitle"):
        parts.append(f"<p class='subtitle'><em>{_esc(cover['subtitle'])}</em></p>")
    if cover.get("tagline"):
        parts.append(f"<p class='tagline'>{_esc(cover['tagline'])}</p>")
    for section in schema.get("sections", []) or []:
        parts.append(f"<section><h2>{_esc(section.get('title', ''))}</h2>")
        for block in section.get("blocks", []) or []:
            parts.append(_render_block(block))
        parts.append("</section>")
    return "".join(parts)


def _html_shell(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head>"
        "<meta charset='utf-8'>"
        f"<title>{_esc(title)}</title>"
        "<style>"
        "body{font:14px/1.5 Inter,system-ui;margin:0;padding:48px;color:#1a1a1a}"
        "h1{font-size:28px;font-weight:700;margin:0 0 8px}"
        "h2{font-size:22px;font-weight:600;margin:32px 0 12px}"
        "p{margin:0 0 12px}"
        ".subtitle{color:#555}.tagline{color:#777;margin-bottom:16px}"
        ".key-finding{border-left:3px solid #2563eb;padding:8px 12px;"
        "margin:12px 0;background:#f8fafc}"
        ".rating{font-size:16px}"
        ".metrics{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}"
        ".metric{flex:1 1 160px;padding:8px 12px;border:1px solid #e5e7eb;border-radius:6px}"
        ".metric-label{color:#555;font-size:12px}"
        ".metric-value{font-size:18px;font-weight:600}"
        "table{border-collapse:collapse;width:100%;margin:12px 0}"
        "th,td{border:1px solid #e5e7eb;padding:6px 8px;text-align:left}"
        "th{background:#f3f4f6}"
        ".placeholder{color:#777;font-style:italic}"
        "</style>"
        "</head><body>" + body + "</body></html>"
    )


class ReportListItem(BaseModel):
    id: str
    department: str
    report_type: str
    title: str
    created_at: str


class ReportListOut(BaseModel):
    items: list[ReportListItem]


def build_reports_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/reports", tags=["reports"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("", response_model=ReportListOut)
    async def list_reports(
        department: str | None = None,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> ReportListOut:
        stmt = select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc())
        if department is not None:
            stmt = stmt.where(Report.department == department)
        rows = list(session.execute(stmt).scalars())
        return ReportListOut(
            items=[
                ReportListItem(
                    id=r.id,
                    department=r.department,
                    report_type=r.report_type,
                    title=r.title,
                    created_at=r.created_at.isoformat() if r.created_at else "",
                )
                for r in rows
            ]
        )

    @router.get("/{report_id}")
    async def read_report(
        report_id: str,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> dict:
        try:
            schema = get_report(session, report_id=report_id, user_id=user.id)
        except ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc
        return {"schema": schema.model_dump(mode="json")}

    @router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_report(
        report_id: str,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> None:
        row = session.execute(
            select(Report).where(Report.id == report_id, Report.user_id == user.id)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
        session.delete(row)
        session.commit()

    @router.post("/{report_id}/export/pdf")
    async def export_report_pdf_route(
        report_id: str,
        request: Request,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> Response:
        try:
            schema = get_report(session, report_id=report_id, user_id=user.id)
        except ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc
        launcher = getattr(request.app.state, "browser_launcher", None)
        if launcher is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "PDF export unavailable (browser launcher not configured)",
            )
        payload = schema.model_dump(mode="json")
        html = _html_shell(
            title=payload.get("cover", {}).get("title", "Report"),
            body=_schema_to_html(payload),
        )
        pdf = await export_report_pdf(launcher, html)
        filename = f"report-{report_id}.pdf"
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"content-disposition": f'attachment; filename="{filename}"'},
        )

    return router
