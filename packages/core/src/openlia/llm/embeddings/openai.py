"""OpenAI embeddings provider."""

from __future__ import annotations

import httpx

_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider:
    """Calls the OpenAI ``/v1/embeddings`` endpoint synchronously.

    Sync because the embedding call sites (session-idle extraction,
    artifact write) live inside service-layer transactions that are
    themselves sync. Network jitter doesn't dominate cost here —
    summary embeddings are short, batched, and rare.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com",
        timeout: float = 30.0,
    ) -> None:
        if model not in _DIMS:
            raise ValueError(f"unknown OpenAI embedding model: {model!r}")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def dim(self) -> int:
        return _DIMS[self._model]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base_url}/v1/embeddings",
                headers={
                    "authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json={"input": texts, "model": self._model},
            )
            resp.raise_for_status()
            data = resp.json()
        rows = sorted(data["data"], key=lambda r: r["index"])
        return [list(r["embedding"]) for r in rows]
