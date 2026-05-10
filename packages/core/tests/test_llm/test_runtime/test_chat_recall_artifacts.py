"""Slice 12 — recall_artifacts integration with ChatRunner.

Verifies the runner exposes the tool schema when a handler is wired,
dispatches calls through the handler with the runtime-context user_id
(never the LLM-supplied args), and forwards the compact result payload
back to the model as a tool message.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import (
    ChatDone,
    ChatToolCallResult,
    ChatToolCallStart,
)
from openlia.llm.runtime.messages import ChatMessage
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.recall_artifacts import RECALL_ARTIFACTS_TOOL_NAME
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
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
        tier=ModelTier.EVERYDAY,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


class _Registry:
    def get_department_tier_override(self, department_id: str):
        return None

    def get_user_preference(self, user_id, tier):
        return None

    def get_tier_default(self, tier):
        return None

    def get_any_in_tier(self, tier):
        return None


def _always_resolved():
    resolved = _resolved()

    def _resolve(*, department_id, user_id, registry, tier_override=None, model_id_override=None):
        return resolved

    return _resolve


async def _collect(it):
    return [e async for e in it]


async def test_recall_artifacts_schema_exposed_when_handler_wired(prompts_root: Path) -> None:
    """The runner should advertise the recall_artifacts tool to the model
    when a handler has been wired, and not when it has not."""
    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))
    data = FakeDataDispatcher(manifest={"secretary": {}})

    async def handler(user_id, query, top_k):
        return []

    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        recall_artifacts=handler,
    )
    await _collect(
        runner.run(
            department_id="secretary",
            user_id="alice",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )

    # The first generate() call carries the tool list the model sees.
    first_request = provider.captured_requests[0]
    tool_names = {t.name for t in (first_request.tools or [])}
    assert RECALL_ARTIFACTS_TOOL_NAME in tool_names


async def test_recall_artifacts_not_exposed_without_handler(prompts_root: Path) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))
    data = FakeDataDispatcher(manifest={"secretary": {}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
    )
    await _collect(
        runner.run(
            department_id="secretary",
            user_id="alice",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )

    first_request = provider.captured_requests[0]
    tool_names = {t.name for t in (first_request.tools or [])}
    assert RECALL_ARTIFACTS_TOOL_NAME not in tool_names


async def test_recall_artifacts_dispatches_with_context_user_id(prompts_root: Path) -> None:
    """When the model calls recall_artifacts, the runner must invoke the
    injected handler with the user_id from its request context. An
    attempt by the model to pass a different user_id in the args is
    silently ignored."""
    call = ToolCall(
        id="c1",
        name=RECALL_ARTIFACTS_TOOL_NAME,
        # The malicious LLM tries to spoof a victim id.
        arguments={"query": "nvidia", "top_k": 2, "user_id": "victim"},
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final", ""),
                ("tokens", ["done"]),
            ]
        )
    )
    data = FakeDataDispatcher(manifest={"secretary": {}})

    captured: dict[str, object] = {}

    async def handler(user_id, query, top_k):
        captured["user_id"] = user_id
        captured["query"] = query
        captured["top_k"] = top_k
        return [{"id": "r1", "subject": "NVDA", "tagline": "growth", "score": 0.95}]

    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        recall_artifacts=handler,
    )

    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="alice",
            messages=[ChatMessage(role="user", content="find my nvidia notes")],
        )
    )

    # Handler was invoked with the request-context user_id.
    assert captured["user_id"] == "alice"
    assert captured["query"] == "nvidia"
    assert captured["top_k"] == 2

    # Emitted tool-call start/result for recall_artifacts.
    starts = [e for e in events if isinstance(e, ChatToolCallStart)]
    results = [e for e in events if isinstance(e, ChatToolCallResult)]
    assert any(e.tool_name == RECALL_ARTIFACTS_TOOL_NAME for e in starts)
    assert any(e.ok for e in results)
    assert any(isinstance(e, ChatDone) for e in events)

    # The tool result payload was appended to the conversation that
    # went back to the model — find the second generate() request and
    # verify a tool message with the compact rows is present.
    second_request = provider.captured_requests[1]
    tool_msgs = [m for m in second_request.messages if m.role == "tool"]
    assert tool_msgs, "expected a tool-role reply in the second turn"
    payload = json.loads(tool_msgs[-1].content)
    assert payload["results"][0]["subject"] == "NVDA"


async def test_recall_artifacts_empty_corpus_clean(prompts_root: Path) -> None:
    """Empty corpus → ok=True with results: []. No error event."""
    call = ToolCall(
        id="c1",
        name=RECALL_ARTIFACTS_TOOL_NAME,
        arguments={"query": "anything"},
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final", ""),
                ("tokens", ["done"]),
            ]
        )
    )
    data = FakeDataDispatcher(manifest={"secretary": {}})

    async def handler(user_id, query, top_k):
        return []

    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        recall_artifacts=handler,
    )

    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="alice",
            messages=[ChatMessage(role="user", content="find anything")],
        )
    )

    results = [e for e in events if isinstance(e, ChatToolCallResult)]
    assert results and results[0].ok

    second_request = provider.captured_requests[1]
    tool_msgs = [m for m in second_request.messages if m.role == "tool"]
    payload = json.loads(tool_msgs[-1].content)
    assert payload == {"results": []}
