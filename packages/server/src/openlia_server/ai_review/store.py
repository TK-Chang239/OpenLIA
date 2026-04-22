"""In-memory store for in-flight AI review tasks."""
from __future__ import annotations

import uuid
from threading import Lock
from typing import Any


class ReviewStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: dict[str, dict[str, Any]] = {}

    def create(self) -> str:
        review_id = str(uuid.uuid4())
        with self._lock:
            self._entries[review_id] = {
                "state": "running",
                "progress": 0,
                "result": None,
                "error": None,
            }
        return review_id

    def update(self, review_id: str, **fields: Any) -> None:
        with self._lock:
            if review_id in self._entries:
                self._entries[review_id].update(fields)

    def get(self, review_id: str) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._entries[review_id]) if review_id in self._entries else None


DEFAULT_STORE = ReviewStore()
