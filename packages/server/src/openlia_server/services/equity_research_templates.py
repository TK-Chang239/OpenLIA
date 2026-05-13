"""Equity Research user-uploaded report template service.

Templates replace the default per-mode report prompt for the Equity Research
department. They are uploaded as Word/PDF/Markdown/text/JSON files; on upload
we extract the text once and persist both the raw bytes and the extracted
text. The LLM consumes the extracted text via a thin scaffold (see
``packages/core/src/openlia/prompts/equity_research.yaml``).

Two ownership scopes:

- ``global``  — admin-published, visible to all users.
- ``user``    — uploaded by a single user, visible only to them.

Each template carries ``compatible_modes`` (subset of the equity_research
report modes). Editing metadata (name, modes) does not change the bytes;
replacing bytes requires a fresh upload (which is a new row).

Delete cascades: any ``ErUserConfig.selected_template_id_by_mode`` entry
that points at the deleted row is reset to ``"default"``.
"""

from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from openlia_server.db.models.departments import ErTemplate, ErUserConfig
from openlia_server.services import attachment_storage

ReportMode = Literal["stock_initiation", "stock_update", "sector_research"]
OwnerScope = Literal["global", "user"]

_VALID_MODES: tuple[ReportMode, ...] = (
    "stock_initiation",
    "stock_update",
    "sector_research",
)

_MIN_EXTRACTED_CHARS = 200

# Accepted formats. JSON is treated as plain text (no structural parsing).
_TEXT_MIMES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "application/json",
    }
)
_PDF_MIME = "application/pdf"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_ALLOWED_MIMES = _TEXT_MIMES | {_PDF_MIME, _DOCX_MIME}

# Extension fallbacks for clients that send octet-stream.
_EXT_TO_MIME = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".pdf": _PDF_MIME,
    ".docx": _DOCX_MIME,
}


@dataclass(frozen=True)
class TemplateDTO:
    id: str
    owner_scope: OwnerScope
    owner_user_id: str | None
    created_by_user_id: str | None
    name: str
    compatible_modes: tuple[ReportMode, ...]
    raw_filename: str
    raw_mime: str
    raw_size_bytes: int
    char_count: int
    estimated_tokens: int
    created_at: str
    updated_at: str


class TemplateValidationError(ValueError):
    """Raised when an upload cannot be accepted (bad mime, parse fail, too short)."""


