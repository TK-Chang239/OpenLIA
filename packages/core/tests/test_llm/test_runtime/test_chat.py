from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
)
from openlia.llm.runtime.messages import ChatMessage
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
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
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


class _Registry:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises


def _always_resolved(*, resolved: ResolvedModel):
    def _resolve(*, department_id, user_id, registry, model_id_override=None):
        return resolved

    return _resolve


def _always_raises():
    def _resolve(*, department_id, user_id, registry, model_id_override=None):
        raise ModelNotConfiguredError(slot_kind="department", slot_id="secretary")

    return _resolve


async def _collect(it):
    return [e async for e in it]


async def test_streams_simple_reply_with_no_tools(prompts_root: Path) -> None:
    # Secretary exposes the `suggest_redirect` extra tool, so the runner
    # opens a tool-loop turn first; the model returns no calls -> streaming.
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final", ""), ("tokens", ["Hi", " there"])])
    )
    data = FakeDataDispatcher(manifest={"secretary": {}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
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
            messages=[ChatMessage(role="user", content="hello")],
        )
    )
    types = [type(e) for e in events]
    assert types[0] is ChatStart
    assert ChatToken in types
    assert types[-1] is ChatDone
    tokens = [e.text for e in events if isinstance(e, ChatToken)]
    assert "".join(tokens) == "Hi there"


async def test_tool_calling_turn_emits_tool_events(prompts_root: Path) -> None:
    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final", ""),
                ("tokens", ["AAPL", " is", " up"]),
            ]
        )
    )
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Stock quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(
        manifest=manifest,
        results={"stock_quote": {"symbol": "AAPL", "price": 190}},
    )
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
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
            messages=[ChatMessage(role="user", content="AAPL?")],
        )
    )
    types = [type(e) for e in events]
    assert ChatToolCallStart in types
    assert ChatToolCallResult in types
    assert ChatDone in types


async def test_model_not_configured_emits_chat_error_and_stops(prompts_root: Path) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[]))
    data = FakeDataDispatcher(manifest={"secretary": {}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_raises(),
        registry=_Registry(raises=True),
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
    types = [type(e) for e in events]
    assert types == [ChatStart, ChatError]
    err = events[-1]
    assert isinstance(err, ChatError)
    assert err.error_class == "ModelNotConfiguredError"
    assert "secretary" in err.message


async def test_cancellation_stops_yielding_without_terminal_event(
    prompts_root: Path,
) -> None:
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("final", ""), ("tokens", ["A", "B", "C", "D", "E"])])
    )
    data = FakeDataDispatcher(manifest={"secretary": {}})
    token = CancellationToken()
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
    )
    events: list[Any] = []
    async for e in runner.run(
        department_id="secretary",
        user_id="u_1",
        messages=[ChatMessage(role="user", content="hi")],
        cancel_token=token,
    ):
        events.append(e)
        if isinstance(e, ChatToken) and e.text == "B":
            token.cancel()
    assert ChatDone not in [type(e) for e in events]
    assert ChatError not in [type(e) for e in events]
    tokens_seen = [e.text for e in events if isinstance(e, ChatToken)]
    assert "E" not in tokens_seen


async def test_user_message_includes_prior_history(prompts_root: Path) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))
    data = FakeDataDispatcher(manifest={"secretary": {}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
    )
    await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[
                ChatMessage(role="user", content="hi"),
                ChatMessage(role="assistant", content="hello"),
                ChatMessage(role="user", content="what's up?"),
            ],
        )
    )
    req = provider.captured_requests[0]
    contents = [m.content for m in req.messages]
    # Last user message is wrapped in <user_input> tags at the provider layer (A.1).
    # Earlier user messages are passed through unchanged.
    assert contents == ["hi", "hello", "<user_input>what's up?</user_input>"]


async def test_two_round_tool_loop_appends_both_results(prompts_root: Path) -> None:
    call_a = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    call_b = ToolCall(id="c2", name="stock_quote", arguments={"symbol": "MSFT"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call_a]),
                ("tool_calls", [call_b]),
                ("final", ""),
                ("tokens", ["Both done"]),
            ]
        )
    )
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(
        manifest=manifest,
        results={"stock_quote": {"price": 100}},
    )
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
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
            messages=[ChatMessage(role="user", content="AAPL and MSFT?")],
        )
    )
    starts = [e for e in events if isinstance(e, ChatToolCallStart)]
    assert len(starts) == 2
    assert starts[0].call_id == "c1"
    assert starts[1].call_id == "c2"
    assert type(events[-1]) is ChatDone


