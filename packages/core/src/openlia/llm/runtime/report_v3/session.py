"""Provider session wrapper for the v3 engine.

``LLMSession`` is the v3 facade over the existing ``LLMProvider``
abstraction. It does two things Phase 0 cares about:

1. Resolves a ``Capabilities`` snapshot for the chosen provider/model
   via the existing ``capabilities_for`` registry — no new capability
   table, no new lookup logic.
2. Enforces the v3 capability contract: the model MUST support native
   web search. Providers that don't (Ollama in particular, also
   gpt-5-mini and claude-haiku and gemini-flash-lite at the model
   level) are rejected at construction with a clear error.

Generation/streaming live on the underlying ``LLMProvider``; Phase 0
exposes a passthrough placeholder so the route can construct a session
and report capability gate failures end-to-end. Phase 1 adds the real
tool-use loop on top.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...capabilities import capabilities_for
from ...types import Capabilities


class CapabilityError(RuntimeError):
    """The chosen provider/model does not meet v3's capability contract.

    Currently this fires when ``capabilities.web_search_native`` is
    False. v3 requires native web search because the engine relies on
    the provider's first-class web tool for research and citation
    attribution; a configured-search fallback would defeat the whole
    architecture.
    """


@dataclass(frozen=True)
class LLMSession:
    """A v3 session bound to a specific provider/model pair.

    Construct via ``LLMSession.create()`` so the capability gate runs
    before any tools are wired or any LLM calls are made. Direct
    construction skips the gate and is only intended for tests that
    inject pre-validated capabilities.
    """

    provider_kind: str
    model: str
    capabilities: Capabilities

    @classmethod
    def create(
        cls,
        *,
        provider_kind: str,
        model: str,
        capability_override: dict | None = None,
    ) -> LLMSession:
        """Resolve capabilities, run the gate, return a session.

        Raises ``CapabilityError`` if the model does not advertise
        ``web_search_native``. Ollama is the canonical rejection — no
        Ollama model currently has native web search — but the gate
        also catches gpt-5.4-mini, claude-haiku, gemini-flash-lite and
        other hosted models that lack the capability.
        """
        capabilities = capabilities_for(
            provider_kind=provider_kind,
            model=model,
            override=capability_override,
        )
        if not capabilities.web_search_native:
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
        )
