"""User-uploaded report templates (PR 9).

A `report_templates` row stores one user-owned template plus the original
source document. The serialized TemplateSpec lives in `template_spec_json`
for runtime lookup; the original markdown / docx blob lives in
`source_doc_blob` so the review UI can re-parse on demand.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin, UTCDateTime


class ReportTemplate(Base, TimestampMixin):
    __tablename__ = "report_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)

    # Serialized TemplateSpec (Pydantic .model_dump()) — the runtime reads
    # this and reconstructs the spec via TemplateSpec.model_validate.
    template_spec_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Original source markdown (after docx/txt ingest). The review UI can
    # re-parse this if the user edits boundaries; the runtime never reads it.
    source_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Original uploaded blob + mime — kept for traceability and re-ingest.
    source_doc_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_doc_mime: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (Index("ix_report_templates_user_id", "user_id"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ReportTemplate(id={self.id!r}, name={self.name!r})"

    # Convenience: when callers need the actual datetime fields for tests
    # they can read .created_at / .updated_at via TimestampMixin.
    created_at: Mapped[datetime]  # type: ignore[assignment]
    updated_at: Mapped[datetime]  # type: ignore[assignment]
    _ = UTCDateTime  # silence "unused import" lint when SQLAlchemy strips
