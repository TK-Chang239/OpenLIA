"""Build the right ``BatchTransport`` for a settings-level provider kind.

Lives apart from ``batch_transport`` (which the transports import) to keep
the import graph acyclic. Returns ``None`` for providers without a wired
batch path so callers fall back to the live API.

The settings ``provider_kind`` ("openai") maps to the Responses batch
transport — OpenAI batch supports ``/v1/responses``, and the EU engine's
OpenAI path is Responses-based.
"""

from __future__ import annotations

from openlia.llm.adapters.anthropic_batch import AnthropicBatchTransport
from openlia.llm.adapters.openai_batch import OpenAIBatchTransport
from openlia.llm.batch_transport import BatchTransport
from openlia.llm.types import ProviderCredentials


def build_batch_transport(
    *,
    provider_kind: str,
    credentials: ProviderCredentials,
    model: str,
) -> BatchTransport | None:
    """Return a batch transport for ``provider_kind``, or ``None`` if unsupported."""
    if provider_kind == "openai":
        return OpenAIBatchTransport(credentials=credentials, model=model)
    if provider_kind == "anthropic":
        return AnthropicBatchTransport(credentials=credentials, model=model)
    return None


__all__ = ["build_batch_transport"]
