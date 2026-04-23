"""GET /reports/{id} and POST /reports/{id}/export/pdf."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.report_export import export_report_pdf
from openlia_server.services.report_store import (
    ReportNotFoundError,
    get_report,
)


def _html_shell(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head>"
        "<meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<style>body{font:14px/1.5 Inter,system-ui;margin:0;padding:48px;color:#1a1a1a}"
        "h1{font-size:28px;font-weight:700;margin:0 0 8px}"
        "h2{font-size:22px;font-weight:600;margin:32px 0 12px}"
        "p{margin:0 0 12px}</style>"
        "</head><body>" + body + "</body></html>"
    )


def _schema_to_basic_html(schema: dict) -> str:
    cover = schema.get("cover", {})
    body = [
        f"<h1>{cover.get('title', 'Report')}</h1>",
        f"<p><em>{cover.get('subtitle', '')}</em></p>",
        f"<p>{cover.get('tagline', '')}</p>",
    ]
    for section in schema.get("sections", []):
        body.append(f"<h2>{section.get('title', '')}</h2>")
        for block in section.get("blocks", []):
            if block.get("type") == "text":
                body.append(f"<p>{block.get('content', '')}</p>")
            else:
                body.append(f"<p><em>[{block.get('type', 'block')}]</em></p>")
    return "".join(body)


def build_reports_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/reports", tags=["reports"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

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
        payload = schema.model_dump(mode="json")
        html = _html_shell(
            title=payload["cover"].get("title", "Report"),
            body=_schema_to_basic_html(payload),
        )
        launcher = request.app.state.browser_launcher
        pdf = await export_report_pdf(launcher, html)
        filename = f"report-{report_id}.pdf"
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"content-disposition": f'attachment; filename="{filename}"'},
        )

    return router
