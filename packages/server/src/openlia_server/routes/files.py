"""File download routes — request glue only; resolution lives in services.files."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import files as svc

_ERROR_MAP: dict[type[Exception], tuple[int, str]] = {
    svc.ReportNotFound: (404, "report_not_found"),
    svc.AttachmentNotFound: (404, "attachment_not_found"),
    svc.MessageNotFound: (404, "message_not_found"),
    svc.Forbidden: (403, "forbidden"),
    svc.FileGone: (410, "file_gone"),
    svc.UnsupportedFormat: (415, "unsupported_format"),
}


def _raise_http(exc: Exception) -> None:
    status, code = _ERROR_MAP[type(exc)]
    raise HTTPException(status_code=status, detail={"code": code, "message": str(exc)})


def build_files_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="", tags=["files"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/reports/{report_id}/download")
    def download_report(
        report_id: str,
        format: str | None = None,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        try:
            blob = svc.resolve_report_download(
                db, user_id=user.id, report_id=report_id, format=format
            )
        except tuple(_ERROR_MAP) as exc:
            _raise_http(exc)
        return Response(
            content=blob.content,
            media_type=blob.media_type,
            headers={"Content-Disposition": f'attachment; filename="{blob.filename}"'},
        )

    @router.get("/chat/attachments/{attachment_id}/download")
    def download_attachment(
        attachment_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> FileResponse:
        try:
            stored = svc.resolve_attachment_download(
                db, user_id=user.id, attachment_id=attachment_id
            )
        except tuple(_ERROR_MAP) as exc:
            _raise_http(exc)
        return FileResponse(
            stored.path,
            media_type=stored.media_type,
            headers={"Content-Disposition": f'attachment; filename="{stored.filename}"'},
        )

    return router