async def test_max_rounds_falls_through_to_final_text(prompts_root: Path) -> None:
    from openlia.llm.runtime.tools import MAX_TOOL_TURNS

    call = ToolCall(id="cx", name="stock_quote", arguments={"symbol": "X"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[("tool_calls", [call])] * MAX_TOOL_TURNS + [("tokens", ["done"])]
        )
    )
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 1}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
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
            messages=[ChatMessage(role="user", content="go")],
        )
    )
    assert type(events[-1]) is ChatDone
    tokens = [e.text for e in events if isinstance(e, ChatToken)]
    assert "".join(tokens) == "done"


async def test_args_preview_unicode_safe(prompts_root: Path) -> None:
    """P2-NEW-5-09: args_preview must not slice mid-codepoint when the
    arguments contain multi-byte / non-ASCII characters. Python str slicing
    is codepoint-safe, so the round-trip through `_unicode_safe_truncate`
    must preserve full characters and never crash."""
    long_payload = "公司财报新闻" * 30  # 6-char unit, 30 repeats = 180 codepoints.
    call = ToolCall(id="c1", name="stock_quote", arguments={"q": long_payload})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final", ""),
                ("tokens", ["ok"]),
            ]
        )
    )
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
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
    starts = [e for e in events if isinstance(e, ChatToolCallStart)]
    assert len(starts) == 1
    preview = starts[0].args_preview
    # Must round-trip through encode/decode without a UnicodeDecodeError —
    # i.e. the truncation never lands inside a codepoint.
    preview.encode("utf-8").decode("utf-8")
    assert len(preview) <= 120


async def test_provider_error_in_tool_loop_emits_chat_error(prompts_root: Path) -> None:
    from openlia.llm.exceptions import LLMProviderError
    from openlia.llm.types import LLMRequest

    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})

    class _LoopErrorProvider(FakeProvider):
        async def generate(self, request: LLMRequest):
            if self._turn_index >= 1:
                raise LLMProviderError("mid-loop failure")
            return await super().generate(request)

    provider = _LoopErrorProvider(script=FakeProviderScript(turns=[("tool_calls", [call])]))
    manifest = {
        "secretary": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 1}})
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
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
            messages=[ChatMessage(role="user", content="AAPL?")],
        )
    )
    assert type(events[-1]) is ChatError
    assert "mid-loop failure" in events[-1].message


# --- Phase 9: v2 routed chat path tests ---


class _StubRouterLlm:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def generate_json(self, *, prompt: str):
        self.call_count += 1
        if not self._responses:
            return []
        return self._responses.pop(0)


class _StubDispatcher:
    def __init__(self, candidates: list[dict], dispatch_results: dict | None = None) -> None:
        self._candidates = candidates
        self._dispatch_results = dispatch_results or {}
        self.dispatched: list[tuple[str, dict]] = []

    def candidate_tools(self) -> list[dict]:
        return list(self._candidates)

    def in_department(self, dept: str):
        class _Ctx:
            async def __aenter__(self_inner):
                return None

            async def __aexit__(self_inner, *exc):
                return False

        return _Ctx()

    async def dispatch_tool_use(self, prefixed_name: str, arguments: dict):
        self.dispatched.append((prefixed_name, arguments))
        return self._dispatch_results.get(prefixed_name, {"called": prefixed_name})


_V2_CANDIDATES = [
    {
        "name": "eodhd__get_quote",
        "description": "Latest quote",
        "input_schema": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "fmp__get_company_profile",
        "description": "Company profile",
        "input_schema": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "newsapi_ai__search",
        "description": "News search",
        "input_schema": {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
    },
]


async def test_v2_router_happy_path_passes_subset_to_main_llm(prompts_root: Path) -> None:
    # Router picks eodhd__get_quote; main LLM emits no tool_calls and streams
    # final text. Verify the main-LLM tool list contains the routed pick PLUS
    # the escalation tool, and that the system prompt has the cache breakpoint
    # marker placed before the tool section.
    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["hi"])]))
    router = _StubRouterLlm([["eodhd__get_quote"]])
    dispatcher = _StubDispatcher(_V2_CANDIDATES)
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        dispatcher=dispatcher,
        router_llm_client=router,
        routing_context_loader=lambda dept: f"context for {dept}",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="AAPL?")],
        )
    )
    # Router was invoked exactly once at conversation start.
    assert router.call_count == 1
    # Main-LLM request had routed tool + escalation tool.
    main_request = provider.captured_requests[0]
    tool_names = {t.name for t in (main_request.tools or [])}
    assert "eodhd__get_quote" in tool_names
    assert "request_additional_tools" in tool_names
    assert "fmp__get_company_profile" not in tool_names
    # Cache breakpoint marker placed before tool section in system prompt.
    from openlia.llm.runtime.chat import CACHE_BREAKPOINT_MARKER

    assert main_request.system is not None
    assert CACHE_BREAKPOINT_MARKER in main_request.system
    assert main_request.system.index(CACHE_BREAKPOINT_MARKER) < main_request.system.index(
        "eodhd__get_quote"
    )
    assert type(events[-1]) is ChatDone


