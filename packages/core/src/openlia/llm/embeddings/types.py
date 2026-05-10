"""Embedding provider Protocol."""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Tiny contract every embedding backend implements.

    ``dim`` is the dimensionality of the vectors produced. Slice 10's
    storage layer sizes BLOB columns based on it and tags rows with the
    model name so a model swap can trigger re-embedding rather than
    silently mixing dimensions.
    """

    @property
    def dim(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...
