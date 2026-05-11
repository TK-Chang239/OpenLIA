"""Deterministic in-memory embedding provider for tests.

Produces vectors whose entries are derived from a stable hash of the
input so equal inputs always embed to equal vectors (cosine similarity
is 1.0). Different inputs produce different vectors. No similarity
guarantees beyond that — tests that care about ranking should write
their own fakes.
"""

from __future__ import annotations

import hashlib
import struct


class FakeEmbeddingProvider:
    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        out: list[float] = []
        i = 0
        while len(out) < self._dim:
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                digest = hashlib.sha256(digest).digest()
                i = 0
                continue
            (val,) = struct.unpack("<I", chunk)
            out.append((val % 10_000) / 10_000.0)
            i += 4
        return out
