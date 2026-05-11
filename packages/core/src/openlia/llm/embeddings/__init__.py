"""Pluggable embedding providers for the cross-session memory graph.

The graph stores summary embeddings on artifact summaries (slice 10)
and UserConstruct statements; slice-12 retrieval matches the user's
current message against those vectors via brute-force cosine.

Providers expose a tiny contract: a ``dim`` (fixed per model) and an
``embed(texts: list[str]) -> list[list[float]]`` method. Two real
implementations ship today — OpenAI cloud and Ollama local — selected
by user config / env at startup. Tests use ``FakeEmbeddingProvider``.
"""

from __future__ import annotations

from openlia.llm.embeddings.fake import FakeEmbeddingProvider
from openlia.llm.embeddings.ollama import OllamaEmbeddingProvider
from openlia.llm.embeddings.openai import OpenAIEmbeddingProvider
from openlia.llm.embeddings.types import EmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAIEmbeddingProvider",
]
