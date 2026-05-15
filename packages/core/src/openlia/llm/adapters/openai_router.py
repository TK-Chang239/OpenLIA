"""OpenAIRouter: per-turn multiplexer over Chat Completions and the
Responses API.

The OpenAI ecosystem has two HTTP surfaces with different capabilities:

  * `/v1/chat/completions` — what we've always used; well-supported
    across tooling; clearest token accounting; no native web search
    for general-purpose models.
  * `/v1/responses` — the only endpoint that exposes the native
    server-side `{"type":"web_search"}` tool, plus other built-ins.

Spec decision B2: don't migrate everything. Only opt into Responses
when the runtime explicitly requests native web search via
`LLMRequest.native_tools`. Non-search turns keep paying zero
latency/cost penalty by staying on Chat Completions.

The router is transparent to the rest of the system: it reports
`kind="openai"` and implements LLMProvider, so callers see a single
adapter. The inner adapters share credentials and model; the router
selects which one to dispatch to per `generate()`/`stream()` call.

Conversation continuity across APIs is handled inside each adapter:
they both consume the same canonical Message list and render to their
own wire format. Server-side `web_search_call` items from prior
Responses turns are dropped during translation back to Chat
Completions (their text has already been integrated into the
assistant message; citations flow through LLMResponse.citations).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.adapters.openai_responses import OpenAIResponsesAdapter
from openlia.llm.base import LLMProvider
from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ProviderCredentials,
    TestResult,
)


class OpenAIRouter(LLMProvider):
    """Routes per-turn between Chat Completions and Responses API."""

    kind = "openai"

    def __init__(
        self,
        *,
        credentials: ProviderCredentials,
        model: str,
        capabilities: Capabilities,
    ) -> None:
        super().__init__(credentials=credentials, model=model, capabilities=capabilities)
        self._chat = OpenAIAdapter(
            credentials=credentials, model=model, capabilities=capabilities
        )
        self._responses = OpenAIResponsesAdapter(
            credentials=credentials, model=model, capabilities=capabilities
        )

    def _select(self, request: LLMRequest) -> LLMProvider:
        """Routing rule: native web_search → Responses; else → Chat."""
        if "web_search" in request.native_tools:
            return self._responses
        return self._chat

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return await self._select(request).generate(request)

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        async for chunk in self._select(request).stream(request):
            yield chunk

    async def list_models(self) -> list[ModelInfo]:
        # Chat Completions and Responses use the same model registry;
        # delegate to the chat adapter to avoid a duplicate call.
        return await self._chat.list_models()

    async def test_connection(self, model: str) -> TestResult:
        # Connection probe stays on Chat Completions: it's the simpler
        # endpoint, has clearer error semantics for ping-style usage,
        # and a working Chat path is a prerequisite for the Responses
        # path on the same credentials.
        return await self._chat.test_connection(model)
