"""MB instruction-profile service — resolver + upload + listing + delete.

An instruction profile is free-form analyst methodology (principles,
how-to-reason, tone, emphasis) the user uploads once and reuses across
reports. Unlike a template it needs no structural parsing: the upload
path extracts plain text from any supported document and stores it in
``body_text``, which the runner injects verbatim into the system prompt.

Forked from ``eu_v2_instructions_service`` with ``ReportEuInstructions``
swapped for ``ReportMbInstructions`` (same owner-scoping, soft-delete,
and listing semantics) so the two artifact types behave identically from
the route layer's point of view.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.report_mb import ReportMbInstructions


class InstructionsNotFoundError(LookupError):
    """The requested instructions_id does not exist (or is owned by another user)."""


class InstructionsValidationError(ValueError):
    """The uploaded document yielded no usable instruction text."""


@dataclass(frozen=True)
class InstructionsSummary:
    """Listing row — no body, no source artifacts."""

    id: str
    name: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


def resolve_instructions(
    *,
    db: DBSession,
    user_id: str,
    instructions_id: str,
) -> str:
    """Load a profile's ``body_text`` by id. Built-ins are
    user-id-agnostic; user uploads are owner-scoped.

    Raises ``InstructionsNotFoundError`` for unknown ids, owner
    mismatches, and soft-deleted rows.
    """
    row = db.get(ReportMbInstructions, instructions_id)
    if row is None or row.deleted_at is not None:
        raise InstructionsNotFoundError(f"mb instructions {instructions_id!r} not found")
    if not row.is_builtin and row.user_id != user_id:
        raise InstructionsNotFoundError(f"mb instructions {instructions_id!r} not found")
    return row.body_text


def list_instructions(*, db: DBSession, user_id: str) -> list[InstructionsSummary]:
    """All built-ins + this user's non-deleted uploads, name-sorted."""
    stmt = select(ReportMbInstructions).where(ReportMbInstructions.deleted_at.is_(None))
    rows = db.execute(stmt).scalars().all()
    visible = [row for row in rows if row.is_builtin or row.user_id == user_id]
    visible.sort(key=lambda r: (not r.is_builtin, r.name.lower()))
    return [
        InstructionsSummary(
            id=r.id,
            name=r.name,
            is_builtin=r.is_builtin,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in visible
    ]


def create_instructions_from_upload(
    *,
    db: DBSession,
    user_id: str,
    name: str,
    body_text: str,
    source_doc_blob: bytes | None = None,
    source_doc_mime: str | None = None,
) -> ReportMbInstructions:
    """Persist an extracted instruction profile.

    ``body_text`` is the server-extracted plain text (caller runs the
    shared ``attachments.extract_text`` first). Empty / whitespace-only
    text fails validation — an instruction profile with no words can't
    guide the model. Returns the persisted row (flushed, not committed —
    the caller commits as part of the request).
    """
    text = (body_text or "").strip()
    if not text:
        raise InstructionsValidationError(
            "No instruction text could be extracted from the upload. "
            "Use a document with selectable text (not a scanned image)."
        )
    now = datetime.now(UTC)
    row = ReportMbInstructions(
        id=uuid.uuid4().hex,
        user_id=user_id,
        name=name.strip() or "Untitled instructions",
        is_builtin=False,
        body_text=text,
        source_doc_blob=source_doc_blob,
        source_doc_mime=source_doc_mime,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(row)
    db.flush()
    return row


def soft_delete_instructions(
    *,
    db: DBSession,
    user_id: str,
    instructions_id: str,
) -> None:
    """Owner-scoped soft delete. Built-ins cannot be deleted.

    Raises ``InstructionsNotFoundError`` for unknown ids, built-ins,
    owner mismatches, or already-deleted rows.
    """
    row = db.get(ReportMbInstructions, instructions_id)
    if row is None or row.deleted_at is not None:
        raise InstructionsNotFoundError(f"mb instructions {instructions_id!r} not found")
    if row.is_builtin:
        raise InstructionsNotFoundError(
            f"mb instructions {instructions_id!r} is a built-in and cannot be deleted"
        )
    if row.user_id != user_id:
        raise InstructionsNotFoundError(f"mb instructions {instructions_id!r} not found")
    row.deleted_at = datetime.now(UTC)
    db.flush()
