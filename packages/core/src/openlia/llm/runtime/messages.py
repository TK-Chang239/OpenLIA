from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

_ALLOWED_LENGTHS = ("brief", "standard", "long")


@dataclass(frozen=True)
class Attachment:
    """A user-attached file as it sits server-side after upload.

    The runtime materializer reads ``storage_path`` to load bytes for image
    / native-PDF blocks and uses ``extracted_text`` (when present) for the
    text-extraction path. ``id`` mirrors the ``chat_attachments`` row id.
    """

    id: str
    filename: str
    mime_type: str
    storage_path: str
    size_bytes: int = 0
    extracted_text: str | None = None


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    attachments: list[Attachment] = field(default_factory=list)


# ─── Provider-neutral content blocks ────────────────────────────────────────


@dataclass(frozen=True)
class ContentBlock:
    """Marker base for materialized content blocks. Adapters dispatch on
    the concrete subclass (TextBlock / ImageBlock / DocumentBlock)."""


@dataclass(frozen=True)
class TextBlock(ContentBlock):
    text: str
    source_filename: str | None = None


@dataclass(frozen=True)
class ImageBlock(ContentBlock):
    data: bytes
    mime_type: str
    source_filename: str | None = None


@dataclass(frozen=True)
class DocumentBlock(ContentBlock):
    """Native document content (e.g. PDF) for providers with first-class
    document input. Non-native providers must extract to TextBlock at the
    materializer layer; adapters that receive a DocumentBlock anyway are
    expected to either pass it through or fall back to a text placeholder."""

    data: bytes
    mime_type: str
    source_filename: str | None = None


@dataclass(frozen=True)
class ReportRequest:
    mode: str
    user_input: str
    enabled_sections: list[str] = field(default_factory=list)
    custom_sections: list[dict[str, Any]] = field(default_factory=list)
    length: str = "standard"
    section_topics: Mapping[str, list[dict[str, Any]]] | None = None
    reference_portfolio: list[dict[str, Any]] | None = None
    user_template_text: str | None = None
    user_template_name: str | None = None
    # Per-report override for the web-search budget. ``None`` means the
    # runner resolves from the framework default (and falls back to the
    # global 8 if the framework didn't declare one). See
    # ``_resolve_search_budget`` in ``llm.runtime.report``.
    web_search_budget_override: int | None = None
    # Phase 6: when True, uncited concrete claims become validation
    # errors and trigger the strict-validation retry loop. Default False
    # keeps the warn-only path.
    citations_strict: bool = False

    def __post_init__(self) -> None:
        if self.length not in _ALLOWED_LENGTHS:
            raise ValueError(f"length must be one of {_ALLOWED_LENGTHS}, got {self.length!r}")


@dataclass(frozen=True)
class BatchItem:
    id: str
    context: dict[str, Any]


@dataclass(frozen=True)
class BatchResult:
    id: str
    ok: bool
    data: dict[str, Any] | None
    error: str | None