async def test_v2_escalation_grows_tool_set_and_summarizes(prompts_root: Path) -> None:
    # Round 1: router returns ["eodhd__get_quote"]. Main LLM emits an
    # escalation call. Router re-invoked, returns ["fmp__get_company_profile"].
    # Round 2: main LLM emits no tool_calls, streams final text.
    escalation_call = ToolCall(
        id="esc_1",
        name="request_additional_tools",
        arguments={"reason": "I need company profile"},
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [escalation_call]),
                ("final", ""),
                ("tokens", ["done"]),
            ]
        )
    )
    router = _StubRouterLlm(
        [
            ["eodhd__get_quote"],  # initial route
            ["fmp__get_company_profile"],  # escalation route
        ]
    )
    dispatcher = _StubDispatcher(_V2_CANDIDATES)
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        dispatcher=dispatcher,
        router_llm_client=router,
        routing_context_loader=lambda dept: f"context for {dept}",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="AAPL?")],
        )
    )
    assert router.call_count == 2
    # Second main-LLM request should now have BOTH routed tools.
    second_request = provider.captured_requests[1]
    tool_names_second = {t.name for t in (second_request.tools or [])}
    assert "eodhd__get_quote" in tool_names_second
    assert "fmp__get_company_profile" in tool_names_second
    assert "request_additional_tools" in tool_names_second
    # Tool result for the escalation should describe what was added.
    results = [e for e in events if isinstance(e, ChatToolCallResult)]
    assert any("fmp__get_company_profile" in r.summary for r in results)
    assert type(events[-1]) is ChatDone


async def test_v2_disable_runtime_routing_skips_router(prompts_root: Path, monkeypatch) -> None:
    # When dept.disable_runtime_routing=True, router must not be called and
    # the escalation tool must NOT be present in the main LLM's tool list.
    from openlia import departments as depts_pkg

    secretary = depts_pkg.get_department("secretary")
    monkeypatch.setattr(type(secretary), "disable_runtime_routing", True, raising=False)

    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))

    class _Sentinel:
        async def generate_json(self, *, prompt: str):
            raise AssertionError("router must not be invoked when disabled")

    dispatcher = _StubDispatcher(_V2_CANDIDATES)
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        dispatcher=dispatcher,
        router_llm_client=_Sentinel(),
        routing_context_loader=lambda dept: "ctx",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )
    main_request = provider.captured_requests[0]
    tool_names = {t.name for t in (main_request.tools or [])}
    # Full pool is exposed; escalation tool is omitted.
    assert "eodhd__get_quote" in tool_names
    assert "fmp__get_company_profile" in tool_names
    assert "newsapi_ai__search" in tool_names
    assert "request_additional_tools" not in tool_names
    assert type(events[-1]) is ChatDone


async def test_run_threads_disabled_skill_ids_into_system_prompt(
    prompts_root: Path,
) -> None:
    """Per-session opt-out: skills in `disabled_skill_ids` must not appear
    in the rendered chat.system prompt's skills_menu."""
    # Seed a skill on disk so the registry has something to filter.
    skills_root = prompts_root / "_skills_with_one"
    user_dir = skills_root / "user" / "demo-skill"
    user_dir.mkdir(parents=True)
    (user_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: a demo\n"
        'version: "1.0.0"\n'
        "departments: [secretary]\n"
        "---\n"
        "Body.\n"
    )

    from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

    fs = FilesystemSkillStore(root=skills_root)
    skill_reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await skill_reg.refresh(user_ids=["u_1"])

    # Re-render the secretary prompt to include a skills_menu reference
    # (the test prompt root is minimal — patch in a richer one).
    (prompts_root / "secretary.yaml").write_text(
        "chat:\n"
        "  system: |\n"
        "    secretary system\n"
        "    skills:\n"
        "    {% for s in skills_menu %}- {{ s.id }}\n"
        "    {% endfor %}\n"
    )

    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=skill_reg,
        message_id_factory=lambda: "m_1",
    )
    await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
            disabled_skill_ids=frozenset({"demo-skill"}),
        )
    )
    sys_prompt = provider.captured_requests[0].system or ""
    assert "demo-skill" not in sys_prompt


