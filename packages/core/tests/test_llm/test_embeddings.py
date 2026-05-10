"""Slice 9 — pluggable embedding provider.

Used by the graph memory subsystem (slice 10+) to embed UserConstruct
statements and artifact summaries for vector recall (slice 12). Tests
exercise the public ``embed`` contract:

* Input: list of strings.
* Output: list of equal-length float vectors, one per input, with a
  stable ``dim`` matching the provider's model.

The OpenAI HTTP call is mocked via respx so we can assert the request
shape without a live API key.
"""

from __future__ import annotations

import httpx
import respx
from openlia.llm.embeddings import FakeEmbeddingProvider, OpenAIEmbeddingProvider


def test_fake_provider_returns_one_vector_per_input() -> None:
    """The fake provider is used by every downstream test to avoid
    network calls; verifying its shape catches regressions in the
    Protocol that would otherwise hide behind mocks elsewhere."""
    provider = FakeEmbeddingProvider(dim=8)

    out = provider.embed(["hello", "world", "third"])

    assert len(out) == 3
    assert all(len(v) == 8 for v in out)
    assert provider.dim == 8


@respx.mock
def test_openai_provider_calls_embeddings_endpoint_and_parses_vectors() -> None:
    route = respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [
                    {"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"object": "embedding", "index": 1, "embedding": [0.4, 0.5, 0.6]},
                ],
            },
        )
    )

    provider = OpenAIEmbeddingProvider(api_key="test", model="text-embedding-3-small")
    out = provider.embed(["a", "b"])

    assert route.called
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer test"
    assert b"text-embedding-3-small" in sent.content
    assert out == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_openai_provider_dim_matches_known_models() -> None:
    """Embedding dim is fixed per model and is what slice-10's storage
    layer uses to size BLOB columns / detect re-embedding needs after a
    model swap. Get the constants wrong here and silent drift follows."""
    assert OpenAIEmbeddingProvider(api_key="x", model="text-embedding-3-small").dim == 1536
    assert OpenAIEmbeddingProvider(api_key="x", model="text-embedding-3-large").dim == 3072
