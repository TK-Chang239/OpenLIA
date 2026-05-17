"""Normalize a chat-binding subject (typically a ticker) for equality
comparison. v1: lowercase + whitespace-trim only. Exchange-suffix
smoothing is deferred."""

from __future__ import annotations


def normalize_subject(raw: str | None) -> str:
    if not raw:
        return ""
    return raw.strip().lower()