async def test_v2_replays_assistant_tool_calls_and_sets_tool_call_id(
    prompts_root: Path,
) -> None:
    # OpenRouter/OpenAI/Anthropic all reject a `tool` message that doesn't
    # pair with a prior assistant `tool_use`/`tool_calls` block carrying
    # the same id. Verify the v2 loop both replays the assistant turn AND
    # tags each tool message with its originating tool_call_id.
    quote_call = ToolCall(id="qc_1", name="eodhd__get_quote", arguments={"symbol": "AAPL"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [quote_call]),
                ("final", ""),
                ("tokens", ["done"]),
            ]
        )
    )
    router = _StubRouterLlm([["eodhd__get_quote"]])
    dispatcher = _StubDispatcher(
        _V2_CANDIDATES, dispatch_results={"eodhd__get_quote": {"price": 200}}
    )
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        dispatcher=dispatcher,
        router_llm_client=router,
        routing_context_loader=lambda dept: f"context for {dept}",
    )
    await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="AAPL?")],
        )
    )
    # Second main-LLM request must replay: user, assistant(tool_calls), tool(result).
    second = provider.captured_requests[1]
    roles = [m.role for m in second.messages]
    assert "assistant" in roles, f"missing assistant turn in {roles}"
    assistant = next(m for m in second.messages if m.role == "assistant")
    assert any(tc.id == "qc_1" for tc in assistant.tool_calls)
    tool_msg = next(m for m in second.messages if m.role == "tool")
    assert tool_msg.tool_call_id == "qc_1"


async def test_v2_exposes_dept_extra_tools_and_echoes_them(prompts_root: Path) -> None:
    # Secretary's extra_tools (suggest_redirect, save_report_to_repo) must
    # appear in the v2 main-LLM tool list AND, when called, be dispatched as
    # a structured echo (NOT routed through the connector dispatcher).
    suggest_call = ToolCall(
        id="sr_1",
        name="suggest_redirect",
        arguments={"department": "equity_research", "reason": "deeper dive"},
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [suggest_call]),
                ("final", ""),
                ("tokens", ["ok"]),
            ]
        )
    )
    router = _StubRouterLlm([["eodhd__get_quote"]])
    dispatcher = _StubDispatcher(_V2_CANDIDATES)
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        dispatcher=dispatcher,
        router_llm_client=router,
        routing_context_loader=lambda dept: f"context for {dept}",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )
    main_request = provider.captured_requests[0]
    tool_names = {t.name for t in (main_request.tools or [])}
    assert "suggest_redirect" in tool_names
    assert "save_report_to_repo" in tool_names
    # Extra-tool call must NOT touch the connector dispatcher.
    assert dispatcher.dispatched == []
    # Result event must echo the LLM's args as a structured payload so the
    # frontend can render the redirect card.
    results = [e for e in events if isinstance(e, ChatToolCallResult)]
    sr = next(r for r in results if r.call_id == "sr_1")
    assert sr.ok is True
    assert sr.structured == {"department": "equity_research", "reason": "deeper dive"}


