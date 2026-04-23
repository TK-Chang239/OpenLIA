"""File download routes for reports and chat attachments."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatAttachment, ChatMessage, ChatSession, Report
from openlia_server.middleware.auth import build_require_auth


def _safe_filename(name: str) -> str:
    return name.replace('"', "").replace("\r", "").replace("\n", "")


def build_files_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="", tags=["files"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/reports/{report_id}/download")
    def download_report(
        report_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        row = db.get(Report, report_id)
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "report_not_found"})
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail={"code": "forbidden"})
        safe_title = _safe_filename(row.title or "report")
        filename = f"{safe_title}.md"
        return Response(
            content=row.content_markdown.encode(),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/chat/attachments/{attachment_id}/download")
    def download_attachment(
        attachment_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> FileResponse:
        row = db.get(ChatAttachment, attachment_id)
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "attachment_not_found"})
        # Auth: attachment → message → session → user
        msg = db.get(ChatMessage, row.message_id)
        if msg is None:
            raise HTTPException(status_code=404, detail={"code": "message_not_found"})
        sess = db.get(ChatSession, msg.session_id)
        if sess is None or sess.user_id != user.id:
            raise HTTPException(status_code=403, detail={"code": "forbidden"})
        path = Path(row.storage_path)
        if not path.is_file():
            raise HTTPException(status_code=410, detail={"code": "file_gone"})
        return FileResponse(
            path,
            media_type=row.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{_safe_filename(row.filename)}"'
            },
        )

    return router
