"""Resolve a user-owned report template id to its stored TemplateSpec dict (PR 14).

Owned by the server layer so the runner stays storage-agnostic. The route layer
calls `resolve_user_template_spec` with the authenticated user id and the
incoming `report_template_id`; this returns the validated `template_spec` dict
that the runtime then materializes into a `TemplateSpec`.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from openlia_server.db.models.report_templates import ReportTemplate


def resolve_user_template_spec(
    db: Session,
    *,
    user_id: str,
    template_id: str,
) -> dict[str, Any]:
    """Return the `template_spec` dict for a template owned by `user_id`.

    Raises `HTTPException(404)` if the template does not exist or belongs to
    a different user. Ownership is enforced at the resolver boundary so that
    routes and services that wire reports through the runner cannot leak
    another user's framework configuration.
    """
    row = db.get(ReportTemplate, template_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="report template not found")
    return dict(row.template_spec_json or {})
