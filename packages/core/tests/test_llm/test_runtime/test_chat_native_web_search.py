"""ChatRunner forwards `native_tools` and `web_search_max_uses` to the
provider via `LLMRequest`, mirroring what ReportRunner does. Without
this, even when the server resolves `WebSearchResolution(variant="native")`
the provider never receives the native web_search tool block and the
model has no way to invoke it. Result: zero provider-side web_search
invocations and zero billable units.

We assert on the outgoing protocol (`provider.captured_requests`) rather
than internal state so the test survives refactors of the chat runner's
internals as long as the contract with the provider holds.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.messages import ChatMessage
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
)
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

pytestmark = pytest.mark.asyncio


def _empty_skill_registry(root: Path) -> SkillRegistry:
    fs = FilesystemSkillStore(root=root)
    return SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    root.mkdir()
    (root / "secretary.yaml").write_text(
        dedent(
            """\
            chat:
              system: You are the Secretary.
            """
        )
    )
    return root


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True,
            tool_calling=True,
            structured_output=True,
            web_search_native=True,
        ),
        overrides={},
    )


class _Registry:
    pass


def _always_resolved(*, resolved: ResolvedModel):
    def _resolve(*, department_id, user_id, registry, model_id_override=None):
        return resolved

    return _resolve


async def _collect(it):
    return [e async for e in it]


def _build_runner(
    *,
    prompts_root: Path,
    provider: FakeProvider,
    variant: str | None,
) -> ChatRunner:
    return ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"secretary": {}}),
            web_search=WebSearchResolution(
                available=variant is not None,
                variant=variant,
                adapter=None,
            ),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
    )


async def test_chat_streaming_request_carries_native_web_search_when_variant_native(
    prompts_root: Path,
) -> None:
    """The legacy v1 streaming path (final-text turn) goes through
    `provider.stream(LLMRequest(...))`. When the dispatcher's web
    search resolution is native, this streaming request must declare
    `native_tools=("web_search",)` so the adapter swaps in the
    provider-native tool block before sending."""
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])])
    )
    runner = _build_runner(prompts_root=prompts_root, provider=provider, variant="native")

    await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )

    assert provider.captured_requests, "provider received no request"
    streaming_request = provider.captured_requests[-1]
    assert streaming_request.native_tools == ("web_search",)


async def test_chat_streaming_request_omits_native_web_search_when_variant_not_native(
    prompts_root: Path,
) -> None:
    """When web search is configured (adapter-based) or unavailable,
    `native_tools` must stay empty so the adapter does NOT add a native
    tool block (would either duplicate the configured tool, guardrail
    G-6, or expose a tool the user hasn't paid for)."""
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])])
    )
    runner = _build_runner(prompts_root=prompts_root, provider=provider, variant=None)

    await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )

    assert provider.captured_requests
    streaming_request = provider.captured_requests[-1]
    assert streaming_request.native_tools == ()
