"""Chat runtime translates LLMChunk.server_tool_event into the
ChatWebSearchInvoked / ChatWebSearchCompleted SSE events that the UI
consumes to show "Searching..." status and citation chips. The
adapters do the native-protocol parsing; the runtime stays
protocol-agnostic and just relays."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import (
    ChatDone,
    ChatToken,
    ChatWebSearchCompleted,
    ChatWebSearchInvoked,
)
from openlia.llm.runtime.messages import ChatMessage
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    ProviderCredentials,
    ResolvedModel,
    ServerToolEvent,
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
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
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


async def test_server_tool_event_invoked_yields_chat_web_search_invoked(
    prompts_root: Path,
) -> None:
    """An LLMChunk with `server_tool_event.kind == "invoked"` causes
    the ChatRunner to emit a `ChatWebSearchInvoked` SSE event before
    the token stream resumes."""
    chunks = [
        LLMChunk(
            delta="",
            server_tool_event=ServerToolEvent(
                kind="invoked", provider="anthropic", query="NVDA earnings"
            ),
        ),
        LLMChunk(
            delta="",
            server_tool_event=ServerToolEvent(
                kind="completed",
                provider="anthropic",
                urls=("https://reuters.com/a", "https://ft.com/b"),
                n_results=2,
            ),
        ),
        LLMChunk(delta="Done", finish_reason="stop"),
    ]
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final", ""), ("stream_chunks", chunks)])
    )
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"secretary": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )

    invoked = [e for e in events if isinstance(e, ChatWebSearchInvoked)]
    completed = [e for e in events if isinstance(e, ChatWebSearchCompleted)]
    assert len(invoked) == 1
    assert invoked[0].query == "NVDA earnings"
    assert invoked[0].provider == "anthropic"
    assert invoked[0].message_id == "m_1"

    assert len(completed) == 1
    assert completed[0].n_results == 2
    assert completed[0].urls == ["https://reuters.com/a", "https://ft.com/b"]
    assert completed[0].provider == "anthropic"

    # And the tokens still flow.
    tokens = [e for e in events if isinstance(e, ChatToken)]
    assert "".join(t.text for t in tokens) == "Done"
    assert any(isinstance(e, ChatDone) for e in events)


async def test_chunk_without_server_tool_event_emits_no_web_search_frames(
    prompts_root: Path,
) -> None:
    """Plain text streams must not produce any ChatWebSearch* events."""
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final", ""), ("tokens", ["Hello"])])
    )
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"secretary": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_x",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )
    assert not any(
        isinstance(e, (ChatWebSearchInvoked, ChatWebSearchCompleted)) for e in events
    )
