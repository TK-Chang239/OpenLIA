"""Server-layer web search resolver delegates to the runtime
`resolve_web_search` contract.

Previously the server returned `WebSearchResolution(available=False,
variant=None, adapter=None)` unconditionally as a stub. That meant the
native variant was never selected even for models whose capabilities
advertise it, so the provider never received the native web_search tool
and provider dashboards showed zero web_search billable units.

The fix: the server-layer resolver consults the runtime's
`resolve_web_search`, which honors both the model's capabilities and
the env-flag kill switch. The configured-adapter factory is `None`
until Phase 9 rewires connector-based search, but the native path
needs no adapter and must work today.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel


def _resolved(*, web_search_native: bool, provider_kind: str = "anthropic") -> ResolvedModel:
    return ResolvedModel(
        provider_kind=provider_kind,
        provider_id="p1",
        model_id="m1",
        model_ref="x-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True,
            tool_calling=True,
            structured_output=True,
            web_search_native=web_search_native,
        ),
        overrides={},
    )


def test_resolver_returns_native_when_model_supports_it() -> None:
    """A native-capable model must yield variant='native' so the report
    and chat runners forward `native_tools=('web_search',)` to the
    provider, which then runs the search server-side and bills the
    user for it."""
    from openlia_server.services.runtime import _resolve_web_search_for

    result = _resolve_web_search_for(resolved=_resolved(web_search_native=True))

    assert isinstance(result, WebSearchResolution)
    assert result.available is True
    assert result.variant == "native"


def test_resolver_returns_unavailable_when_model_lacks_native_and_no_configured_adapter() -> None:
    """A model without native web search and no configured adapter
    falls through to `available=False`. Today this is the path for
    `web_search_native=False` models because Phase 9's configured
    connector dispatcher is not yet wired."""
    from openlia_server.services.runtime import _resolve_web_search_for

    result = _resolve_web_search_for(resolved=_resolved(web_search_native=False))

    assert result.available is False
    assert result.variant is None


def test_resolver_respects_disable_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """`OPENLIA_DISABLE_NATIVE_WEB_SEARCH=1` must prevent the native
    variant from being selected even for a native-capable model. This
    is the production-emergency kill switch."""
    from openlia_server.services.runtime import _resolve_web_search_for

    monkeypatch.setenv("OPENLIA_DISABLE_NATIVE_WEB_SEARCH", "1")

    result = _resolve_web_search_for(resolved=_resolved(web_search_native=True))

    assert result.variant != "native"
    assert result.available is False
