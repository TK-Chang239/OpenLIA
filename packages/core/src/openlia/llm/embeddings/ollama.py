"""Ollama embeddings provider (local).

Targets the ``/api/embeddings`` endpoint of a running Ollama daemon.
Default model ``nomic-embed-text`` (768d) is small, fast, and a
reasonable quality floor; ``mxbai-embed-large`` (1024d) is the next
step up. Each call embeds one input — Ollama doesn't batch — so the
provider loops on the caller's behalf.
"""

from __future__ import annotations

import httpx

_DIMS: dict[str, int] = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
}


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
    ) -> None:
        if model not in _DIMS:
            raise ValueError(f"unknown Ollama embedding model: {model!r}")
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def dim(self) -> int:
        return _DIMS[self._model]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        with httpx.Client(timeout=self._timeout) as client:
            for text in texts:
                resp = client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model, "prompt": text},
                )
                resp.raise_for_status()
                out.append(list(resp.json()["embedding"]))
        return out