async def test_v2_dispatch_serializes_pydantic_style_tool_results(
    prompts_root: Path,
) -> None:
    # Firecrawl's `search` returns a `SearchData` object. The Anthropic /
    # OpenAI adapters require the conversation's role=tool message content
    # to be a JSON-encoded string, so a non-dict / non-JSON-native return
    # value must be coerced before json.dumps. Without coercion the chat
    # turn dies with `TypeError: Object of type SearchData is not JSON
    # serializable` and the user sees no answer.
    import json as _json

    class _FakeSearchData:
        """Mimics firecrawl-py's SearchData shape: pydantic-like."""

        def __init__(self) -> None:
            self.web = [{"url": "https://example.com", "title": "Example"}]

        def model_dump(self) -> dict:
            return {"web": list(self.web)}

    quote_call = ToolCall(id="qc_1", name="firecrawl__search", arguments={"query": "openai"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [quote_call]),
                ("final", ""),
                ("tokens", ["done"]),
            ]
        )
    )
    candidates = [
        {
            "name": "firecrawl__search",
            "description": "Search the web",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        }
    ]
    router = _StubRouterLlm([["firecrawl__search"]])
    dispatcher = _StubDispatcher(
        candidates, dispatch_results={"firecrawl__search": _FakeSearchData()}
    )
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        dispatcher=dispatcher,
        router_llm_client=router,
        routing_context_loader=lambda dept: f"context for {dept}",
    )
    # Should NOT raise TypeError during dispatch.
    await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="search openai")],
        )
    )
    # The replayed conversation in the second main-LLM call must include a
    # tool message whose content parses back as JSON containing the
    # model_dump'd shape.
    second = provider.captured_requests[1]
    tool_msg = next(m for m in second.messages if m.role == "tool")
    parsed = _json.loads(tool_msg.content)
    assert parsed.get("web") == [{"url": "https://example.com", "title": "Example"}]


async def test_v2_dispatch_serializes_dataclass_tool_results(
    prompts_root: Path,
) -> None:
    # Generalize: any object exposing __dict__ (dataclass / plain) should
    # round-trip via the boundary's _to_jsonable helper without raising.
    import json as _json
    from dataclasses import dataclass

    @dataclass
    class _Quote:
        symbol: str
        price: float

    quote_call = ToolCall(id="qc_2", name="eodhd__get_quote", arguments={"symbol": "AAPL"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [quote_call]),
                ("final", ""),
                ("tokens", ["ok"]),
            ]
        )
    )
    router = _StubRouterLlm([["eodhd__get_quote"]])
    dispatcher = _StubDispatcher(
        _V2_CANDIDATES,
        dispatch_results={"eodhd__get_quote": _Quote(symbol="AAPL", price=200.5)},
    )
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        dispatcher=dispatcher,
        router_llm_client=router,
        routing_context_loader=lambda dept: f"context for {dept}",
    )
    await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="AAPL?")],
        )
    )
    second = provider.captured_requests[1]
    tool_msg = next(m for m in second.messages if m.role == "tool")
    parsed = _json.loads(tool_msg.content)
    assert parsed["symbol"] == "AAPL"
    assert parsed["price"] == 200.5


async def test_v2_dispatch_formats_missing_required_arg_as_structured_payload(
    prompts_root: Path,
) -> None:
    # When the dispatcher raises MissingRequiredArgumentError (a
    # pre-dispatch constraint violation, e.g. EODHD financial_news called
    # with neither `s` nor `t`), `_dispatch_v2_call` must surface a
    # structured error payload (with a `missing` list and a hint), not an
    # opaque string. This lets the model self-correct on its next turn.
    import json as _json

    from openlia.connectors.dispatch import MissingRequiredArgumentError

    class _RaisingDispatcher(_StubDispatcher):
        async def dispatch_tool_use(self, prefixed_name: str, arguments: dict):
            self.dispatched.append((prefixed_name, arguments))
            raise MissingRequiredArgumentError(prefixed_name, ("s", "t"))

    bad_call = ToolCall(id="bn_1", name="eodhd__financial_news", arguments={})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [bad_call]),
                ("final", ""),
                ("tokens", ["sorry"]),
            ]
        )
    )
    candidates = [
        {
            "name": "eodhd__financial_news",
            "description": "Fetch financial news. Need s or t.",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    router = _StubRouterLlm([["eodhd__financial_news"]])
    dispatcher = _RaisingDispatcher(candidates)
    runner = ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
        dispatcher=dispatcher,
        router_llm_client=router,
        routing_context_loader=lambda dept: f"context for {dept}",
    )
    events = await _collect(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="any news?")],
        )
    )
    results = [e for e in events if isinstance(e, ChatToolCallResult)]
    fn = next(r for r in results if r.call_id == "bn_1")
    assert fn.ok is False
    second = provider.captured_requests[1]
    tool_msg = next(m for m in second.messages if m.role == "tool")
    parsed = _json.loads(tool_msg.content)
    assert parsed.get("missing") == ["s", "t"]
    assert "hint" in parsed
    assert "error" in parsed
