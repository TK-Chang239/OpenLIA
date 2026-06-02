"""Provider batch-transport abstraction.

The provider Batch APIs (OpenAI, Anthropic) process requests
asynchronously at ~50% of live token price. This module defines the
provider-agnostic surface the EU batch orchestrator drives:

  - ``BatchRequestItem`` / ``BatchResultItem`` — one in/out entry per run,
    keyed by ``custom_id`` (the orchestrator's per-run handle).
  - ``BatchStatus`` — normalized lifecycle state across providers.
  - ``BatchTransport`` — submit / poll / fetch / cancel one batch.
  - ``supports_batch`` — whether a (provider_kind, model) pair has a batch
    path; callers fall back to the live API when it does not.

Concrete transports live in ``adapters/openai_batch.py`` and
``adapters/anthropic_batch.py``. The request body each submits is built
with the SAME translation the live adapters use, so a batched turn is
byte-for-byte the live request minus the transport.

``provider_kind`` here is the settings-level kind ("openai", "anthropic",
...), not an adapter ``kind`` like "openai_responses". The factory maps a
supported kind to the right transport (OpenAI -> Responses batch).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from openlia.llm.types import LLMRequest, LLMResponse


@dataclass(frozen=True)
class BatchRequestItem:
    """One request in a batch, tagged with the orchestrator's run handle."""

    custom_id: str
    request: LLMRequest


class BatchStatus(StrEnum):
    """Normalized batch lifecycle state.

    Provider-native statuses map onto these four: anything still working
    is ``IN_PROGRESS``; a finished-with-results batch is ``COMPLETED``;
    a provider-level error or cancellation is ``FAILED``; a batch that
    blew its completion window is ``EXPIRED``.
    """

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class BatchResultItem:
    """One result, keyed back to its ``custom_id``.

    Exactly one of ``response`` / ``error`` is set: ``response`` on a
    succeeded item, ``error`` (a short message) on a per-item failure.
    """

    custom_id: str
    response: LLMResponse | None
    error: str | None


@runtime_checkable
class BatchTransport(Protocol):
    """Submit one batch, poll it, fetch its results, or cancel it."""

    async def submit_batch(self, items: list[BatchRequestItem]) -> str:
        """Submit a batch; return the provider batch id."""
        ...

    async def poll_batch(self, batch_id: str) -> BatchStatus:
        """Return the batch's current normalized status."""
        ...

    async def fetch_results(self, batch_id: str) -> dict[str, BatchResultItem]:
        """Return results keyed by ``custom_id`` (only when COMPLETED)."""
        ...

    async def cancel_batch(self, batch_id: str) -> None:
        """Best-effort cancel of an in-flight batch."""
        ...


# Settings-level provider kinds with a wired batch transport. Others
# (openrouter, ollama, gemini) have no usable batch path in v1 and fall
# back to the live API.
_BATCH_PROVIDERS = frozenset({"openai", "anthropic"})


def supports_batch(provider_kind: str, model: str) -> bool:
    """Whether this (provider_kind, model) pair can run via the Batch API.

    ``model`` is accepted for forward compatibility (a provider may gate
    batch by model tier) but is not consulted today.
    """
    del model  # reserved for future per-model gating
    return provider_kind in _BATCH_PROVIDERS


__all__ = [
    "BatchRequestItem",
    "BatchResultItem",
    "BatchStatus",
    "BatchTransport",
    "supports_batch",
]
