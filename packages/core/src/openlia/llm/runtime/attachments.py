"""Runtime materializer: ``Attachment`` → provider-neutral content blocks.

Owns the (mime x capabilities) → block-type routing table. For text-extractable
formats (PDF on non-pdf_native providers, all Office docs), the runtime relies
on extracted text supplied by the caller via ``extracted_text_cache``; the
parsing itself happens server-side at upload time so the runtime stays
deployment-agnostic and avoids re-parsing on every send.

For image and native-PDF paths, raw bytes are read from ``Attachment.storage_path``
on demand. The path is opaque to this module — it's a string handed in by the
server's storage backend (see ``openlia_server.services.attachment_storage``).

See ``planning/specs/systems/composer-attachments-design.md``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from openlia.llm.runtime.messages import (
    Attachment,
    ContentBlock,
    DocumentBlock,
    ImageBlock,
    TextBlock,
)
from openlia.llm.types import Capabilities


class AttachmentNotSupportedError(Exception):
    """Raised when an attachment has no viable materialization path for the
    selected model — currently only the (image + non-vision-model) and the
    (mime not in allowlist) cases. The error message includes both the
    filename and a hint at what to do (switch model, remove file)."""


@dataclass(frozen=True)
class MaterializationResult:
    blocks: list[ContentBlock]
    warnings: list[str] = field(default_factory=list)


# ─── MIME → category routing ─────────────────────────────────────────────────

_TEXT_MIMES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/csv",
        "text/x-python",
        "text/x-c",
        "text/x-c++",
        "text/x-java",
        "application/json",
    }
)
_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
_PDF_MIME = "application/pdf"
_OFFICE_MIMES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
    }
)

_Category = Literal["text", "image", "pdf", "office", "unsupported"]


def _categorize(mime: str) -> _Category:
    if mime in _TEXT_MIMES:
        return "text"
    if mime in _IMAGE_MIMES:
        return "image"
    if mime == _PDF_MIME:
        return "pdf"
    if mime in _OFFICE_MIMES:
        return "office"
    return "unsupported"


# ─── Token budgeting ─────────────────────────────────────────────────────────

# Heuristic chars-per-token. Used both for budget checks and for truncating
# text content. Approximate; this is a fit/no-fit decision, not billing.
_CHARS_PER_TOKEN = 4

# No single attachment may extract to more than this many tokens, even if the
# model's context window allows it. Protects the request path from pathological
# documents.
_PER_ATTACHMENT_HARD_CEILING_TOKENS = 500_000


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _truncate_to_tokens(text: str, max_tokens: int, *, source_filename: str) -> str:
    """Cut ``text`` to fit within ``max_tokens`` (approx) and prepend a banner
    explaining the truncation. The banner is itself counted against budget."""
    banner = (
        f"[Truncated: {source_filename!r} was clipped to fit the model's context. "
        "Some content omitted.]\n\n"
    )
    banner_tokens = _estimate_tokens(banner)
    body_token_budget = max(1, max_tokens - banner_tokens)
    body_chars = body_token_budget * _CHARS_PER_TOKEN
    return banner + text[:body_chars]


# ─── Public surface ──────────────────────────────────────────────────────────


def materialize_for_model(
    attachments: Iterable[Attachment],
    *,
    capabilities: Capabilities,
    available_token_budget: int = 1_000_000_000,
    extracted_text_cache: Mapping[str, str] | None = None,
) -> MaterializationResult:
    """Render ``attachments`` into provider-neutral content blocks.

    ``extracted_text_cache`` maps ``Attachment.id`` to pre-extracted text
    (server reads ``chat_attachments.extracted_text`` and supplies it).

    Token-budget enforcement: text blocks (decoded text files + extracted
    PDF/Office text) collectively must fit ``available_token_budget``.
    Each individual text block is also capped at ``_PER_ATTACHMENT_HARD_CEILING_TOKENS``.
    Truncation prepends a banner and emits a per-attachment warning.
    """
    cache = extracted_text_cache or {}
    pending: list[_PendingBlock] = []
    warnings: list[str] = []

    for att in attachments:
        category = _categorize(att.mime_type)

        if category == "unsupported":
            raise AttachmentNotSupportedError(
                f"{att.filename!r} has unsupported mime type {att.mime_type!r}. "
                "Remove the file or convert it to a supported format."
            )

        if category == "text":
            pending.append(_PendingBlock(kind="text", attachment=att, text=_read_text(att)))
            continue

        if category == "image":
            if not capabilities.vision:
                raise AttachmentNotSupportedError(
                    f"{att.filename!r} is an image but the selected model has no vision "
                    "capability. Switch to a vision-capable model or remove the file."
                )
            pending.append(_PendingBlock(kind="image", attachment=att))
            continue

        if category == "pdf":
            if capabilities.pdf_native:
                pending.append(_PendingBlock(kind="document", attachment=att))
                continue
            extracted = att.extracted_text or cache.get(att.id)
            if extracted is None:
                warnings.append(
                    f"{att.filename!r} skipped — selected model has no native PDF "
                    "input and no extracted text was available."
                )
                continue
            pending.append(_PendingBlock(kind="text", attachment=att, text=extracted))
            continue

        if category == "office":
            extracted = att.extracted_text or cache.get(att.id)
            if extracted is None:
                warnings.append(
                    f"{att.filename!r} skipped — Office documents require server-side "
                    "extraction and no extracted text was available."
                )
                continue
            pending.append(_PendingBlock(kind="text", attachment=att, text=extracted))
            continue

    blocks = _apply_truncation(pending, available_token_budget, warnings)
    return MaterializationResult(blocks=blocks, warnings=warnings)


@dataclass(frozen=True)
class _PendingBlock:
    kind: Literal["text", "image", "document"]
    attachment: Attachment
    text: str | None = None  # populated when kind == "text"


def _apply_truncation(
    pending: list[_PendingBlock],
    available_token_budget: int,
    warnings: list[str],
) -> list[ContentBlock]:
    text_indices = [i for i, p in enumerate(pending) if p.kind == "text"]
    text_token_counts = [_estimate_tokens(pending[i].text or "") for i in text_indices]

    # Per-attachment ceiling: clip any oversized text so the budget split
    # below operates on already-bounded sizes.
    per_attachment_caps: dict[int, int] = {}
    for idx, count in zip(text_indices, text_token_counts, strict=True):
        per_attachment_caps[idx] = min(count, _PER_ATTACHMENT_HARD_CEILING_TOKENS)

    capped_total = sum(per_attachment_caps.values())

    needs_global_truncation = capped_total > available_token_budget

    blocks: list[ContentBlock] = []
    for idx, p in enumerate(pending):
        if p.kind == "image":
            blocks.append(
                ImageBlock(
                    data=_read_bytes(p.attachment),
                    mime_type=p.attachment.mime_type,
                    source_filename=p.attachment.filename,
                )
            )
            continue
        if p.kind == "document":
            blocks.append(
                DocumentBlock(
                    data=_read_bytes(p.attachment),
                    mime_type=p.attachment.mime_type,
                    source_filename=p.attachment.filename,
                )
            )
            continue

        # Text block: apply per-file cap and (if needed) proportional global split.
        original_tokens = _estimate_tokens(p.text or "")
        budget_for_this = per_attachment_caps[idx]

        if needs_global_truncation:
            # Proportional split based on (already-capped) sizes.
            this_share = per_attachment_caps[idx] / capped_total if capped_total else 0
            budget_for_this = max(1, int(available_token_budget * this_share))

        if original_tokens > budget_for_this:
            truncated_text = _truncate_to_tokens(
                p.text or "", budget_for_this, source_filename=p.attachment.filename
            )
            warnings.append(
                f"{p.attachment.filename!r} was truncated from ~{original_tokens} "
                f"tokens to fit the model's context (~{budget_for_this} tokens)."
            )
            blocks.append(TextBlock(text=truncated_text, source_filename=p.attachment.filename))
        else:
            blocks.append(TextBlock(text=p.text or "", source_filename=p.attachment.filename))

    return blocks


# ─── IO helpers ──────────────────────────────────────────────────────────────


def _read_bytes(att: Attachment) -> bytes:
    return Path(att.storage_path).read_bytes()


def _read_text(att: Attachment) -> str:
    return _read_bytes(att).decode("utf-8", errors="replace")
