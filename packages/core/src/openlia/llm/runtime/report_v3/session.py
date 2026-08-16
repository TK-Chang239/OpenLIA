"""Provider session wrapper for the v3 engine.

``LLMSession`` is the v3 facade over the existing ``LLMProvider``
abstraction. It does three things:

1. Resolves a ``Capabilities`` snapshot for the chosen provider/model
   via the existing ``capabilities_for`` registry.
2. Enforces the v3 capability contract: the model MUST support native
   web search. Providers that don't (Ollama, gpt-5.4-mini,
   claude-haiku, gemini-flash-lite at the model level) are rejected
   at construction with a clear error.
3. On first ``generate()`` call, resolves credentials from env vars
   and builds the provider adapter via ``build_adapter``. Subsequent
   calls reuse the same adapter. Tests inject a fake adapter via
   ``attach_adapter`` to skip the env / SDK path entirely.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from ...adapters import build_adapter
from ...base import LLMProvider
from ...capabilities import capabilities_for, is_known_model
from ...types import (
    Capabilities,
    LLMRequest,
    LLMResponse,
    Message,
    ProviderCredentials,
    ReasoningEffort,
    ToolSchema,
)

# Token headroom added to ``max_tokens`` when reasoning is enabled.
# Thinking tokens count against the same ceiling as visible output on
# every provider, so the ceiling must absorb both. Mirrors v2.3's
# ``_REASONING_OVERHEAD`` in v2_3_wiring.py — keep in lockstep until
# we refactor to a shared module.
_REASONING_OVERHEAD: dict[ReasoningEffort, int] = {
    ReasoningEffort.MEDIUM: 8192,
    ReasoningEffort.HIGH: 32768,
}


class CapabilityError(RuntimeError):
    """The chosen provider/model does not meet v3's capability contract.

    Fires when ``capabilities.web_search_native`` is False. v3 requires
    native web search because the engine relies on the provider's
    first-class web tool for research and citation attribution.
    """


class CredentialError(RuntimeError):
    """No API key found for the configured provider in the environment."""


# Env vars the wiring layer looks up per provider_kind. Standard names
# matching what v2.3 and the adapter layer expect. Gemini accepts either
# convention some users set.
_ENV_VAR_BY_PROVIDER: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openrouter": ("OPENROUTER_API_KEY",),
}


def _resolve_credentials(provider_kind: str, api_key: str | None = None) -> ProviderCredentials:
    # An explicit key (resolved server-side from the admin-configured provider)
    # wins over the environment so a key entered in Settings -> Models works
    # without also exporting an env var.
    if api_key:
        return ProviderCredentials(api_key=api_key, base_url=None, env_var_name=None)
    candidates = _ENV_VAR_BY_PROVIDER.get(provider_kind, ())
    for env_var in candidates:
        api_key = os.environ.get(env_var)
        if api_key:
            return ProviderCredentials(
                api_key=api_key,
                base_url=None,
                env_var_name=env_var,
            )
    raise CredentialError(
        f"No API key found for {provider_kind!r} in the environment. "
        f"Set one of: {', '.join(candidates) or '(no known env vars)'}."
    )


@dataclass
class LLMSession:
    """A v3 session bound to a specific provider/model pair.

    Construct via ``LLMSession.create()`` so the capability gate runs
    before any tools are wired. The adapter is built lazily on first
    ``generate()`` call to keep construction cheap and avoid requiring
    API keys when the session is mocked in tests.
    """

    provider_kind: str
    model: str
    capabilities: Capabilities
    _adapter: LLMProvider | None = field(default=None, repr=False, compare=False)
    _api_key: str | None = field(default=None, repr=False, compare=False)

    @classmethod
    def create(
        cls,
        *,
        provider_kind: str,
        model: str,
        capability_override: dict | None = None,
        api_key: str | None = None,
    ) -> LLMSession:
        """Resolve capabilities, run the gate, return a session.

        Raises ``CapabilityError`` if the model does not advertise
        ``web_search_native``. Ollama is the canonical rejection — no
        Ollama model currently has native web search — but the gate
        also catches gpt-5.4-mini, claude-haiku, gemini-flash-lite,
        and other hosted models that lack the capability.
        """
        capabilities = capabilities_for(
            provider_kind=provider_kind,
            model=model,
            override=capability_override,
        )
        if not capabilities.web_search_native:
            if not is_known_model(provider_kind, model):
                raise CapabilityError(
                    f"{provider_kind!r}/{model!r} is not in the capability registry, "
                    f"so it defaulted to no native web search. Set a capability "
                    f"override (Settings -> Models) marking ``web_search_native`` "
                    f"true, or pick a model with native web search "
                    f"(e.g. gpt-5.4, claude-sonnet, gemini-3.1-pro)."
                )
            raise CapabilityError(
                f"v3 requires a model with native web search. "
                f"{provider_kind!r}/{model!r} does not advertise "
                f"``web_search_native``. "
                f"Pick a different model "
                f"(e.g. gpt-5.4, claude-sonnet, gemini-3.1-pro)."
            )
        return cls(
            provider_kind=provider_kind,
            model=model,
            capabilities=capabilities,
            _api_key=api_key,
        )

    def attach_adapter(self, adapter: LLMProvider) -> None:
        """Inject a pre-built adapter (used by tests with fakes).

        Production callers go through ``generate``, which builds the
        real adapter from env credentials on first use.
        """
        self._adapter = adapter

    def _ensure_adapter(self) -> LLMProvider:
        if self._adapter is None:
            credentials = _resolve_credentials(self.provider_kind, self._api_key)
            self._adapter = build_adapter(
                kind=self.provider_kind,
                credentials=credentials,
                model=self.model,
                capabilities=self.capabilities,
            )
        return self._adapter

    async def generate(
        self,
        *,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolSchema] | None = None,
        native_tools: tuple[str, ...] = (),
        max_tokens: int | None = None,
        temperature: float = 0.4,
        reasoning_effort: ReasoningEffort | None = None,
        extra: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Send one turn to the model. Returns text + tool_calls + citations.

        Thin wrapper around the underlying provider adapter. Pass
        ``native_tools=("web_search",)`` to let the adapter wire the
        provider's first-class web tool.

        ``reasoning_effort`` enables extended thinking on the
        underlying call. When set, the effective ``max_tokens`` grows
        by ``_REASONING_OVERHEAD[effort]``, clamped to the model's
        declared ceiling, so the truncation guard
        absorbs both visible output and thinking tokens — they share
        the same ceiling on every provider. Adapters whose model
        doesn't support thinking silently drop the field.
        """
        adapter = self._ensure_adapter()
        effective_max = max_tokens or self.capabilities.max_output_tokens
        if reasoning_effort is not None:
            effective_max += _REASONING_OVERHEAD.get(reasoning_effort, 0)
        # Thinking and visible output draw from one ceiling on every provider,
        # and ``max_tokens`` is sent verbatim as the total budget. Clamp so the
        # combined budget never exceeds the model's declared ceiling — without
        # this, claude-sonnet at HIGH effort asks for 96,768 against a 64,000
        # ceiling (gpt-5.4: 160,768 vs 128,000) and the provider rejects it.
        effective_max = min(effective_max, self.capabilities.max_output_tokens)
        request = LLMRequest(
            messages=messages,
            system=system,
            tools=tools,
            max_tokens=effective_max,
            temperature=temperature,
            native_tools=native_tools,
            reasoning_effort=reasoning_effort,
            # Multi-turn tool-use loop: cache the growing prefix so each
            # turn re-reads prior tool results instead of re-billing them.
            cache_conversation=True,
        )
        del extra  # reserved for future per-provider overrides
        return await adapter.generate(request)