def _row_to_dto(row: ErTemplate) -> TemplateDTO:
    return TemplateDTO(
        id=row.id,
        owner_scope=row.owner_scope,  # type: ignore[arg-type]
        owner_user_id=row.owner_user_id,
        created_by_user_id=row.created_by_user_id,
        name=row.name,
        compatible_modes=tuple(row.compatible_modes or ()),
        raw_filename=row.raw_filename,
        raw_mime=row.raw_mime,
        raw_size_bytes=row.raw_size_bytes,
        char_count=row.char_count,
        estimated_tokens=row.estimated_tokens,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _normalize_mime(filename: str, mime: str | None) -> str:
    if mime and mime in _ALLOWED_MIMES:
        return mime
    suffix = ""
    idx = filename.rfind(".")
    if idx >= 0:
        suffix = filename[idx:].lower()
    fallback = _EXT_TO_MIME.get(suffix)
    if fallback is not None:
        return fallback
    return mime or "application/octet-stream"


def _validate_modes(modes: list[str]) -> tuple[ReportMode, ...]:
    if not modes:
        raise TemplateValidationError("at least one compatible mode is required")
    seen: list[ReportMode] = []
    for m in modes:
        if m not in _VALID_MODES:
            raise TemplateValidationError(f"unknown mode {m!r}")
        if m not in seen:
            seen.append(m)  # type: ignore[arg-type]
    return tuple(seen)


_CJK_RE = re.compile(r"[　-鿿가-힯぀-ヿ]")


def _estimate_tokens(text: str) -> int:
    """Rough heuristic. ~3 chars/token if heavily CJK, ~4 otherwise."""
    if not text:
        return 0
    cjk_chars = sum(1 for _ in _CJK_RE.finditer(text))
    ratio = len(text) / max(cjk_chars, 1)
    divisor = 3 if cjk_chars and ratio < 4 else 4
    return max(1, len(text) // divisor)


def _extract_text(content: bytes, mime: str) -> str:
    """Reuse the same extractors as the chat-attachments service.

    Raises ``TemplateValidationError`` on any extractor failure so the caller
    can surface a clear upload error.
    """
    try:
        if mime in _TEXT_MIMES:
            return content.decode("utf-8", errors="replace")
        if mime == _PDF_MIME:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            parts: list[str] = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            return "\n\n".join(parts).strip()
        if mime == _DOCX_MIME:
            from docx import Document

            doc = Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        raise TemplateValidationError(f"could not extract text: {e}") from e
    raise TemplateValidationError(f"unsupported mime type {mime!r}")


class EquityResearchTemplateService:
    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    # ─── Reads ──────────────────────────────────────────────────────────

    def list_visible(self, user_id: str) -> list[TemplateDTO]:
        """Return all templates the given user may see in their picker:
        every global template plus their own user-scoped templates.
        """
        rows = (
            self._db.query(ErTemplate)
            .filter(
                (ErTemplate.owner_scope == "global")
                | ((ErTemplate.owner_scope == "user") & (ErTemplate.owner_user_id == user_id))
            )
            .order_by(ErTemplate.owner_scope.desc(), ErTemplate.created_at.asc())
            .all()
        )
        return [_row_to_dto(r) for r in rows]

    def get(self, template_id: str) -> ErTemplate | None:
        return self._db.get(ErTemplate, template_id)

    def get_for_user(self, user_id: str, template_id: str) -> ErTemplate | None:
        row = self.get(template_id)
        if row is None:
            return None
        if row.owner_scope == "global":
            return row
        if row.owner_scope == "user" and row.owner_user_id == user_id:
            return row
        return None

    def read_raw_bytes(self, template_id: str) -> bytes:
        row = self.get(template_id)
        if row is None:
            raise KeyError(template_id)
        return attachment_storage.read(row.storage_path)

    # ─── Mutations ──────────────────────────────────────────────────────

    def upload(
        self,
        *,
        actor_user_id: str,
        owner_scope: OwnerScope,
        content: bytes,
        filename: str,
        mime_type: str | None,
        name: str | None,
        compatible_modes: list[str],
    ) -> TemplateDTO:
        mime = _normalize_mime(filename, mime_type)
        if mime not in _ALLOWED_MIMES:
            raise TemplateValidationError(f"unsupported file type {mime!r}")
        modes = _validate_modes(compatible_modes)

        text = _extract_text(content, mime)
        if len(text) < _MIN_EXTRACTED_CHARS:
            raise TemplateValidationError(
                f"extracted text is too short ({len(text)} chars; "
                f"need at least {_MIN_EXTRACTED_CHARS}). The file may be "
                "scanned, encrypted, or empty."
            )

        storage_path = attachment_storage.save(content, original_filename=filename)
        resolved_name = (name or "").strip() or _default_name_from_filename(filename)
        row = ErTemplate(
            id=str(uuid.uuid4()),
            owner_scope=owner_scope,
            owner_user_id=actor_user_id if owner_scope == "user" else None,
            created_by_user_id=actor_user_id,
            name=resolved_name,
            compatible_modes=list(modes),
            raw_filename=filename,
            raw_mime=mime,
            raw_size_bytes=len(content),
            storage_path=storage_path,
            extracted_text=text,
            char_count=len(text),
            estimated_tokens=_estimate_tokens(text),
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return _row_to_dto(row)

    def update_metadata(
        self,
        *,
        template_id: str,
        name: str | None,
        compatible_modes: list[str] | None,
    ) -> TemplateDTO:
        row = self.get(template_id)
        if row is None:
            raise KeyError(template_id)
        if name is not None:
            stripped = name.strip()
            if not stripped:
                raise TemplateValidationError("name cannot be empty")
            row.name = stripped
        if compatible_modes is not None:
            row.compatible_modes = list(_validate_modes(compatible_modes))
        self._db.commit()
        self._db.refresh(row)
        return _row_to_dto(row)

    def delete(self, template_id: str) -> None:
        row = self.get(template_id)
        if row is None:
            return
        storage_path = row.storage_path
        # Cascade: any user config that selected this template reverts the
        # affected mode(s) to "default".
        configs = (
            self._db.query(ErUserConfig)
            .filter(ErUserConfig.selected_template_id_by_mode.isnot(None))
            .all()
        )
        for cfg in configs:
            selected = dict(cfg.selected_template_id_by_mode or {})
            changed = False
            for mode, sel_id in list(selected.items()):
                if sel_id == template_id:
                    selected[mode] = "default"
                    changed = True
            if changed:
                cfg.selected_template_id_by_mode = selected
        self._db.delete(row)
        self._db.commit()
        attachment_storage.unlink(storage_path)


def _default_name_from_filename(filename: str) -> str:
    base = filename
    idx = base.rfind("/")
    if idx >= 0:
        base = base[idx + 1 :]
    idx = base.rfind(".")
    if idx > 0:
        base = base[:idx]
    return base or "template"
