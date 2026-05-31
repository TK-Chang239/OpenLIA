"""v3 template service — resolver + upload + listing + delete.

The single source of truth for v3 templates is the
``report_v3_templates`` table. The runtime resolves a ``template_id``
to a ``TemplateSpec`` through ``resolve_template``; the upload path
parses + compiles + persists via ``create_template_from_markdown``.

Built-ins are pre-seeded by the
``2026-05-27_2300_report_v3_templates`` migration and read through
the same row-lookup path as user uploads, so the engine has one
template-loading code path.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec
from openlia.llm.runtime.report_v3 import TemplateSpec
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.report_v3 import ReportV3Template
from openlia_server.services.template_parser import ParsedTemplate, parse_template

_SLUG_SAFE_RE = re.compile(r"[^a-z0-9_]")


class TemplateNotFoundError(LookupError):
    """The requested template_id does not exist (or is owned by another user)."""


class TemplateValidationError(ValueError):
    """The uploaded markdown could not be parsed into a valid TemplateSpec."""


@dataclass(frozen=True)
class TemplateSummary:
    """Listing row — no spec body, no source artifacts."""

    id: str
    name: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


def resolve_template(
    *,
    db: DBSession,
    user_id: str,
    template_id: str,
) -> TemplateSpec:
    """Load a template by id. Built-ins are user-id-agnostic; user
    uploads are owner-scoped (other users' uploads are invisible).

    Raises ``TemplateNotFoundError`` for unknown ids, owner mismatches,
    and soft-deleted rows.
    """
    row = db.get(ReportV3Template, template_id)
    if row is None or row.deleted_at is not None:
        raise TemplateNotFoundError(f"v3 template {template_id!r} not found")
    if not row.is_builtin and row.user_id != user_id:
        raise TemplateNotFoundError(f"v3 template {template_id!r} not found")
    return TemplateSpec.model_validate(row.template_spec_json)


def list_templates(*, db: DBSession, user_id: str) -> list[TemplateSummary]:
    """All built-ins + this user's non-deleted uploads, name-sorted."""
    stmt = select(ReportV3Template).where(ReportV3Template.deleted_at.is_(None))
    rows = db.execute(stmt).scalars().all()
    visible = [row for row in rows if row.is_builtin or row.user_id == user_id]
    visible.sort(key=lambda r: (not r.is_builtin, r.name.lower()))
    return [
        TemplateSummary(
            id=r.id,
            name=r.name,
            is_builtin=r.is_builtin,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in visible
    ]


def _compile_v3_template_spec(
    parsed: ParsedTemplate,
    *,
    template_id: str,
    default_name: str,
) -> TemplateSpec:
    """Turn a ``ParsedTemplate`` into a v3 ``TemplateSpec``.

    v3's TemplateSpec is structurally smaller than v2.2's — no
    body/synthesis tier split, no validators, no chart hooks. Fields
    we read from frontmatter (all optional, all keys lowercase):

      Document-level (in the leading ``<!-- openlia ... -->`` block):
        - ``name`` — overrides ``default_name``
        - ``shape_description`` — one-paragraph blurb for the LLM
        - ``ticker_anchored`` — bool (default True)
        - ``default_length`` — "concise" / "normal" / "elaborative"

      Per-section frontmatter:
        - ``intent`` — overrides the section's brief
        - ``methodology_hints`` — list of strings

    Anything unrecognized is silently ignored — keeps user docs
    forward-compatible as the schema grows.
    """
    doc_fm = parsed.document_frontmatter or {}
    name = str(doc_fm.get("name") or default_name).strip() or default_name
    shape_description = str(
        doc_fm.get("shape_description") or f"{name} — user-uploaded equity research template."
    ).strip()
    ticker_anchored = bool(doc_fm.get("ticker_anchored", True))
    default_length_raw = doc_fm.get("default_length")
    default_length = (
        str(default_length_raw)
        if default_length_raw in ("concise", "normal", "elaborative")
        else None
    )

    sections: list[SectionSpec] = []
    for parsed_section in parsed.sections:
        section_fm = parsed_section.frontmatter or {}
        # SectionSpec.id pattern is ``[a-z0-9_]+``; the parser slugifies
        # with the same charset, but defensively coerce any drift.
        section_id = _SLUG_SAFE_RE.sub("_", parsed_section.id.lower()) or "section"
        intent = str(
            section_fm.get("intent") or parsed_section.brief or parsed_section.title
        ).strip()
        hints_raw = section_fm.get("methodology_hints") or []
        hints = [str(h) for h in hints_raw if isinstance(h, str)]
        sections.append(
            SectionSpec(
                id=section_id,
                title=parsed_section.title,
                intent=intent or parsed_section.title,
                methodology_hints=hints,
            )
        )

    return TemplateSpec(
        template_id=template_id,
        name=name,
        shape_description=shape_description,
        ticker_anchored=ticker_anchored,
        default_length=default_length,
        sections=sections,
    )


def create_template_from_markdown(
    *,
    db: DBSession,
    user_id: str,
    name: str,
    markdown: str,
    source_doc_blob: bytes | None = None,
    source_doc_mime: str | None = None,
) -> ReportV3Template:
    """Parse + compile + persist a markdown template.

    The parser splits H1/H2 headings into sections; the compiler
    produces a v3 TemplateSpec. Empty section lists fail validation.
    Returns the persisted row (flushed but not committed — the caller
    commits as part of the request).
    """
    parsed = parse_template(markdown)
    if not parsed.sections:
        raise TemplateValidationError(
            "Template has no sections — use Markdown H1/H2 headings "
            "(``#`` or ``##``) for section titles. Docx uploads must "
            "use Word's Heading 1 / Heading 2 styles."
        )
    # UUID hex (32 chars, no hyphens) satisfies the TemplateSpec.template_id
    # pattern ``^[a-z0-9_]+$``. Plain ``str(uuid.uuid4())`` would fail
    # Pydantic validation because of the hyphens.
    template_id = uuid.uuid4().hex
    try:
        spec = _compile_v3_template_spec(
            parsed,
            template_id=template_id,
            default_name=name,
        )
    except Exception as exc:
        raise TemplateValidationError(
            f"Template did not compile to a valid TemplateSpec: {exc}"
        ) from exc

    now = datetime.now(UTC)
    row = ReportV3Template(
        id=template_id,
        user_id=user_id,
        name=spec.name,
        is_builtin=False,
        template_spec_json=json.loads(spec.model_dump_json()),
        source_markdown=markdown,
        source_doc_blob=source_doc_blob,
        source_doc_mime=source_doc_mime,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(row)
    db.flush()
    return row


def soft_delete_template(
    *,
    db: DBSession,
    user_id: str,
    template_id: str,
) -> None:
    """Owner-scoped soft delete. Built-ins cannot be deleted.

    Raises ``TemplateNotFoundError`` for unknown ids, built-ins,
    owner mismatches, or already-deleted rows.
    """
    row = db.get(ReportV3Template, template_id)
    if row is None or row.deleted_at is not None:
        raise TemplateNotFoundError(f"v3 template {template_id!r} not found")
    if row.is_builtin:
        raise TemplateNotFoundError(
            f"v3 template {template_id!r} is a built-in and cannot be deleted"
        )
    if row.user_id != user_id:
        raise TemplateNotFoundError(f"v3 template {template_id!r} not found")
    row.deleted_at = datetime.now(UTC)
    db.flush()
