from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ProviderCredentials,
    TestResult,
)


class LLMProvider(ABC):
    kind: str = ""

    def __init__(
        self,
        *,
        credentials: ProviderCredentials,
        model: str,
        capabilities: Capabilities,
    ) -> None:
        self.credentials = credentials
        self.model = model
        self.capabilities = capabilities

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Live model list from the provider. May raise LLMProviderError."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming completion."""

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        """Streaming completion. Plan 4 stubs this; Plan 5 implements SSE."""

    @abstractmethod
    async def test_connection(self, model: str) -> TestResult:
        """1-token ping. Returns structured TestResult — does not raise."""
