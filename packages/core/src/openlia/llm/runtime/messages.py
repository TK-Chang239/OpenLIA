from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

_ALLOWED_LENGTHS = ("brief", "standard", "long")


@dataclass(frozen=True)
class Attachment:
    """Reserved for vision inputs. v1 runners accept but never forward them."""

    kind: Literal["image", "file"]
    url: str
    mime_type: str


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    attachments: list[Attachment] = field(default_factory=list)


@dataclass(frozen=True)
class ReportRequest:
    mode: str
    user_input: str
    enabled_sections: list[str] = field(default_factory=list)
    custom_sections: list[dict[str, Any]] = field(default_factory=list)
    length: str = "standard"
    section_topics: Mapping[str, list[dict[str, Any]]] | None = None
    reference_portfolio: list[dict[str, Any]] | None = None

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
